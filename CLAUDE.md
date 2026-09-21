# protocol-deviation-triage-agent

An AI-assisted triage pipeline for clinical trial protocol deviation reports.
A fast fine-tuned classifier gives a first-pass category, then a chain of
specialized Claude agents independently investigate the trial's actual
protocol facts and the site's deviation history, adjudicate a final category
(confirming or explicitly overriding the classifier with a cited reason),
draft a CAPA review memo, and verify that memo against the evidence
gathered — all before a human ever reviews it.

## Stack

- Python, FastAPI (`app/`) — backend API
- React + TypeScript + Vite, Tailwind CSS (`frontend/`) — review UI
- Hugging Face Transformers / PyTorch — fine-tuned DeBERTa-v3-base classifier
- LangGraph — multi-agent workflow orchestration (`app/graph.py`)
- Anthropic API / Claude Sonnet 5 — five specialized agents (protocol
  investigation, site history, adjudication, memo drafting, verification)
- SQLite — triage state (`app/db.py`)

## Multi-agent pipeline

`app/graph.py` runs 8 nodes in a fixed sequence (not a dynamic supervisor —
see the architecture doc referenced below for why): `ingest -> classify ->
protocol_investigate -> site_history -> adjudicate -> capa_lookup ->
memo_draft -> verify`, with one conditional edge: a failed verification
routes back to `adjudicate` once (bounded retry) before proceeding regardless.

- **Classifier Agent** (`predict_category`) — the fine-tuned DeBERTa model,
  a fast first-pass category + confidence. Kept as an input signal, not
  replaced by the agents below.
- **Protocol Investigator Agent** (`investigate_protocol`) — a real Claude
  tool-use loop against `app/protocol_lookup.py`'s deterministic lookups
  over `data/protocols/<protocol_id>.json` (consent version history, visit
  windows, eligibility criteria). Decides for itself what's relevant to a
  given deviation rather than following a fixed lookup sequence.
- **Site History Agent** (`investigate_history`) — reviews prior deviations
  at the same site (`db.list_reports_by_site`) for a recurring root-cause
  pattern, not just isolated events.
- **Adjudication Agent** (`adjudicate`) — the actual decision-maker: confirms
  or explicitly overrides the classifier's category with a cited reason,
  given the investigator and history findings plus `data/labels.md`'s
  boundary definitions.
- **Memo Drafting Agent** (`draft_memo`) — same CAPA memo as before, now
  informed by the adjudication reasoning and any relevant findings.
- **Verification Agent** (`verify`) — checks the adjudication and memo
  against the evidence actually gathered before the report is allowed to
  queue.

**Retry and failure handling**: every Claude call goes through
`_call_with_retries` (backoff on transient API errors and malformed
structured output). Critical agents (classifier, adjudication, memo draft,
verification) raise `TriageAgentError` after exhausting retries, which
`app/main.py` turns into an HTTP 502 rather than an opaque crash. Advisory
agents (protocol investigator, site history) degrade gracefully to a
labeled "unavailable" finding instead of blocking the whole triage.

## Repo layout

- `app/` — FastAPI backend: `main.py` (HTTP endpoints), `graph.py` (the
  multi-agent LangGraph workflow, see above), `protocol_lookup.py`
  (deterministic protocol-document lookups), `db.py` (SQLite persistence),
  `schemas.py` (Pydantic request/response models).
- `frontend/` — React + TypeScript UI: a 3-step submit wizard, a Review
  Queue dashboard, and an Analytics page. `ReasoningTrace.tsx` renders the
  agent pipeline's findings (protocol/history investigation, adjudication,
  verification) for a human reviewer. Hand-built components styled with
  Tailwind utility classes, plus `lucide-react` for icons — no full UI
  component library, consistent with the rest of the project's
  minimal-dependency approach.
- `data/raw/` — generated-but-unsplit datasets (JSONL, one record per line).
- `data/processed/` — labeled, train/val/test-split datasets (CSV), ready
  for fine-tuning.
- `data/labels.md` — canonical label-schema definitions and boundary notes.
  Anything that needs a category definition (generators, classifier,
  CAPA lookup, the Adjudication Agent) should trace back to this file, not
  redefine it.
- `data/capa_guidance.json` — category → routing team, regulatory
  reference, required CAPA elements. Read by `app/graph.py`'s CAPA-lookup
  node and referenced by the memo-draft prompt.
- `data/protocols/<protocol_id>.json` — structured protocol documents
  (consent version history, visit schedule, eligibility criteria), written
  by us rather than sourced externally so eval cases have a verifiable
  ground truth. Read by `app/protocol_lookup.py`.
