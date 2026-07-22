"""Drain3 template-mining adapter.

Implements the :class:`~nexguard.domain.ports.TemplateMiner` port. Drain3 mines
log templates incrementally with bounded memory (fixed-depth parse tree), which
suits streaming ingestion. Masking instructions normalize volatile tokens (block
ids, IPs, numbers) so structurally-identical lines collapse to one template and a
stable :class:`EventId` — the same id across restarts when a persistence path is
given.
"""

from __future__ import annotations

from drain3 import TemplateMiner as _Drain3Engine
from drain3.file_persistence import FilePersistence
from drain3.masking import MaskingInstruction
from drain3.template_miner_config import TemplateMinerConfig

from nexguard.domain.detection import TemplateMatch
from nexguard.domain.entities import Template
from nexguard.domain.value_objects import EventId

# Order matters: block ids and IPs are matched before the generic number mask.
_DEFAULT_MASKING = (
    MaskingInstruction(r"blk_-?\d+", "BLOCK_ID"),
    MaskingInstruction(r"(\d{1,3}\.){3}\d{1,3}(:\d+)?", "IP"),
    MaskingInstruction(r"/[\w./-]+", "PATH"),
    MaskingInstruction(r"0x[0-9a-fA-F]+", "HEX"),
    MaskingInstruction(r"\b\d+\b", "NUM"),
)


def _default_config() -> TemplateMinerConfig:
    config = TemplateMinerConfig()
    config.drain_sim_th = 0.4
    config.drain_depth = 4
    config.drain_max_children = 100
    config.drain_max_clusters = 1024  # bounded memory
    config.profiling_enabled = False
    config.masking_instructions = list(_DEFAULT_MASKING)
    return config


class Drain3TemplateMiner:
    """Streaming, incremental log template miner."""

    def __init__(
        self,
        *,
        persistence_path: str | None = None,
        config: TemplateMinerConfig | None = None,
    ) -> None:
        persistence = FilePersistence(persistence_path) if persistence_path else None
        self._engine = _Drain3Engine(
            persistence_handler=persistence, config=config or _default_config()
        )

    def mine(self, line: str) -> TemplateMatch:
        content = line.strip()
        result = self._engine.add_log_message(content)
        cluster_id = int(result["cluster_id"])
        template = str(result["template_mined"])
        extracted = self._engine.extract_parameters(template, content, exact_matching=False)
        parameters = tuple(param.value for param in extracted) if extracted else ()
        return TemplateMatch(event_id=EventId(cluster_id), template=template, parameters=parameters)

    def vocabulary(self) -> list[Template]:
        return [
            Template(
                event_id=EventId(cluster.cluster_id),
                template=cluster.get_template(),
                occurrences=cluster.size,
            )
            for cluster in self._engine.drain.clusters
        ]

    def save_state(self) -> None:
        """Persist the current parse-tree snapshot (no-op without a persistence path)."""
        self._engine.save_state("snapshot")
