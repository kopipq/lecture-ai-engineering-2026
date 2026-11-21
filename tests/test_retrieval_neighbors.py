"""第5回 宿題（実装）: 検索結果に前後のページを付ける処理のテスト。APIは呼ばない。"""

import json

import pytest

from app import retrieval, tools


def _page(document_id: str, number: int, section: str = "章") -> dict:
    return {"page_id": f"{document_id}-p{number:03d}", "document_id": document_id,
            "lecture": int(document_id[3:5]), "document_title": document_id,
            "section": section, "title": f"{document_id} p.{number}",
            "page": number, "content": f"{document_id} p.{number} の本文"}


@pytest.fixture
def pages():
    # lec01 は 1〜4 ページ（2 ページ目と 3 ページ目の間で章が変わる）、lec02 は 1〜3 ページ
    lec01 = [_page("lec01-main", n, "章A" if n <= 2 else "章B") for n in range(1, 5)]
    lec02 = [_page("lec02-main", n) for n in range(1, 4)]
    return lec01 + lec02


def _hit(page: dict, distance: float) -> dict:
    return {**page, "distance": distance}


def _ids(results: list[dict]) -> list[str]:
    return [r["page_id"] for r in results]


def test_adds_previous_and_next_page_around_a_hit(pages):
    hits = [_hit(pages[1], 0.1)]  # lec01 p.2

    results = retrieval.expand_neighbors(hits, pages, window=1)

    assert _ids(results) == ["lec01-main-p001", "lec01-main-p002", "lec01-main-p003"]
    assert [r["role"] for r in results] == ["neighbor", "hit", "neighbor"]
    assert results[0]["neighbor_of"] == results[2]["neighbor_of"] == "lec01-main-p002"
    assert results[1]["distance"] == 0.1
    assert results[0]["content"] == "lec01-main p.1 の本文"


def test_crosses_sections_but_not_documents(pages):
    last_of_lec01, first_of_lec02 = pages[3], pages[4]

    results = retrieval.expand_neighbors(
        [_hit(last_of_lec01, 0.1), _hit(first_of_lec02, 0.2)], pages, window=1)

    # 章Aと章Bの境目はまたぐが、lec01 の最後と lec02 の最初はお互いを前後ページにしない
    assert _ids(results) == ["lec01-main-p003", "lec01-main-p004",
                             "lec02-main-p001", "lec02-main-p002"]
    assert {r["neighbor_of"] for r in results if r["role"] == "neighbor"} == {
        "lec01-main-p004", "lec02-main-p001"}


def test_each_page_appears_once_and_hits_stay_hits(pages):
    # p.2 と p.3 が両方ヒット。p.3 は p.2 の次のページでもあるが、ヒットとして 1 回だけ返す
    hits = [_hit(pages[1], 0.1), _hit(pages[2], 0.2), _hit(pages[1], 0.1)]

    results = retrieval.expand_neighbors(hits, pages, window=1)

    assert _ids(results) == ["lec01-main-p001", "lec01-main-p002",
                             "lec01-main-p003", "lec01-main-p004"]
    assert [r["role"] for r in results] == ["neighbor", "hit", "hit", "neighbor"]
    assert results[2]["distance"] == 0.2


def test_window_zero_returns_hits_unchanged(pages):
    hits = [_hit(pages[1], 0.1), _hit(pages[5], 0.3)]

    assert retrieval.expand_neighbors(hits, pages, window=0) == hits


def test_does_not_modify_the_given_hits(pages):
    hits = [_hit(pages[1], 0.1)]
    before = json.dumps(hits, ensure_ascii=False)

    retrieval.expand_neighbors(hits, pages, window=1)

    assert json.dumps(hits, ensure_ascii=False) == before


def test_hit_missing_from_pages_is_kept_without_neighbors(pages):
    unknown = {**_page("lec09-main", 1), "distance": 0.1}

    results = retrieval.expand_neighbors([unknown], pages, window=1)

    assert _ids(results) == ["lec09-main-p001"]
    assert results[0]["role"] == "hit"


def test_negative_window_is_rejected(pages):
    with pytest.raises(ValueError):
        retrieval.expand_neighbors([], pages, window=-1)


