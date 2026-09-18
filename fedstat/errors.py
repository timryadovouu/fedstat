"""Типизированные исключения библиотеки fedstat."""


class FedstatError(Exception):
    """Базовое исключение библиотеки."""


class IndicatorPageError(FedstatError):
    """Не удалось разобрать страницу индикатора (структура JS/HTML изменилась)."""


class CSRFTokenError(FedstatError):
    """Не найден CSRF-токен на странице индикатора."""


class FilterError(FedstatError):
    """Неверное имя поля-фильтра или значение."""


class DownloadError(FedstatError):
    """Сервер отклонил запрос данных (302 / 403 / 503 / CSRF / нет данных)."""


class SDMXParseError(FedstatError):
    """Не удалось разобрать SDMX-ответ (например, вместо данных пришёл HTML)."""
