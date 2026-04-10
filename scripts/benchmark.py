"""
Benchmark script for measuring per-layer response times.

Usage:
    pip install httpx
    python scripts/benchmark.py

Before running:
    1. Set ENABLE_TIMING=true in your .env or Koyeb env vars
    2. Set BASE_URL, USERNAME, and PASSWORD below
    3. Run the admin reset endpoint first so all test orders exist:
       POST <BASE_URL>/admin/reset

Output:
    - Prints a summary table to the terminal
    - Saves raw results to benchmark_results.csv

What it measures:
    - state_load  : Redis get (or memory fallback)
    - routing     : rule-based keyword match OR LLM call
    - tool        : DB query (get/cancel/refund)
    - state_save  : Redis set / clear (or memory fallback)
    - total       : full end-to-end agent time (excludes network)

Note: 'total' in the TIMING log is agent processing time only.
The script also records wall-clock round-trip time (includes network
latency to your deployed instance).
"""

import csv
import re
import statistics
import time
from datetime import datetime

import httpx

# ── Configuration ─────────────────────────────────────────────
BASE_URL  = "https://ethnic-brittany-3rdindustries-fd4f61c1.koyeb.app/"   
USERNAME  = "user_1"
PASSWORD  = "password123"
REPEATS   = 20    # requests per scenario — minimum 20 for stable averages
DELAY     = 0.3   # seconds between requests (be kind to the rate limiter)
# ──────────────────────────────────────────────────────────────

# Test scenarios — covers rule-based and LLM paths, read and write ops
SCENARIOS = [
    {
        "name":        "lookup_rule",
        "description": "Order lookup — rule-based routing",
        "user_id":     "user_2",
        "message":     "Check ORD-2003",
        "path":        "rule",
    },
    {
        "name":        "cancel_queue_rule",
        "description": "Cancel queue — rule-based routing",
        "user_id":     "user_3",
        "message":     "Cancel my order ORD-2008",
        "path":        "rule",
    },
    {
        "name":        "lookup_llm",
        "description": "Order lookup — LLM fallback routing",
        "user_id":     "user_2",
        "message":     "What is happening with my package ORD-2003",
        "path":        "llm",
    },
    {
        "name":        "cancel_llm",
        "description": "Cancel intent — LLM fallback routing",
        "user_id":     "user_3",
        "message":     "I'd like to stop my order ORD-2008",
        "path":        "llm",
    },
]


def login(client: httpx.Client) -> str:
    resp = client.post(
        f"{BASE_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print(f"✅ Logged in as {USERNAME}\n")
    return token


def reset_db(client: httpx.Client) -> None:
    resp = client.post(f"{BASE_URL}/admin/reset")
    resp.raise_for_status()
    print(f"✅ Database reset — {resp.json()['orders_seeded']} orders seeded\n")


def parse_timing_from_logs(response_json: dict) -> dict[str, float] | None:
    """
    The TIMING log line is not in the API response — it goes to server logs.
    Instead we parse timing from the response logs list if present,
    or fall back to None (wall-clock time is still recorded).
    """
    # Future improvement: expose timing in response metadata
    return None


def run_scenario(
    client: httpx.Client,
    token: str,
    scenario: dict,
    repeats: int,
) -> list[dict]:
    results = []
    headers = {"Authorization": f"Bearer {token}"}

    print(f"Running: {scenario['description']} ({repeats}x)")

    for i in range(repeats):
        # Reset agent state before each request so we always hit fresh routing
        client.post(
            f"{BASE_URL}/agent/reset",
            json={"user_id": scenario["user_id"], "message": "_reset_"},
            headers=headers,
        )

        t_start = time.perf_counter()
        resp = client.post(
            f"{BASE_URL}/agent/chat",
            json={"user_id": scenario["user_id"], "message": scenario["message"]},
            headers=headers,
        )
        wall_ms = round((time.perf_counter() - t_start) * 1000, 2)

        resp.raise_for_status()
        data = resp.json()

        results.append({
            "scenario":     scenario["name"],
            "description":  scenario["description"],
            "path":         scenario["path"],
            "repeat":       i + 1,
            "wall_ms":      wall_ms,
            "intent":       data.get("intent"),
            "success":      data.get("success"),
            "action_result": data.get("action_result"),
        })

        print(f"  [{i+1:02d}/{repeats}] wall={wall_ms:.0f}ms  intent={data.get('intent')}")
        time.sleep(DELAY)

    print()
    return results


def summarise(results: list[dict]) -> None:
    print("=" * 70)
    print(f"{'BENCHMARK RESULTS':^70}")
    print(f"{'Run at: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^70}")
    print(f"{'Target: ' + BASE_URL:^70}")
    print("=" * 70)

    # Group by scenario
    scenarios: dict[str, list[float]] = {}
    for r in results:
        scenarios.setdefault(r["scenario"], []).append(r["wall_ms"])

    print(f"\n{'Scenario':<30} {'N':>4} {'Avg':>8} {'Median':>8} {'p95':>8} {'Min':>8} {'Max':>8}")
    print("-" * 70)

    for name, times in scenarios.items():
        desc = next(r["description"] for r in results if r["scenario"] == name)
        path = next(r["path"] for r in results if r["scenario"] == name)
        label = f"{desc} [{path}]"
        avg    = statistics.mean(times)
        median = statistics.median(times)
        p95    = sorted(times)[int(len(times) * 0.95)]
        print(
            f"{label:<30} {len(times):>4} {avg:>7.0f}ms"
            f" {median:>7.0f}ms {p95:>7.0f}ms"
            f" {min(times):>7.0f}ms {max(times):>7.0f}ms"
        )

    # Rule vs LLM comparison
    rule_times = [r["wall_ms"] for r in results if r["path"] == "rule"]
    llm_times  = [r["wall_ms"] for r in results if r["path"] == "llm"]

    if rule_times and llm_times:
        print("\n" + "-" * 70)
        print(f"Rule-based avg : {statistics.mean(rule_times):.0f}ms")
        print(f"LLM fallback avg: {statistics.mean(llm_times):.0f}ms")
        ratio = statistics.mean(llm_times) / statistics.mean(rule_times)
        print(f"LLM is {ratio:.1f}x slower than rule-based routing")

    print("=" * 70)


def save_csv(results: list[dict], filename: str = "benchmark_results.csv") -> None:
    if not results:
        return
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\n✅ Raw results saved to {filename}")


def main():
    print(f"\n{'='*70}")
    print(f"  Agent Benchmark — {BASE_URL}")
    print(f"  {REPEATS} requests per scenario, {DELAY}s delay between requests")
    print(f"{'='*70}\n")

    with httpx.Client(timeout=30.0) as client:
        token = login(client)
        reset_db(client)

        all_results = []
        for scenario in SCENARIOS:
            results = run_scenario(client, token, scenario, REPEATS)
            all_results.extend(results)
            # Reset DB between scenarios so order states don't affect each other
            reset_db(client)

    summarise(all_results)
    save_csv(all_results)


if __name__ == "__main__":
    main()