# 검증 리포트: Demo 시나리오 적절성 분석

**검증일**: 2026-03-16
**검증 대상**: Load Test 시나리오 S1~S5 및 README Quick Start의 Demo 시연 적절성
**검증 관점**: V-1 정확성 / V-3 성능 / V-4 Spec 정합성
**기준**: project-brief.md 핵심 증명 대상 4항, Constitution #6 재현 가능 벤치마크

---

## 이슈 요약

| 이슈 # | 심각도 | 관점 | 위치 | 한 줄 설명 |
|--------|--------|------|------|-----------|
| D-1 | MAJOR | V-4 | `.env.example` (미존재) | Quick Start 1단계 실패: `cp .env.example .env` 대상 파일 부재 |
| D-2 | MAJOR | V-3+V-4 | `loadtest/scenarios.py` | Demo 경량 시나리오 부재: 핵심 인사이트(TTFT 악화)를 5분 이내에 시연 불가 |
| D-3 | MAJOR | V-1 | `loadtest/scenarios.py:175-197` | S5 실행 불가: qwen2.5:14b 미설치 시 에러, 사전 검증 없음 |
| D-4 | MINOR | V-4 | `README.md:126-134` | 환경별 예상 소요시간 미안내: Docker CPU vs Native Metal 차이 불명 |
| D-5 | MINOR | V-4 | `README.md:126-134` | 권장 Demo 순서 미제공: 시나리오 선택·실행 순서 가이드 없음 |
| D-6 | MAJOR | V-4 | `grafana/dashboards/llm-overview.json` | Error Rate 패널 "No data": 에러 0건 시 시계열 부재로 패널 공백. Constitution Steady State 위반 |

**집계**: CRITICAL 0건 / MAJOR 4건 / MINOR 2건

---

## 분석 기준

### Project Brief 핵심 증명 대상

| # | 증명 대상 | 현재 시연 수단 | 시연 가능 여부 |
|---|----------|--------------|---------------|
| 1 | LLM 메트릭 이해 | S1 → `/metrics` 확인 | 가능 |
| 2 | 계측 설계 | `/metrics` Prometheus exposition | 가능 |
| 3 | 대시보드 설계 | Grafana `localhost:3000` | 가능 |
| 4 | 부하 테스트 + 시각화 | S2/S3 → Grafana 변화 관찰 | **제한적** (시간 과다) |

증명 대상 #4가 Demo 핵심이나, 이를 시연할 시나리오(S2, S3)의 실행 시간이 면접/발표 시연에 부적합.

### 시나리오별 실행 시간 (Docker CPU, qwen2.5:7b Q4_K_M)

| 시나리오 | 동시성 | 요청 수 | 실측/추정 Wall Time | 핵심 인사이트 | Demo 적합 |
|----------|--------|---------|-------------------|-------------|----------|
| S1 Baseline | 1 | 5 | **152.8s (~2.5분)** 실측 | baseline 레이턴시 | 적합 |
| S2 Sweep | 1→16 | 25 | **추정 40분+** | queuing 발생 지점 | 부적합 |
| S3 Sustained | 4 | 20 | **1661.3s (~28분)** 실측 | TTFT 악화, 처리량 저하 | 부적합 |
| S4 Variable | 4 | 15 | **추정 20분+** | 프롬프트 길이 영향 | 부적합 |
| S5 Model Cmp | 4 | 10 | **실행 불가** | 모델 간 성능 비교 | 불가 |

---

## 이슈 상세

### 이슈 D-1

- **심각도**: MAJOR
- **관점**: V-4 Spec 정합성
- **위치**: `.env.example` (미존재)
- **Spec 근거**: AC-001 #3 — ".env.example 파일에 5개 환경변수 정의", Constitution #7 — ".env.example만 버전 관리"
- **내용**: README Quick Start 1단계에서 `cp .env.example .env`를 안내하지만, `.env.example` 파일이 저장소에 존재하지 않음. Demo 시작 첫 단계에서 실패. `docker-compose.yml`에 기본값이 `${VAR:-default}` 형태로 설정되어 있어 `.env` 없이도 동작하지만, 사용자가 환경변수를 커스터마이즈할 참조가 없음.
- **제안**: `config.py` 기본값과 `docker-compose.yml` 기본값을 기반으로 `.env.example` 생성.

