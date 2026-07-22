"""Runtime-adjustable detection configuration.

Settings are immutable (12-factor, env-driven), but the ensemble's operating point
must be tunable at runtime — by an admin via Configuration, or automatically by
recalibration from analyst feedback. This small mutable holder is seeded from
Settings and read by the detection pipeline on every scoring pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexguard.config.settings import Settings


@dataclass
class RuntimeConfig:
    seq_weight: float
    stat_weight: float
    threshold: float

    @classmethod
    def from_settings(cls, settings: Settings) -> RuntimeConfig:
        return cls(
            seq_weight=settings.ensemble_seq_weight,
            stat_weight=settings.ensemble_stat_weight,
            threshold=settings.alert_threshold,
        )
