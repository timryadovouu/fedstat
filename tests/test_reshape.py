import pytest

import fedstat
from fedstat.errors import FedstatError
from fedstat.reshape import to_wide
from tests.test_api_offline import FakeClient


@pytest.fixture
def df():
    return fedstat.load("31452", filters={
        "Классификатор объектов административно-территориального деления (ОКАТО)":
            "Российская Федерация",
        "Рынок жилья": "Первичный рынок жилья",
        "Типы квартир": "Все типы квартир",
    }, client=FakeClient())


def test_wide_periods_to_columns(df):
    wide = to_wide(df, columns="PERIOD", values="VALUE", index="TIME")
    assert "TIME" in wide.columns
    for q in ("I квартал", "II квартал", "III квартал", "IV квартал"):
        assert q in wide.columns
    # одна строка на год
    assert wide["TIME"].is_unique


def test_wide_default_index_is_other_columns(df):
    wide = to_wide(df, columns="TIME", values="VALUE")
    # TIME и VALUE ушли, PERIOD остался в индексе-строках
    assert "PERIOD" in wide.columns
    assert "VALUE" not in wide.columns


def test_missing_column_raises(df):
    with pytest.raises(FedstatError):
        to_wide(df, columns="НетТакого", values="VALUE")
