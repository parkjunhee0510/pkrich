# Data-Layer Code Review — 2026-05-29

**Scope:** `src/collector/**` (collection), `src/utils/datastore*.py` + `signal_tracker.py` + `signal_metadata_backfill.py` (storage), `src/types.py`, and `src/output/{schema,sharded_export,web_sync_contract}.py`. ~13k lines.

**Method:** 5 specialist reviewers ran in parallel (price/market-data, news/policy, paid-providers/macro/SEC/options, collector infrastructure, storage/schema). The author then independently verified the load-bearing Critical/High claims against source. **Confidence tags below:** `✓ verified` (read by author), `~ reported` (from reviewer, plausible, not independently re-read), `✗ corrected` (reviewer claim found wrong or overstated).

---

## Overall verdict

The data layer is **architecturally sound and defensively written**: per-ticker exception isolation is consistent, providers degrade to empty/partial rather than crashing the batch, NaN/Inf coercion is centralized, and provider provenance is tracked. There are **no confirmed pipeline-crashing or silent-history-corrupting bugs in the steady-state path.**

The real risk surface is **silent wrong numbers** flowing into decision scoring, concentrated in four themes:

1. **Non-atomic writes** — a crash mid-write can corrupt/empty the canonical CSV history. *(highest-priority systemic risk)*
2. **Magnitude-based unit heuristics** (`abs(x) < 10` → "it's a decimal") — break for outliers, producing 100×-wrong peer/fundamental metrics.
3. **Price/return computation accuracy** — returns built from the `price` column not `close`; a split-adjustment inconsistency in peer 30-day change.
4. **Web→LLM trust boundary** — policy/news content reaches downstream LLM prompts with thin URL/text validation.

Plus one **confirmed mislabeled macro signal** (yield curve).

---

## Priority findings (cross-cutting)

### P1 — Non-atomic file writes can corrupt history `✓ verified (CSV) / ~ reported (sqlite)`
- `signal_tracker.py:567` (`_write_rows`) opens the CSV with `mode="w"` (truncate) and rewrites all rows — **no temp-file + `os.replace`**. A crash/SIGKILL mid-write leaves a truncated or header-only `signal_tracker.csv`. `✓`
- `datastore_csv.py:91` (`_write_price_rows`) — same pattern for `price_history.csv`. `~`
- `datastore_sqlite.py:175` (`sync_signal_history`) — `DELETE FROM signal_history` then `executemany INSERT`; a crash between them empties the table while CSV stays intact, **silently diverging the two backends**. `~`
- **Fix:** write to `*.tmp` then `os.replace()` (atomic on POSIX, near-atomic on NTFS) for the CSV paths; wrap the SQLite sync in `BEGIN IMMEDIATE` … `COMMIT`/`ROLLBACK`, or use a temp-table swap.

### P2 — Magnitude unit heuristics silently mis-scale outliers `~ reported`
- `yfinance_peer_metrics.py:147`, `fmp.py:437`, `helpers/formatters.py:111` all decide decimal-vs-percent from the *magnitude* of the value (`abs(x) < 10`, `< 0.2`, etc.). For high-leverage ROE, hyper-growth revenue, or high-yield instruments this picks the wrong scale and emits values off by 100× into peer ranking / fundamental scoring.
- **Fix:** use field-specific known units (yfinance `returnOnEquity`/`grossMargins`/`revenueGrowth` are always fractions → ×100 unconditionally). Don't infer units from magnitude.

### P3 — Returns computed from `price`, not `close` `✓ verified` *(reframed from reviewer's "look-ahead bias")*
- `signal_tracker.py:515` — `_build_price_series` reads `row.get("price")`, while `FIELDNAMES` (`datastore.py:15`) carries both `price` (collection-time snapshot) and `close` (settled daily close). If the daily run ever executes intraday, forward returns are measured snapshot-to-snapshot instead of close-to-close, adding noise to every signal-return and win-rate stat.
- This is a **return-accuracy/consistency** issue, **not** look-ahead bias (see Corrected Claims).
- **Fix:** prefer `row.get("close")`, fall back to `price` only when close is `N/A`.

### P4 — Split-adjustment inconsistency in peer 30-day change `~ reported`
- `yfinance_peer_metrics.py:118` fetches with `auto_adjust=False` while the main path uses `auto_adjust=True`. After a split the unadjusted close has a discontinuity, so `price_change_30d` is wrong by the split ratio (e.g. 4× for a 4-for-1), corrupting relative-strength scoring for recently-split peers.
- **Fix:** set `auto_adjust=True` for parity.

### P5 — Mislabeled yield-curve signal `✓ verified`
- `macro.py:225` maps `"us2y" → ("^FVX", "US 5Y")` (`^FVX` is the 5-year yield). The derived `yield_curve_10y_2y` (lines 268–273) is therefore actually a **10Y–5Y spread** but is labeled "10Y-2Y Spread." Inversion fires at different times than a true 2Y curve.
- **Fix:** either rename the key/label to 5Y and document the proxy, or source a genuine 2Y series.

---

## Security / trust boundary (web → LLM) `~ reported`

