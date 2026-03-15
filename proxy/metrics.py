"""LLM Serving Metrics — Single Source of Truth (Constitution #2)

All Prometheus metric definitions live here. Do not define metrics elsewhere.
"""

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# M1: E2E Request Duration
# ---------------------------------------------------------------------------
REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds",
    "End-to-end request processing time",
    ["model"],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120],
)

# ---------------------------------------------------------------------------
# M2: Time to First Token
# ---------------------------------------------------------------------------
TTFT = Histogram(
    "llm_ttft_seconds",
    "Time to first token (streaming only)",
    ["model"],
    buckets=[
        0.001, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08,
        0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0,
    ],
)

# ---------------------------------------------------------------------------
# M3: Tokens Per Second
# ---------------------------------------------------------------------------
TOKENS_PER_SECOND = Histogram(
    "llm_tokens_per_second",
    "Output token generation speed",
    ["model"],
    buckets=[1, 5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200, 300],
)

# ---------------------------------------------------------------------------
# M4: Time Per Output Token (TPOT)
# ---------------------------------------------------------------------------
TIME_PER_OUTPUT_TOKEN = Histogram(
    "llm_time_per_output_token_seconds",
    "Time per output token (duration / output_tokens)",
    ["model"],
    buckets=[0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.2, 0.5, 1.0],
)

# ---------------------------------------------------------------------------
# M5: Input Tokens Total
# ---------------------------------------------------------------------------
INPUT_TOKENS = Counter(
    "llm_input_tokens_total",
    "Cumulative input tokens processed",
    ["model"],
)

# ---------------------------------------------------------------------------
# M6: Output Tokens Total
# ---------------------------------------------------------------------------
OUTPUT_TOKENS = Counter(
    "llm_output_tokens_total",
    "Cumulative output tokens generated",
    ["model"],
)

# ---------------------------------------------------------------------------
# M7: Requests Total
# ---------------------------------------------------------------------------
REQUESTS_TOTAL = Counter(
    "llm_requests_total",
    "Total requests by model, status, and stream mode",
    ["model", "status", "stream"],
)

# ---------------------------------------------------------------------------
# M8: Request Errors Total
# ---------------------------------------------------------------------------
REQUEST_ERRORS = Counter(
    "llm_request_errors_total",
    "Error requests by model and HTTP status code",
    ["model", "status_code"],
)

# ---------------------------------------------------------------------------
# M9: Active Requests (Gauge)
# ---------------------------------------------------------------------------
ACTIVE_REQUESTS = Gauge(
    "llm_active_requests",
    "Currently processing requests (inside semaphore)",
)

# ---------------------------------------------------------------------------
# M10: Queue Depth (Gauge)
# ---------------------------------------------------------------------------
QUEUE_DEPTH = Gauge(
    "llm_queue_depth",
    "Requests waiting for semaphore",
)

# ---------------------------------------------------------------------------
# M11: Model Loaded (Gauge)
# ---------------------------------------------------------------------------
MODEL_LOADED = Gauge(
    "llm_model_loaded",
    "Loaded model info (1=loaded, 0=unloaded)",
    ["model", "quantization"],
)
