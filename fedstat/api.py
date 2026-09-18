"""Высокоуровневый API: get_data_ids, list_filters, filter_template, load."""

from .client import FedstatClient
from .discovery import build_download_body, parse_indicator_page
from .errors import CSRFTokenError, DownloadError
from .filters import select_rows
from .sdmx import sdmx_to_dataframe


def _client(client):
    return client if client is not None else FedstatClient()


def get_data_ids(indicator_id, *, client=None):
    """Скачивает и разбирает страницу индикатора -> DataIds (поля, значения, CSRF)."""
    cl = _client(client)
    html = cl.get_indicator_html(str(indicator_id))
    return parse_indicator_page(html, str(indicator_id))


def list_filters(indicator_id, *, client=None):
    """DataFrame со всеми доступными полями-фильтрами и их значениями."""
    return get_data_ids(indicator_id, client=client).to_frame()


def filter_template(indicator_id, *, client=None):
    """Готовый словарь {field_title: '*'} — заполни нужные поля и передай в load()."""
    return get_data_ids(indicator_id, client=client).template()


def load(indicator_id, filters=None, *, client=None, retry_max_times=3,
         try_numeric=True, with_codes=False, drop_empty=False):
    """Скачивает подмножество данных индикатора -> нормализованный DataFrame.

    filters: dict(field_title -> value | [values] | '*'); пропущенное поле = все значения.
    Повторяет весь цикл (свежий CSRF + новая попытка) при отклонении POST.
    """
    indicator_id = str(indicator_id)
    cl = _client(client)

    last_exc = None
    for _ in range(max(1, retry_max_times)):
        data_ids = get_data_ids(indicator_id, client=cl)
        if not data_ids.csrf_token or not data_ids.csrf_token_name:
            raise CSRFTokenError(
                f"На странице индикатора {indicator_id} не найден CSRF-токен."
            )
        selected = select_rows(data_ids, filters)
        body = build_download_body(data_ids, selected)
        try:
            raw = cl.download(body, data_format="sdmx")
        except DownloadError as exc:
            last_exc = exc  # CSRF одноразовый -> следующая попытка перезаберёт токен
            continue
        return sdmx_to_dataframe(
            raw, try_numeric=try_numeric, with_codes=with_codes, drop_empty=drop_empty
        )

    raise last_exc
