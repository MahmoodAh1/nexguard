"""DeepLog-style LSTM sequence detector (PyTorch).

Implements the :class:`~nexguard.domain.ports.SequenceDetector` port. Trained only
on *normal* sessions via next-event prediction, it learns the grammar of legitimate
execution; a session is anomalous when the model is repeatedly surprised. All the
shared machinery (vocab, windowing, scoring, persistence) lives in ``_sequence``;
this module only defines the LSTM network and the fit/load wiring.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import torch
from torch import nn

from nexguard.domain.detection import SequenceVerdict
from nexguard.domain.value_objects import EventId
from nexguard.infrastructure.detection import _sequence as seq

_MODEL_TYPE = "lstm"


class _DeepLogLSTM(nn.Module):
    def __init__(self, vocab_size: int, embed_dim: int, hidden: int, layers: int) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim, padding_idx=seq.PAD)
        self.lstm = nn.LSTM(embed_dim, hidden, num_layers=layers, batch_first=True)
        self.fc = nn.Linear(hidden, vocab_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        embedded = self.embed(x)
        output, _ = self.lstm(embedded)
        logits: torch.Tensor = self.fc(output[:, -1, :])  # predict from last hidden state
        return logits


def _build_module(hp: dict[str, int]) -> _DeepLogLSTM:
    return _DeepLogLSTM(hp["vocab_size"], hp["embed_dim"], hp["hidden"], hp["layers"])


class LstmSequenceDetector:
    """Next-event-prediction anomaly detector backed by an LSTM."""

    def __init__(self, *, scorer: seq.SequenceScorer, hyperparams: dict[str, int]) -> None:
        self._scorer = scorer
        self._hyperparams = hyperparams

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

        id_to_index = seq.build_vocab(normal_sequences)
        hyperparams: dict[str, int] = {
            "vocab_size": seq.RESERVED + len(id_to_index),
            "embed_dim": embed_dim,
            "hidden": hidden,
            "layers": layers,
        }
        contexts, targets = seq.build_samples(normal_sequences, id_to_index, window)
        model = _build_module(hyperparams)
        seq.train_module(model, contexts, targets, epochs=epochs, lr=lr, batch_size=batch_size)

        return cls(
            scorer=seq.SequenceScorer(model, id_to_index, window, top_k),
            hyperparams=hyperparams,
        )

    def score(self, sequence: Sequence[EventId]) -> SequenceVerdict:
        return self._scorer.score(sequence)

    def save(self, path: str | Path) -> None:
        seq.save_artifact(self._scorer, path, model_type=_MODEL_TYPE, hyperparams=self._hyperparams)

    @classmethod
    def load(cls, path: str | Path) -> LstmSequenceDetector:
        meta = seq.read_meta(path)
        hyperparams: dict[str, int] = meta["hyperparams"]
        model = _build_module(hyperparams)
        seq.load_weights(model, path)
        id_to_index = {int(eid): int(idx) for eid, idx in meta["id_to_index"]}
        return cls(
            scorer=seq.SequenceScorer(model, id_to_index, meta["window"], meta["top_k"]),
            hyperparams=hyperparams,
        )
