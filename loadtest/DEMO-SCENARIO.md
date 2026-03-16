# Grafana 대시보드 검증 시나리오

> 목적: 10개 패널 전체에 데이터를 채워서 대시보드 동작을 검증한다.
> 프록시 URL: `http://localhost:8000` (기본값)
> MAX_CONCURRENT_REQUESTS: 4
> 모델: qwen2.5:7b (사전 pull 완료 상태)

---

## 실행 환경별 성능 차이

Ollama 실행 방식에 따라 성능 차이가 크다. 시나리오 소요 시간은 아래 표를 참고한다.

| 항목 | Docker Ollama (CPU) | Native Ollama (Metal GPU) |
|------|-------------------|--------------------------|
| TPS (tok/s) | ~4-5 | ~20-45 |
| S1 소요 시간 | ~6분 | ~2-3분 |
| S2 소요 시간 | ~30분 | ~5-10분 |
| S3 소요 시간 | ~60분+ | ~15-20분 |
| OLLAMA_BASE_URL | `http://ollama:11434` (기본) | `http://host.docker.internal:11434` |

**권장**: 성능 측정이 목적이면 Native Ollama(Metal GPU)를 사용한다. 기능 검증만 필요하면 Docker Ollama(CPU)도 가능하나, S2 이후 시나리오는 시간이 매우 오래 걸린다.

Native Ollama 전환 방법:
```bash
# 1. 호스트에서 Ollama 실행 확인
ollama list  # qwen2.5:7b 확인

# 2. .env 수정
echo "OLLAMA_BASE_URL=http://host.docker.internal:11434" >> .env

# 3. proxy 재시작
docker compose restart proxy
```

---

## 사전 준비

```bash
cd loadtest
pip install -r requirements.txt  # httpx
mkdir -p docs/screenshots        # 스크린샷 저장 디렉토리
```

포트 충돌 시 `.env` 파일로 오버라이드:
```bash
# (선택) 기본 포트가 사용 중이면 프로젝트 루트에 .env 생성
echo "PROXY_PORT=8002" >> .env
echo "GRAFANA_PORT=3001" >> .env
echo "PROMETHEUS_PORT=9091" >> .env
docker compose up -d
```

포트를 변경했으면 이후 모든 명령에서 `--base-url`을 맞춰야 한다:
```bash
# 기본 포트 사용 시
python run.py --scenario s1 --base-url http://localhost:8000

# PROXY_PORT=8002 사용 시
python run.py --scenario s1 --base-url http://localhost:8002
```

현재 포트 확인:
```bash
docker compose ps --format "table {{.Service}}\t{{.Ports}}"
```

Grafana 열기: http://localhost:3000 (또는 `$GRAFANA_PORT`) → LLM → LLM Serving Overview → 시간 범위 **Last 15 minutes**

> **시간 범위 참고**: Docker CPU 환경은 시나리오 실행이 오래 걸리므로 **Last 45 minutes** ~ **Last 1 hour**로 설정해야 전체 데이터가 보인다. Native Metal GPU는 **Last 15 minutes**로 충분하다.

---

## Step 1: Error Rate 패널 데이터 생성 (30초)

존재하지 않는 모델로 요청하여 에러를 발생시킨다. stream=false / stream=true 양쪽 모두 테스트한다.

```bash
# 에러 요청 — non-streaming 2건
for i in 1 2; do
  curl -s http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"nonexistent-model","messages":[{"role":"user","content":"test"}],"stream":false}'
  echo ""
done

# 에러 요청 — streaming 1건
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"nonexistent-model","messages":[{"role":"user","content":"test"}],"stream":true}'
echo ""
```

**확인 패널**: Error Rate % → 값 표시

---

## Step 2: Baseline — Request Rate + 기본 메트릭 (Native ~2분 / Docker CPU ~6분)

```bash
python run.py --scenario s1 --base-url http://localhost:8000
```

- 동시 1, 5건, 짧은 프롬프트
- Grafana 새로고침 간격 30초 대기

