from .base import *

# Override base settings for production
DEBUG = False

# Add production-specific security settings
# For example:
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# CORS configuration for production
# Replace with the actual domain of your frontend application
CORS_ALLOWED_ORIGINS = [
    # "https://your-frontend-domain.com",
]

# CSRF Trusted Origins for production
# Replace with the actual domain of your frontend application
CSRF_TRUSTED_ORIGINS = [
    # "https://your-frontend-domain.com",
]