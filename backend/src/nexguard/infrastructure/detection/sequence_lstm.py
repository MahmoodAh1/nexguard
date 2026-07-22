"""DeepLog-style LSTM sequence detector (PyTorch).

Implements the :class:`~nexguard.domain.ports.SequenceDetector` port. Trained only
on *normal* sessions via next-event prediction, it learns the grammar of
legitimate execution. At inference a session is anomalous when the model is
repeatedly *surprised* — the actual next event falls outside its top-``k``
predictions — quantified by the surprising-step fraction and sequence perplexity.

Weights are saved via ``torch.save`` (loaded with ``weights_only=True``) and
hyperparameters/vocabulary in a sibling JSON file, so loading never unpickles
arbitrary objects.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path

import torch
from torch import nn

from nexguard.domain.detection import SequenceVerdict
from nexguard.domain.value_objects import EventId

_PAD = 0
_UNK = 1
_RESERVED = 2  # real events are indexed from here
_ARTIFACT_VERSION = 1
_EPS = 1e-9


class _DeepLogLSTM(nn.Module):
    def __init__(self, vocab_size: int, embed_dim: int, hidden: int, layers: int) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim, padding_idx=_PAD)
        self.lstm = nn.LSTM(embed_dim, hidden, num_layers=layers, batch_first=True)
        self.fc = nn.Linear(hidden, vocab_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        embedded = self.embed(x)
        output, _ = self.lstm(embedded)
        # predict from the last step's hidden state
        logits: torch.Tensor = self.fc(output[:, -1, :])
        return logits


class LstmSequenceDetector:
    """Next-event-prediction anomaly detector."""

    def __init__(
        self,
        *,
        model: _DeepLogLSTM,
        id_to_index: dict[int, int],
        window: int,
        top_k: int,
        hyperparams: dict[str, int],
    ) -> None:
        self._model = model
        self._model.eval()
        self._id_to_index = id_to_index
        self._index_to_id = {idx: eid for eid, idx in id_to_index.items()}
        self._window = window
        self._top_k = top_k
        self._hyperparams = hyperparams

    # ── training ──
    @classmethod
    def fit(
        cls,
        normal_sequences: list[list[EventId]],
        *,
        window: int = 5,
        embed_dim: int = 32,
        hidden: int = 64,
        layers: int = 1,
        epochs: int = 30,
        top_k: int = 5,
        lr: float = 1e-2,
        batch_size: int = 64,
        seed: int = 42,
    ) -> LstmSequenceDetector:
        if not normal_sequences:
            raise ValueError("cannot fit LstmSequenceDetector on zero sequences")
        torch.manual_seed(seed)

        id_to_index = cls._build_vocab(normal_sequences)
        vocab_size = _RESERVED + len(id_to_index)

        contexts, targets = cls._build_samples(normal_sequences, id_to_index, window)
        model = _DeepLogLSTM(vocab_size, embed_dim, hidden, layers)

        if targets:
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

        return cls(
            model=model,
            id_to_index=id_to_index,
            window=window,
            top_k=top_k,
            hyperparams={
                "vocab_size": vocab_size,
                "embed_dim": embed_dim,
                "hidden": hidden,
                "layers": layers,
            },
        )

    # ── inference ──
    def score(self, sequence: Sequence[EventId]) -> SequenceVerdict:
        indices = [self._id_to_index.get(int(eid), _UNK) for eid in sequence]
        if not indices:
            return SequenceVerdict(anomaly_score=0.0, confidence=1.0, perplexity=1.0)

        surprising: list[int] = []
        cross_entropies: list[float] = []
        per_step_top1: list[float] = []
        per_step_topk: list[list[int]] = []

        with torch.no_grad():
            for position, target in enumerate(indices):
                context = self._context(indices, position)
                logits = self._model(torch.tensor([context], dtype=torch.long))[0]
                probs = torch.softmax(logits, dim=-1)
                topk = torch.topk(logits, min(self._top_k, logits.shape[-1])).indices.tolist()

                cross_entropies.append(-math.log(float(probs[target]) + _EPS))
                per_step_top1.append(float(probs.max()))
                per_step_topk.append(topk)
                if target == _UNK or target not in topk:
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
        window = indices[max(0, position - self._window) : position]
        return [_PAD] * (self._window - len(window)) + window

    def _decode_topk(self, topk_indices: list[int]) -> tuple[EventId, ...]:
        return tuple(
            EventId(self._index_to_id[idx]) for idx in topk_indices if idx in self._index_to_id
        )

    # ── persistence ──
    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self._model.state_dict(), target)
        meta = {
            "version": _ARTIFACT_VERSION,
            "id_to_index": [[eid, idx] for eid, idx in self._id_to_index.items()],
            "window": self._window,
            "top_k": self._top_k,
            "hyperparams": self._hyperparams,
        }
        target.with_suffix(".meta.json").write_text(json.dumps(meta), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> LstmSequenceDetector:
        target = Path(path)
        meta = json.loads(target.with_suffix(".meta.json").read_text(encoding="utf-8"))
        hp = meta["hyperparams"]
        model = _DeepLogLSTM(hp["vocab_size"], hp["embed_dim"], hp["hidden"], hp["layers"])
        # weights_only=True: never unpickle arbitrary objects from the weights file.
        model.load_state_dict(torch.load(target, map_location="cpu", weights_only=True))
        return cls(
            model=model,
            id_to_index={int(eid): int(idx) for eid, idx in meta["id_to_index"]},
            window=meta["window"],
            top_k=meta["top_k"],
            hyperparams=hp,
        )

    # ── helpers ──
    @staticmethod
    def _build_vocab(sequences: list[list[EventId]]) -> dict[int, int]:
        unique: dict[int, None] = {}
        for sequence in sequences:
            for event_id in sequence:
                unique.setdefault(int(event_id), None)
        return {eid: _RESERVED + offset for offset, eid in enumerate(sorted(unique))}

    @classmethod
    def _build_samples(
        cls,
        sequences: list[list[EventId]],
        id_to_index: dict[int, int],
        window: int,
    ) -> tuple[list[list[int]], list[int]]:
        contexts: list[list[int]] = []
        targets: list[int] = []
        for sequence in sequences:
            indices = [id_to_index.get(int(eid), _UNK) for eid in sequence]
            for position, target in enumerate(indices):
                prev = indices[max(0, position - window) : position]
                contexts.append([_PAD] * (window - len(prev)) + prev)
                targets.append(target)
        return contexts, targets
