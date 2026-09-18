"""Разбор встроенного в страницу индикатора JavaScript.

Порт parse_js1/parse_js2 из R-пакета fedstatAPIr. На странице индикатора
fedstat.ru нужные данные (поля-фильтры, их значения и расположение) лежат не в
JSON, а в исходнике JS. Здесь тот же трюк: «слова» вне уже закавыченных участков
обрамляются кавычками, ' меняется на ", результат оборачивается в {...} и
парсится как JSON.
"""

import json
import re

from .errors import IndicatorPageError

# Вставляет ' на границе слова, только если это НЕ внутри одинарных кавычек
# (в остатке строки чётное число кавычек). Эквивалент R-регекса из parse_js*.
_WORD_QUOTE = re.compile(r"\b(?=([^']*'[^']*')*[^']*$)")
# JS допускает хвостовые запятые перед } или ], JSON — нет.
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def js_lines_to_json(lines):
    """Список строк JS -> объект Python (dict), как в parse_js1/parse_js2."""
    quoted = [_WORD_QUOTE.sub("'", ln) for ln in lines]
    text = "\n".join(quoted).replace("'", '"')
    text = "{" + text + "}"
    text = _TRAILING_COMMA.sub(r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - диагностика
        raise IndicatorPageError(
            f"Не удалось преобразовать JS в JSON: {exc}"
        ) from exc


def _slice(lines, start_pat, end_pat, start_off, end_off):
    start = end = None
    for i, ln in enumerate(lines):
        if start is None and re.search(start_pat, ln):
            start = i
        elif start is not None and re.search(end_pat, ln):
            end = i
            break
    if start is None or end is None:
        raise IndicatorPageError(
            f"Не найдены границы блока в JS: {start_pat!r} .. {end_pat!r}"
        )
    return lines[start + start_off : end + end_off + 1]


def parse_js1(script_lines):
    """filters: { field_id: {title, values: {value_id: {title}}} }."""
    block = _slice(script_lines, r"filters: \{", r"left_columns: \[", 1, -2)
    return js_lines_to_json(block)


def parse_js2(script_lines):
    """left_columns/top_columns/groups/filterObjectIds -> списки field_id по типам."""
    block = _slice(script_lines, r"left_columns: \[", r"grid\.init\(\);", 0, -2)
    return js_lines_to_json(block)
