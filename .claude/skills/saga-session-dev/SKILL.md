---
name: saga-session-dev
description: Activates Dev session for Phase 3 BUILD. Configures acceptEdits-mode, Grounding Protocol, TDAID TDD loop, and Worktree parallel execution. Use when starting a dev session. /saga-session-dev, 개발 세션, 구현 세션, Dev, 빌드 세션.
user-invocable: true
metadata:
  author: SAGA
  version: "2.0"
compatibility: Requires Claude Code with SAGA methodology template
---

# Dev 세션 지침

> 이 세션은 **Phase 3 BUILD** 전담입니다.
> Permission Mode: `acceptEdits` — 코드 구현, 테스트 실행, 파일 편집을 수행합니다.

## 세션 책임

| 책임 | 상세 |
|------|------|
| Grounding | Context7으로 핵심 라이브러리 API 확인 |
| TDD 구현 | TDAID 5-Phase: Plan → Red → Green → Refactor → Validate |
| 병렬 빌드 | Worktree 격리로 독립 task 병렬 실행 |
| 커밋 관리 | `feat(TASK-ID): [task 제목]` Conventional Commits |
| PR 생성 | Phase 3→4 Gate 전 PR 준비 |

## 참조 Skill

이 세션에서 활성화되는 Phase Skill:
- **saga-phase-build** — Grounding Protocol, TDAID TDD, P3 프롬프트, Worktree 규칙, PBT
- **saga-recovery** — 실패 대응, Circuit Breaker, 에스컬레이션

## Subagent 활용

Subagent spawn 시 `dev-worker` agent를 사용한다:
```
Agent(name: "impl-worker", subagent_type: "dev-worker", model: "sonnet", isolation: "worktree")
```

병렬 Worktree 실행 규칙:
- 동일 파일 수정 금지 (tasks.md 의존성 그래프로 소유권 확인)
- 의존 관계 있는 task는 순차 실행
- 충돌 발생 시 Lead 해소 → 판단 불가 시 Human 에스컬레이션

## 세션 산출물

| 산출물 | Track 적용 |
|--------|-----------|
| 소스 코드 + 테스트 | Hotfix, Feature, Epic |
| PR | Feature, Epic |

## 세션 입력 조건

- design.md, tasks.md 존재 필수 (Feature/Epic)
- dod.md 존재 필수 (Feature/Epic)
- 미존재 시 → Architect 세션에 설계 요청 후 대기

## 금지 사항

- requirements.md, design.md 수정 (Spec 후퇴 금지)
- Phase 4 VERIFY 작업 수행 (Generator ≠ Validator)
- 테스트 없는 코드 커밋
