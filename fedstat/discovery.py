"""Discovery: разбор страницы индикатора в таблицу фильтров (data_ids) + CSRF.

Здесь только парсинг (без сети), поэтому легко тестируется на сохранённом HTML.
Сетевую часть выполняет client.FedstatClient, а связывает всё api.get_data_ids.
"""

from dataclasses import dataclass, field
from urllib.parse import quote

from lxml import html as lxml_html

from .errors import IndicatorPageError
from .jsparse import parse_js1, parse_js2
from .utils import normalize, xpath_literal

# left_columns/top_columns/groups/filterObjectIds -> тип расположения поля
_OBJECT_RENAME = {
    "left_columns": "lineObjectIds",
    "top_columns": "columnObjectIds",
    "groups": "lineObjectIds",
    "filterObjectIds": "lineObjectIds",
}


@dataclass
class DataIds:
    """Результат discovery по одному индикатору.

    rows: список dict(filter_field_id, filter_field_title, filter_value_id,
                      filter_value_title, filter_field_object_ids)
    object_map: field_id -> 'lineObjectIds'|'columnObjectIds'|'filterObjectIds'
    """

    indicator_id: str
    indicator_title: str
    rows: list = field(default_factory=list)
    object_map: dict = field(default_factory=dict)
    csrf_token_name: str = None
    csrf_token: str = None

    # --- удобные представления ---------------------------------------------
    def fields(self):
        """OrderedDict: filter_field_title -> {field_id, object, values: [titles]}."""
        from collections import OrderedDict

        out = OrderedDict()
        for r in self.rows:
            info = out.setdefault(
                r["filter_field_title"],
                {"field_id": r["filter_field_id"],
                 "object": r["filter_field_object_ids"], "values": []},
            )
            info["values"].append(r["filter_value_title"])
        return out

    def to_frame(self):
        """DataFrame со всеми полями и значениями (то, что видит пользователь)."""
        import pandas as pd

        return pd.DataFrame(self.rows)[
            ["filter_field_title", "filter_value_title",
             "filter_field_id", "filter_value_id", "filter_field_object_ids"]
        ]

    def template(self):
        """Готовый словарь фильтров {field_title: '*'} для правки пользователем."""
        return {title: "*" for title in self.fields()}

    def options(self):
        """{field_title: [уникальные значения]} — что можно подставить в каждый фильтр.

        Готовый обзор всех полей и их допустимых значений (JSON-совместимый),
        чтобы не выбирать поля и значения вручную через .unique().
        """
        return {
            title: list(dict.fromkeys(info["values"]))  # уникальные, с сохранением порядка
            for title, info in self.fields().items()
        }

    def options_frame(self):
        """DataFrame: одна строка на поле — field, object, n_values, values."""
        import pandas as pd

        rows = [
            {"field": title, "object": info["object"],
             "n_values": len(set(info["values"])),
             "values": list(dict.fromkeys(info["values"]))}
            for title, info in self.fields().items()
        ]
        return pd.DataFrame(rows, columns=["field", "object", "n_values", "values"])


def _find_data_script(doc):
    for node in doc.xpath(".//script"):
        txt = node.text_content()
        if "filters: {" in txt and "left_columns: [" in txt:
            return txt
    scripts = doc.xpath(".//script")
    if len(scripts) >= 12:  # историческое поведение R (12-й скрипт)
        return scripts[11].text_content()
    return None


def _extract_csrf(doc):
    holder = doc.xpath("//div[@id='downloadTokenHolder']")
    if not holder:
        return None, None
    name = holder[0].xpath(".//input[@name='struts.token.name']/@value")
    if not name:
        return None, None
    token_name = name[0]
    token = holder[0].xpath(f".//input[@name={xpath_literal(token_name)}]/@value")
    return token_name, (token[0] if token else None)


def _indicator_title_from_html(doc, fallback):
    for xp in (".//h1", ".//title"):
        node = doc.xpath(xp)
        if node and normalize(node[0].text_content()):
            return node[0].text_content().strip()
    return fallback


def parse_indicator_page(html_text, indicator_id):
    """HTML страницы индикатора -> DataIds. Без сети."""
    doc = lxml_html.fromstring(html_text)

    script = _find_data_script(doc)
    if script is None:
        raise IndicatorPageError(
            "Не найден <script> с filters/left_columns на странице индикатора "
            f"{indicator_id} (структура страницы могла измениться)"
        )
    lines = script.split("\n")
    filters = parse_js1(lines)
    objects = parse_js2(lines)

    object_map = {}
    for key, val in objects.items():
        obj_type = _OBJECT_RENAME.get(key, "lineObjectIds")
        ids = val if isinstance(val, list) else [val]
        for fid in ids:
            object_map[str(fid)] = obj_type
    object_map.setdefault("0", "filterObjectIds")  # сам индикатор — скрытый фильтр

    rows = []
    indicator_title = None
    for field_id, fld in filters.items():
        field_id = str(field_id)
        title = fld.get("title", "")
        values = fld.get("values", {}) or {}
        obj_type = object_map.get(field_id, "lineObjectIds")
        for value_id, value in values.items():
            vtitle = value.get("title", "") if isinstance(value, dict) else str(value)
            rows.append({
                "filter_field_id": field_id,
                "filter_field_title": title,
                "filter_value_id": str(value_id),
                "filter_value_title": vtitle.replace("&quot;", '"'),
                "filter_field_object_ids": obj_type,
            })
        if field_id == "0" and len(values) == 1:
            (_, val), = values.items()
            indicator_title = val.get("title") if isinstance(val, dict) else str(val)

    token_name, token = _extract_csrf(doc)
    if indicator_title is None:
        indicator_title = _indicator_title_from_html(doc, str(indicator_id))

    return DataIds(
        indicator_id=str(indicator_id),
        indicator_title=indicator_title,
        rows=rows,
        object_map=object_map,
        csrf_token_name=token_name,
        csrf_token=token,
    )


def build_download_body(data_ids, selected_rows):
    """Собирает URL-encoded тело POST-запроса на downloadData.do (как в R)."""
    parts = [
        ("title", data_ids.indicator_title),
        ("struts.token.name", data_ids.csrf_token_name),
        (data_ids.csrf_token_name, data_ids.csrf_token),
        ("id", data_ids.indicator_id),
    ]

    field_types = {}
    for r in selected_rows:
        field_types.setdefault(r["filter_field_id"], r["filter_field_object_ids"])

    for fid, t in field_types.items():
        if t == "lineObjectIds":
            parts.append(("lineObjectIds", fid))
        elif t == "columnObjectIds":
            parts.append(("columnObjectIds", fid))
    for r in selected_rows:
        parts.append(("selectedFilterIds", f'{r["filter_field_id"]}_{r["filter_value_id"]}'))
    for fid, t in field_types.items():
        if t == "filterObjectIds":
            parts.append(("filterObjectIds", fid))
    if "0" not in field_types:
        parts.append(("filterObjectIds", "0"))

    return "&".join(f"{k}={quote(str(v), safe='')}" for k, v in parts)
