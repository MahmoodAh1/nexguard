"""Unit tests for the incident-report schema and the evidence contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from nexguard.domain.evidence import (
    EnsembleEvidence,
    Evidence,
    FeatureContribution,
    Provenance,
    SequenceEvidence,
    StatisticalEvidence,
)
from nexguard.domain.report import (
    EvidenceRef,
    IncidentReportPayload,
    MitreHypothesis,
    TimelineEntry,
)
from nexguard.domain.value_objects import EventId, Severity


def _valid_report() -> IncidentReportPayload:
    return IncidentReportPayload(
        summary="Anomalous block lifecycle detected.",
        severity=Severity.HIGH,
        confidence="medium",
        timeline=[
            TimelineEntry(
                timestamp="2026-01-01T00:00:00+00:00", description="write began"
            )
        ],
        affected_components=["blk_-123"],
        evidence_refs=[EvidenceRef(kind="event", ref="9")],
        mitre_hypotheses=[
            MitreHypothesis(
                technique_id="T1078",
                name="Valid Accounts",
                rationale="Unusual write sequence.",
                confidence="low",
            )
        ],
        recommended_investigation_steps=["Review the block's replica set."],
        recommended_containment_actions=["Quarantine the datanode."],
    )


class TestIncidentReportPayload:
    def test_valid_payload_constructs(self) -> None:
        report = _valid_report()
        assert report.severity is Severity.HIGH
        assert report.mitre_hypotheses[0].is_hypothesis is True

    def test_requires_at_least_one_investigation_step(self) -> None:
        with pytest.raises(PydanticValidationError):
            IncidentReportPayload(
                summary="x",
                severity=Severity.LOW,
                confidence="low",
                recommended_investigation_steps=[],
            )

    def test_forbids_unknown_fields(self) -> None:
        with pytest.raises(PydanticValidationError):
            IncidentReportPayload(
                summary="x",
                severity=Severity.LOW,
                confidence="low",
                recommended_investigation_steps=["a"],
                confirmed_technique="T1000",  # type: ignore[call-arg]
            )


class TestMitreHypothesis:
    def test_cannot_be_marked_confirmed(self) -> None:
        # is_hypothesis is Literal[True]; asserting a confirmed technique fails.
        with pytest.raises(PydanticValidationError):
            MitreHypothesis(
                technique_id="T1078",
                name="Valid Accounts",
                rationale="x",
                confidence="low",
                is_hypothesis=False,
            )

    @pytest.mark.parametrize("bad_id", ["1078", "TX078", "T10", "technique-1078"])
    def test_rejects_malformed_technique_id(self, bad_id: str) -> None:
        with pytest.raises(PydanticValidationError):
            MitreHypothesis(
                technique_id=bad_id, name="n", rationale="r", confidence="low"
            )

    def test_accepts_sub_technique_id(self) -> None:
        hypo = MitreHypothesis(
            technique_id="T1078.003", name="n", rationale="r", confidence="high"
        )
        assert hypo.technique_id == "T1078.003"


class TestEvidenceRoundTrip:
    def test_json_round_trip_is_lossless(self) -> None:
        evidence = Evidence(
            sequence=SequenceEvidence(
                anomaly_score=0.91,
                confidence=0.77,
                perplexity=4.2,
                actual_event=EventId(9),
                predicted_topk=[EventId(3), EventId(4)],
                surprising_step_indices=[2],
                suspicious_subsequence=[EventId(5), EventId(9)],
            ),
            statistical=StatisticalEvidence(
                anomaly_score=0.63,
                important_features=[
                    FeatureContribution(
                        event_id=EventId(9), template="write", contribution=0.5
                    )
                ],
            ),
            ensemble=EnsembleEvidence(
                seq_weight=0.6,
                stat_weight=0.4,
                seq_score=0.91,
                stat_score=0.63,
                final_score=0.79,
                threshold=0.5,
                severity=Severity.HIGH,
            ),
            provenance=Provenance(
                session_external_id="blk_1", dataset="hdfs", event_count=3
            ),
        )
        restored = Evidence.from_json_dict(evidence.to_json_dict())
        assert restored == evidence
