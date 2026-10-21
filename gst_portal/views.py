import re
import secrets
import time

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import LoginActivity, User
from vanaya.services import VanayaClient, VanayaError, VanayaSessionRequired

from .models import (
    ApiCallLog,
    DashboardLink,
    Document,
    FilingStatus,
    Firm,
    GSTClient,
    NewsArticle,
    Notification,
    Reminder,
    ReturnData,
    ReturnFiling,
    ReturnFilingSync,
)
from .serializers import (
    ApiCallLogSerializer,
    DashboardLinkSerializer,
    DocumentSerializer,
    FirmSerializer,
    GSTClientSerializer,
    NewsArticleSerializer,
    NotificationSerializer,
    ReminderSerializer,
)
from .services import create_notification

# --------------------------------------------------------------------------- #
# Return period / FY helpers
# --------------------------------------------------------------------------- #


_MONTH_NUM = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _fy_start(fy_string):
    """Return the starting calendar year of an FY string ('2026-27' -> 2026)."""
    s = str(fy_string or "").strip()
    if re.fullmatch(r"\d{4}", s):
        return int(s)
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    return int(m.group(1)) if m else None


def _fy_label(fy_string):
    """Normalize any FY-ish input to 'YYYY-YY' (2026 stays, ints → label)."""
    start = _fy_start(fy_string)
    return f"{start}-{str(start + 1)[-2:]}" if start else str(fy_string or "").strip()


def _normalize_return_type(return_type):
    """Map a UI return-type label to the GSTN v2.2 URL type.

    'GSTR1'/'GSTR-1' -> gstr1, 'TDS/TCS' -> gstr7 (GSTR-7 TDS; use gstr8 for
    TCS explicitly), 'ITC04'/'ITC-04' -> itc04, falls through to the input
    lowercased/stripped so unlisted types (GSTR4, GSTR9, ...) still forward.
    """
    label = str(return_type or "").upper().strip("/").replace("-", "").replace(" ", "")
    mapping = {
        "GSTR1": "gstr1",
        "GSTR1A": "gstr1a",
        "GSTR3B": "gstr3b",
        "GSTR4": "gstr4",
        "GSTR5": "gstr5",
        "GSTR6": "gstr6",
        "GSTR7": "gstr7",
        "GSTR8": "gstr8",
        "GSTR9": "gstr9",
        "GSTR9A": "gstr9a",
        "GSTR9C": "gstr9c",
        "GSTR10": "gstr10",
        "ITC04": "itc04",
        "TDS": "gstr7",
        "TCS": "gstr8",
        "TDSTCS": "gstr7",
    }
    if label in mapping:
        return mapping[label]
    return str(return_type or "").lower().strip("/")


def _to_mmyyyy(period, fy_string):
    """Normalize a stored GSTR grid period to MMYYYY (e.g. index 9 = '102026').

    Accepts a 0-11 index, 'Nov-2025', or an already-normalized 'MMYYYY'.
    A bare month name ('April') is resolved against the FY (Apr-Dec from the
    FY start year, Jan-Mar from the next year's January).
    """
    s = str(period or "").strip()
    if not s or re.fullmatch(r"\d{6}", s):
        return s
    m = re.fullmatch(r"([A-Za-z]+)-(\d{4})", s)
    if m:
        month_num = _MONTH_NUM.get(m.group(1).lower()[:3])
        if month_num:
            year = int(m.group(2))
            return f"{month_num:02d}{year}"
    start = _fy_start(fy_string)
    if s.isdigit() and 0 <= int(s) <= 11 and start:
        mm = ((int(s) + 3) % 12) + 1
        y = start if int(s) < 9 else start + 1
        return f"{mm:02d}{y}"
    if start and s.lower()[:3] in _MONTH_NUM:
        month_num = _MONTH_NUM[s.lower()[:3]]
        year = start if month_num >= 4 else start + 1
        return f"{month_num:02d}{year}"
    return s


def _fy_months(fy_string):
    """Return the MMYYYY periods (Apr..Mar) of an FY, oldest first."""
    start = _fy_start(fy_string)
    if not start:
        return []
    periods = []
    for i in range(12):
        mm = ((i + 3) % 12) + 1
        y = start if i < 9 else start + 1
        periods.append(f"{mm:02d}{y}")
    return periods


def _client_for(user, params):
    """Resolve a GSTClient owned by user via explicit id or gstin."""
    client_id = params.get("client") or params.get("client_id")
    gstin = (params.get("gstin") or "").strip()
    qs = GSTClient.objects.filter(owner=user)
    if client_id:
        try:
            client_id = int(client_id)
        except (TypeError, ValueError):
            client_id = None
        if client_id:
            return qs.filter(id=client_id).first(), gstin
    if gstin:
        return qs.filter(gstin=gstin).first(), gstin
    return None, gstin


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _is_staff(request) -> bool:
    return bool(request.user and (request.user.is_staff or request.user.is_superuser))


def _log_api_call(
    request, endpoint, method="GET", gstin="", status_text="Success", ms=0, error=""
):
    try:
        ApiCallLog.objects.create(
            user=request.user if request.user and request.user.is_authenticated else None,
            endpoint=endpoint,
            method=method,
            gstin=(gstin or "").strip(),
            status=status_text,
            time_taken_ms=int(ms),
            error=(error or "")[:2000],
        )
    except Exception:
        # Logging must never break a request.
        return


def _fmt_vanaya_address(addr):
    if not addr:
        return ""
    parts = [
        addr.get("bno"),
        addr.get("bnm"),
        addr.get("flno"),
        addr.get("st"),
        addr.get("locality"),
        addr.get("loc"),
        addr.get("pncd"),
    ]
    return ", ".join(str(p).strip() for p in parts if p and str(p).strip())


def _map_vanaya_lookup(data, gstin):
    """Map a Vanaya search payload to the shape gst-app displays."""
    if not isinstance(data, dict):
        data = {}
    primary_addr = data.get("pradr", {}) or {}
    addr = primary_addr.get("addr", {}) or {}
    additional = data.get("adadr") or []
    branch_addr = additional[0].get("addr", {}) if additional else {}
    company_name = data.get("lgnm") or data.get("tradeNam") or ""
    nature_of_business = data.get("nba") or []
    return {
        "success": True,
        "company_name": company_name,
        "name": company_name,
        "gstin": data.get("gstin") or gstin,
        "trade_name": data.get("tradeNam") or "",
        "address": _fmt_vanaya_address(addr),
        "place": addr.get("loc") or addr.get("city") or addr.get("lt") or "",
        "city": addr.get("loc") or addr.get("city") or "",
        "pincode": addr.get("pncd") or "",
        "pin": addr.get("pncd") or "",
        "branch_address": _fmt_vanaya_address(branch_addr),
        "state": addr.get("stcd") or "",
        "state_code": data.get("stjCd") or "",
        "jurisdiction": data.get("stj") or "",
        "registration_date": data.get("rgdt") or "",
        "business_type": data.get("ctb") or "",
        "taxpayer_type": data.get("dty") or "",
        "last_update": data.get("lstupdt") or "",
        "constitution": data.get("ctb") or "",
        "status": (data.get("sts") or "").upper(),
        "einvoice_status": data.get("einvoiceStatus") or "",
        "nature_of_business": nature_of_business[0] if nature_of_business else "",
        "status_success": data.get("sts") or "Active",
    }


