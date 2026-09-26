"""Deployment configuration; credentials never enter physical run manifests."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL


@dataclass(frozen=True)
class Settings:
    """Runtime infrastructure and authentication configuration.

    Parameters
    ----------
    database_url : str
        SQLAlchemy PostgreSQL connection URL.
    use_remote : bool
        Select the fixed Render database when loading environment settings.
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
    use_remote: bool = False
    source_id: str = "metis-simulator-local"
    session_secret: str = ""
    operator_token: str = ""
    consumer_token: str = ""
    evaluator_token: str = ""
    local_demo: bool = False
    public_demo: bool = False
    interactive_public_demo: bool = False
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
        """Load deployment settings from the environment and working-directory .env.

        Returns
        -------
        Settings
            Configuration with an explicitly selected database connection URL.

        Raises
        ------
        ValueError
            If the remote selector is invalid or remote credentials are absent.
        """
        load_dotenv(Path(".env"), override=False, interpolate=False)
        default = cls()
        remote_value = os.getenv("METIS_USE_REMOTE", "0").lower()
        if remote_value not in {"0", "1", "false", "true"}:
            raise ValueError("METIS_USE_REMOTE must be 1, true, 0, or false")
        use_remote = remote_value in {"1", "true"}
        database_url = os.getenv("METIS_DATABASE_URL", default.database_url)
        if use_remote:
            password = os.getenv("METIS_REMOTE_DB_PASSWORD", "")
            if not password:
                raise ValueError("METIS_USE_REMOTE requires METIS_REMOTE_DB_PASSWORD")
            database_url = URL.create(
                "postgresql+psycopg",
                username="metis",
                password=password,
                host="dpg-daqcab7f3r2c73arc260-a.frankfurt-postgres.render.com",
                port=5432,
                database="metis_29je",
                query={"sslmode": "require"},
            ).render_as_string(hide_password=False)
        source_id = os.getenv("METIS_SOURCE_ID", default.source_id)
        if os.getenv("METIS_SOURCE_ID_PER_COMMIT", "0") == "1":
            commit = os.getenv("RENDER_GIT_COMMIT", "")
            if len(commit) != 40 or any(
                character not in "0123456789abcdef" for character in commit
            ):
                raise ValueError("METIS_SOURCE_ID_PER_COMMIT requires RENDER_GIT_COMMIT")
            source_id = f"{source_id[:51]}-{commit[:12]}"
        return cls(
            database_url=database_url,
            use_remote=use_remote,
            source_id=source_id,
            session_secret=os.getenv("METIS_SESSION_SECRET", ""),
            operator_token=os.getenv("METIS_OPERATOR_TOKEN", ""),
            consumer_token=os.getenv("METIS_CONSUMER_TOKEN", ""),
            evaluator_token=os.getenv("METIS_EVALUATOR_TOKEN", ""),
            local_demo=os.getenv("METIS_LOCAL_DEMO", "0") == "1",
            public_demo=os.getenv("METIS_PUBLIC_DEMO", "0") == "1",
            interactive_public_demo=os.getenv("METIS_INTERACTIVE_PUBLIC_DEMO", "0") == "1",
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
