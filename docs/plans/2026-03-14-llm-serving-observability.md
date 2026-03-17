# llm-serving-observability 설계 문서

> **status**: superseded-by-design-md
> **작성일**: 2026-03-14
> **레포**: `llm-serving-observability` (신규, GitHub 핀 슬롯 3)
> **원안**: ai-agent-strategy.md Phase 3-B에서 분리·재정의

---

## 1. 목적

LLM 서빙의 **관측 가능성(Observability)** 구축을 학습하고 포트폴리오로 증명한다.

기존 인프라 경험(K8s, Prometheus, Grafana, ArgoCD)은 이미 보유.
이 레포에서 증명할 것은 **LLM 서빙 특화 메트릭 설계 + 대시보드 구현** 역량이다.

| 증명 대상 | 내용 |
|-----------|------|
| LLM 메트릭 이해 | TTFT, TPS, 레이턴시 분포 등 LLM 서빙 고유 지표 |
| 계측 설계 | OpenAI 호환 프록시에 Prometheus 메트릭 삽입 |
| 대시보드 설계 | Grafana로 LLM 서빙 운영 대시보드 구성 |
| 부하 테스트 | 동시 요청 증가에 따른 성능 변화 측정·시각화 |

**범위 밖 (YAGNI)**:
- K8s 배포, ArgoCD GitOps → 기존 경험으로 충분, 중복 증명 불필요
- LangSmith, RAGAS → fAInancial-agent에서 LangFuse + RAGAS 이미 경험
- Fine-tuning → 별도 프로젝트 범위

---

## 2. 환경

### 로컬 (비용 $0)

| 항목 | 값 |
|------|-----|
| 머신 | MacBook Pro M4 Pro / 24GB RAM |
| LLM 서빙 | Ollama (Metal GPU 가속) |
| 모델 | 7B~14B Q4 양자화 |
| 모니터링 | Prometheus + Grafana (Docker) |
| 부하 테스트 | k6 또는 Python 스크립트 |

### 클라우드 (선택, 스크린샷용)

| 항목 | 값 |
|------|-----|
| 인스턴스 | RunPod Spot (~$0.5/hr) 또는 GCP Spot |
| LLM 서빙 | vLLM (CUDA) |
| GPU 메트릭 | DCGM Exporter |
| 사용 시간 | 2~3시간 (벤치마크 + 스크린샷 촬영 후 종료) |

---

## 3. 아키텍처

```
                        Docker Compose
 ┌──────────────────────────────────────────────────────┐
 │                                                      │
 │  ┌──────────┐    ┌─────────────────────┐             │
 │  │  Ollama   │◄───│  LLM Proxy (FastAPI) │──► /metrics│
 │  │  :11434   │    │  :8000               │            │
 │  └──────────┘    └─────────────────────┘             │
 │                           ▲                          │
 │                           │ POST /v1/chat/completions│
 │                  ┌────────┴────────┐                 │
 │                  │  Load Generator  │                 │
 │                  │  (k6 / Python)   │                 │
 │                  └─────────────────┘                 │
 │                                                      │
 │  ┌────────────┐    ┌──────────┐                      │
 │  │ Prometheus  │───►│ Grafana   │                     │
 │  │ :9090       │    │ :3000     │                     │
 │  └────────────┘    └──────────┘                      │
 └──────────────────────────────────────────────────────┘
```

### 핵심 컴포넌트

| # | 컴포넌트 | 역할 |
|---|----------|------|
| 1 | **Ollama** | LLM 서빙 엔진. Metal 가속, OpenAI 호환 API 제공 |
| 2 | **LLM Proxy** | Ollama 앞단 FastAPI 프록시. 요청/응답을 계측하여 Prometheus 메트릭 노출 |
| 3 | **Prometheus** | /metrics 스크래핑, 시계열 저장 |
| 4 | **Grafana** | LLM 서빙 대시보드 시각화 |
| 5 | **Load Generator** | 동시 요청 생성, 부하 시나리오 실행 |

### 왜 프록시인가?