- `data/eval_cases.json` — 33 hand-authored end-to-end evaluation cases
  (see `scripts/run_eval.py`); some carry an `expected_evidence` field
  checked against the agents' actual findings, not just the final category.
- `scripts/` — data generation, training, and evaluation scripts (see below).
- `models/` — trained model artifacts (gitignored; too large for git).
- `tests/` — unit tests, run with `python -m unittest`.

## Label schema

Five categories: `major`, `minor`, `technical`, `administrative`,
`unreported`. Full definitions and boundary cases (what separates `minor`
from `technical`, etc.) live in `data/labels.md`, grounded in ICH E3(R1)
and FDA's Dec 2024 draft guidance on protocol deviations — see that file's
"Regulatory basis" section for how this project's 5-category scheme maps
onto (and diverges from) official terminology.

## Dataset generation

Two independent generators produce the same record schema
(`id, source, protocol_id, site_id, subject_id, deviation_date,
discovery_date, text, category, voice, length, register, scenario_hint,
reviewed, generated_at, model, split`):

- `scripts/generate_synthetic_deviations.py` — offline, template-based,
  stdlib only. No API key needed. Deterministic given `--seed`.
- `scripts/generate_reports.py` — calls the Claude API (`claude-sonnet-5`
  by default) to write the narrative text, using structured JSON output
  and a voice/length/register grid for variety (not sampling temperature —
  Sonnet 5 rejects a non-default `temperature`). Requires
  `ANTHROPIC_API_KEY`. Start with a small `--n-per-category` before scaling
  up.
- `scripts/combine_datasets.py` — merges both into
  `data/processed/combined_deviations_labeled.csv`, tagging each record's
  `source`. Splits are preserved from the source datasets rather than
  re-shuffled, so no record moves between train/val/test on combine.

Every generated record starts with `reviewed: False`. Flip to `True` during
the manual quality-review pass before treating a record as trustworthy
training data.

## Model training and evaluation

- `scripts/train_classifier.py` — fine-tunes `deberta-v3-base` on
  `combined_deviations_labeled.csv`. Uses `optim="adafactor"`, not the
  torch default AdamW — plain AdamW reproducibly corrupted every model
  parameter to NaN on CPU in this environment (see the script's comment
  and the "Fix training collapse" commit for the full diagnosis). Saves to
  `models/deviation-classifier/` (gitignored) plus a `training_results.json`
  alongside it.
- `scripts/run_eval.py` — runs the 33 cases in `data/eval_cases.json`
  through the real end-to-end multi-agent pipeline and reports
  classification accuracy, a memo-completeness rubric, evidence-grounding
  (did the agents actually cite the fact a case's category depends on, not
  just land on the right answer by chance), and latency. Writes
  `eval_results.json` and `eval_report.md`. Current: 100% classification
  accuracy, 5/5 evidence-grounding checks correct.

## Setup

Backend:
```
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on Unix
pip install -r requirements.txt
```

Frontend:
```
cd frontend
npm install
```

Set `ANTHROPIC_API_KEY` before running anything that calls Claude
(`generate_reports.py`, any of `app/graph.py`'s five Claude agents,
`app/pdf_extract.py`, `run_eval.py`). Either export it in your shell, or
copy `.env.example` to `.env` and fill in your key — `app/graph.py` and
`generate_reports.py` both call `load_dotenv()` on import, so a
project-local `.env` is picked up automatically. `.env` is gitignored;
never commit a key or put one directly in a script.

## Running it

Two processes, in separate terminals:
```
.venv/Scripts/uvicorn app.main:app --reload        # backend, :8000
cd frontend && npm run dev                          # frontend, :5173
```
The FastAPI app allows CORS from the Vite dev server origin
(`localhost:5173`) — see `app/main.py`. That allow-list is permissive for
local dev only and should be tightened before any real deployment.

## Testing

Backend:
```
python -m unittest discover tests
```
Frontend has no automated test suite yet — verify with `npm run build`
(type-checks) and manual click-through. Same scope call made for the
Streamlit UI it replaced: no permanent UI regression tests in this pass.

## Conventions

- No comments in code unless they explain a non-obvious *why* (a subtle
  invariant, a workaround, something that would surprise a reader).
- Generation scripts take a `--seed` for reproducibility and default to a
  small `--n-per-category` so a test run is cheap before scaling up.
- Prefer reusing entity/date-generation logic across scripts (see how
  `generate_reports.py` imports from `generate_synthetic_deviations.py`)
  over duplicating pools of fake site names, drugs, etc.
- Frontend: Tailwind utility classes directly in JSX; repeated patterns
  (inputs, buttons, cards) are pulled into `@apply`-based classes in
  `frontend/src/index.css`, not a component library.
