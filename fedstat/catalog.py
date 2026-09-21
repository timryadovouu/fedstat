"""Каталог всех индикаторов fedstat: поиск показателя по названию -> id.

База (`indicators.json.gz`) поставляется с пакетом и построена парсингом страницы
https://www.fedstat.ru/organizations/ (дерево «ведомство → индикаторы»).
Обновить базу может мейнтейнер через `refresh_catalog()` (нужен доступ к fedstat.ru).
"""

from __future__ import annotations

import gzip
import json
import re
from importlib import resources
from typing import TYPE_CHECKING, Optional

from lxml import html as lxml_html

if TYPE_CHECKING:
    import pandas as pd

    from .client import FedstatClient

_DATA_FILE = "indicators.json.gz"
_ORG_PATH = "/organizations/"


def parse_organizations(html_text: str) -> "pd.DataFrame":
    """HTML страницы /organizations/ -> DataFrame[id, title, department, hidden].

    Уникальные индикаторы (по id, оставляется первое вхождение). Без сети.
    """
    import pandas as pd

    doc = lxml_html.fromstring(html_text)
    seen: set[str] = set()
    rows = []
    for dept_div in doc.xpath('//*[@id="orgsTree"]/div'):
        department = None
        for el in dept_div.xpath('.//*[contains(@class,"i_name org")]'):
            department = " ".join(el.text_content().split())
            break
        for a in dept_div.xpath('.//a[contains(@href,"/indicator/")]'):
            m = re.search(r"/indicator/(\d+)", a.get("href") or "")
            if not m:
                continue
            iid = m.group(1)
            if iid in seen:
                continue
            seen.add(iid)
            title = " ".join(a.text_content().split())
            hidden = False
            node = a
            while node is not None and node is not dept_div:
                node = node.getparent()
                if node is None:
                    break
                cls = node.get("class") or ""
                if "i_excluded" in cls or "hide" in cls:
                    hidden = True
                    break
            rows.append({"id": iid, "title": title,
                         "department": department, "hidden": hidden})
    return pd.DataFrame(rows, columns=["id", "title", "department", "hidden"])


def fetch_indicators(*, client: Optional["FedstatClient"] = None) -> "pd.DataFrame":
    """Скачать и разобрать полный список индикаторов с fedstat.ru (нужен доступ к сайту)."""
    from .client import FedstatClient
    from .errors import DownloadError

    cl = client or FedstatClient()
    if hasattr(cl, "_warm_up"):
        cl._warm_up()
    resp = cl.session.get(cl.base_url + _ORG_PATH, timeout=cl.timeout, verify=cl.verify)
    if resp.status_code != 200:
        raise DownloadError(
            f"fedstat вернул HTTP {resp.status_code} для {_ORG_PATH}"
        )
    return parse_organizations(resp.text)


def _load_bundled() -> list:
    raw = resources.files("fedstat").joinpath(_DATA_FILE).read_bytes()
    return json.loads(gzip.decompress(raw).decode("utf-8"))


def catalog() -> "pd.DataFrame":
    """Полный каталог индикаторов из поставляемой базы -> DataFrame[id, title, department, hidden]."""
    import pandas as pd

    return pd.DataFrame(_load_bundled(), columns=["id", "title", "department", "hidden"])


def find(query: str, *, include_hidden: bool = False,
         regex: bool = False) -> "pd.DataFrame":
    """Поиск индикаторов по названию -> DataFrame.

    Поиск идёт по ПОДСТРОКЕ, регистронезависимо и БЕЗ морфологии. Несколько слов
    в запросе трактуются как И (все должны встретиться в названии, в любом порядке).

    Важно: ищите по ОСНОВЕ слова, а не по словарной форме — в названиях слова стоят
    в разных падежах. Например «ипотека» не найдётся (в названиях «ипотечных»,
    «ипотеки»), нужно `find("ипотеч")`; аналогично `find("безработиц")`.

    query: искомый текст (одно или несколько слов).
    include_hidden: включать скрытые на сайте индикаторы (по умолчанию нет).
    regex: трактовать query как регулярное выражение (тогда И-по-словам не применяется).
    """
    import pandas as pd

    df = catalog()
    if not include_hidden:
        df = df[~df["hidden"]]
    title = df["title"]
    if regex:
        mask = title.str.contains(query, case=False, regex=True, na=False)
    else:
        mask = pd.Series(True, index=df.index)
        for token in query.split():
            mask &= title.str.contains(token, case=False, regex=False, na=False)
    return df[mask].reset_index(drop=True)


def refresh_catalog(*, client: Optional["FedstatClient"] = None,
                    out_path: Optional[str] = None) -> str:
    """Для мейнтейнера: скачать свежий список и перезаписать поставляемую базу.

    Требует доступ к fedstat.ru. Возвращает путь к записанному файлу.
    """
    df = fetch_indicators(client=client)
    records = df.to_dict(orient="records")
    if out_path is None:
        out_path = str(resources.files("fedstat").joinpath(_DATA_FILE))
    payload = json.dumps(records, ensure_ascii=False).encode("utf-8")
    with gzip.open(out_path, "wb") as fh:
        fh.write(payload)
    return out_path