```
# .env.example
OLLAMA_BASE_URL=http://ollama:11434
PROXY_PORT=8000
MAX_CONCURRENT_REQUESTS=4
DEFAULT_MODEL=qwen2.5:7b
LOG_LEVEL=info
```

### 이슈 D-2

- **심각도**: MAJOR
- **관점**: V-3 성능 + V-4 Spec 정합성
- **위치**: `loadtest/scenarios.py` (S1~S5 전체)
- **Spec 근거**: project-brief.md 핵심 증명 #4 — "동시 요청 증가에 따른 성능 변화 측정 및 시각화"
- **내용**: 프로젝트의 핵심 인사이트인 "TTFT ~264x 악화 = queuing의 canary metric"를 시연하려면 동시 요청(concurrency ≥ 2)이 필수. 그러나 현재 이를 보여줄 수 있는 시나리오(S2, S3)는 모두 Docker CPU 기준 20분 이상 소요. S1은 concurrency 1이므로 queuing 효과 없음.
- **Gap 분석**:

| 조건 | 요구 | 현재 |
|------|------|------|
| queuing 효과 시연 | 동시 요청 ≥ 2 | S1(1) 불가, S2/S3(2+) 시간 과다 |
| Demo 시간 예산 | 5~10분 이내 | S2 40분+, S3 28분 |
| Grafana 변화 관찰 | 부하 전/후 비교 | S1만으로는 변화 미미 |

- **제안**: Demo 전용 경량 시나리오 추가.

```python
"s-demo": {
    "name": "S-Demo Quick",
    "description": (
        "Concurrency 2, 6 requests, short prompts. "
        "Demo-friendly (~5min) scenario that demonstrates queuing effects."
    ),
    "concurrency": 2,
    "num_requests": 6,
    "prompts": _SHORT_PROMPTS,
    "model": None,
}
```

설계 근거:
- concurrency 2: 최소 queuing 발생 지점. Ollama 순차 처리 특성상 2번째 요청부터 대기.
- 6 requests: 통계적 분포(P50/P95) 산출 가능한 최소 수량.
- short prompts: 개별 요청 ~30s로 짧아 총 실행 시간 ~5분 이내.
- 기대 효과: S1 대비 TTFT 2~4x 악화 관측 → "queuing = TTFT 악화" 인사이트 축소 시연.

### 이슈 D-3

- **심각도**: MAJOR
- **관점**: V-1 정확성
- **위치**: `loadtest/scenarios.py:175-197`, `loadtest/run.py:346-364`
- **내용**: S5 시나리오는 `models: ["qwen2.5:7b", "qwen2.5:14b"]`를 하드코딩. T-006이 Partial이므로 qwen2.5:14b가 설치되지 않은 상태에서 S5를 실행하면 Ollama가 404/500 에러를 반환. `run.py`에서 에러를 `RequestResult.error`로 캡처하지만, 사용자가 이를 사전에 알 수 없음.
- **제안**: 두 가지 중 선택.
  - (A) `run.py`에 모델 사전 확인 로직 추가 (`GET /api/tags`로 설치된 모델 조회 → 미설치 모델 경고 후 스킵)
  - (B) README의 S5 설명에 전제 조건 명시 ("qwen2.5:14b 사전 설치 필요")

### 이슈 D-4

- **심각도**: MINOR
- **관점**: V-4 Spec 정합성
- **위치**: `README.md:126-134` (Load Test Scenarios 섹션)
- **내용**: Docker CPU 모드와 Native Metal 모드의 성능 차이가 3~5x 이상 예상되나, 사용자가 자신의 환경에서 시나리오별 예상 소요시간을 판단할 수 없음. 벤치마크 결과(S1: 2.5분, S3: 28분)가 Docker CPU 기준임을 README에서 명확히 전달하지 않음.
- **제안**: README 시나리오 표에 예상 소요시간 열 추가, Docker CPU 기준 명시.

### 이슈 D-5

- **심각도**: MINOR
- **관점**: V-4 Spec 정합성
- **위치**: `README.md:126-134`
- **내용**: 5개 시나리오가 나열되어 있으나, 어떤 시나리오를 어떤 순서로 실행해야 효과적인 Demo인지 가이드가 없음. 사용자가 S3부터 실행하면 28분 대기 후에야 결과를 볼 수 있음.
- **제안**: "Recommended Demo Flow" 섹션 추가.

