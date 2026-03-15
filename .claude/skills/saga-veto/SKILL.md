---
name: saga-veto
description: Manages VETO protocol, Agent Teams lifecycle, team composition, and consensus rules for multi-perspective decision making. Use when running VETO votes, setting up Agent Teams, or needing multi-perspective review. VETO, 투표, Agent Teams, 팀 구성, 합의, 다관점 검토, Teammate, 팀원 역할, Kill-switch, Generator-Validator.
user-invocable: false
metadata:
  author: SAGA
  version: "2.0"
compatibility: Requires Claude Code with SAGA methodology template
---

# SAGA VETO 프로토콜 및 Agent Teams 운용 지침

## Teammate VETO Perspective Guide

Phase별 Teammate/Reviewer 역할 배치:

| Phase | 역할 | 관점 | 주요 확인 항목 |
|-------|------|------|-------------|
| P1 SPEC | 사양-비평가 | 완결성·EARS 정확성 | PRD 누락, 모호성 |
| P1 SPEC | 도메인-전문가 | 구현 가능성·Constitution | 기술 제약, 원칙 충돌 |
| P2 DESIGN | 설계-비평가 | 아키텍처·순환 의존성 | 인터페이스 완결성 |
| P2 DESIGN | 구현-전략가 | DoD·구현 가능성 | Phase 3 실현 가능 수준 |
| P4 VERIFY | V-1 정확성 | 테스트·커버리지·중복 | Constitution 준수 |
| P4 VERIFY | V-2 보안 | 인증·인가·인젝션 | OWASP Top 10 |
| P4 VERIFY | V-3 성능 | N+1·메모리·블로킹 | Steady State 기준 |
| P4 VERIFY | V-4 Spec 정합성 | EARS 1:1·AC 충족 | design.md 인터페이스 일치 |

## Agent Teams 사용 조건

사용 전 확인:
- `settings.json`에 `"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"` 설정 여부
- 팀원은 Lead 대화 히스토리를 상속받지 않으므로 프롬프트에 핵심 컨텍스트 포함 필수
- 팀원 수: 3~4명, 모델: Sonnet 권장

**알려진 제약:** 세션 재개 불가, Nested Teams 불가, 세션당 1 Team.
다음 중 하나 해당 시 Subagent 기반으로 복귀:
- Agent Teams 기능 불안정 (스폰 오류 반복)
- 단일 Phase 내 Agent Teams Round가 5를 초과하는 상황이 반복됨

## Agent Teams Lifecycle (8단계)

```
[1] TeamCreate(team_name, description) — kebab-case, {phase}-{purpose}
[2] TaskCreate × N — 팀원 spawn 전 모든 태스크 사전 생성
[3] Agent tool + team_name — 팀원 spawn (3~4명, Sonnet)
[4] TaskUpdate(owner + in_progress) — Lead 할당 또는 팀원 자율 클레임
[5] SendMessage — broadcast(안건) 또는 message(1:1)
[6] 모니터링 — TaskList + TeammateIdle Hook(소프트 게이트)
[7] SendMessage(shutdown_request) — 팀원 응답 대기
[8] TeamDelete — 반드시 Lead 실행. 활성 팀원 있으면 실패
```

**TeammateIdle Hook**: 소프트 게이트. exit 2 피드백은 팀원에게 전달되지만 강제 차단 불가.
팀원 프롬프트에 "TeammateIdle 훅 피드백 수신 시 반드시 지시에 따를 것" 명시 필수.

## Generator–Validator 분리 원칙

Phase 3(BUILD) 산출물을 Phase 4(VERIFY)에서 검증할 때,
Phase 3 Generator와 동일한 Subagent 인스턴스를 Phase 4 Validator로 재사용하지 않는다.

---

## VETO 운용

### Phase A: Agent Teams 내부 토론
- Lead는 안건 broadcast 후 논의에서 제외 (앵커링 바이어스 방지)
- 각 Agent는 Lead에게 직접 투표 제출 (`VOTE: Approve` / `VETO + evidence + proposal`)
- **합의 기준**: Veto 0건 (전원 Approve)
- **Round 한도**: 5 Round → 미해소 시 SAGA 문서 원칙 기반 결정, `tasks.md`에 해당 안건 앞 `[문서 기반 결정]` 태그 기록

### Phase B: Lead 검토
- Lead가 합의안을 Constitution·requirements.md 기준으로 독립 분석
- Approve → 확정 / Veto → 사유 + 개선 방향과 함께 Phase A 재시작
- **Round 한도**: 3 Round → 미해소 시 Human 에스컬레이션

### Kill-switch 예외 (투표 없이 즉시 발동)

| 조건 | 조치 |
|------|------|
| 보안 취약점 (CVE High/Critical) | 즉시 VETO + **작업 중단** |
| 법적 컴플라이언스 위반 | 즉시 VETO + **Human 에스컬레이션** |
