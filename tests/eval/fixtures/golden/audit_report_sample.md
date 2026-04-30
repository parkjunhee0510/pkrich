# LLM Audit Report — 2026-04-28

**Window:** 2026-04-15 ~ 2026-04-28 (14d) | **Tickers:** 2 | **Replay cost:** $0.00
**Overall verdict:** 1 fail / 0 warn / 1 pass / 0 info (out of 2)

## Executive Summary

Audit completed with 1 fail, 0 warn, and 0 insufficient-data checks. Failing checks: I3. Insufficient-data checks: none.

## Verdict Matrix

| ID | Dimension | Severity | Pass rate | Samples | Top metric |
|----|-----------|----------|-----------|---------|------------|
| I1 | schema_stability | OK pass | 100.0% | 0 | missing_field_rate=0.000 |
| I3 | format_consistency | FAIL fail | 33.0% | 0 | format_count=3.000 |

## 차원별 상세

### I1 — severity: pass
- missing_field_rate: 0.0000

### I3 — severity: fail
- format_count: 3.0000

**Recommendation:** Normalize ISO.

## Methodology

The audit reads existing ticker output and pipeline logs only, except D1 replay when enabled. Checks with no evaluable samples are reported as info instead of pass so missing evidence is visible.
