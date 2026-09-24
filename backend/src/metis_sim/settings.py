"""Deployment configuration; credentials never enter physical run manifests."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime infrastructure and authentication configuration.

    Parameters
    ----------
    database_url : str
        SQLAlchemy PostgreSQL connection URL.
    session_secret : str
        Secret signing sessions and durable opaque cursors.
    operator_token, consumer_token, evaluator_token : str
        Independent deployment-issued credentials; never sent to the browser.
    local_demo : bool
        Explicitly enable loopback-only prepared-run session issuance.
    public_demo : bool
        Explicitly enable a shared, read-only HTTPS demo.
    public_viewer_limit : int
        Maximum simultaneous public demo visual streams per process.
    """

    database_url: str = "postgresql+psycopg://metis:metis-local@127.0.0.1:55432/metis"
    source_id: str = "metis-simulator-local"
    session_secret: str = ""
    operator_token: str = ""
    consumer_token: str = ""
    evaluator_token: str = ""
    local_demo: bool = False
    public_demo: bool = False
    public_viewer_limit: int = 5
    cookie_secure: bool = False
    session_lifetime_s: int = 7200
    origins: tuple[str, ...] = (
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    frontend_path: Path = field(default_factory=lambda: Path("frontend/build/web"))
    demo_config: Path = field(default_factory=lambda: Path("configs/demo.yaml"))
    minimum_free_bytes: int = 256 * 1024 * 1024
    storage_quota_bytes: int = 5 * 1024 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        """Load explicit deployment settings from environment variables."""
        default = cls()
        source_id = os.getenv("METIS_SOURCE_ID", default.source_id)
        if os.getenv("METIS_SOURCE_ID_PER_COMMIT", "0") == "1":
            commit = os.getenv("RENDER_GIT_COMMIT", "")
            if len(commit) != 40 or any(
                character not in "0123456789abcdef" for character in commit
            ):
                raise ValueError("METIS_SOURCE_ID_PER_COMMIT requires RENDER_GIT_COMMIT")
            source_id = f"{source_id[:51]}-{commit[:12]}"
        return cls(
            database_url=os.getenv("METIS_DATABASE_URL", default.database_url),
            source_id=source_id,
            session_secret=os.getenv("METIS_SESSION_SECRET", ""),
            operator_token=os.getenv("METIS_OPERATOR_TOKEN", ""),
            consumer_token=os.getenv("METIS_CONSUMER_TOKEN", ""),
            evaluator_token=os.getenv("METIS_EVALUATOR_TOKEN", ""),
            local_demo=os.getenv("METIS_LOCAL_DEMO", "0") == "1",
            public_demo=os.getenv("METIS_PUBLIC_DEMO", "0") == "1",
            public_viewer_limit=max(1, int(os.getenv("METIS_PUBLIC_VIEWER_LIMIT", "5"))),
            cookie_secure=os.getenv("METIS_COOKIE_SECURE", "0") == "1",
            origins=tuple(os.getenv("METIS_ORIGINS", ",".join(default.origins)).split(",")),
            frontend_path=Path(os.getenv("METIS_FRONTEND_PATH", str(default.frontend_path))),
            demo_config=Path(os.getenv("METIS_DEMO_CONFIG", str(default.demo_config))),
            minimum_free_bytes=int(
                os.getenv("METIS_MINIMUM_FREE_BYTES", str(default.minimum_free_bytes))
            ),
            storage_quota_bytes=int(
                os.getenv("METIS_STORAGE_QUOTA_BYTES", str(default.storage_quota_bytes))
            ),
        )
