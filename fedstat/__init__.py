"""fedstat — неофициальный Python-клиент к fedstat.ru (ЕМИСС).

Быстрый старт:
    import fedstat
    fedstat.list_filters("31452")          # какие фильтры доступны
    f = fedstat.filter_template("31452")   # шаблон со всеми полями
    f["Год"] = "2023"
    df = fedstat.load("31452", filters=f)  # нормализованный DataFrame
"""

from .api import filter_template, get_data_ids, list_filters, load
from .client import FedstatClient
from .discovery import DataIds, parse_indicator_page
from .errors import (
    CSRFTokenError,
    DownloadError,
    FedstatError,
    FilterError,
    IndicatorPageError,
    SDMXParseError,
)
from .reshape import to_wide
from .sdmx import sdmx_to_dataframe

__version__ = "0.1.0"

__all__ = [
    "load",
    "list_filters",
    "filter_template",
    "get_data_ids",
    "to_wide",
    "FedstatClient",
    "DataIds",
    "parse_indicator_page",
    "sdmx_to_dataframe",
    "FedstatError",
    "IndicatorPageError",
    "CSRFTokenError",
    "FilterError",
    "DownloadError",
    "SDMXParseError",
]
