"""Generate a synthetic, labeled dataset of clinical trial protocol deviation
reports for Step 1 of the triage agent build plan.

Offline and deterministic (stdlib only) so it can run without a GPU or any
API keys. Produces:
  - data/raw/synthetic_deviations.jsonl   (pre-split, full-fidelity records)
  - data/processed/deviations_labeled.csv (final labeled + split dataset)

Label taxonomy
--------------
major          - safety / subject-rights / data-integrity impact requiring
                 expedited IRB or sponsor reporting.
minor          - low-impact deviation with no safety or data-integrity effect.
technical      - equipment, systems, or procedural/technical failure.
administrative - documentation, delegation, or training paperwork issue with
                 no direct clinical impact.
unreported     - a deviation occurred but was never logged/reported within
                 the required timeframe; discovered later via monitoring
                 or audit.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

CATEGORIES = ["major", "minor", "technical", "administrative", "unreported"]

SITE_CITIES = [
    "Boston", "Austin", "Chicago", "Denver", "Seattle", "Atlanta",
    "Phoenix", "Raleigh", "Columbus", "Portland", "Nashville", "Tampa",
]
INVESTIGATORS = [
    "Dr. Patel", "Dr. Nguyen", "Dr. Okafor", "Dr. Kowalski", "Dr. Rossi",
    "Dr. Kim", "Dr. Alvarez", "Dr. Larsen", "Dr. Haddad", "Dr. Fischer",
]
DRUG_NAMES = ["Study Drug XJ-401", "Study Drug RN-88", "Investigational Product ARC-12", "Study Drug MTV-7"]
VISIT_NAMES = ["Visit 2 (Week 4)", "Visit 3 (Week 8)", "Visit 4 (Week 12)", "Visit 5 (Week 24)", "Screening Visit"]
DEVICE_NAMES = ["ePRO tablet", "IVRS randomization terminal", "-20C storage freezer", "central lab shipment logger", "ECG recorder"]
QUESTIONNAIRES = ["quality-of-life questionnaire", "concomitant medication log", "non-critical symptom diary"]
CONSENT_VERSIONS = ["v3.0 (dated 2023-11-02)", "v2.1 (dated 2023-04-15)", "v4.0 (dated 2024-01-20)"]

TRAILING_CLAUSES = [
    " The site coordinator has been notified.",
    " No further action was taken at the time.",
    " This was identified during routine source document verification.",
    " The principal investigator was made aware the same day.",
    "",
    "",
]

TEMPLATES: dict[str, list[str]] = {
    "major": [
        "Subject {subject_id} at {site} received a {dose_error} of {drug} during {visit}, deviating from the protocol-specified dosing regimen.",
        "Subject {subject_id} was enrolled at {site} despite meeting exclusion criterion related to {exclusion_reason}, which was not identified during screening.",
        "The treatment assignment for Subject {subject_id} was inadvertently unblinded to site staff at {site} after a randomization system error.",
        "{visit} procedures, including a protocol-mandated biopsy, were performed on Subject {subject_id} at {site} before written informed consent was obtained.",
        "Subject {subject_id} experienced a serious adverse event at {site} that was not managed according to the protocol-specified safety monitoring plan.",
        "Subject {subject_id} was administered {drug} concurrently with an excluded concomitant medication at {site}, posing a potential safety risk.",
        "A dosing error resulted in Subject {subject_id} at {site} receiving {drug} intended for a different subject, confirmed after kit reconciliation.",
        "Subject {subject_id} continued on {drug} at {site} for two additional cycles after protocol-defined stopping criteria were met.",
    ],
    "minor": [
        "{visit} for Subject {subject_id} at {site} was conducted {days_late} days outside the protocol-specified visit window; no safety assessments were affected.",
        "Subject {subject_id} at {site} did not complete the {questionnaire} at {visit}; the omission was noncritical to primary endpoints.",
        "Subject {subject_id} at {site} took a dose of {drug} approximately {hours_late} hours later than the scheduled administration time.",
        "A non-critical laboratory sample for Subject {subject_id} at {site} was collected {days_late} days outside the specified collection window.",
        "Subject {subject_id}'s {visit} vital signs were recorded using a backup manual cuff at {site} rather than the automated device, per site procedure.",
        "The site at {site} scheduled Subject {subject_id}'s {visit} on a non-business day, resulting in a same-day rescheduling with no other impact.",
        "Subject {subject_id} at {site} was given verbal rather than written dietary instructions ahead of {visit}, with no effect on assessment validity.",
    ],
    "technical": [
        "A temperature excursion was recorded in the {device} at {site}, with storage conditions for {drug} falling outside the validated range for approximately {hours_late} hours.",
        "The {device} at {site} experienced a system outage, resulting in Subject {subject_id} being assigned to the incorrect treatment kit during randomization.",
        "The {device} used by Subject {subject_id} at {site} malfunctioned during {visit}, resulting in loss of patient-reported outcome data for that visit.",
        "Calibration of the {device} at {site} lapsed past its scheduled service date, potentially affecting the accuracy of assessments collected during {visit}.",
        "An EDC system outage at {site} prevented timely entry of Subject {subject_id}'s {visit} data within the protocol-specified window.",
        "The {device} used to ship Subject {subject_id}'s {visit} lab samples from {site} failed in transit, and the temperature log could not be verified on arrival.",
        "A software update to the {device} at {site} caused a randomization list mismatch, discovered before any subjects were affected.",
    ],
    "administrative": [
        "The delegation of authority log at {site} was not updated to reflect {investigator}'s role prior to {investigator} performing {visit} procedures for Subject {subject_id}.",
        "The continuing review submission to the IRB of record for {site} was submitted {days_late} days after the required deadline.",
        "A source document for Subject {subject_id}'s {visit} at {site} was missing {investigator}'s signature and date at the time of monitoring review.",
        "{site} used informed consent form {consent_version} for Subject {subject_id} instead of the currently approved version, though no new safety information was omitted from the discussion.",
        "The site training log at {site} did not document {investigator}'s completion of protocol-specific training prior to conducting {visit} assessments.",
        "A staff member at {site} signed the {questionnaire} on behalf of Subject {subject_id} without documenting the reason for the exception.",
        "The pharmacy accountability log at {site} for {drug} was not reconciled within the protocol-specified timeframe following {visit}.",
    ],
    "unreported": [
        "During a routine monitoring visit at {site}, it was discovered that a protocol deviation involving Subject {subject_id}'s {visit} from {deviation_date} was never logged or reported.",
        "An audit of {site} records revealed that Subject {subject_id} received an off-protocol dose of {drug} on {deviation_date}, which was never submitted as a deviation report.",
        "{investigator} at {site} mentioned during a call that a deviation occurred during {visit} for Subject {subject_id}, but no deviation report or CAPA was ever filed.",
        "The sponsor identified during database lock review that a missed {visit} for Subject {subject_id} at {site} on {deviation_date} had not been documented as a protocol deviation.",
        "A retrospective chart review at {site} uncovered that Subject {subject_id}'s exclusion-criterion violation from {deviation_date} was never reported to the IRB.",
        "Monitoring staff found that the {device} malfunction at {site} affecting Subject {subject_id} on {deviation_date} had not been captured in the site's deviation log.",
        "{site} failed to notify the sponsor of a consent version discrepancy affecting Subject {subject_id}, discovered {days_late} days after the {deviation_date} visit during a for-cause audit.",
    ],
}

DOSE_ERRORS = ["double dose", "half of the prescribed dose", "an infusion rate exceeding the protocol maximum", "an incorrect drug kit"]
EXCLUSION_REASONS = [
    "a prohibited concomitant condition", "prior participation in a conflicting investigational study",
    "renal function outside the eligible range", "an excluded prior therapy",
]


def _random_date(rng: random.Random, start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=rng.randint(0, max(span, 0)))


def _make_ids(rng: random.Random, site_num: int) -> dict:
    return {
        "protocol_id": f"PDA-2024-{rng.randint(100, 199)}",
        "site": f"Site {site_num:03d} ({rng.choice(SITE_CITIES)})",
        "site_id": f"{site_num:03d}",
        "subject_id": f"{site_num:03d}-{rng.randint(1000, 9999)}",
    }


def _fill_slots(rng: random.Random, ids: dict) -> dict:
    slots = dict(ids)
    slots.update(
        drug=rng.choice(DRUG_NAMES),
        visit=rng.choice(VISIT_NAMES),
        device=rng.choice(DEVICE_NAMES),
        questionnaire=rng.choice(QUESTIONNAIRES),
        investigator=rng.choice(INVESTIGATORS),
        consent_version=rng.choice(CONSENT_VERSIONS),
        dose_error=rng.choice(DOSE_ERRORS),
        exclusion_reason=rng.choice(EXCLUSION_REASONS),
        days_late=rng.randint(2, 14),
        hours_late=rng.randint(2, 18),
    )
    return slots


def generate_records(seed: int = 42, n_per_category: int = 60) -> list[dict]:
    rng = random.Random(seed)
    today = date(2024, 6, 1)
    records: list[dict] = []
    counter = 1

    for category in CATEGORIES:
        templates = TEMPLATES[category]
        for _ in range(n_per_category):
            site_num = rng.randint(1, 40)
            ids = _make_ids(rng, site_num)
            slots = _fill_slots(rng, ids)

            if category == "unreported":
                deviation_date = _random_date(rng, today - timedelta(days=240), today - timedelta(days=60))
                discovery_date = deviation_date + timedelta(days=rng.randint(45, 150))
            else:
                deviation_date = _random_date(rng, today - timedelta(days=90), today - timedelta(days=1))
                discovery_date = deviation_date + timedelta(days=rng.randint(0, 5))

            slots["deviation_date"] = deviation_date.isoformat()

            template = rng.choice(templates)
            text = template.format(**slots) + rng.choice(TRAILING_CLAUSES)

            records.append(
                {
                    "id": f"DEV-{counter:06d}",
                    "protocol_id": slots["protocol_id"],
                    "site_id": slots["site_id"],
                    "subject_id": slots["subject_id"],
                    "deviation_date": deviation_date.isoformat(),
                    "discovery_date": discovery_date.isoformat(),
                    "text": text,
                    "category": category,
                }
            )
            counter += 1

    rng.shuffle(records)
    return records


def stratified_split(
    records: list[dict], seed: int = 42, ratios: tuple[float, float, float] = (0.7, 0.15, 0.15)
) -> list[dict]:
    assert abs(sum(ratios) - 1.0) < 1e-9
    rng = random.Random(seed + 1)
    by_category: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    for r in records:
        by_category[r["category"]].append(r)

    for category, group in by_category.items():
        group = group[:]
        rng.shuffle(group)
        n = len(group)
        n_train = round(n * ratios[0])
        n_val = round(n * ratios[1])
        for i, r in enumerate(group):
            if i < n_train:
                r["split"] = "train"
            elif i < n_train + n_val:
                r["split"] = "val"
            else:
                r["split"] = "test"

    return records


def write_raw_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def write_processed_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id", "protocol_id", "site_id", "subject_id",
        "deviation_date", "discovery_date", "text", "category", "split",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-per-category", type=int, default=60)
    parser.add_argument("--raw-out", type=Path, default=Path("data/raw/synthetic_deviations.jsonl"))
    parser.add_argument("--processed-out", type=Path, default=Path("data/processed/deviations_labeled.csv"))
    args = parser.parse_args()

    records = generate_records(seed=args.seed, n_per_category=args.n_per_category)
    write_raw_jsonl(records, args.raw_out)

    split_records = stratified_split(records, seed=args.seed)
    write_processed_csv(split_records, args.processed_out)

    print(f"Wrote {len(records)} records to {args.raw_out}")
    print(f"Wrote {len(split_records)} labeled+split records to {args.processed_out}")


if __name__ == "__main__":
    main()
