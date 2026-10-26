"""app.ask のテスト（LLMもAPIキーも使わない）。"""

from types import SimpleNamespace

from app.ask import _generation_config, run_interactive


class FakeChat:
    def __init__(self):
        self.questions = []

    def send_message(self, message):
        self.questions.append(message)
        return SimpleNamespace(
            text=f"{message}への回答",
            usage_metadata=None,
        )


def test_interactive_chat_uses_same_session_for_follow_up_questions(capsys):
    chat = FakeChat()
    questions = iter(["LoRAとは？", "それの用途は？", "終了"])

    run_interactive(chat, input_fn=lambda _: next(questions))

    assert chat.questions == ["LoRAとは？", "それの用途は？"]
    output = capsys.readouterr().out
    assert "LoRAとは？への回答" in output
    assert "それの用途は？への回答" in output
    assert "会話を終了します。" in output


def test_generation_config_uses_requested_temperature():
    assert _generation_config(0.7).temperature == 0.7
    assert _generation_config(None) is None
