"""CICIDS-style network-flow dataset source.

CICIDS is tabular network flows (a CSV with a ``Label`` column: BENIGN or an
attack name), not textual logs. To fit it into the same templating pipeline, this
adapter groups flows into sessions by a key (default: source IP) and renders each
flow as a structured event line from its categorical fields, so Drain3 can
template them. A session is anomalous if any of its flows is non-benign.

Full continuous flow features are a more natural fit for the statistical detector;
this adapter demonstrates the DatasetSource abstraction extends to flow data.
"""

from __future__ import annotations

import csv
from collections import OrderedDict
from collections.abc import Iterator, Sequence
from pathlib import Path

from nexguard.domain.detection import RawSession

_DATASET = "cicids"


class CicidsDatasetSource:
    """Reads a CICIDS-style flow CSV into per-source sessions."""

    def __init__(
        self,
        csv_path: str | Path,
        *,
        session_key: str = "Source IP",
        label_column: str = "Label",
        benign_label: str = "BENIGN",
        feature_columns: Sequence[str] = ("Protocol", "Service", "Flag"),
    ) -> None:
        self._csv_path = Path(csv_path)
        self._session_key = session_key
        self._label_column = label_column
        self._benign_label = benign_label.upper()
        self._feature_columns = tuple(feature_columns)

    def iter_sessions(self) -> Iterator[RawSession]:
        buckets: OrderedDict[str, list[str]] = OrderedDict()
        anomalous: dict[str, bool] = {}

        with self._csv_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (row.get(self._session_key) or "unknown").strip()
                buckets.setdefault(key, []).append(self._render(row))
                is_attack = (
                    row.get(self._label_column) or ""
                ).strip().upper() != self._benign_label
                anomalous[key] = anomalous.get(key, False) or is_attack

        for key, lines in buckets.items():
            yield RawSession(
                external_id=f"cicids_{key}",
                dataset=_DATASET,
                lines=tuple(lines),
                label=anomalous[key],
            )

    def _render(self, row: dict[str, str]) -> str:
        fields = " ".join(
            f"{col.lower()}={(row.get(col) or '').strip()}" for col in self._feature_columns
        )
        return f"flow {fields}"
