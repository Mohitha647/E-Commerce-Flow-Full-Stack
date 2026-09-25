"""
Ensures the test suite always runs against a fresh, throwaway SQLite file
(never your local dev commerceflow.db), and uses a dedicated Redis DB index
so cache state doesn't leak between test runs. Must set these env vars
BEFORE `app.*` modules are imported anywhere, since app.db creates the
SQLAlchemy engine at import time -- pytest loads conftest.py first, which
is what makes this ordering safe.
"""
import os
import pathlib
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="commerceflow_test_")
_db_path = pathlib.Path(_tmp_dir) / "test.db"

os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_db_path}")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("CACHE_TTL_SECONDS", "5")
