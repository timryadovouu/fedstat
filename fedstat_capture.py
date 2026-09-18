#!/usr/bin/env python3
"""
fedstat_capture.py — снятие фикстур с fedstat.ru (ЕМИСС) для разработки Python-библиотеки.

Что делает для каждого indicator_id:
  1. GET страницы индикатора  -> всегда сохраняет сырой HTML (даже если дальше что-то сломается);
  2. парсит встроенный JS (порт parse_js1/parse_js2 из R-пакета fedstatAPIr)
     -> вытаскивает поля-фильтры, их значения и типы (line/column/filter ObjectIds);
  3. достаёт CSRF-токен из <div id="downloadTokenHolder">;
  4. POST на downloadData.do?format=... -> сохраняет сырой ответ (SDMX-XML и/или Excel);
  5. складывает разобранную таблицу фильтров и метаданные в JSON.

Это ровно те артефакты, на которых потом строятся и тестируются парсеры библиотеки.

Зависимости:
    pip install requests lxml

Примеры запуска:
    # снять всё по двум индикаторам (SDMX), сохранить в ./fixtures
    python fedstat_capture.py 31074 37426

    # только посмотреть, какие есть фильтры, БЕЗ скачивания данных (быстро, безопасно)
    python fedstat_capture.py 31074 --dry-run

    # сузить выборку, чтобы SDMX не был гигантским (совпадение по подстроке в названии)
    python fedstat_capture.py 31074 --filter "Год=2023" --filter "Период=январь"

    # снять и SDMX, и Excel
    python fedstat_capture.py 31074 --format sdmx,excel

Замечания:
  * значение фильтра "*" (или пропуск фильтра) = "взять все значения этого поля".
    Если ничего не фильтровать, скачается ВЕСЬ массив по индикатору — может быть большим/долгим.
  * CSRF-токен одноразовый; на каждый индикатор делается свежий GET.
  * если что-то упадёт на этапе POST — HTML уже сохранён, скрипт сообщит, что именно не вышло.
"""

import argparse
import json
import os
import re
import sys
import time
from urllib.parse import quote

try:
    import requests
except ImportError:
    sys.exit("Нужен пакет requests:  pip install requests lxml")

try:
    from lxml import html as lxml_html
except ImportError:
    sys.exit("Нужен пакет lxml:  pip install requests lxml")


BASE_URL = "https://www.fedstat.ru"

# Заголовки «как у браузера» — уменьшают шанс словить 403 от антибота.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


# --- Порт хака "JS -> JSON" из R (gsub с lookahead + '->") -------------------
_WORD_QUOTE = re.compile(r"\b(?=([^']*'[^']*')*[^']*$)")
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def _js_lines_to_json(lines):
    """Повторяет логику parse_js1/parse_js2: обрамляет слова кавычками только вне
    уже закавыченных участков, меняет ' на ", оборачивает в {...} и парсит как JSON."""
    quoted = [_WORD_QUOTE.sub("'", ln) for ln in lines]
    text = "\n".join(quoted).replace("'", '"')
    text = "{" + text + "}"
    text = _TRAILING_COMMA.sub(r"\1", text)  # убрать хвостовые запятые (JS их допускает, JSON — нет)
    return json.loads(text)


def _find_data_script(doc):
    """Ищем <script>, где лежат filters:{...} и left_columns:[...] — не по индексу, а по содержимому."""
    for node in doc.xpath(".//script"):
        txt = node.text_content()
        if "filters: {" in txt and "left_columns: [" in txt:
            return txt
    # запасной вариант — историческое поведение R (12-й скрипт, 1-based)
    scripts = doc.xpath(".//script")
    if len(scripts) >= 12:
        return scripts[11].text_content()
    return None


def _slice(lines, start_pat, end_pat, start_off, end_off):
    start = end = None
    for i, ln in enumerate(lines):
        if start is None and re.search(start_pat, ln):
            start = i
        elif start is not None and re.search(end_pat, ln):
            end = i
            break
    if start is None or end is None:
        raise ValueError(f"Не нашёл границы блока в JS: {start_pat!r} .. {end_pat!r}")
    return lines[start + start_off : end + end_off + 1]


def parse_js1(script_lines):
    """filters: { field_id: {title, values: {value_id: {title}}} }"""
    block = _slice(script_lines, r"filters: \{", r"left_columns: \[", 1, -2)
    return _js_lines_to_json(block)


