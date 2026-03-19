# Grafana 대시보드 검증 시나리오

| 항목 | 값 |
|------|-----|
| **목적** | 10개 패널 전체에 데이터를 채워서 대시보드 동작을 검증한다 |
| **프록시 URL** | `http://localhost:8000` (기본값) |
| **MAX_CONCURRENT_REQUESTS** | 4 |
| **모델** | qwen2.5:7b (사전 pull 완료 상태) |
| **예상 소요** | ~18-22분 (Native Metal GPU, 검증 포함) |

---

## 실행 전략

**일괄 검증 방식**: 시나리오를 연속 실행한 뒤, 마지막에 Grafana에서 일괄 검증한다. 단, Screenshot 2(Peak Load)만 S2 concurrency=8 실행 **도중에** 실시간 캡처한다.

**근거**: Counter/Histogram 기반 패널(#1,2,5,6,7,8,9)은 Prometheus에 데이터가 누적되므로 사후 검증 가능. Gauge 패널(#3 Active Requests, #4 Queue Depth)은 부하 중에만 >0이므로 실시간 캡처 필수.

```
[환경 준비] → [Error 요청] → [Warm-up] → [S1] → [S2 + Screenshot 2] → [S3] → [일괄 검증 + Screenshot 1]
   2분          30초          10-60초     1분      3분 (실시간 캡처)     5분          5분
```

---

## 사전 준비 (~2분)

### 1. Native Ollama 설치 및 모델 확인

Native Ollama(Metal GPU)를 사용하여 TPS ~20-45로 실행한다.

```bash
# Ollama 설치 확인 (미설치 시 https://ollama.com 에서 다운로드)
ollama list

# qwen2.5:7b 없으면 pull
ollama pull qwen2.5:7b
```

### 2. Docker 스택 기동

```bash
# .env에 Native Ollama URL 설정 (이미 .env가 있으면 해당 라인을 직접 수정)
echo "OLLAMA_BASE_URL=http://host.docker.internal:11434" > .env

docker compose up -d
docker compose ps --format "table {{.Service}}\t{{.Ports}}"
```

포트 충돌 시 `.env`로 세 포트 모두 오버라이드:
```bash
cat > .env << 'EOF'
OLLAMA_BASE_URL=http://host.docker.internal:11434
PROXY_PORT=8002
GRAFANA_PORT=3001
PROMETHEUS_PORT=9091
EOF
docker compose up -d
```

### 3. 의존성 및 디렉토리

```bash
cd loadtest
pip install -r requirements.txt  # httpx
mkdir -p ../docs/screenshots     # 스크린샷 저장 디렉토리
```

### 4. Grafana 준비

```bash
# 헬스체크
curl -s http://localhost:3000/api/health
# 기대: {"commit":"...","database":"ok","version":"..."}
```

Grafana 열기: http://localhost:3000 → LLM → LLM Serving Overview
- 시간 범위: **Last 15 minutes**
- **Auto-refresh: 5s** 로 설정 (S2 실시간 캡처를 위해)

---

## 연속 실행 (~10분)

아래 명령을 순서대로 실행한다. **S2 concurrency=8 시점에만 Grafana로 전환**하여 Screenshot 2를 캡처한다.

### Step 1: Error Rate 데이터 생성 (30초)

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

### Step 2: Warm-up + S1 Baseline (~1분)

```bash
# Warm-up (KEEP_ALIVE=5m cold start 회피, 10-60초)
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5:7b","messages":[{"role":"user","content":"warmup"}],"stream":false}' > /dev/null

# S1: 동시 1, 5건, 짧은 프롬프트
python run.py --scenario s1 --base-url http://localhost:8000
```

### Step 3: S2 Concurrency Sweep + Screenshot 2 (~3분)

```bash
python run.py --scenario s2 --base-url http://localhost:8000
```

- 동시 1 → 2 → 4 → 8 → 16 단계별 실행
- **concurrency=8 도달 시**: 터미널에 `concurrency=4` 결과 출력 후 다음 레벨 시작

**Screenshot 2 캡처 (실시간 필수):**

1. 터미널에서 `=== Scenario: S2 Concurrency Sweep | concurrency=4 ===` 결과가 출력되면 → 다음 레벨(concurrency=8) 시작 신호
2. 즉시 Grafana 탭으로 전환
3. Active Requests=4 (MAX_CONCURRENT_REQUESTS 상한), Queue Depth>0 확인 즉시 캡처
4. 저장: **`docs/screenshots/grafana-dashboard.png`** (README.md 참조 파일명)

> **캡처 윈도우**: Native GPU에서 ~20-30초. Prometheus scrape_interval=15s이므로 peak 값이 1-2회 스크래핑됨. `concurrency=4` 결과 출력 직후 전환하면 충분.

### Step 4: S3 Sustained Load (~5분)

```bash
# S2 → S3 사이 5분 경과 가능하므로 warm-up 재실행
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5:7b","messages":[{"role":"user","content":"warmup"}],"stream":false}' > /dev/null

# S3: 동시 4, 20건, 혼합 프롬프트 (short/medium/long)
python run.py --scenario s3 --base-url http://localhost:8000
```

### Quick Run (Step 1~4 한 줄 실행)

Screenshot 2 캡처가 불필요하거나 이미 확보된 경우:

```bash
# Error 생성
for i in 1 2; do
  curl -s http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"nonexistent-model","messages":[{"role":"user","content":"test"}],"stream":false}'
done
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"nonexistent-model","messages":[{"role":"user","content":"test"}],"stream":true}'

# Warm-up + S1 + S2 + S3 연속
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5:7b","messages":[{"role":"user","content":"warmup"}],"stream":false}' > /dev/null && \
python run.py --scenario s1 --base-url http://localhost:8000 && \
python run.py --scenario s2 --base-url http://localhost:8000 && \
python run.py --scenario s3 --base-url http://localhost:8000
```

---

## 일괄 검증 (~5분)

모든 시나리오 실행 완료 후 Grafana에서 일괄 검증한다.

### Error Rate 데이터 갱신

Step 1의 에러가 `rate([5m])` 윈도우 밖으로 벗어났으므로 에러 1건을 재주입한다:

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"nonexistent-model","messages":[{"role":"user","content":"test"}],"stream":false}' > /dev/null
```

### Screenshot 1 캡처 — Baseline

1. Grafana 시간 범위를 S1 실행 구간으로 조정
2. 모든 기본 메트릭 패널에 데이터가 표시된 상태 확인
3. 저장: `docs/screenshots/grafana-dashboard-baseline.png`

### 검증 체크리스트

| # | 패널 | 데이터 소스 | 기대값 |
|---|------|-----------|--------|
| 1 | Request Rate | S1+ (Counter) | > 0 req/s |
| 2 | Error Rate % | Step 1 (Counter) | > 0% |
| 3 | Active Requests | S2 Screenshot 2 (Gauge) | 단계별 변화 (1→2→4→4 상한) |
| 4 | Queue Depth | S2 Screenshot 2 (Gauge) | 동시 8+에서 > 0 |
| 5 | Request Duration | S1+ (Histogram) | P50/P95/P99 그래프 |
| 6 | TTFT | S1+ (Histogram) | P50/P95/P99 그래프 |
| 7 | Tokens Per Second | S1+ (Histogram) | TPS 그래프 |
| 8 | TPOT | S1+ (Histogram) | TPOT 그래프 |
| 9 | Input vs Output Tokens | S1+ (Counter) | 두 라인 (input/output) |
| 10 | Model Info | 항상 (Gauge) | qwen2.5:7b, Q4_K_M |
| 11 | Screenshot Baseline | 일괄 검증 시 | `docs/screenshots/grafana-dashboard-baseline.png` 존재 |
| 12 | Screenshot Peak Load | S2 실시간 | `docs/screenshots/grafana-dashboard.png` 존재 (README 참조) |

> Gauge 패널(#3, #4)은 Screenshot 2에서 확인한다. 부하 완료 후에는 값이 0으로 돌아가므로 사후 검증 불가.

### 스크린샷 최종 확인

```bash
ls -la docs/screenshots/
# 필수 2장:
#   grafana-dashboard-baseline.png
#   grafana-dashboard.png (README 참조)
```

---

## Step 5 (Optional): Model Comparison (~10-15분)

2번째 모델을 pull하고 S5를 실행하여 `$model` 드롭다운 필터링이 동작하는지 검증한다.

```bash
# 2번째 모델 pull
ollama pull qwen2.5:14b

