"""Тесты парсера SDMX на реальном ответе индикатора 31452."""

import pytest

from fedstat.errors import SDMXParseError
from fedstat.sdmx import sdmx_to_dataframe


def test_shape_and_columns(sdmx_path):
    df = sdmx_to_dataframe(sdmx_path)
    assert df.shape == (827, 7)  # компактный срез (только РФ)
    assert "VALUE" in df.columns
    assert "TIME" in df.columns
    assert "Рынок жилья" in df.columns


def test_dimensions_decoded_not_codes(sdmx_path):
    df = sdmx_to_dataframe(sdmx_path)
    # первое наблюдение — Российская Федерация, а не код "643"
    first = df.iloc[0]
    assert first["Рынок жилья"] in {"Первичный рынок жилья", "Вторичный рынок жилья"}
    okato = "Классификатор объектов административно-территориального деления (ОКАТО)"
    assert "Российская Федерация" in df[okato].unique().tolist()


def test_value_is_numeric(sdmx_path):
    import pandas as pd

    df = sdmx_to_dataframe(sdmx_path)
    assert pd.api.types.is_numeric_dtype(df["VALUE"])
    assert df["VALUE"].notna().all()


def test_with_codes_adds_code_columns(sdmx_path):
    df = sdmx_to_dataframe(sdmx_path, with_codes=True)
    assert any(c.endswith("_code") for c in df.columns)


def test_html_instead_of_sdmx_raises():
    with pytest.raises(SDMXParseError):
        sdmx_to_dataframe(b"<!DOCTYPE html><html><body>error</body></html>")
