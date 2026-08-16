# protocol-deviation-triage-agent

An AI-assisted triage pipeline for clinical trial protocol deviation reports:
classify a deviation into one of 5 categories, look up the relevant CAPA
guidance, and draft a review memo for human approval.

## Stack

- Python, FastAPI (`app/`)
- Hugging Face Transformers (DeBERTa-v3 fine-tuning, Phase 2)
- LangGraph (workflow orchestration, Phase 3)
- Anthropic API / Claude (memo drafting node, Phase 4)
- Streamlit (human review UI, Phase 5)
- SQLite (triage state)

## Repo layout

- `app/` — FastAPI app (currently just `/health`; will host the mock queue
  endpoint in Phase 3).
- `data/raw/` — generated-but-unsplit datasets (JSONL, one record per line).
- `data/processed/` — labeled, train/val/test-split datasets (CSV), ready
  for fine-tuning.
- `data/labels.md` — canonical label-schema definitions and boundary notes.
  Anything that needs a category definition (generators, classifier,
  CAPA lookup) should trace back to this file, not redefine it.
- `scripts/` — data generation and processing scripts (see below).
- `models/` — trained model artifacts (gitignored; too large for git).
- `tests/` — unit tests, run with `python -m unittest`.

## Label schema

Five categories: `major`, `minor`, `technical`, `administrative`,
`unreported`. Full definitions and boundary cases (what separates `minor`
from `technical`, etc.) live in `data/labels.md` — currently a first draft,
not yet validated against ICH E6(R3) or FDA Warning Letter language.

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

## Setup

```
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on Unix
pip install -r requirements.txt
```

Set `ANTHROPIC_API_KEY` in your environment (or use `ant auth login`) before
running `generate_reports.py`. Never commit a key or put it in a script —
env var only.

## Testing

```
python -m unittest discover tests
```

## Conventions

- No comments in code unless they explain a non-obvious *why* (a subtle
  invariant, a workaround, something that would surprise a reader).
- Generation scripts take a `--seed` for reproducibility and default to a
  small `--n-per-category` so a test run is cheap before scaling up.
- Prefer reusing entity/date-generation logic across scripts (see how
  `generate_reports.py` imports from `generate_synthetic_deviations.py`)
  over duplicating pools of fake site names, drugs, etc.
