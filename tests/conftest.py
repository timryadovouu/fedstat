import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

INDICATOR = "31452"


@pytest.fixture(scope="session")
def indicator_html():
    path = FIXTURES / f"{INDICATOR}_indicator.html"
    if not path.exists():
        pytest.skip(f"нет фикстуры {path}")
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def sdmx_path():
    # компактный срез (только РФ) — коммитится в репозиторий; большой файл в .gitignore
    path = FIXTURES / f"{INDICATOR}_small.sdmx.xml"
    if not path.exists():
        pytest.skip(f"нет фикстуры {path}")
    return str(path)


@pytest.fixture(scope="session")
def data_ids(indicator_html):
    from fedstat.discovery import parse_indicator_page

    return parse_indicator_page(indicator_html, INDICATOR)
