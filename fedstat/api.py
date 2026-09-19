"""Высокоуровневый API: get_data_ids, list_filters, filter_template, load."""

import time

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
         retry_pause=3.0, try_numeric=True, with_codes=False, drop_empty=False):
    """Скачивает подмножество данных индикатора -> нормализованный DataFrame.

    filters: dict(field_title -> value | [values] | '*'); пропущенное поле = все значения.
    Повторяет весь цикл (свежий CSRF + новая попытка) при отклонении POST,
    с нарастающей паузой между попытками (fedstat часто отвечает 503 при перегрузке).

    retry_max_times: сколько раз пытаться скачать.
    retry_pause: базовая пауза (сек) между попытками; растёт как retry_pause * 2**n.
    """
    indicator_id = str(indicator_id)
    cl = _client(client)

    attempts = max(1, retry_max_times)
    last_exc = None
    for attempt in range(attempts):
        data_ids = get_data_ids(indicator_id, client=cl)
        if not data_ids.csrf_token or not data_ids.csrf_token_name:
            raise CSRFTokenError(
                f"На странице индикатора {indicator_id} не найден CSRF-токен."
            )
        selected = select_rows(data_ids, filters)
        body = build_download_body(data_ids, selected)
        referer = f"{getattr(cl, 'base_url', '')}/indicator/{indicator_id}"
        try:
            raw = cl.download(body, data_format="sdmx", referer=referer)
        except DownloadError as exc:
            last_exc = exc  # CSRF одноразовый -> следующая попытка перезаберёт токен
            if attempt < attempts - 1:
                # чистая сессия (новые cookies + новый UA) — аналог Cmd+Shift+R
                if hasattr(cl, "reset_session"):
                    cl.reset_session()
                time.sleep(retry_pause * (2 ** attempt))  # 3, 6, 12 ... сек
            continue
        return sdmx_to_dataframe(
            raw, try_numeric=try_numeric, with_codes=with_codes, drop_empty=drop_empty
        )

    raise DownloadError(
        f"Не удалось скачать данные индикатора {indicator_id} за {attempts} попыток. "
        f"Последняя ошибка: {last_exc} "
        "Обычно 503/302 — временная нестабильность fedstat; повторите позже "
        "или увеличьте retry_max_times/retry_pause. Если ошибка повторяется стабильно — "
        "проверьте значения фильтров."
    )
