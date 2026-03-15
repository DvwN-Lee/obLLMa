# SAGA 핵심 운용 지침 (Core Protocol)

> 매 세션 항상 로드. Phase·Agent·실패 세부 지침은 Skills를 호출한다.
> CLAUDE.md(Constitution)와 함께 적용되며, 충돌 시 CLAUDE.md가 우선한다.

**Skills (필요 시 호출):**
- `saga-phase-gate` — Phase 진입·Gate 조건·Handoff
- `saga-phase-spec` — EARS 가이드·P1/P2 프롬프트·design/tasks 포맷
- `saga-phase-build` — TDAID TDD·P3 프롬프트·Worktree 병렬 실행
- `saga-phase-verify` — V-1~V-4 체크리스트·verify-report·P4/P5 프롬프트
- `saga-agents` — Subagent 구성·모델 티어링·Worktree 격리
- `saga-veto` — VETO 프로토콜·Agent Teams·팀 구성·합의
- `saga-recovery` — 실패 대응·Circuit Breaker·에스컬레이션

---

## 1. 세션 시작 체크

1. `memory/MEMORY.md` — 이전 세션 패턴·아키텍처 결정
2. `docs/handoffs/HANDOFF.md` — 현재 Phase Gate 상태 (없으면 Phase 0)
3. `docs/improvements/INDEX.md` — 미해결 개선 항목
4. `status: pending-update` 파일 — 7일 내 해소 필요 항목

HANDOFF.md에 진행 중 Phase 있으면 → 해당 Phase 재개. 신규 요청이면 → 트랙 판단.

## 2. 트랙 선택

**기준 하나라도 상위 트랙에 해당하면 상위 선택 (안전 우선).**

| 트랙 | 판단 기준 | Phase 경로 |
|------|----------|-----------|
| **Hotfix** | ≤5파일 AND 단일 버그 AND Subagent 불필요 | 3 → 4-Auto |
| **Feature** | 6~20파일 OR 신규 모듈 ≤1 OR Subagent 1~2 | 2 → 3 → 4 |
| **Epic** | >20파일 OR 신규 시스템 계층 OR Subagent ≥3 | 1 → 2 → 3 → 4 → 5 |

트랙 전환: `git commit`으로 보존 → 상위 트랙 첫 Phase부터 재개.

## 3. P0 Foundation 체크리스트

Phase 0 완료 전 확인:
- [ ] CLAUDE.md Constitution 정의 (원칙 5~9개, 금지 행동 3~5개)
- [ ] `.claude/settings.json` allow/deny/ask 3-Tier 구성
- [ ] Hook 스크립트 배포 및 테스트 (classify-bash, lint-docs, sync-check)
- [ ] `project-brief.md` 존재 확인 (Feature/Epic Track)

## 4. 세션 마무리

**MEMORY.md 업데이트** — 저장: 반복 확인된 패턴, 핵심 아키텍처 결정, 반복 문제 해결법. 저장 금지: 임시 상태, 단일 세션 패턴, CLAUDE.md 중복.

**Handoff** — `docs/handoffs/HANDOFF.md`는 절대 수정 금지 (Human 전용). Gate 전환 시 `phase-N-YYYYMMDD-HHmm.md` 생성.

**Retrospective (Episodic Memory)** — Phase 완료 후 `memory/episodes/{date}-{feature}.md` 생성:
```
## What went well       — [Phase N] ...
## What to improve      — [Phase N] ...
## 숫자                 — Cycle Time, Phase별 소요, VETO/이슈 건수
```
Episodic 3회 반복 패턴 → Semantic Memory(CLAUDE.md) 승격.

## 5. 보안 인식

```
Layer 1: 시스템 프롬프트  → 확률적 behavioral
Layer 2: settings.json   → 확률적 (간헐적 무시 가능)
Layer 3: PreToolUse Hook → 결정론적 (exit 2 = 강제 차단)
```

민감 파일 접근 금지: `.env`, `.env.*`, `*.pem`, `*.key`, `credentials*`, `secrets*`, `terraform.tfvars`