def test_keeps_hit_rank_order_not_page_order(pages):
    # 2 位の p.2 より 1 位の p.3 を先に並べる。p.2 の前の p.1 は p.2 の直前に置く
    results = retrieval.expand_neighbors([_hit(pages[2], 0.1), _hit(pages[1], 0.2)], pages, window=1)

    assert _ids(results) == ["lec01-main-p003", "lec01-main-p004",
                             "lec01-main-p001", "lec01-main-p002"]


def test_shared_neighbor_belongs_to_the_higher_ranked_hit(pages):
    # p.2 は p.1 の次で、p.3 の前でもある。先に処理する 1 位の p.1 の前後として 1 回だけ返す
    results = retrieval.expand_neighbors([_hit(pages[0], 0.1), _hit(pages[2], 0.2)], pages, window=1)

    assert _ids(results) == ["lec01-main-p001", "lec01-main-p002",
                             "lec01-main-p003", "lec01-main-p004"]
    assert results[1]["neighbor_of"] == "lec01-main-p001"


def test_window_two_stops_at_document_edges(pages):
    first, last = pages[0], pages[3]  # lec01 の最初と最後

    from_first = retrieval.expand_neighbors([_hit(first, 0.1)], pages, window=2)
    from_last = retrieval.expand_neighbors([_hit(last, 0.1)], pages, window=2)

    assert _ids(from_first) == ["lec01-main-p001", "lec01-main-p002", "lec01-main-p003"]
    assert _ids(from_last) == ["lec01-main-p002", "lec01-main-p003", "lec01-main-p004"]


def test_negative_window_is_rejected_before_calling_the_api(monkeypatch):
    def search(query):
        raise AssertionError("負の値のときは埋め込みAPIを呼ばない")

    monkeypatch.setattr(retrieval, "search", search)
    with pytest.raises(ValueError):
        retrieval.search_with_neighbors("質問", window=-1)


def test_search_materials_reports_page_loading_errors(monkeypatch, pages):
    def unreadable(*args, **kwargs):
        raise PermissionError("読めません")

    monkeypatch.setattr(retrieval, "search", lambda query: [_hit(pages[1], 0.1)])
    monkeypatch.setattr(retrieval, "load_pages", unreadable)
    monkeypatch.setattr(retrieval, "RAG_NEIGHBOR_PAGES", 1)

    data = json.loads(tools.search_materials("質問"))

    assert data["results"] == []
    assert "読めません" in data["error"]


@pytest.mark.parametrize("value, expected", [(None, 0), ("0", 0), ("1", 1), (" 2 ", 2)])
def test_neighbor_setting_is_read_from_environment(monkeypatch, value, expected):
    from app import config

    if value is None:
        monkeypatch.delenv("AIE_RAG_NEIGHBORS", raising=False)
    else:
        monkeypatch.setenv("AIE_RAG_NEIGHBORS", value)
    assert config._neighbor_pages() == expected


@pytest.mark.parametrize("value", ["-1", "abc", "1.5", "²"])
def test_invalid_neighbor_setting_stops_with_a_message(monkeypatch, value):
    from app import config

    monkeypatch.setenv("AIE_RAG_NEIGHBORS", value)
    with pytest.raises(SystemExit, match="AIE_RAG_NEIGHBORS"):
        config._neighbor_pages()


def test_search_materials_uses_configured_window(monkeypatch, pages):
    monkeypatch.setattr(retrieval, "search", lambda query: [_hit(pages[1], 0.1)])
    monkeypatch.setattr(retrieval, "load_pages", lambda *args, **kwargs: pages)

    monkeypatch.setattr(retrieval, "RAG_NEIGHBOR_PAGES", 0)
    plain = json.loads(tools.search_materials("質問"))["results"]
    monkeypatch.setattr(retrieval, "RAG_NEIGHBOR_PAGES", 1)
    expanded = json.loads(tools.search_materials("質問"))["results"]

    assert _ids(plain) == ["lec01-main-p002"]
    assert "role" not in plain[0]  # 付けない設定では、元の検索結果をそのまま返す
    assert _ids(expanded) == ["lec01-main-p001", "lec01-main-p002", "lec01-main-p003"]
