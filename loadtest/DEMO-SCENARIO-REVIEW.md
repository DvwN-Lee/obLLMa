# DEMO-SCENARIO.md 검증 리포트

> **분석일**: 2026-03-15
> **세션**: Analyst (Phase 4 VERIFY)
> **대상**: `loadtest/DEMO-SCENARIO.md` (248줄, Docker CPU 대응 수정본)
> **교차 참조**: `docs/design.md` §1-3/§1-4, `proxy/main.py`, `loadtest/run.py`, `loadtest/scenarios.py`
> **합의 방식**: VETO 프로토콜 — V-1~V-4 독립 검증 후 Lead 통합

---

## 결론

VETO 4개 Agent 독립 검증 결과, CRITICAL 1건·MAJOR 5건·MINOR 3건 확정.
Phase Gate **차단** — CRITICAL 1건 해소 필수.

| 심각도 | 건수 |
|--------|:----:|
| **CRITICAL** | 1 |
| **MAJOR** | 5 |
| **MINOR** | 3 |

---

## VETO 투표 결과

| Agent | 관점 | 투표 | CRITICAL-1 동의 | 추가 발견 |
|-------|------|:----:|:---------------:|----------|
| V-1 정확성 | 코드 실행 흐름 | Approve | O | generator 예외 처리 누락 (MAJOR) |
| V-2 보안 | DoS/안정성 | VETO | O | 입력 검증 부재 (MAJOR), httpx 풀 미설정 (MAJOR) |
| V-3 성능 | Step 3 검증 가능성 | VETO | O | run.py stream 하드코딩 (MAJOR), QUEUE_DEPTH 무효 (MAJOR) |
| V-4 Spec 정합성 | design.md ↔ code | VETO | O | MonitoredSemaphore AC 미충족 (MAJOR) |

- **CRITICAL-1 심각도**: 전원 동의 (4/4)
- **VETO 3건**: 추가 이슈를 CRITICAL-1과 함께 해소해야 한다는 의견. Lead 검토 후 통합 확정.

---

## C-1: Streaming 모드에서 Semaphore/Active Requests 즉시 해제 [CRITICAL]

**출처**: V-1, V-2, V-3, V-4 전원 확인

### Spec (design.md §1-3, lines 57-75)

```
[1] semaphore.acquire()
[2] llm_active_requests.inc()
[3] start = time.monotonic()
[4] stream POST to Ollama
[5] first content chunk → TTFT 기록
[6] SSE chunks passthrough to client
[7] usage chunk → token counts 기록
[8] [DONE] → duration, TPS 기록
[9] llm_active_requests.dec()    <-- [DONE] 이후
[10] semaphore.release()          <-- [DONE] 이후
```

### 실제 코드 (proxy/main.py:91-138)

```python
async def chat_completions(request: Request):
    ACTIVE_REQUESTS.inc()           # line 116
    try:
        if stream:
            return await _handle_streaming(body, model, start)  # line 121
            # StreamingResponse 객체 반환 -- 스트리밍 시작 전
    finally:
        ACTIVE_REQUESTS.dec()       # line 137 -- 즉시 실행
        _semaphore.release()        # line 138 -- 즉시 실행
```

`_handle_streaming()` (line 146)은 `StreamingResponse(event_generator(), ...)`를 반환한다.
`event_generator()`는 async generator로, FastAPI ASGI 레이어가 응답을 소비할 때 비로소 실행된다.

### 실행 순서

1. `chat_completions()` -> `_handle_streaming()` 호출 -> StreamingResponse 객체 **즉시 반환**
2. `finally` 블록 실행 -> **semaphore 해제 + active_requests 감소** (수 마이크로초)
3. ASGI 레이어가 generator 소비 시작 -> Ollama 스트리밍 시작 (수십 초~수분)

### S2 concurrency=8 시뮬레이션 (V-3 분석)

