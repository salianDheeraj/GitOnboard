"""
Regression coverage for large-repository import support.

Root cause under test: `backend/services/github.py` used to hard-code a
500MB repo-size ceiling and a 50,000-file extraction ceiling, and ran ZIP
extraction as fully synchronous work directly awaited on the single asyncio
event loop the backend process runs on (services/queue.py schedules jobs via
asyncio.create_task on that same loop, and the Dockerfile starts a single
uvicorn worker). For a multi-hundred-MB archive, that extraction would stall
every other request/websocket the backend was serving for its entire
duration.

These tests verify, without ever hard-coding a repository name or a specific
byte threshold:
  * the size/file-count ceilings are driven by `backend.config.settings`,
    not literals, and can be raised to admit large repositories
  * ZIP extraction preserves dotfiles and still excludes generated/vendor
    directories (the same invariant test_worktree_dotfile_consistency.py
    protects for the scanner/worktree-provisioner paths)
  * extraction actually runs off the event loop, so a slow extraction does
    not starve concurrently scheduled work
"""
from __future__ import annotations

import asyncio
import io
import time
import zipfile
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from backend.config import settings
import backend.services.github as github_module
from backend.services.github import _extract_zipball, check_repo_limits, download_repo_zipball


def _build_zip_bytes(root_folder: str, files: dict) -> bytes:
    """Builds an in-memory GitHub-zipball-shaped archive: every entry is
    nested under `root_folder`, mirroring what GitHub's zipball endpoint
    actually returns."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{root_folder}/", "")
        for rel_path, content in files.items():
            zf.writestr(f"{root_folder}/{rel_path}", content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# check_repo_limits: config-driven, not hard-coded
# ---------------------------------------------------------------------------

def _repo_metadata_transport(size_kb: int) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 999, "default_branch": "main", "size": size_kb})

    return httpx.MockTransport(handler)


@pytest.fixture
def restore_repo_limit_settings():
    original_size = settings.max_repo_size_mb
    yield
    settings.max_repo_size_mb = original_size


async def test_check_repo_limits_rejects_above_configured_ceiling(monkeypatch, restore_repo_limit_settings):
    settings.max_repo_size_mb = 10  # 10MB ceiling for this test only

    async def fake_get_client(token=None):
        return httpx.AsyncClient(transport=_repo_metadata_transport(size_kb=20 * 1024))

    monkeypatch.setattr(github_module, "get_github_client", fake_get_client)

    with pytest.raises(HTTPException) as exc_info:
        await check_repo_limits("owner", "repo")

    assert exc_info.value.status_code == 400
    # The message must reflect the *configured* ceiling, not a hard-coded one.
    assert "10MB" in exc_info.value.detail


async def test_check_repo_limits_admits_large_repo_once_ceiling_is_raised(monkeypatch, restore_repo_limit_settings):
    # A repository well above the old hard-coded 500MB literal must be
    # importable once the ceiling is configured to allow it.
    settings.max_repo_size_mb = 5000
    large_size_kb = 1400 * 1024  # ~1.4GB, in the ballpark of a large real monorepo

    async def fake_get_client(token=None):
        return httpx.AsyncClient(transport=_repo_metadata_transport(size_kb=large_size_kb))

    monkeypatch.setattr(github_module, "get_github_client", fake_get_client)

    result = await check_repo_limits("owner", "repo")
    assert result["size_kb"] == large_size_kb


# ---------------------------------------------------------------------------
# _extract_zipball: dotfiles, generated-dir exclusion, configurable file cap
# ---------------------------------------------------------------------------

def test_extract_zipball_preserves_dotfiles_and_excludes_generated_dirs(tmp_path):
    root_folder = "acme-widgets-abc123"
    files = {
        "README.md": "# widgets\n",
        ".gitignore": "*.pyc\n",
        ".github/workflows/ci.yml": "name: ci\n",
        "src/main.py": "def main(): pass\n",
        "node_modules/leftpad/index.js": "module.exports = {};\n",
        "dist/bundle.js": "console.log(1);\n",
    }
    zip_path = tmp_path / "repo.zip"
    zip_path.write_bytes(_build_zip_bytes(root_folder, files))

    target_dir = tmp_path / "extracted"
    target_dir.mkdir()

    file_count = _extract_zipball(str(zip_path), str(target_dir), max_file_count=1000)

    extracted = set()
    for p in target_dir.rglob("*"):
        if p.is_file():
            extracted.add(str(p.relative_to(target_dir)).replace("\\", "/"))

    assert extracted == {"README.md", ".gitignore", ".github/workflows/ci.yml", "src/main.py"}
    assert file_count == len(extracted)


def test_extract_zipball_enforces_configurable_file_count_ceiling(tmp_path):
    root_folder = "big-repo-def456"
    # Build a fixture whose file count is derived from the limit itself, so
    # nothing here is a hard-coded magic number like the old 50,000 literal.
    small_max = 5
    files = {f"pkg/module_{i}.py": f"x = {i}\n" for i in range(small_max + 3)}
    zip_path = tmp_path / "repo.zip"
    zip_path.write_bytes(_build_zip_bytes(root_folder, files))

    target_dir = tmp_path / "extracted"
    target_dir.mkdir()

    with pytest.raises(HTTPException) as exc_info:
        _extract_zipball(str(zip_path), str(target_dir), max_file_count=small_max)

    assert exc_info.value.status_code == 400
    assert f"{small_max:,}" in exc_info.value.detail


def test_extract_zipball_admits_file_count_within_configured_ceiling(tmp_path):
    root_folder = "ok-repo-ghi789"
    generous_max = 50
    files = {f"pkg/module_{i}.py": f"x = {i}\n" for i in range(generous_max - 5)}
    zip_path = tmp_path / "repo.zip"
    zip_path.write_bytes(_build_zip_bytes(root_folder, files))

    target_dir = tmp_path / "extracted"
    target_dir.mkdir()

    file_count = _extract_zipball(str(zip_path), str(target_dir), max_file_count=generous_max)
    assert file_count == len(files)


# ---------------------------------------------------------------------------
# download_repo_zipball: extraction must not block the event loop
# ---------------------------------------------------------------------------

async def test_download_repo_zipball_offloads_extraction_off_event_loop(monkeypatch, tmp_path):
    root_folder = "slow-repo-jkl012"
    zip_bytes = _build_zip_bytes(root_folder, {"README.md": "hi\n"})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/zipball/main"):
            return httpx.Response(200, content=zip_bytes)
        if "/commits/" in request.url.path:
            return httpx.Response(200, json={"sha": "deadbeef", "commit": {"author": {"date": "2026-01-01"}}})
        return httpx.Response(404)

    async def fake_get_client(token=None):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(github_module, "get_github_client", fake_get_client)

    # Simulate a slow, CPU/disk-bound extraction with a blocking sleep. This
    # is the discriminator: a coroutine that `await`s a truly-offloaded
    # blocking call runs *concurrently* with other scheduled work, so total
    # wall time for [download || heartbeat] converges toward max(their
    # durations). If download_repo_zipball ever regresses to awaiting this
    # blocking work directly instead of via asyncio.to_thread, nothing else
    # can run until it returns, so total wall time converges toward their
    # *sum* instead. A tick-count assertion can't tell these apart (the
    # heartbeat still eventually reaches 10 ticks either way, just serially
    # after extraction instead of alongside it) — wall-clock time can.
    extract_duration_sec = 0.25
    heartbeat_duration_sec = 0.3  # 10 * 0.03s

    def slow_extract(zip_path, target_dir, max_file_count):
        time.sleep(extract_duration_sec)
        return 1

    monkeypatch.setattr(github_module, "_extract_zipball", slow_extract)

    async def heartbeat():
        for _ in range(10):
            await asyncio.sleep(0.03)

    target_dir = tmp_path / "target"
    start = time.monotonic()
    download_task = asyncio.create_task(
        download_repo_zipball("owner", "repo", "main", str(target_dir), token=None)
    )
    heartbeat_task = asyncio.create_task(heartbeat())

    result = await download_task
    await heartbeat_task
    elapsed = time.monotonic() - start

    assert result["file_count"] == 1
    assert result["commit_info"]["hash"] == "deadbeef"
    # Concurrent execution converges toward max(0.25, 0.3) = 0.3s; blocked
    # (serial) execution converges toward their sum = 0.55s. The midpoint is
    # a comfortable, non-flaky cutoff between the two regimes.
    serial_sum = extract_duration_sec + heartbeat_duration_sec
    concurrent_max = max(extract_duration_sec, heartbeat_duration_sec)
    assert elapsed < (serial_sum + concurrent_max) / 2, (
        f"extraction appears to have blocked the event loop: elapsed={elapsed:.3f}s"
    )
