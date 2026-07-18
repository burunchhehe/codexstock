# CodexStock Research Forge

Research Forge is CodexStock's research-only strategy validation sub-engine. It is exposed as one product and one MCP gateway, while its internal responsibilities remain separate.

## Runtime boundaries

```text
CodexStock MCP
└─ Research Forge Gateway
   ├─ Data Adapter
   ├─ Strategy & Validation Lab
   ├─ Experiment Registry
   ├─ Microstructure Store
   └─ Replay & Report
```

The Strategy Lab is a batch/CPU workload. Microstructure collection is an append-only, restartable event workload and should run in a separate process when a live provider is connected. They share contracts, not execution loops.

## Safety invariants

```yaml
decision_scope: research_only
live_order_allowed: false
requires_codexstock_validation: true
```

Research Forge has no broker-order adapter. `PAPER_CANDIDATE` is a recommendation only and is never an automatic promotion or live-order authorization.

## Durable async worker

Run one recovery cycle:

```powershell
codexstock-research-forge worker --once
```

Run a continuous owner-death monitor and restart worker:

```powershell
codexstock-research-forge worker --poll-seconds 5 --orphan-grace-seconds 30
```

Every execution owns an atomic filesystem lease. The worker does not steal a job from a live process; it only marks a stale running job interrupted after its owner is confirmed dead, then reconstructs the original typed handler from the persisted job payload. `async_jobs/worker_status.json` is the machine-readable heartbeat. Use an OS service supervisor if this command must start automatically after a machine reboot.

## KIS read-only realtime

Install the optional dependency with `pip install -e ".[realtime]"`, then use `research_realtime_status` and `research_realtime_start`. The collector uses only the official domestic-stock quotation streams `H0STCNT0` (trades) and `H0STASP0` (ten-level order book). It has no order TR, forces `read_only=true`, restores every subscription after reconnect, echoes KIS PINGPONG frames, rejects malformed field counts and persists its checkpoint under `realtime/checkpoint.json`.

Live KIS traffic currently uses 46 fields for `H0STCNT0` and 62 fields for `H0STASP0`; the latter includes KRX midpoint price, midpoint total quantity and midpoint classification. Run quality separates gaps occurring inside a connected collection from gaps between separate bounded sessions. KIS realtime frames do not provide an exchange sequence number, so timestamp gaps, cumulative-volume behavior, reconnect counts and duplicate hashes cannot alone prove that no packet was lost. A full market-hours soak remains a release gate for a lossless claim.

Each bounded realtime run writes a credential-free immutable evidence file under `realtime/runs/`. `research_realtime_runs` recomputes every SHA-256 hash and reports altered files. The evidence contains run timing, accepted/duplicate counts, reconnects, internal and session-boundary gaps, read-only policy and final per-stream checkpoint summaries.

For a time-bounded market-session soak, run `codexstock-research-forge realtime-soak --symbols 005930 --duration-seconds 18000`. The same bound is available as `duration_seconds` on `research_realtime_start`; set `max_messages` to zero when duration is the only stop condition.

Only one collector may own a realtime root. A fresh `RUNNING` checkpoint blocks a second start, and every new collector also claims an atomic `collector.lease` containing its PID. A lease is reclaimed only after the owner process is confirmed dead; this prevents two processes from corrupting the append-only events or checkpoint.

`research_microstructure_archive_export` copies only newly appended complete JSONL lines into immutable ZSTD Parquet chunks, so the live collector is never paused. The manifest records the source byte offset, source-chunk hash, row count, Parquet hash and compression size. `research_microstructure_archive_verify` validates the manifest and every archived file; a repeated export starts exactly at the saved byte offset.

`research_microstructure_archive_query` uses DuckDB to apply bounded symbol, UTC time-range and event-type filters across the archived chunks. It reports both returned and total matched rows plus truncation. Parquet is the scalable/compact path, not an unconditional low-row-count speed claim: the completion audit records the measured JSONL and Parquet latency at the current archive size.

