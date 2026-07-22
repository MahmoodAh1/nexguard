"""BGL (BlueGene/L) log dataset source.

Unlike HDFS, BGL is node/time-oriented rather than session-partitioned, so we
sessionize it into fixed-size tumbling windows of consecutive log messages — the
standard DeepLog treatment. A window is labeled anomalous if it contains any
alert line (BGL marks each line with an alert category, or ``-`` for normal).
Implements the same :class:`~nexguard.domain.ports.DatasetSource` port as HDFS,
demonstrating the abstraction generalizes across log datasets.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from nexguard.domain.detection import RawSession

_DATASET = "bgl"
_NORMAL_LABEL = "-"


class BglDatasetSource:
    """Reads a BGL log file into fixed-window sessions."""

    def __init__(self, log_path: str | Path, *, window_size: int = 20) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self._log_path = Path(log_path)
        self._window_size = window_size

    def iter_sessions(self) -> Iterator[RawSession]:
        window_index = 0
        contents: list[str] = []
        timestamps: list[str] = []
        anomalous = False

        with self._log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                parsed = _parse_line(raw)
                if parsed is None:
                    continue
                label, iso_ts, content = parsed
                contents.append(content)
                timestamps.append(iso_ts)
                anomalous = anomalous or label != _NORMAL_LABEL

                if len(contents) >= self._window_size:
                    yield _make_session(window_index, contents, timestamps, anomalous)
                    window_index += 1
                    contents, timestamps, anomalous = [], [], False

        if contents:
            yield _make_session(window_index, contents, timestamps, anomalous)


def _make_session(
    index: int, contents: list[str], timestamps: list[str], anomalous: bool
) -> RawSession:
    return RawSession(
        external_id=f"bgl_win_{index:05d}",
        dataset=_DATASET,
        lines=tuple(contents),
        label=anomalous,
        timestamps=tuple(timestamps),
    )


def _parse_line(raw: str) -> tuple[str, str, str] | None:
    """Return (label, iso_timestamp, content) or None for a blank line.

    BGL fields: Label, Timestamp(epoch), Date, Node, Time, NodeRepeat, Type,
    Component, Level, Content. The content message is what we template.
    """
    line = raw.strip()
    if not line:
        return None
    parts = line.split(None, 9)
    label = parts[0]
    iso_ts = _epoch_to_iso(parts[1]) if len(parts) > 1 else ""
    content = parts[9] if len(parts) > 9 else line
    return label, iso_ts, content


def _epoch_to_iso(token: str) -> str:
    try:
        return datetime.fromtimestamp(int(token), tz=UTC).isoformat()
    except (ValueError, OSError):
        return ""
