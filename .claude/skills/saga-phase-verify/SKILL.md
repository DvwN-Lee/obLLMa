---
name: saga-phase-verify
description: Runs Phase 4 VERIFY cross-validation and Phase 5 REFINE with V-1~V-4 checklists, severity classification, verify-report generation, and Spec drift detection. Use when running verification, writing verify-reports, classifying issue severity, or checking Spec drift. 검증, 교차 검증, Phase 4, Phase 5, VERIFY, REFINE, V-1, V-2, V-3, V-4, verify-report, 심각도, CRITICAL, MAJOR, MINOR, Spec drift, Spec↔Code.
user-invocable: false
metadata:
  author: SAGA
  version: "2.0"
compatibility: Requires Claude Code with SAGA methodology template
---

# SAGA Phase 4~5 Verify & Refine 지침

## 1. V-1~V-4 검증 체크리스트

### V-1 정확성 검토
- [ ] Constitution 아키텍처 원칙 준수
- [ ] 레이어 역전/순환 의존성 없음
- [ ] 모든 공개 인터페이스에 테스트 존재
- [ ] 테스트 커버리지 ≥ 프로젝트 기준
- [ ] 코드 중복 없음

### V-2 보안 검토
- [ ] 외부 입력 검증 누락 없음
- [ ] 인증/인가 우회 가능성 없음
- [ ] 민감 데이터 노출 위험 없음
- [ ] SQL Injection, XSS, Command Injection 취약점 없음
- [ ] 의존성 보안 취약점 없음

### V-3 성능 검토
- [ ] N+1 쿼리 또는 불필요 반복 호출 없음
- [ ] 대량 데이터 시 메모리/시간 복잡도 적절
- [ ] 캐싱 전략 적용 확인 (필요 시)
- [ ] 비동기 필요 작업의 블로킹 호출 없음
- [ ] Steady State 정량 기준 충족 (Constitution 정의 시)

### V-4 Spec 정합성 검증
- [ ] requirements.md 모든 EARS 항목 구현 확인
- [ ] Acceptance Criteria 충족
- [ ] `[NEEDS CLARIFICATION]` 항목이 합의 방향으로 구현
- [ ] design.md 인터페이스와 실제 구현 일치
- [ ] 엣지 케이스 커버

## 2. 심각도 분류

| 심각도 | 정의 | 판단 기준 | 처리 |
|--------|------|----------|------|
| **CRITICAL** | 즉시 수정. Gate 통과 불가 | Constitution 위반, 보안 취약점, 데이터 유실, 핵심 미작동 | Phase 3 회귀 |
| **MAJOR** | 수정 후 재검증 | 요구사항 미충족, 커버리지 미달, 아키텍처 위반, 성능 미달 | Subagent 위임 |
| **MINOR** | 다음 Sprint 가능 | 코드 스타일, 네이밍, 문서 오타, 비필수 리팩터링 | 일괄 처리 |

**Pessimistic Consolidation**: V-1~V-4 간 심각도 상충 시 최상위 등급 적용 (안전 우선).
**Reasoning Merge**: 등급은 상위, 상충 Validator 근거 모두 병합하여 이슈 상세에 기재.
**Lead Override**: 오탐 판단 시 등급 하향 가능. 단, '등급 조정 사유(Overriding Rationale)' 필수 추가.

## 3. verify-report.md 포맷

```markdown
# 검증 리포트: [기능/PR명]

**검증일**: YYYY-MM-DD
**검증 대상**: PR #[번호] — [제목]
**검증 관점**: V-1 정확성 / V-2 보안 / V-3 성능 / V-4 Spec 정합성

## 이슈 요약

| 이슈 # | 심각도 | 관점 | 위치 | 한 줄 설명 |
|--------|--------|------|------|-----------|

**집계**: CRITICAL N건 / MAJOR N건 / MINOR N건

## Phase Gate 판정
- [ ] CRITICAL 0건 → Phase 5 진입 가능 (Epic)
- [ ] CRITICAL + MAJOR 0건 → PR Merge 가능 (Feature)
- [ ] CRITICAL 존재 → Phase 3 회귀 필요

**판정**: ✅ 통과 / ❌ 차단 — [이유]

## 이슈 상세
### 이슈 #N
- **심각도**: CRITICAL | MAJOR | MINOR
- **관점**: V-N
- **위치**: `파일:라인`
- **내용**: [설명]
- **제안**: [수정 방향]

## Spec↔Code 동기화 확인
- [ ] 구현이 design.md 인터페이스 정의와 일치
- [ ] 새 함수/클래스/API가 design.md에 반영
- [ ] tasks.md 완료 마커가 실제 구현과 일치
- [ ] 모든 EARS 요구사항이 구현과 1:1 추적 가능
```

## 4. P4/P5 프롬프트 템플릿

### 4-1. 교차 검증 (Lead → Reviewer Agents)

```
역할: Phase 4(VERIFY) [V-1 정확성 | V-2 보안 | V-3 성능 | V-4 Spec 정합성] Agent
검증 대상: [PR diff / 변경 파일 목록]
주입: @CLAUDE.md, @requirements.md, @design.md

§1 체크리스트의 해당 관점 항목을 검증.
이슈 보고 형식:
  이슈 #N — 심각도: [등급] / 위치: [파일:라인] / 내용: [설명] / 제안: [수정안]
```

### 4-2. verify-report 작성 (Lead)

```
역할: Phase 4(VERIFY) Lead Agent
작업: 4-1 검증 결과를 §3 포맷으로 docs/verify-report-YYYYMMDD.md 작성.
심각도 상충 시 §2 Pessimistic Consolidation 적용.
```

### 5-1. 심각도별 수정 라우팅 (Phase 5 Lead)

```
역할: Phase 5(REFINE) Lead Agent
주입: Phase 4 검증 리포트 이슈 목록

MAJOR: 독립 Subagent 할당 → 수정 후 Phase 4 해당 항목 재검증
MINOR: 동일 파일 일괄 처리 → lint/format 자동 실행
Spec↔Code: 코드를 Spec에 맞게 수정 (Spec 후퇴 금지)

모든 MAJOR 수정 후 전체 테스트 suite 재실행.
```

## 5. Spec↔Code Drift Protocol

**원칙**: 코드를 Spec에 맞게 수정한다. Spec을 코드에 맞추는 방향(Spec 후퇴)은 금지.

**감지**: `git diff HEAD -- docs/design.md docs/requirements.md`
(Spec 파일 변경 여부 확인. 코드↔Spec 드리프트 실질 판단은 테스트 + 수동 리뷰로.)

**처리**:
- CRITICAL drift (인터페이스 파괴) → Phase 2 재시작 (Human 개입)
- 의도적 설계 변경 → Phase 5에서 요구사항 변경 절차 후 Spec 갱신

## 6. Phase 4→5/완료 조건 요약

| 트랙 | 완료 조건 |
|------|----------|
| **Hotfix** | 4-Auto 전체 테스트 통과 + Lint/Type check |
| **Feature** | 검증 리포트 완성 + CRITICAL 0건 + PR Human Approve |
| **Epic P4→5** | 검증 리포트 + CRITICAL 0건 + Spec↔Code 검증 |
| **Epic P5→완료** | CRITICAL/MAJOR 전체 수정 + Spec 동기화 + Human 승인 |