```
T=0ms   : 8개 요청 asyncio.gather() 동시 출발
           -> 4개: semaphore 획득, ACTIVE_REQUESTS=4, QUEUE_DEPTH=4
T=~1ms  : 4개 요청 각각 _handle_streaming() return -> StreamingResponse 반환
           -> finally 즉시: ACTIVE_REQUESTS=0, semaphore 4개 release
T=~2ms  : 남은 4개 요청 semaphore 획득 -> ACTIVE_REQUESTS=4, QUEUE_DEPTH=0
T=~3ms  : 이 4개도 StreamingResponse 반환 -> ACTIVE_REQUESTS=0
T=1~30s : event_generator() 내부에서 Ollama 스트리밍 실제 진행
           이 기간 동안 ACTIVE_REQUESTS=0, QUEUE_DEPTH=0
```

### 영향

| 메트릭 | 기대 (design.md) | 실제 |
|--------|:-----------------:|:----:|
| `llm_active_requests` | 스트리밍 완료까지 유지 | 즉시 0으로 복귀 |
| `llm_queue_depth` | 동시 8+에서 대기열 형성 | 즉시 해소 |
| Semaphore 제한 | 동시 4개 초과 차단 | 실질적으로 무제한 (httpx max_connections=100이 유일한 상한) |

### Step 3 검증 불가 항목

- DEMO Line 136: "Active Requests -> 단계별 1->2->4->4(상한) 변화" -- 관측 불가
- DEMO Line 137: "Queue Depth -> 동시 8에서 ~4, 동시 16에서 ~12 대기" -- 관측 불가
- 체크리스트 #3, #4 (DEMO lines 211-212) 기대값이 현실과 불일치

### 수정 방향

semaphore release와 active_requests dec을 `event_generator()` 내부 `try/finally`로 이동.
`chat_completions()`의 `finally` 블록에서는 streaming 경로일 때 semaphore/active_requests를 건드리지 않도록 분기.

```python
async def _handle_streaming(body, model, start, semaphore):
    client = await get_client()

    async def event_generator():
        try:
            # ... 기존 streaming logic ...
        finally:
            ACTIVE_REQUESTS.dec()
            semaphore.release()

    return StreamingResponse(event_generator(), ...)
```

---

## M-1: event_generator() 예외 처리 누락 [MAJOR]

**출처**: V-1

**위치**: `proxy/main.py:149-206`

**현상**: `event_generator()` 내부에 `try/except`가 없다. 스트리밍 중 네트워크 오류 또는 Ollama 오류 발생 시 `REQUEST_ERRORS`, `REQUESTS_TOTAL(status="error")` 카운터가 갱신되지 않는다. `chat_completions()`의 except 블록(line 124-135)은 이미 종료된 후이므로 generator 내부 예외를 포착할 수 없다.

**영향**: streaming 에러 요청은 `llm_requests_total`과 `llm_request_errors_total` 어디에도 카운트되지 않는 "유령 요청"이 된다.

**수정 방향**: `event_generator()` 내부 `async with client.stream(...)` 블록을 `try/except`로 감싸고, 예외 발생 시 `REQUEST_ERRORS` 카운터 갱신.

---

## M-2: httpx 커넥션 풀 미설정 [MAJOR]

**출처**: V-2

**위치**: `proxy/main.py:50-53`

**현상**: `httpx.AsyncClient` 생성 시 `limits` 파라미터 미지정. 기본값 `DEFAULT_LIMITS(max_connections=100, max_keepalive_connections=20)` 적용. C-1으로 세마포어가 무효화된 상태에서 이 묵시적 100개 상한이 유일한 동시성 방어선이며, 단일 Ollama 인스턴스에 대해 과도하다.

**보안 영향**: 의도적 대량 streaming 요청으로 Ollama에 100개 동시 연결 가능. GPU VRAM 고갈 및 서비스 마비 초래 가능 (DoS).

