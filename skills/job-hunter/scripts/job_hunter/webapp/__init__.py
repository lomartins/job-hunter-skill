"""Local-only FastAPI webapp for browsing and triaging tracked jobs."""

from .app import create_app

__all__ = ["create_app"]
