import os

APP_ENVIRONMENT = os.getenv('APP_ENVIRONMENT', 'dev')

if APP_ENVIRONMENT == 'prod':
    from .production import *
else:
    from .development import *
