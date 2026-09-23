"""Local setup and single-process simulation service commands."""

import argparse
import os
import secrets
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv

from metis_sim.logging import configure_logging
from metis_sim.settings import Settings


def local_credentials() -> Path:
    """Create ignored local credentials once without printing their secret values."""
    directory = Path(".local")
    directory.mkdir(exist_ok=True, mode=0o700)
    path = directory / "runtime.env"
    if not path.exists():
        values = {
            "METIS_SESSION_SECRET": secrets.token_urlsafe(48),
            "METIS_OPERATOR_TOKEN": secrets.token_urlsafe(32),
            "METIS_CONSUMER_TOKEN": secrets.token_urlsafe(32),
            "METIS_EVALUATOR_TOKEN": secrets.token_urlsafe(32),
        }
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write("".join(f"{key}={value}\n" for key, value in values.items()))
    load_dotenv(path)
    return path


def main() -> None:
    """Run explicit setup, migrations, or a localhost mission demonstration."""
    parser = argparse.ArgumentParser(description="Metis satellite simulation")
    parser.add_argument("command", choices=["init", "migrate", "serve", "demo"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--at", type=int, default=0, help="Persist a demo up to this tick and pause (e.g. 18000)"
    )
    parser.add_argument("--config", default="configs/demo.yaml")
    args = parser.parse_args()
    if args.command in {"init", "demo"}:
        path = local_credentials()
        if args.command == "init":
            print(f"Local credentials created/loaded from {path}; secret values are not printed.")
            return
    else:
        load_dotenv(Path(".local/runtime.env"))
    if args.command == "migrate":
        command.upgrade(Config("alembic.ini"), "head")
        print("Database schema is current.")
        return
    if args.command == "demo":
        if args.host not in {"127.0.0.1", "localhost", "::1"}:
            parser.error("Local demo session issuance requires a loopback bind")
        os.environ["METIS_LOCAL_DEMO"] = "1"
        os.environ["METIS_DEMO_CONFIG"] = args.config
        # A user-selected loopback port must remain usable by the browser. An
        # explicit deployment allowlist always takes precedence over this default.
        local_origins = (
            f"http://127.0.0.1:{args.port}",
            f"http://localhost:{args.port}",
            f"http://[::1]:{args.port}",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        )
        os.environ.setdefault("METIS_ORIGINS", ",".join(local_origins))
    configure_logging()
    from metis_sim.api.app import create_app

    app = create_app(Settings.from_env(), demo_at=args.at)
    uvicorn.run(app, host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
