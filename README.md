# fedstat

![tests](https://github.com/timryadovouu/fedstat/actions/workflows/tests.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/fedstat)
![Python](https://img.shields.io/pypi/pyversions/fedstat)
![License](https://img.shields.io/pypi/l/fedstat)

Неофициальный Python-клиент к [fedstat.ru](https://www.fedstat.ru) (ЕМИСС) —
порт идей R-пакета [`fedstatAPIr`](https://github.com/DenchPokepon/fedstatAPIr).
Скачивает данные показателей с фильтрами и отдаёт нормализованный
`pandas.DataFrame`.

Статус: **MVP** — `list_filters` / `filter_template` / `load` (формат SDMX).
Дальше планируется догнать полный функционал R-пакета (Excel, режим словаря,
расширенные ретраи и т.д.).

## Установка

**Для использования** (после публикации на PyPI — планируется):

```bash
pip install fedstat
```

**Пока проект на GitHub** — ставится напрямую из репозитория, без ручного клонирования:

```bash
pip install git+ssh://git@github.com/timryadovouu/fedstat.git
```

**Для разработки** (клон + окружение poetry):

```bash
git clone git@github.com:timryadovouu/fedstat.git
cd fedstat
poetry install
```

`poetry install` ставит зависимости в локальное окружение проекта — эта команда
предполагает, что исходники уже склонированы (вариант «для разработки»).

## Пример

Готовый ноутбук: [`notebooks/example.ipynb`](notebooks/example.ipynb).

## Быстрый старт

```python
import fedstat

# 1. Какие фильтры есть у показателя (id — из URL вида /indicator/31452)
fedstat.list_filters("31452")            # DataFrame: поле -> допустимые значения

# 2. Шаблон со всеми полями (значения по умолчанию "*" = все)
f = fedstat.filter_template("31452")
f["Год"] = "2023"
f["Рынок жилья"] = "Первичный рынок жилья"

# 3. Скачать нормализованный ("длинный") DataFrame
df = fedstat.load("31452", filters=f)
df.to_csv("cena.csv", index=False)
df.to_excel("cena.xlsx", index=False)

# 4. При желании — "широкий" вид (одно измерение по столбцам)
wide = fedstat.to_wide(df, columns="PERIOD", values="VALUE", index="TIME")
```

Правила фильтров:
- ключ — заголовок поля, как на сайте (регистр и лишние пробелы игнорируются);
- значение — строка, список строк или `"*"` (все значения);
- пропущенное поле = все значения;
- неверное имя поля/значения -> `FilterError` с подсказкой похожего варианта.

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
| `fedstat.api` | высокоуровневые `load` / `list_filters` / `filter_template` |

## Публикация (для мейнтейнера)

Новые версии публикуются на PyPI **автоматически по git-тегу** через
GitHub Actions + Trusted Publishing (OIDC, без токенов).

Однократная настройка на PyPI (https://pypi.org/manage/project/fedstat/settings/publishing/):
добавить trusted publisher — owner `timryadovouu`, репозиторий `fedstat`,
workflow `publish.yml`, environment `pypi`.

Выпуск версии:

```bash
poetry version patch          # 0.1.2 -> 0.1.3 (или minor / major)
# обновить CHANGELOG.md, закоммитить
git tag v0.1.3 && git push origin main v0.1.3
```

Пуш тега запускает `publish.yml`, который собирает пакет и публикует на PyPI.

## Разработка и тесты

Тесты гоняются офлайн на сохранённых фикстурах (`fixtures/`), сеть не нужна:

```bash
poetry run pytest -q
```

Снятие новых фикстур с живого сайта — ноутбук `notebooks/capture_fixtures.ipynb`
(нужен доступ к fedstat.ru).
