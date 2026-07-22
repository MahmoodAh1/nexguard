"""HDFS log dataset source.

HDFS logs are naturally session-partitioned by ``block_id``: every block's
lifecycle is an ordered event sequence with a ground-truth normal/anomaly label,
which is exactly the shape the sequence + statistical detectors need (see
``docs/architecture/README.md``). This adapter groups raw lines into
:class:`RawSession`s by block id, preserving order and attaching timestamps and
labels.
"""

from __future__ import annotations

import csv
import re
from collections import OrderedDict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from nexguard.domain.detection import RawSession

_BLOCK_ID = re.compile(r"blk_-?\d+")
# HDFS line prefix: "081109 203615 148 INFO ..." -> date=yymmdd, time=HHMMSS.
_TIMESTAMP = re.compile(r"^(\d{6})\s+(\d{6})\b")
_DATASET = "hdfs"


class HdfsDatasetSource:
    """Reads an HDFS log file (+ optional label CSV) into labeled sessions."""

    def __init__(self, log_path: str | Path, label_path: str | Path | None = None) -> None:
        self._log_path = Path(log_path)
        self._label_path = Path(label_path) if label_path else None

    def iter_sessions(self) -> Iterator[RawSession]:
        labels = self._load_labels()
        buckets: OrderedDict[str, list[tuple[str, str]]] = OrderedDict()

        with self._log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.rstrip("\n")
                if not line.strip():
                    continue
                iso_ts = self._parse_timestamp(line)
                for block_id in dict.fromkeys(_BLOCK_ID.findall(line)):
                    buckets.setdefault(block_id, []).append((line, iso_ts))

        for block_id, entries in buckets.items():
            lines = tuple(entry[0] for entry in entries)
            timestamps = tuple(entry[1] for entry in entries)
            yield RawSession(
                external_id=block_id,
                dataset=_DATASET,
                lines=lines,
                label=labels.get(block_id),
                timestamps=timestamps,
            )

    def _load_labels(self) -> dict[str, bool]:
        if self._label_path is None or not self._label_path.exists():
            return {}
        labels: dict[str, bool] = {}
        with self._label_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                block_id = (row.get("BlockId") or row.get("block_id") or "").strip()
                label = (row.get("Label") or row.get("label") or "").strip().lower()
                if block_id:
                    labels[block_id] = label in {"anomaly", "anomalous", "1", "true"}
        return labels

    @staticmethod
    def _parse_timestamp(line: str) -> str:
        match = _TIMESTAMP.match(line)
        if not match:
            return ""
        try:
            moment = datetime.strptime(f"{match.group(1)} {match.group(2)}", "%y%m%d %H%M%S")
        except ValueError:
            return ""
        return moment.replace(tzinfo=UTC).isoformat()
