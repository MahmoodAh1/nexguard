"""Generate a small, realistic, LABELED HDFS log sample (deterministic).

Produces a fixture that mirrors the structure of the real LogHub HDFS dataset:
normal blocks follow the standard allocate -> receive -> respond -> receipt ->
stored lifecycle; anomalous blocks inject a realistic fault (write exception,
premature deletion, redundant/duplicate storage, or a missing responder). Because
it is seeded, the output is byte-for-byte reproducible.

Usage:
    python scripts/generate_hdfs_sample.py [--normal 60] [--anomalous 10] [--out DIR]

The full dataset is fetched separately via scripts/download_data.py (ADR-0005).
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

_DEFAULT_OUT = Path("backend/tests/fixtures/hdfs")
_DATE = "081109"


def _ip(rng: random.Random) -> str:
    return f"10.250.{rng.randint(1, 30)}.{rng.randint(1, 254)}"


class _Clock:
    def __init__(self) -> None:
        self._seconds = 20 * 3600  # 20:00:00

    def tick(self, rng: random.Random) -> str:
        self._seconds += rng.randint(0, 3)
        h, rem = divmod(self._seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{_DATE} {h % 24:02d}{m:02d}{s:02d}"


def _line(ts: str, thread: int, comp: str, message: str) -> str:
    return f"{ts} {thread} INFO {comp}: {message}"


def _normal_block(block_id: str, rng: random.Random, clock: _Clock) -> list[str]:
    replicas = [_ip(rng) for _ in range(3)]
    size = rng.choice([67108864, 33554432, 11194756, 91011])
    path = f"/user/root/rand{rng.randint(1, 9)}/_temporary/_task_{rng.randint(100000, 999999)}"
    lines = [
        _line(
            clock.tick(rng),
            rng.randint(10, 999),
            "dfs.FSNamesystem",
            f"BLOCK* NameSystem.allocateBlock: {path} {block_id}",
        ),
    ]
    for ip in replicas:
        lines.append(
            _line(
                clock.tick(rng),
                rng.randint(10, 999),
                "dfs.DataNode$DataXceiver",
                f"Receiving block {block_id} src: /{ip}:{rng.randint(40000, 59999)} "
                f"dest: /{ip}:50010",
            )
        )
    for responder in range(len(replicas)):
        lines.append(
            _line(
                clock.tick(rng),
                rng.randint(10, 999),
                "dfs.DataNode$PacketResponder",
                f"PacketResponder {responder} for block {block_id} terminating",
            )
        )
    for ip in replicas:
        lines.append(
            _line(
                clock.tick(rng),
                rng.randint(10, 999),
                "dfs.DataNode$DataXceiver",
                f"Received block {block_id} of size {size} from /{ip}",
            )
        )
    for ip in replicas:
        lines.append(
            _line(
                clock.tick(rng),
                rng.randint(10, 999),
                "dfs.FSNamesystem",
                f"BLOCK* NameSystem.addStoredBlock: blockMap updated: {ip}:50010 "
                f"is added to {block_id} size {size}",
            )
        )
    return lines


def _anomalous_block(block_id: str, rng: random.Random, clock: _Clock) -> list[str]:
    """A normal-ish prefix with an injected fault that breaks the expected lifecycle."""
    lines = _normal_block(block_id, rng, clock)
    fault = rng.choice(["exception", "delete", "redundant", "missing_responder"])
    if fault == "exception":
        ip = _ip(rng)
        lines.insert(
            2,
            _line(
                clock.tick(rng),
                rng.randint(10, 999),
                "dfs.DataNode$DataXceiver",
                f"writeBlock {block_id} received exception java.io.IOException: "
                f"Connection reset by peer while writing to /{ip}:50010",
            ),
        )
    elif fault == "delete":
        lines.append(
            _line(
                clock.tick(rng),
                rng.randint(10, 999),
                "dfs.FSNamesystem",
                f"BLOCK* NameSystem.delete: {block_id} is added to invalidSet of /{_ip(rng)}:50010",
            ),
        )
        lines.append(
            _line(
                clock.tick(rng),
                rng.randint(10, 999),
                "dfs.DataNode",
                f"Deleting block {block_id} file /var/hadoop/dfs/data/current/{block_id}",
            ),
        )
    elif fault == "redundant":
        ip = _ip(rng)
        for _ in range(3):
            lines.append(
                _line(
                    clock.tick(rng),
                    rng.randint(10, 999),
                    "dfs.FSNamesystem",
                    f"BLOCK* NameSystem.addStoredBlock: Redundant addStoredBlock request "
                    f"received for {block_id} on {ip}:50010",
                ),
            )
    else:  # missing_responder: drop the responder events entirely
        lines = [ln for ln in lines if "PacketResponder" not in ln]
    return lines


def generate(
    normal: int, anomalous: int, seed: int = 1337
) -> tuple[str, list[tuple[str, bool]]]:
    rng = random.Random(seed)
    clock = _Clock()
    labels: list[tuple[str, bool]] = []
    all_lines: list[str] = []

    plan = ["normal"] * normal + ["anomaly"] * anomalous
    rng.shuffle(plan)
    counter = 0
    for kind in plan:
        counter += 1
        block_id = (
            f"blk_{rng.randint(-9_000_000_000_000_000_000, 9_000_000_000_000_000_000)}"
        )
        if kind == "normal":
            all_lines.extend(_normal_block(block_id, rng, clock))
            labels.append((block_id, False))
        else:
            all_lines.extend(_anomalous_block(block_id, rng, clock))
            labels.append((block_id, True))
    return "\n".join(all_lines) + "\n", labels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normal", type=int, default=60)
    parser.add_argument("--anomalous", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    log_text, labels = generate(args.normal, args.anomalous, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "hdfs_sample.log").write_text(log_text, encoding="utf-8")

    label_lines = ["BlockId,Label"]
    label_lines += [
        f"{bid},{'Anomaly' if is_anom else 'Normal'}" for bid, is_anom in labels
    ]
    (args.out / "anomaly_label.csv").write_text(
        "\n".join(label_lines) + "\n", encoding="utf-8"
    )

    anomalies = sum(1 for _, a in labels if a)
    print(
        f"Wrote {len(labels)} blocks ({anomalies} anomalous) to {args.out}/hdfs_sample.log"
    )


if __name__ == "__main__":
    main()
