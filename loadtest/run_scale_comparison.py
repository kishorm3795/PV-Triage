"""Run benchmark ladder with 3 workers for scaling comparison against 1 worker."""

import json
import os
from loadtest.run_benchmarks import run_suite

matrix_3w = [
    {"c": 1, "r": 1, "d": 20},
    {"c": 5, "r": 5, "d": 20},
    {"c": 10, "r": 10, "d": 25},
    {"c": 20, "r": 10, "d": 25},
    {"c": 30, "r": 15, "d": 25},
    {"c": 40, "r": 20, "d": 30},
    {"c": 60, "r": 20, "d": 30},
    {"c": 80, "r": 20, "d": 35},
    {"c": 100, "r": 25, "d": 35},
    {"c": 140, "r": 30, "d": 40},
]

print("Starting 3-worker scaling benchmark ladder...")
results_3w = run_suite(3, matrix_3w)
print("\n--- 3 Workers Results ---")
print(json.dumps(results_3w, indent=2))
