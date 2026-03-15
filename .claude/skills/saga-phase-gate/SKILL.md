---
name: saga-phase-gate
description: Manages Phase entry conditions, Gate checklists, deliverable tracking, and track switching across all SAGA phases. Use when entering a Phase, checking Gate conditions, reviewing deliverables, or switching tracks. Phase 진입, Gate 확인, Phase 전환, Gate 조건, 산출물, Handoff, 트랙 전환, Phase 0, Phase 1→2, Phase 2→3, Phase 3→4, Phase 4→5.
user-invocable: false
metadata:
  author: SAGA
  version: "2.0"
compatibility: Requires Claude Code with SAGA methodology template
---

# SAGA Phase Gate 운용 지침

## Permission Mode

| Phase | 명칭 | Permission Mode |
|-------|------|----------------|
| 0 | FOUNDATION | `default` |
| 1 | SPECIFICATION | `plan` |
| 2 | DESIGN | `acceptEdits` |
| 3 | BUILD | `acceptEdits` + Hooks 활성화 |
| 4 | VERIFY | `plan` |
| 5 | REFINE | `acceptEdits` |

## Phase별 필수 산출물

| 산출물 | Phase | Hotfix | Feature | Epic | 생성 주체 |
|--------|:-----:|:------:|:-------:|:----:|---------|
| `CLAUDE.md` | 0 | Y | Y | Y | Agent |
| `.claude/settings.json` | 0 | Y | Y | Y | Agent |
| `project-brief.md` | 0 입력 | — | Y | Y | Human 작성 |
| `requirements.md` (EARS) | 1 | — | — | Y | Agent |
| `design.md` | 2 | — | Y | Y | Agent |
| `tasks.md` | 2 | — | Y | Y | Agent |
| `docs/dod.md` | 2 | — | Y | Y | Agent |
| 코드 + 테스트 | 3 | Y | Y | Y | Agent |
| `docs/verify-report-YYYYMMDD.md` | 4 | — | Y | Y | Agent |
| `docs/handoffs/phase-N-YYYYMMDD-HHmm.md` | Gate 전환 시 | 권장 | Y | Y | **Agent** |

## Phase Gate 조건

**Phase 0 → 1 (또는 트랙 진입):**
- CLAUDE.md Constitution 완비
- settings.json allow/deny/ask 구성 완료
- Hook 스크립트 배포 및 테스트 완료

**Phase 1 → 2 (Epic Track):**
- 모든 요구사항에 **EARS 표기법** 적용 완료
- `[NEEDS CLARIFICATION]` 태그 0건
- VETO 미해소 건수 0건
- **Wave 분할 계획 수립** (Phase 2 병렬 Subagent 설계 선행 조건)
- Handoff 파일 시크릿 스캐닝 통과: `detect-secrets scan docs/handoffs/` 0건
- requirements.md Human 승인

**Phase 2 → 3:**
- design.md 모든 인터페이스 정의 완료
- tasks.md 의존성 그래프 순환 없음
- **`docs/dod.md` 작성 및 완비**

**Phase 3 → 4:**
- 모든 tasks.md 항목 완료 (미완료 0건, Feature/Epic)
- 전체 테스트 suite 통과 + Lint/Type check 통과
- PR 생성 완료
- Phase 4 Validator ≠ Phase 3 Generator (별개 인스턴스)

**Phase 4 → 완료 (Feature) / Phase 4 → 5 (Epic) / Phase 5 → 완료 (Epic):**
→ 상세 조건은 `saga-phase-verify` §6 참조.

**Phase Gate commit**: `<type>(TASK-ID): <Phase N 요약>` (Conventional Commits)

## Handoff 파일 원칙

| 파일 | 생성 주체 | 수정 가능 여부 |
|------|----------|-------------|
| `docs/handoffs/phase-N-YYYYMMDD-HHmm.md` | **Agent** (Gate 전환 시) | Agent 생성 후 수정 가능 |
| `docs/handoffs/HANDOFF.md` (대시보드) | **Human 전용** | Agent 수정·생성 금지 |

> CLAUDE.md Constitution의 `docs/handoffs/` 금지 규칙이 있는 경우,
> phase-N 파일 생성 허용으로 Constitution을 수정하거나, Human이 직접 생성한다.

## Phase 진입 시 입력 산출물 미존재 처리

Phase 진입 전 위 산출물 표의 해당 입력 산출물을 확인한다.
**미존재 시 → Human에게 해당 산출물 제공 요청 후 대기. Phase 진입 보류.**
