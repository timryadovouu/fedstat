"""Мелкие вспомогательные функции."""

import re


def normalize(s):
    """Нормализация заголовков: убрать лишние пробелы, привести к нижнему регистру."""
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def xpath_literal(s):
    """Безопасный строковый литерал для XPath (учёт кавычек в значении)."""
    if '"' not in s:
        return f'"{s}"'
    if "'" not in s:
        return f"'{s}'"
    parts = s.split('"')
    return "concat(" + ", '\"', ".join(f'"{p}"' for p in parts) + ")"
