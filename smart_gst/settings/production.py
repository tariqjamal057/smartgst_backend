import environ

from .base import *  # noqa: F403

env = environ.Env()

DEBUG = False

# Trust the X-Forwarded-Proto header from the reverse proxy (HTTPS behind Nginx).
# Required for SECURE_SSL_REDIRECT/HSTS to work without ssl-terminating Django.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Hosts allowed to serve the API. Override via the ALLOWED_HOSTS env var.
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=[
        "api.taxoratax.com",
        "accounts.taxoratax.com",
        "www.accounts.taxoratax.com",
        "187.77.132.216",
        "localhost",
        "127.0.0.1",
    ],
)

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Frontend origins allowed to call this API. Override via the
# CORS_ALLOWED_ORIGINS env var (comma-separated). Accounts (login) runs at
# https://accounts.taxoratax.com; localhost entries keep local dev working.
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "https://accounts.taxoratax.com",
        "https://www.accounts.taxoratax.com",
        "https://api.taxoratax.com",
        "https://taxora-eight.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
]

# Login/auth requests carry cookies, so credentialed CORS must be enabled.
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

# Origins permitted to submit CSRF-protected requests (same frontend domains).
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "https://accounts.taxoratax.com",
        "https://www.accounts.taxoratax.com",
        "https://api.taxoratax.com",
        "https://taxora-eight.vercel.app",
    ],
)

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
)
