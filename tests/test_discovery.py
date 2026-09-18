"""Тесты discovery на реальной сохранённой странице индикатора 31452."""

from fedstat.discovery import build_download_body, parse_indicator_page


def test_parse_real_page_fields(data_ids):
    fields = data_ids.fields()
    # 7 полей, как в meta.json снятой фикстуры
    assert set(fields) == {
        "Показатель",
        "Год",
        "Классификатор объектов административно-территориального деления (ОКАТО)",
        "Единица измерения",
        "Период",
        "Рынок жилья",
        "Типы квартир",
    }
    assert len(fields["Год"]["values"]) == 27
    assert len(fields["Период"]["values"]) == 4
    assert fields["Год"]["object"] == "columnObjectIds"
    assert fields["Классификатор объектов административно-территориального деления (ОКАТО)"]["object"] == "lineObjectIds"


def test_csrf_extracted(data_ids):
    assert data_ids.csrf_token_name
    assert data_ids.csrf_token
    assert data_ids.indicator_id == "31452"


def test_template_all_stars(data_ids):
    tpl = data_ids.template()
    assert set(tpl) == set(data_ids.fields())
    assert set(tpl.values()) == {"*"}


def test_build_body_structure(data_ids):
    body = build_download_body(data_ids, data_ids.rows)
    assert body.startswith("title=")
    assert "&id=31452" in body
    assert "selectedFilterIds=" in body
    # индикатор (поле 0) как скрытый фильтр, ровно один раз
    assert body.count("filterObjectIds=0") == 1


def test_missing_script_raises():
    import pytest

    from fedstat.errors import IndicatorPageError

    with pytest.raises(IndicatorPageError):
        parse_indicator_page("<html><body>no data</body></html>", "999")