**수정 방향**: `httpx.AsyncClient(limits=httpx.Limits(max_connections=MAX_CONCURRENT_REQUESTS * 2, max_keepalive_connections=MAX_CONCURRENT_REQUESTS))` 명시 설정.

---

## M-3: model 필드 입력 검증 부재 [MAJOR]

**출처**: V-2

**위치**: `proxy/main.py:92-94`

**현상**: `body.get("model", DEFAULT_MODEL)`은 임의 문자열을 Ollama에 전달한다. `stream` 필드도 타입 검증 없이 사용된다. 외부 노출 시 프록시를 통한 예상치 않은 Ollama API 조작 가능성 존재.

**수정 방향**: `model` 값에 허용 패턴(`[a-zA-Z0-9.:_-]+`) 검증 적용. `stream` 필드를 `bool` 타입으로 강제 변환.

---

## M-4: run.py stream 하드코딩 [MAJOR]

**출처**: V-3

**위치**: `loadtest/run.py:76`

**현상**: `_send_request()`가 `"stream": True`로 하드코딩. Non-streaming 모드에서는 `chat_completions()`의 `finally` 타이밍이 정확하여 Step 3 기대값 관측이 가능하지만, 현재 CLI에 non-streaming 옵션이 없어 이 대안을 실행할 수 없다.

**수정 방향**: `--no-stream` CLI 플래그 추가 또는 `scenarios.py`에 `stream` 키 지원.

---

## M-5: AC-002 항목 8 미충족 — MonitoredSemaphore [MAJOR]

**출처**: V-4

**위치**: `proxy/main.py:39-41` vs `docs/tasks.md:73`

**현상**: tasks.md AC-002 항목 8은 `MonitoredSemaphore(MAX_CONCURRENT_REQUESTS)` 래퍼 클래스를 통한 동시성 제한 + 대기자 수 추적을 명시. 실제 구현은 `asyncio.Semaphore` 직접 사용 + 전역 변수(`_queue_waiters`, `_queue_lock`) 수동 관리. 기능은 동작하나 AC 인터페이스와 불일치.

**수정 방향**: `MonitoredSemaphore` 래퍼 클래스를 별도 구현하여 세마포어 acquire/release와 `llm_queue_depth` 추적 로직을 캡슐화. C-1 수정과 병행 시 generator 내 release도 래퍼 내부에서 처리 가능.

---

## m-1: "전체 실행" 섹션과 Step 1의 불일치 [MINOR]

**위치**: `DEMO-SCENARIO.md:186-194`

**현상**: Step 1 (lines 72-87)은 non-streaming 에러만 실행하고 streaming 에러 미기록을 명시적으로 설명. 전체 실행 섹션(lines 186-194)은 여전히 streaming curl을 포함하며 주석도 "(non-streaming + streaming)"으로 기술.

**수정 방향**: 전체 실행 섹션에서 streaming curl 제거, 주석을 `(non-streaming only)`로 변경.

---

## m-2: Known Issue #1 유령 요청 영향 미기술 [MINOR]

**위치**: `DEMO-SCENARIO.md:225-239`

**현상**: Known Issue #1에서 에러 메트릭 미기록은 정확히 기술되어 있으나, streaming 에러 요청이 `llm_requests_total`과 `llm_request_errors_total` 어디에도 카운트되지 않는 "유령 요청"이 된다는 전체 영향 설명이 누락.

**수정 방향**: "streaming 에러 요청은 success/error 어느 카운터에도 기록되지 않는다" 보충.

---

## m-3: [DONE] 수신과 duration 기록 코드 분리 [MINOR]

**출처**: V-4

**위치**: `proxy/main.py:166-167, 194-202`

**현상**: design.md §1-3 [8] `[DONE] -> duration, TPS 기록`에 대응하는 코드가 `[DONE]` 수신 블록(line 166-167: `continue`)과 실제 기록 코드(line 194-202: `async with` 종료 후)로 분리되어 있어 추적성이 낮다. Spec 의도(스트림 완료 후 기록)는 충족.

