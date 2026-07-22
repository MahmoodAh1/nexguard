"""Shared next-event-prediction machinery for sequence detectors.

Both the LSTM and Transformer detectors are DeepLog-style: they learn to predict
the next event from a window of prior events, and flag a session when the actual
next event repeatedly falls outside the model's top-``k`` predictions. Only the
neural module differs — everything else (vocabulary, windowing, scoring, evidence
assembly, persistence) is shared here so the two variants stay behaviorally
identical and directly comparable.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import torch
from torch import nn

from nexguard.domain.detection import SequenceVerdict
from nexguard.domain.value_objects import EventId

PAD = 0
UNK = 1
RESERVED = 2  # real events are indexed from here
ARTIFACT_VERSION = 2
_EPS = 1e-9


# ── vocabulary + training data ──
def build_vocab(sequences: list[list[EventId]]) -> dict[int, int]:
    unique: dict[int, None] = {}
    for sequence in sequences:
        for event_id in sequence:
            unique.setdefault(int(event_id), None)
    return {eid: RESERVED + offset for offset, eid in enumerate(sorted(unique))}


def build_samples(
    sequences: list[list[EventId]], id_to_index: dict[int, int], window: int
) -> tuple[list[list[int]], list[int]]:
    contexts: list[list[int]] = []
    targets: list[int] = []
    for sequence in sequences:
        indices = [id_to_index.get(int(eid), UNK) for eid in sequence]
        for position, target in enumerate(indices):
            prev = indices[max(0, position - window) : position]
            contexts.append([PAD] * (window - len(prev)) + prev)
            targets.append(target)
    return contexts, targets


def train_module(
    model: nn.Module,
    contexts: list[list[int]],
    targets: list[int],
    *,
    epochs: int,
    lr: float,
    batch_size: int,
) -> None:
    if not targets:
        return
    x = torch.tensor(contexts, dtype=torch.long)
    y = torch.tensor(targets, dtype=torch.long)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    model.train()
    for _ in range(epochs):
        for start in range(0, len(y), batch_size):
            xb = x[start : start + batch_size]
            yb = y[start : start + batch_size]
            optimizer.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optimizer.step()
    model.eval()


# ── scoring ──
class SequenceScorer:
    """Wraps a trained module and turns a session into a :class:`SequenceVerdict`."""

    def __init__(
        self,
        model: nn.Module,
        id_to_index: dict[int, int],
        window: int,
        top_k: int,
    ) -> None:
        self.model = model
        self.model.eval()
        self.id_to_index = id_to_index
        self.window = window
        self.top_k = top_k
        self._index_to_id = {idx: eid for eid, idx in id_to_index.items()}

    def score(self, sequence: Sequence[EventId]) -> SequenceVerdict:
        indices = [self.id_to_index.get(int(eid), UNK) for eid in sequence]
        if not indices:
            return SequenceVerdict(anomaly_score=0.0, confidence=1.0, perplexity=1.0)

        surprising: list[int] = []
        cross_entropies: list[float] = []
        per_step_top1: list[float] = []
        per_step_topk: list[list[int]] = []

        with torch.no_grad():
            for position, target in enumerate(indices):
                context = self._context(indices, position)
                logits = self.model(torch.tensor([context], dtype=torch.long))[0]
                probs = torch.softmax(logits, dim=-1)
                topk = torch.topk(logits, min(self.top_k, logits.shape[-1])).indices.tolist()

                cross_entropies.append(-math.log(float(probs[target]) + _EPS))
                per_step_top1.append(float(probs.max()))
                per_step_topk.append(topk)
                if target == UNK or target not in topk:
                    surprising.append(position)

        num_steps = len(indices)
        # DeepLog semantics: a single surprising step is a strong signal, so the
        # score saturates in the number of surprises rather than diluting by
        # session length (one anomalous event in a long session still scores high).
        anomaly_score = 1.0 - math.exp(-1.5 * len(surprising))
        perplexity = math.exp(sum(cross_entropies) / num_steps)
        flagged = max(range(num_steps), key=lambda i: cross_entropies[i])

        return SequenceVerdict(
            anomaly_score=round(anomaly_score, 6),
            confidence=round(per_step_top1[flagged], 6),
            perplexity=round(perplexity, 6),
            actual_event=EventId(int(sequence[flagged])),
            predicted_topk=self._decode_topk(per_step_topk[flagged]),
            surprising_step_indices=tuple(surprising),
            suspicious_subsequence=tuple(
                EventId(int(e)) for e in sequence[max(0, flagged - 2) : flagged + 1]
            ),
        )

    def _context(self, indices: list[int], position: int) -> list[int]:
        window = indices[max(0, position - self.window) : position]
        return [PAD] * (self.window - len(window)) + window

    def _decode_topk(self, topk_indices: list[int]) -> tuple[EventId, ...]:
        return tuple(
            EventId(self._index_to_id[idx]) for idx in topk_indices if idx in self._index_to_id
        )


# ── persistence ──
def save_artifact(
    scorer: SequenceScorer,
    path: str | Path,
    *,
    model_type: str,
    hyperparams: dict[str, int],
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    torch.save(scorer.model.state_dict(), target)
    meta = {
        "version": ARTIFACT_VERSION,
        "model_type": model_type,
        "id_to_index": [[eid, idx] for eid, idx in scorer.id_to_index.items()],
        "window": scorer.window,
        "top_k": scorer.top_k,
        "hyperparams": hyperparams,
    }
    target.with_suffix(".meta.json").write_text(json.dumps(meta), encoding="utf-8")


def read_meta(path: str | Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        Path(path).with_suffix(".meta.json").read_text(encoding="utf-8")
    )
    return data


def load_weights(model: nn.Module, path: str | Path) -> None:
    # weights_only=True: never unpickle arbitrary objects from the weights file.
    model.load_state_dict(torch.load(Path(path), map_location="cpu", weights_only=True))
    model.eval()
