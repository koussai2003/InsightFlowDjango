# InsightFlow Django — local performance check

**Run date:** 15 November 2026  
**Tool:** Locust 2.47.0  
**Python:** 3.13.2  
**Django:** 6.1.3  
**Server:** Django development server at `127.0.0.1:8021`  
**Load:** 20 simulated users, ramped at 4 users/second, 30-second run limit

## Results

| Endpoint | Requests | Failures | Average response | Median | 95th percentile | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| `GET /api/health/` | 332 | 0 | 3.14 ms | 3 ms | 6 ms | 17.12 ms |
| `GET /api/csrf/` | 105 | 0 | 3.38 ms | 3 ms | 5 ms | 10.35 ms |
| **Combined** | **437** | **0** | **3.20 ms** | **3 ms** | **6 ms** | **17.12 ms** |

Combined throughput in the Locust CSV was approximately **14.95 requests/second**. The request mix is weighted toward health checks, as configured by the task weights in `locustfile.py`.

## What the result suggests

During this small local run, both endpoints responded quickly and Locust recorded no failed requests. The longest response was about 17 ms. This is a smoke-level baseline for these lightweight endpoints on this computer.

## Limits

- This ran against Django’s development server on the same machine, not a production server or remote database.
- Both endpoints are lightweight. The health check does not query the database, and the CSRF endpoint does not exercise project queries, CSV upload, image storage, WebSockets, or ML/data processing.
- The local `.env` selects SQLite, but this run does not establish PostgreSQL performance because these requests do not exercise database-backed features.
- This single short run is not a capacity limit or SLA. Repeat with a production-like server/database and representative authenticated operations before drawing broader conclusions.

## Reproduce

From this project folder:

1. Start the server in one terminal: `python manage.py runserver 127.0.0.1:8021`.
2. In another terminal run:

   ```powershell
   .\.venv\Scripts\python.exe -m locust -f locustfile.py --host http://127.0.0.1:8021 --headless -u 20 -r 4 -t 30s --only-summary --csv performance/locust-baseline --csv-full-history
   ```

3. Compare the terminal summary with `locust-baseline_stats.csv`. The saved CSV files are the raw record for this run.

## Saved Locust output

- `locust-baseline_stats.csv` — endpoint and aggregate counts/latencies.
- `locust-baseline_stats_history.csv` — time-series snapshots during the run.
- `locust-baseline_failures.csv` — failed-request details (none for this run).
- `locust-baseline_exceptions.csv` — Locust-side exceptions (none for this run).
