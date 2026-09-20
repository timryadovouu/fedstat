# fedstat

![tests](https://github.com/timryadovouu/fedstat/actions/workflows/tests.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/fedstat)
![Python](https://img.shields.io/pypi/pyversions/fedstat)
![License](https://img.shields.io/pypi/l/fedstat)

Неофициальный Python-клиент к [fedstat.ru](https://www.fedstat.ru) (ЕМИСС) —
порт идей R-пакета [`fedstatAPIr`](https://github.com/DenchPokepon/fedstatAPIr).
Скачивает данные показателей с фильтрами и отдаёт нормализованный
`pandas.DataFrame`.

Основные функции: `list_filters` / `filter_template` / `load` / `to_wide`.
Парсер проверен на разных структурах показателей (квартальные и месячные данные,
разное число измерений, иерархические регионы).

## Установка

```bash
pip install fedstat
```

**Для разработки** (клон + окружение poetry):

```bash
git clone git@github.com:timryadovouu/fedstat.git
cd fedstat
poetry install
```

`poetry install` ставит зависимости в локальное окружение проекта — эта команда
предполагает, что исходники уже склонированы (вариант «для разработки»).

## Быстрый старт

```python
import fedstat

# 1. Посмотреть доступные фильтры показателя (id — из URL вида /indicator/31452)
fedstat.filter_options("31452")                  # dict {поле: [уникальные значения]}
fedstat.filter_options("31452", as_frame=True)   # то же таблицей (field, object, n_values, values)

# 2. Взять шаблон фильтров и заполнить нужное ("*"/пропуск = все значения)
f = fedstat.filter_template("31452")
f["Год"] = [str(y) for y in range(2017, 2027)]   # можно список
f["Рынок жилья"] = "Первичный рынок жилья"
f["Типы квартир"] = "Все типы квартир"

# 3. Скачать нормализованный ("длинный") DataFrame
df = fedstat.load("31452", filters=f)
df.to_csv("cena.csv", index=False)

# 4. При желании — "широкий" вид (одно измерение по столбцам)
fedstat.to_wide(df, columns="PERIOD", values="VALUE", index="TIME")
```

Правила фильтров:
- ключ — заголовок поля, как на сайте (регистр и лишние пробелы игнорируются);
- значение — строка, список строк или `"*"` (все значения); пропущенное поле = все значения;
- неверное имя поля/значения -> `FilterError` с подсказкой похожего варианта;
- пустая комбинация фильтров -> ошибка 302 от fedstat. Частый подвох: для ОКАТО
  с 2023 г. данные лежат под «Российская Федерация без учёта новых субъектов»,
  а не под «Российская Федерация».

## Примеры

- [`notebooks/fedstatCheck.ipynb`](notebooks/fedstatCheck.ipynb) — 4 разобранных показателя
  (цена жилья, индекс цен, безработица, ставки по ипотеке), включая месячные данные.
- [`notebooks/example.ipynb`](notebooks/example.ipynb) — минимальный пример.

## Формат вывода

Одна строка = одно наблюдение. Столбцы измерений расшифрованы из справочников
(codelists) в человекочитаемые названия, `VALUE` приведён к числу (десятичная
запятая -> точка). Опции `load(...)`:
- `with_codes=True` — добавить исходные коды измерений (`<поле>_code`);
- `drop_empty=True` — выбросить строки без значения;
- `try_numeric=False` — оставить `VALUE` строкой.

## Модули

| модуль | назначение |
|---|---|
| `fedstat.client` | HTTP-сессия, заголовки, ретраи GET, POST на скачивание |
| `fedstat.discovery` | разбор страницы индикатора -> `DataIds` (поля, значения, CSRF) |
| `fedstat.jsparse` | разбор встроенного JS (порт `parse_js1/parse_js2`) |
| `fedstat.filters` | отбор строк по фильтрам, шаблон, подсказки |
| `fedstat.sdmx` | SDMX -> нормализованный `DataFrame` |
| `fedstat.reshape` | `to_wide` — «широкий» вид (pivot) |
| `fedstat.api` | `load` / `list_filters` / `filter_options` / `filter_template` |
