"""Phase 6: run the 30 hand-authored eval cases through the real end-to-end
pipeline (real classifier, real Claude memo draft) and report classification
accuracy, memo completeness against a rubric, and queue delivery latency.

Uses a separate SQLite file (eval_triage.db) so this doesn't mix into
whatever real triage state exists from manual testing via the Streamlit UI.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, graph  # noqa: E402

EVAL_CASES_PATH = Path("data/eval_cases.json")
CAPA_GUIDANCE_PATH = Path("data/capa_guidance.json")
EVAL_DB_PATH = Path("eval_triage.db")
RESULTS_JSON_PATH = Path("eval_results.json")
REPORT_MD_PATH = Path("eval_report.md")

MIN_WORDS = 15
MIN_CAPA_ACTIONS = 2
# Each case now makes ~7-10 real API calls across the multi-agent pipeline;
# 33 cases back-to-back with no pacing tripped a real Anthropic rate limit
# during this project's development (one call silently waited 26 minutes).
# A small pause between cases keeps total request rate well under typical
# per-minute limits without meaningfully slowing the overall run.
INTER_CASE_DELAY_SECONDS = 3


def check_evidence(case: dict, final_state: dict) -> bool | None:
    """Grades whether the agent pipeline actually found the evidence a
    case's correct category depends on -- not just whether it landed on
    the right category, which a lucky guess could also produce. Returns
    None for cases with no expected_evidence field (most of them)."""
    expected = case.get("expected_evidence")
    if not expected:
        return None
    if "material_safety_change" in expected:
        actual = (final_state.get("protocol_findings") or {}).get("material_safety_change")
        return actual == expected["material_safety_change"]
    if "pattern_detected" in expected:
        actual = (final_state.get("history_findings") or {}).get("pattern_detected")
        return actual == expected["pattern_detected"]
    return None


def score_memo(memo: dict, expected_category: str, capa_guidance: dict) -> dict:
    required_elements = set(capa_guidance.get("required_capa_elements", []))
    actions = memo.get("recommended_capa_actions", [])

    checks = {
        "summary_substantive": len(memo.get("summary", "").split()) >= MIN_WORDS,
        "root_cause_substantive": len(memo.get("root_cause_narrative", "").split()) >= MIN_WORDS,
        "capa_actions_sufficient": len(set(actions)) >= MIN_CAPA_ACTIONS,
        "capa_actions_tailored": not any(a in required_elements for a in actions),
        "expedited_flag_correct": memo.get("requires_expedited_reporting") == (expected_category == "major"),
        "ownership_fields_present": bool(memo.get("responsible_party")) and bool(memo.get("target_resolution_date")),
    }
    checks["_score"] = sum(1 for v in checks.values() if v is True) / len(checks)
    return checks


def main() -> None:
    with EVAL_CASES_PATH.open(encoding="utf-8") as f:
        cases = json.load(f)
    with CAPA_GUIDANCE_PATH.open(encoding="utf-8") as f:
        guidance_by_category = json.load(f)

    if EVAL_DB_PATH.exists():
        EVAL_DB_PATH.unlink()
    db.DB_PATH = EVAL_DB_PATH
    db.init_db()

    results = []
    for i, case in enumerate(cases, start=1):
        print(f"[{i}/{len(cases)}] {case['case_id']} (expected: {case['expected_category']})...")

        if i > 1:
            time.sleep(INTER_CASE_DELAY_SECONDS)

        initial_state = {
            "protocol_id": case["protocol_id"],
            "site_id": case["site_id"],
            "subject_id": case["subject_id"],
            "deviation_date": case["deviation_date"],
            "discovery_date": case["discovery_date"],
            "raw_text": case["text"],
        }

        start = time.time()
        final_state = graph.graph.invoke(initial_state)
        elapsed = time.time() - start

        predicted = final_state["category"]
        rubric = score_memo(final_state["memo"], case["expected_category"], guidance_by_category[predicted])
        evidence_correct = check_evidence(case, final_state)

        results.append(
            {
                "case_id": case["case_id"],
                "expected_category": case["expected_category"],
                "predicted_category": predicted,
                "correct": predicted == case["expected_category"],
                "is_boundary_case": case["is_boundary_case"],
                "confidence": final_state["confidence"],
                "elapsed_seconds": elapsed,
                "status": final_state["status"],
                "rubric": rubric,
                "evidence_correct": evidence_correct,
                "adjudication": final_state.get("adjudication"),
                "memo": final_state["memo"],
            }
        )
        evidence_note = "" if evidence_correct is None else f", evidence {'OK' if evidence_correct else 'WRONG'}"
        print(f"  -> predicted {predicted}, rubric score {rubric['_score']:.2f}{evidence_note}, {elapsed:.1f}s")

    with RESULTS_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    report = build_report(results)
    with REPORT_MD_PATH.open("w", encoding="utf-8") as f:
        f.write(report)

    print("\n" + report)
    print(f"\nWrote {RESULTS_JSON_PATH} and {REPORT_MD_PATH}")


def build_report(results: list[dict]) -> str:
    n = len(results)
    clear = [r for r in results if not r["is_boundary_case"]]
    boundary = [r for r in results if r["is_boundary_case"]]

    def accuracy(rows: list[dict]) -> float:
        return sum(1 for r in rows if r["correct"]) / len(rows) if rows else float("nan")

    rubric_keys = [k for k in results[0]["rubric"] if k != "_score"]
    rubric_pass_rates = {
        k: sum(1 for r in results if r["rubric"][k]) / n for k in rubric_keys
    }
    mean_rubric_score = statistics.mean(r["rubric"]["_score"] for r in results)

    latencies = [r["elapsed_seconds"] for r in results]

    misclassified = [r for r in results if not r["correct"]]
    evidence_checked = [r for r in results if r["evidence_correct"] is not None]
    evidence_wrong = [r for r in evidence_checked if not r["evidence_correct"]]

    lines = [
        "# Phase 6 Evaluation Report",
        "",
        f"**Cases:** {n} ({len(clear)} clear-cut, {len(boundary)} boundary)",
        "",
        "## Classification accuracy",
        f"- Overall: {accuracy(results):.1%}",
        f"- Clear-cut cases: {accuracy(clear):.1%}",
        f"- Boundary cases: {accuracy(boundary):.1%}",
        "",
        "## Memo completeness (rubric)",
        f"- Mean rubric score: {mean_rubric_score:.2f} / 1.00",
    ]
    for k, rate in rubric_pass_rates.items():
        lines.append(f"- `{k}`: {rate:.1%} pass rate")

    lines += [
        "",
        "## Evidence grounding (agentic pipeline)",
        f"- Cases with a checkable expected_evidence field: {len(evidence_checked)}",
    ]
    if evidence_checked:
        lines.append(
            f"- Correct evidence found: {len(evidence_checked) - len(evidence_wrong)}/{len(evidence_checked)}"
        )
        for r in evidence_wrong:
            lines.append(f"  - {r['case_id']}: expected evidence not found/matched by the agent pipeline")
    else:
        lines.append("- None")

    lines += [
        "",
        "## Queue delivery latency",
        f"- Mean: {statistics.mean(latencies):.2f}s",
        f"- Median: {statistics.median(latencies):.2f}s",
        f"- Max: {max(latencies):.2f}s",
        "",
        "## Misclassified cases",
    ]
    if misclassified:
        for r in misclassified:
            lines.append(
                f"- {r['case_id']} (boundary={r['is_boundary_case']}): "
                f"expected `{r['expected_category']}`, predicted `{r['predicted_category']}` "
                f"(confidence {r['confidence']:.2f})"
            )
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
