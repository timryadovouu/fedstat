"""HTTP-клиент для fedstat.ru: сессия, заголовки, ретраи GET, POST на скачивание."""

import time

import requests

from .errors import DownloadError

BASE_URL = "https://www.fedstat.ru"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


class FedstatClient:
    """Тонкая обёртка над requests.Session с ретраями (сайт часто лагает)."""

    def __init__(self, base_url=BASE_URL, timeout=180.0, retry_max_times=3,
                 verify=True, session=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retry_max_times = retry_max_times
        self.verify = verify
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def get_indicator_html(self, indicator_id):
        """GET страницы индикатора с ретраями и растущей паузой. Возвращает text."""
        url = f"{self.base_url}/indicator/{indicator_id}"
        last_exc = None
        for attempt in range(self.retry_max_times):
            try:
                resp = self.session.get(url, timeout=self.timeout, verify=self.verify)
            except requests.RequestException as exc:
                last_exc = exc
            else:
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code == 403:
                    raise DownloadError(
                        f"fedstat вернул 403 (Forbidden) для {indicator_id}: "
                        "запрос заблокирован антиботом. Попробуйте задать заголовки/UA."
                    )
                if resp.status_code != 503:  # 503 = перегрузка, имеет смысл повторить
                    raise DownloadError(
                        f"fedstat вернул HTTP {resp.status_code} для {indicator_id}."
                    )
                last_exc = DownloadError(f"HTTP {resp.status_code}")
            time.sleep(2 ** attempt)  # 1, 2, 4 ... сек
        raise DownloadError(
            f"Не удалось получить страницу индикатора {indicator_id}: {last_exc}"
        )

    def download(self, body, data_format="sdmx"):
        """POST на downloadData.do. Возвращает сырые байты (SDMX/Excel).

        Без ретраев: CSRF-токен одноразовый. Повтор — на уровне api.load
        (перезабор токена + новая попытка).
        """
        url = f"{self.base_url}/indicator/downloadData.do?format={data_format}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.base_url}/indicator/",
            "Origin": self.base_url,
        }
        try:
            resp = self.session.post(
                url, data=body.encode("utf-8"), headers=headers,
                timeout=self.timeout, verify=self.verify, allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise DownloadError(f"POST на скачивание не удался: {exc}") from exc

        status = resp.status_code
        ctype = resp.headers.get("content-type", "")

        if status == 302:
            raise DownloadError(
                "fedstat отклонил запрос (302). Возможные причины: пустая выборка, "
                "неверные значения фильтров или устаревший CSRF-токен."
            )
        if status == 403:
            raise DownloadError("fedstat вернул 403 (Forbidden): заблокировано антиботом.")
        if status == 503:
            raise DownloadError("fedstat вернул 503 (Service Unavailable): сервер перегружен.")
        if status != 200:
            raise DownloadError(f"fedstat вернул HTTP {status}.")

        if not any(t in ctype for t in ("xml", "excel", "octet-stream")):
            preview = resp.content[:400].decode("utf-8", "replace")
            if "csrf" in preview.lower():
                raise DownloadError(
                    "Проверка CSRF-токена не пройдена (токен устарел/использован). "
                    "Повторите запрос заново."
                )
            raise DownloadError(
                f"Ожидались данные, а пришёл content-type={ctype!r}. Начало ответа: {preview[:200]}"
            )
        return resp.content
