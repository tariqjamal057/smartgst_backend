from django.contrib import admin

from .models import (
    ApiCallLog,
    Document,
    Firm,
    GSTClient,
    NewsArticle,
    Notification,
    Reminder,
    ReturnData,
)


@admin.register(Firm)
class FirmAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "plan", "is_active", "reg_date")
    list_filter = ("is_active", "plan")
    search_fields = ("name", "email")


@admin.register(GSTClient)
class GSTClientAdmin(admin.ModelAdmin):
    list_display = ("name", "gstin", "owner", "firm", "state")
    search_fields = ("name", "gstin", "mobile")


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "news_type", "year", "month", "featured")
    list_filter = ("news_type", "year")
    search_fields = ("title", "summary")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "date", "is_done")
    list_filter = ("is_done",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "is_read", "created_at")
    list_filter = ("is_read",)


@admin.register(ReturnData)
class ReturnDataAdmin(admin.ModelAdmin):
    list_display = ("owner", "return_type", "section", "period", "fy", "client")
    list_filter = ("return_type", "fy")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "client", "file_type", "created_at")


@admin.register(ApiCallLog)
class ApiCallLogAdmin(admin.ModelAdmin):
    list_display = ("endpoint", "method", "gstin", "status", "time_taken_ms", "created_at")
    list_filter = ("status", "method")
