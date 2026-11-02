"""第1回: 素のLLMに質問するスクリプト。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask            # 質問を省略すると、講座に固有の質問をする
    uv run python -m app.ask --interactive
    uv run python -m app.ask --interactive "LoRAとは何ですか？"
    uv run python -m app.ask --temperature 0.8 "LoRAとは何ですか？"

対話モードでは会話履歴を保ったまま質問を続けられる。どのモードもツールは使わない。
講座に固有のことを聞くと、「分からない」と答えるか、一般論でもっともらしく答える
（講座の実際とは違う）ことを確かめよう。
（第3回で、用語集を検索できるエージェントにして改善する）
"""

import argparse
from collections.abc import Callable
from typing import Protocol

from google import genai
from google.genai import errors, types

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"


class ChatSession(Protocol):
    def send_message(self, message: str) -> types.GenerateContentResponse: ...


def _generation_config(temperature: float | None) -> types.GenerateContentConfig | None:
    if temperature is None:
        return None
    return types.GenerateContentConfig(temperature=temperature)


def _response_text(response: types.GenerateContentResponse) -> str:
    if response.text is None:
        raise RuntimeError("モデルからテキスト応答を取得できませんでした。")
    return response.text


def _print_usage(response: types.GenerateContentResponse) -> None:
    usage = response.usage_metadata
    if usage is None:
        print("[トークン数] 利用量メタデータを取得できませんでした")
    else:
        print(
            f"[トークン数] 入力: {usage.prompt_token_count}, "
            f"出力: {usage.candidates_token_count}"
        )


def ask(question: str, temperature: float | None = None) -> str:
    client = genai.Client(api_key=get_api_key())
    response = client.models.generate_content(
        model=MODEL,
        contents=question,
        config=_generation_config(temperature),
    )

    _print_usage(response)
    return _response_text(response)


def run_interactive(
    chat: ChatSession,
    initial_question: str | None = None,
    input_fn: Callable[[str], str] = input,
) -> None:
    """同じチャットセッションを使って、履歴を保ちながら質問を受け付ける。"""
    if initial_question:
        _send_message(chat, initial_question)

    print("質問を入力してください。終了するには「終了」または Ctrl-D を入力します。")
    while True:
        try:
            question = input_fn("質問> ").strip()
        except EOFError:
            print()
            return

        if question.casefold() in {"終了", "exit", "quit"}:
            print("会話を終了します。")
            return
        if not question:
            continue
        _send_message(chat, question)


def _send_message(chat: ChatSession, question: str) -> None:
    print(f"\n[質問] {question}")
    response = chat.send_message(question)
    _print_usage(response)
    print(_response_text(response))


def main() -> None:
    parser = argparse.ArgumentParser(description="素のLLMに質問する")
    parser.add_argument("question", nargs="?")
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="会話履歴を保ったまま続けて質問する",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        help="回答の揺らぎ（0.0〜2.0）。比較実験に使う",
    )
    args = parser.parse_args()

    print(f"[model] {MODEL}")
    if args.temperature is not None:
        if not 0.0 <= args.temperature <= 2.0:
            parser.error("--temperature は 0.0 以上 2.0 以下を指定してください")
        print(f"[temperature] {args.temperature}")

    try:
        if args.interactive:
            client = genai.Client(api_key=get_api_key())
            chat = client.chats.create(
                model=MODEL,
                config=_generation_config(args.temperature),
            )
            run_interactive(chat, args.question)
        else:
            question = args.question or DEFAULT_QUESTION
            print(f"[質問] {question}\n")
            print(ask(question, args.temperature))
    except errors.APIError as e:
        print(api_error_message(e.code, e.message))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
