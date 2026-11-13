"""agents/sampling.py — Live sampling of completed runs for quality monitoring.

Usage:
    # Run once (CLI)
    python -m agents.sampling --once --db agents/out/sampling.db

    # Run as background daemon (polls every 60s)
    SAMPLE_RATE=0.1 SAMPLE_DB=agents/out/sampling.db python -m agents.sampling --daemon

    # Print scores table
    python -m agents.sampling --print --db agents/out/sampling.db

    # Export time series CSV
    python -m agents.sampling --export-csv --db agents/out/sampling.db --out agents/out/sampling_timeseries.csv

    # Print summary statistics
    python -m agents.sampling --summary --db agents/out/sampling.db
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import sqlite3
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from agents.batch import load_scenarios
from agents.scoring import get_scorer, reset_scorer
from shared.contracts import RunResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("agents.sampling")

# -----------------------------------------------------------------------------
# RunSource Protocol — Member A's trace store adapter (read-only)
# -----------------------------------------------------------------------------


class RunSource(Protocol):
    """Protocol for fetching completed runs. Implementations provided below."""

    def fetch_completed_runs(self, since: Optional[datetime] = None) -> List[RunResult]:
        """Return completed runs. If since is given, only return runs after that timestamp."""
        ...


class BatchOutputRunSource:
    """Fallback adapter: reads timestamped batch output JSON files from agents/out/.

    This works without Member A's API/trace store. Reads all batch_*.json files
    and uses the pre-computed scores stored in the batch output.
    """

    def __init__(self, out_dir: str = "agents/out"):
        self.out_dir = Path(out_dir)

    def fetch_completed_runs(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Return list of completed run dicts with pre-computed scores.

        Returns dicts with keys: run_id, timestamp, score (dict), prompt_version, routing, status
        """
        runs: List[Dict[str, Any]] = []
        if not self.out_dir.exists():
            return runs

        for json_file in sorted(self.out_dir.glob("batch_*.json")):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                file_timestamp = data.get("metadata", {}).get("timestamp")
                for r in data.get("results", []):
                    if r.get("status") != "completed":
                        continue
                    runs.append(
                        {
                            "run_id": r["run_id"],
                            "timestamp": file_timestamp or datetime.utcnow().isoformat(),
                            "score": r.get("score", {}),
                            "prompt_version": r.get("prompt_versions", {}).get("assessor"),
                            "routing": r.get("routing"),
                            "status": r.get("status"),
                        }
                    )
            except Exception as exc:
                logger.warning("Failed to read %s: %s", json_file, exc)
        return runs


class TraceStoreRunSource:
    """Member A's trace store adapter (read-only).

    Expected interface (to be implemented by Member A):
    - HTTP endpoint or Redis key pattern for completed runs
    - Returns RunResult JSON with full trace and tool_calls

    This is a placeholder — replace with actual implementation when A's trace store is available.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("TRACE_STORE_URL")
        if not self.base_url:
            logger.warning("TRACE_STORE_URL not set; TraceStoreRunSource will return empty")

    def fetch_completed_runs(self, since: Optional[datetime] = None) -> List[RunResult]:
        if not self.base_url:
            return []
        # TODO: Implement HTTP fetch from Member A's trace store
        # Example:
        # import httpx
        # params = {"since": since.isoformat()} if since else {}
        # resp = httpx.get(f"{self.base_url}/runs/completed", params=params, timeout=10)
        # resp.raise_for_status()
        # return [RunResult(**r) for r in resp.json()]
        logger.info("TraceStoreRunSource: fetching from %s", self.base_url)
        return []


# -----------------------------------------------------------------------------
# Sampling Database
# -----------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    groundedness_score REAL,
    citation_resolve INTEGER,  -- 0 or 1
    claim_support_score REAL,
    quote_verbatim INTEGER,    -- 0 or 1
    scorer TEXT NOT NULL,
    prompt_version TEXT,
    routing TEXT,
    status TEXT
);

CREATE INDEX IF NOT EXISTS idx_samples_timestamp ON samples(timestamp);
CREATE INDEX IF NOT EXISTS idx_samples_run_id ON samples(run_id);
"""


