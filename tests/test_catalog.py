import fedstat
from fedstat.catalog import parse_organizations

SYNTHETIC = """
<html><body>
<div id="orgsTree">
  <div>
    <div class="i_name org">Росстат</div>
    <div class="ved_child">
      <div class="ved_item group i_actual"><a href="/indicator/111"><span class="i_name">Показатель А</span></a></div>
      <div class="ved_item group i_excluded hide"><a href="/indicator/222"><span class="i_name">Скрытый Б</span></a></div>
    </div>
  </div>
</div>
</body></html>
"""


def test_parse_organizations_basic():
    df = parse_organizations(SYNTHETIC)
    assert list(df.columns) == ["id", "title", "department", "hidden"]
    by_id = {r["id"]: r for _, r in df.iterrows()}
    assert by_id["111"]["title"] == "Показатель А"
    assert by_id["111"]["department"] == "Росстат"
    assert by_id["111"]["hidden"] is False or by_id["111"]["hidden"] == False  # noqa: E712
    assert by_id["222"]["hidden"] == True  # noqa: E712


def test_parse_dedup_by_id():
    dup = SYNTHETIC.replace("</div>\n</div>\n</body>",
                            '<a href="/indicator/111">дубль</a></div>\n</div>\n</body>')
    df = parse_organizations(dup)
    assert (df["id"] == "111").sum() == 1  # оставлено одно вхождение


def test_bundled_catalog_loads():
    cat = fedstat.catalog()
    assert list(cat.columns) == ["id", "title", "department", "hidden"]
    assert len(cat) > 5000            # база заметного размера
    assert cat["id"].is_unique


def test_find_returns_known_indicator():
    res = fedstat.find("безработиц")
    assert "43062" in set(res["id"])
    # по умолчанию скрытые не включаются
    assert not res["hidden"].any()


def test_find_is_substring_no_morphology():
    # словарная форма не находится (морфологии нет), основа — находится
    assert len(fedstat.find("ипотека")) == 0
    assert len(fedstat.find("ипотеч")) > 0


def test_find_multiword_is_and():
    # несколько слов -> все должны встретиться в названии
    res = fedstat.find("ипотеч кредит")
    assert len(res) > 0
    for t in res["title"]:
        low = t.lower()
        assert "ипотеч" in low and "кредит" in low
