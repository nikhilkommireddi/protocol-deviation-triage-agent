# Protocol Deviation Label Schema

Five mutually-exclusive categories used to triage protocol deviation reports.
This is the canonical definition source — the synthetic data generators
(`scripts/generate_synthetic_deviations.py`, `scripts/generate_reports.py`)
and the eventual classifier and CAPA-lookup node should all trace back to
this file rather than re-deriving definitions independently.

**Status: first draft.** Written from general clinical-trial-operations
knowledge, not yet validated against ICH E6(R3) or real FDA Warning Letter
language (Chunk 1.2). Treat category boundaries as provisional until that
reading pass happens — they're specific enough to drive consistent labeling
today, but the wording may need to shift once compared to real regulatory
text.

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
  with no such consequence reaching a subject. A temperature excursion is
  `technical` unless out-of-spec product actually reached a subject, in
  which case it's `major`.
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
