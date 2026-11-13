"""Test higher concurrency for 1 worker to find the exact breaking point."""
import json
from loadtest.run_benchmarks import run_suite

matrix_high = [
    {"c": 40, "r": 20, "d": 30},
    {"c": 60, "r": 20, "d": 35},
    {"c": 80, "r": 20, "d": 35},
    {"c": 100, "r": 25, "d": 40},
]

print("Running stress concurrency ladder on 1 worker...")
results = run_suite(1, matrix_high)
print("\n--- Higher Concurrency Results (1 Worker) ---")
print(json.dumps(results, indent=2))
