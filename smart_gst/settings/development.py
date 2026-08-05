from .base import *  # noqa: F403

# Override base settings for development
DEBUG = True

# Allow all hosts for local development
ALLOWED_HOSTS = ["*"]

# CORS configuration for development
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-tenant-id",
]

# Add development-specific apps
INSTALLED_APPS += [  # noqa: F405
    "drf_spectacular",
]

# Add development-specific middleware
MIDDLEWARE += []  # noqa: F405
