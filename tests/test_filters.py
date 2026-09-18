import pytest

from fedstat.errors import FilterError
from fedstat.filters import select_rows


def test_select_all_when_no_filters(data_ids):
    assert len(select_rows(data_ids, None)) == len(data_ids.rows)


def test_star_keeps_all_values_of_field(data_ids):
    sel = select_rows(data_ids, {"Период": "*"})
    assert len(sel) == len(data_ids.rows)


def test_exact_value_narrows(data_ids):
    sel = select_rows(data_ids, {"Рынок жилья": "Первичный рынок жилья"})
    markets = {r["filter_value_title"] for r in sel if r["filter_field_title"] == "Рынок жилья"}
    assert markets == {"Первичный рынок жилья"}


def test_normalization_case_and_spaces(data_ids):
    # регистр и лишние пробелы игнорируются
    sel = select_rows(data_ids, {"  рынок ЖИЛЬЯ ": "первичный рынок жилья"})
    markets = {r["filter_value_title"] for r in sel if r["filter_field_title"] == "Рынок жилья"}
    assert markets == {"Первичный рынок жилья"}


def test_list_of_values(data_ids):
    sel = select_rows(data_ids, {"Период": ["I квартал", "II квартал"]})
    periods = {r["filter_value_title"] for r in sel if r["filter_field_title"] == "Период"}
    assert periods == {"I квартал", "II квартал"}


def test_unknown_field_suggests(data_ids):
    with pytest.raises(FilterError) as exc:
        select_rows(data_ids, {"Переод": "I квартал"})
    assert "Период" in str(exc.value)


def test_unknown_value_raises(data_ids):
    with pytest.raises(FilterError):
        select_rows(data_ids, {"Рынок жилья": "Космический рынок"})
