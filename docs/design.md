# design.md: llm-serving-observability

> **Phase**: 2 (DESIGN)
> **Track**: Feature
> **입력**: docs/plans/2026-03-14-llm-serving-observability.md, docs/findings/2026-03-14-research-findings.md

---

## 1. Architecture Overview

### 1-1. System Diagram

```
                macOS Host
 ┌────────────────────────────────────────┐
 │  Ollama (native, Metal GPU)            │
 │  localhost:11434                        │
 │  /v1/chat/completions (OpenAI compat)  │
 └──────────▲─────────────────────────────┘
            │ ${OLLAMA_BASE_URL}
            │ (default: http://ollama:11434)
 ┌──────────┼─────────────────────────────────────┐
 │          │          Docker Compose              │
 │  ┌───────┴──────────────────┐                   │
 │  │  LLM Proxy (FastAPI)      │──► /metrics      │
 │  │  :8000                    │    (Prometheus)   │
 │  │  /v1/chat/completions     │                   │
 │  │  /health                  │                   │
 │  └───────▲──────────────────┘                   │
 │          │ POST /v1/chat/completions             │
 │  ┌───────┴──────────────┐                        │
 │  │  Load Generator       │                        │
 │  │  (Python asyncio)     │                        │
 │  └──────────────────────┘                        │
 │                                                  │
 │  ┌──────────────┐    ┌────────────┐              │
 │  │  Prometheus   │───►│  Grafana    │             │
 │  │  :9090        │    │  :3000      │             │
 │  └──────────────┘    └────────────┘              │
 │                                                  │
 │  ┌──────────────┐ (docker-compose 포함, fallback) │
 │  │  Ollama       │                                │
 │  │  :11434       │                                │
 │  └──────────────┘                                │
 └──────────────────────────────────────────────────┘
```

### 1-2. Ollama Hybrid Strategy

