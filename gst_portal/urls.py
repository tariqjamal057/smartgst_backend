from rest_framework.routers import DefaultRouter

from .views import (
    ApiLogsViewSet,
    ClientsViewSet,
    DashboardLinkViewSet,
    DashboardViewSet,
    DocumentsViewSet,
    FirmsViewSet,
    GstViewSet,
    NewsViewSet,
    NotificationsViewSet,
    RemindersViewSet,
    ReturnDataViewSet,
)

router = DefaultRouter()
router.register("clients", ClientsViewSet, basename="clients")
router.register("firms", FirmsViewSet, basename="firms")
router.register("news", NewsViewSet, basename="news")
router.register("dashboard-links", DashboardLinkViewSet, basename="dashboard-links")
router.register("reminders", RemindersViewSet, basename="reminders")
router.register("notifications", NotificationsViewSet, basename="notifications")
router.register("returns", ReturnDataViewSet, basename="returns")
router.register("documents", DocumentsViewSet, basename="documents")
router.register("api-logs", ApiLogsViewSet, basename="api-logs")
router.register("dashboard", DashboardViewSet, basename="dashboard")
router.register("gst", GstViewSet, basename="gst")

urlpatterns = router.urls
