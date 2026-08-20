"""
Regression coverage for resource-safety guardrails added to support large
repository imports (backend/services/worker.py).

These protect against a large import silently exhausting disk space, and
verify the timeouts that bound the download/analysis stages are driven by
`backend.config.settings` rather than hard-coded literals — so operators can
raise them for large repositories without editing code.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from backend.config import settings
from backend.services.worker import _ensure_sufficient_disk_space


@pytest.fixture
def restore_min_free_disk_setting():
    original = settings.min_free_disk_mb
    yield
    settings.min_free_disk_mb = original


def test_ensure_sufficient_disk_space_passes_when_plenty_free(tmp_path, restore_min_free_disk_setting):
    settings.min_free_disk_mb = 1  # 1MB — any real filesystem clears this
    _ensure_sufficient_disk_space(tmp_path)  # must not raise


def test_ensure_sufficient_disk_space_raises_when_ceiling_unreachable(tmp_path, restore_min_free_disk_setting):
    # No real disk has this much free space; the check must be driven by the
    # configured setting, not skipped or hard-coded to something reachable.
    actual_free_mb = shutil.disk_usage(tmp_path).free / (1024 * 1024)
    settings.min_free_disk_mb = int(actual_free_mb) + 10_000_000

    with pytest.raises(Exception, match="Insufficient disk space"):
        _ensure_sufficient_disk_space(tmp_path)


def test_repo_import_timeouts_are_configurable_not_hardcoded(restore_min_free_disk_setting):
    # These must be Settings fields (overridable via env/.env), not literals
    # sprinkled through worker.py / github.py.
    assert isinstance(settings.repo_download_timeout_sec, (int, float))
    assert isinstance(settings.repo_analysis_timeout_sec, (int, float))
    assert isinstance(settings.max_repo_size_mb, int)
    assert isinstance(settings.max_repo_file_count, int)

    # Defaults must comfortably admit a large real-world monorepo (GitHub-
    # reported size for microsoft/vscode is ~1.3GB) rather than reproducing
    # the old 500MB / 50,000-file ceiling.
    assert settings.max_repo_size_mb > 1400
    assert settings.max_repo_file_count > 50_000
