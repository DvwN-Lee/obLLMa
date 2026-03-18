# Benchmark Results

| 항목 | 값 |
|------|-----|
| **Date** | 2026-03-15 |
| **Hardware** | Apple Silicon (Docker Desktop, CPU mode — no Metal GPU passthrough) |
| **Model** | qwen2.5:7b (Q4_K_M, 4.7GB) |
| **Ollama** | v0.18.0, OLLAMA_NUM_THREADS=6, OLLAMA_KEEP_ALIVE=5m, OLLAMA_MAX_LOADED_MODELS=1 |
| **Proxy** | FastAPI + prometheus_client, MAX_CONCURRENT_REQUESTS=4 |

## S1 Baseline (Single Request Latency)

| Metric | Avg | P50 | P95 | P99 |
|--------|-----|-----|-----|-----|
| TTFT (s) | 0.804 | 0.753 | 1.453 | 1.453 |
| Duration (s) | 30.532 | 33.051 | 46.205 | 46.205 |
| TPS (tok/s) | 9.8 | 9.9 | 11.0 | 11.0 |
| Output Tokens | 306.0 | 331.0 | 458.0 | 458.0 |

- Requests: 5 | Errors: 0 | Wall time: 152.8s
- Observations: CPU-only inference yields ~10 TPS. TTFT is sub-1s with no queuing.

## S3 Sustained Load (Concurrency 4, 20 Requests)

| Metric | Avg | P50 | P95 | P99 |
|--------|-----|-----|-----|-----|
| TTFT (s) | 212.199 | 161.082 | 489.488 | 536.069 |
| Duration (s) | 293.174 | 292.607 | 538.641 | 551.365 |
| TPS (tok/s) | 3.0 | 1.8 | 6.5 | 12.0 |
| Output Tokens | 678.8 | 568.0 | 1849.0 | 2062.0 |

- Requests: 20 | Errors: 0 | Wall time: 1661.3s
- Observations: With concurrency=4 on CPU, semaphore queuing dominates TTFT. TPS drops to ~3 avg due to resource contention. This demonstrates why observability matters — without metrics, the queuing latency would be invisible.

## Key Insights

1. **TTFT is the canary metric**: Under load, TTFT degrades ~264x (0.8s -> 212s) while TPS only drops 3x. TTFT captures queuing effects that TPS alone cannot.
2. **CPU vs GPU gap**: Docker CPU mode (~10 TPS) vs native Metal would show significant improvement. The observability stack captures this difference.
3. **Zero errors at load**: The semaphore-based concurrency control (MAX_CONCURRENT_REQUESTS=4) prevents OOM while maintaining 100% success rate.