**참고 결과 (Docker CPU, qwen2.5:7b)**:
```
Requests: 5 | Errors: 0 | Wall time: 342.0s

Metric                     Avg       P50       P95       P99
-------------------------------------------------------------
TTFT (s)                 2.338     1.072     7.644     7.644
Duration (s)            68.388    71.906   104.157   104.157
TPS (tok/s)                4.4       4.5       5.8       5.8
Output Tokens            280.0     301.0     521.0     521.0
```

**확인 패널**:
- Request Rate → 0 이상
- Request Duration P50/P95/P99 → 그래프 표시
- TTFT P50/P95/P99 → 그래프 표시
- Tokens Per Second → 그래프 표시
- TPOT → 그래프 표시
- Input vs Output Tokens Rate → 그래프 표시
- Model Info → qwen2.5:7b, Q4_K_M 표시

### Screenshot 캡처 — Baseline (Shot 1)

Step 2 완료 후 Grafana 대시보드를 캡처한다. 모든 기본 메트릭 패널에 데이터가 표시된 상태이다.

1. Grafana에서 시간 범위를 조정하여 S1 데이터가 모두 보이는지 확인
2. 브라우저 전체 화면 또는 대시보드 영역 스크린샷 캡처
3. 저장: `docs/screenshots/grafana-dashboard-baseline.png`

> Docker CPU 환경에서는 S1만으로도 기본 메트릭 검증이 충분하다. S2 이후를 실행하지 않을 경우 이 스크린샷을 `docs/screenshots/grafana-dashboard.png`로도 복사하여 README 참조를 충족한다.

---

## Step 3: Concurrency Sweep — Active Requests + Queue Depth (Native ~5분 / Docker CPU ~30분)

```bash
python run.py --scenario s2 --base-url http://localhost:8000
```

- 동시 1 → 2 → 4 → 8 → 16 단계별 실행
- 동시 5+ 에서 Queue Depth 상승 (MAX_CONCURRENT_REQUESTS=4 초과)
- 동시 8, 16에서 Active Requests=4 + Queue Depth 변화 관측

**확인 패널**:
- Active Requests → 단계별 1 → 2 → 4 → 4(상한) 변화
- Queue Depth → 동시 8에서 ~4, 동시 16에서 ~12 대기

### Screenshot 캡처 — Peak Load (Shot 2)

Step 3의 concurrency=8 단계 실행 중 또는 직후에 캡처한다. Active Requests가 상한(4)에 도달하고 Queue Depth가 상승한 상태가 가장 적합하다.

1. S2 실행 중 concurrency=8 단계가 진행되는 동안 Grafana 확인
2. Active Requests=4, Queue Depth>0 이 보이는 시점에서 스크린샷 캡처
3. 저장: **`docs/screenshots/grafana-dashboard.png`** (README.md 참조 파일명)

> 이 스크린샷이 README.md의 `![Grafana LLM Serving Overview](docs/screenshots/grafana-dashboard.png)` 에 사용된다. 10개 패널 전체에 데이터가 채워진 Peak Load 상태가 프로젝트 대표 이미지로 가장 적합하다.

---

## Step 4: Sustained Load — 장시간 부하 안정성 (Native ~15분 / Docker CPU ~60분+)

```bash
python run.py --scenario s3 --base-url http://localhost:8000
```

- 동시 4, 20건, 혼합 프롬프트 (short/medium/long)
- 장시간 부하에서 레이턴시 분포 안정성 확인

**확인 패널**:
- Request Duration → P50과 P99 간격이 넓어짐 (프롬프트 길이 차이)
- TTFT → long 프롬프트에서 TTFT 증가 관측
- Tokens Per Second → 부하 중 TPS 변화 추이

---

## Step 5 (Optional): Model Comparison — $model 템플릿 변수 검증 (10~15분)

2번째 모델을 pull하고 S5를 실행하여 `$model` 드롭다운 필터링이 동작하는지 검증한다.

> `--model`은 단일 값 인수이므로, S5의 멀티모델 비교는 `--model` 없이 실행해야 한다.
> `--model` 생략 시 scenarios.py 기본값(`qwen2.5:7b`, `qwen2.5:14b`)이 순차 실행된다.

```bash
# 2번째 모델 pull (S5 기본값: qwen2.5:14b)
ollama pull qwen2.5:14b
# 또는 Docker 사용 시:
# docker compose exec ollama ollama pull qwen2.5:14b

# --model 생략 → 두 모델(qwen2.5:7b, qwen2.5:14b) 순차 비교
python run.py --scenario s5 --base-url http://localhost:8000
```