Ollama 자체 `/api` 엔드포인트는 Prometheus 메트릭을 노출하지 않는다.
LLM Proxy가 요청을 중계하면서 토큰 수, 레이턴시, TTFT 등을 계측하고 `/metrics`로 노출한다.
이 설계는 vLLM, TGI 등 다른 LLM 서빙 엔진으로 교체해도 프록시만 수정하면 된다.

---

## 4. LLM 서빙 메트릭

### 4-1. 요청 레벨 메트릭

| 메트릭 | 타입 | 설명 |
|--------|------|------|
| `llm_request_duration_seconds` | Histogram | 전체 요청 처리 시간 (P50/P95/P99) |
| `llm_ttft_seconds` | Histogram | Time to First Token (스트리밍 첫 토큰까지 시간) |
| `llm_tokens_per_second` | Histogram | 초당 생성 토큰 수 (TPS) |
| `llm_input_tokens_total` | Counter | 누적 입력 토큰 수 |
| `llm_output_tokens_total` | Counter | 누적 출력 토큰 수 |
| `llm_requests_total` | Counter | 총 요청 수 (status, model 레이블) |
| `llm_request_errors_total` | Counter | 에러 요청 수 |

### 4-2. 서빙 레벨 메트릭

| 메트릭 | 타입 | 설명 |
|--------|------|------|
| `llm_active_requests` | Gauge | 현재 처리 중인 동시 요청 수 |
| `llm_queue_depth` | Gauge | 대기 중인 요청 수 |
| `llm_model_loaded` | Gauge | 로드된 모델 정보 (레이블: model, quantization) |

### 4-3. 시스템 메트릭 (Mac)

> **Note**: design.md D-4에서 Phase 3 범위 제외 결정. proxy/metrics.py에 미정의.

| 메트릭 | 타입 | 설명 |
|--------|------|------|
| ~~`llm_memory_used_bytes`~~ | ~~Gauge~~ | ~~Ollama 프로세스 메모리 사용량~~ |
| ~~`llm_metal_gpu_utilization`~~ | ~~Gauge~~ | ~~Metal GPU 사용률 (powermetrics 기반)~~ |

---

## 5. Grafana 대시보드 설계

### 5-1. Overview 패널

```
┌─────────────────────────┬──────────────────────────┐
│  Total Requests (Rate)  │  Error Rate (%)          │
│  [시계열 그래프]         │  [시계열 그래프]          │
├─────────────────────────┼──────────────────────────┤
│  Active Requests        │  Queue Depth             │
│  [Gauge]                │  [Gauge]                 │
└─────────────────────────┴──────────────────────────┘
```

### 5-2. Latency 패널

```
┌─────────────────────────┬──────────────────────────┐
│  Request Duration       │  TTFT Distribution       │
│  P50 / P95 / P99        │  P50 / P95 / P99         │
│  [시계열 그래프]         │  [히스토그램]             │
├─────────────────────────┼──────────────────────────┤
│  Tokens Per Second      │  Input vs Output Tokens  │
│  [시계열 그래프]         │  [시계열 그래프]          │
└─────────────────────────┴──────────────────────────┘
```

### 5-3. Resource 패널

```
┌─────────────────────────┬──────────────────────────┐
│  Memory Usage           │  GPU Utilization (Metal)  │
│  [시계열 그래프]         │  [시계열 그래프]          │
└─────────────────────────┴──────────────────────────┘
```

---

## 6. 모델 선택

| 모델 | 크기 | 한국어 | M4 Pro 24GB 구동 | 비고 |
|------|------|--------|-----------------|------|
| `qwen2.5:7b` | ~4.4GB | 양호 | 쾌적 | 다국어 강점, 벤치마크 상위 |
| `llama3.1:8b` | ~4.7GB | 보통 | 쾌적 | 영어 중심, 범용 |
| `exaone3.5:7.8b` | ~4.9GB | 우수 | 쾌적 | LG AI Research, 한국어 특화 |
| `qwen2.5:14b` | ~9GB | 양호 | 원활 | 품질↑, 속도↓ 트레이드오프 측정용 |

**기본 모델**: `qwen2.5:7b` (빠른 응답 → 메트릭 수집에 유리)
**비교 모델**: `exaone3.5:7.8b` (한국어 품질 비교) 또는 `qwen2.5:14b` (크기별 성능 비교)