class SamplingDB:
    """SQLite storage for sampled run scores."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def insert_sample(self, sample: Dict[str, Any]) -> bool:
        """Insert a sample. Returns True if inserted, False if duplicate run_id."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO samples (run_id, timestamp, groundedness_score, citation_resolve,
                                      claim_support_score, quote_verbatim, scorer, prompt_version, routing, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sample["run_id"],
                        sample["timestamp"],
                        sample.get("groundedness_score"),
                        1 if sample.get("citation_resolve") else 0,
                        sample.get("claim_support_score"),
                        1 if sample.get("quote_verbatim") else 0,
                        sample["scorer"],
                        sample.get("prompt_version"),
                        sample.get("routing"),
                        sample.get("status"),
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False  # duplicate run_id

    def get_all_samples(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM samples ORDER BY timestamp").fetchall()
            return [dict(row) for row in rows]

    def get_samples_since(self, since: datetime) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM samples WHERE timestamp >= ? ORDER BY timestamp",
                (since.isoformat(),),
            ).fetchall()
            return [dict(row) for row in rows]


# -----------------------------------------------------------------------------
# Sampling Job
# -----------------------------------------------------------------------------


def run_sampling_once(
    run_source: RunSource,
    db: SamplingDB,
    sample_rate: float = 0.1,
    scorer_mode: str = "local",
) -> int:
    """Run one sampling iteration: fetch runs, sample ~sample_rate, score, store.

    Returns number of new samples inserted.
    """
    # Check if run_source is BatchOutputRunSource (returns pre-scored dicts)
    if isinstance(run_source, BatchOutputRunSource):
        runs = run_source.fetch_completed_runs()
        if not runs:
            logger.info("No completed runs found")
            return 0

        threshold = int(sample_rate * 100)
        inserted = 0

        for run in runs:
            h = int(hashlib.md5(run["run_id"].encode()).hexdigest(), 16) % 100
            if h >= threshold:
                continue

            score = run.get("score", {})

            sample = {
                "run_id": run["run_id"],
                "timestamp": run["timestamp"],
                "groundedness_score": score.get("groundedness"),
                "citation_resolve": score.get("citation_resolve"),
                "claim_support_score": score.get("claim_support"),
                "quote_verbatim": score.get("quote_verbatim"),
                "scorer": scorer_mode,
                "prompt_version": run.get("prompt_version"),
                "routing": run.get("routing"),
                "status": run.get("status"),
            }

            if db.insert_sample(sample):
                inserted += 1
                logger.info(
                    "Sampled run %s: groundedness=%.2f, cites_resolved=%s",
                    run["run_id"],
                    score.get("groundedness", 0),
                    score.get("citation_resolve"),
                )

        logger.info("Sampling iteration complete: %d new samples inserted", inserted)
        return inserted

    # Otherwise, use the full RunResult path (for TraceStoreRunSource)
    reset_scorer()
    os.environ["SCORER"] = scorer_mode
    scorer = get_scorer()

    runs = run_source.fetch_completed_runs()
    if not runs:
        logger.info("No completed runs found")
        return 0

    threshold = int(sample_rate * 100)
    inserted = 0

    for run in runs:
        h = int(hashlib.md5(run.run_id.encode()).hexdigest(), 16) % 100
        if h >= threshold:
            continue

        score = scorer.score(run, [])

        sample = {
            "run_id": run.run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "groundedness_score": score.get("groundedness"),
            "citation_resolve": score.get("citation_resolve"),
            "claim_support_score": score.get("claim_support"),
            "quote_verbatim": score.get("quote_verbatim"),
            "scorer": scorer_mode,
            "prompt_version": run.prompt_versions.get("assessor") if run.prompt_versions else None,
            "routing": run.routing,
            "status": run.status,
        }

        if db.insert_sample(sample):
            inserted += 1
            logger.info(
                "Sampled run %s: groundedness=%.2f, cites_resolved=%s",
                run.run_id,
                score.get("groundedness", 0),
                score.get("citation_resolve"),
            )

    logger.info("Sampling iteration complete: %d new samples inserted", inserted)
    return inserted


