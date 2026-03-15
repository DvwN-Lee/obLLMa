"""
run.py — Async load generator for the LLM Serving Observability project.

Usage:
    python run.py --scenario s1 --base-url http://localhost:8000
    python run.py --scenario s2 --base-url http://localhost:8000
    python run.py --scenario s5 --base-url http://localhost:8000 --model qwen2.5:7b

Each request uses httpx streaming to measure:
  - TTFT      : time from send to first SSE chunk containing content
  - Duration  : time from send to data: [DONE]
  - TPS       : output_tokens / duration
  - Tokens    : completion_tokens from the usage chunk

After all requests complete, a summary table is printed to stdout.

Dependencies: httpx (see loadtest/requirements.txt)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from scenarios import get_scenario

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RequestResult:
    ttft: float | None = None        # seconds to first token
    duration: float | None = None    # seconds for full response
    output_tokens: int = 0
    tps: float | None = None         # tokens / second
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class RunConfig:
    base_url: str
    model: str
    concurrency: int
    num_requests: int
    prompts: list[list[dict]]        # cycled across requests


# ---------------------------------------------------------------------------
# Single-request coroutine
# ---------------------------------------------------------------------------


async def _send_request(
    client: httpx.AsyncClient,
    config: RunConfig,
    prompt_index: int,
) -> RequestResult:
    """Send one streaming chat completion and return measured metrics."""
    messages = config.prompts[prompt_index % len(config.prompts)]
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    result = RequestResult()
    start = time.monotonic()

    try:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json=payload,
        ) as resp:
            resp.raise_for_status()

            async for raw_line in resp.aiter_lines():
                if not raw_line.startswith("data: "):
                    continue

                data_str = raw_line[6:].strip()

                if data_str == "[DONE]":
                    result.duration = time.monotonic() - start
                    break

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # TTFT — first chunk that carries content text
                if result.ttft is None:
                    choices = chunk.get("choices", [])
                    if choices:
                        content = choices[0].get("delta", {}).get("content")
                        if content:
                            result.ttft = time.monotonic() - start

                # Usage chunk — appears just before [DONE]
                usage = chunk.get("usage")
                if usage:
                    result.output_tokens = usage.get("completion_tokens", 0)

    except httpx.HTTPStatusError as exc:
        result.error = f"HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        result.error = f"RequestError: {exc}"
    except Exception as exc:  # noqa: BLE001
        result.error = f"Unexpected: {exc}"

    # Compute TPS only for successful requests with duration > 0
    if result.success and result.duration and result.output_tokens > 0:
        result.tps = result.output_tokens / result.duration

    return result


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------


async def run_batch(config: RunConfig) -> list[RequestResult]:
    """Run `config.num_requests` requests with `config.concurrency` semaphore."""
    sem = asyncio.Semaphore(config.concurrency)
    # No read timeout — LLM responses can take 30-120s
    timeout = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0)
    results: list[RequestResult | None] = [None] * config.num_requests

    async with httpx.AsyncClient(
        base_url=config.base_url,
        timeout=timeout,
    ) as client:

        async def _worker(idx: int) -> None:
            async with sem:
                results[idx] = await _send_request(client, config, idx)

        await asyncio.gather(*[_worker(i) for i in range(config.num_requests)])

    # Filter None slots (should not occur, but satisfy type checker)
    return [r for r in results if r is not None]


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Nearest-rank percentile over a sorted list."""
    if not sorted_vals:
        return float("nan")
    n = len(sorted_vals)
    rank = math.ceil(pct / 100.0 * n) - 1
    rank = max(0, min(rank, n - 1))
    return sorted_vals[rank]


@dataclass
class MetricStats:
    values: list[float] = field(default_factory=list)

    def add(self, v: float | None) -> None:
        if v is not None and not math.isnan(v):
            self.values.append(v)

    @property
    def avg(self) -> float:
        return sum(self.values) / len(self.values) if self.values else float("nan")

    def p(self, pct: float) -> float:
        return _percentile(sorted(self.values), pct)


