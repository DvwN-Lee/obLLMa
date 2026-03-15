# findings: Architecture Verification

**조사일**: 2026-03-14
**조사 범위**: design.md 핵심 기술 가정 5건 (A1~A5) 검증
**팀**: Researcher Session (3x researcher-worker 병렬)

---

## 결론 (Conclusions)

**아키텍처 확정 가능. 단, design.md에 2건의 보완이 필요.**

5건의 기술 가정 중 1건 CONFIRMED, 4건 PARTIAL. DENIED 없음.
PARTIAL 4건은 모두 구현 시 우회 가능한 수준이며, 아키텍처 변경을 요구하지 않는다.

| ID | 가정 | 판정 | 설계 영향 |
|----|------|:----:|----------|
| A1 | Ollama `stream_options.include_usage` | CONFIRMED | 없음. Ollama v0.5.x+ 지원 확인 |
| A2 | httpx SSE 스트리밍 파싱 | PARTIAL | timeout 설정 추가 필요 (`read=None`) |
| A3 | asyncio.Semaphore 대기자 추적 | PARTIAL | MonitoredSemaphore 래퍼 클래스 필요 (VETO에서 이미 식별) |
| A4 | host.docker.internal macOS | PARTIAL | `extra_hosts` 방어 설정 추가 권고 |
| A5 | prometheus_client + FastAPI mount | PARTIAL | **`app.mount()` → `@app.get("/metrics")` 패턴 변경 필요** |

---

## 근거 (Evidence)

### A1: stream_options.include_usage — CONFIRMED

| 항목 | 출처 | 내용 |
|------|------|------|
| E-A1-1 | [Ollama PR #6784](https://github.com/ollama/ollama/pull/6784) | 2024-12-13 머지. `stream_options.include_usage` 구현 |
| E-A1-2 | [Issue #5200](https://github.com/ollama/ollama/issues/5200), [#4448](https://github.com/ollama/ollama/issues/4448) | 모두 Closed |

- Ollama v0.5.x 이후 지원. 스트리밍 최종 청크에 `usage` 필드 반환.
- OpenAI 호환 API는 여전히 "experimental" 표기 — 향후 breaking change 가능성은 낮지만 인지 필요.

### A2: httpx SSE 스트리밍 — PARTIAL

| 항목 | 출처 | 내용 |
|------|------|------|
| E-A2-1 | [httpx Async Docs](https://www.python-httpx.org/async/) | `client.stream()` + `aiter_lines()` 공식 지원 |
| E-A2-2 | [httpx Timeout Docs](https://www.python-httpx.org/advanced/timeouts/) | 기본 read timeout 5초 |

- `aiter_lines()`로 SSE 파싱 가능하나, 빈 줄 필터링 + `data:` 프리픽스 처리 필요.
- **LLM 응답 30~120초 → 반드시 `httpx.Timeout(connect=10.0, read=None)` 설정 필요**.
- 선택적: `httpx-sse` 라이브러리 사용 가능하나 Ollama 단순 SSE에는 불필요.

### A3: asyncio.Semaphore 대기자 추적 — PARTIAL

| 항목 | 출처 | 내용 |
|------|------|------|
| E-A3-1 | [CPython asyncio/locks.py](https://github.com/python/cpython/blob/main/Lib/asyncio/locks.py) | `_value`, `_waiters` 속성 존재 |
| E-A3-2 | [CPython Issue #90155](https://github.com/python/cpython/issues/90155) | `_waiters` deque FIFO 버그 (3.9~3.11, 이후 수정) |

- `_value`, `_waiters`는 private 속성 — 공개 API 아님.
- **MonitoredSemaphore 래퍼 클래스로 캡슐화 권장** (VETO 리뷰에서 이미 식별됨).
- `_waiters`는 초기 `None` → 첫 대기 시 deque 초기화 — `None` 체크 필요.

### A4: host.docker.internal macOS — PARTIAL

| 항목 | 출처 | 내용 |
|------|------|------|
| E-A4-1 | [Docker Desktop Networking](https://docs.docker.com/desktop/features/networking/) | macOS에서 자동 주입 공식 확인 |
| E-A4-2 | [docker/for-mac #7332](https://github.com/docker/for-mac/issues/7332) | v4.31~4.35 IPv6 해석 회귀 |
| E-A4-3 | [docker/for-mac #7786](https://github.com/docker/for-mac/issues/7786) | v4.48.0 DNS 타임아웃 회귀 |

- 기본 동작은 안정적이나, Docker Desktop 버전별 회귀 이력 존재.
- **`extra_hosts: ["host.docker.internal:host-gateway"]` 방어 설정 권고**.
- Linux 이식성도 확보됨 (Linux Docker Engine은 이 설정 필수).

### A5: prometheus_client + FastAPI — PARTIAL

| 항목 | 출처 | 내용 |
|------|------|------|
| E-A5-1 | [prometheus_client ASGI Docs](http://prometheus.github.io/client_python/exporting/http/asgi/) | `make_asgi_app()` 공식 지원 |
| E-A5-2 | [prometheus/client_python #1016](https://github.com/prometheus/client_python/issues/1016) | `app.mount("/metrics")` → `/metrics/` 307 리다이렉트 버그 |

- `make_asgi_app()` + `app.mount("/metrics")` 조합에서 **trailing slash 리다이렉트(307) 발생**.
- Prometheus 스크레이퍼가 리다이렉트를 따르지 못할 수 있음.
- **대안: FastAPI 네이티브 라우트로 교체**:
  ```python
  from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

  @app.get("/metrics")
  async def metrics():
      return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
  ```

---

## 권장 조치

### design.md 보완 필요 (2건)

- **[MAJOR] A5 — /metrics 구현 패턴 변경**: design.md 2-1의 `/metrics` 설명에 `make_asgi_app()` mount 대신 `@app.get("/metrics")` + `generate_latest()` 패턴 명시. Prometheus 스크래핑 실패 방지.
- **[MINOR] A2 — httpx timeout 명시**: design.md 2-4 Configuration에 `HTTPX_READ_TIMEOUT=None` 또는 코드 수준 timeout 설정 언급 추가.

### 구현 시 참고 (design 변경 불필요)

- **A1**: docker-compose.yml에서 Ollama 이미지 버전을 0.5.x 이상으로 고정 (`ollama/ollama:0.5` 또는 `latest`).
- **A3**: MonitoredSemaphore 래퍼 클래스 구현 (proxy/main.py 내부).
- **A4**: docker-compose.yml에 `extra_hosts: ["host.docker.internal:host-gateway"]` 추가.
