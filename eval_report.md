# Phase 6 Evaluation Report

**Cases:** 30 (20 clear-cut, 10 boundary)

## Classification accuracy
- Overall: 96.7%
- Clear-cut cases: 100.0%
- Boundary cases: 90.0%

## Memo completeness (rubric)
- Mean rubric score: 0.98 / 1.00
- `summary_substantive`: 100.0% pass rate
- `root_cause_substantive`: 100.0% pass rate
- `capa_actions_sufficient`: 100.0% pass rate
- `capa_actions_tailored`: 100.0% pass rate
- `expedited_flag_correct`: 90.0% pass rate
- `ownership_fields_present`: 100.0% pass rate

## Queue delivery latency
- Mean: 10.33s
- Median: 9.88s
- Max: 19.84s

## Misclassified cases
- EVAL-006 (boundary=True): expected `major`, predicted `administrative` (confidence 0.78)