def _compute_stats(results: list[RequestResult]) -> dict[str, MetricStats]:
    ttft = MetricStats()
    duration = MetricStats()
    tps = MetricStats()
    tokens = MetricStats()

    for r in results:
        if r.success:
            ttft.add(r.ttft)
            duration.add(r.duration)
            tps.add(r.tps)
            tokens.add(float(r.output_tokens) if r.output_tokens else None)

    return {
        "ttft": ttft,
        "duration": duration,
        "tps": tps,
        "tokens": tokens,
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_COL_W = 10  # width for stat columns


def _fmt(v: float, decimals: int = 3) -> str:
    if math.isnan(v):
        return "n/a".rjust(_COL_W)
    return f"{v:.{decimals}f}".rjust(_COL_W)


def _print_summary(
    scenario_name: str,
    label: str,
    results: list[RequestResult],
    wall_time: float,
) -> None:
    errors = sum(1 for r in results if not r.success)
    stats = _compute_stats(results)

    print()
    print(f"=== Scenario: {scenario_name}" + (f" | {label}" if label else "") + " ===")
    print(
        f"Requests: {len(results)} | "
        f"Errors: {errors} | "
        f"Wall time: {wall_time:.1f}s"
    )
    if errors:
        for r in results:
            if r.error:
                print(f"  Error: {r.error}")

    header = (
        f"\n{'Metric':<20}"
        f"{'Avg':>{_COL_W}}"
        f"{'P50':>{_COL_W}}"
        f"{'P95':>{_COL_W}}"
        f"{'P99':>{_COL_W}}"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)

    rows = [
        ("TTFT (s)", stats["ttft"], 3),
        ("Duration (s)", stats["duration"], 3),
        ("TPS (tok/s)", stats["tps"], 1),
        ("Output Tokens", stats["tokens"], 1),
    ]
    for name, st, decimals in rows:
        print(
            f"{name:<20}"
            f"{_fmt(st.avg, decimals)}"
            f"{_fmt(st.p(50), decimals)}"
            f"{_fmt(st.p(95), decimals)}"
            f"{_fmt(st.p(99), decimals)}"
        )


# ---------------------------------------------------------------------------
# Scenario runners
# ---------------------------------------------------------------------------


async def _run_simple(
    scenario: dict,
    base_url: str,
    model: str,
    label: str = "",
) -> None:
    """Run a scenario with a single fixed concurrency level."""
    config = RunConfig(
        base_url=base_url,
        model=model,
        concurrency=scenario["concurrency"],
        num_requests=scenario["num_requests"],
        prompts=scenario["prompts"],
    )
    t0 = time.monotonic()
    results = await run_batch(config)
    wall = time.monotonic() - t0
    _print_summary(scenario["name"], label, results, wall)


async def _run_sweep(scenario: dict, base_url: str, model: str) -> None:
    """S2: run each concurrency level sequentially."""
    levels: list[int] = scenario["concurrency"]
    for level in levels:
        config = RunConfig(
            base_url=base_url,
            model=model,
            concurrency=level,
            num_requests=scenario["num_requests"],
            prompts=scenario["prompts"],
        )
        t0 = time.monotonic()
        results = await run_batch(config)
        wall = time.monotonic() - t0
        _print_summary(scenario["name"], f"concurrency={level}", results, wall)


async def _run_variable_prompt(scenario: dict, base_url: str, model: str) -> None:
    """S4: run short / medium / long prompt pools separately at fixed concurrency."""
    pools: dict[str, list[list[dict]]] = scenario["prompts"]
    for size_label, prompts in pools.items():
        sub_scenario = {
            **scenario,
            "prompts": prompts,
        }
        await _run_simple(sub_scenario, base_url, model, label=f"prompt={size_label}")


async def _run_model_comparison(scenario: dict, base_url: str, model_override: str | None) -> None:
    """S5: run same scenario sequentially for each model."""
    models: list[str] = scenario.get("models", [])
    if model_override:
        # If caller forced a single model, respect that
        models = [model_override]
    for mdl in models:
        sub_scenario = {**scenario}
        t0 = time.monotonic()
        config = RunConfig(
            base_url=base_url,
            model=mdl,
            concurrency=sub_scenario["concurrency"],
            num_requests=sub_scenario["num_requests"],
            prompts=sub_scenario["prompts"],
        )
        results = await run_batch(config)
        wall = time.monotonic() - t0
        _print_summary(scenario["name"], f"model={mdl}", results, wall)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def _dispatch(args: argparse.Namespace) -> None:
    scenario_key = args.scenario.lower()
    scenario = get_scenario(scenario_key)

    # Resolve effective model: CLI flag > scenario default > proxy default (None)
    effective_model: str = args.model or scenario.get("model") or "qwen2.5:7b"

    print(f"\nLoading scenario: {scenario['name']}")
    print(f"Description     : {scenario['description']}")
    print(f"Base URL        : {args.base_url}")
    print(f"Model           : {effective_model if scenario_key != 's5' else '(per-model)'}")

    if scenario_key == "s2":
        await _run_sweep(scenario, args.base_url, effective_model)
    elif scenario_key == "s4":
        await _run_variable_prompt(scenario, args.base_url, effective_model)
    elif scenario_key == "s5":
        await _run_model_comparison(scenario, args.base_url, args.model)
    else:
        # S1, S3 — simple fixed-concurrency run
        await _run_simple(scenario, args.base_url, effective_model)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Async load generator for the LLM Serving Observability project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run.py --scenario s1\n"
            "  python run.py --scenario s2 --base-url http://localhost:8000\n"
            "  python run.py --scenario s5 --model qwen2.5:7b\n"
        ),
    )
    parser.add_argument(
        "--scenario",
        required=True,
        metavar="SCENARIO",
        help="Scenario key: s1 | s2 | s3 | s4 | s5",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        metavar="URL",
        help="Base URL of the LLM proxy (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="MODEL",
        help=(
            "Model name override (e.g. qwen2.5:7b). "
            "Overrides scenario default. For S5, limits comparison to one model."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_dispatch(args))


if __name__ == "__main__":
    main()
