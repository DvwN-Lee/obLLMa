---
name: saga-phase-spec
description: Guides Phase 1 SPECIFICATION and Phase 2 DESIGN with EARS notation, requirements analysis, design document standards, and task breakdown formats. Use when writing requirements, design docs, or task breakdowns. EARS, 요구사항, requirements.md, design.md, tasks.md, Phase 1, Phase 2, SPECIFICATION, DESIGN, dod.md, 사양 작성, 설계 리뷰, VETO 투표.
user-invocable: false
metadata:
  author: SAGA
  version: "2.0"
compatibility: Requires Claude Code with SAGA methodology template
---

# SAGA Phase 1~2 Specification & Design 지침

## 1. EARS Notation Guide

모든 요구사항을 다음 5패턴 중 하나로 작성한다:

| 패턴 | 형식 | 예시 |
|------|------|------|
| Ubiquitous | The [system] shall [action] | The system shall encrypt all passwords |
| Event-driven | When [event], the [system] shall [action] | When a user logs in, the system shall create a session |
| Unwanted | If [condition], then the [system] shall [action] | If auth fails 5 times, then the system shall lock the account |
| State-driven | While [state], the [system] shall [action] | While offline, the system shall queue requests |
| Optional | Where [feature], the [system] shall [action] | Where dark mode is enabled, the system shall apply dark theme |

**`[NEEDS CLARIFICATION]` 규칙**: 모호/불명확한 요구사항에 반드시 태그 추가. Phase 1→2 Gate 통과 전 0건 필수.

## 2. P1 프롬프트 템플릿

### 1-1. 요구사항 분석 (Lead → Teammates)

```
역할: SAGA Phase 1(SPECIFICATION) Lead Agent
주입: @CLAUDE.md, [PRD/이슈 설명]

작업:
1. PRD에서 명시적/암묵적 요구사항 추출
2. 각 요구사항을 EARS 5패턴 중 하나로 변환
3. [NEEDS CLARIFICATION] 태그 추가 (모호 항목)
4. 비기능 요구사항 분리 (성능/보안/호환성)

초안 완성 후 Teammate에게 VETO 검토 요청.
Teammate 역할: [사양-비평가], [도메인-전문가]
```

### 1-2. VETO 투표 (Teammate)

```
역할: Phase 1 [역할명] Agent
검토 대상: [requirements.md 초안]

검토 기준:
1. 완결성 — PRD 모든 요구사항 포함 여부
2. EARS 정확성 — 올바른 패턴 사용 여부
3. 모호성 — [NEEDS CLARIFICATION] 누락 여부
4. Constitution 정합성 — CLAUDE.md 원칙 충돌 여부
5. 구현 가능성 — 현재 기술 스택 범위 내 여부

VETO 시: 구체적 사유 + 수정안 필수. 사유 없는 VETO 무효.
```

## 3. design.md 표준 포맷

```markdown
# design.md: [프로젝트명]

## 아키텍처 개요
[시스템 컴포넌트 구조 + 의존성 다이어그램 (텍스트)]

## 공개 인터페이스 정의
[함수 시그니처, API 엔드포인트, 클래스 인터페이스]

## 데이터 모델
[핵심 데이터 구조 및 스키마]

## 기술 결정사항
[라이브러리/패턴 선택 근거, Constitution 정합성 확인]
```

## 4. tasks.md 표준 포맷

```markdown
| Task ID | 설명 | AC | 의존 Task | 병렬 그룹 | 상태 | 시작 | 완료 | Cycle Time |
|---------|------|----|----------|----------|------|------|------|------------|
| T-001 | [제목] | [Acceptance Criteria] | — | G1 | Todo | | | |
```

상태 모델: `Todo → In Progress → Done`
의존성 그래프에 순환 없음 필수 (위상 정렬 검증).

## 5. P2 프롬프트 템플릿

### 2-1. 시스템 설계 (Lead → Subagents)

```
역할: SAGA Phase 2(DESIGN) Lead Agent
주입: @CLAUDE.md, @requirements.md

금지: requirements.md 외 기능 추가 설계, 구현 코드 작성,
      design.md 없이 tasks.md 작성, 순환 의존성 포함 tasks.md

작업:
1. design.md 작성 (§3 포맷)
2. tasks.md 작성 (§4 포맷) — 의존성 그래프 + 병렬 그룹 식별
3. 초안 완성 후 Subagent에게 리뷰 요청

Subagent 역할: [설계-비평가], [구현-전략가]
```

### 2-2. 설계 리뷰 (Subagent)

```
역할: Phase 2 [설계-비평가 | 구현-전략가] Subagent
검토 대상: [design.md + tasks.md 초안]

검토 기준:
1. 인터페이스 완결성 — requirements.md 전체 기능 표현 여부
2. 순환 의존성 없음 — tasks.md 그래프 검증
3. Constitution 정합성 — CLAUDE.md 원칙 준수
4. DoD 충족 가능성 — 설계로 DoD 기준 충족 가능 여부
5. 구현 가능성 — Phase 3 실현 가능 수준의 정의 여부

Reject 시: 구체적 사유 + 수정안 필수. 사유 없는 Reject 무효.
```

## 6. dod.md 체크리스트 참조

Phase 2 완료 시 `docs/dod.md` 작성 필수 (Phase 2→3 Gate 조건).

**최소 필수 항목**:
- [ ] 모든 R-NNN이 tasks.md에 task로 분해됨
- [ ] 각 task에 AC(Acceptance Criteria) 1개 이상
- [ ] design.md 공개 인터페이스 정의 완료
- [ ] tasks.md 순환 의존성 0건

도메인별 확장: [SAGA-domain-adaptation.md §5](../../../methodology/SAGA-domain-adaptation.md#5-doddefinition-of-done-체크리스트-템플릿) 참조.
