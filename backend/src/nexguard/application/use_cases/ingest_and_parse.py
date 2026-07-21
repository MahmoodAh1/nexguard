"""Ingest & parse use case.

Turns raw, session-grouped log lines into persisted :class:`Session` entities:
each line is mined into a template + stable ``EventId``, host-like tokens are
captured for later verification, and the mined vocabulary is upserted. It depends
only on ports, so it runs identically over SQLite, Postgres, or in-memory repos.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime

from nexguard.domain.detection import RawSession, TemplateMatch
from nexguard.domain.entities import LogEvent, Session
from nexguard.domain.ports import LogRepository, TemplateMiner, TemplateRepository

_IP = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")


class IngestAndParse:
    """Parse grouped raw sessions and persist them."""

    def __init__(
        self,
        miner: TemplateMiner,
        log_repo: LogRepository,
        template_repo: TemplateRepository | None = None,
    ) -> None:
        self._miner = miner
        self._log_repo = log_repo
        self._template_repo = template_repo

    async def execute(self, sessions: Iterable[RawSession]) -> list[Session]:
        built: list[Session] = []
        for raw in sessions:
            events = [
                LogEvent(
                    event_id=(match := self._miner.mine(line)).event_id,
                    raw=line,
                    line_no=index,
                    params=self._params(match, line),
                    timestamp=self._timestamp_at(raw, index),
                )
                for index, line in enumerate(raw.lines)
            ]
            session = Session(
                external_id=raw.external_id,
                dataset=raw.dataset,
                events=events,
                label=raw.label,
            )
            await self._log_repo.add_session(session)
            built.append(session)

        if self._template_repo is not None:
            await self._template_repo.upsert_many(self._miner.vocabulary())
        return built

    @staticmethod
    def _params(match: TemplateMatch, line: str) -> dict[str, str]:
        params = {f"p{index}": value for index, value in enumerate(match.parameters)}
        for index, ip in enumerate(_IP.findall(line)):
            params[f"ip_{index}"] = ip
        return params

    @staticmethod
    def _timestamp_at(raw: RawSession, index: int) -> datetime | None:
        if index >= len(raw.timestamps):
            return None
        iso = raw.timestamps[index]
        return datetime.fromisoformat(iso) if iso else None
