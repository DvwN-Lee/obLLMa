# {{PROJECT_NAME}} 개선사항 인덱스

> **상태**: 초기 구성
> **작성일**: {{DATE}}

---

## 개요

{{PROJECT_NAME}} 프로젝트의 개선사항을 우선순위별로 추적하는 로드맵 문서.

## 우선순위별 통합 로드맵

### P0: 즉시 (문서 + 최소 설정)

| # | 영역 | 조치 | 상태 |
|---|------|------|:----:|
| {{P0_1_ID}} | {{P0_1_AREA}} | {{P0_1_ACTION}} | - |
| {{P0_2_ID}} | {{P0_2_AREA}} | {{P0_2_ACTION}} | - |

### P1: 단기 (스크립트/코드)

| # | 영역 | 조치 | 관련 문서 |
|---|------|------|----------|
| {{P1_1_ID}} | {{P1_1_AREA}} | {{P1_1_ACTION}} | - |

### P2: 중기 (방법론 확장)

| # | 영역 | 조치 | 관련 문서 |
|---|------|------|----------|
| {{P2_1_ID}} | {{P2_1_AREA}} | {{P2_1_ACTION}} | - |

---

## 권한 정책 매트릭스

### 파일 작업 권한

| 작업 | 프로젝트 내부 (일반) | 프로젝트 내부 (보안 경계) | 프로젝트 내부 (민감 데이터) |
|------|:---:|:---:|:---:|
| **CREATE** | Allow | Human | Human |
| **EDIT** | Allow | Human | Human |
| **DELETE** | Human | Human | Human |
| **READ** | Allow | Allow | Deny |

**보안 경계 파일**: `.claude/settings.json`, `.claude/hooks/*`, `CLAUDE.md`
**민감 데이터 파일**: `.env*`, `*credentials*`, `*secrets*`, `*.pem`, `*.key`

### 민감 데이터 파일 접근 정책

`.env` 파일은 **Deny**하되, `.env.example`만 Read/Edit **Allow**:

```
.env            → Deny (Read/Edit/Create 모두 차단)
.env.*          → Deny (실제 값 파일)
.env.example    → Allow (Read + Edit 허용)
```
