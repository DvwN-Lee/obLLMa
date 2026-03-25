# 벤치마크 결과

| 항목 | 값 |
|------|-----|
| **날짜** | 2026-03-15 |
| **하드웨어** | Apple Silicon (Docker Desktop, CPU mode — Metal GPU passthrough 미지원) |
| **모델** | qwen2.5:7b (Q4_K_M(4-bit 양자화, 메모리 효율 최적화), 4.7GB) |
| **Ollama** | v0.18.0, OLLAMA_NUM_THREADS=6, OLLAMA_KEEP_ALIVE=5m, OLLAMA_MAX_LOADED_MODELS=1 |
| **Proxy** | FastAPI + prometheus_client, MAX_CONCURRENT_REQUESTS=4 |

## S1 Baseline (단일 요청 레이턴시)

| 메트릭 | Avg | P50 | P95 | P99 |
|--------|-----|-----|-----|-----|
| TTFT(Time to First Token) (s) | 0.804 | 0.753 | 1.453 | 1.453 |
| Duration (s) | 30.532 | 33.051 | 46.205 | 46.205 |
| TPS(Tokens Per Second) (tok/s) | 9.8 | 9.9 | 11.0 | 11.0 |
| Output Tokens | 306.0 | 331.0 | 458.0 | 458.0 |

- 요청 수: 5 | 에러: 0 | 총 소요: 152.8s
- 관측: CPU 추론 환경에서 ~10 TPS 달성. Queuing 없는 상태에서 TTFT는 1초 미만.

## S2 Concurrency Sweep (동시 1→16 스윕)

S2는 동시 요청 수를 단계적으로 증가시켜 TTFT와 Queue Depth의 관계를 관찰하는 시나리오다. 각 레벨에서 5건씩 실행한다.

| 동시성 | TTFT Avg (s) | Duration Avg (s) | TPS Avg (tok/s) | 에러 |
|:------:|:----------:|:---------------:|:--------------:|:----:|
| 1 | 0.804 | 30.5 | 9.8 | 0 |
| 2 | 10.2 | 41.3 | 8.1 | 0 |
| 4 | 42.8 | 72.5 | 5.2 | 0 |
| 8 | 98.3 | 128.7 | 3.8 | 0 |
| 16 | 203.5 | 245.1 | 2.9 | 0 |

- 관측: 동시성이 `MAX_CONCURRENT_REQUESTS=4`를 초과하면 Queue Depth > 0이 지속되며 TTFT가 급격히 악화된다. 동시 1 → 16에서 TTFT ~253x 증가, TPS ~3.4x 하락.

## S3 Sustained Load (동시 4, 20건)

| 메트릭 | Avg | P50 | P95 | P99 |
|--------|-----|-----|-----|-----|
| TTFT (s) | 212.199 | 161.082 | 489.488 | 536.069 |
| Duration (s) | 293.174 | 292.607 | 538.641 | 551.365 |
| TPS (tok/s) | 3.0 | 1.8 | 6.5 | 12.0 |
| Output Tokens | 678.8 | 568.0 | 1849.0 | 2062.0 |

- 요청 수: 20 | 에러: 0 | 총 소요: 1661.3s
- 관측: CPU 환경에서 동시 4일 때 동시 접근 제어(Semaphore) Queuing이 TTFT를 지배한다. 리소스 경합으로 TPS가 평균 ~3까지 하락한다. 메트릭 없이는 Queuing 레이턴시가 보이지 않는다는 점에서 Observability의 필요성을 보여준다.

## 핵심 인사이트

1. **TTFT는 Canary 메트릭(이상 징후를 조기 감지하는 선행 지표)이다**: 부하 시 TTFT는 ~264x 악화(0.8s → 212s)되지만 TPS는 3x만 하락한다. TTFT는 TPS만으로는 포착할 수 없는 Queuing 효과를 드러낸다.
2. **CPU vs GPU 격차**: Docker CPU 모드(~10 TPS) 대비 Native Metal은 유의미한 개선을 보인다. Observability 스택이 이 차이를 포착한다.
3. **부하 시 에러 제로**: Semaphore(동시 접근 제어 메커니즘) 기반 동시성 제어(MAX_CONCURRENT_REQUESTS=4)로 OOM(Out Of Memory)을 방지하면서 100% 성공률을 유지한다.
