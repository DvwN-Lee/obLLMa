> **[DEPRECATED]** — 2026-03-16 폐기
>
> **폐기 사유**: T-1~T-9 전체 구현 완료. Plan 작성 시점에 이미 코드 반영이 완료되어 Plan-Code Desync(C-1) 및 Task ID 충돌(C-2)이 구조적으로 발생.
>
> **완료 기록**: [`cpu-optimization-plan-review.md`](cpu-optimization-plan-review.md) — C-1 대조표(§Round 1 상세)에 T-1~T-9 구현 위치·상태 기록.
>
> **VETO 기록 보존**: 본 문서 하단의 VETO 투표 기록(§VETO 투표 결과)은 Constitution #1 해석 선례로서 보존 가치가 있다.
>
> **현위치 유지 근거**: `docs/` 경로의 git history를 보존하기 위해 별도 archive 디렉토리로 이동하지 않는다.

---

# CPU 최적화 Dev 인계 Plan

> **작성일**: 2026-03-16
> **세션**: Researcher (VETO 검증 완료)
> **대상**: Docker Compose 리소스, Grafana 설정, Proxy 코드
> **합의 방식**: VETO 프로토콜 — 3 Agent (설계-비평가, 구현-전략가, 도메인-전문가)

---

## 배경

Ollama Docker 컨테이너가 **CPU 1387%** (14코어 점유)를 유휴 상태에서 소비.
4개 Subagent (V-1~V-4) 교차 검증으로 MAJOR 6건, MINOR 5건 확인.

---

## 사전 조건

Dev 세션 시작 전 반드시 확인:

```bash
# Docker Desktop VM 메모리 확인 (16GB 이상 필요)
docker info | grep "Total Memory"
# 16GB 미만이면 Docker Desktop > Settings > Resources > Memory 조정
```

---

## Task Group A: Docker Compose 리소스 최적화

**대상 파일**: `docker-compose.yml`
**병렬 그룹**: A (단일 파일, 순차 편집)

### T-1: Ollama CPU 제한 추가

**현재**: CPU 제한 없음 → 전체 코어 독점
**변경**:

```yaml
ollama:
  deploy:
    resources:
      limits:
        memory: 10g    # T-2
        cpus: '6'      # 추론 시 600% 상한
```

**근거**: M4 Pro 14코어 중 6코어를 Ollama에 할당, 나머지 8코어를 OS + 관측 서비스에 예약. domain-expert 권장 '4'와 초안 '8' 사이의 절충값.

### T-2: Ollama 메모리 및 환경변수 최적화

**현재**: `memory: 8g`, 환경변수 없음
**변경**:

```yaml
ollama:
  environment:
    - OLLAMA_MAX_LOADED_MODELS=1
    - OLLAMA_KEEP_ALIVE=5m
    - OLLAMA_NUM_THREADS=6
  deploy:
    resources:
      limits:
        memory: 10g
        cpus: '6'
```

| 변수 | 값 | 효과 |
|------|-----|------|
| `OLLAMA_MAX_LOADED_MODELS` | 1 | 멀티모델 동시 로드 방지 → 메모리 폭증 차단 |
| `OLLAMA_KEEP_ALIVE` | 5m | 모델 5분 유휴 후 자동 언로드 → idle 메모리 해제 |
| `OLLAMA_NUM_THREADS` | 6 | 추론 스레드 6개 제한 → CPU 상한과 일치 |

**메모리 배분 (VM 16GB 기준)**:

| 서비스 | 할당 |
|--------|------|
| ollama | 10g |
| prometheus | 512m |
| proxy + grafana | ~2g (미제한, 자율) |
| VM overhead | ~3g |
| **합계** | ~15.5g / 16g |

> **주의**: Docker Desktop VM 메모리가 16GB 미만이면 ollama를 `8g`으로 유지할 것.

### T-3: 헬스체크 주기 완화

**현재**: ollama 10s / proxy 10s
**변경**:

```yaml
ollama:
  healthcheck:
    test: ["CMD", "curl", "--fail", "http://localhost:11434/"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 60s

proxy:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 5s
    retries: 5
    start_period: 15s
```

