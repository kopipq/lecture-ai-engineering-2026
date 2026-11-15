"""テスト全体の共通設定。"""

import pytest

from app import tools


@pytest.fixture(autouse=True)
def log_dir(tmp_path, monkeypatch):
    """どのテストも本物の learning_log/ に書き込まないよう、保存先を一時フォルダに差し替える。"""
    path = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", path)
    return path
