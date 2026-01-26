from .base import *  # noqa: F403

# Override base settings for development
DEBUG = True

# Allow all hosts for local development
ALLOWED_HOSTS = ["*"]

# CORS configuration for development
CORS_ALLOW_ALL_ORIGINS = True

# Add development-specific apps
INSTALLED_APPS += [  # noqa: F405
    "drf_spectacular",
]

# Add development-specific middleware
MIDDLEWARE += []  # noqa: F405