def _pick(item, *keys):
    """First non-empty value among ``keys`` on a row dict (or None)."""
    for key in keys:
        v = item.get(key)
        if v not in (None, ""):
            return v
    return None


def _num(item, *keys):
    """First numeric value among ``keys`` (int/float/parseable string) or 0.0."""
    for key in keys:
        v = item.get(key)
        try:
            if isinstance(v, bool):
                continue
            n = float(v)
            return n
        except (TypeError, ValueError):
            continue
    return 0.0


def _map_tds_tcs_rows(body, taxation_type, period=""):
    """Map a GSTR-7 (``TDS``) / GSTR-8 (``TCS``) section payload to rows.

    The GSTN payload is a per-counterparty (``ctin``) block list; the relevant
    values live under ``tds_det`` / ``tcs_det`` (or the row itself). Returns
    the exact shape gst-app renders in the TDS/TCS download grid.
    """
    if not isinstance(body, dict):
        return []
    data = body.get("data", body)
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("TDS", "TCS", "rows", "items", "records", "tds", "tcs"):
            v = data.get(key)
            if isinstance(v, list):
                items = v
                break
        if not items:
            for v in data.values():
                if isinstance(v, list):
                    items = v
                    break
    seen = set()
    rows = []
    for r in items:
        if not isinstance(r, dict):
            continue
        ctin = str(_pick(r, "ctin", "gstin", "counterPartyGstin", "dst_gstin", "") or "")
        if not ctin or (ctin, taxation_type) in seen:
            # GSTR-7/8 return one block per ctin; de-duplicate.
            continue
        seen.add((ctin, taxation_type))
        det = r.get("tds_det") or r.get("tcs_det") or []
        if isinstance(det, dict):
            det = [det]
        det = [d for d in det if isinstance(d, dict)]

        def _sumdet(*keys):
            total = 0.0
            for d in det:
                total += _num(d, *keys)
            return total

        taxable_value = _num(r, "taxable_value", "taxableValue", "txval", "taxable") or _sumdet(
            "txval", "taxable_value"
        )
        rows.append(
            {
                "id": len(rows) + 1,
                "selected": False,
                "taxationType": taxation_type,
                "gstin": ctin,
                "taxPeriod": str(
                    _pick(
                        r,
                        "ret_period",
                        "period",
                        "tax_period",
                        "taxPeriod",
                    )
                    or period
                ),
                "tradeName": str(_pick(r, "trdnm", "tradeNam", "lgnm", "legalName") or ""),
                "taxableValue": round(taxable_value, 2),
                "igst": round(_sumdet("iamt", "tx_i") or _num(r, "iamt", "igst"), 2),  # noqa: E501
                "cgst": round(_sumdet("camt", "tx_c") or _num(r, "camt", "cgst"), 2),
                "sgst": round(_sumdet("samt", "tx_s") or _num(r, "samt", "sgst"), 2),
                "status": "Not Accept",
            }
        )
    return rows


_GST_AMOUNT_KEYS = {
    "txval": (
        "txval",
        "txVal",
        "taxable_value",
        "taxable",
        "taxableValue",
        "ttl_txval",
        "tot_txval",
        "total_taxable",
        "tx",
    ),  # noqa: E501
    "igst": ("iamt", "igst", "ttl_iamt", "tot_iamt"),
    "cgst": ("camt", "cgst", "ttl_camt", "tot_camt"),
    "sgst": ("samt", "sgst", "ttl_samt", "tot_samt"),
    "cess": ("csamt", "cess", "ttl_csamt", "tot_csamt"),
}


