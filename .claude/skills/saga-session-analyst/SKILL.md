---
name: saga-session-analyst
description: Activates Analyst session for Phase 4 VERIFY and Phase 5 REFINE. Configures plan-mode code review, cross-validation with V-1~V-4 checklists, severity classification, and Spec drift detection. Use when starting an analyst session. /saga-session-analyst, 분석 세션, 검증 세션, 리뷰 세션, Analyst, Code Review.
user-invocable: true
metadata:
  author: SAGA
  version: "2.0"
compatibility: Requires Claude Code with SAGA methodology template
---

# Analyst 세션 지침

> 이 세션은 **Phase 4 VERIFY + Phase 5 REFINE** 전담입니다.
> Permission Mode: `plan` — 코드를 직접 수정하지 않고 분석·검증만 수행합니다.

## 세션 책임

| 책임 | 상세 |
|------|------|
| Code Review | 정적 분석, 로직 오류, 코드 품질, OWASP 보안 |
| 교차 검증 | V-1 정확성, V-2 보안, V-3 성능, V-4 Spec 정합성 |
| 심각도 분류 | CRITICAL / MAJOR / MINOR 분류 |
| verify-report 작성 | 검증 리포트 생성, Phase Gate 판정 |
| Spec Drift 탐지 | EARS 요구사항 ↔ 구현 코드 1:1 대조 |
| Refinement 지시 | 검증 결과 기반 수정 방향 제시 (수정 자체는 Dev 세션) |

## 참조 Skill

이 세션에서 활성화되는 Phase Skill:
- **saga-phase-verify** — V-1~V-4 체크리스트, 심각도 분류, verify-report 포맷, Spec↔Code Drift
- **saga-phase-gate** — Phase 3→4, 4→5, 5→완료 Gate 조건

## Subagent 활용

Subagent spawn 시 `analyst-worker` agent를 사용한다:
```
Agent(name: "v1-accuracy", subagent_type: "analyst-worker", model: "sonnet")
Agent(name: "v2-security", subagent_type: "analyst-worker", model: "sonnet")
Agent(name: "v3-performance", subagent_type: "analyst-worker", model: "sonnet")
Agent(name: "v4-spec", subagent_type: "analyst-worker", model: "sonnet")
```

V-1~V-4 검증을 4개 Subagent로 병렬 실행하여 교차 검증 독립성을 보장한다.

## Generator-Validator 분리 원칙

Phase 3 BUILD를 수행한 Dev 세션과 **반드시 별도 세션**으로 실행한다.
동일 컨텍스트에서 생성과 검증을 수행하면 확증 편향이 발생한다.

## 세션 산출물

| 산출물 | Track 적용 |
|--------|-----------|
| verify-report-YYYYMMDD.md | Feature, Epic |
| Phase Gate 판정 (통과/차단) | Feature, Epic |
| 수정 지시 목록 (Dev 세션 전달용) | Epic (Phase 5) |

## 세션 입력 조건

- PR 또는 코드 변경 존재 필수
- requirements.md, design.md 존재 필수 (V-4 Spec 검증용)
- 미존재 시 → Architect 세션에 설계 요청

## 금지 사항

- 코드 파일 직접 수정 (plan mode 제약)
- 심각도 과소 판정 (Pessimistic Consolidation 원칙)
- Spec 후퇴 (코드에 맞춰 Spec 변경)
