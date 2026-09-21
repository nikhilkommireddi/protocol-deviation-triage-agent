# Protocol Deviation Label Schema

Five mutually-exclusive categories used to triage protocol deviation reports.
This is the canonical definition source — the synthetic data generators
(`scripts/generate_synthetic_deviations.py`, `scripts/generate_reports.py`)
and the eventual classifier and CAPA-lookup node should all trace back to
this file rather than re-deriving definitions independently.

**Status: checked against regulatory sources (Chunk 1.2).** Category
definitions below were originally written from general clinical-trial-ops
knowledge; this pass compared them against real regulatory language and
adjusted the framing accordingly (see Regulatory basis).

## Regulatory basis

- The "protocol deviation" definition itself traces to **ICH E3(R1)**
  (Clinical Study Reports) — "any change, divergence, or departure from the
  study design or procedures defined in the protocol" — not ICH E6(R3) as
  originally assumed. E6(R3) is the broader Good Clinical Practice /
  quality-management guideline; it doesn't define "deviation" itself.
- The directly operative framework is FDA's **December 2024 draft
  guidance**, *"Protocol Deviations for Clinical Investigations of Drugs,
  Biological Products, and Devices."* It classifies deviations along two
  axes: **Important vs. Not Important** (impact on subject rights/safety/
  well-being or on data completeness, accuracy, and reliability) crossed
  with **Intentional/Planned vs. Unintentional**.
- **This project's 5-category scheme does not map 1:1 onto that
  taxonomy, and that's worth being explicit about:**
  - `major` ≈ FDA's "important deviation" concept.
  - `minor` ≈ "not important deviation."
  - `technical` and `administrative` are **not official regulatory
    categories** — they're a root-cause sub-typing I added on top of the
    importance axis, useful for routing CAPA ownership (a technical
    deviation routes to IT/facilities/quality-systems; an administrative
    one routes to regulatory-affairs/site training), but not vocabulary
    FDA or ICH use.
  - `unreported` doesn't correspond to either FDA axis — it's a
    reporting-compliance flag that could in principle apply regardless of
    importance or intentionality, consistent with its "orthogonal" framing
    below.
  - The FDA guidance's **intentional/planned vs. unintentional** axis has
    no equivalent in this scheme at all. Every category here implicitly
    assumes unintentional deviations; a deliberate, pre-agreed deviation
    (e.g. enrolling a borderline-eligible subject by sponsor/site
    agreement) isn't represented. Worth reconsidering if this taxonomy
    needs to support planned deviations later.
- A real FDA warning letter reviewed for this pass (an unblinded assessor
  conducting efficacy assessments) showed what "adequate CAPA" looks like
  in practice: the FDA rejected a corrective action plan for lacking
  specifics on retraining, reassessment, added monitoring checkpoints, and
  named responsibility/timelines. Worth reusing that structure when Phase 4
  builds the memo-drafting prompt.

## major

**Definition:** Deviations with safety, subject-rights, or data-integrity
impact that require expedited IRB/sponsor reporting.

**Examples:**
- A subject received an incorrect dose (over- or under-dose) of the
  investigational product.
- A subject was enrolled despite meeting a protocol-specified exclusion
  criterion.
- A protocol-mandated procedure was performed before informed consent was
  obtained.

**Boundary notes:**
- *vs. minor* — the discriminator is severity of clinical/data-integrity
  impact, not the type of event. A visit outside its window is `minor`
  unless it caused a real missed safety check, in which case it's `major`.
- *vs. technical* — `major` is about consequence (someone could be harmed,
  data compromised); `technical` is about a systems/equipment root cause
  with no such consequence reaching a subject. "Reached a subject" means
  the subject actually received something different from what the
  protocol specified as a result of the failure — out-of-spec product
  actually administered, the wrong kit/randomization assignment actually
  dispensed — not merely that the failure happened at a point in the
  process near the subject. A temperature excursion or kit-assignment
  mismatch caught and corrected before dispensing/dosing stays `technical`;
  once the subject is actually dosed or dispensed the wrong assignment, the
  uncertainty about whether they were harmed is itself the reason it
  escalates to `major` — this is a precautionary threshold, not a proof-of-harm one.
- *vs. administrative* — if a documentation gap changed what a subject was
  told or could decide (e.g. an outdated consent form withheld new safety
  information), that's `major`, not `administrative`.

## minor

**Definition:** Low-impact deviation with no bearing on subject safety or
data integrity.

**Examples:**
- A visit was conducted a few days outside its protocol-specified window,
  for a non-critical assessment.
- A non-critical questionnaire was not completed at a visit.
- A dose was taken a few hours later than scheduled, with no clinical
  impact.

**Boundary notes:**
- *vs. administrative* — `minor` involves an actual protocol-specified
  clinical activity happening off-spec (wrong timing, wrong device);
  `administrative` involves paperwork about who's authorized or when
  something was filed, not the clinical activity itself.
- *vs. major* — see major's boundary note above; the line is whether the
  timing slip had any real safety or data consequence.

## technical

**Definition:** Deviation caused by equipment, systems, or
procedural/technical failure, rather than a human judgment call.

**Examples:**
- A temperature excursion was recorded in drug storage.
- An IVRS/randomization system outage caused an incorrect kit assignment.
- An ePRO device malfunctioned, causing loss of patient-reported outcome
  data.

**Boundary notes:**
- *vs. minor* — `minor` is a human/process timing slip; `technical` is a
  system or piece of equipment failing on its own, independent of what
  staff decided to do.
- *vs. major* — see major's boundary note; a technical failure escalates to
  `major` only if it actually reached and affected a subject.

## administrative

**Definition:** Documentation, delegation, or training paperwork issue with
no direct clinical impact.

**Examples:**
- The delegation-of-authority log was not updated before a staff member
  performed a procedure.
- A continuing-review submission to the IRB was submitted after the
  required deadline.
- A source document was missing a signature or date.

**Boundary notes:**
- *vs. major* — the discriminator is whether the paperwork gap changed what
  the subject was told or could decide, versus being purely a
  version-control/documentation gap. An outdated consent form used with no
  new safety information withheld stays `administrative`; if it withheld
  something material, it's `major`.
- *vs. minor* — see minor's boundary note; `administrative` deviations
  don't involve the clinical activity itself going off-spec.

## unreported

**Definition:** A deviation occurred (of any underlying type or severity)
but was never logged or reported within the required timeframe — discovered
later via monitoring or audit. This is a reporting-compliance category,
**orthogonal to the other four** (it's about the failure to report, not
what happened).

**Examples:**
- A monitoring visit revealed a deviation from months earlier that was
  never logged.
- An audit found an off-protocol dose that was never submitted as a
  deviation report.
- Database lock review revealed a missed visit that had never been
  documented as a deviation.

**Boundary notes:**
- Write/label `unreported` from the discovery/audit perspective — the
  emphasis is on the fact that reporting never happened, not on the
  severity of the underlying event. A report describing the *original*
  event (dosing error, missed visit, etc.) without mentioning a reporting
  gap belongs in one of the other four categories instead.
- In principle any deviation could also be "unreported" — in practice, use
  this category only when the report's whole point is the discovery of the
  gap itself, since that's the distinct triage action it implies (file the
  missed report / investigate why it wasn't caught), rather than tagging
  every deviation with two labels.
