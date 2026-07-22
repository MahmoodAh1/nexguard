"""Download full LogHub datasets (HDFS, BGL) for real training / benchmarking.

The bundled fixtures are tiny and deterministic (for tests + demo); this fetches
the full datasets on demand, with optional SHA-256 verification and extraction,
so a benchmark run is reproducible without committing multi-GB binaries (ADR-0005).

Usage:
    python scripts/download_data.py hdfs
    python scripts/download_data.py bgl --out ml/data/raw
    python scripts/download_data.py hdfs --url <mirror-url> --sha256 <hash>

Datasets are published by LogHub (https://github.com/logpai/loghub). URLs may
change over time; override with --url if a default 404s.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _ROOT / "ml" / "data" / "raw"


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    url: str
    archive: str
    sha256: str | None = None  # fill in to enforce verification


# LogHub releases (Zenodo). Override with --url if these move.
_REGISTRY: dict[str, DatasetSpec] = {
    "hdfs": DatasetSpec(
        name="hdfs",
        url="https://zenodo.org/records/8196385/files/HDFS_v1.zip",
        archive="HDFS_v1.zip",
    ),
    "bgl": DatasetSpec(
        name="bgl",
        url="https://zenodo.org/records/8196385/files/BGL.zip",
        archive="BGL.zip",
    ),
}


def _download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")

    def _progress(block_num: int, block_size: int, total: int) -> None:
        if total > 0:
            pct = min(100, block_num * block_size * 100 // total)
            sys.stdout.write(f"\r  {pct:3d}%")
            sys.stdout.flush()

    urllib.request.urlretrieve(
        url, target, _progress
    )
    sys.stdout.write("\n")


def _verify(path: Path, expected_sha256: str) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        raise SystemExit(
            f"checksum mismatch for {path.name}: {actual} != {expected_sha256}"
        )
    print(f"  sha256 verified: {actual}")


def _extract(archive: Path, out_dir: Path) -> None:
    if not zipfile.is_zipfile(archive):
        print(f"  {archive.name} is not a zip; leaving as-is")
        return
    print(f"  extracting {archive.name}")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(out_dir / archive.stem)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=sorted(_REGISTRY))
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--url", default=None, help="override the download URL")
    parser.add_argument("--sha256", default=None, help="expected SHA-256 to verify")
    parser.add_argument("--no-extract", action="store_true")
    args = parser.parse_args()

    spec = _REGISTRY[args.dataset]
    url = args.url or spec.url
    archive_path = args.out / spec.archive

    if not archive_path.exists():
        _download(url, archive_path)
    else:
        print(f"Using cached {archive_path}")

    expected = args.sha256 or spec.sha256
    if expected:
        _verify(archive_path, expected)

    if not args.no_extract:
        _extract(archive_path, args.out)

    print(f"Done. Data under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