Replay creation accepts `microstructure_source=live|archive|hybrid`. Archive mode remains functional if JSONL logs have been moved out of hot storage. Hybrid mode reads both and deduplicates on the immutable provider event ID before sorting and hashing the timeline; source input counts and the final unique count are stored in replay metadata.

## CLI

```powershell
python -m codexstock_research_forge status
python -m codexstock_research_forge doctor
python -m codexstock_research_forge mcp manifest
python -m codexstock_research_forge demo
```

Set `CODEXSTOCK_RESEARCH_FORGE_HOME` to relocate experiment, report, and microstructure runtime data.

## Data provenance

- `mock`: deterministic smoke tests only.
- `synthetic`: the legacy `NativeBacktester`; never evidence of market performance.
- `historical_provider`: local adjusted OHLCV cache with a recorded SHA-256 digest.
- `KRX KIND listed-company Excel`: official exact-date current snapshot. It is source-hashed, deduplicated, and never treated as proof of earlier delisted membership.

Official KIND snapshots may be accumulated in a `PointInTimeUniverseHistory`. The first capture is a baseline; later captures produce explicit add/remove/update events and allow deterministic reconstruction only between captured coverage dates. Same-date identical captures are idempotent. A current-only baseline does not pass as complete historical universe evidence.

`research_universe_sync_global_history` supplements the current KIND baseline with official KRX Global initial-listing, relisting and delisting statistics. Every annual JSON response is SHA-256 hashed and retried with bounded backoff. When neither an initial-listing nor relisting row can be matched to a delisted code, the interval begins at the requested coverage start and `precoverage_listing_dates_clipped` is incremented. Such a dataset is useful for reducing survivorship bias but intentionally fails the strict complete-history evidence gate.

Invalid OHLC rows, non-monotonic timestamps, missing execution costs, missing adjusted-price evidence, and missing point-in-time universe evidence block promotion.

## Strategy DSL

The DSL is a typed JSON object, not executable Python. Supported strategy types are `ma_cross`, `portfolio_ma_cross`, composable `indicator_rules`, and `multi_timeframe_indicator_rules`. Multi-timeframe operands name a declared context; higher bars become visible only at explicit `available_at` or their calculated close time. Unknown keys and arbitrary executable surfaces are rejected.

An `ma_cross` strategy may declare `label_horizon_rows` from 0 through 10,000 when its target or event label remains unresolved across a known number of observations. `research_strict_walk_forward_run` accepts calendar boundaries (`purge_days`, `embargo_days`) and observation boundaries (`purge_rows`, `embargo_rows`). The effective training-tail purge is the greater of the request and `label_horizon_rows`; invalid negative or oversized values are rejected before merging. Real OHLCV adapters apply row exclusions after date and source filtering, and reports retain requested, declared, effective, and fold-level row counts. Example arguments:

```json
{
  "experiment_id": "exp_...",
  "folds": 3,
  "fast_values": [3, 5, 8],
  "slow_values": [20, 50],
  "purge_days": 5,
  "embargo_days": 5,
  "purge_rows": 10,
  "embargo_rows": 2
}
```

Custom indicators are immutable versioned expression trees over approved fields, built-in indicators, constants, arithmetic, and lag. Registration requires fixed golden cases and automatically checks deterministic output plus prefix stability at every test row, preventing formulas that change past values after future rows arrive. No Python, imports, file access, or network calls are accepted.

LS, Kiwoom, and KIS compatibility is evidence-driven per indicator. An HTS reference package must include its immutable export id, source-file SHA-256, platform profile, export timestamp, symbol, timeframe, input OHLCV, parameters, at least ten timestamped output references, and an absolute tolerance. Every reference point is compared and the registry stores max error, RMSE, mismatch samples, and source identity. One passing RSI export verifies only that profile's RSI; a whole profile is not marked fully verified until all built-ins have passing exports.

