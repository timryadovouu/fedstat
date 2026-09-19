"""Параметризованные тесты по всем сохранённым фикстурам разных индикаторов.

Проверяют, что discovery и SDMX-парсер держат разные структуры показателей
(кварталы/месяцы, разное число измерений, поля вроде «Возраст», иерархические
регионы и т.п.). Фикстуры кладутся в fixtures/ ноутбуком capture_more.ipynb.
"""

import glob
import pathlib

import pandas as pd
import pytest

from fedstat.discovery import parse_indicator_page
from fedstat.sdmx import sdmx_to_dataframe

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"

HTML_FILES = sorted(FIXTURES.glob("*_indicator.html"))
SMALL_SDMX = sorted(FIXTURES.glob("*_small.sdmx.xml"))


def _iid(path):
    return path.name.split("_")[0]


@pytest.mark.parametrize("html_path", HTML_FILES, ids=lambda p: _iid(p))
def test_discovery_parses_any_indicator(html_path):
    di = parse_indicator_page(html_path.read_text(encoding="utf-8"), _iid(html_path))
    assert di.fields(), "не распарсились поля-фильтры"
    assert di.csrf_token and di.csrf_token_name, "не найден CSRF-токен"
    # каждое поле имеет хотя бы одно значение
    for title, info in di.fields().items():
        assert info["values"], f"поле {title!r} без значений"


@pytest.mark.parametrize("sdmx_path", SMALL_SDMX, ids=lambda p: _iid(p))
def test_sdmx_parses_any_indicator(sdmx_path):
    df = sdmx_to_dataframe(str(sdmx_path))
    assert not df.empty
    assert "VALUE" in df.columns and "TIME" in df.columns
    assert pd.api.types.is_numeric_dtype(df["VALUE"])
    assert df["VALUE"].notna().any()


def test_at_least_two_indicators_covered():
    # напоминание: держим фикстуры хотя бы для пары разных показателей
    ids = {_iid(p) for p in SMALL_SDMX}
    assert len(ids) >= 2, f"мало индикаторов в фикстурах: {ids}"
