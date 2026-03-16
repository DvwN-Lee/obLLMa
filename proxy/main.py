"""LLM Proxy — FastAPI proxy for Ollama with Prometheus instrumentation."""

import asyncio
import json
import logging
import re
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
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

# Model name validation pattern (M-3)
_MODEL_NAME_RE = re.compile(r"^[a-zA-Z0-9.:_-]+$")


# ---------------------------------------------------------------------------
# MonitoredSemaphore (M-5: AC-002 item 8)
# ---------------------------------------------------------------------------


class MonitoredSemaphore:
    """Wraps asyncio.Semaphore with automatic Prometheus gauge tracking."""

    def __init__(self, max_concurrent: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_waiters = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            self._queue_waiters += 1
            QUEUE_DEPTH.set(self._queue_waiters)
        try:
            await self._semaphore.acquire()
        finally:
            async with self._lock:
                self._queue_waiters -= 1
                QUEUE_DEPTH.set(self._queue_waiters)
        ACTIVE_REQUESTS.inc()

    def release(self) -> None:
        ACTIVE_REQUESTS.dec()
        self._semaphore.release()


_semaphore = MonitoredSemaphore(MAX_CONCURRENT_REQUESTS)

# httpx client with no read timeout (LLM responses can take 30-120s)
_http_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=OLLAMA_BASE_URL,
            timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0),
            limits=httpx.Limits(
                max_connections=MAX_CONCURRENT_REQUESTS * 2,
                max_keepalive_connections=MAX_CONCURRENT_REQUESTS,
            ),
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
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", DEFAULT_MODEL)
    stream = bool(body.get("stream", True))

    # M-3: model name validation
    if not _MODEL_NAME_RE.match(model):
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid model name: {model}"},
        )

    # Ensure stream_options.include_usage for streaming
    if stream:
        stream_options = body.get("stream_options", {})
        stream_options["include_usage"] = True
        body["stream_options"] = stream_options

    await _semaphore.acquire()
    start = time.monotonic()

    # C-1: Streaming path — semaphore ownership transfers to event_generator()
    if stream:
        return await _handle_streaming(body, model, start)

    # Non-streaming path — semaphore released in finally
    try:
        return await _handle_non_streaming(body, model, start)
    except httpx.HTTPStatusError as exc:
        status_code = str(exc.response.status_code)
        REQUEST_ERRORS.labels(model=model, status_code=status_code).inc()
        REQUESTS_TOTAL.labels(model=model, status="error", stream="false").inc()
        return JSONResponse(
            status_code=int(exc.response.status_code),
            content={"error": f"Ollama returned {exc.response.status_code}"},
        )
    except Exception:
        REQUEST_ERRORS.labels(model=model, status_code="502").inc()
        REQUESTS_TOTAL.labels(model=model, status="error", stream="false").inc()
        return JSONResponse(
            status_code=502,
            content={"error": "Failed to connect to Ollama"},
        )
    finally:
        _semaphore.release()


# ---------------------------------------------------------------------------
# Streaming handler
# ---------------------------------------------------------------------------


async def _handle_streaming(body: dict, model: str, start: float):
    client = await get_client()

    async def event_generator():
        # C-1: semaphore ownership is inside the generator
        try:
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

            # Record duration and throughput after [DONE]
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

        except httpx.HTTPStatusError as exc:
            # M-1: streaming error metric recording
            status_code = str(exc.response.status_code)
            REQUEST_ERRORS.labels(model=model, status_code=status_code).inc()
            REQUESTS_TOTAL.labels(model=model, status="error", stream="true").inc()
            logger.error("Streaming error: Ollama returned %s for model %s", status_code, model)
        except Exception as exc:
            REQUEST_ERRORS.labels(model=model, status_code="502").inc()
            REQUESTS_TOTAL.labels(model=model, status="error", stream="true").inc()
            logger.error("Streaming error: %s", exc)
        finally:
            # C-1: release semaphore after streaming completes (not immediately)
            _semaphore.release()

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


_known_models: set[tuple[str, str]] = set()


async def _poll_model_status():
    """Periodically check Ollama for loaded models and update M11 gauge."""
    global _known_models
    while True:
        try:
            client = await get_client()
            resp = await client.get("/api/ps", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                current: set[tuple[str, str]] = set()
                for m in models:
                    name = m.get("name", "unknown")
                    details = m.get("details", {})
                    quant = details.get("quantization_level", "unknown")
                    MODEL_LOADED.labels(model=name, quantization=quant).set(1)
                    current.add((name, quant))
                for name, quant in _known_models - current:
                    MODEL_LOADED.labels(model=name, quantization=quant).set(0)
                _known_models = current
        except Exception:
            pass
        await asyncio.sleep(30)


_background_tasks: set[asyncio.Task] = set()


@app.on_event("startup")
async def startup():
    task = asyncio.create_task(_poll_model_status())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
