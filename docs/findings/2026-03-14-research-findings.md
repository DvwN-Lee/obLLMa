# findings: LLM Serving Observability 기술 조사

**조사일**: 2026-03-14
**조사 범위**: Ollama API, FastAPI+prometheus_client 계측, Grafana 프로비저닝, LLM 서빙 메트릭 표준, 부하 테스트 도구
**플랜 참조**: `docs/plans/2026-03-14-llm-serving-observability.md`

---

## 결론 (Conclusions)

1. **프록시 계측은 필수**: Ollama 네이티브 `/api/metrics`는 기본 수준. 프록시에서 TTFT, TPS, 토큰 수를 직접 계측해야 한다.
2. **메트릭 설계는 vLLM + OTel GenAI 스펙을 참조**: 플랜의 메트릭 설계가 업계 표준과 잘 정렬되어 있으나, histogram 버킷과 레이블 전략을 보강해야 한다.
3. **FastAPI + prometheus_client 조합은 검증됨**: `make_asgi_app()` + `BaseHTTPMiddleware` 패턴으로 `/metrics` 노출 가능.
4. **스트리밍 TTFT 측정 전략 확립**: Ollama NDJSON 스트리밍에서 첫 비어있지 않은 `response` 청크 타임스탬프로 측정.
5. **부하 테스트는 Python asyncio 추천**: k6+xk6-sse도 가능하나, Python이 TTFT 측정·Prometheus 통합에 더 직관적.
6. **Grafana 프로비저닝은 Docker 볼륨 마운트로 완전 자동화 가능**: datasource + dashboard JSON 모두 GitOps 가능.

---

## R-1. Ollama API

### OpenAI 호환 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/v1/chat/completions` | POST | OpenAI 호환 채팅 API |
| `/api/generate` | POST | Ollama 네이티브 생성 API (더 상세한 메트릭) |
| `/api/tags` | GET | 설치된 모델 목록 |
| `/api/ps` | GET | 현재 로드된 모델 상태 (GPU/CPU 비율) |
| `/api/pull` | POST | 모델 다운로드 (NDJSON 진행률) |
| `/` | GET | 헬스체크 ("Ollama is running") |

- API 키 불필요 (제공해도 무시됨)
- 모델 자동 언로드: 5분 (환경변수 `OLLAMA_KEEP_ALIVE`로 변경 가능)

### 스트리밍 응답 형식

**포맷**: NDJSON (`application/x-ndjson`), SSE가 아닌 줄 구분 JSON.

```json
{"model":"qwen2.5:7b","created_at":"2026-03-14T...","response":"Hello","done":false}
{"model":"qwen2.5:7b","created_at":"2026-03-14T...","response":" world","done":false}
{"model":"qwen2.5:7b","created_at":"2026-03-14T...","response":"","done":true,
 "total_duration":174560334,"load_duration":101397084,
 "prompt_eval_count":11,"prompt_eval_duration":13074791,
 "eval_count":18,"eval_duration":52479709}
```

**핵심**: 토큰 수(`prompt_eval_count`, `eval_count`)와 시간 정보는 **최종 청크(`done:true`)에만** 포함.

### 토큰 카운팅

| API | 입력 토큰 필드 | 출력 토큰 필드 | 단위 |
|-----|--------------|--------------|------|
| `/api/generate` | `prompt_eval_count` | `eval_count` | 개수 |
| `/api/generate` | `prompt_eval_duration` | `eval_duration` | 나노초 |
| `/v1/chat/completions` | `usage.prompt_tokens` | `usage.completion_tokens` | 개수 |

- 스트리밍 시 `/v1/chat/completions`에서 `stream_options.include_usage: true` 설정 필요
- TPS 계산: `eval_count / eval_duration * 1e9`

### 네이티브 메트릭