def _row_numbers(row):
    """Sum the recognized GST amount fields of one row into a totals dict."""
    totals = {"txval": 0.0, "igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0, "records": 1}
    if not isinstance(row, dict):
        return totals
    for bucket, keys in _GST_AMOUNT_KEYS.items():
        totals[bucket] += _num(row, *keys)
    return totals


def _aggregate_payload(payload):
    """Reduce any stored ReturnData payload into flat tax totals.

    Handles a list of row dicts (GSTR-1 sections), a single summary dict
    (GSTR-3B ``3bsummary``) and nested ``{section: [...]}`` wrappers, so the
    report numbers always come from the actual recorded rows.
    """
    totals = {"txval": 0.0, "igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0, "records": 0}

    def _add(item):
        add = _row_numbers(item)
        for k, v in add.items():
            totals[k] += v

    if isinstance(payload, dict):
        items = []
        for key in ("data", "records", "rows", "items", "sum_det", "det", "itms", "inv"):
            v = payload.get(key)
            if isinstance(v, list):
                items = v
                break
        if not items:
            items = [v for v in payload.values() if isinstance(v, dict)]
        for item in items:
            _add(item)
    elif isinstance(payload, list):
        for row in payload:
            _add(row)
    return totals


REPORT_SPECS = {
    "GSTR-3B Summary": {"types": ["GSTR3B"]},
    "GSTR-1 Summary": {"types": ["GSTR1"]},
    "GSTR-1A Summary": {"types": ["GSTR1A"]},
    "GSTR-2A Summary": {"types": ["GSTR2A"]},
    "GSTR-2B Summary": {"types": ["GSTR2B"]},
    "GSTR Consolidated Reports": {"types": ["GSTR1", "GSTR1A", "GSTR3B"]},
    "GSTR-3B All Table Details": {"types": ["GSTR3B"], "details": True},
    "GSTR-1 Financial Year Invoice Dates": {"types": ["GSTR1"]},
    "GSTR-2B Invoice Date in Next FY": {"types": ["GSTR2B"]},
}


# --------------------------------------------------------------------------- #
# Resources
# --------------------------------------------------------------------------- #


class ClientsViewSet(viewsets.ModelViewSet):
    serializer_class = GSTClientSerializer

    def get_queryset(self):
        qs = (
            GSTClient.objects.all()
            if _is_staff(self.request)
            else GSTClient.objects.filter(owner=self.request.user)
        )
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(gstin__icontains=search))
        return qs

    def perform_create(self, serializer):
        from billing.services import client_limit

        limit = client_limit(self.request.user)
        if limit is not None:
            used = GSTClient.objects.filter(owner=self.request.user).count()
            if used >= limit:
                raise ValidationError(
                    {
                        "detail": (
                            f"Client limit reached ({used}/{limit}). "
                            "Upgrade your plan to add more clients."
                        )
                    }
                )
        serializer.save(owner=self.request.user)
        create_notification(
            user=self.request.user,
            title="Client added",
            message=(
                f"{serializer.instance.name} ({serializer.instance.gstin}) "
                "was added to your client list."
            ),
            notification_type="Success",
        )

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Aggregated client counts for the dashboard cards.

        Returns total / active / inactive splits plus how many were added in the
        current calendar month. Scoped like get_queryset (owner unless staff).
        """
        qs = self.get_queryset()
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_qs = qs.filter(created_at__gte=month_start)
        return Response(
            {
                "total": qs.count(),
                "active": qs.filter(status="active").count(),
                "inactive": qs.filter(status="inactive").count(),
                "total_new_this_month": month_qs.count(),
                "active_new_this_month": month_qs.filter(status="active").count(),
                "inactive_new_this_month": month_qs.filter(status="inactive").count(),
            }
        )


class FirmsViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = FirmSerializer
    queryset = Firm.objects.all()

    def perform_create(self, serializer):
        serializer.save()


class NewsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = NewsArticleSerializer
    queryset = NewsArticle.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        news_type = self.request.query_params.get("type")
        if news_type and news_type != "all":
            qs = qs.filter(news_type=news_type)
        year = self.request.query_params.get("year")
        month = self.request.query_params.get("month")
        if year:
            qs = qs.filter(year=int(year))
        if month:
            qs = qs.filter(month=int(month))
        limit = self.request.query_params.get("limit")
        if limit and limit.isdigit():
            qs = qs[: int(limit)]
        return qs


class DashboardLinkViewSet(viewsets.ReadOnlyModelViewSet):
    """Important Links & Important Portals shown on the user dashboard."""

    permission_classes = (permissions.AllowAny,)
    serializer_class = DashboardLinkSerializer
    queryset = DashboardLink.objects.filter(is_active=True)

    def get_queryset(self):
        qs = super().get_queryset()
        kind = self.request.query_params.get("kind")
        if kind in ("link", "portal"):
            qs = qs.filter(kind=kind)
        return qs


class RemindersViewSet(viewsets.ModelViewSet):
    serializer_class = ReminderSerializer

    def get_queryset(self):
        return Reminder.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class NotificationsViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="mark-read")
    def mark_read(self, request):
        ids = request.data.get("ids") or []
        qs = self.get_queryset()
        if ids:
            qs = qs.filter(id__in=ids)
        qs.update(is_read=True)
        return Response({"success": True})

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        self.get_queryset().update(is_read=True)
        return Response({"success": True})


class ReturnDataViewSet(viewsets.ViewSet):
    """Server-side store for the GSTR-1 / GSTR-3B entry grids."""

    def _key(self, request, data=None):
        src = data if isinstance(data, dict) else request.query_params
        return {
            "return_type": (src.get("return_type") or src.get("type") or "GSTR1").upper(),
            "period": _to_mmyyyy(src.get("period"), src.get("fy")),
            "fy": _fy_label(src.get("fy")),
            "client_id": src.get("client") or None,
        }

    def list(self, request):
        key = self._key(request)
        qs = ReturnData.objects.filter(
            owner=request.user,
            return_type=key["return_type"],
            period=key["period"],
            fy=key["fy"],
        )
        if key["client_id"]:
            qs = qs.filter(client_id=key["client_id"])
        else:
            qs = qs.filter(client__isnull=True)
        sections = {}
        for row in qs:
            sections[row.section] = row.payload
        return Response(
            {
                "return_type": key["return_type"],
                "period": key["period"],
                "fy": key["fy"],
                "sections": sections,
            }
        )

    @action(detail=False, methods=["post"], url_path="save")
    def save(self, request):
        data = request.data or {}
        key = self._key(request, data)
        sections = data.get("sections") or {}
        if not isinstance(sections, dict):
            return Response(
                {"detail": "sections must be an object of {section: rows}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        client = None
        if key["client_id"]:
            client = GSTClient.objects.filter(id=key["client_id"]).first()
        for section, rows in sections.items():
            ReturnData.objects.update_or_create(
                owner=request.user,
                return_type=key["return_type"],
                section=section,
                period=key["period"],
                fy=key["fy"],
                client=client,
                defaults={"payload": rows},
            )
        if key["period"] and key["fy"]:
            already_filed = ReturnFiling.objects.filter(
                owner=request.user,
                client=client,
                return_type=key["return_type"],
                period=key["period"],
                fy=key["fy"],
                status=FilingStatus.FILED,
            ).exists()
            ReturnFiling.objects.update_or_create(
                owner=request.user,
                client=client,
                return_type=key["return_type"],
                period=key["period"],
                fy=key["fy"],
                defaults={
                    "gstin": (client.gstin if client else "") or "",
                    "status": FilingStatus.FILED if already_filed else FilingStatus.PREPARED,
                    "synced_at": timezone.now(),
                },
            )
        return Response({"success": True, "saved_sections": list(sections.keys())})

    @action(detail=False, methods=["post"], url_path="file")
    def file(self, request):
        """Mark a return's grid data as filed (simulated in sandbox)."""
        data = request.data or {}
        sections = data.get("sections") or {}
        if not isinstance(sections, dict):
            sections = {}
        create_notification(
            user=request.user,
            title=f"GSTR-1 {data.get('period') or ''} Filed Successfully",
            message="Your return data has been reconciled and filed successfully.",
            notification_type="Success",
        )
        return Response({"success": True, "filed": True, "saved_sections": list(sections.keys())})

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        rows = ReturnData.objects.filter(owner=request.user)
        periods = (
            rows.exclude(fy="")
            .order_by("-fy", "-period")
            .values("return_type", "fy", "period")
            .distinct()[:20]
        )
        counts = dict(rows.values_list("return_type").annotate(total=Count("id")))
        return Response({"periods": list(periods), "counts": counts, "total": rows.count()})


class DocumentsViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    search_fields = ("name",)
    ordering_fields = ("created_at",)

    def get_queryset(self):
        qs = (
            Document.objects.all()
            if _is_staff(self.request)
            else Document.objects.filter(owner=self.request.user)
        )
        return qs

    def perform_create(self, serializer):
        file_obj = self.request.FILES.get("file")
        extra = {}
        if file_obj:
            extra = {
                "file_size": file_obj.size,
                "file_type": (
                    file_obj.name.rsplit(".", 1)[-1].lower() if "." in file_obj.name else ""
                ),
            }
            if not serializer.validated_data.get("name"):
                extra["name"] = file_obj.name
        serializer.save(owner=self.request.user, **extra)


class ApiLogsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = ApiCallLogSerializer

    def get_queryset(self):
        qs = ApiCallLog.objects.all()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status__iexact=status_filter)
        return qs


