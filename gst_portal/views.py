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
from vanaya.services import VanayaClient, VanayaError

from .models import (
    ApiCallLog,
    DashboardLink,
    Document,
    Firm,
    GSTClient,
    NewsArticle,
    Notification,
    Reminder,
    ReturnData,
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
    return {
        "success": True,
        "company_name": company_name,
        "name": company_name,
        "gstin": data.get("gstin") or gstin,
        "trade_name": data.get("tradeNam") or "",
        "address": _fmt_vanaya_address(addr),
        "branch_address": _fmt_vanaya_address(branch_addr),
        "state": addr.get("stcd") or "",
        "state_code": data.get("stjCd") or "",
        "registration_date": data.get("rgdt") or "",
        "last_update": data.get("lstupdt") or "",
        "constitution": data.get("ctb") or "",
        "status": (data.get("sts") or "").upper(),
        "einvoice_status": data.get("einvoiceStatus") or "",
        "status_success": data.get("sts") or "Active",
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
            "period": src.get("period") or "",
            "fy": src.get("fy") or "",
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
                defaults={"payload": rows if isinstance(rows, list) else []},
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
    def _gst_call(self, request, endpoint, method, fn, gstin="", **handler):
        """Run a Vanaya call, audit it into ApiCallLog and normalize errors."""
        started = time.monotonic()
        try:
            body = fn()
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
        )

    @action(detail=False, methods=["get"], url_path="filing-status")
    def filing_status(self, request):
        """Per-client filing status for the logged-in user.

        Uses the user's own saved return grids (ReturnData) as the source of
        truth and, when a live Vanaya session exists, tries GETPREF for the
        requested FY to attach the GSTN "latest filed" snapshot. Individual
        GSTIN verification stays available through ``/gst/search/<gstin>/``.
        """
        fy = request.query_params.get("fy") or ""
        user = request.user
        rows = ReturnData.objects.filter(owner=user)
        filed_counts = dict(
            rows.exclude(return_type="").values_list("return_type").annotate(total=Count("id"))
        )
        saved_periods = list(
            rows.exclude(fy="").order_by("-fy", "-period").values("fy", "period").distinct()[:12]
        )
        clients = GSTClient.objects.filter(owner=user)[:15]
        live = None
        active_gstin = (request.query_params.get("gstin") or "").strip()
        if fy:
            try:
                client = self._build_client(request.query_params)
                live = client.get_returns("GETPREF", fy=fy)
            except VanayaError as exc:
                live = {"success": False, "detail": exc.message}
            except Exception as exc:  # pragma: no cover - defensive
                live = {"success": False, "detail": str(exc)}

        response = {
            "success": True,
            "fy": fy,
            "gstin": active_gstin or settings.VANAYA_GSTIN,
            "gstn": (
                (
                    "connected"
                    if VanayaClient.from_credential(gstin=active_gstin).get_auth_token()
                    else "disconnected"
                )
                if active_gstin
                else (
                    "connected"
                    if VanayaClient.from_defaults().get_auth_token()
                    else "disconnected"
                )
            ),
            "filed_counts": {
                "GSTR1": filed_counts.get("GSTR1", 0),
                "GSTR1A": filed_counts.get("GSTR1A", 0),
                "GSTR3B": filed_counts.get("GSTR3B", 0),
                "TDS_TCS": filed_counts.get("TDS_TCS", 0),
            },
            "filed_total": rows.count(),
            "periods": saved_periods,
            "clients": [
                {
                    "id": c.id,
                    "name": c.name or "",
                    "gstin": c.gstin or "",
                    "mobile": c.mobile or "",
                    "firm": c.firm.name if c.firm else "",
                    "status": "Active" if c.reg_date else "Registered",
                }
                for c in clients
            ],
            "last_sync": timezone.now().isoformat(),
        }
        if live is not None:
            response["gstn_latest"] = live
        return Response(response)

    @action(detail=False, methods=["post"], url_path="ret-save")
    def ret_save(self, request):
        """PUT a GSTR section to GSTN (``/taxpayerapi/v2.2/returns/<type>``).

        Body: ``{"return_type": "gstr1", "ret_period": "012025",
        "payload": {"ctin": "...", "inv": [...]}}`` -> ``reference_id``.
        """
        data = request.data or {}
        return_type = (data.get("return_type") or data.get("type") or "").lower().strip("/")
        ret_period = data.get("ret_period") or data.get("period") or ""
        payload = data.get("payload") or data.get("data") or {}
        if not return_type or not ret_period or not isinstance(payload, dict):
            return Response(
                {"success": False, "detail": "return_type, ret_period and payload are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self._gst_call(
            request,
            f"returns_v2:save:{return_type}",
            "PUT",
            lambda: self._build_client(data).gstr_save(return_type, ret_period, payload),
            gstin=data.get("gstin", ""),
        )

    @action(detail=False, methods=["get"], url_path="ret-section")
    def ret_section(self, request):
        """GET a GSTR section (``/taxpayerapi/v2.2/returns/<type>``)."""
        return_type = (request.query_params.get("return_type") or "").lower().strip("/")
        ret_period = (
            request.query_params.get("ret_period") or request.query_params.get("period") or ""
        )
        if not return_type or not ret_period:
            return Response(
                {"success": False, "detail": "return_type and ret_period are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        section_params = {
            k: v for k, v in request.query_params.items() if k in ("ctin", "doc_id", "inv_period")
        }
        return self._gst_call(
            request,
            f"returns_v2:get:{return_type}",
            "GET",
            lambda: self._build_client(request.query_params).gstr_get(
                return_type, ret_period, **section_params
            ),
            gstin=request.query_params.get("gstin", ""),
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
