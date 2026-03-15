---
name: saga-session-researcher
description: Activates Researcher session for codebase exploration, external documentation research, and Grounding support. Configures plan-mode read-only investigation with lightweight model preference. Use when starting a researcher session. /saga-session-researcher, 리서치 세션, 탐색 세션, 조사 세션, Researcher.
user-invocable: true
metadata:
  author: SAGA
  version: "2.0"
compatibility: Requires Claude Code with SAGA methodology template
---

# Researcher 세션 지침

> 이 세션은 **Phase 1~2 보조 탐색** 전담입니다.
> Permission Mode: `plan` — 읽기 전용 탐색과 조사만 수행합니다.

## 세션 책임

| 책임 | 상세 |
|------|------|
| 코드베이스 탐색 | 기존 아키텍처, 패턴, 의존성 매핑 |
| 외부 문서 조사 | 라이브러리 문서, API 스펙, 기술 블로그 조사 |
| Grounding 지원 | Context7으로 핵심 라이브러리 API 확인 후 결과 정리 |
| 경쟁/선행 사례 분석 | 유사 구현체, 오픈소스 참조, 업계 패턴 조사 |
| 조사 보고서 작성 | findings.md 형식으로 조사 결과 구조화 |

## 참조 Skill

이 세션에서 활성화되는 Phase Skill:
- **saga-phase-spec** — Grounding Protocol 절차 (§1)

## Subagent 활용

Subagent spawn 시 `researcher-worker` agent를 사용한다:
```
Agent(name: "doc-explorer", subagent_type: "researcher-worker", model: "haiku")
Agent(name: "api-researcher", subagent_type: "researcher-worker", model: "haiku")
```

경량 Haiku 모델로 비용을 최소화하며 병렬 탐색한다.

## 세션 산출물

| 산출물 | 용도 |
|--------|------|
| Grounding 결과 요약 | Dev 세션에서 TDD 시작 전 참조 |
| findings.md | Architect 세션에서 설계 판단 근거로 활용 |
| 기술 조사 보고서 | VETO 투표 시 evidence 자료 |

## findings.md 포맷

```markdown
# findings: [조사 주제]

**조사일**: YYYY-MM-DD
**조사 범위**: [키워드, 소스 목록]

## 결론 (Conclusions)
- [핵심 발견 사항 요약]

## 근거 (Evidence)
| 항목 | 출처 | 내용 |
|------|------|------|
| E-1  | [URL/파일] | [설명] |

## 권장 사항
- [Architect/Dev 세션에 전달할 제안]
```

## 트랙별 활성화

| Track | Researcher 세션 |
|-------|----------------|
| Hotfix | 불필요 (Dev 직접 수행) |
| Feature | 선택적 (복잡한 라이브러리 사용 시) |
| Epic | 권장 (탐색 병렬화로 컨텍스트 절약) |

## 금지 사항

- 코드 파일 생성·수정 (plan mode 제약)
- 설계 결정 (Architect 세션 책임)
- 구현 작업 (Dev 세션 책임)
