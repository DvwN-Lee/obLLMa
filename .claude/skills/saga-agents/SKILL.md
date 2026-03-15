---
name: saga-agents
description: Configures subagent composition, model tiering, and Worktree isolation for multi-agent workflows. Use when setting up agents, choosing between direct work and delegation, or configuring parallel execution. Subagent, 병렬 실행, Worktree, 모델 선택, 격리.
user-invocable: false
metadata:
  author: SAGA
  version: "2.0"
compatibility: Requires Claude Code with SAGA methodology template
---

# SAGA 에이전트 구성 지침

## 에이전트 선택 기준

| 상황 | 구성 |
|------|------|
| 단일 파일, 명확한 범위 | 직접 수행 |
| 독립적 병렬 작업 (Phase 2·3·5) | Subagent (`Agent` tool) |
| 다관점 토론·합의 필요 (Phase 1·4) | Agent Teams → `saga-veto` skill 참조 |

**동시 Subagent 한도: ≤3개.** 초과 시 큐에 등록, 완료 후 순차 실행.

## 모델 티어링

| 역할 | 모델 | 적용 |
|------|------|------|
| Lead (의사결정·아키텍처) | **Opus** | 복잡한 판단, 설계 |
| Worker/Subagent (실행) | **Sonnet** | 코드 생성, 문서 작성 |
| Hook Classifier (경량 판단) | **Haiku** | 명령 분류, 패턴 매칭 |

## Worktree 격리

Phase 3 BUILD에서 병렬 Subagent를 사용할 때 `isolation: "worktree"` 파라미터를 사용한다.

```python
Agent(
    subagent_type="general-purpose",
    isolation="worktree",    # 격리된 git worktree 생성
    prompt="..."
)
```

- 각 Subagent는 독립된 worktree에서 작업하여 충돌을 방지한다
- Lead는 모든 Subagent 완료 후 결과를 통합하고 worktree를 정리한다
- 비정상 종료 후 잔존 worktree: `git worktree list` 확인 → cherry-pick 후 `git worktree remove`

## findings.md 최소 포맷

```markdown
# findings: [팀명 / 검증 관점]

**생성일**: YYYY-MM-DD
**팀**: [Team명]

## 결론 (Conclusions)
- [핵심 발견 사항 요약]

## 근거 (Evidence)
| 항목 | 위치 | 내용 |
|------|------|------|
| E-1  | [파일:라인] | [설명] |

## 권장 조치
- [CRITICAL/MAJOR/MINOR]: [권장 사항]
```
