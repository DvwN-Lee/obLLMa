"""
scenarios.py — Load test scenario definitions for LLM Serving Observability.

Each scenario is a dict with:
  name         : str
  description  : str
  concurrency  : int | list[int]   (list = sweep, run each level sequentially)
  num_requests : int               (per concurrency level)
  prompts      : list[dict]        (OpenAI messages format, cycled across requests)
  model        : str | None        (None = use CLI default or proxy default)

For S5 (model comparison), an additional key is present:
  models       : list[str]         (each model is run sequentially at `concurrency`)
"""

from typing import Any

# ---------------------------------------------------------------------------
# Prompt pools
# ---------------------------------------------------------------------------

_SHORT_PROMPTS: list[list[dict]] = [
    [{"role": "user", "content": "What is TTFT in LLM serving?"}],
    [{"role": "user", "content": "Explain asyncio in one sentence."}],
    [{"role": "user", "content": "머신러닝과 딥러닝의 차이를 간단히 설명해줘."}],
    [{"role": "user", "content": "What does a Prometheus histogram measure?"}],
    [{"role": "user", "content": "FastAPI에서 StreamingResponse를 언제 사용하나요?"}],
]

_MEDIUM_PROMPTS: list[list[dict]] = [
    [
        {
            "role": "user",
            "content": (
                "Explain the concept of Time to First Token (TTFT) and why it matters "
                "for user experience in large language model serving systems. "
                "Include how it differs from end-to-end latency and total throughput."
            ),
        }
    ],
    [
        {
            "role": "user",
            "content": (
                "Prometheus와 Grafana를 함께 사용하는 관측 가능성(Observability) 스택에 대해 설명해줘. "
                "메트릭 수집, 저장, 시각화 각 단계에서 각 도구의 역할을 설명하고, "
                "LLM 서빙 시스템에서 특히 중요한 메트릭 종류는 무엇인지 알려줘."
            ),
        }
    ],
    [
        {
            "role": "user",
            "content": (
                "Describe the trade-offs between batching requests in an LLM inference server "
                "versus processing them one at a time. Consider throughput, latency, GPU utilization, "
                "and queue depth in your answer. Give a concrete example with numbers."
            ),
        }
    ],
    [
        {
            "role": "user",
            "content": (
                "Python의 asyncio 이벤트 루프와 스레드 기반 동시성의 차이를 설명해줘. "
                "I/O 바운드 작업과 CPU 바운드 작업 각각에서 어떤 방식이 유리한지, "
                "LLM 프록시 서버를 예시로 들어 설명해줘."
            ),
        }
    ],
]