def print_scores_table(db: SamplingDB) -> None:
    """Print sampled scores as a formatted table."""
    samples = db.get_all_samples()
    if not samples:
        print("No samples in database")
        return

    print("\n" + "=" * 120)
    print("LIVE SAMPLING SCORES — {len(samples)} samples".format(len=len))
    print("=" * 120)
    print(
        "{'Run ID':<35} {'Time':<20} {'Grounded':>8} {'Cites OK':>8} {'Claim Supp':>10} {'Quote VB':>8} {'Scorer':<8} {'Prompt':<8} {'Routing':<12}".format()
    )
    print("-" * 120)
    for s in samples:
        ts = s["timestamp"][:19].replace("T", " ")
        grounded = (
            "{s[groundedness_score]:.2f}".format(s=s) if s["groundedness_score"] is not None else "N/A"
        )
        cites = (
            "✓" if s["citation_resolve"] else ("✗" if s["citation_resolve"] is not None else "?")
        )
        claim = "{s[claim_support_score]:.2f}".format(s=s) if s["claim_support_score"] is not None else "N/A"
        quote = "✓" if s["quote_verbatim"] else ("✗" if s["quote_verbatim"] is not None else "?")
        prompt = s["prompt_version"] or "N/A"
        routing = s["routing"] or "N/A"
        print(
            "{s[run_id]:<35} {ts:<20} {grounded:>8} {cites:>8} {claim:>10} {quote:>8} {s[scorer]:<8} {prompt:<8} {routing:<12}".format(
                s=s, ts=ts, grounded=grounded, cites=cites, claim=claim, quote=quote, prompt=prompt, routing=routing
            )
        )
    print("=" * 120 + "\n")


def print_summary_stats(db: SamplingDB) -> None:
    """Print aggregate summary statistics."""
    samples = db.get_all_samples()
    if not samples:
        print("No samples in database")
        return

    # Filter to only completed samples with scores
    scored = [s for s in samples if s["groundedness_score"] is not None]
    if not scored:
        print("No scored samples available")
        return

    groundedness = [s["groundedness_score"] for s in scored]
    claim_support = [s["claim_support_score"] for s in scored if s["claim_support_score"] is not None]
    cites_resolved = sum(1 for s in scored if s["citation_resolve"])
    quotes_verbatim = sum(1 for s in scored if s["quote_verbatim"])

    print("\n" + "=" * 60)
    print("SAMPLING SUMMARY — {len_scored} scored samples / {len_total} total".format(len_scored=len(scored), len_total=len(samples)))
    print("=" * 60)
    print("Groundedness:     mean={mean_g:.3f}, stdev={stdev_g:.3f}, min={min_g:.3f}, max={max_g:.3f}".format(
        mean_g=statistics.mean(groundedness),
        stdev_g=statistics.stdev(groundedness) if len(groundedness) > 1 else 0,
        min_g=min(groundedness),
        max_g=max(groundedness),
    ))
    if claim_support:
        print("Claim Support:    mean={mean_c:.3f}, stdev={stdev_c:.3f}".format(
            mean_c=statistics.mean(claim_support),
            stdev_c=statistics.stdev(claim_support) if len(claim_support) > 1 else 0,
        ))
    else:
        print("Claim Support:    N/A")
    print("Citation Resolve: {cites}/{total} ({pct:.1f}%)".format(
        cites=cites_resolved, total=len(scored), pct=cites_resolved/len(scored)*100 if scored else 0
    ))
    print("Quote Verbatim:   {quotes}/{total} ({pct:.1f}%)".format(
        quotes=quotes_verbatim, total=len(scored), pct=quotes_verbatim/len(scored)*100 if scored else 0
    ))

    # By prompt version
    by_prompt = {}
    for s in scored:
        pv = s["prompt_version"] or "unknown"
        if pv not in by_prompt:
            by_prompt[pv] = []
        by_prompt[pv].append(s["groundedness_score"])

    print("\nBy Prompt Version:")
    for pv, scores in sorted(by_prompt.items()):
        print("  {pv}: n={n}, groundedness_mean={mean:.3f}".format(
            pv=pv, n=len(scores), mean=statistics.mean(scores)
        ))

    # By routing
    by_routing = {}
    for s in scored:
        rt = s["routing"] or "unknown"
        if rt not in by_routing:
            by_routing[rt] = []
        by_routing[rt].append(s["groundedness_score"])

    print("\nBy Routing:")
    for rt, scores in sorted(by_routing.items()):
        print("  {rt}: n={n}, groundedness_mean={mean:.3f}".format(
            rt=rt, n=len(scores), mean=statistics.mean(scores)
        ))

    print("=" * 60 + "\n")


