"""Преобразование нормализованного ("длинного") DataFrame в "широкий" (pivot)."""

from .errors import FedstatError


def to_wide(df, columns="PERIOD", values="VALUE", index=None, aggfunc="mean"):
    """Разносит одно измерение по столбцам (обёртка над pandas.pivot_table).

    df:      результат fedstat.load(...) (длинный вид).
    columns: какое поле развернуть в столбцы (напр. "PERIOD" или "TIME").
    values:  столбец со значениями (по умолчанию "VALUE").
    index:   что оставить в строках. По умолчанию — все прочие столбцы,
             кроме `columns` и `values` (т.е. полный ключ наблюдения).
    aggfunc: как агрегировать дубли (по умолчанию среднее).

    Возвращает DataFrame с обычным (сброшенным) индексом.
    """
    import pandas as pd

    for col in (columns, values):
        if col not in df.columns:
            raise FedstatError(
                f"Столбца {col!r} нет в данных. Доступные: {list(df.columns)}"
            )

    if index is None:
        index = [c for c in df.columns if c not in (columns, values)]
    if not index:
        raise FedstatError(
            "Не осталось столбцов для строк (index). Укажите index явно."
        )

    wide = pd.pivot_table(df, index=index, columns=columns, values=values,
                          aggfunc=aggfunc)
    wide = wide.reset_index()
    wide.columns.name = None
    return wide
