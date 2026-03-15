# dod.md: llm-serving-observability

> **Phase**: 2 (DESIGN) → Phase 3 (BUILD) Gate 조건
> **Track**: Feature

---

## Phase 2 → 3 Gate Checklist

Phase 3 BUILD 진입 전 아래 항목이 모두 충족되어야 한다.

### Design Completeness

- [ ] design.md 작성 완료 — 아키텍처, 인터페이스, 데이터 모델, 기술 결정 포함
- [ ] tasks.md 작성 완료 — 7개 태스크, AC 정의, 의존성 그래프 순환 없음
- [ ] dod.md 작성 완료 (이 문서)
- [ ] tasks.md의 모든 태스크에 AC 1개 이상 정의

### Interface Definition

- [ ] Proxy API 3개 엔드포인트 정의 (/v1/chat/completions, /health, /metrics)
- [ ] Prometheus 메트릭 11개 정의 (이름, 타입, 레이블, 버킷)
- [ ] Grafana 대시보드 패널 10개 + PromQL 쿼리 정의
- [ ] 환경변수 5개 정의 (OLLAMA_BASE_URL 등)

### Constitution Alignment

- [ ] Constitution #1 (Docker Compose 자족성): Ollama Hybrid Strategy 문서화
- [ ] Constitution #2 (메트릭 SSOT): proxy/metrics.py 단일 정의 명시
- [ ] Constitution #3 (Grafana GitOps): JSON 프로비저닝 방식 설계
- [ ] Constitution #4 (OpenAI 호환성): /v1/chat/completions 양방향 사용 결정
- [ ] Constitution #5 (관측 우선): 11개 메트릭 + 커스텀 버킷 설계
- [ ] Constitution #6 (재현 가능 벤치마크): 5가지 시나리오 스크립트 기반
- [ ] Constitution #7 (비용 $0 기본): 로컬 환경 완전 동작 설계

---

## Phase 3 BUILD 완료 기준 (DoD)

Phase 3 완료 시 아래 항목이 모두 충족되어야 한다.

### Functionality

- [ ] `docker compose up -d` → 전체 스택 헬스체크 통과
- [ ] `POST /v1/chat/completions` → streaming + non-streaming 정상 동작
- [ ] `GET /metrics` → 11개 메트릭 Prometheus exposition format 노출
- [ ] Grafana 대시보드 자동 프로비저닝, $model 변수 동작
- [ ] Load Generator S1~S5 시나리오 실행 가능

### Metric Accuracy

- [ ] TTFT: 스트리밍 첫 content 청크 시점 정확히 기록
- [ ] TPS: output_tokens / duration 올바르게 계산
- [ ] TPOT: duration / output_tokens 올바르게 계산
- [ ] Active Requests: 세마포어 내부 요청 수와 일치
- [ ] Queue Depth: 세마포어 대기 요청 수와 일치
- [ ] Histogram 버킷: design.md 3-1의 커스텀 버킷 적용 확인

### Dashboard

- [ ] 10개 패널 모두 데이터 표시 (부하 발생 후 No Data 없음)
- [ ] PromQL 쿼리 정상 동작 (Prometheus에서 직접 검증)
- [ ] $model 변수로 모델별 필터링 동작

### Benchmark

- [ ] 최소 2개 모델 벤치마크 완료
- [ ] benchmarks/results.md에 결과 기록
- [ ] Grafana 스크린샷 2장 이상

### Documentation

- [ ] README.md: Quick Start 5단계 이내
- [ ] README.md: 아키텍처 다이어그램, 스크린샷 포함
