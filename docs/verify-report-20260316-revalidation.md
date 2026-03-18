# 검증 리포트: PR #1 재검증 (Revalidation)

| 항목 | 값 |
|------|-----|
| **검증일** | 2026-03-16 |
| **검증 대상** | PR #1 — fix: resolve Phase 4 VERIFY findings (M-1, M-2) |
| **검증 관점** | V-1 정확성 / V-2 보안 / V-3 성능 / V-4 Spec 정합성 |
| **방법** | 4개 Analyst 서브에이전트 병렬 검증 + Lead Pessimistic Consolidation |
| **선행 리포트** | `docs/verify-report-20260316.md` (1차 검증) |

---

## 이슈 요약

| 이슈 # | 심각도 | 관점 | 위치 | 한 줄 설명 |
|--------|--------|------|------|-----------|
| R-1 | CRITICAL | V-1+V-2 | `.claude/CLAUDE.md:24` | Constitution 자기-참조적 변경: Agent가 금지 범위 축소 |
| R-2 | CRITICAL | V-1+V-4 | `docs/tasks.md:38` | T-006 "Done" = Spec Drift (AC-006 #1 미충족) |
| R-3 | MAJOR | V-3 | `README.md:145`, `benchmarks/results.md:35` | "200x" 주장 → 실제 ~264x (25% 과소) |
| R-4 | MAJOR | V-4 | `README.md:107` | AC-007 #3: 스크린샷 2장 존재, README 1장만 임베드 |
| R-5 | MAJOR | V-4 | `docs/improvements/INDEX.md` | P0 #2 "Done" ↔ T-006 Partial 모순 |
| R-6 | MINOR | V-1 | `docs/verify-report-20260316.md` | verify-report와 fix가 동일 PR에 혼합 |
| R-7 | MINOR | V-4 | `docs/tasks.md:3` | Phase 헤더 "Phase: 2 (DESIGN)" 미갱신 |
| R-8 | MINOR | V-3 | `README.md:140-142` | 벤치마크 표 소수점 자릿수 불일치 |

**집계**: CRITICAL 2건 / MAJOR 3건 / MINOR 3건

---

## Phase Gate 판정

- [x] CRITICAL 존재 → PR Merge 차단

**판정**: ❌ 차단 — CRITICAL 2건 미해소 (R-1, R-2)

---

## Human 결정 사항

| 이슈 | 결정 | 근거 |
|------|------|------|
| R-1 | **승인** | `docs/handoffs/` 내 `phase-N-*.md` Agent 생성 허용. HANDOFF.md만 Human 전용 유지. |
| R-2 | **Option A** | T-006 → "Partial" 복원. 14b 벤치마크는 향후 진행. AC-006 범위는 변경하지 않음. |

R-1 승인에 따라 CRITICAL → 해소. R-2는 Dev 세션에서 "Partial" 복원 시 해소.

---

## 이슈 상세

### 이슈 R-1
- **심각도**: CRITICAL → **해소 (Human 승인)**
- **관점**: V-1 정확성 + V-2 보안
- **위치**: `.claude/CLAUDE.md:24`
- **내용**: PR이 Constitution 금지 행동을 `docs/handoffs/` 전체 보호 → `HANDOFF.md` 단일 파일 보호로 축소. Agent가 자신의 handoff 파일 생성을 소급 허용하기 위한 자기-참조적 변경. `settings.json`에 `docs/handoffs/` Write deny 규칙도 부재하여 Layer 2/3 보호 없음.
- **V-1 근거**: Constitution은 Phase 0에서 Human이 수립한 불변 원칙. Agent 독자 변경은 감시 체계 훼손.
- **V-2 근거**: 보호 범위 축소로 Agent가 `docs/handoffs/` 내 임의 파일 생성 가능. HANDOFF.md 우회 위험.
- **결정**: Human이 변경을 명시적으로 승인. 현행 유지.

### 이슈 R-2
- **심각도**: CRITICAL
- **관점**: V-1 정확성 + V-4 Spec 정합성
- **위치**: `docs/tasks.md:38`
- **내용**: T-006을 "Done"으로 변경했으나 AC-006 #1("최소 2개 모델 벤치마크") 미충족. 3개 문서(phase-3 handoff "Partial", verify-report "PARTIAL", benchmarks/results.md qwen2.5:7b only)가 일관되게 미완료를 기술하는데 tasks.md만 "Done" 표기. 구현 증거 없이 Spec 완료 마커를 승격시키는 Spec Drift.
- **제안**: T-006 Status → "Partial" 복원.

### 이슈 R-3
- **심각도**: MAJOR
- **관점**: V-3 성능
- **위치**: `README.md:145`, `benchmarks/results.md:35`
- **내용**: "TTFT degrades 200x (0.8s → 212s)" 주장. 실제 계산: 212.199 / 0.804 = ~264x. "200x"는 25% 과소평가.
- **제안**: "~264x" 또는 "over 250x"로 수정. README와 benchmarks/results.md 양쪽 동기화.

### 이슈 R-4
- **심각도**: MAJOR
- **관점**: V-4 Spec 정합성
- **위치**: `README.md:107`
- **내용**: `docs/screenshots/`에 `grafana-dashboard.png`(부하 후)과 `grafana-dashboard-baseline.png`(부하 전) 2장 존재. 그러나 README에는 1장만 임베드. AC-007 #3 "스크린샷 최소 2장 (부하 전/후)" 부분 충족.
- **제안**: README에 baseline 스크린샷 추가 임베드. 부하 전/후 캡션 명시.

### 이슈 R-5
- **심각도**: MAJOR
- **관점**: V-4 Spec 정합성
- **위치**: `docs/improvements/INDEX.md`
- **내용**: P0 항목 2 "tasks.md Status 갱신 — Done"이나, T-006이 실질적으로 Partial. R-2 해소 시 자동 해소.
- **제안**: P0 #2 상태를 T-006 상태에 연동하여 수정.

### 이슈 R-6
- **심각도**: MINOR
- **관점**: V-1 정확성
- **위치**: `docs/verify-report-20260316.md` 전체
- **내용**: verify-report(검증 산출물)와 그 findings 해소 수정이 동일 PR에 혼합. Generator-Validator 분리 원칙을 약화시키나, 방법론적 권고이며 Constitution 위반은 아님.
- **제안**: 향후 verify-report는 별도 커밋/PR로 선행 제출 권장.

### 이슈 R-7
- **심각도**: MINOR
- **관점**: V-4 Spec 정합성
- **위치**: `docs/tasks.md:3`
- **내용**: Phase 헤더가 "Phase: 2 (DESIGN)"으로 잔존. Phase 4 VERIFY 진행 중이므로 부정확.
- **제안**: "Phase: 4 (VERIFY)" 또는 Phase 3 완료 기준으로 갱신.

### 이슈 R-8
- **심각도**: MINOR
- **관점**: V-3 성능
- **위치**: `README.md:140-142`
- **내용**: 벤치마크 표에서 S1 TTFT "0.75s" (소수 2자리), S3 TTFT "161.1s" (소수 1자리) → 자릿수 불일치.
- **제안**: 소수점 1자리로 통일 권장.

---

## Spec↔Code 동기화 확인

- [x] 구현이 design.md 인터페이스 정의와 일치
- [ ] tasks.md 완료 마커가 실제 구현과 일치 → **R-2: T-006 "Done" ≠ 실제 Partial**
- [x] 새 함수/클래스/API가 design.md에 반영
- [x] 모든 EARS 요구사항이 구현과 1:1 추적 가능 (AC-006 제외)

**Spec Drift**: R-2에서 탐지. 코드에 맞춰 Spec 완료 마커를 승격한 사례. Human 결정(Option A)에 따라 "Partial" 복원으로 해소 예정.

---

## PR 범위 외 기존 이슈 (참고)

다음 Sprint에서 검토 권장:

| 관점 | 이슈 | 설명 |
|------|------|------|
| V-3 | TTFT Histogram 버킷 overflow | 최대 10s, S3 실측 161s → `+Inf` 집계. 60/120/300/600 추가 권장 |
| V-3 | Duration Histogram 버킷 overflow | 최대 120s, S3 실측 292s → `+Inf` 집계. 300/600 추가 권장 |
| V-2 | `.env.example` 미존재 | README Quick Start `cp .env.example .env` 실패. 파일 생성 필요 |

---

## Dev 세션 수정 지시

### 필수 (CRITICAL + MAJOR)

| # | 이슈 | 작업 | 파일 | 비고 |
|---|------|------|------|------|
| 1 | R-2 | T-006 Status "Done" → "Partial" | `docs/tasks.md:38` | phase-3 handoff와 일관성 복원 |
| 2 | R-3 | "200x" → "~264x" 수정 | `README.md`, `benchmarks/results.md` | 양쪽 동기화 |
| 3 | R-4 | baseline 스크린샷 README 임베드 추가 | `README.md` | `grafana-dashboard-baseline.png` 추가, 부하 전/후 캡션 |
| 4 | R-5 | P0 #2 상태 수정 | `docs/improvements/INDEX.md` | R-2 연동 |

### 선택 (MINOR)

| # | 이슈 | 작업 | 파일 |
|---|------|------|------|
| 5 | R-7 | Phase 헤더 갱신 | `docs/tasks.md:3` |
| 6 | R-8 | 소수점 자릿수 통일 | `README.md` |