def export_timeseries_csv(db: SamplingDB, out_path: str) -> None:
    """Export samples as CSV time series for charting."""
    samples = db.get_all_samples()
    if not samples:
        logger.warning("No samples to export")
        return

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "run_id",
        "timestamp",
        "groundedness_score",
        "citation_resolve",
        "claim_support_score",
        "quote_verbatim",
        "scorer",
        "prompt_version",
        "routing",
        "status",
    ]
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for s in samples:
            writer.writerow(s)
    logger.info("Exported {len} samples to {out}".format(len=len(samples), out=out_file))


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def get_run_source() -> RunSource:
    """Get the appropriate RunSource based on env/config."""
    trace_url = os.getenv("TRACE_STORE_URL")
    if trace_url:
        logger.info("Using TraceStoreRunSource: %s", trace_url)
        return TraceStoreRunSource(trace_url)
    else:
        logger.info("Using BatchOutputRunSource (fallback)")
        return BatchOutputRunSource()


def main() -> int:
    parser = argparse.ArgumentParser(description="Live sampling for PV-Triage quality monitoring")
    parser.add_argument("--once", action="store_true", help="Run one sampling iteration and exit")
    parser.add_argument(
        "--daemon", action="store_true", help="Run as background daemon (polls every 60s)"
    )
    parser.add_argument(
        "--print", action="store_true", dest="print_table", help="Print scores table"
    )
    parser.add_argument("--summary", action="store_true", help="Print summary statistics")
    parser.add_argument("--export-csv", action="store_true", help="Export time series CSV")
    parser.add_argument("--out", help="Output CSV path (for --export-csv)")
    parser.add_argument(
        "--db",
        default=os.getenv("SAMPLE_DB", "agents/out/sampling.db"),
        help="SQLite database path",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=float(os.getenv("SAMPLE_RATE", "0.1")),
        help="Sampling rate (0-1)",
    )
    parser.add_argument(
        "--scorer",
        choices=["local", "eval"],
        default=os.getenv("SCORER", "local"),
        help="Scorer mode",
    )
    parser.add_argument("--interval", type=int, default=60, help="Daemon poll interval (seconds)")

    args = parser.parse_args()

    db = SamplingDB(args.db)
    run_source = get_run_source()

    if args.print_table:
        print_scores_table(db)
        return 0

    if args.summary:
        print_summary_stats(db)
        return 0

    if args.export_csv:
        if not args.out:
            parser.error("--out required with --export-csv")
        export_timeseries_csv(db, args.out)
        return 0

    if args.once:
        run_sampling_once(run_source, db, args.rate, args.scorer)
        return 0

    if args.daemon:
        logger.info(
            "Starting sampling daemon (interval={interval}d, rate={rate:.1f}%)".format(interval=args.interval, rate=args.rate * 100)
        )
        try:
            while True:
                run_sampling_once(run_source, db, args.rate, args.scorer)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Daemon stopped")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
