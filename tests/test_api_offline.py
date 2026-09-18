"""Полный путь fedstat.load() на фикстурах, через поддельный клиент (без сети)."""

import pathlib

import pytest

import fedstat

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
INDICATOR = "31452"


class FakeClient:
    """Отдаёт сохранённые HTML и SDMX вместо похода в сеть."""

    def __init__(self):
        self.html = (FIXTURES / f"{INDICATOR}_indicator.html").read_text("utf-8")
        self.sdmx = (FIXTURES / f"{INDICATOR}_small.sdmx.xml").read_bytes()
        self.last_body = None

    def get_indicator_html(self, indicator_id):
        return self.html

    def download(self, body, data_format="sdmx"):
        self.last_body = body
        return self.sdmx


@pytest.fixture
def fake_client():
    if not (FIXTURES / f"{INDICATOR}_small.sdmx.xml").exists():
        pytest.skip("нет SDMX-фикстуры")
    return FakeClient()


def test_load_returns_tidy_frame(fake_client):
    df = fedstat.load(INDICATOR, client=fake_client)
    assert df.shape == (827, 7)  # компактный срез (только РФ)
    assert "VALUE" in df.columns


def test_load_builds_body_with_selected_filters(fake_client):
    fedstat.load(INDICATOR, filters={"Рынок жилья": "Первичный рынок жилья"},
                 client=fake_client)
    # тело POST собрано и содержит выбранные фильтры
    assert "selectedFilterIds=" in fake_client.last_body
    assert "id=31452" in fake_client.last_body


def test_list_filters_and_template(fake_client):
    frame = fedstat.list_filters(INDICATOR, client=fake_client)
    assert "filter_field_title" in frame.columns
    tpl = fedstat.filter_template(INDICATOR, client=fake_client)
    assert "Год" in tpl and set(tpl.values()) == {"*"}