Use `research_hts_csv_template` to obtain the exact CSV header for a profile and indicator. Every file begins with `timestamp,open,high,low,close,volume` followed by the indicator's `hts_*` output columns. Keep warmup outputs blank, provide at least 20 chronological timezone-aware OHLCV rows and at least 10 rows containing HTS outputs, then send the unchanged text plus export metadata to `research_hts_csv_import`. The importer hashes the exact CSV text, rejects header drift, duplicate/out-of-order timestamps, malformed OHLCV and non-finite values, builds the immutable package, and runs the same per-output verifier. It never promotes other indicators or an entire profile from one passing file.

## Analytical storage and background jobs

DuckDB stores deduplicated bars and exports ZSTD Parquet partitioned by timeframe, year, month, and an eight-way stable symbol hash bucket. The legacy adjusted-OHLCV JSON cache is migrated as a stream, so the full file is never loaded into memory. A source-hash checkpoint records completed symbols and isolated invalid rows; interrupted imports resume without reloading completed symbols. Bulk timestamps are forced through a string cast so offsets are not normalized twice.

Long backtests, strict walk-forward runs, and collection runs can be submitted through `research_async_submit`. Job state is atomically persisted and exposes percentage, phase, result, structured failure, cancellation request, and attempt count. Jobs left `RUNNING` by a worker-process restart become `INTERRUPTED` and can be retried from their persisted payload.

`research_concurrency_soak` runs collection, DuckDB writes and reads, indicator calculations, and a compatible stored backtest in parallel. It persists timings and structured errors, then removes its synthetic database rows.

## Execution modes

`OPTIMISTIC`, `REALISTIC`, and `CONSERVATIVE` presets define costs, delay, volume participation, impact, and queue assumptions. Optimistic results are blocked from promotion evidence. Active volatility interruptions reject fills. When price-level execution and queue-ahead quantities are present, fill capacity is the lesser of the bar-volume cap and execution remaining after the modeled queue; otherwise the declared missing-queue haircut is recorded. `research_execution_compare` applies identical signals to all modes.

## Replay and evidence reports

`research_replay_create` creates an immutable, hashed timeline that merges daily/minute bars, ticks, order books, program flow, and strategy trades in deterministic timestamp order. `research_replay_page` provides bounded cursor pages and reconstructs chart, order-book, and position state at the cursor.

Report export produces JSON, Markdown, and Excel plus a SHA-256 evidence manifest. The bundle records the experiment, dataset evidence, code version, adapter, seed, validation decision, and execution model. `research_report_verify` detects a changed experiment or any missing or modified report artifact.

## Microstructure event contract

Event types are `tick`, `orderbook`, and `program_flow`.

```json
{
  "event_type": "tick",
  "symbol": "005930",
  "timestamp": "2026-07-13T09:00:00+09:00",
  "source": "KIS",
  "payload": {"price": 70000, "quantity": 10}
}
```

Events require timezone-aware timestamps. The store rejects time regression, suppresses recent duplicates, records gaps, partitions JSONL by event type/date/symbol, and atomically updates a restart checkpoint.

The KIS polling worker is forced into real-account read-only quotation mode and cannot access order submission. It captures recent item conclusions as ticks, ten-level order books, and the official `program-trade-by-stock` feed. Rolling REST windows are expected to overlap: exact events are deduplicated and unseen rows older than the stream checkpoint are counted as stale overlap instead of violating time order. Workers persist cycle, failure, capability, and availability state and may run as cancellable asynchronous jobs.

## Current limitations

- KIS read-only REST polling for ticks, ten-level order books, and program flow is integrated. A WebSocket subscription worker is still preferable for exchange-level event completeness and lower latency.
- Official KRX snapshot ingestion is implemented, but the configured Open API key currently receives HTTP 401 until the KRX service permission is approved. A single snapshot is deliberately rejected as evidence for a longer historical period.
- The local adjusted OHLCV cache contains known invalid rows in some periods; the quality gate intentionally fails those experiments.
- Volume participation, partial fills, latency, costs, market impact, suspensions, and price-limit blocks are modeled. Exchange order-book queue position is not yet modeled.
- Background execution is process-local; persisted interrupted jobs require an explicit retry after an MCP worker restart.