- `/api/metrics` 존재하나 기본 수준 (요청 수, 인퍼런스 시간 정도)
- **커뮤니티 대안**: [ollama-metrics](https://github.com/NorskHelsenett/ollama-metrics) (프록시 기반 확장)
- **결론**: 프록시에서 직접 계측하는 플랜의 접근이 올바름

### Apple Silicon 성능 (M4 Pro 24GB)

| 모델 | 예상 TPS | 비고 |
|------|---------|------|
| 7B Q4 (qwen2.5:7b 등) | 20~45 tok/s | 쾌적, 메트릭 수집에 적합 |
| 14B Q4 (qwen2.5:14b) | ~10 tok/s | 느리지만 구동 가능 |

- **병목**: 메모리 대역폭 (273 GB/s), GPU 코어 수가 아님
- Metal 가속 필수 (Ollama 0.5+)
- 동시 요청 시 TTFT가 급격히 증가 (큐잉 효과)

---

## R-2. FastAPI + prometheus_client 계측 패턴

### 아키텍처 패턴

```python
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI()

# 메트릭 정의
llm_requests_total = Counter(
    'llm_requests_total', 'Total LLM requests',
    ['model', 'status', 'stream']
)
llm_request_duration = Histogram(
    'llm_request_duration_seconds', 'E2E request duration',
    ['model'],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120]
)
llm_ttft = Histogram(
    'llm_ttft_seconds', 'Time to first token',
    ['model'],
    buckets=[0.001, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
)
llm_active_requests = Gauge('llm_active_requests', 'Active requests')

# /metrics 엔드포인트 마운트
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

### TTFT 측정 로직 (스트리밍 프록시)

```python
import time
import httpx

async def proxy_streaming(request_body, model):
    start = time.monotonic()
    first_token_received = False

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", OLLAMA_URL, json=request_body) as resp:
            async for line in resp.aiter_lines():
                chunk = json.loads(line)

                if not first_token_received and chunk.get("response"):
                    ttft = time.monotonic() - start
                    llm_ttft.labels(model=model).observe(ttft)
                    first_token_received = True

                yield line  # StreamingResponse로 클라이언트에 전달

                if chunk.get("done"):
                    duration = time.monotonic() - start
                    llm_request_duration.labels(model=model).observe(duration)
                    # 토큰 수 기록
                    llm_output_tokens.labels(model=model).inc(chunk.get("eval_count", 0))
```

### 핵심 라이브러리

| 라이브러리 | 용도 | 비고 |
|-----------|------|------|
| `prometheus_client` | 메트릭 정의·노출 | `make_asgi_app()`으로 ASGI 통합 |
| `httpx` | Ollama로의 비동기 HTTP 프록시 | 스트리밍 지원 (`client.stream()`) |
| `fastapi` | API 프레임워크 | `StreamingResponse`로 SSE 중계 |
| `uvicorn` | ASGI 서버 | 프로덕션 서빙 |

---

## R-3. LLM 서빙 메트릭 업계 표준

### 플랜 메트릭 vs 업계 표준 검증

| 플랜 메트릭 | 업계 대응 (vLLM) | OTel GenAI | 판정 |
|------------|-----------------|-----------|------|
| `llm_request_duration_seconds` | `vllm:e2e_request_latency_seconds` | `gen_ai.server.request.duration` | 적합 |
| `llm_ttft_seconds` | `vllm:time_to_first_token_seconds` | `gen_ai.server.time_to_first_token` | 적합 |
| `llm_tokens_per_second` | (계산 메트릭) | - | 적합 (recording rule 권장) |
| `llm_input_tokens_total` | `vllm:prompt_tokens_total` (Counter) | `gen_ai.client.token.usage` | 적합 |
| `llm_output_tokens_total` | `vllm:generation_tokens_total` (Counter) | `gen_ai.client.token.usage` | 적합 |
| `llm_requests_total` | `vllm:request_success_total` | - | 적합 |
| `llm_request_errors_total` | (finished_reason=error) | - | 적합 |
| `llm_active_requests` | `vllm:num_requests_running` | - | 적합 |
| `llm_queue_depth` | `vllm:num_requests_waiting` | - | 적합 |
| `llm_model_loaded` | - | - | 적합 (Ollama 특화) |
| (없음) | `vllm:time_per_output_token_seconds` | `gen_ai.server.time_per_output_token` | **추가 권장** |
| (없음) | `vllm:kv_cache_usage_perc` | - | 선택 (vLLM 전용) |

### 추가 권장 메트릭

| 메트릭 | 타입 | 설명 | 근거 |
|--------|------|------|------|
| `llm_time_per_output_token_seconds` | Histogram | 토큰 간 평균 시간 (ITL) | vLLM/TGI 표준, 스트리밍 품질 지표 |
| `llm_queue_wait_seconds` | Histogram | 큐 대기 시간 | vLLM `time_in_queue`, 용량 계획 필수 |

### Histogram 버킷 권장

| 메트릭 | 권장 버킷 | 출처 |
|--------|---------|------|
| TTFT | `[0.001, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]` | OTel GenAI + vLLM |
| E2E Duration | `[0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120]` | LLM 특성 (긴 생성) |
| TPS | `[1, 5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200]` | M4 Pro 7B 기준 |
| Token Count | `[1, 4, 16, 64, 256, 1024, 4096, 16384]` | OTel GenAI 로그스케일 |

### 레이블 전략

**필수**: `model`, `status` ("success", "error"), `stream` ("true", "false")
**권장**: `quantization`, `finished_reason` ("stop", "length", "error")
**향후 OTel 정렬**: `gen_ai.operation.name`, `gen_ai.provider.name`

---

## R-4. Grafana 프로비저닝

### Docker Compose 볼륨 구조

```yaml
services:
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
      - GF_PATHS_PROVISIONING=/etc/grafana/provisioning
    volumes:
      - ./grafana/provisioning/datasources:/etc/grafana/provisioning/datasources
      - ./grafana/provisioning/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - grafana-data:/var/lib/grafana
```

### Datasource YAML (`grafana/provisioning/datasources/prometheus.yml`)

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      httpMethod: POST
      timeInterval: "15s"
```

### Dashboard Provider YAML (`grafana/provisioning/dashboards/dashboards.yml`)

```yaml
apiVersion: 1
providers:
  - name: 'LLM Monitoring'
    orgId: 1
    folder: 'LLM'
    type: file
    disableDeletion: false
    editable: true
    updateIntervalSeconds: 10
    options:
      path: /var/lib/grafana/dashboards
```

### 대시보드 JSON 핵심 구조

```json
{
  "uid": "llm-overview",
  "title": "LLM Serving Overview",
  "tags": ["llm", "observability"],
  "timezone": "browser",
  "schemaVersion": 39,
  "refresh": "30s",
  "time": { "from": "now-1h", "to": "now" },
  "templating": {
    "list": [{
      "name": "model",
      "type": "query",
      "query": "label_values(llm_requests_total, model)",
      "datasource": { "type": "prometheus", "uid": "prometheus" }
    }]
  },
  "panels": [
    {
      "type": "timeseries",
      "title": "Request Rate",
      "gridPos": { "x": 0, "y": 0, "w": 12, "h": 8 },
      "targets": [{
        "expr": "rate(llm_requests_total{model=~\"$model\"}[5m])",
        "legendFormat": "{{model}} - {{status}}"
      }]
    }
  ]
}
```

### 핵심 PromQL 패턴

```promql
# 요청률 (RPS)
sum by (model) (rate(llm_requests_total[5m]))

# 에러율 (%)
sum(rate(llm_request_errors_total[5m])) / sum(rate(llm_requests_total[5m])) * 100

# TTFT P95
histogram_quantile(0.95, sum(rate(llm_ttft_seconds_bucket[5m])) by (le))

# E2E Latency P95/P99
histogram_quantile(0.95, sum(rate(llm_request_duration_seconds_bucket[5m])) by (le, model))
histogram_quantile(0.99, sum(rate(llm_request_duration_seconds_bucket[5m])) by (le, model))

# TPS (토큰 처리량)
sum(rate(llm_output_tokens_total[5m]))

# 활성 요청
llm_active_requests
```

### 레이아웃 권장 (Z-패턴)

| 위치 | 패널 | 타입 | gridPos |
|------|------|------|---------|
| 좌상 | Total Request Rate | stat | w=6, h=4 |
| 우상 | Error Rate (%) | stat+threshold | w=6, h=4 |
| 좌상2 | Active Requests | gauge | w=6, h=4 |
| 우상2 | Queue Depth | gauge | w=6, h=4 |
| 중좌 | Request Duration P50/P95/P99 | timeseries | w=12, h=8 |
| 중우 | TTFT Distribution | timeseries | w=12, h=8 |
| 하좌 | Tokens Per Second | timeseries | w=12, h=8 |
| 하우 | Input vs Output Tokens | timeseries | w=12, h=8 |

---

## R-5. 부하 테스트 도구

### 도구 비교

| 도구 | SSE 지원 | TTFT 측정 | Prometheus 통합 | 난이도 | 추천 |
|------|---------|----------|----------------|--------|------|
| **k6 + xk6-sse** | 확장 필요 | 가능 | Remote Write | 중 | 대규모 부하 |
| **Python asyncio + httpx** | 네이티브 | 직접 구현 | 직접 구현 | 하 | **1순위 권장** |
| **LLM Locust** | 지원 | 자동 | 내장 | 중 | LLM 특화 |
| **vLLM benchmark_serving.py** | 지원 | 자동 | - | 하 | 참조용 |

### Python asyncio 부하 테스트 (권장)

**이유**:
- 프록시가 이미 Python(FastAPI)이므로 기술 스택 통일
- httpx의 스트리밍 지원으로 TTFT 직접 측정
- `asyncio.Semaphore`로 동시성 제어
- 결과를 Prometheus Pushgateway 또는 파일로 출력
- k6 빌드 의존성(xk6-sse 커스텀 빌드) 없음

### 권장 테스트 시나리오

| # | 시나리오 | 동시성 | 프롬프트 | 목적 |
|---|---------|--------|---------|------|
| S1 | Baseline | 1 | 짧음 (50 tok) | 단일 요청 레이턴시 기준선 |
| S2 | Concurrency Sweep | 1,2,4,8,16 | 짧음 | 동시성 vs 성능 곡선 |
| S3 | Sustained Load | 4 (고정) | 혼합 | 안정성, 메모리 누수 확인 |
| S4 | Variable Prompt | 4 | 50/200/500 tok | 프롬프트 길이 vs 성능 |
| S5 | Model Comparison | 4 | 동일 | 7B vs 14B 비교 |

### Periscope 참조 프로젝트

[wizenheimer/periscope](https://github.com/wizenheimer/periscope): k6 + Grafana + InfluxDB로 OpenAI 호환 엔드포인트 벤치마킹하는 오픈소스 프로젝트. 5가지 테스트 유형 (Smoke, Stress, Spike, Soak, Recovery) 포함.

---

## 근거 (Evidence)

| 항목 | 출처 | 내용 |
|------|------|------|
| E-1 | [Ollama OpenAI Compatibility](https://docs.ollama.com/api/openai-compatibility) | `/v1/chat/completions` 포맷, API 키 불필요 |
| E-2 | [Ollama Streaming Docs](https://docs.ollama.com/api/streaming) | NDJSON 스트리밍, 최종 청크 토큰 정보 |
| E-3 | [prometheus_client Python](https://github.com/prometheus/client_python) | `make_asgi_app()`, Histogram 커스텀 버킷, ASGI 통합 |
| E-4 | [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/) | async generator 스트리밍, SSE media_type |
| E-5 | [vLLM Metrics Design](https://docs.vllm.ai/en/latest/design/metrics/) | `vllm:` 프리픽스 메트릭, TTFT/TPOT Histogram |
| E-6 | [HuggingFace TGI Metrics](https://huggingface.co/docs/text-generation-inference/en/reference/metrics) | TGI 20개 메트릭, 배치 레벨 상세 |
| E-7 | [OTel GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/) | `gen_ai.server.*` 메트릭, 버킷 권장사항 |
| E-8 | [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/) | YAML 프로비저닝, 볼륨 마운트, 대시보드 JSON |
| E-9 | [k6 xk6-sse](https://github.com/phymbert/xk6-sse) | k6 SSE 확장, 스트리밍 TTFT 측정 |
| E-10 | [Periscope](https://github.com/wizenheimer/periscope) | k6 LLM 벤치마킹 레퍼런스 프로젝트 |
| E-11 | [LLM Locust](https://github.com/truefoundry/llm-locust) | Python LLM 부하 테스트, TTFT/ITL 자동 |
| E-12 | [Ollama M4 Pro Benchmark](https://www.linkedin.com/pulse/benchmarking-local-ollama-llms-apple-m4-pro-vs-rtx-3060-dmitry-markov-6vlce) | 20-45 tok/s (7B), 메모리 대역폭 병목 |
| E-13 | [ollama-metrics](https://github.com/NorskHelsenett/ollama-metrics) | Ollama 프록시 기반 메트릭 확장 |
| E-14 | [NVIDIA LLM Benchmarking](https://developer.nvidia.com/blog/llm-benchmarking-fundamental-concepts/) | TTFT, TPS, E2E 정의 |

---

## 권장 사항 (Architect/Dev 세션 전달)

### 플랜 보강 항목

1. **메트릭 추가**: `llm_time_per_output_token_seconds` (ITL) Histogram 추가 — 스트리밍 품질의 핵심 지표
2. **Histogram 버킷 명시**: vLLM/OTel 기반 버킷 값을 `metrics.py`에 상수로 정의
3. **레이블 전략 확정**: 최소 `model`, `status`, `stream` / 권장 `quantization`, `finished_reason`
4. **Ollama 네이티브 API 활용**: `/v1/chat/completions` 대신 `/api/generate` 사용 시 나노초 단위 시간 정보 획득 가능 (더 정밀한 계측)

### 구현 시 주의사항

5. **스트리밍 TTFT**: 첫 비어있지 않은 `response` 필드의 청크 시간 기록 (빈 문자열 무시)
6. **토큰 수 수집**: 스트리밍 시 `done:true` 최종 청크에서만 토큰 수를 추출 — 버퍼링 필요
7. **동시 요청 시 TTFT 급증**: Ollama는 요청을 순차 처리하므로, 동시 요청이 늘면 TTFT가 선형적으로 증가. 이것이 관측해야 할 핵심 현상.
8. **`stream_options.include_usage: true`**: OpenAI 호환 API 사용 시 스트리밍에서 usage 정보 포함하려면 이 옵션 필수

### 도구 선택

9. **부하 테스트**: Python asyncio + httpx 1순위 (기술 스택 통일, 빌드 의존성 없음)
10. **참조 프로젝트**: Periscope (k6 기반), LLM Locust (Python 기반) 구조 참고