# --------------------------------------------------------------------------- #
# Vanaya / GST integration
# --------------------------------------------------------------------------- #


class GstViewSet(viewsets.ViewSet):
    """Live GSTN data via the Vanaya GSP gateway.

    Mirror of the ``/vanaya/`` surface but gst-app specific and audited into
    ``ApiCallLog`` for the super-admin API monitor. Session state (OTP /
    auth-token / dek) is shared with ``/vanaya/`` through the Django cache.
    """

    permission_classes = (permissions.IsAuthenticated,)

    @action(detail=False, methods=["get"], url_path="search/(?P<gstin>[^/.]+)")
    def search(self, request, gstin=None):
        started = time.monotonic()
        try:
            client = self._build_client(request.query_params)
            body = client.search_gstin(gstin)
        except VanayaSessionRequired as exc:
            return Response(
                {"success": False, "gstn": "disconnected", "data": {}, "detail": exc.message}
            )
        except VanayaError as exc:
            _log_api_call(
                request,
                f"search:{gstin}",
                "GET",
                gstin,
                "Failed",
                (time.monotonic() - started) * 1000,
                exc.message,
            )
            return Response({"success": False, "detail": exc.message}, status=exc.status_code)
        ms = (time.monotonic() - started) * 1000
        _log_api_call(request, f"search:{gstin}", "GET", gstin, "Success", ms)
        return Response(_map_vanaya_lookup(body.get("data") or {}, gstin))

    @action(detail=False, methods=["get"], url_path="credentials")
    def credentials(self, request):
        """List the pool GSTN credentials + which ones have a cached session."""
        entries = []
        for cred in settings.VANAYA_CREDENTIALS:
            client = VanayaClient.from_credential(gstin=cred.get("gstin"))
            entries.append(
                {
                    "gstin": cred.get("gstin", ""),
                    "username": cred.get("username", ""),
                    "state_code": cred.get("state_code", ""),
                    "connected": bool(client.get_auth_token()),
                }
            )
        return Response({"success": True, "credentials": entries})

    @action(detail=False, methods=["post"], url_path="send-otp")
    def send_otp(self, request):
        started = time.monotonic()
        gstin = (request.data.get("gstin") or "").strip()
        try:
            client = self._cred_client(request.data)
            client.send_otp()
        except VanayaError as exc:
            _log_api_call(
                request,
                "authenticate:OTPREQUEST",
                "POST",
                gstin,
                "Failed",
                (time.monotonic() - started) * 1000,
                exc.message,
            )
            return Response({"success": False, "detail": exc.message}, status=exc.status_code)
        # Custom app-owned OTP (accounts-app style): generated here, cached per
        # GSTIN and printed to the terminal so devs/operators can read it.
        generated_otp = f"{secrets.randbelow(1000000):06d}"
        cache.set(f"otp_gst_{gstin}", generated_otp, timeout=600)
        print(
            f"[GST OTP] {gstin} ({client.username}) -> {generated_otp} (valid 10 min)",
            flush=True,
        )
        _log_api_call(
            request,
            "authenticate:OTPREQUEST",
            "POST",
            gstin,
            "Success",
            (time.monotonic() - started) * 1000,
        )
        return Response({"success": True, "otp_sent": True, "expires_in": 600})

    @action(detail=False, methods=["post"], url_path="authenticate")
    def authenticate(self, request):
        started = time.monotonic()
        gstin = (request.data.get("gstin") or "").strip()
        otp = str(request.data.get("otp", "")).strip()
        # Configured app-owned OTP gate: verify OUR OTP first, then complete
        # the GSTN session with the sandbox default OTP (575757).
        cached_otp = cache.get(f"otp_gst_{gstin}")
        try:
            if cached_otp is not None:
                if not otp or otp != str(cached_otp):
                    return Response(
                        {"success": False, "detail": "Invalid OTP."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                client = self._cred_client(request.data)
                body = client.authenticate(otp=settings.VANAYA_DEFAULT_OTP or otp)
                cache.delete(f"otp_gst_{gstin}")
            else:
                client = self._cred_client(request.data)
                body = client.authenticate(otp=otp)
        except VanayaError as exc:
            _log_api_call(
                request,
                "authenticate:AUTHTOKEN",
                "POST",
                gstin,
                "Failed",
                (time.monotonic() - started) * 1000,
                exc.message,
            )
            return Response({"success": False, "detail": exc.message}, status=exc.status_code)
        _log_api_call(
            request,
            "authenticate:AUTHTOKEN",
            "POST",
            gstin,
            "Success",
            (time.monotonic() - started) * 1000,
        )
        return Response(
            {"success": True, "auth_token": body.get("auth_token"), "expiry": body.get("expiry")}
        )

    @action(detail=False, methods=["get"], url_path="returns")
    def returns(self, request):
        params = {k: v for k, v in request.query_params.items() if k not in ("gstin",)}
        started = time.monotonic()
        try:
            client = self._build_client(request.query_params)
            body = client.get_returns(**params)
        except VanayaSessionRequired as exc:
            return Response(
                {"success": True, "gstn": "disconnected", "data": {}, "detail": exc.message},
                status=status.HTTP_200_OK,
            )
        except VanayaError as exc:
            _log_api_call(
                request,
                "returns",
                "GET",
                request.query_params.get("gstin", ""),
                "Failed",
                (time.monotonic() - started) * 1000,
                exc.message,
            )
            return Response({"success": False, "detail": exc.message}, status=exc.status_code)
        _log_api_call(
            request,
            "returns",
            "GET",
            request.query_params.get("gstin", ""),
            "Success",
            (time.monotonic() - started) * 1000,
        )
        return Response(body)

    # ------------------------------------------------------------------ #
    # Official GSTN G2B surface (via Vanaya): filter history, filing      #
    # status, v2.x section save/fetch, profile and session logout.         #
    # ------------------------------------------------------------------ #
    def _gst_call(
        self, request, endpoint, method, fn, gstin="", calm_on_gateway_error=False, **handler
    ):
        """Run a Vanaya call, audit it into ApiCallLog and normalize errors.

        ``calm_on_gateway_error`` is used by read-only dashboard panels: a
        failed/stale GSTN connection degrades to a calm "disconnected" empty
        state (200) instead of a 502, and the stale session is purged so the
        next open is instant rather than re-hammering the gateway.
        """
        started = time.monotonic()
        try:
            body = fn()
        except VanayaSessionRequired as exc:
            # No authenticated GSTN session: respond with a fast, calm empty
            # state instead of a 502 / 5s timeout / accidental OTP send.
            return Response(
                {
                    "success": True,
                    "gstn": "disconnected",
                    "data": [],
                    "detail": exc.message,
                },
                status=status.HTTP_200_OK,
                **handler,
            )
        except VanayaError as exc:
            _log_api_call(
                request,
                endpoint,
                method,
                gstin or request.query_params.get("gstin", ""),
                "Failed",
                (time.monotonic() - started) * 1000,
                exc.message,
            )
            if calm_on_gateway_error:
                # Purge only auth-related failures (stale/invalid session). A
                # plain 404 ("Not Found" endpoint/GSTIN entitlement) is left
                # alone so a valid session is not killed by a no-data answer.
                if any(
                    token in (exc.message or "").lower()
                    for token in ("auth", "invalid", "otp", "session")
                ):
                    self._purge_stale(gstin or request.query_params.get("gstin", ""))
                return Response(
                    {
                        "success": True,
                        "gstn": "disconnected",
                        "data": [],
                        "detail": exc.message,
                    },
                    status=status.HTTP_200_OK,
                    **handler,
                )
            return Response(
                {"success": False, "detail": exc.message}, status=exc.status_code, **handler
            )
        _log_api_call(
            request,
            endpoint,
            method,
            gstin or request.query_params.get("gstin", ""),
            "Success",
            (time.monotonic() - started) * 1000,
        )
        return Response(body)

    def _purge_stale(self, gstin):
        """Drop cached Vanaya sessions for a GSTIN whose live read just failed.

        Clears the requested GSTIN's cache key plus its matching pool
        credential's key (they can differ after a fallback).
        """
        gstin = (gstin or "").strip()
        if not gstin:
            return
        targets = {gstin}
        cred = VanayaClient.find_credential(gstin=gstin)
        if cred and cred.get("gstin"):
            targets.add(cred["gstin"])
        for g in targets:
            try:
                VanayaClient.from_defaults(gstin=g).clear_session()
            except VanayaError:
                pass

    def _cred_client(self, data):
        """Client for a request carrying credential ids (gstin / username).

        Uses the pool entry so state_code matches, enabling the "login with a
        credential" flow; falls back to the normal build otherwise.
        """
        merged = data if isinstance(data, dict) else {}
        gstin = (merged.get("gstin") or "").strip()
        username = (merged.get("username") or "").strip()
        if gstin or username:
            return VanayaClient.from_credential(gstin=gstin, username=username)
        return self._build_client(merged)

    @action(detail=False, methods=["get"], url_path="pref")
    def pref(self, request):
        """GETPREF: previously filed / preferred GSTR-3B list for a FY."""
        fy = request.query_params.get("fy") or ""
        params = {"action": "GETPREF"}
        if fy:
            params["fy"] = fy
        return self._gst_call(
            request,
            "returns:GETPREF",
            "GET",
            lambda: (
                self._build_client(request.query_params).get_returns("GETPREF", fy=fy)
                if fy
                else self._build_client(request.query_params).get_returns("GETPREF")
            ),
            gstin=request.query_params.get("gstin", ""),
            calm_on_gateway_error=True,
        )

    @action(detail=False, methods=["get"], url_path="filed")
    def filed(self, request):
        """GETRET: the filed return data for a given period/FY."""
        ret_period = (
            request.query_params.get("retPeriod") or request.query_params.get("ret_period") or ""
        )
        fy = request.query_params.get("fy") or ""
        params = {"retPeriod": ret_period}
        if fy:
            params["fy"] = fy
        return self._gst_call(
            request,
            "returns:GETRET",
            "GET",
            lambda: self._build_client(request.query_params).get_returns("GETRET", **params),
            gstin=request.query_params.get("gstin", ""),
            calm_on_gateway_error=True,
        )

    @action(detail=False, methods=["get"], url_path="ledger")
    def ledger(self, request):
        """GETCASH/GETITC: electronic cash & ITC ledger balances."""
        action = request.query_params.get("action") or "GETITC"
        params = {
            k: v
            for k, v in request.query_params.items()
            if k not in ("action", "gstin", "username", "ip", "ip_usr", "cust_id", "state_code")
        }
        return self._gst_call(
            request,
            f"ledger:{action}",
            "GET",
            lambda: self._build_client(request.query_params).ledger(action, **params),
            gstin=request.query_params.get("gstin", ""),
            calm_on_gateway_error=True,
        )

    @action(detail=False, methods=["get"], url_path="payment")
    def payment(self, request):
        """CHALLAN/STATUS/ADJUST/GETCASH/LIAB_IMPORT/LIAB_SYSTEM."""
        action = request.query_params.get("action") or "STATUS"
        params = {
            k: v
            for k, v in request.query_params.items()
            if k not in ("action", "gstin", "username", "ip", "ip_usr", "cust_id", "state_code")
        }
        return self._gst_call(
            request,
            f"payment:{action}",
            "GET",
            lambda: self._build_client(request.query_params).payment(action, **params),
            gstin=request.query_params.get("gstin", ""),
            calm_on_gateway_error=action in {"STATUS", "LIAB_SYSTEM", "GETCASH"},
        )

    @action(detail=False, methods=["get"], url_path="fo")
    def fo(self, request):
        """GetLatestReturns/GetFilingMatrix/GetGivenMetrics."""
        action = request.query_params.get("action") or "GetFilingMatrix"
        params = {
            k: v
            for k, v in request.query_params.items()
            if k not in ("action", "gstin", "username", "ip", "ip_usr", "cust_id", "state_code")
        }
        return self._gst_call(
            request,
            f"fo:{action}",
            "GET",
            lambda: self._build_client(request.query_params).get_fo(action, **params),
            gstin=request.query_params.get("gstin", ""),
            calm_on_gateway_error=True,
        )

    @action(detail=False, methods=["get"], url_path="filing-status")
    def filing_status(self, request):
        """Filing matrix for one client + FY, read from the database.

        Data is written by ``filing_sync`` (which calls GSTN) or by saving a
        GSTR grid (ReturnData.save). No live GSTN call happens on read, so the
        dashboard is always fast and stable; press Update All to resync.
        """
        fy = _fy_label(request.query_params.get("fy"))
        user = request.user
        client, gstin = _client_for(user, request.query_params)
        active_gstin = gstin or (client.gstin if client else "")

        rows = ReturnFiling.objects.filter(owner=user, fy=fy)
        if client:
            rows = rows.filter(client=client)
        elif gstin:
            rows = rows.filter(gstin=gstin)
        else:
            rows = rows.filter(client__isnull=True)

        ordered = list(rows.order_by("period"))
        rows_payload = [
            {
                "return_type": r.return_type,
                "period": r.period,
                "status": r.status,
                "arn": r.arn,
                "filed_at": r.filed_at.isoformat() if r.filed_at else None,
                "synced_at": r.synced_at.isoformat() if r.synced_at else None,
            }
            for r in ordered
        ]

        done = rows.exclude(status=FilingStatus.PENDING)
        filed_counts = dict(done.values_list("return_type").annotate(total=Count("id")))
        last_sync = rows.exclude(synced_at__isnull=True).order_by("-synced_at").first()

        gstn = "disconnected"
        try:
            if active_gstin:
                gstn = (
                    "connected"
                    if VanayaClient.from_credential(gstin=active_gstin).get_auth_token()
                    else "disconnected"
                )
            else:
                gstn = (
                    "connected"
                    if VanayaClient.from_defaults().get_auth_token()
                    else "disconnected"
                )
        except Exception:
            gstn = "disconnected"

        return Response(
            {
                "success": True,
                "fy": fy,
                "gstin": active_gstin or "",
                "client": (
                    {"id": client.id, "name": client.name or "", "gstin": client.gstin or ""}
                    if client
                    else None
                ),
                "gstn": gstn,
                "rows": rows_payload,
                "filed_counts": {
                    "GSTR1": filed_counts.get("GSTR1", 0),
                    "GSTR1A": filed_counts.get("GSTR1A", 0),
                    "GSTR3B": filed_counts.get("GSTR3B", 0),
                    "TDS_TCS": filed_counts.get("TDS_TCS", 0),
                },
                "filed_total": done.count(),
                "periods": list(
                    done.values_list("period", flat=True).order_by("period").distinct()
                ),
                "last_sync": last_sync.synced_at.isoformat() if last_sync else None,
            }
        )

    @action(detail=False, methods=["post"], url_path="filing-sync")
    def filing_sync(self, request):
        """Refresh a FY's filing matrix: consult GSTN, then persist to DB.

        Calls Vanaya GETPREF for the requested client/FY (the only return
        snapshot action available), stores the raw response in
        ``ReturnFilingSync`` for auditability, and upserts one ``ReturnFiling``
        row per return type × month. Statuses are kept honest:

        * PREPARED — a GSTR grid has been saved in this app for that period.
        * FILED — a GSTN acknowledgement (ARN) was recorded at submission.
        * PENDING — nothing known about that period yet.
        """
        data = dict(request.data or {})
        for k, v in (request.query_params or {}).items():
            data.setdefault(k, v)

        fy = _fy_label(data.get("fy"))
        user = request.user
        client, gstin = _client_for(user, data)
        active_gstin = gstin or (client.gstin if client else "")

        if not fy or not active_gstin:
            return Response(
                {
                    "success": False,
                    "detail": "fy and a gstin (or client) are required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Consult GSTN first (best-effort; the DB update happens regardless).
        live_payload = None
        sync_detail = ""
        sync_ok = False
        try:
            vc = self._build_client({"gstin": active_gstin})
            live_payload = vc.get_returns("GETPREF", fy=fy)
            sync_ok = bool(live_payload and live_payload.get("success", True) is not False)
            if live_payload is None:
                sync_ok = False
        except Exception as exc:
            sync_detail = str(exc)[:380]

        ReturnFilingSync.objects.create(
            owner=user,
            client=client,
            gstin=active_gstin,
            fy=fy,
            action="GETPREF",
            payload=live_payload or {},
            success=sync_ok,
            detail=sync_detail,
        )

        periods = _fy_months(fy)
        return_types = ["GSTR1", "GSTR1A", "GSTR3B", "TDS_TCS"]
        base = ReturnFiling.objects.filter(owner=user, client=client, fy=fy)
        existing = {(row.return_type, row.period): row for row in base.filter(period__in=periods)}
        section_qs = ReturnData.objects.filter(owner=user, fy=fy, period__in=periods)
        if client:
            section_qs = section_qs.filter(client=client)
        else:
            section_qs = section_qs.filter(client__isnull=True)
        prepared_keys = set(section_qs.values_list("return_type", "period").distinct())

        updated = 0
        now = timezone.now()
        for rt in return_types:
            for period in periods:
                row = existing.get((rt, period))
                row_status = FilingStatus.PENDING
                arn = ""
                filed_at = None
                if row:
                    if row.status == FilingStatus.FILED:
                        row_status = FilingStatus.FILED
                        arn = row.arn
                        filed_at = row.filed_at
                    else:
                        row_status = (
                            FilingStatus.PREPARED
                            if (rt, period) in prepared_keys
                            else FilingStatus.PENDING
                        )
                elif (rt, period) in prepared_keys:
                    row_status = FilingStatus.PREPARED
                if row is None:
                    row = ReturnFiling(
                        owner=user,
                        client=client,
                        gstin=active_gstin,
                        return_type=rt,
                        period=period,
                        fy=fy,
                    )
                row.gstin = active_gstin
                row.status = row_status
                row.arn = arn
                row.filed_at = filed_at
                row.synced_at = now
                row.save()
                updated += 1

        return Response(
            {
                "success": True,
                "fy": fy,
                "gstin": active_gstin,
                "gstn_ok": sync_ok,
                "detail": sync_detail
                or (
                    "GSTN preferences snapshot stored."
                    if sync_ok
                    else "GSTN snapshot failed; DB still updated from app data."
                ),
                "updated": updated,
                "prepared": len(prepared_keys),
            }
        )

    @action(detail=False, methods=["post"], url_path="ret-save")
    def ret_save(self, request):
        """PUT a GSTR section to GSTN (``PUT /taxpayerapi/v2.2/returns/<type>``).

        Body: ``{"return_type": "gstr1", "ret_period": "012025",
        "section": "B2B", "params": {"ctin": "..."},
        "payload": {"b2b": [...]}}`` -> ``reference_id``.
        """
        data = request.data or {}
        return_type = _normalize_return_type(data.get("return_type") or data.get("type") or "")
        ret_period = _to_mmyyyy(data.get("ret_period") or data.get("period"), data.get("fy"))
        payload = data.get("payload") or data.get("data") or {}
        if not return_type or not ret_period or not isinstance(payload, dict):
            return Response(
                {
                    "success": False,
                    "detail": "return_type, ret_period (or period) and payload are required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        section = data.get("section") or ""
        query = dict((data.get("params") or {}))
        if section:
            query.setdefault("section", section)
        version = query.pop("version", None) or data.get("version")
        return self._gst_call(
            request,
            f"returns_v2:save:{return_type}",
            "PUT",
            lambda: self._build_client(data).gstr_save(
                return_type,
                ret_period,
                payload,
                gstin=data.get("gstin", ""),
                version=version,
                **query,
            ),
            gstin=data.get("gstin", ""),
        )

    @action(detail=False, methods=["get"], url_path="ret-section")
    def ret_section(self, request):
        """GET a GSTR section (``GET /taxpayerapi/v2.2/returns/<type>``).

        Query: ``return_type``, ``ret_period`` (or ``period``), ``section``
        plus GSTN document filters (``ctin``, ``from``/``to``, ``state_cd``,
        ``doc_id``, ``inv_period``) — everything except the bookkeeping keys
        is forwarded verbatim to Vanaya. Optional ``version`` selects the
        return-type-specific API version (default from the per-type map).
        """
        qp = request.query_params
        return_type = _normalize_return_type(qp.get("return_type") or qp.get("type") or "")
        ret_period = _to_mmyyyy(qp.get("ret_period") or qp.get("period"), qp.get("fy"))
        if not return_type or not ret_period:
            return Response(
                {"success": False, "detail": "return_type and ret_period are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        extra = {
            k: v
            for k, v in qp.items()
            if k not in ("return_type", "type", "ret_period", "period", "fy", "gstin", "client")
        }
        version = extra.pop("version", None)
        return self._gst_call(
            request,
            f"returns_v2:get:{return_type}",
            "GET",
            lambda: self._build_client(request.query_params).gstr_get(
                return_type, ret_period, gstin=qp.get("gstin", ""), version=version, **extra
            ),
            gstin=qp.get("gstin", ""),
        )

    @action(detail=False, methods=["get"], url_path="tds-tcs")
    def tds_tcs(self, request):
        """Aggregate GSTR-7 (TDS) + GSTR-8 (TCS) section rows for the grid.

        Query: ``period``/``ret_period`` (+ optional ``fy``) and ``gstin``.
        Calls the ``TDS`` section of GSTR-7 and the ``TCS`` section of GSTR-8
        on the current session, normalizes both into the TDS/TCS table rows
        and merges them. A missing session degrades to a calm empty state.
        """
        qp = request.query_params
        ret_period = _to_mmyyyy(qp.get("period") or qp.get("ret_period"), qp.get("fy"))
        gstin = qp.get("gstin", "")
        if not ret_period:
            return Response(
                {"success": False, "detail": "period (or ret_period) and fy are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        started = time.monotonic()
        try:
            client = self._build_client(request.query_params)
        except VanayaError as exc:
            return Response({"success": False, "detail": exc.message}, status=exc.status_code)
        rows = []
        warnings = []
        for return_type, taxation_type in (("gstr7", "TDS"), ("gstr8", "TCS")):
            try:
                body = client.gstr_get(return_type, ret_period, gstin=gstin, section=taxation_type)
                rows += _map_tds_tcs_rows(body, taxation_type, period=ret_period)
            except VanayaSessionRequired as exc:
                _log_api_call(
                    request, f"tds-tcs:{return_type}", "GET", gstin, "Failed", 0, exc.message
                )
                return Response(
                    {"success": True, "gstn": "disconnected", "data": [], "detail": exc.message},
                    status=status.HTTP_200_OK,
                )
            except VanayaError as exc:
                _log_api_call(
                    request,
                    f"tds-tcs:{return_type}",
                    "GET",
                    gstin,
                    "Failed",
                    (time.monotonic() - started) * 1000,
                    exc.message,
                )
                warnings.append(f"{taxation_type}: {exc.message}")
        _log_api_call(
            request,
            "tds-tcs",
            "GET",
            gstin,
            "Success",
            (time.monotonic() - started) * 1000,
        )
        return Response(
            {
                "success": True,
                "gstin": gstin,
                "period": ret_period,
                "data": rows,
                "warnings": warnings,
            }
        )

    def _section_breakdown(self, data_qs, return_type, period):
        """Per-section tax totals for one return type + period (GSTR-3B tables)."""
        out = {}
        for row in data_qs.filter(return_type=return_type, period=period):
            agg = _aggregate_payload(row.payload)
            out[row.section] = {k: round(v, 2) for k, v in agg.items()}
        return out

    @action(detail=False, methods=["get"], url_path="report-summary")
    def report_summary(self, request):
        """Build the REAL data behind the REPORTS page (Summary tab).

        Three sources are merged so reports reflect actual returns even when
        a client filed outside this application:

        * GSTN live — ``GETPREF`` (real return-frequency/obligation snapshot)
          plus best-effort ``GETRET`` per return type for the selected end
          period (filed ARN/status). Sandbox degrades to warnings; production
          returns GSTN-authoritative status.
        * App database — ``ReturnData`` grid totals and ``ReturnFiling``
          status for the selected FY/period range.

        Query: ``gstin``, ``fy``/``year``, optional ``from``/``to`` months
        (name, MSYYYY or MMYYYY) to narrow the range.
        """
        qp = request.query_params
        user = request.user
        fy = _fy_label(qp.get("fy") or qp.get("year"))
        gstin = (qp.get("gstin") or "").strip()
        client, _gstin = _client_for(user, qp)
        active_gstin = gstin or _gstin or (client.gstin if client else "")
        if not fy or not active_gstin:
            return Response(
                {"success": False, "detail": "fy and gstin are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        periods = _fy_months(fy)
        from_p = _to_mmyyyy(qp.get("from") or qp.get("from_pp") or "", fy)  # noqa: E501
        to_p = _to_mmyyyy(qp.get("to") or qp.get("to_pp") or "", fy)
        if from_p in periods:
            periods = periods[periods.index(from_p) :]
        if to_p in periods:
            periods = periods[: periods.index(to_p) + 1]

        # ---- GSTN live (best-effort, never blocks the report) ----------- #
        started = time.monotonic()
        gstn = "disconnected"
        live = {}
        warnings = []
        try:
            vc = self._build_client({"gstin": active_gstin})
            if vc.get_auth_token():
                gstn = "connected"
                try:
                    pref = vc.get_returns("GETPREF", fy=fy)
                    live["preferences"] = (pref or {}).get("data", {}).get("response") or []
                except VanayaError as exc:
                    warnings.append(f"GETPREF: {exc.message}")
                if to_p:
                    for rt in ("GSTR1", "GSTR1A", "GSTR3B"):
                        try:
                            rc = vc.get_returns("GETRET", ret_period=to_p)
                            live.setdefault("filed", {})[rt] = rc.get("data", rc)
                        except VanayaError as exc:
                            live.setdefault("filed", {})[rt] = {"error": exc.message}
        except VanayaError as exc:
            warnings.append(f"GSTN session: {exc.message}")

        # ---- App database: filing status + section totals ---------------- #
        filing_map = {}
        filing_qs = ReturnFiling.objects.filter(
            owner=user, gstin=active_gstin, fy=fy, period__in=periods
        )
        if client:
            filing_qs = filing_qs.filter(client=client)
        for r in filing_qs:
            filing_map[(r.return_type, r.period)] = {
                "return_type": r.return_type,
                "period": r.period,
                "status": r.status,
                "arn": r.arn,
                "filed_at": r.filed_at.isoformat() if r.filed_at else None,
            }

        data_qs = ReturnData.objects.filter(owner=user, fy=fy, period__in=periods)
        if client:
            data_qs = data_qs.filter(client=client)
        else:
            data_qs = data_qs.filter(client__isnull=True)
        totals_map = {}
        for row in data_qs:
            key = (row.return_type, row.period)
            prev = totals_map.setdefault(
                key,
                {"txval": 0.0, "igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0, "records": 0},
            )
            agg = _aggregate_payload(row.payload)
            for k in prev:
                prev[k] += agg.get(k, 0.0)

        reports = []
        for name, spec in REPORT_SPECS.items():
            rows = []
            for period in periods:
                for rt in spec["types"]:
                    totals = totals_map.get((rt, period), {})
                    filing = filing_map.get((rt, period))
                    entry = {
                        "period": period,
                        "return_type": rt,
                        "status": filing["status"] if filing else "UNKNOWN",
                        "arn": (filing or {}).get("arn", ""),
                        "filed_at": (filing or {}).get("filed_at"),
                        "taxable": round(totals.get("txval", 0.0), 2),
                        "igst": round(totals.get("igst", 0.0), 2),
                        "cgst": round(totals.get("cgst", 0.0), 2),
                        "sgst": round(totals.get("sgst", 0.0), 2),
                        "cess": round(totals.get("cess", 0.0), 2),
                        "records": totals.get("records", 0),
                        "local_data": bool(totals.get("records", 0)),
                    }
                    if spec.get("details"):
                        entry["sections"] = self._section_breakdown(data_qs, rt, period)
                    rows.append(entry)
            reports.append({"name": name, "types": spec["types"], "rows": rows})

        _log_api_call(
            request,
            "report-summary",
            "GET",
            active_gstin,
            "Success",
            (time.monotonic() - started) * 1000,
        )
        return Response(
            {
                "success": True,
                "fy": fy,
                "gstin": active_gstin,
                "gstn": gstn,
                "periods": periods,
                "live": live,
                "reports": reports,
                "warnings": warnings,
            }
        )

    @action(detail=False, methods=["post"], url_path="profile")
    def profile(self, request):
        """Live taxpayer profile from GSTN (PROFILE on the auth endpoint)."""
        return self._gst_call(
            request,
            "authenticate:PROFILE",
            "POST",
            lambda: self._cred_client(request.data).get_profile(),
            gstin=request.data.get("gstin", ""),
        )

    @action(detail=False, methods=["post"], url_path="logout")
    def logout(self, request):
        """End the Vanaya session and purge its cached state."""
        return self._gst_call(
            request,
            "authenticate:LOGOUT",
            "POST",
            lambda: self._cred_client(request.data).logout(),
            gstin=request.data.get("gstin", ""),
        )

    def _build_client(self, data):
        if isinstance(data, dict):
            merged = {k: v for k, v in data.items()}
        else:
            merged = data
        if merged.get("ip") and not merged.get("ip_usr"):
            merged["ip_usr"] = merged.pop("ip")
        # Explicit gstin + username -> honor them exactly. Otherwise rotate
        # through the sandbox credential pool (cache-first, login-once).
        if merged.get("gstin") and merged.get("username"):
            return VanayaClient.from_data(merged)
        if merged.get("gstin"):
            return VanayaClient.from_pool(requested_gstin=merged["gstin"])
        return VanayaClient.from_pool()


# --------------------------------------------------------------------------- #
# Dashboards
# --------------------------------------------------------------------------- #


class DashboardViewSet(viewsets.ViewSet):
    """Aggregated real data for the user / admin / super-admin dashboards."""

    @action(detail=False, methods=["get"], url_path="user")
    def user(self, request):
        user = request.user
        clients = GSTClient.objects.filter(owner=user)
        reminders = Reminder.objects.filter(user=user)
        return Response(
            {
                "clients_count": clients.count(),
                "reminders": ReminderSerializer(reminders[:20], many=True).data,
                "reminders_due": reminders.filter(is_done=False)
                .filter(date__lte=timezone.localdate())
                .count(),
                "notifications_unread": Notification.objects.filter(
                    user=user, is_read=False
                ).count(),
                "return_counts": dict(
                    ReturnData.objects.filter(owner=user)
                    .values_list("return_type")
                    .annotate(total=Count("id"))
                ),
                "return_total": ReturnData.objects.filter(owner=user).count(),
            }
        )

    @action(detail=False, methods=["get"], url_path="admin")
    def admin(self, request):
        if not _is_staff(request):
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
        month_start = timezone.now().replace(day=1)
        clients = GSTClient.objects.all()
        firms = Firm.objects.annotate(client_count=Count("clients"))
        return Response(
            {
                "total_clients": clients.count(),
                "total_staff": User.objects.filter(is_superuser=False).count(),
                "filings_this_month": ReturnData.objects.filter(
                    created_at__gte=month_start
                ).count(),
                "total_documents": Document.objects.count(),
                "recent_clients": GSTClientSerializer(clients[:8], many=True).data,
                "firms": [
                    {
                        "id": f.id,
                        "name": f.name,
                        "clients": f.client_count,
                        "plan": f.plan,
                        "status": "Active" if f.is_active else "Inactive",
                        "filed": ReturnData.objects.filter(client__firm=f).count(),
                    }
                    for f in firms[:20]
                ],
                "recent_documents": DocumentSerializer(Document.objects.all()[:8], many=True).data,
            }
        )

    @action(detail=False, methods=["get"], url_path="super")
    def super_(self, request):
        if not request.user.is_superuser:
            return Response(
                {"detail": "Super admin access required."}, status=status.HTTP_403_FORBIDDEN
            )
        today = timezone.localdate()
        api_logs = ApiCallLog.objects.all()
        failed_logins = LoginActivity.objects.filter(success=False)[:10]
        firms = Firm.objects.annotate(client_count=Count("clients")).order_by("-client_count")
        total_logs = api_logs.count()
        failed = api_logs.filter(status__iexact="Failed").count()
        return Response(
            {
                "total_firms": firms.count(),
                "active_firms": firms.filter(is_active=True).count(),
                "total_clients": GSTClient.objects.count(),
                "api_calls_today": api_logs.filter(created_at__date=today).count(),
                "total_api_calls": total_logs,
                "api_success_rate": (
                    round((total_logs - failed) / total_logs * 100, 1) if total_logs else 0
                ),
                "top_firms": [
                    {"name": f.name, "clients": f.client_count, "plan": f.plan} for f in firms[:10]
                ],
                "firms": FirmSerializer(firms[:100], many=True).data,
                "failed_api_logs": ApiCallLogSerializer(
                    api_logs.filter(status__iexact="Failed")[:15], many=True
                ).data,
                "security_alerts": [
                    {
                        "id": a.id,
                        "type": "Failed Login",
                        "time": a.created_at.isoformat(),
                        "ip": a.ip_address,
                        "description": f"Failed login attempt for {a.user.email}",
                    }
                    for a in failed_logins
                ]
                + [
                    {
                        "id": log.id,
                        "type": "API Error",
                        "time": log.created_at.isoformat(),
                        "ip": "",
                        "description": f"{log.method} {log.endpoint}: {log.error[:120]}",
                    }
                    for log in api_logs.filter(status__iexact="Failed").exclude(error="")[:5]
                ],
            }
        )