def parse_js2(script_lines):
    """left_columns/top_columns/groups/filterObjectIds -> списки field_id по типам."""
    block = _slice(script_lines, r"left_columns: \[", r"grid\.init\(\);", 0, -2)
    return _js_lines_to_json(block)


def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def build_data_ids(html_text):
    """Возвращает (rows, object_map, indicator_field) — аналог data_ids из R.

    rows: список dict(filter_field_id, filter_field_title, filter_value_id,
                       filter_value_title, filter_field_object_ids)
    object_map: field_id -> 'lineObjectIds'|'columnObjectIds'|'filterObjectIds'
    indicator_field: dict(id, title) для поля "0" (сам показатель), если найдено.
    """
    doc = lxml_html.fromstring(html_text)

    script = _find_data_script(doc)
    if script is None:
        raise ValueError("Не нашёл <script> с filters/left_columns на странице")
    lines = script.split("\n")

    filters = parse_js1(lines)
    objects = parse_js2(lines)

    # object_map: тип каждого поля
    rename = {
        "left_columns": "lineObjectIds",
        "top_columns": "columnObjectIds",
        "groups": "lineObjectIds",
        "filterObjectIds": "lineObjectIds",
    }
    object_map = {}
    for key, val in objects.items():
        obj_type = rename.get(key, "lineObjectIds")
        ids = val if isinstance(val, list) else [val]
        for fid in ids:
            object_map[str(fid)] = obj_type
    if "0" not in object_map:
        object_map["0"] = "filterObjectIds"  # сам индикатор — скрытый фильтр

    rows = []
    indicator_field = None
    for field_id, field in filters.items():
        field_id = str(field_id)
        title = field.get("title", "")
        values = field.get("values", {}) or {}
        obj_type = object_map.get(field_id, "lineObjectIds")
        for value_id, value in values.items():
            vtitle = (value.get("title", "") if isinstance(value, dict) else str(value))
            vtitle = vtitle.replace("&quot;", '"')
            rows.append({
                "filter_field_id": field_id,
                "filter_field_title": title,
                "filter_value_id": str(value_id),
                "filter_value_title": vtitle,
                "filter_field_object_ids": obj_type,
            })
        if field_id == "0" and len(values) == 1:
            (vid, val), = values.items()
            indicator_field = {"id": str(vid),
                               "title": (val.get("title") if isinstance(val, dict) else str(val))}

    return rows, object_map, indicator_field


def extract_csrf(html_text):
    """(token_name, token_value) из <div id='downloadTokenHolder'>."""
    doc = lxml_html.fromstring(html_text)
    holder = doc.xpath("//div[@id='downloadTokenHolder']")
    if not holder:
        return None, None
    name_input = holder[0].xpath(".//input[@name='struts.token.name']/@value")
    if not name_input:
        return None, None
    token_name = name_input[0]
    token_input = holder[0].xpath(f".//input[@name={_xpath_literal(token_name)}]/@value")
    token_value = token_input[0] if token_input else None
    return token_name, token_value


def _xpath_literal(s):
    if '"' not in s:
        return f'"{s}"'
    if "'" not in s:
        return f"'{s}'"
    parts = s.split('"')
    return "concat(" + ", '\"', ".join(f'"{p}"' for p in parts) + ")"


def apply_filters(rows, filters):
    """filters: dict(field_title_substr -> value_title_substr | '*'). Совпадение по подстроке."""
    if not filters:
        return rows
    keep = list(rows)
    for f_field, f_value in filters.items():
        fn = _norm(f_field)
        # какие поля подходят под этот ключ
        target_field_ids = {r["filter_field_id"] for r in rows if fn in _norm(r["filter_field_title"])}
        if not target_field_ids:
            print(f"    [!] фильтр по полю '{f_field}' ни с чем не совпал — пропущен")
            continue
        if f_value.strip() == "*":
            continue  # все значения — ничего не выкидываем
        vn = _norm(f_value)
        keep = [
            r for r in keep
            if r["filter_field_id"] not in target_field_ids or vn in _norm(r["filter_value_title"])
        ]
    return keep


