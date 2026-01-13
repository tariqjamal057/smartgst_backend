from .base import *

# Override base settings for development
DEBUG = True

# Allow all hosts for local development
ALLOWED_HOSTS = ["*"]

# CORS configuration for development
CORS_ALLOW_ALL_ORIGINS = True

# Add development-specific apps
INSTALLED_APPS += [
    # e.g., 'debug_toolbar',
]

# Add development-specific middleware
MIDDLEWARE += [
    # e.g., 'debug_toolbar.middleware.DebugToolbarMiddleware',
]