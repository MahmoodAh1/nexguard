"""Offline model comparison: train LSTM / Transformer / IsolationForest / Ensemble
on a labeled log dataset and report detection + operational metrics.

Run with the backend environment (which has the ``nexguard`` package installed):

    cd backend && uv run python ../ml/evaluate.py
    cd backend && uv run python ../ml/evaluate.py --epochs 30 --threshold 0.5

Results are printed and written to ``ml/results/model_comparison.md``. MLflow
tracking is attached via the ExperimentTracker port when enabled.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from nexguard.application.use_cases.ingest_and_parse import IngestAndParse
from nexguard.domain.entities import Session
from nexguard.evaluation.harness import ComparisonResult, run_comparison
from nexguard.infrastructure.datasets.hdfs import HdfsDatasetSource
from nexguard.infrastructure.memory.repositories import InMemoryLogRepository
from nexguard.infrastructure.parsing.drain3_miner import Drain3TemplateMiner

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_LOG = _ROOT / "backend" / "tests" / "fixtures" / "hdfs" / "hdfs_sample.log"
_DEFAULT_LABELS = (
    _ROOT / "backend" / "tests" / "fixtures" / "hdfs" / "anomaly_label.csv"
)
_DEFAULT_OUT = _ROOT / "ml" / "results" / "model_comparison.md"


async def _ingest(log: Path, labels: Path) -> list[Session]:
    repo = InMemoryLogRepository()
    use_case = IngestAndParse(Drain3TemplateMiner(), repo)
    return await use_case.execute(HdfsDatasetSource(log, labels).iter_sessions())


def _render(result: ComparisonResult, log: Path) -> str:
    best = result.best_by_f1()
    return "\n".join(
        [
            "# NexGuard — Model Comparison",
            "",
            f"- Generated: {datetime.now(tz=UTC).isoformat()}",
            f"- Dataset: `{log.name}`  ·  threshold: {result.threshold}",
            f"- Best by F1: **{best.name}** (F1 = {best.metrics.f1:.4f})",
            "",
            result.as_table(),
            "",
            "> ROC-AUC / PR-AUC use continuous scores; FPR x session volume = the",
            "> analyst's daily false-alert load. Prefer higher recall at acceptable FPR",
            "> for a SOC that cannot miss incidents.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=_DEFAULT_LOG)
    parser.add_argument("--labels", type=Path, default=_DEFAULT_LABELS)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    sessions = asyncio.run(_ingest(args.log, args.labels))
    result = run_comparison(
        sessions,
        lstm_epochs=args.epochs,
        transformer_epochs=args.epochs * 2,
        threshold=args.threshold,
    )

    report = _render(result, args.log)
    print(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
