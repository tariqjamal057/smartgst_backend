from django.contrib import admin

from core.models import User

admin.site.site_header = "SmartGST Admin"
admin.site.site_title = "SmartGST Admin Portal"
admin.site.index_title = "Welcome to SmartGST Admin Portal"

admin.site.register(User)