_LONG_PROMPTS: list[list[dict]] = [
    [
        {
            "role": "user",
            "content": (
                "You are an expert in distributed systems and ML infrastructure. "
                "Please write a comprehensive technical guide on building a production-grade "
                "LLM serving observability system. Cover the following topics in detail:\n\n"
                "1. Key performance metrics for LLM serving: TTFT, TPS (tokens per second), "
                "TPOT (time per output token), E2E latency, queue depth, and active requests. "
                "Explain what each metric measures and why it matters.\n\n"
                "2. Prometheus metric types (Counter, Gauge, Histogram, Summary) and when to use "
                "each type for LLM metrics. Give specific examples for LLM workloads.\n\n"
                "3. Grafana dashboard design patterns for LLM serving: what panels to include, "
                "which PromQL queries to use, and how to set up template variables for "
                "multi-model comparison.\n\n"
                "4. Concurrency control strategies in async Python: asyncio.Semaphore vs "
                "thread pools, how to track queue depth, and how semaphore limits affect "
                "observed latency metrics.\n\n"
                "5. Load testing methodology for LLM APIs: how to design scenarios that reveal "
                "different bottlenecks, the importance of variable prompt lengths, and how to "
                "interpret the resulting performance distributions.\n\n"
                "Please be specific and include example code snippets where helpful."
            ),
        }
    ],
    [
        {
            "role": "user",
            "content": (
                "LLM 서빙 시스템의 성능 최적화에 대한 종합적인 가이드를 작성해줘. "
                "다음 주제들을 상세히 다뤄줘:\n\n"
                "1. 모델 양자화(Quantization)의 종류와 트레이드오프: Q4_K_M, Q8_0, FP16 등 "
                "각 포맷이 추론 속도, 메모리 사용량, 모델 품질에 미치는 영향을 비교해줘.\n\n"
                "2. KV 캐시 관리: KV 캐시가 무엇인지, 프리필(prefill)과 디코딩(decoding) 단계에서 "
                "어떻게 작동하는지, 그리고 메모리 제약 상황에서 어떻게 관리해야 하는지 설명해줘.\n\n"
                "3. 배치 처리 전략: 연속 배치(Continuous Batching) vs 정적 배치(Static Batching)의 "
                "차이, 각각의 장단점, 그리고 Ollama, vLLM, TGI 각 서빙 프레임워크의 접근 방식을 비교해줘.\n\n"
                "4. macOS에서의 Metal GPU 활용: Apple Silicon의 통합 메모리 아키텍처가 LLM 추론에 "
                "미치는 영향, Metal Performance Shaders(MPS)를 통한 가속, CPU 오프로딩 전략을 설명해줘.\n\n"
                "5. 관측 가능성 기반 성능 튜닝: Prometheus 메트릭을 분석해서 병목 구간을 찾고 "
                "최적화하는 방법론을 단계별로 설명해줘. 실제 메트릭 값과 해석 방법을 포함해줘."
            ),
        }
    ],
]

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "s1": {
        "name": "S1 Baseline",
        "description": (
            "Single concurrent request, short prompts. "
            "Establishes baseline latency without queuing effects."
        ),
        "concurrency": 1,
        "num_requests": 5,
        "prompts": _SHORT_PROMPTS,
        "model": None,
    },
    "s2": {
        "name": "S2 Concurrency Sweep",
        "description": (
            "Sweep concurrency levels [1, 2, 4, 8, 16] with short prompts, "
            "5 requests per level. Reveals how queue depth affects latency."
        ),
        "concurrency": [1, 2, 4, 8, 16],
        "num_requests": 5,
        "prompts": _SHORT_PROMPTS,
        "model": None,
    },
    "s3": {
        "name": "S3 Sustained Load",
        "description": (
            "Concurrency 4, 20 requests, mixed prompt lengths (short/medium/long). "
            "Tests steady-state throughput and latency stability over time."
        ),
        "concurrency": 4,
        "num_requests": 20,
        "prompts": _SHORT_PROMPTS[:2] + _MEDIUM_PROMPTS[:2] + _LONG_PROMPTS[:1],
        "model": None,
    },
    "s4": {
        "name": "S4 Variable Prompt Length",
        "description": (
            "Concurrency 4, 5 requests each at three prompt sizes: "
            "short (~50 tok), medium (~200 tok), long (~500 tok). "
            "Isolates the impact of input length on TTFT and TPS."
        ),
        "concurrency": 4,
        "num_requests": 5,
        # run.py will cycle through all three pools in separate sub-runs
        "prompts": {
            "short": _SHORT_PROMPTS,
            "medium": _MEDIUM_PROMPTS,
            "long": _LONG_PROMPTS,
        },
        "model": None,
    },
    "s-demo": {
        "name": "S-Demo Quick",
        "description": (
            "Concurrency 2, 6 requests, short prompts. "
            "Demo-friendly (~5min) scenario that demonstrates queuing effects."
        ),
        "concurrency": 2,
        "num_requests": 6,
        "prompts": _SHORT_PROMPTS,
        "model": None,
    },
    "s5": {
        "name": "S5 Model Comparison",
        "description": (
            "Concurrency 4, 5 requests, identical prompt, two models sequentially: "
            "qwen2.5:7b vs qwen2.5:14b. Enables direct performance comparison."
        ),
        "concurrency": 4,
        "num_requests": 5,
        "prompts": [
            [
                {
                    "role": "user",
                    "content": (
                        "Explain the key differences between transformer encoder and decoder "
                        "architectures, and describe how decoder-only models like GPT generate "
                        "text token by token using autoregressive decoding."
                    ),
                }
            ]
        ],
        "model": None,
        "models": ["qwen2.5:7b", "qwen2.5:14b"],
    },
}


def get_scenario(key: str) -> dict[str, Any]:
    """Return scenario dict by case-insensitive key (e.g. 's1', 'S1')."""
    normalized = key.lower()
    if normalized not in SCENARIOS:
        available = ", ".join(sorted(SCENARIOS.keys()))
        raise KeyError(f"Unknown scenario '{key}'. Available: {available}")
    return SCENARIOS[normalized]
