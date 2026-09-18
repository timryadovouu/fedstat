"""Разбор SDMX-ML (GenericData v1.0) в нормализованный ("длинный") DataFrame.

Структура ответа fedstat:
  <CodeLists>                     -- справочники: код -> человекочитаемое название
    <structure:CodeList id=...><structure:Name/>
      <structure:Code value=...><structure:Description/></structure:Code>
  <DataSet>
    <generic:Series>
      <generic:SeriesKey>   <generic:Value concept=.. value=../>   -- измерения
      <generic:Attributes>  <generic:Value concept=.. value=../>   -- напр. EI, PERIOD
      <generic:Obs>  <generic:Time/>  <generic:ObsValue value=../>

Итог: одна строка = одно наблюдение. Столбцы измерений расшифрованы по CodeLists,
ObsValue приведён к числу (десятичная запятая -> точка).
"""

from lxml import etree

from .errors import SDMXParseError


def _lname(tag):
    return tag.rsplit("}", 1)[-1]


def _iter_descendants(el, name):
    return (c for c in el.iter() if _lname(c.tag) == name)


def sdmx_to_dataframe(source, *, try_numeric=True, with_codes=False, drop_empty=False):
    """Разбирает SDMX в pandas.DataFrame.

    source: путь к файлу, bytes или file-like.
    try_numeric: привести VALUE к числу (запятая -> точка).
    with_codes: добавить исходные коды измерений колонками '<поле>_code'.
    drop_empty: выбросить строки без значения.
    """
    import pandas as pd

    if isinstance(source, (bytes, bytearray)):
        head = bytes(source[:512]).lstrip().lower()
        if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
            raise SDMXParseError(
                "Вместо SDMX получен HTML (вероятно, страница ошибки или истёкший CSRF-токен)."
            )
        import io

        source = io.BytesIO(source)

    codelists = {}
    rows = []
    try:
        for _, el in etree.iterparse(source, events=("end",), recover=True):
            ln = _lname(el.tag)
            if ln == "CodeList":
                cid = el.get("id")
                name = next((c.text for c in el if _lname(c.tag) == "Name"), cid)
                codes = {}
                for code in el:
                    if _lname(code.tag) == "Code":
                        desc = next(
                            (d.text or "" for d in code if _lname(d.tag) == "Description"),
                            "",
                        )
                        codes[code.get("value")] = desc
                codelists[cid] = {"name": name, "codes": codes}
                el.clear()
            elif ln == "Series":
                key, attrs = {}, {}
                for v in _iter_descendants(el, "Value"):
                    parent = _lname(v.getparent().tag)
                    (key if parent == "SeriesKey" else attrs)[v.get("concept")] = v.get("value")
                for obs in _iter_descendants(el, "Obs"):
                    tv = next((c.text for c in obs if _lname(c.tag) == "Time"), None)
                    ov = next(
                        (c.get("value") for c in obs if _lname(c.tag) == "ObsValue"), None
                    )
                    row = dict(key)
                    row.update(attrs)
                    row["TIME"] = tv
                    row["VALUE"] = ov
                    rows.append(row)
                el.clear()
    except etree.XMLSyntaxError as exc:
        raise SDMXParseError(f"Ошибка разбора SDMX-XML: {exc}") from exc

    if not rows:
        raise SDMXParseError(
            "В SDMX не найдено наблюдений (пустой ответ или неверные фильтры)."
        )

    df = pd.DataFrame(rows)

    # расшифровка кодов измерений в подписи
    names = {cid: (cl["name"] or cid) for cid, cl in codelists.items()}
    for cid, cl in codelists.items():
        if cid in df.columns:
            if with_codes:
                df[f"{names[cid]}_code"] = df[cid]
            df[cid] = df[cid].map(cl["codes"]).fillna(df[cid])
    df = df.rename(columns=names)

    if try_numeric:
        df["VALUE"] = pd.to_numeric(
            df["VALUE"].astype("string").str.replace(",", ".", regex=False),
            errors="coerce",
        )
    if drop_empty:
        df = df[df["VALUE"].notna()].reset_index(drop=True)

    return df
