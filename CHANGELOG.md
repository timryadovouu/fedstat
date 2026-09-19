# Changelog

Все заметные изменения проекта. Формат основан на
[Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версионирование — [SemVer](https://semver.org/lang/ru/).

## [0.1.2] - 2026-09-19
### Добавлено
- Маркер `py.typed` и аннотации типов на публичном API — пакет типизирован.
- CI-матрица: тесты на Python 3.11 / 3.12 / 3.13.
- Автопубликация на PyPI по git-тегу через Trusted Publishing (OIDC, без токенов).

## [0.1.1] - 2026-09-19
### Изменено
- Ослаблены зависимости (`pandas>=1.5`, `lxml>=4.6`, `requests>=2.25`,
  `openpyxl>=3.0`) — библиотека уживается с pandas 2.x и не ломает чужие окружения.

## [0.1.0] - 2026-09-19
### Добавлено
- Первый публичный релиз (MVP).
- `list_filters`, `filter_template` — обзор доступных фильтров показателя.
- `load` — скачивание данных с фильтрами в нормализованный `pandas.DataFrame`.
- `to_wide` — «широкий» вид (pivot).
- Устойчивость к нестабильности fedstat: ретраи с паузами, ротация User-Agent,
  свежая сессия и прогрев (аналог жёсткого обновления страницы).
- Понятные ошибки (403/503/302, CSRF, пустая выборка).

[0.1.2]: https://github.com/timryadovouu/fedstat/releases/tag/v0.1.2
[0.1.1]: https://github.com/timryadovouu/fedstat/releases/tag/v0.1.1
[0.1.0]: https://github.com/timryadovouu/fedstat/releases/tag/v0.1.0
