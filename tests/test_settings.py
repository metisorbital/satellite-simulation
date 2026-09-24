"""Deployment setting behavior at the writer identity boundary."""

import pytest
from metis_sim.settings import Settings


def test_render_commit_scopes_writer_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give overlapping deployments independent source ownership."""
    monkeypatch.setenv("METIS_SOURCE_ID", "metis-demo")
    monkeypatch.setenv("METIS_SOURCE_ID_PER_COMMIT", "1")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "a" * 40)

    assert Settings.from_env().source_id == "metis-demo-aaaaaaaaaaaa"


def test_render_commit_scope_requires_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject accidental reuse of a source when the deploy identity is absent."""
    monkeypatch.setenv("METIS_SOURCE_ID_PER_COMMIT", "1")
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)

    with pytest.raises(ValueError, match="requires RENDER_GIT_COMMIT"):
        Settings.from_env()