Docker Compose에 Ollama 서비스를 포함하여 `docker compose up` 한 번으로 전체 스택이 기동되도록 한다 (Constitution #1 준수). 단, macOS에서 Metal GPU를 사용하려면 네이티브 Ollama가 필요하므로 `OLLAMA_BASE_URL` 환경변수로 전환한다.

| 모드 | OLLAMA_BASE_URL | GPU | 용도 |
|------|----------------|-----|------|
| Docker (기본) | `http://ollama:11434` | CPU only | Quick start, CI, 기능 검증 |
| Native (Metal) | `http://host.docker.internal:11434` | Metal GPU | 벤치마크, 성능 측정 |

### 1-3. Request Lifecycle (Streaming)

```
Client ──POST /v1/chat/completions──► Proxy
                                        │
                                   [1] semaphore.acquire()
                                   [2] llm_active_requests.inc()
                                   [3] start = time.monotonic()
                                        │
                                   [4] stream POST to Ollama
                                        │
                                   [5] first content chunk → TTFT 기록
                                   [6] SSE chunks passthrough to client
                                   [7] usage chunk → token counts 기록
                                   [8] [DONE] → duration, TPS 기록
                                        │
                                   [9] llm_active_requests.dec()
                                   [10] semaphore.release()
```

### 1-4. Request Lifecycle (Non-Streaming)

```
Client ──POST /v1/chat/completions──► Proxy
                                        │
                                   [1] semaphore.acquire()
                                   [2] llm_active_requests.inc()
                                   [3] start = time.monotonic()
                                        │
                                   [4] POST to Ollama (stream=false)
                                   [5] response 수신 → duration 기록
                                   [6] usage에서 token counts 기록
                                   [7] TPS 계산 및 기록
                                        │
                                   [8] llm_active_requests.dec()
                                   [9] semaphore.release()
```

---

## 2. Public Interface Definition

### 2-1. Proxy API Endpoints

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| POST | `/v1/chat/completions` | OpenAI 호환 채팅 API (프록시) | ChatCompletionRequest | SSE stream / JSON |
| GET | `/health` | 프록시 + Ollama 헬스체크 | - | `{"status": "ok", "ollama": "connected"}` |
| GET | `/metrics` | Prometheus 메트릭 노출 | - | text/plain (Prometheus exposition) |

> **구현 참고**: `/metrics`는 `make_asgi_app()` + `app.mount()` 대신 `@app.get("/metrics")` + `generate_latest()` 패턴을 사용한다. `app.mount()`는 trailing slash 리다이렉트(307) 버그로 Prometheus 스크래핑이 실패할 수 있다 ([prometheus/client_python #1016](https://github.com/prometheus/client_python/issues/1016)).

### 2-2. Request Model

```python
class ChatCompletionRequest(BaseModel):
    model: str                           # e.g. "qwen2.5:7b"
    messages: list[Message]              # [{"role": "user", "content": "..."}]
    stream: bool = True                  # default: streaming
    temperature: float = 0.7
    max_tokens: int | None = None
    # 기타 OpenAI 호환 필드는 Ollama로 passthrough
```

### 2-3. Response (Streaming SSE)

```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"}}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","choices":[],"usage":{"prompt_tokens":11,"completion_tokens":42}}

data: [DONE]
```

Ollama의 `/v1/chat/completions`는 OpenAI와 동일한 SSE 포맷(`data: {...}\n\n`)으로 응답한다 (네이티브 `/api/generate`의 NDJSON과는 다름). 프록시는 이 SSE 응답을 그대로 패스스루하되, 각 청크를 파싱하여 메트릭을 수집한다.

### 2-4. Configuration (Environment Variables)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama 서버 주소 |
| `PROXY_PORT` | `8000` | 프록시 리스닝 포트 |
| `MAX_CONCURRENT_REQUESTS` | `4` | 동시 처리 최대 요청 수 (세마포어) |
| `DEFAULT_MODEL` | `qwen2.5:7b` | 모델 미지정 시 기본 모델 |
| `LOG_LEVEL` | `info` | 로그 레벨 |

> **httpx timeout**: Ollama 응답은 30~120초 소요 가능. httpx 기본 read timeout(5초)으로는 부족하므로, 프록시에서 `httpx.Timeout(connect=10.0, read=None)` 설정이 필수다.

---

## 3. Data Model: Metrics

Constitution #2(메트릭 SSOT)에 따라 모든 메트릭은 `proxy/metrics.py` 한 파일에서 정의한다.

### 3-1. Request-Level Metrics

| # | Name | Type | Labels | Buckets | Description |
|---|------|------|--------|---------|-------------|
| M1 | `llm_request_duration_seconds` | Histogram | `model` | `[0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120]` | E2E 요청 처리 시간 |
| M2 | `llm_ttft_seconds` | Histogram | `model` | `[0.001, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]` | Time to First Token |
| M3 | `llm_tokens_per_second` | Histogram | `model` | `[1, 5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200, 300]` | 출력 토큰 생성 속도 |
| M4 | `llm_time_per_output_token_seconds` | Histogram | `model` | `[0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.2, 0.5, 1.0]` | Time Per Output Token (TPOT). 계산: `duration / output_tokens` |
| M5 | `llm_input_tokens_total` | Counter | `model` | - | 누적 입력 토큰 수 |
| M6 | `llm_output_tokens_total` | Counter | `model` | - | 누적 출력 토큰 수 |
| M7 | `llm_requests_total` | Counter | `model`, `status`, `stream` | - | 총 요청 수 |
| M8 | `llm_request_errors_total` | Counter | `model`, `status_code` | - | 에러 요청 수 |

### 3-2. Serving-Level Metrics

| # | Name | Type | Labels | Description |
|---|------|------|--------|-------------|
| M9 | `llm_active_requests` | Gauge | - | 현재 처리 중 요청 수 (세마포어 내부) |
| M10 | `llm_queue_depth` | Gauge | - | 세마포어 대기 중 요청 수 |
| M11 | `llm_model_loaded` | Gauge | `model`, `quantization` | 로드된 모델 정보 (1=loaded, 0=unloaded) |

### 3-3. Label Strategy

| Label | Values | 적용 메트릭 |
|-------|--------|-----------|
| `model` | `"qwen2.5:7b"`, `"qwen2.5:14b"`, etc. | M1~M8, M11 |
| `status` | `"success"`, `"error"` | M7 |
| `stream` | `"true"`, `"false"` | M7 |
| `status_code` | `"500"`, `"502"`, `"504"`, etc. | M8 |
| `quantization` | `"Q4_K_M"`, `"Q8_0"`, etc. | M11 |

### 3-4. Histogram Bucket Rationale

- **E2E Duration**: LLM 응답은 2~60초 범위. Prometheus 기본 버킷(~10초)으로 불충분. [0.1~120초] 범위로 확장.
- **TTFT**: OTel GenAI + vLLM 표준 기반. 밀리초~초 단위로 세분화 (첫 토큰 도착의 미세 차이가 UX에 중요).
- **TPS**: M4 Pro 7B 기준 20~45 tok/s. [1~200] 범위로 7B와 14B 모두 커버.
- **TPOT**: Time Per Output Token. `duration / output_tokens`로 계산. [5ms~1초] 범위. vLLM `time_per_output_token_seconds` 참조.

### 3-5. Concurrency Control

```
MAX_CONCURRENT_REQUESTS = 4 (configurable)

asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
├── 세마포어 내부: llm_active_requests (Gauge)
└── 세마포어 대기: llm_queue_depth (Gauge)
```

세마포어 기반 동시성 제한으로 Ollama의 순차 처리 특성을 명시적으로 관리한다. 부하 테스트에서 동시 요청이 세마포어 한도를 초과하면 `llm_queue_depth`가 증가하며, 이것이 관측의 핵심 포인트이다.

---

## 4. Grafana Dashboard Structure

### 4-1. Dashboard File

단일 JSON 파일: `grafana/dashboards/llm-overview.json`

Template variable: `$model` (label_values from `llm_requests_total`)

### 4-2. Panel Layout (Z-Pattern, 24-column grid)

| Row | Left (w=12) | Right (w=12) | Height |
|-----|-------------|--------------|--------|
| 0 | Request Rate (stat) w=6 | Error Rate % (stat+threshold) w=6 | h=4 |
| 0 | Active Requests (gauge) w=6 | Queue Depth (gauge) w=6 | h=4 |
| 1 | Request Duration P50/P95/P99 (timeseries) | TTFT P50/P95/P99 (timeseries) | h=8 |
| 2 | Tokens Per Second (timeseries) | TPOT - Time Per Output Token (timeseries) | h=8 |
| 3 | Input vs Output Tokens Rate (timeseries) | Model Info (table) | h=6 |

### 4-3. Key PromQL Queries

| Panel | PromQL |
|-------|--------|
| Request Rate | `sum by (model) (rate(llm_requests_total{model=~"$model"}[5m]))` |
| Error Rate % | `sum(rate(llm_request_errors_total{model=~"$model"}[5m])) / sum(rate(llm_requests_total{model=~"$model"}[5m])) * 100` |
| Active Requests | `llm_active_requests` |
| Queue Depth | `llm_queue_depth` |
| Duration P50 | `histogram_quantile(0.50, sum(rate(llm_request_duration_seconds_bucket{model=~"$model"}[5m])) by (le))` |
| Duration P95 | `histogram_quantile(0.95, sum(rate(llm_request_duration_seconds_bucket{model=~"$model"}[5m])) by (le))` |
| Duration P99 | `histogram_quantile(0.99, sum(rate(llm_request_duration_seconds_bucket{model=~"$model"}[5m])) by (le))` |
| TTFT P50 | `histogram_quantile(0.50, sum(rate(llm_ttft_seconds_bucket{model=~"$model"}[5m])) by (le))` |
| TTFT P95 | `histogram_quantile(0.95, sum(rate(llm_ttft_seconds_bucket{model=~"$model"}[5m])) by (le))` |
| TPS P50 | `histogram_quantile(0.50, sum(rate(llm_tokens_per_second_bucket{model=~"$model"}[5m])) by (le))` |
| TPS P95 | `histogram_quantile(0.95, sum(rate(llm_tokens_per_second_bucket{model=~"$model"}[5m])) by (le))` |
| TPOT P95 | `histogram_quantile(0.95, sum(rate(llm_time_per_output_token_seconds_bucket{model=~"$model"}[5m])) by (le))` |
| Input Tokens Rate | `sum by (model) (rate(llm_input_tokens_total{model=~"$model"}[5m]))` |
| Output Tokens Rate | `sum by (model) (rate(llm_output_tokens_total{model=~"$model"}[5m]))` |

---

## 5. File Structure

```
llm-serving-observability/
├── docker-compose.yml              # All services (Ollama, Proxy, Prometheus, Grafana)
├── .env.example                    # OLLAMA_BASE_URL, MAX_CONCURRENT_REQUESTS, etc.
├── proxy/
│   ├── Dockerfile                  # Python 3.12-slim, uvicorn
│   ├── requirements.txt            # fastapi, uvicorn, httpx, prometheus_client
│   ├── main.py                     # FastAPI app, routes, streaming pipeline
│   ├── metrics.py                  # Prometheus metric definitions (SSOT)
│   └── config.py                   # Environment variable loading
├── prometheus/
│   └── prometheus.yml              # scrape_configs: proxy:8000/metrics
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── prometheus.yml      # Prometheus datasource (http://prometheus:9090)
│   │   └── dashboards/
│   │       └── dashboards.yml      # Dashboard file provider
│   └── dashboards/
│       └── llm-overview.json       # Main dashboard JSON
├── loadtest/
│   ├── run.py                      # Python asyncio load generator
│   ├── scenarios.py                # S1~S5 scenario definitions
│   └── requirements.txt            # httpx, asyncio
└── README.md                       # Portfolio README + screenshots
```

---

## 6. Technical Decisions

### D-1. OpenAI Compatible API for Both Directions

**결정**: 프록시는 내부(Ollama 연결)와 외부(클라이언트 제공) 모두 `/v1/chat/completions` 사용.

**대안**: Ollama native `/api/generate` (NDJSON, 나노초 타이밍 제공).

**근거**:
- Constitution #4(OpenAI 호환성) 준수 — 엔진 교체 시 URL만 변경
- 포맷 변환 불필요 (SSE passthrough) — 복잡도 감소
- `stream_options.include_usage: true`로 토큰 카운트 확보 가능
- 타이밍은 프록시 레벨 `time.monotonic()`으로 충분 (관측 목적)
- vLLM, TGI 등으로 교체 시 프록시 코드 변경 0건

### D-2. Python asyncio Load Generator (k6 대신)

**결정**: Python asyncio + httpx로 부하 테스트 구현.

**대안**: k6 + xk6-sse.

**근거**:
- SSE 스트리밍 네이티브 지원 (k6는 xk6-sse 커스텀 빌드 필요)
- TTFT 직접 측정 가능 (클라이언트 관점 검증)
- 프록시와 동일 기술 스택 (Python) — 학습 비용 0
- asyncio.Semaphore로 동시성 제어 직관적

### D-3. Semaphore-based Concurrency Control

**결정**: 프록시에 `asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)` 적용.

**근거**:
- Ollama는 요청을 순차 처리 — 무제한 동시 요청은 TTFT만 악화
- 세마포어 대기자 수 = `llm_queue_depth` 메트릭으로 직결
- 부하 테스트에서 동시성 증가 → 큐 깊이 증가 패턴을 명확히 시각화

### D-4. System Metrics Scope Out

**결정**: `llm_memory_used_bytes`, `llm_metal_gpu_utilization`은 Phase 3 범위에서 제외.

**근거**:
- Metal GPU 사용률은 `powermetrics`(sudo 필요) + Docker 외부 수집 필요 — 플랫폼 의존적
- 핵심 LLM 서빙 메트릭(M1~M11)이 관측 가능성의 본질
- 시스템 메트릭은 향후 선택적 Enhancement로 분리

### D-5. Single Dashboard JSON

**결정**: 대시보드 1개 파일(`llm-overview.json`)로 Overview + Latency + Throughput 통합.

**대안**: 3개 대시보드 분리 (Overview, Latency, Resource).

**근거**:
- 패널 수 10개 이하 — 분리 시 전환 번거로움만 증가
- Template variable `$model`로 모델별 필터링 가능
- 포트폴리오 스크린샷 시 단일 대시보드가 더 임팩트

### D-6. Queue Wait Time Metric Scope Out

**결정**: `llm_queue_wait_seconds` Histogram은 Phase 3 범위에서 제외.

**대안**: 세마포어 acquire 전후 타임스탬프 차이로 큐 대기 시간 측정.

**근거**:
- 구현 시 `asyncio.Semaphore` 래퍼 클래스(CapacitySemaphore) 필요 — 복잡도 증가
- `llm_queue_depth` Gauge로 큐 상태는 이미 관측 가능
- findings R-3에서 권장되었으나, 현 11개 메트릭으로 LLM 서빙 관측의 핵심은 충분히 커버
- 향후 Enhancement로 분리 가능
