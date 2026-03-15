# CLAUDE.md — llm-serving-observability

> **프로젝트 유형**: LLM 서빙 관측 가능성 (Observability) 포트폴리오
> **Phase 0 상태**: 완료

---

## Constitution

llm-serving-observability 프로젝트 관리 시 반드시 준수해야 하는 불변 원칙이다.

### 핵심 원칙

1. **Docker Compose 자족성**: 모든 서비스는 `docker-compose up`으로 즉시 구동 가능해야 한다. 외부 서비스 의존 금지.
2. **메트릭 SSOT**: 메트릭 정의(이름, 타입, 레이블, 버킷)는 `proxy/metrics.py` 한 곳에서만 관리한다.
3. **Grafana GitOps**: 대시보드는 JSON 파일로 버전 관리한다. UI 직접 수정 후 JSON 미반영 금지.
4. **OpenAI 호환성**: 프록시는 OpenAI API 규격(`/v1/chat/completions`)을 준수하여 LLM 엔진 교체 가능성을 보장한다.
5. **관측 우선**: 기능 추가보다 메트릭 정확성과 대시보드 가독성을 우선한다.
6. **재현 가능한 벤치마크**: 부하 테스트는 스크립트로 관리하며, 동일 조건에서 재현 가능해야 한다.
7. **비용 $0 기본**: 로컬 환경(Ollama + Docker)에서 모든 기능이 동작해야 한다. 클라우드는 선택 사항.

### 금지 행동

- `docs/handoffs/` 내 파일 수정 또는 생성 (Human 전용 영역)
- 메트릭 이름·타입·레이블 변경 시 대시보드 JSON 동기화 없이 커밋
- Ollama 모델을 Docker 이미지에 번들링 (용량 문제, 런타임 pull 사용)
- `.env` 파일에 실제 시크릿 커밋 (`.env.example`만 버전 관리)

### 작업 흐름

```
[코드 변경] → [pytest] → [docker-compose up] → [메트릭 확인] → [대시보드 동기화] → [커밋]
```

- 메트릭 변경 시: `proxy/metrics.py` 수정 → 대시보드 JSON PromQL 업데이트 → 통합 테스트
- 대시보드 변경 시: Grafana UI에서 편집 → JSON Export → `grafana/dashboards/` 반영

### Steady State 기준

| 항목 | 기준 |
|------|------|
| docker-compose up | 전체 스택 헬스체크 통과 (Ollama, Proxy, Prometheus, Grafana) |
| /metrics 응답 | Prometheus 스크래핑 성공, 모든 메트릭 타입 정상 노출 |
| Grafana 대시보드 | 프로비저닝 자동 로드, No Data 패널 없음 (부하 발생 후) |

---

## SAGA 운용 지침

@SAGA-CORE.md

---

## PR Writing Rules

- Do not include "Generated with [Claude Code](...)" or "🤖 Generated with" lines in PR descriptions.
- Do not include "Co-Authored-By: Claude ..." lines in PR descriptions or commit messages.
- Use `.claude/hooks/pr-wrapper.sh` to strip these lines before posting a PR description.
- Use `.claude/hooks/strip-claude-meta.sh` as a commit-msg hook to strip them from commits.
