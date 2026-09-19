"""HTTP-клиент для fedstat.ru: сессия, заголовки, ретраи GET, POST на скачивание."""

import random
import time

import requests

from .errors import DownloadError

BASE_URL = "https://www.fedstat.ru"

# Пул реалистичных User-Agent (разные браузеры/ОС) — ротируется между сессиями,
# чтобы снизить шанс антибота/кэширования на стороне fedstat.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Fedora; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def _build_headers(user_agent):
    """Набор «браузерных» заголовков (снижает шанс блокировки/кэша)."""
    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        # аналог Cmd+Shift+R — не отдавать кэшированную страницу/токен
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


# для обратной совместимости (использовалось в ноутбуках снятия фикстур)
DEFAULT_HEADERS = _build_headers(USER_AGENTS[0])


class FedstatClient:
    """Тонкая обёртка над requests.Session с ретраями (сайт часто лагает).

    rotate_user_agent: на каждую свежую сессию выбирать случайный User-Agent из пула.
    reset_session(): начать чистую сессию (новые cookies + новый UA) — аналог
    жёсткого обновления страницы (Cmd+Shift+R), помогает при 302/ошибке CSRF.
    """

    def __init__(self, base_url=BASE_URL, timeout=180.0, retry_max_times=3,
                 verify=True, session=None, user_agent=None, rotate_user_agent=True,
                 warm_up=True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retry_max_times = retry_max_times
        self.verify = verify
        self.rotate_user_agent = rotate_user_agent
        self.warm_up = warm_up
        self._warmed = False
        self._user_agent = user_agent or random.choice(USER_AGENTS)
        self.session = session or requests.Session()
        self.session.headers.update(_build_headers(self._user_agent))

    def reset_session(self):
        """Чистая сессия: новые cookies и (при rotate_user_agent) новый User-Agent."""
        if self.rotate_user_agent:
            self._user_agent = random.choice(USER_AGENTS)
        self.session = requests.Session()
        self.session.headers.update(_build_headers(self._user_agent))
        self._warmed = False
        return self

    def _warm_up(self):
        """Зайти на главную, чтобы получить стартовые cookies сессии (как браузер).

        Best-effort: ошибки прогрева не критичны и игнорируются.
        """
        if self._warmed or not self.warm_up:
            return
        try:
            self.session.get(self.base_url + "/", timeout=self.timeout,
                             verify=self.verify)
        except requests.RequestException:
            pass
        self._warmed = True

    def get_indicator_html(self, indicator_id):
        """GET страницы индикатора с ретраями и растущей паузой. Возвращает text."""
        self._warm_up()
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

    def download(self, body, data_format="sdmx", referer=None):
        """POST на downloadData.do. Возвращает сырые байты (SDMX/Excel).

        Без ретраев: CSRF-токен одноразовый. Повтор — на уровне api.load
        (перезабор токена + новая попытка). referer — URL страницы индикатора,
        с которой «пришёл» запрос (fedstat может проверять Referer).
        """
        url = f"{self.base_url}/indicator/downloadData.do?format={data_format}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": referer or f"{self.base_url}/indicator/",
            "Origin": self.base_url,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
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
                "fedstat отклонил запрос (302). Чаще всего это значит, что выбранная "
                "комбинация фильтров НЕ содержит данных — проверьте значения фильтров. "
                "Типичный подвох: похожие значения одного поля (например для ОКАТО за 2023 "
                "данные лежат под 'Российская Федерация без учёта новых субъектов', "
                "а не под 'Российская Федерация'). Реже причина — устаревший CSRF-токен."
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
