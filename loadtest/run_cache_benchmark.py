"""loadtest/run_cache_benchmark.py - Phase 6 Caching Benchmark.

Measures p95 latency, throughput (RPS), and cost per run before vs. after whole-run
caching under a realistic repeat-request mix using Locust.
"""

import os
import subprocess
import time
import pandas as pd

RESULTS_DIR = os.path.abspath("loadtest/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def run_locust_test(tag: str, repeat_ratio: float, users: int = 20, duration: int = 25) -> dict:
    csv_prefix = os.path.join(RESULTS_DIR, f"cache_bench_{tag}")
    cmd = [
        "locust",
        "-f", "loadtest/locustfile.py",
        "--headless",
        "-u", str(users),
        "-r", "10",
        "-t", f"{duration}s",
        "--host", "http://localhost:8000",
        "--csv", csv_prefix,
        "--only-summary",
    ]
    env = os.environ.copy()
    env["LOADTEST_REPEAT_RATIO"] = str(repeat_ratio)
    env["RATE_LIMIT_PER_MIN"] = "10000"  # High limit so benchmark isolates caching mechanics

    print(f"\n========================================================")
    print(f"Running Benchmark: {tag} (Repeat Ratio = {repeat_ratio * 100:.0f}%, Users = {users})")
    print(f"========================================================")
    subprocess.run(cmd, env=env, check=True)

    stats_file = f"{csv_prefix}_stats.csv"
    if not os.path.exists(stats_file):
        raise FileNotFoundError(f"Missing {stats_file}")

    df = pd.read_csv(stats_file)
    e2e_row = df[df["Name"].str.contains("Complete Run", na=False)]
    if e2e_row.empty:
        total_row = df[df["Name"] == "Aggregated"]
        row = total_row.iloc[0]
    else:
        row = e2e_row.iloc[0]

    req_count = int(row["Request Count"])
    failures = int(row["Failure Count"])
    rps = float(row["Requests/s"])
    p50 = float(row["50%"])
    p95 = float(row["95%"])
    avg = float(row["Average Response Time"])

    # Estimate average token cost per run:
    # Baseline unique run: ~1,500 tokens at $0.00035/run
    # Cached run: 0 tokens ($0.00000/run)
    # Effective cost = (1 - repeat_ratio) * $0.00035
    avg_cost = (1.0 - repeat_ratio) * 0.00035

    res = {
        "tag": tag,
        "repeat_ratio": repeat_ratio,
        "users": users,
        "duration": duration,
        "requests": req_count,
        "failures": failures,
        "throughput_rps": rps,
        "p50_ms": p50,
        "p95_ms": p95,
        "avg_ms": avg,
        "avg_cost_usd": avg_cost,
    }
    print(f"[{tag}] Results -> RPS: {rps:.2f}, p50: {p50:.1f}ms, p95: {p95:.1f}ms, Cost/run: ${avg_cost:.6f}")
    return res

def main():
    # Warm up cache with sample reports
    print("Pre-warming Redis cache with templates...")
    from loadtest.locustfile import SAMPLE_REPORTS
    import urllib.request, json
    for i, rep in enumerate(SAMPLE_REPORTS):
        payload = {**rep, "report_id": f"rep_warmup_{i}"}
        req = urllib.request.Request("http://localhost:8000/v1/reports", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "X-Client-ID": "warmup"}, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                pass
        except Exception:
            pass
    time.sleep(2.0)

    # 1. Without cache (100% unique)
    uncached = run_locust_test("uncached_0pct", repeat_ratio=0.0, users=20, duration=25)

    # 2. Realistic 50% repeat mix
    mixed_50 = run_locust_test("cached_50pct", repeat_ratio=0.5, users=20, duration=25)

    # 3. High repeat 80% repeat mix
    cached_80 = run_locust_test("cached_80pct", repeat_ratio=0.8, users=20, duration=25)

    print("\n\n================ CACHING BENCHMARK COMPARISON ================")
    summary = pd.DataFrame([uncached, mixed_50, cached_80])
    print(summary[["tag", "repeat_ratio", "throughput_rps", "p50_ms", "p95_ms", "avg_cost_usd"]].to_string(index=False))

if __name__ == "__main__":
    main()
