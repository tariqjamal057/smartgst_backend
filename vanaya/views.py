from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    AuthenticateSerializer,
    GenericGetSerializer,
    GenericPostSerializer,
    SendOTPSerializer,
)
from .services import VanayaClient, VanayaError


def _error_response(exc: VanayaError) -> Response:
    return Response(
        {"detail": exc.message, "error_cd": exc.error_cd},
        status=exc.status_code,
    )


class VanayaViewSet(viewsets.ViewSet):
    """Base API surface mirroring the Vanaya Postman collection.

    Endpoints:
      POST /api/vanaya/send-otp/
      POST /api/vanaya/authenticate/
      GET  /api/vanaya/search/
      GET  /api/vanaya/returns/
      GET  /api/vanaya/ping/
      GET  /api/vanaya/call/            (generic authenticated GET)
      POST /api/vanaya/call/            (generic POST)
    """

    permission_classes = (IsAuthenticated,)

    def _build_client(self, data: dict) -> VanayaClient:
        merged = dict(data or {})
        if merged.get("ip") and not merged.get("ip_usr"):
            merged["ip_usr"] = merged.pop("ip")
        return VanayaClient.from_data(merged)

    # ------------------------------------------------------------------ #
    # Auth API                                                           #
    # ------------------------------------------------------------------ #
    @action(detail=False, methods=["post"], url_path="send-otp")
    def send_otp(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            client = self._build_client(serializer.validated_data)
            body = client.send_otp()
            return Response(body, status=status.HTTP_200_OK)
        except VanayaError as exc:
            return _error_response(exc)

    @action(detail=False, methods=["post"], url_path="authenticate")
    def authenticate(self, request):
        serializer = AuthenticateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            client = self._build_client(serializer.validated_data)
            body = client.authenticate(serializer.validated_data["otp"])
            return Response(body, status=status.HTTP_200_OK)
        except VanayaError as exc:
            return _error_response(exc)

    @action(detail=False, methods=["post"], url_path="logout")
    def logout(self, request):
        try:
            client = self._build_client(request.data or {})
            client.clear_session()
        except VanayaError as exc:
            return _error_response(exc)
        return Response({"detail": "Vanaya session cleared."})

    # ------------------------------------------------------------------ #
    # Postman mirror helpers (authenticated GET/POST)                    #
    # ------------------------------------------------------------------ #
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        try:
            client = self._build_client(request.query_params)
            gstin = request.query_params.get("gstin")
            return Response(client.search_gstin(gstin))
        except VanayaError as exc:
            return _error_response(exc)

    @action(detail=False, methods=["get"], url_path="returns")
    def returns(self, request):
        params = {
            key: value for key, value in request.query_params.items() if key not in ("gstin",)
        }
        try:
            client = self._build_client(request.query_params)
            return Response(client.get_returns(**params))
        except VanayaError as exc:
            return _error_response(exc)

    @action(detail=False, methods=["get"], url_path="ping")
    def ping(self, request):
        return Response({"status": "pong"})

    # ------------------------------------------------------------------ #
    # Generic handlers: pass any endpoint/action through the base client #
    # ------------------------------------------------------------------ #
    @action(detail=False, methods=["get", "post"], url_path="call")
    def call(self, request):
        serializer_cls = GenericGetSerializer if request.method == "GET" else GenericPostSerializer
        payload = request.query_params if request.method == "GET" else request.data
        serializer = serializer_cls(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            client = self._build_client(serializer.validated_data)
            if request.method == "GET":
                params = dict(request.query_params)
                params.pop("path", None)
                params.pop("action", None)
                params.pop("gstin", None)
                result = client.get(
                    serializer.validated_data["path"],
                    serializer.validated_data["action"],
                    params=params or None,
                )
            else:
                result = client.post(
                    serializer.validated_data["path"],
                    serializer.validated_data["action"],
                    payload=serializer.validated_data.get("payload") or {},
                )
            return Response(result)
        except VanayaError as exc:
            return _error_response(exc)
