"""NexGuard command-line interface.

Entry point for operating the platform: run the API, seed the demo end-to-end,
initialize the schema, and manage users. Kept dependency-free (argparse) so it
adds no runtime weight.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from nexguard import __version__
from nexguard.config.settings import get_settings
from nexguard.domain.entities import UserRole
from nexguard.interfaces.api.container import Container
from nexguard.interfaces.bootstrap import seed_demo

_DEFAULT_LOG = "tests/fixtures/hdfs/hdfs_sample.log"
_DEFAULT_LABELS = "tests/fixtures/hdfs/anomaly_label.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexguard", description="NexGuard SOC platform CLI")
    parser.add_argument("--version", action="version", version=f"NexGuard {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the API server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    sub.add_parser("init-db", help="create database schema (dev)")

    seed = sub.add_parser("seed", help="seed the demo: ingest, train, detect, create users")
    seed.add_argument("--log", default=_DEFAULT_LOG)
    seed.add_argument("--labels", default=_DEFAULT_LABELS)
    seed.add_argument("--epochs", type=int, default=15)

    user = sub.add_parser("create-user", help="create a user")
    user.add_argument("email")
    user.add_argument("password")
    user.add_argument("--role", choices=[r.value for r in UserRole], default=UserRole.VIEWER.value)

    args = parser.parse_args(argv)

    if args.command == "serve":
        return _serve(args.host, args.port, reload=args.reload)
    if args.command == "init-db":
        return asyncio.run(_init_db())
    if args.command == "seed":
        if not Path(args.log).exists():
            parser.error(f"log file not found: {args.log}")
        return asyncio.run(_seed(args.log, args.labels, args.epochs))
    if args.command == "create-user":
        return asyncio.run(_create_user(args.email, args.password, UserRole(args.role)))
    return 1


def _serve(host: str, port: int, *, reload: bool) -> int:
    import uvicorn

    uvicorn.run(
        "nexguard.interfaces.api.app:app",
        host=host,
        port=port,
        reload=reload,
        factory=False,
    )
    return 0


async def _init_db() -> int:
    container = Container(get_settings())
    await container.database.create_all()
    await container.database.dispose()
    print("schema created")
    return 0


async def _seed(log: str, labels: str, epochs: int) -> int:
    container = Container(get_settings())
    await container.startup()
    try:
        result = await seed_demo(container, log_path=log, label_path=labels, lstm_epochs=epochs)
    finally:
        await container.shutdown()
    if result.skipped:
        print(f"already seeded: {result.alerts_created} alerts present — nothing to do")
        return 0
    anomalies = sum(1 for o in result.outcomes if o.is_anomaly)
    detected = sum(1 for o in result.outcomes if o.is_anomaly and o.alerted)
    print(
        f"seeded: {result.sessions_ingested} sessions, {result.alerts_created} alerts, "
        f"{result.users_created} users | anomaly recall {detected}/{anomalies}"
    )
    return 0


async def _create_user(email: str, password: str, role: UserRole) -> int:
    container = Container(get_settings())
    await container.startup()
    try:
        async with container.database.session() as session:
            user = await container.create_user(session).execute(
                email=email, password=password, role=role
            )
    finally:
        await container.shutdown()
    print(f"created user {user.email} ({user.role.value})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
