"""宿題（実装）: 承認付きツール save_learning_log のテスト（LLM も API キーも使わない）。

保存は取り消しにくい操作なので、モデルが呼んでもすぐには実行されない。
利用者が承認したときだけ learning_log/ に書き込まれることを確かめる。
"""

import pytest
from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent, ask_approval, run_with_approval

SAVE_TOOL = "save_learning_log"

# log_dir（保存先の一時フォルダ）は tests/conftest.py で全テストに差し込まれる


def _returns(result, tool_name):
    return [
        p
        for m in result.all_messages()
        for p in m.parts
        if isinstance(p, ToolReturnPart) and p.tool_name == tool_name
    ]


# --- ツール単体 ---


def test_save_writes_markdown_file(log_dir):
    message = tools.save_learning_log("LoRA の復習", "低ランク行列だけを学習する。")
    files = list(log_dir.glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert text.startswith("# LoRA の復習\n")
    assert "低ランク行列だけを学習する。" in text
    assert files[0].name in message


def test_save_does_not_overwrite_existing_log(log_dir):
    tools.save_learning_log("1つ目", "a")
    tools.save_learning_log("2つ目", "b")
    assert len(list(log_dir.glob("*.md"))) == 2


def test_save_keeps_title_on_one_line(log_dir):
    tools.save_learning_log("見出し\n# 偽の見出し", "本文")
    text = next(log_dir.glob("*.md")).read_text(encoding="utf-8")
    assert text.splitlines()[0] == "# 見出し # 偽の見出し"


def test_save_rejects_empty_content(log_dir):
    assert "空" in tools.save_learning_log("見出し", "  \n ")
    assert not log_dir.exists()


def test_save_rejects_too_long_content(log_dir):
    assert "長すぎ" in tools.save_learning_log("見出し", "あ" * (tools.MAX_LOG_CHARS + 1))
    assert not log_dir.exists()


# --- エージェント経由（承認の流れ） ---


def test_save_waits_for_approval_and_writes_nothing_yet(log_dir):
    model = TestModel(call_tools=[SAVE_TOOL])
    with agent.override(model=model):
        result = agent.run_sync("今日の学びを保存して")

    assert isinstance(result.output, DeferredToolRequests)
    assert [c.tool_name for c in result.output.approvals] == [SAVE_TOOL]
    assert _returns(result, SAVE_TOOL) == []  # ツール本体はまだ実行されていない
    assert not log_dir.exists()


def test_approved_save_writes_the_log(log_dir):
    asked = []

    def approve(call: ToolCallPart) -> bool:
        asked.append(call.tool_name)
        return True

    result = run_with_approval(
        agent, "今日の学びを保存して", TestModel(call_tools=[SAVE_TOOL]), confirm=approve
    )

    assert asked == [SAVE_TOOL]
    assert len(list(log_dir.glob("*.md"))) == 1
    assert isinstance(result.output, str)
    assert "保存しました" in str(_returns(result, SAVE_TOOL)[0].content)


def test_denied_save_writes_nothing_and_tells_the_model(log_dir):
    result = run_with_approval(
        agent, "今日の学びを保存して", TestModel(call_tools=[SAVE_TOOL]), confirm=lambda call: False
    )

    assert not log_dir.exists()
    assert isinstance(result.output, str)
    returns = _returns(result, SAVE_TOOL)
    assert returns and "許可しませんでした" in str(returns[0].content)


# --- CLI の確認プロンプト ---


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("y", True), ("Yes", True), ("n", False), ("", False)],
)
def test_ask_approval_accepts_only_yes(monkeypatch, typed, expected):
    monkeypatch.setattr("builtins.input", lambda prompt: typed)
    call = ToolCallPart(SAVE_TOOL, {"title": "t", "content": "c"})
    assert ask_approval(call) is expected


def test_ask_approval_denies_when_input_is_closed(monkeypatch):
    def closed(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", closed)
    assert ask_approval(ToolCallPart(SAVE_TOOL, {"title": "t", "content": "c"})) is False
