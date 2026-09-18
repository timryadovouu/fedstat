"""Отбор строк data_ids по человекочитаемым фильтрам.

Правила:
  * ключ фильтра — заголовок поля (как на fedstat.ru); сравнение нормализованное
    (регистр и лишние пробелы игнорируются);
  * значение "*" или пропущенное поле = взять все значения этого поля;
  * значение может быть строкой или списком строк;
  * неизвестное поле или значение -> FilterError с подсказкой похожего варианта.
"""

import difflib

from .errors import FilterError
from .utils import normalize


def _suggest(name, candidates):
    match = difflib.get_close_matches(
        normalize(name), [normalize(c) for c in candidates], n=1, cutoff=0.5
    )
    if not match:
        return ""
    real = candidates[[normalize(c) for c in candidates].index(match[0])]
    return f" Возможно, вы имели в виду {real!r}?"


def _match_values(field_title, wanted, available_rows):
    """Возвращает подмножество строк одного поля, подходящих под `wanted`."""
    if wanted == "*" or wanted is None:
        return available_rows

    wanted_list = wanted if isinstance(wanted, (list, tuple, set)) else [wanted]
    titles = [r["filter_value_title"] for r in available_rows]

    selected = []
    for w in wanted_list:
        wn = normalize(w)
        exact = [r for r in available_rows if normalize(r["filter_value_title"]) == wn]
        if exact:
            selected.extend(exact)
            continue
        substr = [r for r in available_rows if wn in normalize(r["filter_value_title"])]
        if substr:
            selected.extend(substr)
            continue
        raise FilterError(
            f"Значение {w!r} не найдено в поле {field_title!r}."
            + _suggest(w, titles)
        )
    # убрать дубли, сохранив порядок
    seen, out = set(), []
    for r in selected:
        k = (r["filter_field_id"], r["filter_value_id"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def select_rows(data_ids, filters=None):
    """DataIds + dict(field_title -> value|list|'*') -> список выбранных строк.

    Поля, не упомянутые в filters, берутся целиком (все значения).
    """
    filters = filters or {}
    fields = data_ids.fields()
    field_titles = list(fields)
    norm_to_title = {normalize(t): t for t in field_titles}

    # проверка ключей на опечатки
    for key in filters:
        if normalize(key) not in norm_to_title:
            raise FilterError(
                f"Поля {key!r} нет у индикатора {data_ids.indicator_id}."
                + _suggest(key, field_titles)
                + f" Доступные поля: {field_titles}"
            )

    # нормализованный доступ к запрошенным значениям
    requested = {normalize(k): v for k, v in filters.items()}

    selected = []
    for title in field_titles:
        rows_of_field = [r for r in data_ids.rows if r["filter_field_title"] == title]
        wanted = requested.get(normalize(title), "*")  # пропущено -> все значения
        selected.extend(_match_values(title, wanted, rows_of_field))
    return selected