# --model 생략 → 두 모델(qwen2.5:7b, qwen2.5:14b) 순차 비교
python run.py --scenario s5 --base-url http://localhost:8000
```

**확인 패널**:
- Model Info → 두 모델 표시
- `$model` 드롭다운 → 모델별 필터링 동작
- Tokens Per Second → 모델별 TPS 차이 시각화

**Screenshot 3 (Optional):**
- `$model` → All 선택
- 저장: `docs/screenshots/grafana-dashboard-model-comparison.png`

---

## `--no-stream` 모드

모든 시나리오는 `--no-stream` 플래그로 non-streaming 모드 실행이 가능하다:

```bash
python run.py --scenario s1 --base-url http://localhost:8000 --no-stream
```

Non-streaming 모드에서는 TTFT가 측정되지 않는다. Duration, TPS, Output Tokens는 동일하게 측정된다.

---

## Docker CPU 환경 실행 시 참고

Native Ollama를 사용할 수 없는 경우 Docker Ollama(CPU)로도 실행 가능하나, 소요 시간이 크게 증가한다.

| 항목 | Native Metal GPU | Docker CPU |
|------|-----------------|-----------|
| TPS (tok/s) | ~20-45 | ~4-5 |
| S1 소요 | ~1분 | ~6분 |
| S2 소요 | ~3분 | ~30분 |
| S3 소요 | ~5분 | ~60분+ |
| 총 소요 (검증 포함) | ~18-22분 | ~2시간+ |
| OLLAMA_BASE_URL | `http://host.docker.internal:11434` | `http://ollama:11434` (기본) |
| Screenshot 캡처 윈도우 | ~20-30초 (타이트) | ~2분 (여유) |
| Grafana 시간 범위 | Last 15 minutes | Last 45 minutes ~ 1 hour |