def build_post_body(rows, object_map, indicator_id, indicator_title, token_name, token_value):
    parts = [
        ("title", indicator_title),
        ("struts.token.name", token_name),
        (token_name, token_value),
        ("id", indicator_id),
    ]

    # уникальные поля и их типы
    field_types = {}
    for r in rows:
        field_types.setdefault(r["filter_field_id"], r["filter_field_object_ids"])

    for fid, t in field_types.items():
        if t == "lineObjectIds":
            parts.append(("lineObjectIds", fid))
        elif t == "columnObjectIds":
            parts.append(("columnObjectIds", fid))
    for r in rows:
        parts.append(("selectedFilterIds", f'{r["filter_field_id"]}_{r["filter_value_id"]}'))
    for fid, t in field_types.items():
        if t == "filterObjectIds":
            parts.append(("filterObjectIds", fid))
    # индикатор как скрытый фильтр — добавляем, только если поля "0" не было среди строк
    if "0" not in field_types:
        parts.append(("filterObjectIds", "0"))

    return "&".join(f"{k}={quote(str(v), safe='')}" for k, v in parts)


def indicator_title_from_html(html_text, fallback):
    doc = lxml_html.fromstring(html_text)
    for xp in (".//h1", ".//title"):
        node = doc.xpath(xp)
        if node:
            t = _norm(node[0].text_content())
            if t:
                return node[0].text_content().strip()
    return fallback


def capture(indicator_id, args, session):
    print(f"\n=== indicator {indicator_id} ===")
    prefix = os.path.join(args.out, indicator_id)

    # 1. GET страницы — сохраняем HTML в первую очередь
    url = f"{BASE_URL}/indicator/{indicator_id}"
    t0 = time.time()
    r = session.get(url, timeout=args.timeout, verify=not args.insecure)
    dt = time.time() - t0
    html_path = f"{prefix}_indicator.html"
    with open(html_path, "wb") as fh:
        fh.write(r.content)
    print(f"  [ok] HTML сохранён: {html_path}  (HTTP {r.status_code}, {len(r.content)} байт, {dt:.1f}с)")
    if r.status_code != 200:
        print(f"  [!] статус {r.status_code} — дальше, скорее всего, не получится")

    html_text = r.text
    meta = {"indicator_id": indicator_id, "get_status": r.status_code,
            "get_seconds": round(dt, 2), "formats": {}}

    # 2. парсинг фильтров
    try:
        rows, object_map, indicator_field = build_data_ids(html_text)
    except Exception as e:
        print(f"  [!] не удалось распарсить фильтры из JS: {e}")
        print("      HTML сохранён — этого достаточно, чтобы я доработал парсер. Данные (SDMX) не сняты.")
        meta["parse_error"] = str(e)
        _dump_json(f"{prefix}_meta.json", meta)
        return

    # разобранную таблицу фильтров сохраняем — она полезна для разработки/тестов
    _dump_json(f"{prefix}_data_ids.json", rows)
    fields = {}
    for r_ in rows:
        fields.setdefault(r_["filter_field_title"],
                          {"field_id": r_["filter_field_id"],
                           "object": r_["filter_field_object_ids"], "n_values": 0})
        fields[r_["filter_field_title"]]["n_values"] += 1
    print(f"  [ok] распарсено полей-фильтров: {len(fields)} (всего значений: {len(rows)})")
    for title, info in fields.items():
        print(f"        - {title!r}: {info['n_values']} знач., тип {info['object']}, id {info['field_id']}")
    meta["fields"] = fields

    token_name, token_value = extract_csrf(html_text)
    meta["csrf_found"] = bool(token_name and token_value)
    print(f"  [{'ok' if meta['csrf_found'] else '!'}] CSRF-токен: {'найден' if meta['csrf_found'] else 'НЕ найден'}")

    if args.dry_run:
        print("  [dry-run] скачивание данных пропущено. Смотри список полей выше и *_data_ids.json,")
        print("            затем при желании сузь выборку через --filter \"Поле=значение\".")
        _dump_json(f"{prefix}_meta.json", meta)
        return

    if not (token_name and token_value):
        print("  [!] без CSRF-токена POST невозможен. HTML и таблица фильтров сохранены.")
        _dump_json(f"{prefix}_meta.json", meta)
        return

    # 3. применяем фильтры (если заданы)
    sel = apply_filters(rows, args.filters)
    meta["applied_filters"] = args.filters
    meta["selected_rows"] = len(sel)
    if args.filters:
        print(f"  [ok] после фильтрации значений выбрано: {len(sel)} из {len(rows)}")

    indicator_title = (indicator_field or {}).get("title") \
        or indicator_title_from_html(html_text, indicator_id)

    # 4. POST по каждому формату
    for fmt in args.format:
        ext = {"sdmx": "sdmx.xml", "excel": "xls"}.get(fmt, fmt)
        body = build_post_body(sel, object_map, indicator_id, indicator_title, token_name, token_value)
        post_url = f"{BASE_URL}/indicator/downloadData.do?format={fmt}"
        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "Referer": url, "Origin": BASE_URL}
        t0 = time.time()
        try:
            pr = session.post(post_url, data=body.encode("utf-8"), headers=headers,
                              timeout=args.timeout, verify=not args.insecure,
                              allow_redirects=False)
        except Exception as e:
            print(f"  [!] POST({fmt}) упал: {e}")
            meta["formats"][fmt] = {"error": str(e)}
            continue
        dt = time.time() - t0
        ctype = pr.headers.get("content-type", "")
        info = {"status": pr.status_code, "content_type": ctype,
                "bytes": len(pr.content), "seconds": round(dt, 2)}

        ok = pr.status_code == 200 and (
            "xml" in ctype or "excel" in ctype or "octet-stream" in ctype)
        out_path = f"{prefix}_data.{ext}"
        with open(out_path, "wb") as fh:
            fh.write(pr.content)
        info["saved"] = out_path
        meta["formats"][fmt] = info

        if ok:
            print(f"  [ok] {fmt}: {out_path}  (HTTP {pr.status_code}, {ctype}, {len(pr.content)} байт, {dt:.1f}с)")
        else:
            print(f"  [!] {fmt}: HTTP {pr.status_code}, content-type={ctype!r}. "
                  f"Сырой ответ всё равно сохранён в {out_path} — загляни в него (часто это HTML с ошибкой/302).")
        # свежий CSRF на следующий формат (токен одноразовый) — перезабираем страницу
        if fmt != args.format[-1]:
            rr = session.get(url, timeout=args.timeout, verify=not args.insecure)
            token_name, token_value = extract_csrf(rr.text)

    _dump_json(f"{prefix}_meta.json", meta)