**변경 사항**:
- ollama: `ollama list` → `curl --fail` (프로세스 fork 오버헤드 제거, VETO 도메인-전문가 권장)
- interval: 10s → 30s (폴링 빈도 1/3로 감소)
- start_period 추가: ollama 60s (모델 로딩 대기), proxy 15s

> **주의**: ollama Dockerfile에 curl이 포함되어 있는지 확인 필요. 미포함 시 `ollama list` 유지.

### T-4: Prometheus 메모리 제한 추가

**현재**: 메모리 제한 없음
**변경**:

```yaml
prometheus:
  deploy:
    resources:
      limits:
        memory: 512m
```

---

## Task Group B: Grafana 설정 최적화

**대상 파일**: `grafana/provisioning/dashboards/dashboards.yml`, `grafana/dashboards/llm-overview.json`
**병렬 그룹**: B (Group A와 병렬 가능)

### T-5: Dashboard Provisioner 폴링 주기 완화

**대상**: `grafana/provisioning/dashboards/dashboards.yml`
**현재**: `updateIntervalSeconds: 10`
**변경**: `updateIntervalSeconds: 60`

**근거**: 10초마다 VirtioFS bind mount 디렉토리를 스캔하는 비용 제거. 대시보드 JSON 변경은 개발 중에만 발생하므로 60초면 충분.

### T-6: Template Variable Refresh 모드 변경

**대상**: `grafana/dashboards/llm-overview.json`
**현재**: `"refresh": 2` (On Time Range Change → 매 dashboard refresh마다 실행)
**변경**: `"refresh": 1` (On Dashboard Load → 페이지 로드 시 1회만 실행)

**근거**: 모델 목록은 자주 변하지 않으므로 매 30초 쿼리가 불필요. 페이지 새로고침 시 갱신으로 충분.

### ~~T-7: Dashboard Auto-Refresh 변경~~ (VETO로 제거)

**VETO 판정**: domain-expert — 데모 시나리오에서 S2 concurrency sweep의 실시간 관측이 핵심 가치. 30s 유지.

> **`"refresh": "30s"` 유지**. 변경하지 않는다.

---

## Task Group C: Proxy 코드 개선

**대상 파일**: `proxy/main.py`
**병렬 그룹**: C (Group A/B와 병렬 가능, 내부는 순차)

### T-7: _poll_model_status() 모델 셋 추적 + set(0) 리셋

**현재** (`main.py:309-328`): MODEL_LOADED gauge에 set(1)만 수행, 언로드 모델 set(0) 누락
**변경**:

```python
_known_models: set[tuple[str, str]] = set()

async def _poll_model_status():
    """Periodically check Ollama for loaded models and update M11 gauge."""
    global _known_models
    while True:
        try:
            client = await get_client()
            resp = await client.get("/api/ps", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                current: set[tuple[str, str]] = set()
                for m in models:
                    name = m.get("name", "unknown")
                    details = m.get("details", {})
                    quant = details.get("quantization_level", "unknown")
                    MODEL_LOADED.labels(model=name, quantization=quant).set(1)
                    current.add((name, quant))
                # 이전에 있었지만 현재 없는 모델 → unloaded
                for name, quant in _known_models - current:
                    MODEL_LOADED.labels(model=name, quantization=quant).set(0)
                _known_models = current
        except Exception:
            pass
        await asyncio.sleep(30)
```

**근거**: impl-strategist 권장 — `remove()` 대신 `set(0)` 사용. remove() 시 Grafana 패널에서 "No Data"가 되지만, set(0)은 unloaded 상태를 명시적 표현.

### T-8: /metrics 엔드포인트 단순화

**현재** (`main.py:119-124`):

```python
return StreamingResponse(
    iter([generate_latest()]),
    media_type=CONTENT_TYPE_LATEST,
)
```

**변경**:

```python
from fastapi.responses import Response

return Response(
    content=generate_latest(),
    media_type=CONTENT_TYPE_LATEST,
)
```

**근거**: 단일 바이트열을 iter()로 래핑하는 StreamingResponse는 불필요한 객체 생성. Response로 직접 반환.

### T-9: Background Task 참조 보존

**현재** (`main.py:331-333`):

