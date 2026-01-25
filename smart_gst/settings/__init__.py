from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

APP_ENVIRONMENT = env("APP_ENVIRONMENT", default=None)


if APP_ENVIRONMENT == "prod":
    from .production import *  # noqa: F403, F401
else:
    from .development import *  # noqa: F403, F401
