# Project Brief: llm-serving-observability

## 목적

LLM 서빙의 관측 가능성(Observability) 구축을 학습하고 포트폴리오로 증명한다.

기존 인프라 경험(K8s, Prometheus, Grafana, ArgoCD)은 이미 보유.
이 레포에서 증명할 것은 **LLM 서빙 특화 메트릭 설계 + 대시보드 구현** 역량이다.

## 핵심 증명 대상

| 항목 | 내용 |
|------|------|
| LLM 메트릭 이해 | TTFT, TPS, 레이턴시 분포 등 LLM 서빙 고유 지표 |
| 계측 설계 | OpenAI 호환 프록시에 Prometheus 메트릭 삽입 |
| 대시보드 설계 | Grafana로 LLM 서빙 운영 대시보드 구성 |
| 부하 테스트 | 동시 요청 증가에 따른 성능 변화 측정 및 시각화 |

## 기술 스택

- **LLM 서빙**: Ollama (Apple Silicon Metal 가속)
- **프록시**: FastAPI + prometheus_client
- **모니터링**: Prometheus + Grafana
- **부하 테스트**: Python asyncio + httpx
- **인프라**: Docker Compose (로컬 $0)
- **기본 모델**: qwen2.5:7b

## 범위 밖 (YAGNI)

- K8s 배포, ArgoCD GitOps (기존 경험으로 충분)
- LangSmith, RAGAS (별도 프로젝트에서 경험)
- Fine-tuning, 인증/보안, AlertManager
- 다중 모델 동시 서빙 (24GB RAM 제약)

## 참조

- 설계 문서: `docs/plans/2026-03-14-llm-serving-observability.md`
- 기술 조사: `docs/findings/2026-03-14-research-findings.md`