모델 간 전환으로 "모델 크기 vs 서빙 성능" 비교 대시보드를 만들 수 있다.

---

## 7. 태스크 분해

| # | 태스크 | 산출물 | 의존성 |
|---|--------|--------|--------|
| T1 | 프로젝트 셋업 + Ollama 연동 | Docker Compose, Ollama 헬스체크, 모델 pull 자동화 | - |
| T2 | LLM Proxy (FastAPI) | OpenAI 호환 프록시 + Prometheus 메트릭 노출 | T1 |
| T3 | Prometheus + Grafana 스택 | docker-compose에 추가, prometheus.yml, Grafana provisioning | T1 |
| T4 | Grafana 대시보드 구현 | JSON 대시보드 (Overview + Latency + Resource) | T2, T3 |
| T5 | Load Generator + 벤치마크 | k6 스크립트 또는 Python, 시나리오별 부하 테스트 | T2 |
| T6 | 모델 비교 벤치마크 | 7B vs 14B 성능 비교 데이터 + 대시보드 패널 | T4, T5 |
| T7 | README + 스크린샷 | 포트폴리오 README, 대시보드 스크린샷/GIF | T4, T6 |

### 의존성 그래프

```
T1 ──► T2 ──► T4 ──► T6 ──► T7
 │            ▲       ▲
 └───► T3 ───┘   T5 ──┘
```

T2와 T3은 병렬 진행 가능.

---

## 8. 변경 파일 목록 (예상)

| 파일 | 태스크 |
|------|--------|
| `docker-compose.yml` | T1, T3 |
| `proxy/main.py` | T2 |
| `proxy/metrics.py` | T2 |
| `proxy/Dockerfile` | T2 |
| `prometheus/prometheus.yml` | T3 |
| `grafana/provisioning/datasources/` | T3 |
| `grafana/provisioning/dashboards/` | T4 |
| `grafana/dashboards/*.json` | T4 |
| `loadtest/script.js` 또는 `loadtest/run.py` | T5 |
| `benchmarks/` | T6 |
| `README.md` | T7 |

---

## 9. YAGNI 적용 항목

| 항목 | 판단 | 근거 |
|------|------|------|
| K8s Deployment | 제외 | 이미 보유한 경험, 중복 증명 불필요 |
| ArgoCD GitOps | 제외 | 동일 |
| vLLM 로컬 구동 | 제외 | CUDA 필수, Mac에서 불가. 클라우드 선택사항 |
| DCGM Exporter | 선택 | 클라우드 GPU 사용 시에만 (스크린샷용) |
| 인증/보안 | 제외 | 로컬 학습용, 외부 노출 없음 |
| 다중 모델 동시 서빙 | 제외 | 단일 모델 전환으로 비교, 24GB RAM 제약 |
| AlertManager | 제외 | 학습 목적, 알람 수신 대상 없음 |

---

## 10. 타겟 JD 매칭

| 회사 | 요구사항 | 이 레포로 증명 |
|------|----------|---------------|
| KB금융 | vLLM/MIG, Multi-Agent | LLM 서빙 메트릭 이해 + 모니터링 설계 |
| KT | Agentic Fabric, LLM 서빙 | LLM Proxy 계측 패턴 |
| 현대오토에버 | MCP, K8s | LLM 인프라 관측 역량 (K8s는 기존 레포) |
| 미래에셋 | vLLM, MCP | LLM 서빙 운영 관점 |

---

## 11. 원안 대비 변경 요약

| 항목 | 원안 (ai-agent-strategy.md) | 변경 |
|------|---------------------------|------|
| 레포명 | `llm-serving-k8s` | `llm-serving-observability` |
| 범위 | vLLM + K8s + ArgoCD + LLMOps | LLM 서빙 모니터링 특화 |
| LLM 엔진 | vLLM (CUDA 필수) | Ollama (로컬) + vLLM (클라우드 선택) |
| 인프라 | GKE/EKS 클러스터 | Docker Compose (로컬) |
| 비용 | GPU 클라우드 상시 | $0 (로컬) ~ $3 (클라우드 스크린샷) |
| 소요 기간 | 5주 | 태스크 7개, 목적 축소로 단축 예상 |
