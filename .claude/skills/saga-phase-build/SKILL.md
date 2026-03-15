---
name: saga-phase-build
description: Guides Phase 3 BUILD implementation with TDAID 5-Phase TDD loop, Worktree parallel execution, and P3 prompt templates. Use when implementing code, running TDD, or managing Worktree builds. 구현, 빌드, TDD, TDAID, Phase 3, BUILD, Worktree, 리팩터링, PBT, Property-Based Testing, 테스트 작성.
user-invocable: false
metadata:
  author: SAGA
  version: "2.0"
compatibility: Requires Claude Code with SAGA methodology template
---

# SAGA Phase 3 BUILD 지침

## 1. Grounding Protocol

TDD 루프 시작 전, 핵심 의존 라이브러리의 최신 API를 확인하여 hallucination을 방지한다.

**절차**:
1. 담당 task의 핵심 의존 라이브러리 1~3개 식별 (design.md 기술 결정사항 + task AC 기준)
2. Context7 MCP 호출:
   - `resolve-library-id` → 라이브러리명으로 Context7 ID 조회
   - `query-docs` → task 관련 API/패턴 문서 검색
3. Grounding 결과 요약 후 TDD 루프 컨텍스트에 유지:
   ```
   라이브러리: [이름] vX.Y.Z
   관련 API: [함수/클래스, 시그니처]
   주요 변경사항: [이전 버전 대비]
   참고 스니펫: [Context7 핵심 코드]
   ```

## 2. TDAID 5-Phase TDD Loop

Phase 3 각 태스크는 다음 5단계 루프로 실행한다:

```
[Plan]     테스트 전략 수립, PBT 적용 결정, 경계 조건 식별
[Red]      실패 테스트 작성 (Contract 우선)
[Green]    최소 구현 (YAGNI)
[Refactor] 리팩터링 (3조건 충족 시에만)
[Validate] 통합 테스트 + 커버리지 + DoD 체크리스트
```

**[Plan]**: AC 기반 테스트 목록 + PBT 적용 여부 결정 + 경계 조건(null, 빈값, 최대값, 음수) 식별. 테스트 우선순위: Contract → Integration → E2E → Unit.

**[Red]**: 1순위 Contract 테스트(인터페이스 시그니처 검증) → Contract 통과 전 Integration 작성 금지. 엣지 케이스 최소 2개. 실행 후 예상 실패 확인 (통과하면 테스트 재작성).

**[Green]**: 테스트 통과 위한 최소 코드만 작성. 과도한 추상화·미래 코드 금지. Constitution 원칙 준수. 전체 suite 실행.

**[Refactor]**: 아래 3조건 AND 충족 시에만 수행:

| 조건 | 기준 |
|------|------|
| 전체 테스트 통과 | 실패 0건 |
| 커버리지 감소 없음 | Refactor 전 대비 0% 엄격 |
| 기능 추가 없음 | git diff 범위가 리팩터링으로 한정 |

재진입: 테스트 실패 → Red 재진입 / 커버리지 감소 → Refactor 재수행 / 기능 추가 감지 → 즉시 중단, 새 Red 시작.

**[Validate]**: 통합 테스트 + 커버리지 검증 + DoD 체크리스트 확인. Feature/Epic Track에만 적용. Validate 통과 = Phase 3→4 Gate 사전 점검 완료.

## 3. P3 프롬프트 템플릿

### 3-0. Grounding (TDD 시작 전)

```
역할: Phase 3(BUILD) Worker Agent
작업: TDD 루프 시작 전 Grounding 수행

1. 담당 task 핵심 의존 라이브러리 식별 (1~3개)
2. Context7 호출: resolve-library-id → query-docs
3. Grounding 결과 요약 후 3-1 TDD 루프 시작
```

### 3-1. TDD 루프 (단일 task)

```
역할: Phase 3(BUILD) Worker Agent
주입: @CLAUDE.md, [task 내용], [design.md 관련 섹션], [Grounding 결과]

실행: [Plan] → [Red] → [Green] → [Refactor] → [Validate] → git commit
커밋 형식: feat([task-id]): [task 제목]
Constitution 위반 발견 시 즉시 중단 + Human 보고.
```

### 3-2. Worktree 병렬 실행 (Lead → Subagents)

```
역할: Phase 3(BUILD) Lead Agent
주입: tasks.md 병렬 작업 그룹

배치:
1. 독립 task 그룹별 Subagent spawn (isolation: "worktree")
2. 각 Subagent 주입: 담당 task, CLAUDE.md, design.md 관련 섹션
3. 완료 후 메인 브랜치 통합
```

## 4. Worktree 병렬 실행 규칙

- **동일 파일 수정 금지**: tasks.md 의존성 그래프로 파일 소유권 확인
- **의존성 확인**: task 간 의존 관계 있으면 순차 실행 (병렬 불가)
- **충돌 해결**: merge conflict 발생 시 의미적 우선순위 기준 Lead 해소 → 판단 불가 시 Human 에스컬레이션
- **비정상 종료**: `git worktree list` 확인 → 내용 검토 후 cherry-pick → `git worktree remove`

## 5. Phase 3→4 준비 체크리스트

- [ ] tasks.md 전체 항목 완료 (미완료 0건, Feature/Epic)
- [ ] 전체 테스트 suite 통과
- [ ] Lint + Type check 통과
- [ ] PR 생성 완료
- [ ] Phase 4 Validator ≠ Phase 3 Generator (별개 Subagent 인스턴스)

## 6. PBT Quick Reference

**적용 기준**: EARS 요구사항에 "ANY", "ALL", "EVERY" 등 범위 표현이 있는 경우.

**EARS → Property 변환**:
```
EARS:     WHEN [event], THE SYSTEM SHALL [action]
Property: forAll(input) => trigger(event, input) implies action(result) == true
```

프레임워크: Python → Hypothesis, JS/TS → fast-check. Shrinking으로 최소 반례 자동 탐색.