```markdown
## Recommended Demo Flow (~10분)

1. `python run.py --scenario s1` — baseline 확인 (~2.5분)
2. Grafana(`localhost:3000`) → 대시보드 부하 전 상태 관찰
3. `python run.py --scenario s-demo` — queuing 효과 관찰 (~5분)
4. Grafana → TTFT 악화, Queue Depth 증가 확인
```

### 이슈 D-6

- **심각도**: MAJOR
- **관점**: V-4 Spec 정합성
- **위치**: `grafana/dashboards/llm-overview.json` (Error Rate % 패널)
- **Spec 근거**: Constitution Steady State — "No Data 패널 없음 (부하 발생 후)"
- **내용**: Error Rate 패널의 PromQL이 `sum(rate(llm_request_errors_total{...}[5m])) / sum(rate(llm_requests_total{...}[5m])) * 100` 구조. `llm_request_errors_total` 카운터가 한 번도 증가하지 않으면 Prometheus에 시계열 자체가 존재하지 않아 "No data" 표시. 에러를 의도적으로 생성해야만 패널이 동작하는 것은 대시보드 설계 결함.
- **제안**: PromQL 끝에 `or vector(0)` 추가로 에러 0건 시 "0%" 표시.

```promql
# 현재: 에러 0건이면 No data
sum(rate(llm_request_errors_total{model=~"$model"}[5m])) / sum(rate(llm_requests_total{model=~"$model"}[5m])) * 100

# 수정: 에러 0건이면 0% 표시
sum(rate(llm_request_errors_total{model=~"$model"}[5m])) / sum(rate(llm_requests_total{model=~"$model"}[5m])) * 100
or vector(0)
```

---

## Spec↔Code 동기화 확인

| 항목 | 결과 |
|------|------|
| AC-001 #3: `.env.example` 5개 변수 정의 | **미충족** — 파일 부재 |
| AC-005 #2: S1~S5 실행 가능 | **부분 충족** — S5 14b 미설치 시 실패 |
| AC-006 #1: 최소 2개 모델 벤치마크 | **미충족** — T-006 Partial |
| Constitution #6: 재현 가능 벤치마크 | **충족** — 시나리오 스크립트 기반, 동일 조건 재현 가능 |
| project-brief 핵심 증명 #4 | **제한적** — 부하 테스트 시연 시간 과다 |
| Constitution Steady State: No Data 패널 없음 | **미충족** — Error Rate 패널 "No data" (에러 0건 시) |

---

## 적절한 부분 (유지)

1. **S1~S5 시나리오 설계**: baseline → sweep → sustained → variable → comparison 체계적 구성
2. **프롬프트 풀**: 영/한 혼합, 길이 3단계(short ~50tok, medium ~200tok, long ~500tok)
3. **CLI 인터페이스**: `--scenario`, `--model`, `--no-stream` 깔끔한 구성
4. **통계 출력**: Avg/P50/P95/P99 포맷, 에러 건수 포함
5. **Semaphore 기반 동시성 제어**: Load Generator와 Proxy 양쪽 일관된 패턴

---

## Dev 세션 수정 지시

### 필수 (MAJOR)

| # | 이슈 | 작업 | 파일 |
|---|------|------|------|
| 1 | D-1 | `.env.example` 생성 (5개 환경변수 + 주석) | `.env.example` (신규) |
| 2 | D-2 | `s-demo` 시나리오 추가 (concurrency 2, 6 req, short prompts) | `loadtest/scenarios.py` |
| 3 | D-2 | `run.py` dispatch에 `s-demo` → `_run_simple` 라우팅 | `loadtest/run.py` |
| 4 | D-2 | README에 "Recommended Demo Flow" 섹션 추가 | `README.md` |
| 5 | D-3 | README S5 설명에 "qwen2.5:14b 사전 설치 필요" 전제 조건 추가 또는 `run.py`에 모델 사전 확인 로직 추가 | `README.md` 또는 `loadtest/run.py` |
| 6 | D-6 | Error Rate 패널 PromQL에 `or vector(0)` 추가 → 에러 0건 시 "0%" 표시 | `grafana/dashboards/llm-overview.json` |

### 선택 (MINOR)

| # | 이슈 | 작업 | 파일 |
|---|------|------|------|
| 7 | D-4 | README 시나리오 표에 예상 소요시간 열 추가 | `README.md` |
| 8 | D-5 | D-2 #4에서 함께 해소 | - |
