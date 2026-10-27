"""Production configuration must reject missing/placeholder secrets."""
import os
import pytest


def test_production_rejects_missing_secrets(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("INGESTION_TOKEN", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    from app import create_app
    with pytest.raises(RuntimeError) as exc:
        create_app("production")
    msg = str(exc.value)
    assert "SECRET_KEY" in msg
    assert "INGESTION_TOKEN" in msg
    assert "BOOTSTRAP_ADMIN_PASSWORD" in msg


def test_production_rejects_placeholder_secrets(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dev-only-change-me-in-production")
    monkeypatch.setenv("INGESTION_TOKEN", "demo-ingestion-token-change-me")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "ChangeMeImmediately!")
    from app import create_app
    with pytest.raises(RuntimeError):
        create_app("production")


def test_production_accepts_strong_secrets(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a-sufficiently-long-production-secret-key")
    monkeypatch.setenv("INGESTION_TOKEN", "strong-ingestion-token-xyz")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Str0ng-Admin-Pass!")
    from app import create_app
    app = create_app("production")
    assert app.config["SECRET_KEY"].startswith("a-sufficiently")
    assert app.config["DEBUG"] is False


def test_unsafe_next_redirect_ignored(client):
    """External next= URLs must not be followed after login."""
    r = client.post(
        "/auth/login?next=https://evil.example/phish",
        data={"username": "admin", "password": "testadminpass"},
        follow_redirects=False,
    )
    # Should redirect to dashboard, not external site
    assert r.status_code in (302, 303)
    loc = r.headers.get("Location", "")
    assert "evil.example" not in loc
