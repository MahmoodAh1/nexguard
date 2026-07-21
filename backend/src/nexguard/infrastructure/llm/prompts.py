"""Incident-report prompt construction.

Builds the prompt sent to the LLM, embedding a structured **grounding block** —
the exact set of real facts (session id, hosts, timestamps, event ids, the
suspicious subsequence, top statistical features) that the model is permitted to
reference. The natural-language instruction tells the model to cite only these
facts and to treat MITRE techniques as hypotheses. The deterministic stub reads
this same block, so what a report is grounded in and what it is verified against
are one and the same.
"""

from __future__ import annotations

import json

from nexguard.domain.entities import Alert, Session
from nexguard.domain.report import IncidentReportPayload
from nexguard.domain.verification import host_tokens

_GROUNDING_START = "=== EVIDENCE (JSON) ==="
_GROUNDING_END = "=== END EVIDENCE ==="


def build_grounding(alert: Alert, session: Session) -> dict[str, object]:
    """The machine-readable facts a report may reference."""
    evidence = alert.evidence
    time_range = session.time_range
    timestamps = sorted(
        {e.timestamp.isoformat() for e in session.events if e.timestamp is not None}
    )
    return {
        "severity": evidence.ensemble.severity.value,
        "final_score": round(evidence.ensemble.final_score, 4),
        "session_external_id": session.external_id,
        "dataset": session.dataset,
        "event_count": session.event_count,
        "event_ids": sorted({int(e) for e in session.unique_event_ids()}),
        "hosts": sorted(host_tokens(session)),
        "timestamps": timestamps,
        "time_range": {
            "start": time_range.start.isoformat() if time_range else None,
            "end": time_range.end.isoformat() if time_range else None,
        },
        "suspicious_subsequence": [
            int(e) for e in evidence.sequence.suspicious_subsequence
        ],
        "predicted_topk": [int(e) for e in evidence.sequence.predicted_topk],
        "actual_event": (
            int(evidence.sequence.actual_event)
            if evidence.sequence.actual_event is not None
            else None
        ),
        "surprising_steps": list(evidence.sequence.surprising_step_indices),
        "perplexity": evidence.sequence.perplexity,
        "important_features": [
            {
                "event_id": int(f.event_id),
                "template": f.template,
                "contribution": f.contribution,
            }
            for f in evidence.statistical.important_features
        ],
    }


def extract_grounding(prompt: str) -> dict[str, object]:
    """Recover the grounding block a prompt was built with (used by the stub)."""
    start = prompt.index(_GROUNDING_START) + len(_GROUNDING_START)
    end = prompt.index(_GROUNDING_END)
    return json.loads(prompt[start:end].strip())  # type: ignore[no-any-return]


def build_report_prompt(alert: Alert, session: Session) -> str:
    grounding = build_grounding(alert, session)
    schema = IncidentReportPayload.json_schema_str()
    return f"""You are a senior SOC analyst assistant for NexGuard. Draft a structured incident
report for the anomalous session below. You MUST follow these rules:

1. Reference ONLY facts present in the EVIDENCE block. Do not invent hosts,
   timestamps, event ids, or components. Every citation must be verifiable.
2. MITRE ATT&CK techniques are HYPOTHESES, never confirmed facts. Mark each one
   accordingly and explain your reasoning.
3. Be precise and actionable. Recommend concrete investigation and containment
   steps for a Hadoop/HDFS environment.
4. Return ONLY a single JSON object that conforms to the schema. No prose.

{_GROUNDING_START}
{json.dumps(grounding, indent=2)}
{_GROUNDING_END}

JSON SCHEMA:
{schema}
"""
