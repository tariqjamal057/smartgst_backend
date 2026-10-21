from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import BaseModel


class Firm(BaseModel):
    """A CA firm / partner firm managed by the super admin."""

    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, default="")
    plan = models.CharField(max_length=20, blank=True, default="Basic")
    api_key = models.CharField(max_length=200, blank=True, default="")
    password = models.CharField(max_length=200, blank=True, default="")
    is_active = models.BooleanField(default=True)
    reg_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class GSTClient(BaseModel):
    """A client (taxpayer) tracked inside the portal."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gst_clients",
        null=True,
        blank=True,
    )
    firm = models.ForeignKey(
        Firm, on_delete=models.SET_NULL, null=True, blank=True, related_name="clients"
    )
    name = models.CharField(max_length=200)
    gstin = models.CharField(max_length=15, blank=True, default="")
    pan = models.CharField(max_length=10, blank=True, default="")
    mobile = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    state = models.CharField(max_length=50, blank=True, default="")
    address = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    reg_date = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[("active", "Active"), ("inactive", "Inactive")],
        default="active",
    )
    # Client-details form fields (populated live from GSTN; editable).
    trade_name = models.CharField(max_length=200, blank=True, default="")
    place = models.CharField(max_length=100, blank=True, default="")
    pin = models.CharField(max_length=10, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    business_type = models.CharField(max_length=60, blank=True, default="")
    taxpayer_type = models.CharField(max_length=40, blank=True, default="")
    upload_type = models.CharField(max_length=20, blank=True, default="")
    tan = models.CharField(max_length=12, blank=True, default="")
    cin = models.CharField(max_length=30, blank=True, default="")
    file_no = models.CharField(max_length=60, blank=True, default="")
    responsible_person = models.CharField(max_length=120, blank=True, default="")
    designation = models.CharField(max_length=120, blank=True, default="")
    alternate_mobile = models.CharField(max_length=20, blank=True, default="")
    gst_user_id = models.CharField(max_length=120, blank=True, default="")
    lut_number = models.CharField(max_length=30, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        gstin = self.gstin or ""
        if gstin and len(gstin) != 15:
            raise ValidationError({"gstin": "GSTIN must be exactly 15 characters."})
        if gstin and not gstin.isalnum():
            raise ValidationError({"gstin": "GSTIN must be alphanumeric."})
        pan = self.pan or ""
        if pan and len(pan) != 10:
            raise ValidationError({"pan": "PAN must be exactly 10 characters."})

    def __str__(self):
        return f"{self.name} ({self.gstin})"


class NewsArticle(BaseModel):
    """A GST news / notification / advisory article shown in News & Updates."""

    NEWS_TYPES = [
        ("Notification", "Notification"),
        ("Advisory", "Advisory"),
        ("Revenue Update", "Revenue Update"),
        ("Circular", "Circular"),
        ("Update", "Update"),
        ("Press Release", "Press Release"),
    ]

    news_type = models.CharField(max_length=30, choices=NEWS_TYPES, default="Update")
    published_date = models.CharField(max_length=40, blank=True, default="")
    year = models.IntegerField(default=2026)
    month = models.IntegerField(default=1)
    featured = models.BooleanField(default=False)
    title = models.CharField(max_length=400)
    summary = models.TextField(blank=True, default="")
    tag = models.CharField(max_length=50, blank=True, default="")
    pdf_available = models.BooleanField(default=False)
    pdf_url = models.URLField(blank=True, default="")

    class Meta:
        ordering = ["-year", "-month", "-id"]
        verbose_name_plural = "News articles"

    def __str__(self):
        return self.title


class DashboardLink(BaseModel):
    """A quick-access link / portal shown on the user dashboard.

    ``kind`` separates the "Important Links" strip from the "Important
    Portals" grid so one model + one seeder can drive both sections.
    """

    KIND_LINK = "link"
    KIND_PORTAL = "portal"
    KIND_CHOICES = [
        (KIND_LINK, "Important link"),
        (KIND_PORTAL, "Important portal"),
    ]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_LINK)
    label = models.CharField(max_length=200)
    url = models.URLField()
    icon = models.CharField(max_length=20, blank=True, default="🔗")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "sort_order", "id"]

    def __str__(self):
        return f"{self.kind}: {self.label}"


class Reminder(BaseModel):
    """A GST due-date reminder created by the user (client-site calendar)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gst_reminders"
    )
    title = models.CharField(max_length=200)
    date = models.DateField()
    note = models.TextField(blank=True, default="")
    is_done = models.BooleanField(default=False)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return self.title


