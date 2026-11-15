"""第3回: エージェントに持たせるツール。

ここに書いた関数の docstring と型ヒントが、そのままモデルへの「ツールの説明文」になる。
説明文を書き換えると、モデルがツールを使うかどうか・どんな引数で呼ぶかが変わる。
"""

import json
import random
from datetime import datetime
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MAX_RESULTS = 3

# 宿題（実装）: 学習の記録の保存先。個人のメモなので .gitignore で共有しない
LEARNING_LOG_DIR = Path(__file__).resolve().parent.parent / "learning_log"
MAX_LOG_CHARS = 10_000


@cache
def load_glossary() -> list[dict]:
    with open(DATA_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["terms"]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "").replace("　", "")


def _names(entry: dict) -> list[str]:
    return [_normalize(entry["term"]), _normalize(entry["id"])] + [
        _normalize(a) for a in entry["aliases"]
    ]


def search_glossary(query: str) -> str:
    """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

    AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
    答える前に使うこと。query には調べたい用語を1つだけ入れる（例: "LoRA"）。
    """
    q = _normalize(query)
    if not q:
        return "検索語が空です。調べたい用語を1つ指定してください。"
    glossary = load_glossary()

    exact = [e for e in glossary if q in _names(e)]
    # 「r」のような短い別名が何にでも当たらないよう、名前側が短いものは除く
    partial = [
        e for e in glossary
        if e not in exact and any(q in n or (len(n) >= 3 and n in q) for n in _names(e))
    ]
    in_definition = [
        e for e in glossary
        if e not in exact and e not in partial and q in _normalize(e["definition"])
    ]
    hits = (exact + partial + in_definition)[:MAX_RESULTS]

    if not hits:
        return f"用語集に「{query}」は見つかりませんでした。"
    return json.dumps(
        [
            {
                "term": e["term"],
                "lecture": e["lecture"],
                "definition": e["definition"],
                "related": e["related"],
            }
            for e in hits
        ],
        ensure_ascii=False,
    )


def get_lecture_summary(lecture: int) -> str:
    """指定した回（1始まりの整数）の講義の要点を返す。

    「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。
    """
    path = DATA_DIR / "lectures" / f"{lecture:02d}.md"
    if not path.exists():
        available = sorted(p.stem for p in (DATA_DIR / "lectures").glob("*.md"))
        return f"第{lecture}回の要点はまだありません。用意されている回: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


def make_quiz(lecture: int) -> str:
    """指定した回（1始まりの整数）の用語から確認問題を1問作り、問題と答えを返す。

    「第2回の内容から確認問題を出して」のように、復習用の問題を求められたときに使う。
    答え（answer）は、利用者が自分で考えたあとに示すこと。
    """
    terms = [e for e in load_glossary() if e["lecture"] == lecture]
    if not terms:
        return f"第{lecture}回の用語は用語集にありません。別の回を指定してください。"
    entry = random.choice(terms)
    return json.dumps(
        {
            "lecture": lecture,
            "term": entry["term"],
            "question": f"「{entry['term']}」とはどういう意味ですか？",
            "answer": entry["definition"],
        },
        ensure_ascii=False,
    )


def save_learning_log(title: str, content: str) -> str:
    """学習の記録を learning_log/ フォルダに Markdown ファイルとして保存する。

    利用者が「今日の学びを記録して」「このやりとりをメモに残して」のように、
    記録の保存をはっきり頼んだときだけ使う。title には記録の短い見出しを、
    content には保存する本文を入れる。ファイルを書き込むので、実行の前に利用者の確認が入る。
    """
    # ファイル名はモデルに決めさせず日時から作る（learning_log/ の外へ書かせないため）
    heading = " ".join(title.split()) or "学習の記録"
    body = content.strip()
    if not body:
        return "保存する本文が空です。記録したい内容を content に入れてください。"
    if len(body) > MAX_LOG_CHARS:
        return f"本文が長すぎます（{len(body)} 文字）。{MAX_LOG_CHARS} 文字以内にまとめてください。"

    now = datetime.now()
    LEARNING_LOG_DIR.mkdir(parents=True, exist_ok=True)
    text = f"# {heading}\n\n記録日時: {now:%Y-%m-%d %H:%M}\n\n{body}\n"
    for n in range(1, 100):
        suffix = "" if n == 1 else f"-{n}"
        path = LEARNING_LOG_DIR / f"{now:%Y%m%d-%H%M%S}{suffix}.md"
        try:
            with open(path, "x", encoding="utf-8") as f:  # "x": 既にあれば上書きせず失敗する
                f.write(text)
        except FileExistsError:
            continue
        return f"learning_log/{path.name} に保存しました。"
    return "同じ時刻の記録が多すぎて保存できませんでした。少し待ってから保存してください。"
