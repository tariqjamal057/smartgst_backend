from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .serializers import UserRegistrationSerializer, UserSerializer


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
        subject = "Your SmartGST OTP Code"
        message = (
            f"Your OTP for SmartGST registration is: {otp}\n\nThis OTP is valid for 10 minutes."
        )
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
            return Response({"success": True, "message": "OTP sent successfully."})
        except Exception as e:
            # If email fails, still return success so dev flow isn't blocked
            # In production, remove this fallback
            return Response(
                {"success": True, "message": "OTP stored (email send failed: " + str(e) + ")"},
                status=status.HTTP_200_OK,
            )


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
    # This view already handles obtaining tokens with username/password
    pass


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
