"""Настройка логирования. Уровень берётся из переменной окружения LOG_LEVEL.

Какие уровни где используются:
- DEBUG    — детали: открытие/закрытие сессии БД, начало запроса, фильтры списков;
- INFO     — обычные события: запуск/остановка, завершённый запрос,
             создание/изменение/удаление записи;
- WARNING  — ошибки клиента: 404, 409, 422;
- ERROR    — сбои сервера: недоступна БД в /health, необработанное исключение;
- CRITICAL — приложение запущено, но база данных недоступна.
"""

import logging
import logging.config

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def setup_logging(level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": {"format": LOG_FORMAT}},
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "default"},
            },
            "loggers": {
                "app": {"level": level, "handlers": ["console"], "propagate": True},
            },
        }
    )
