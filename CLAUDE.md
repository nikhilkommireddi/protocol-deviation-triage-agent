# protocol-deviation-triage-agent

An AI-assisted triage pipeline for clinical trial protocol deviation reports:
classify a deviation into one of 5 categories, look up the relevant CAPA
guidance, and draft a review memo for human approval.

## Stack

- Python, FastAPI (`app/`) — backend API
- React + TypeScript + Vite, Tailwind CSS (`frontend/`) — review UI
- Hugging Face Transformers / PyTorch — fine-tuned DeBERTa-v3-base classifier
- LangGraph — workflow orchestration (`app/graph.py`)
- Anthropic API / Claude Sonnet 5 — memo drafting node
- SQLite — triage state (`app/db.py`)

## Repo layout

- `app/` — FastAPI backend: `main.py` (HTTP endpoints), `graph.py` (the
  5-node LangGraph triage workflow), `db.py` (SQLite persistence),
  `schemas.py` (Pydantic request/response models).
- `frontend/` — React + TypeScript UI (submit a deviation, review/approve
  drafted memos). Hand-built components styled with Tailwind utility
  classes — no component library, consistent with the rest of the project's
  minimal-dependency approach.
- `data/raw/` — generated-but-unsplit datasets (JSONL, one record per line).
- `data/processed/` — labeled, train/val/test-split datasets (CSV), ready
  for fine-tuning.
- `data/labels.md` — canonical label-schema definitions and boundary notes.
  Anything that needs a category definition (generators, classifier,
  CAPA lookup) should trace back to this file, not redefine it.
- `data/capa_guidance.json` — category → routing team, regulatory
  reference, required CAPA elements. Read by `app/graph.py`'s CAPA-lookup
  node and referenced by the memo-draft prompt.
- `data/eval_cases.json` — 30 hand-authored end-to-end evaluation cases
  (see `scripts/run_eval.py`).
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
- `scripts/run_eval.py` — runs the 30 cases in `data/eval_cases.json`
  through the real end-to-end pipeline (real classifier, real Claude memo
  draft) and reports classification accuracy, a memo-completeness rubric,
  and latency. Writes `eval_results.json` and `eval_report.md`.

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
(`generate_reports.py`, the LangGraph memo-draft node, `run_eval.py`).
Either export it in your shell, or copy `.env.example` to `.env` and fill
in your key — `app/graph.py` and `generate_reports.py` both call
`load_dotenv()` on import, so a project-local `.env` is picked up
automatically. `.env` is gitignored; never commit a key or put one
directly in a script.

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
