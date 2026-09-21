# Phase 6 Evaluation Report

**Cases:** 33 (21 clear-cut, 12 boundary)

## Classification accuracy
- Overall: 97.0%
- Clear-cut cases: 95.2%
- Boundary cases: 100.0%

## Memo completeness (rubric)
- Mean rubric score: 0.99 / 1.00
- `summary_substantive`: 100.0% pass rate
- `root_cause_substantive`: 100.0% pass rate
- `capa_actions_sufficient`: 100.0% pass rate
- `capa_actions_tailored`: 100.0% pass rate
- `expedited_flag_correct`: 93.9% pass rate
- `ownership_fields_present`: 100.0% pass rate

## Evidence grounding (agentic pipeline)
- Cases with a checkable expected_evidence field: 5
- Correct evidence found: 5/5

## Queue delivery latency
- Mean: 91.00s
- Median: 42.14s
- Max: 1588.05s

## Misclassified cases
- EVAL-013 (boundary=False): expected `technical`, predicted `major` (confidence 0.75)