Docker CPU 사용 시 추가 주의사항:
- S2 concurrency=16: ~10분+ 소요 가능 (16건 중 12건 큐 대기)
- Step 5 (14b): `docker-compose.yml`의 `memory: 10g` 제한으로 OOM 위험. 스킵 권장.

---

## 알려진 이슈

### 1. KEEP_ALIVE=5m에 의한 Cold Start

`OLLAMA_KEEP_ALIVE=5m` 설정으로 5분간 요청이 없으면 모델이 자동 언로드된다. 이후 첫 요청 시 모델을 재로드(cold start)하므로 TTFT가 수십 초까지 증가할 수 있다.

**대응**: 시나리오 실행 직전에 warm-up 요청 1건을 보내 cold start를 회피한다. 특히 S2 → S3 사이에 검증 시간이 5분을 초과하면 warm-up을 재실행해야 한다.

### 2. Gauge 패널의 실시간 캡처 제약

Active Requests(#3)와 Queue Depth(#4) 패널은 Gauge 타입으로, 부하가 종료되면 값이 0으로 돌아간다. 이 패널이 데이터를 보여주는 것을 확인하려면 **S2 concurrency=8 실행 도중에** Screenshot 2를 캡처해야 한다. Prometheus scrape_interval=15s이므로, Native GPU 환경에서는 캡처 윈도우가 ~20-30초로 짧다.