- `policy_events.py:59` — URL **scheme not validated**; `javascript:`/`data:`/`file:` URLs survive the empty-check and are stored as `source_url`, then rendered/fetched downstream. *Fix:* require `url.startswith(("http://","https://"))`.
- `policy_events.py:184` — LLM-generated `headline`/`summary`/`raw_excerpt` (originating from untrusted web search) flow verbatim into later LLM prompts → **prompt-injection surface**. *Fix:* collapse newlines and strip injection markers before persisting.
- `policy_events.py:23` — dedup id is SHA-1 truncated to **48 bits**; birthday collisions become non-negligible and silently drop real events. *Fix:* SHA-256, ≥64 bits.
- `ir_rss.py:44` / `news_rss.py:171` — `feedparser.parse(url)` with **no timeout** and no scheme guard → SSRF via `file://` in `watchlist.yaml` and pipeline hang on an unresponsive feed. *Fix:* validate scheme; enforce a request timeout.
- `fmp.py:78` (and `finnhub.py`, `polygon_options.py`) — **API key in URL query string**. `✓` The typed error wrappers raise with `endpoint` (not the URL), so the key leaks only via a raw `HTTPError.url` in an unhandled traceback — real but mitigated. *Fix:* prefer an auth header; scrub `exc.url` before logging.
- `sec_edgar.py:16` / `sec_form4.py:25` — SEC User-Agent contact is `local-automation`, not a real email; EDGAR fair-access policy can IP-block this. *Fix:* use a real contact email.

---

## Robustness / external-data resilience `~ reported`

- `rate_limiter.py:214` — `acquire(timeout=None)` blocks indefinitely; a misconfigured low `calls_per_minute` with many tickers can **hang the entire daily run** with no circuit breaker. *Fix:* pass a per-provider timeout and fail the provider on expiry.
- `orchestrator.py:323` — `_resolve_ttl` takes the **max** TTL across all data types a provider emits, so a provider serving both `price` (TTL 0) and `fundamentals` (TTL 24h) caches **price for 24h** → yesterday's price served as today's. *Fix:* cache per-data-type, or use `min`. *(Reviewer notes the code comment acknowledges the simplification — verify before fixing.)*
- `polygon_options.py:67` — snapshot fetches only `limit=50` contracts, **no pagination**; max-pain / GEX / IV-skew are computed on ≤50 contracts and are systematically wrong for liquid names (SPY, AAPL, QQQ). *Fix:* follow the `next_url` cursor.
- `price.py:299` — sector-ETF history is re-fetched once per ticker with no memoization; 20 tech tickers fire 20 identical `XLK` calls back-to-back → throttle risk that drops technicals for the ticker. *Fix:* memoize ETF history by symbol per run.
- `orchestrator.py:159` — in parallel mode, a ticker that raises is `continue`d and absent from output with **no failure entry**, so `failure_count()` undercounts. *Fix:* write a synthetic failure + empty `CollectedTickerData`.

---

## Lower-severity / correctness nits `~ reported`

- `fmp.py:614` — dividend "5y CAGR" uses a 4-year span/exponent; verify off-by-one.
- `macro_events.py:223` — `all_keywords` rule behaves as **OR**, not AND (uses `any(...)`); conjunction rules over-fire.
- `polygon_options.py:122` / `price.py:1066,1269` — DTE/date derived from `date.today()` / `utcfromtimestamp` instead of `run_date`; ±1-day drift if run near midnight or on a non-UTC host.
- `sharded_export.py:158` — tickers dropped from the watchlist have their `tickers/<dir>/history.json` **deleted**, so the frontend loses history permanently. *Fix:* retention window instead of immediate delete.
- `bootstrap.py:29` — config/cache paths are relative to CWD; running outside repo root silently falls back to defaults. *Fix:* anchor to `__file__`.
- `base.py:176` — class-level mutable `provides: set` default; a subclass that mutates rather than reassigns corrupts siblings. *Fix:* `frozenset` default.
- `types.py:240` — `PolicyImpactReport` fields are bare `dict`/`list` (unparameterized) → schema drift vs the web `index.ts` is invisible to type checkers.

---

## Corrected / overstated reviewer claims (transparency)

- `✗` **"Critical: `52w_high` vs `high_52w` column mismatch."** Verified `datastore_sqlite.py:286` (read) and `:635` (write) use the **same** dict keys `52w_high`/`52w_low`; the round-trip is internally consistent. **Not a live bug** — at most a physical-vs-logical naming nit.
- `✗` **"Critical: look-ahead bias in return backfill."** The kernel is real (uses `price` not `close`, see P3) but it is **not** look-ahead bias; reframed to a return-accuracy issue and downgraded.
- `✗` **"Medium: same-day 1D return prematurely evaluated."** False positive — `_future_trading_sessions` (`:539`) uses `signal_date < session_date <= run_date`; when `run_date == signal_date` the set is empty, so this cannot occur.
- `✗` **"High: RSI Wilder seeding double-counts."** The reviewer's own text contradicts itself and partially retracts. **Unverified** — treat as "add a unit test for `technicals.py` RSI seeding against a known reference series," not a confirmed bug.

---

## Recommended next steps (ordered)

1. **P1 atomic writes** — make all three write paths crash-safe. Cheap, high payoff; protects the canonical history.
2. **P3 + P4** — fix return source (`close`) and peer `auto_adjust` parity; these directly affect backtest/signal-quality data the project reports on.
3. **P5 + macro_events OR/AND** — correct the macro signals feeding regime detection.
4. **P2 unit heuristics** — replace magnitude guessing with field-specific units.
5. **Security pass** — URL scheme validation + feed timeouts + SEC email; prompt-injection hardening of policy text.
6. **Verify-then-fix** — `_resolve_ttl` max-vs-min, rate-limiter timeout, polygon pagination (each needs a quick confirm against current behavior before changing).
7. Add unit tests alongside each fix (RSI seeding, CSV↔SQLite round-trip parity, return windows).

*No code was modified during this review.*