```python
@app.on_event("startup")
async def startup():
    asyncio.create_task(_poll_model_status())
```

**변경**:

```python
_background_tasks: set[asyncio.Task] = set()

@app.on_event("startup")
async def startup():
    task = asyncio.create_task(_poll_model_status())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
```

**근거**: Python 3.10+ 공식 문서에서 create_task 반환값 미보관 시 GC 수거 경고. done_callback 패턴으로 참조 유지.

---

## ~~T-5 (VETO 제거): Docker Compose Profiles~~

**VETO**: 전원 (3/3) — Constitution #1 위반

| Agent | 근거 |
|-------|------|
| design-critic | `depends_on: ollama: condition: service_healthy` + profiles 조합 시 Compose dependency resolution 실패 |
| impl-strategist | AC-001 ("docker compose up -d 시 모든 서비스 기동") 무효화 |
| domain-expert | Constitution #1 직접 위반, 옵션 C (OLLAMA_BASE_URL 환경변수 분기) 권장 |

**대안**: 현재 `OLLAMA_BASE_URL` 환경변수 전환 방식을 유지. `.env.example`에 Native Metal 전환 가이드를 주석으로 명시.

---

## 실행 순서 및 병렬화

```
[Group A] docker-compose.yml ─── T-1, T-2, T-3, T-4 (순차)
                                        ↕ 병렬
[Group B] grafana/ ──────────── T-5, T-6 (순차)
                                        ↕ 병렬
[Group C] proxy/main.py ─────── T-9, T-8, T-7 (순차, 위험도 낮은 순)
```

3개 Worktree Subagent로 병렬 실행 가능. Group A/B/C는 서로 다른 파일이므로 충돌 없음.

---

## 검증 방법

### Group A 검증

```bash
# YAML 문법 검증
docker compose config

# 서비스 기동 확인
docker compose up -d

# 리소스 제한 적용 확인
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# 헬스체크 동작 확인
docker compose ps
```

### Group B 검증

```bash
# Grafana 재시작 후 브라우저에서 대시보드 열기
# 우하단 refresh 표시가 30s인지 확인
# template variable 클릭 시 모델 목록 로드되는지 확인
```

### Group C 검증

```bash
# proxy 재시작 후 메트릭 확인
curl -s http://localhost:8000/metrics | grep llm_model_loaded
# 모델 로드 전: 값 없거나 0
# 모델 로드 후: 값 1
# 모델 언로드 후: 값 0 (30초 폴링 대기)

# /metrics 응답 확인
curl -s http://localhost:8000/metrics | head -5
# Content-Type: text/plain 확인
```

### 통합 검증

```bash
# 전체 스택 기동 후 idle CPU 측정
docker stats --no-stream
# 기대값: ollama <10% (idle), 전체 <15%

# 부하 테스트 중 CPU 확인
python loadtest/run.py --scenario s1 --base-url http://localhost:8000
docker stats --no-stream
# 기대값: ollama <600% (cpus: '6' 제한)
```

---

## 예상 효과

| 지표 | 현재 | 개선 후 |
|------|:----:|:-------:|
| Ollama idle CPU | 1387% | < 10% (KEEP_ALIVE 후 언로드) |
| Ollama 부하 CPU | 1387% | < 600% (cpus: '6') |
| 전체 idle CPU (브라우저 열림) | 5~10% | 3~5% |
| 헬스체크 빈도 | 12회/분 | 4회/분 |
| Grafana provisioner 폴링 | 6회/분 | 1회/분 |
| OOM 재시작 위험 | 높음 (8g) | 낮음 (10g + MAX_LOADED=1) |

---

## VETO 투표 기록

| Agent | 역할 | 최종 판정 |
|-------|------|:---------:|
| design-critic | 설계-비평가 | Approve (T-5 VETO) |
| impl-strategist | 구현-전략가 | Approve (T-5 VETO, T-9 조건부) |
| domain-expert | 도메인-전문가 | Approve (T-5 VETO, T-7 VETO, T-1/T-2 값 조정) |

**합의**: T-5 제거, T-7 제거 (30s 유지), T-1/T-2 값 조정 반영 후 전원 Approve.
