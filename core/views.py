from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import LoginActivity, NotificationPreference, User, UserSession
from .serializers import (
    NotificationPreferenceSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)


def send_password_reset_email(user, request):
    current_site = request.get_host()
    mail_subject = "Reset your SmartGST password."
    message = render_to_string(
        "core/password_reset_email.html",
        {
            "user": user,
            "domain": current_site,
            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": default_token_generator.make_token(user),
        },
    )
    send_mail(mail_subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _parse_device(ua):
    ua = ua or ""
    if "Mobile" in ua:
        return "Mobile device"
    if "Windows" in ua:
        return "Windows device"
    if "Macintosh" in ua or "Mac OS" in ua:
        return "Mac device"
    if "Linux" in ua:
        return "Linux device"
    return "Unknown device"


def _device_type(ua):
    ua = ua or ""
    if "Mobile" in ua:
        return "mobile"
    if "iPad" in ua or "Tablet" in ua:
        return "tablet"
    return "web"


class SecurityViewSet(ViewSet):
    permission_classes = (IsAuthenticated,)

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        current = request.data.get("current_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not current or not new_password or not confirm_password:
            return Response(
                {"detail": "All password fields are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        if not user.check_password(current):
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_password != confirm_password:
            return Response(
                {"detail": "New passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new_password) < 8:
            return Response(
                {"detail": "New password must be at least 8 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.save()
        # Invalidate all other sessions (keep current token)
        UserSession.objects.filter(user=user).exclude(is_current=True).update(is_active=False)
        return Response({"detail": "Password changed successfully."})

    @action(detail=False, methods=["get"])
    def sessions(self, request):
        rows = UserSession.objects.filter(user=request.user).order_by("-last_active_at")
        return Response(
            [
                {
                    "id": s.id,
                    "device": s.device,
                    "device_type": s.device_type,
                    "ip_address": s.ip_address,
                    "location": s.location,
                    "is_current": s.is_current,
                    "is_active": s.is_active,
                    "last_active_at": s.last_active_at.isoformat(),
                }
                for s in rows
            ]
        )

    @action(detail=True, methods=["post"])
    def revoke_session(self, request, pk=None):
        session = UserSession.objects.filter(pk=pk, user=request.user).first()
        if not session:
            return Response(
                {"detail": "Session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if session.is_current:
            return Response(
                {"detail": "Cannot revoke the current session."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        session.is_active = False
        session.save()
        return Response({"detail": "Session revoked."})

    @action(detail=False, methods=["post"])
    def revoke_all(self, request):
        UserSession.objects.filter(user=request.user).exclude(is_current=True).update(
            is_active=False
        )
        return Response({"detail": "All other sessions revoked."})

    @action(detail=False, methods=["get"])
    def login_activity(self, request):
        rows = LoginActivity.objects.filter(user=request.user)[:20]
        return Response(
            [
                {
                    "id": a.id,
                    "ip_address": a.ip_address,
                    "location": a.location,
                    "device": a.device,
                    "success": a.success,
                    "created_at": a.created_at.isoformat(),
                }
                for a in rows
            ]
        )


class SendOtpView(generics.GenericAPIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        if not email or not otp:
            return Response(
                {"success": False, "message": "Email and otp are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Store OTP in cache for 10 minutes
        cache.set(f"otp_{email}", otp, timeout=600)
        print(f"[Account OTP] {email} -> {otp} (valid 10 min)", flush=True)
        subject = "Your SmartGST OTP Code"
        message = (
            f"Your OTP for SmartGST registration is: {otp}\n\nThis OTP is valid for 10 minutes."
        )
        from core.tasks import send_otp_email_task

        sent = False
        # Dispatch asynchronously via Celery so the request returns instantly
        # while the user fills in the rest of the sign-up form. If the broker
        # is down, fall back to a synchronous send so dev flow still works.
        try:
            send_otp_email_task.delay(subject, message, email, settings.DEFAULT_FROM_EMAIL)
            sent = True
        except Exception:
            # Celery/broker unavailable is expected in dev; sync fallback below.
            sent = False
        if not sent:
            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
                sent = True
            except Exception as e:
                return Response(
                    {"success": True, "message": "OTP stored (email send failed: " + str(e) + ")"},
                    status=status.HTTP_200_OK,
                )
        return Response({"success": True, "message": "OTP sent successfully."})


class UserRegistrationView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        email = request.data.get("email")
        otp = request.data.get("otp")
        if not email or not otp:
            return Response(
                {"detail": "Email and otp are required for registration."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cached_otp = cache.get(f"otp_{email}")
        if not cached_otp:
            return Response(
                {"detail": "OTP expired or not sent. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if str(otp) != str(cached_otp):
            return Response(
                {"detail": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # OTP verified, proceed with registration
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        cache.delete(f"otp_{email}")
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        ip = _get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")
        device = _parse_device(ua)
        response = super().post(request, *args, **kwargs)
        email = request.data.get("email", "")
        user = User.objects.filter(email=email).first()
        if response.status_code == status.HTTP_200_OK and user:
            LoginActivity.objects.create(
                user=user, ip_address=ip, device=device, user_agent=ua, success=True
            )
            token = response.data.get("access", "")
            response.data["user"] = UserSerializer(user).data
            session = UserSession.objects.create(
                user=user,
                device=device,
                device_type=_device_type(ua),
                ip_address=ip,
                user_agent=ua,
                token=token,
                is_current=True,
            )
            UserSession.objects.filter(user=user).exclude(pk=session.pk).update(is_current=False)
        elif response.status_code != status.HTTP_200_OK and user:
            LoginActivity.objects.create(
                user=user, ip_address=ip, device=device, user_agent=ua, success=False
            )
        return response


class LogoutView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationPreferenceSerializer

    def get_object(self):
        obj, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        return obj


class RequestPasswordResetView(generics.GenericAPIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            send_password_reset_email(user, request)  # Placeholder for actual email sending
            return Response(
                {"detail": "Password reset email sent if user exists."}, status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Password reset email sent if user exists."}, status=status.HTTP_200_OK
            )  # Always return 200 to prevent email enumeration


class SetNewPasswordView(generics.GenericAPIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        uidb64 = request.data.get("uidb64")
        token = request.data.get("token")
        password = request.data.get("password")
        password2 = request.data.get("password2")

        if password != password2:
            return Response(
                {"detail": "Password fields didn't match."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = get_user_model().objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            user.set_password(password)
            user.save()
            return Response({"detail": "Password reset successful."}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"detail": "The reset link is invalid."}, status=status.HTTP_400_BAD_REQUEST
            )
