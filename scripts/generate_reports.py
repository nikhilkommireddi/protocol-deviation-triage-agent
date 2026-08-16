"""Generate a labeled dataset of clinical trial protocol deviation reports
by calling Claude Sonnet 5 to write the narrative text (Step 1.4 of the
build plan).

This is the Claude-API-backed sibling of generate_synthetic_deviations.py.
It reuses that script's entity/date generation (site/subject IDs, drug and
visit names, the unreported-category reporting-gap logic) so records stay
structurally realistic, and replaces the template-string narrative with an
LLM-written one for natural variation in voice, length, and register.

Variety comes entirely from an explicit voice/length/register grid passed
in the prompt, not from sampling temperature -- Claude Sonnet 5 rejects a
non-default `temperature` (400 error), so that lever isn't available.

Run small batches first (the default --n-per-category is deliberately
modest per category so you can eyeball output before scaling up):

    python scripts/generate_reports.py --n-per-category 5
    # inspect data/raw/claude_generated_deviations.jsonl, then:
    python scripts/generate_reports.py --n-per-category 60
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic

from generate_synthetic_deviations import (
    CATEGORIES,
    CONSENT_VERSIONS,
    DEVICE_NAMES,
    DRUG_NAMES,
    INVESTIGATORS,
    QUESTIONNAIRES,
    VISIT_NAMES,
    _make_ids,
    _random_date,
)

VOICES = [
    "formal clinical narrative, as written in a sponsor-facing deviation report",
    "terse site-coordinator note: brief, clipped, minimal embellishment",
    "monitor/auditor finding language: formal, third-person, states what was observed",
]
LENGTHS = ["one sentence", "two to three sentences", "a short paragraph (4-5 sentences)"]
REGISTERS = ["neutral, matter-of-fact", "slightly apologetic and explanatory", "procedural and checklist-like"]

# Category definitions and boundary notes -- this is a first pass at the
# label schema that Chunk 1.3 should turn into the canonical data/labels.md.
# Keeping it here for now grounds the generation prompt; once labels.md
# exists, load these from that file instead of duplicating them.
CATEGORY_GUIDANCE = {
    "major": {
        "definition": (
            "Safety, subject-rights, or data-integrity impact requiring expedited "
            "IRB/sponsor reporting."
        ),
        "boundary_notes": (
            "vs minor: the discriminator is severity of clinical/data-integrity impact, "
            "not event type -- a missed visit window is minor unless it caused a real "
            "missed safety check. vs technical: major is about consequence (someone could "
            "be harmed, data compromised); technical is about a systems root cause with no "
            "such consequence reaching a subject."
        ),
        "scenario_hints": [
            "a subject received an incorrect dose (over/under) of the investigational product",
            "a subject was enrolled despite failing a key exclusion criterion",
            "treatment assignment was inadvertently unblinded to site staff",
            "a protocol-mandated procedure was performed before informed consent was obtained",
            "a serious adverse event was not managed per the protocol's safety monitoring plan",
            "a subject was given an excluded concomitant medication posing a safety risk",
        ],
    },
    "minor": {
        "definition": "Low-impact deviation with no bearing on subject safety or data integrity.",
        "boundary_notes": (
            "vs administrative: minor involves an actual protocol-specified clinical activity "
            "happening off-spec (wrong timing, wrong device); administrative involves paperwork "
            "about who's authorized or when things were filed, not the clinical activity itself."
        ),
        "scenario_hints": [
            "a visit was conducted a few days outside the protocol-specified window, non-critical assessment",
            "a non-critical questionnaire was not completed at a visit",
            "a dose was taken a few hours later than the scheduled time, no clinical impact",
            "a lab sample was collected slightly outside its collection window",
        ],
    },
    "technical": {
        "definition": "Deviation caused by equipment, systems, or procedural/technical failure.",
        "boundary_notes": (
            "vs minor: minor is a human/process timing slip; technical is a system or piece "
            "of equipment failing on its own, independent of what staff decided to do."
        ),
        "scenario_hints": [
            "a temperature excursion was recorded in drug storage",
            "an IVRS/randomization system outage caused an incorrect kit assignment",
            "an ePRO device malfunctioned, causing loss of patient-reported outcome data",
            "lab equipment calibration lapsed past its scheduled service date",
            "an EDC system outage prevented timely data entry",
        ],
    },
    "administrative": {
        "definition": (
            "Documentation, delegation, or training paperwork issue with no direct "
            "clinical impact."
        ),
        "boundary_notes": (
            "vs major: if the paperwork gap actually changed what the subject was told or "
            "could decide (e.g. an outdated consent form withheld new safety information), "
            "that's major, not administrative -- administrative is purely a version-control "
            "or documentation gap."
        ),
        "scenario_hints": [
            "the delegation of authority log was not updated before a staff member performed a procedure",
            "the continuing review submission to the IRB was submitted after the required deadline",
            "a source document was missing a signature or date",
            "an outdated informed consent form version was used, with no new safety information withheld",
        ],
    },
    "unreported": {
        "definition": (
            "A deviation occurred (of any underlying type) but was never logged or reported "
            "within the required timeframe -- discovered later via monitoring or audit. This "
            "is a reporting-compliance category, orthogonal to the other four; write it from "
            "the discovery/audit perspective."
        ),
        "boundary_notes": "the emphasis is on the fact that reporting never happened, not on the severity of the underlying event.",
        "scenario_hints": [
            "a monitoring visit revealed a deviation from months earlier that was never logged",
            "an audit found an off-protocol dose that was never submitted as a deviation report",
            "a site mentioned a deviation verbally but no deviation report or CAPA was ever filed",
            "database lock review revealed a missed visit that had never been documented as a deviation",
        ],
    },
}

REPORT_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "reports": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["index", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["reports"],
    "additionalProperties": False,
}


def _build_system_prompt(category: str) -> str:
    lines = [
        "You write short, realistic clinical trial protocol deviation report narratives "
        "for synthetic training data. Each narrative should read like a real entry a site "
        "coordinator, investigator, or monitor would write.",
        "",
        "The five-category label schema used across this dataset:",
    ]
    for cat, info in CATEGORY_GUIDANCE.items():
        marker = " <- this batch's category" if cat == category else ""
        lines.append(f"- {cat}{marker}: {info['definition']} ({info['boundary_notes']})")
    lines += [
        "",
        f"Every report you write in this request is a '{category}' deviation. Stay "
        "unambiguously inside that category's definition and do not drift into a "
        "neighboring one.",
        "Use only the identifiers and entities provided for each report -- do not invent "
        "additional named people, drugs, or products beyond what's given.",
        "Do not include a regulatory citation or CAPA recommendation; write only the "
        "deviation narrative itself.",
    ]
    return "\n".join(lines)


def _build_user_prompt(category: str, slots: list[dict], flavor: dict) -> str:
    return (
        f"Write one deviation report narrative for each of the {len(slots)} report slots "
        "below. Match each slot's requested voice, length, and register, and center the "
        "narrative on its scenario hint using its specific identifiers.\n\n"
        f"Available entity flavor (use if natural, not required for every report):\n"
        f"{json.dumps(flavor, indent=2)}\n\n"
        f"Report slots:\n{json.dumps(slots, indent=2)}\n\n"
        "Return exactly one entry per slot index."
    )


def _make_slot(rng: random.Random, counter: int, category: str, today: date) -> dict:
    site_num = rng.randint(1, 40)
    ids = _make_ids(rng, site_num)

    if category == "unreported":
        deviation_date = _random_date(rng, today - timedelta(days=240), today - timedelta(days=60))
        discovery_date = deviation_date + timedelta(days=rng.randint(45, 150))
    else:
        deviation_date = _random_date(rng, today - timedelta(days=90), today - timedelta(days=1))
        discovery_date = deviation_date + timedelta(days=rng.randint(0, 5))

    return {
        "index": counter,
        "protocol_id": ids["protocol_id"],
        "site_id": ids["site_id"],
        "site": ids["site"],
        "subject_id": ids["subject_id"],
        "deviation_date": deviation_date.isoformat(),
        "discovery_date": discovery_date.isoformat(),
        "scenario_hint": rng.choice(CATEGORY_GUIDANCE[category]["scenario_hints"]),
        "voice": rng.choice(VOICES),
        "length": rng.choice(LENGTHS),
        "register": rng.choice(REGISTERS),
    }


def generate_batch(
    client: anthropic.Anthropic,
    rng: random.Random,
    category: str,
    batch_size: int,
    model: str,
    effort: str,
    today: date,
) -> list[dict]:
    slots = [_make_slot(rng, i, category, today) for i in range(batch_size)]
    flavor = {
        "drug_names": rng.sample(DRUG_NAMES, k=min(2, len(DRUG_NAMES))),
        "visit_names": rng.sample(VISIT_NAMES, k=min(3, len(VISIT_NAMES))),
        "investigators": rng.sample(INVESTIGATORS, k=min(3, len(INVESTIGATORS))),
        "devices": rng.sample(DEVICE_NAMES, k=min(2, len(DEVICE_NAMES))),
        "questionnaires": rng.sample(QUESTIONNAIRES, k=min(2, len(QUESTIONNAIRES))),
        "consent_versions": rng.sample(CONSENT_VERSIONS, k=min(2, len(CONSENT_VERSIONS))),
    }

    system_prompt = _build_system_prompt(category)
    user_prompt = _build_user_prompt(category, slots, flavor)

    for attempt in range(2):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            output_config={
                "effort": effort,
                "format": {"type": "json_schema", "schema": REPORT_BATCH_SCHEMA},
            },
            messages=[{"role": "user", "content": user_prompt}],
        )
        if response.stop_reason == "refusal":
            print(f"  [warn] refusal on {category} batch (attempt {attempt + 1}); retrying", file=sys.stderr)
            continue
        text = next(b.text for b in response.content if b.type == "text")
        parsed = json.loads(text)
        break
    else:
        raise RuntimeError(f"Claude refused to generate a '{category}' batch after retrying")

    text_by_index = {r["index"]: r["text"] for r in parsed["reports"]}
    generated_at = datetime.now(timezone.utc).isoformat()

    records = []
    for slot in slots:
        records.append(
            {
                "protocol_id": slot["protocol_id"],
                "site_id": slot["site_id"],
                "subject_id": slot["subject_id"],
                "deviation_date": slot["deviation_date"],
                "discovery_date": slot["discovery_date"],
                "text": text_by_index[slot["index"]],
                "category": category,
                "voice": slot["voice"],
                "length": slot["length"],
                "register": slot["register"],
                "scenario_hint": slot["scenario_hint"],
                "reviewed": False,
                "generated_at": generated_at,
                "model": model,
            }
        )
    return records


def stratified_split(records: list[dict], seed: int, ratios: tuple[float, float, float] = (0.7, 0.15, 0.15)) -> list[dict]:
    rng = random.Random(seed + 1)
    by_category: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    for r in records:
        by_category[r["category"]].append(r)

    for group in by_category.values():
        rng.shuffle(group)
        n = len(group)
        n_train = round(n * ratios[0])
        n_val = round(n * ratios[1])
        for i, r in enumerate(group):
            r["split"] = "train" if i < n_train else ("val" if i < n_train + n_val else "test")

    return records


def write_raw_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def write_processed_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id", "protocol_id", "site_id", "subject_id", "deviation_date", "discovery_date",
        "text", "category", "voice", "length", "register", "scenario_hint",
        "reviewed", "generated_at", "model", "split",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-per-category", type=int, default=5, help="Start small; scale up once output looks right.")
    parser.add_argument("--batch-size", type=int, default=5, help="Reports requested per API call.")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--effort", default="low", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--raw-out", type=Path, default=Path("data/raw/claude_generated_deviations.jsonl"))
    parser.add_argument("--processed-out", type=Path, default=Path("data/processed/claude_generated_deviations_labeled.csv"))
    args = parser.parse_args()

    client = anthropic.Anthropic()
    rng = random.Random(args.seed)
    today = date(2024, 6, 1)

    all_records: list[dict] = []
    counter = 1
    for category in CATEGORIES:
        n_batches = (args.n_per_category + args.batch_size - 1) // args.batch_size
        remaining = args.n_per_category
        for batch_num in range(n_batches):
            size = min(args.batch_size, remaining)
            remaining -= size
            print(f"[{category}] batch {batch_num + 1}/{n_batches} ({size} reports)...")
            batch_records = generate_batch(client, rng, category, size, args.model, args.effort, today)
            for r in batch_records:
                r["id"] = f"GEN-{counter:06d}"
                counter += 1
            all_records.extend(batch_records)

    write_raw_jsonl(all_records, args.raw_out)
    split_records = stratified_split(all_records, seed=args.seed)
    write_processed_csv(split_records, args.processed_out)

    print(f"Wrote {len(all_records)} records to {args.raw_out}")
    print(f"Wrote {len(split_records)} labeled+split records to {args.processed_out}")


if __name__ == "__main__":
    main()