**수정 방향**: 주석으로 연결 명시하거나, `[DONE]` 수신 시점에 duration/TPS 기록을 배치.

---

## 기존 이슈 해소 상태 (이전 리뷰 라운드)

| # | 이슈 | 심각도 | 해소 |
|---|------|--------|:----:|
| 1 | 포트 불일치 (8002/3001) | MAJOR | O |
| 2 | S4/S5 미포함 | MAJOR | O |
| 3 | 스트림 모드 혼합 | MINOR | O |
| 4 | Active Requests 기대값 | MINOR | O |
| 5 | S3 설명 부정확 | MINOR | O |
| 6 | S5 CLI 인수 | MINOR | O |

---

## 신규 추가 항목 품질 평가 (Docker CPU 대응 수정)

| 항목 | 판정 | 근거 |
|------|:----:|------|
| 환경별 성능 표 (lines 14-21) | PASS | CPU/Metal GPU TPS 범위, 소요 시간 합리적 |
| Native 전환 가이드 (lines 24-34) | PASS | `.env` + `docker compose restart proxy` 정확 |
| S1 참고 결과 (lines 102-112) | PASS | Docker CPU TPS ~4.4 사용자 보고와 일치 |
| Known Issue #1 (lines 225-239) | PASS | 코드 분석과 일치, 원인 설명 정확 |
| Known Issue #2 (lines 241-248) | PASS | 아키텍처 제약(Docker = no Metal) 정확 |
| 포트 확인 명령 (lines 63-66) | PASS | `docker compose ps --format` 유효 |

---

## Dev 세션 전달 수정 지시 (우선순위순)

| 순위 | ID | 심각도 | 파일 | 조치 |
|:----:|:--:|--------|------|------|
| 1 | C-1 | CRITICAL | `proxy/main.py` | semaphore release + active_requests dec을 `event_generator()` 내부 `try/finally`로 이동. `chat_completions()` finally에서 streaming 경로 분기 |
| 2 | M-1 | MAJOR | `proxy/main.py` | `event_generator()` 내 `async with client.stream()` 을 `try/except`로 감싸고 에러 시 `REQUEST_ERRORS` 카운트 |
| 3 | M-5 | MAJOR | `proxy/main.py` | `MonitoredSemaphore` 래퍼 클래스 구현, `_queue_waiters` 전역 변수 제거 |
| 4 | M-2 | MAJOR | `proxy/main.py` | `httpx.AsyncClient(limits=...)` 명시 설정 |
| 5 | M-3 | MAJOR | `proxy/main.py` | `model` 필드 패턴 검증 추가 |
| 6 | M-4 | MAJOR | `loadtest/run.py` | `--no-stream` CLI 플래그 추가 |
| 7 | m-1 | MINOR | `DEMO-SCENARIO.md` | 전체 실행 섹션 streaming curl 제거 |
| 8 | m-2 | MINOR | `DEMO-SCENARIO.md` | Known Issue #1에 유령 요청 영향 보충 |
| 9 | m-3 | MINOR | `proxy/main.py` | [DONE] 기록 코드 추적성 개선 (주석) |

---

## VETO Round 2: Screenshot 캡처 단계 추가

> **일시**: 2026-03-15
> **안건**: DEMO-SCENARIO.md에 스크린샷 캡처 단계 누락 — dod.md 요구사항(스크린샷 2장 이상, README 참조) 및 AC-007 미충족
> **합의 방식**: VETO 프로토콜 — 3 Agent (설계-비평가, 구현-전략가, 도메인-전문가) 독립 검토

### 투표 결과