**확인 패널**:
- Model Info → 두 모델 표시 (qwen2.5:7b, qwen2.5:14b)
- Grafana 상단 `$model` 드롭다운 → 모델별 필터링 동작
- Tokens Per Second → 모델별 TPS 차이 시각화

### Screenshot 캡처 — Model Comparison (Shot 3, Optional)

Step 5 완료 후 `$model` 드롭다운에서 두 모델이 모두 보이는 상태를 캡처한다.

1. Grafana `$model` 드롭다운에서 `All` 선택
2. Tokens Per Second 패널에서 두 모델의 TPS 차이가 보이는 시점 확인
3. 저장: `docs/screenshots/grafana-dashboard-model-comparison.png`

---

## 전체 실행 (Step 1~4 연속)

시간이 제한적이면 아래 한 줄로 전체 실행:

```bash
# Step 1: 에러 생성 (non-streaming only)
for i in 1 2; do
  curl -s http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"nonexistent-model","messages":[{"role":"user","content":"test"}],"stream":false}'
done

# Step 2~3: S1 → S2 연속 실행
python run.py --scenario s1 --base-url http://localhost:8000 && \
python run.py --scenario s2 --base-url http://localhost:8000
```

S3은 20건 혼합 프롬프트(short/medium/long)로 시간이 오래 걸리므로 선택 실행.

---

## 검증 체크리스트

| # | 패널 | Step | 기대값 |
|---|------|------|--------|
| 1 | Request Rate | Step 2+ | > 0 req/s |
| 2 | Error Rate % | Step 1 | > 0% |
| 3 | Active Requests | Step 3 | 단계별 변화 (1→2→4→4 상한) |
| 4 | Queue Depth | Step 3 | 동시 8+에서 > 0 |
| 5 | Request Duration | Step 2+ | P50/P95/P99 그래프 |
| 6 | TTFT | Step 2+ | P50/P95/P99 그래프 |
| 7 | Tokens Per Second | Step 2+ | TPS 그래프 |
| 8 | TPOT | Step 2+ | TPOT 그래프 |
| 9 | Input vs Output Tokens | Step 2+ | 두 라인 (input/output) |
| 10 | Model Info | 항상 | qwen2.5:7b, Q4_K_M |
| 11 | $model 필터 | Step 5 | 두 모델(7b, 14b) 드롭다운 필터링 동작 |
| 12 | Screenshot Baseline | Step 2 후 | `docs/screenshots/grafana-dashboard-baseline.png` 존재 |
| 13 | Screenshot Peak Load | Step 3 후 | `docs/screenshots/grafana-dashboard.png` 존재 (README 참조) |

---

## Known Issues

### 1. Docker CPU 환경에서 낮은 TPS

**현상**: Docker Ollama(CPU only)에서 TPS ~4-5 tok/s로 Native Metal GPU 대비 5-10배 느리다. `OLLAMA_NUM_THREADS=6` 제한이 적용되어 있으므로, 스레드 무제한 환경과 TPS가 다를 수 있다.

**원인**: Docker 컨테이너는 macOS Metal GPU에 접근할 수 없어 CPU 전용 추론을 수행한다.

**영향**: S2 이후 시나리오 실행 시간이 크게 증가한다. 기능 검증에는 문제없으나 성능 벤치마크 목적이라면 Native Ollama를 사용해야 한다.

### 2. KEEP_ALIVE=5m에 의한 Cold Start

**현상**: `OLLAMA_KEEP_ALIVE=5m` 설정으로 5분간 요청이 없으면 모델이 자동 언로드된다. 이후 첫 요청 시 모델을 재로드(cold start)하므로 TTFT가 수십 초까지 증가할 수 있다.

**대응**:
- 시나리오 실행 직전에 warm-up 요청 1건을 보내면 cold start를 회피할 수 있다:
  ```bash
  curl -s http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen2.5:7b","messages":[{"role":"user","content":"warmup"}],"stream":false}' > /dev/null
  ```
- S1 첫 요청의 TTFT가 비정상적으로 높으면 cold start가 원인일 가능성이 높다.
