"""Transformer-encoder sequence detector (PyTorch).

An interchangeable alternative to the LSTM behind the same
:class:`~nexguard.domain.ports.SequenceDetector` port. Same DeepLog next-event
task, but a self-attention encoder captures long-range dependencies. Because both
variants share ``_sequence``, they are directly comparable in the evaluation
harness. Dropout is disabled for reproducibility.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import torch
from torch import nn

from nexguard.domain.detection import SequenceVerdict
from nexguard.domain.value_objects import EventId
from nexguard.infrastructure.detection import _sequence as seq

_MODEL_TYPE = "transformer"


class _TransformerEncoderModel(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        embed_dim: int,
        nhead: int,
        layers: int,
        dim_feedforward: int,
        window: int,
    ) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim, padding_idx=seq.PAD)
        # Learned positional encoding; context windows are a fixed length.
        self.positional = nn.Parameter(torch.zeros(1, window, embed_dim))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=0.0,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=layers)
        self.fc = nn.Linear(embed_dim, vocab_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        hidden = self.embed(x) + self.positional
        hidden = self.encoder(hidden)
        logits: torch.Tensor = self.fc(hidden[:, -1, :])  # predict from the last position
        return logits


def _build_module(hp: dict[str, int]) -> _TransformerEncoderModel:
    return _TransformerEncoderModel(
        vocab_size=hp["vocab_size"],
        embed_dim=hp["embed_dim"],
        nhead=hp["nhead"],
        layers=hp["layers"],
        dim_feedforward=hp["dim_feedforward"],
        window=hp["window"],
    )


class TransformerSequenceDetector:
    """Next-event-prediction anomaly detector backed by a Transformer encoder."""

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
        nhead: int = 4,
        layers: int = 2,
        dim_feedforward: int = 64,
        epochs: int = 30,
        top_k: int = 5,
        lr: float = 1e-3,
        batch_size: int = 64,
        seed: int = 42,
    ) -> TransformerSequenceDetector:
        if not normal_sequences:
            raise ValueError("cannot fit TransformerSequenceDetector on zero sequences")
        if embed_dim % nhead != 0:
            raise ValueError(f"embed_dim ({embed_dim}) must be divisible by nhead ({nhead})")
        torch.manual_seed(seed)

        id_to_index = seq.build_vocab(normal_sequences)
        hyperparams: dict[str, int] = {
            "vocab_size": seq.RESERVED + len(id_to_index),
            "embed_dim": embed_dim,
            "nhead": nhead,
            "layers": layers,
            "dim_feedforward": dim_feedforward,
            "window": window,
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
    def load(cls, path: str | Path) -> TransformerSequenceDetector:
        meta = seq.read_meta(path)
        hyperparams: dict[str, int] = meta["hyperparams"]
        model = _build_module(hyperparams)
        seq.load_weights(model, path)
        id_to_index = {int(eid): int(idx) for eid, idx in meta["id_to_index"]}
        return cls(
            scorer=seq.SequenceScorer(model, id_to_index, meta["window"], meta["top_k"]),
            hyperparams=hyperparams,
        )
