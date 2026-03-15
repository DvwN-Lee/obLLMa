---
name: saga-session-architect
description: Activates Architect session for Phase 1 SPECIFICATION and Phase 2 DESIGN. Configures plan-mode constraints, EARS-based requirements analysis, system design, and task decomposition. Use when starting an architect session. /saga-session-architect, 아키텍트 세션, 설계 세션, 사양 세션, Architect.
user-invocable: true
metadata:
  author: SAGA
  version: "2.0"
compatibility: Requires Claude Code with SAGA methodology template
---

# Architect 세션 지침

> 이 세션은 **Phase 1 SPECIFICATION + Phase 2 DESIGN** 전담입니다.
> Permission Mode: `plan` — 코드 수정 없이 분석·설계만 수행합니다.

## 세션 책임

| 책임 | 상세 |
|------|------|
| 요구사항 분석 | PRD → EARS 5패턴 변환, `[NEEDS CLARIFICATION]` 태그 |
| 시스템 설계 | design.md 작성 (아키텍처, 인터페이스, 데이터 모델) |
| 태스크 분해 | tasks.md 작성 (의존성 그래프, 병렬 그룹, AC) |
| VETO 주도 | Agent Teams로 사양·설계 리뷰 진행 |
| DoD 정의 | dod.md 체크리스트 작성 |

## 참조 Skill

이 세션에서 활성화되는 Phase Skill:
- **saga-phase-spec** — EARS 가이드, P1/P2 프롬프트, design/tasks 포맷
- **saga-phase-gate** — Phase 0→1→2 Gate 조건, 산출물 체크리스트
- **saga-veto** — VETO 프로토콜, Agent Teams Lifecycle, Teammate 역할 배치

## Subagent 활용

Subagent spawn 시 `architect-worker` agent를 사용한다:
```
Agent(name: "spec-analyst", subagent_type: "architect-worker", model: "sonnet")
```

Agent Teams 구성 시 Teammate 역할:
- **사양-비평가**: 완결성, EARS 정확성, 모호성 검토
- **도메인-전문가**: 구현 가능성, Constitution 정합성 검토
- **설계-비평가**: 아키텍처 순환 의존성, 인터페이스 완결성
- **구현-전략가**: DoD 충족 가능성, Phase 3 실현 가능 수준

## 세션 산출물

| 산출물 | Track 적용 |
|--------|-----------|
| requirements.md (EARS) | Epic |
| design.md | Feature, Epic |
| tasks.md | Feature, Epic |
| dod.md | Feature, Epic |

## 금지 사항

- 코드 파일 생성·수정 (plan mode 제약)
- Phase 3 BUILD 작업 수행
- requirements.md 외 기능 추가 설계
