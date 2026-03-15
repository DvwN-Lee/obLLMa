# Grafana 대시보드 검증 시나리오

> 목적: 10개 패널 전체에 데이터를 채워서 대시보드 동작을 검증한다.
> 프록시 URL: `http://localhost:8000` (기본값)
> MAX_CONCURRENT_REQUESTS: 4
> 모델: qwen2.5:7b (사전 pull 완료 상태)

---

## 사전 준비

```bash
cd loadtest
pip install -r requirements.txt  # httpx
```

포트 충돌 시 `.env` 파일로 오버라이드:
```bash
# (선택) 기본 포트가 사용 중이면 프로젝트 루트에 .env 생성
echo "PROXY_PORT=8002" >> .env
echo "GRAFANA_PORT=3001" >> .env
echo "PROMETHEUS_PORT=9091" >> .env
docker compose up -d
```

Grafana 열기: http://localhost:3000 → LLM → LLM Serving Overview → 시간 범위 **Last 15 minutes**

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

## Step 2: Baseline — Request Rate + 기본 메트릭 (2~3분)

```bash
python run.py --scenario s1 --base-url http://localhost:8000
```

- 동시 1, 5건, 짧은 프롬프트
- Grafana 새로고침 간격 30초 대기

**확인 패널**:
- Request Rate → 0 이상
- Request Duration P50/P95/P99 → 그래프 표시
- TTFT P50/P95/P99 → 그래프 표시
- Tokens Per Second → 그래프 표시
- TPOT → 그래프 표시
- Input vs Output Tokens Rate → 그래프 표시
- Model Info → qwen2.5:7b, Q4_K_M 표시

---

## Step 3: Concurrency Sweep — Active Requests + Queue Depth (5~10분)

```bash
python run.py --scenario s2 --base-url http://localhost:8000
```

- 동시 1 → 2 → 4 → 8 → 16 단계별 실행
- 동시 5+ 에서 Queue Depth 상승 (MAX_CONCURRENT_REQUESTS=4 초과)
- 동시 8, 16에서 Active Requests=4 + Queue Depth 변화 관측

**확인 패널**:
- Active Requests → 단계별 1 → 2 → 4 → 4(상한) 변화
- Queue Depth → 동시 8에서 ~4, 동시 16에서 ~12 대기

---

## Step 4: Sustained Load — 장시간 부하 안정성 (15~20분)

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

```bash
# 2번째 모델 pull (경량 모델 권장)
ollama pull qwen2.5:1.5b
# 또는 Docker 사용 시:
# docker compose exec ollama ollama pull qwen2.5:1.5b

python run.py --scenario s5 --base-url http://localhost:8000 --model qwen2.5:7b --model qwen2.5:1.5b
```

**확인 패널**:
- Model Info → 두 모델 표시 (qwen2.5:7b, qwen2.5:1.5b)
- Grafana 상단 `$model` 드롭다운 → 모델별 필터링 동작
- Tokens Per Second → 모델별 TPS 차이 시각화

---

## 전체 실행 (Step 1~4 연속)

시간이 제한적이면 아래 한 줄로 전체 실행:

```bash
# Step 1: 에러 생성 (non-streaming + streaming)
for i in 1 2; do
  curl -s http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"nonexistent-model","messages":[{"role":"user","content":"test"}],"stream":false}'
done
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"nonexistent-model","messages":[{"role":"user","content":"test"}],"stream":true}'

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
| 11 | $model 필터 | Step 5 | 드롭다운 선택 시 패널 필터링 |