def _dump_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def parse_args(argv):
    p = argparse.ArgumentParser(description="Снятие фикстур с fedstat.ru для Python-библиотеки")
    p.add_argument("indicators", nargs="+", help="один или несколько indicator_id (например 31074 37426)")
    p.add_argument("--out", default="fixtures", help="каталог для файлов (по умолчанию ./fixtures)")
    p.add_argument("--format", default="sdmx",
                   help="форматы через запятую: sdmx, excel (по умолчанию sdmx)")
    p.add_argument("--filter", action="append", default=[], metavar="ПОЛЕ=ЗНАЧЕНИЕ",
                   help="сузить выборку (совпадение по подстроке в названии); можно несколько раз. "
                        "ЗНАЧЕНИЕ '*' = все значения поля")
    p.add_argument("--dry-run", action="store_true",
                   help="только показать фильтры и сохранить HTML, БЕЗ скачивания данных")
    p.add_argument("--timeout", type=float, default=180.0, help="таймаут запроса, сек (по умолчанию 180)")
    p.add_argument("--insecure", action="store_true", help="не проверять SSL-сертификат")
    args = p.parse_args(argv)

    args.format = [f.strip() for f in args.format.split(",") if f.strip()]
    filters = {}
    for item in args.filter:
        if "=" not in item:
            p.error(f"--filter должен быть в виде ПОЛЕ=ЗНАЧЕНИЕ, а не {item!r}")
        k, v = item.split("=", 1)
        filters[k.strip()] = v.strip()
    args.filters = filters
    return args


def main(argv):
    args = parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    for ind in args.indicators:
        try:
            capture(str(ind).strip(), args, session)
        except requests.exceptions.RequestException as e:
            print(f"\n[!] сеть/таймаут на индикаторе {ind}: {e}")
        except Exception as e:
            print(f"\n[!] непредвиденная ошибка на индикаторе {ind}: {e}")

    print(f"\nГотово. Файлы в: {os.path.abspath(args.out)}")
    print("Пришли мне весь этот каталог (или заархивируй) — HTML + *_data.sdmx.xml + *_data_ids.json + *_meta.json.")


if __name__ == "__main__":
    main(sys.argv[1:])
