# LLM Serving Observability

LLM 서빙의 관측 가능성(Observability)을 구축하는 프로젝트입니다. Ollama 기반 LLM 서빙에 Prometheus 메트릭 계측과 Grafana 대시보드를 구현합니다.

## Architecture

```
                    macOS Host
 ┌────────────────────────────────────────┐
 │  Ollama (native, Metal GPU)            │
 │  localhost:11434                        │
 └──────────▲─────────────────────────────┘
            │
 ┌──────────┼─────────────────────────────────────┐
 │          │          Docker Compose              │
 │  ┌───────┴──────────────────┐                   │
 │  │  LLM Proxy (FastAPI)      │──► /metrics      │
 │  │  :8000                    │                   │
 │  └───────▲──────────────────┘                   │
 │          │                                      │
 │  ┌───────┴──────────────┐                        │
 │  │  Load Generator       │                        │
 │  │  (Python asyncio)     │                        │
 │  └──────────────────────┘                        │
 │                                                  │
 │  ┌──────────────┐    ┌────────────┐              │
 │  │  Prometheus   │───►│  Grafana    │             │
 │  │  :9090        │    │  :3000      │             │
 │  └──────────────┘    └────────────┘              │
 └──────────────────────────────────────────────────┘
```

**LLM Proxy**가 Ollama 앞단에서 요청을 중계하며, TTFT, TPS, 레이턴시 등 LLM 서빙 고유 메트릭을 Prometheus로 노출합니다.

## LLM Serving Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `llm_request_duration_seconds` | Histogram | E2E 요청 처리 시간 (P50/P95/P99) |
| `llm_ttft_seconds` | Histogram | Time to First Token |
| `llm_tokens_per_second` | Histogram | 출력 토큰 생성 속도 |
| `llm_time_per_output_token_seconds` | Histogram | Time Per Output Token (TPOT) |
| `llm_input_tokens_total` | Counter | 누적 입력 토큰 수 |
| `llm_output_tokens_total` | Counter | 누적 출력 토큰 수 |
| `llm_requests_total` | Counter | 요청 수 (model, status, stream 레이블) |
| `llm_request_errors_total` | Counter | 에러 요청 수 |
| `llm_active_requests` | Gauge | 현재 처리 중 요청 수 |
| `llm_queue_depth` | Gauge | 대기 중 요청 수 |
| `llm_model_loaded` | Gauge | 로드된 모델 정보 |

## Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/DvwN-Lee/obLLMa.git
cd obLLMa
cp .env.example .env  # 필요시 OLLAMA_BASE_URL 수정
```

### 2. Start Stack

```bash
docker compose up -d
```

전체 스택 기동: Ollama, LLM Proxy, Prometheus, Grafana

### 3. Pull Model

```bash
# Docker Ollama 사용 시
docker compose exec ollama ollama pull qwen2.5:7b

# Native Ollama (Metal GPU) 사용 시
# .env에서 OLLAMA_BASE_URL=http://host.docker.internal:11434 설정 후
ollama pull qwen2.5:7b
```

### 4. Verify

```bash
# Proxy health check
curl http://localhost:8000/health

# Send a test request
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5:7b", "messages": [{"role": "user", "content": "Hello"}], "stream": false}'

# Check metrics
curl http://localhost:8000/metrics
```

### 5. Run Load Test

```bash
cd loadtest
pip install -r requirements.txt
python run.py --scenario s1 --base-url http://localhost:8000
```

## Grafana Dashboard

`http://localhost:3000` 에 접속하면 LLM Serving Overview 대시보드가 자동 프로비저닝됩니다.

| Before Load | After Load |
|:-----------:|:----------:|
| ![Baseline](docs/screenshots/grafana-dashboard-baseline.png) | ![Under Load](docs/screenshots/grafana-dashboard.png) |

### Dashboard Panels

| Panel | Description |
|-------|-------------|
| Request Rate | 초당 요청 수 (모델별) |
| Error Rate % | 에러율 퍼센트 |
| Active Requests | 현재 처리 중인 요청 게이지 |
| Queue Depth | 대기 중인 요청 게이지 |
| Request Duration P50/P95/P99 | E2E 레이턴시 분포 |
| TTFT P50/P95/P99 | 첫 토큰까지 시간 분포 |
| Tokens Per Second | 토큰 생성 속도 |
| TPOT | 토큰당 생성 시간 |
| Input vs Output Tokens | 입출력 토큰 처리량 |
| Model Info | 로드된 모델 상태 |

## Load Test Scenarios

```bash
python run.py --scenario s1  # Baseline: 단일 요청 레이턴시
python run.py --scenario s2  # Concurrency Sweep: 1,2,4,8,16 동시 요청
python run.py --scenario s3  # Sustained Load: 4 동시, 20 요청
python run.py --scenario s4  # Variable Prompt: 프롬프트 길이별 비교
python run.py --scenario s5  # Model Comparison: 모델별 성능 비교
```

## Benchmark Results

qwen2.5:7b (Q4_K_M) on Apple Silicon Docker Desktop (CPU mode):

| Scenario | TTFT P50 | TPS Avg | Duration P50 | Errors |
|----------|----------|---------|--------------|--------|
| S1 Baseline (concurrency 1) | 0.8s | 9.8 tok/s | 33.1s | 0% |
| S3 Sustained (concurrency 4, 20 req) | 161.1s | 3.0 tok/s | 292.6s | 0% |

**Key Insight**: Under load, TTFT degrades ~264x (0.8s → 212s) while TPS only drops 3x — TTFT is the canary metric that captures queuing effects invisible to throughput alone.

See [benchmarks/results.md](benchmarks/results.md) for full data and analysis.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM Serving | Ollama (Apple Silicon Metal) |
| Proxy | FastAPI + prometheus_client |
| Monitoring | Prometheus + Grafana |
| Load Testing | Python asyncio + httpx |
| Infrastructure | Docker Compose |

## Project Structure

```
├── docker-compose.yml
├── proxy/
│   ├── main.py              # FastAPI proxy + streaming pipeline
│   ├── metrics.py            # Prometheus metric definitions (SSOT)
│   ├── config.py             # Environment variable loading
│   ├── Dockerfile
│   └── requirements.txt
├── prometheus/
│   └── prometheus.yml        # Scrape configuration
├── grafana/
│   ├── provisioning/         # Auto-provisioning configs
│   └── dashboards/
│       └── llm-overview.json # Grafana dashboard
├── loadtest/
│   ├── run.py               # CLI load generator
│   └── scenarios.py         # S1~S5 scenario definitions
└── benchmarks/              # Benchmark results
```