| Agent | 역할 | 투표 | 핵심 의견 |
|-------|------|:----:|-----------|
| design-critic | 설계-비평가 | Approve (조건부) | Step 6 독립 섹션 대신 각 Step 인라인 배치 권장. `grafana-dashboard.png` = Peak Load(README 호환), Baseline은 별도 파일명 |
| impl-strategist | 구현-전략가 | Approve | `mkdir -p docs/screenshots` 사전 준비 추가 필수. Docker CPU 환경에서 S2 미실행 시 Step 2 캡처를 README 대표로 대체 가능 |
| domain-expert | 도메인-전문가 | Approve (조건부) | S2 concurrency=8 시점이 포트폴리오 최적. Docker CPU는 시간 범위 Last 45min~1hr 필요 |

**합의**: 전원 Approve (조건 충족) → Round 1 통과

### Lead 통합 판정

| 항목 | 합의 내용 | 근거 |
|------|-----------|------|
| Shot 1 (Baseline) | Step 2 완료 후, `grafana-dashboard-baseline.png` | 기본 메트릭 패널 데이터 표시 확인용 |
| Shot 2 (Peak Load) | Step 3 concurrency=8 시점, **`grafana-dashboard.png`** | README.md 참조 파일명 호환. 10개 패널 전체 데이터 = 대표 이미지 |
| Shot 3 (Optional) | Step 5 완료 후, `grafana-dashboard-model-comparison.png` | $model 드롭다운 + 멀티모델 TPS 비교 |
| 사전 준비 | `mkdir -p docs/screenshots` 추가 | impl-strategist 제안. 디렉토리 부재 시 저장 실패 방지 |
| 시간 범위 | Native: Last 15min / Docker CPU: Last 45min~1hr | domain-expert 제안. 환경별 소요 시간 차이 반영 |
| 체크리스트 | #12 Baseline 존재, #13 Peak Load 존재 (README 참조) | dod.md line 69/74 충족 검증 |

### Spec 정합성 확인

| Spec 항목 | 요구 | 충족 |
|-----------|------|:----:|
| dod.md line 69 | Grafana 스크린샷 2장 이상 | O (Shot 1 + Shot 2 필수, Shot 3 선택) |
| dod.md line 74 | README.md: 스크린샷 포함 | O (`grafana-dashboard.png` = Shot 2) |
| AC-007 (tasks.md lines 133-141) | 스크린샷 캡처 절차 문서화 | O (각 Step 인라인 배치) |
| README.md line 107 | `docs/screenshots/grafana-dashboard.png` 참조 | O (Shot 2 파일명 일치) |

### 적용 내역

| 변경 | DEMO-SCENARIO.md 위치 | 내용 |
|------|----------------------|------|
| 사전 준비 | Line 43 | `mkdir -p docs/screenshots` 추가 |
| 시간 범위 참고 | Line 71 | Docker CPU / Native 환경별 안내 |
| Shot 1 (Baseline) | Lines 126-134 | Step 2 후 인라인 캡처 안내 |
| Shot 2 (Peak Load) | Lines 152-160 | Step 3 concurrency=8 시점 캡처 안내 |
| Shot 3 (Optional) | Lines 202-208 | Step 5 후 모델 비교 캡처 안내 |
| 체크리스트 #12-13 | Lines 251-252 | 스크린샷 존재 여부 검증 항목 |

### Docker CPU 환경 대체 경로

S2 이후를 실행하지 않는 경우, Shot 1(Baseline)을 `grafana-dashboard.png`로 복사하여 README 참조를 충족한다. DEMO-SCENARIO.md Line 134에 이 대안을 명시.

---

## Phase Gate 판정

**차단** — CRITICAL 1건 (C-1) 해소 필수.

C-1 해소 후 Step 3 (Active Requests / Queue Depth) 재검증 필요.
MAJOR 5건은 C-1과 병행 수정 권장 (특히 M-1, M-5는 C-1 수정 시 함께 반영 가능).
Screenshot 캡처 단계는 VETO Round 2에서 합의 완료, DEMO-SCENARIO.md 반영 완료.
