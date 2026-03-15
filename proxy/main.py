"""LLM Proxy — FastAPI proxy for Ollama with Prometheus instrumentation."""

import asyncio
import json
import logging
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from config import (
    DEFAULT_MODEL,
    LOG_LEVEL,
    MAX_CONCURRENT_REQUESTS,
    OLLAMA_BASE_URL,
)
from metrics import (
    ACTIVE_REQUESTS,
    INPUT_TOKENS,
    MODEL_LOADED,
    OUTPUT_TOKENS,
    QUEUE_DEPTH,
    REQUEST_DURATION,
    REQUEST_ERRORS,
    REQUESTS_TOTAL,
    TIME_PER_OUTPUT_TOKEN,
    TOKENS_PER_SECOND,
    TTFT,
)

logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("llm-proxy")

app = FastAPI(title="LLM Proxy", version="0.1.0")

# Concurrency control
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
_queue_waiters = 0
_queue_lock = asyncio.Lock()

# httpx client with no read timeout (LLM responses can take 30-120s)
_http_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=OLLAMA_BASE_URL,
            timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0),
        )
    return _http_client


@app.on_event("shutdown")
async def shutdown():
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    try:
        client = await get_client()
        resp = await client.get("/", timeout=5.0)
        if resp.status_code == 200:
            return {"status": "ok", "ollama": "connected"}
    except Exception:
        pass
    return JSONResponse(
        status_code=503,
        content={"status": "error", "ollama": "disconnected"},
    )


@app.get("/metrics")
async def metrics():
    return StreamingResponse(
        iter([generate_latest()]),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", DEFAULT_MODEL)
    stream = body.get("stream", True)

    # Ensure stream_options.include_usage for streaming
    if stream:
        stream_options = body.get("stream_options", {})
        stream_options["include_usage"] = True
        body["stream_options"] = stream_options

    # Queue tracking
    global _queue_waiters
    async with _queue_lock:
        _queue_waiters += 1
        QUEUE_DEPTH.set(_queue_waiters)

    try:
        await _semaphore.acquire()
    finally:
        async with _queue_lock:
            _queue_waiters -= 1
            QUEUE_DEPTH.set(_queue_waiters)

    ACTIVE_REQUESTS.inc()
    start = time.monotonic()

    try:
        if stream:
            return await _handle_streaming(body, model, start)
        else:
            return await _handle_non_streaming(body, model, start)
    except httpx.HTTPStatusError as exc:
        status_code = str(exc.response.status_code)
        REQUEST_ERRORS.labels(model=model, status_code=status_code).inc()
        REQUESTS_TOTAL.labels(model=model, status="error", stream=str(stream).lower()).inc()
        raise
    except Exception:
        REQUEST_ERRORS.labels(model=model, status_code="502").inc()
        REQUESTS_TOTAL.labels(model=model, status="error", stream=str(stream).lower()).inc()
        return JSONResponse(
            status_code=502,
            content={"error": "Failed to connect to Ollama"},
        )
    finally:
        ACTIVE_REQUESTS.dec()
        _semaphore.release()


# ---------------------------------------------------------------------------
# Streaming handler
# ---------------------------------------------------------------------------


async def _handle_streaming(body: dict, model: str, start: float):
    client = await get_client()

    async def event_generator():
        first_token_seen = False
        output_tokens = 0

        async with client.stream(
            "POST", "/v1/chat/completions", json=body
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    if line.strip():
                        yield line + "\n\n"
                    continue

                data_str = line[6:]
                yield f"data: {data_str}\n\n"

                if data_str.strip() == "[DONE]":
                    continue

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # TTFT: first chunk with content
                if not first_token_seen:
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        if delta.get("content"):
                            ttft_val = time.monotonic() - start
                            TTFT.labels(model=model).observe(ttft_val)
                            first_token_seen = True

                # Usage info (final chunk)
                usage = chunk.get("usage")
                if usage:
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    output_tokens = completion_tokens

                    INPUT_TOKENS.labels(model=model).inc(prompt_tokens)
                    OUTPUT_TOKENS.labels(model=model).inc(completion_tokens)

        # Record duration and throughput metrics
        duration = time.monotonic() - start
        REQUEST_DURATION.labels(model=model).observe(duration)

        if output_tokens > 0:
            tps = output_tokens / duration
            TOKENS_PER_SECOND.labels(model=model).observe(tps)
            tpot = duration / output_tokens
            TIME_PER_OUTPUT_TOKEN.labels(model=model).observe(tpot)

        REQUESTS_TOTAL.labels(
            model=model, status="success", stream="true"
        ).inc()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Non-streaming handler
# ---------------------------------------------------------------------------


async def _handle_non_streaming(body: dict, model: str, start: float):
    client = await get_client()
    resp = await client.post("/v1/chat/completions", json=body)
    resp.raise_for_status()

    data = resp.json()
    duration = time.monotonic() - start

    REQUEST_DURATION.labels(model=model).observe(duration)

    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    INPUT_TOKENS.labels(model=model).inc(prompt_tokens)
    OUTPUT_TOKENS.labels(model=model).inc(completion_tokens)

    if completion_tokens > 0:
        tps = completion_tokens / duration
        TOKENS_PER_SECOND.labels(model=model).observe(tps)
        tpot = duration / completion_tokens
        TIME_PER_OUTPUT_TOKEN.labels(model=model).observe(tpot)

    REQUESTS_TOTAL.labels(
        model=model, status="success", stream="false"
    ).inc()

    return JSONResponse(content=data)


# ---------------------------------------------------------------------------
# Background: Model status polling
# ---------------------------------------------------------------------------


async def _poll_model_status():
    """Periodically check Ollama for loaded models and update M11 gauge."""
    while True:
        try:
            client = await get_client()
            resp = await client.get("/api/ps", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                # Reset all model_loaded to 0, then set loaded ones to 1
                # prometheus_client doesn't support clearing label sets,
                # so we track known models
                models = data.get("models", [])
                for m in models:
                    name = m.get("name", "unknown")
                    details = m.get("details", {})
                    quant = details.get("quantization_level", "unknown")
                    MODEL_LOADED.labels(model=name, quantization=quant).set(1)
        except Exception:
            pass
        await asyncio.sleep(30)


@app.on_event("startup")
async def startup():
    asyncio.create_task(_poll_model_status())