class Notification(BaseModel):
    """An in-app notification for a portal user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gst_notifications"
    )
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, default="")
    notification_type = models.CharField(max_length=30, blank=True, default="Info")
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ReturnType(models.TextChoices):
    GSTR1 = "GSTR1", "GSTR-1"
    GSTR1A = "GSTR1A", "GSTR-1A"
    GSTR3B = "GSTR3B", "GSTR-3B"
    TDS_TCS = "TDS_TCS", "TDS/TCS"


class FilingStatus(models.TextChoices):
    FILED = "FILED", "Filed"
    PREPARED = "PREPARED", "Prepared"
    PENDING = "PENDING", "Pending"


class ReturnFiling(BaseModel):
    """Derived filing status for one client + return type + period.

    Populated when the user refreshes a financial year (``filing_sync``):
    GSTN is consulted and the result is stored here so the dashboard reads
    from the database instead of hitting GSTN on every render.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="return_filings"
    )
    client = models.ForeignKey(
        GSTClient,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="return_filings",
    )
    gstin = models.CharField(max_length=15, blank=True, default="")
    return_type = models.CharField(max_length=20, choices=ReturnType.choices)
    period = models.CharField(max_length=10, help_text="MMMM with MMYYYY (e.g. 012026 = Jan 2026)")
    fy = models.CharField(max_length=10)
    status = models.CharField(
        max_length=10, choices=FilingStatus.choices, default=FilingStatus.PENDING
    )
    arn = models.CharField(max_length=30, blank=True, default="")
    filed_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=20, blank=True, default="")  # "gstn" | "app"

    class Meta:
        ordering = ["-period"]
        unique_together = [["owner", "client", "return_type", "period", "fy"]]

    def __str__(self):
        return f"{self.gstin} {self.return_type} {self.period} {self.status}"


class ReturnFilingSync(BaseModel):
    """Raw snapshot of a GSTN filing-status refresh so syncs are auditable."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="return_filing_syncs"
    )
    client = models.ForeignKey(
        GSTClient, on_delete=models.CASCADE, null=True, blank=True, related_name="filing_syncs"
    )
    gstin = models.CharField(max_length=15, blank=True, default="")
    fy = models.CharField(max_length=10, blank=True, default="")
    action = models.CharField(max_length=30, blank=True, default="GETPREF")
    payload = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=False)
    detail = models.CharField(max_length=400, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.gstin} {self.fy} {self.action} {'ok' if self.success else 'fail'}"


class ReturnData(BaseModel):
    """Stored rows for one GSTR *section* of one client + period.

    The gst-app user dashboard persists its entire GSTR-1 / GSTR-3B entry
    grid in localStorage; this table is the server-side replacement. Each
    record holds the JSON payload for a single section (``b2b``,
    ``b2cLarge``, ``itcDetails`` ...) so the frontend can round-trip the
    exact shape it already manages.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="return_data"
    )
    client = models.ForeignKey(
        GSTClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_rows",
    )
    return_type = models.CharField(
        max_length=20, choices=ReturnType.choices, default=ReturnType.GSTR1
    )
    section = models.CharField(max_length=60)
    period = models.CharField(max_length=10, blank=True, default="")
    fy = models.CharField(max_length=10, blank=True, default="")
    payload = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = [["owner", "return_type", "section", "period", "fy", "client"]]

    def __str__(self):
        return f"{self.get_return_type_display()} {self.section} {self.period} ({self.fy})"


class Document(BaseModel):
    """An uploaded document (PDF / doc / xlsx) attached to the portal."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gst_documents"
    )
    client = models.ForeignKey(
        GSTClient, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents"
    )
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to="gst_portal/documents/", blank=True, null=True)
    file_size = models.IntegerField(default=0)
    file_type = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ApiCallLog(BaseModel):
    """Audit trail for every GST / Vanaya API call (super-admin monitor)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_call_logs",
    )
    endpoint = models.CharField(max_length=200)
    method = models.CharField(max_length=10, default="GET")
    gstin = models.CharField(max_length=15, blank=True, default="")
    status = models.CharField(max_length=20, default="Success")
    time_taken_ms = models.IntegerField(default=0)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.method} {self.endpoint} {self.status}"
