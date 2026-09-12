import base64
import json
import tempfile
from pathlib import Path
from unittest import mock

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.conf import settings
from django.core.cache import cache
from django.http import QueryDict
from django.test import SimpleTestCase

from . import crypto
from .services import AUTHENTICATE_PATH, RETURNS_PATH, VanayaClient, VanayaError
from .views import VanayaViewSet


def _aes_ecb_encrypt(key_bytes: bytes, data: bytes) -> bytes:
    return AES.new(key_bytes, AES.MODE_ECB).encrypt(pad(data, AES.block_size))


class JavaBridgeTests(SimpleTestCase):
    """End-to-end sanity checks against the real Java CLI helpers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Scratch area: compiled classes + a throwaway RSA keypair.
        cls.workdir = Path(tempfile.mkdtemp(prefix="vanaya-test-"))
        cls.class_dir = crypto.ensure_built(
            settings.VANAYA_JAVA_SOURCE_DIR, cls.workdir / "classes"
        )

        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()

        cls.plain_key_path = cls.workdir / "plain.pem"
        cls.plain_key_path.write_bytes(
            cls.private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        cls.encrypted_key_path = cls.workdir / "encrypted.pem"
        cls.encrypted_key_path.write_bytes(
            cls.private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(b"test-pass"),
            )
        )
        cls.public_key_path = cls.workdir / "public.pem"
        cls.public_key_path.write_bytes(
            cls.public_key.public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

        # 32-char string -> 32 bytes -> AES-256 (matches the real app key).
        cls.app_key = "a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8"

        # Base64 of a 32-byte EK; used by the two-step payload tests.
        cls.ek = base64.b64encode(b"X" * 32).decode()

    @classmethod
    def tearDownClass(cls):
        import shutil

        shutil.rmtree(cls.workdir, ignore_errors=True)
        super().tearDownClass()

    def _verify(self, message: str, signature: str):
        self.public_key.verify(
            base64.b64decode(signature),
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def _auth_token_message(self) -> str:
        return (
            "v2.0:taxmatetest::TXN20260912120000AB12:20260912120000"
            "+0530:33CGFPA6633Q4Z4:OTPREQUEST"
        )

    def test_signature_plain_key(self):
        message = self._auth_token_message()
        signature = crypto.sign_sha256(str(self.plain_key_path), message, self.class_dir)
        self._verify(message, signature)

    def test_signature_encrypted_key(self):
        message = self._auth_token_message()
        signature = crypto.sign_sha256(
            str(self.encrypted_key_path), message, self.class_dir, "test-pass"
        )
        self._verify(message, signature)

    def test_app_key_encryption_round_trip(self):
        encrypted = crypto.rsa_encrypt_app_key(
            str(self.public_key_path), self.app_key, self.class_dir
        )
        decrypted = self.private_key.decrypt(base64.b64decode(encrypted), padding.PKCS1v15())
        self.assertEqual(decrypted, self.app_key.encode())

    def test_otp_round_trip(self):
        encrypted = crypto.encrypt_otp(
            str(self.public_key_path), self.app_key, "575757", self.class_dir, "user1"
        )
        plain = unpad(
            AES.new(self.app_key.encode(), AES.MODE_ECB).decrypt(base64.b64decode(encrypted)),
            AES.block_size,
        )
        self.assertEqual(plain, b"575757")

    def test_sek_round_trip(self):
        sek = base64.b64encode(
            _aes_ecb_encrypt(self.app_key.encode(), base64.b64decode(self.ek))
        ).decode()
        self.assertEqual(crypto.decrypt_sek(self.app_key, sek, self.class_dir), self.ek)

    def test_api_response_round_trip_full(self):
        data_key = b"K" * 32
        ek_bytes = base64.b64decode(self.ek)
        rek = base64.b64encode(_aes_ecb_encrypt(ek_bytes, data_key)).decode()
        plain = base64.b64encode(b'{"ok": true, "n": 3}')
        data = base64.b64encode(_aes_ecb_encrypt(data_key, plain)).decode()
        decrypted = crypto.decrypt_api_response(self.ek, rek, data, self.class_dir)
        self.assertEqual(json.loads(decrypted), {"ok": True, "n": 3})

    def test_decrypt_search_data(self):
        result = crypto.decrypt_search_data(
            base64.b64encode(b'{"gstin": "33CGFPA6633Q4Z4"}').decode()
        )
        self.assertEqual(result, {"gstin": "33CGFPA6633Q4Z4"})


class VanayaClientTests(SimpleTestCase):
    """Behaviour of the public vs authenticated request/response branches."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.workdir = Path(tempfile.mkdtemp(prefix="vanaya-client-"))
        cls.class_dir = crypto.ensure_built(
            settings.VANAYA_JAVA_SOURCE_DIR, cls.workdir / "classes"
        )
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private_key = key
        cls.public_key_path = cls.workdir / "public.pem"
        cls.public_key_path.write_bytes(
            key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        cls.private_key_path = cls.workdir / "private.pem"
        cls.private_key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        cls.ek = base64.b64encode(b"X" * 32).decode()

    @classmethod
    def tearDownClass(cls):
        import shutil

        shutil.rmtree(cls.workdir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.client = VanayaClient(
            gstin="33CGFPA6633Q4Z4",
            username="TN_NT2.21614",
            cust_id="taxmatetest",
            state_code="33",
            ip_usr="137.232.3.35",
            base_url="https://yoda.api.vayanagsp.in",
            private_key_path=str(self.private_key_path),
            public_key_path=str(self.public_key_path),
            key_password="",
            java_source_dir=settings.VANAYA_JAVA_SOURCE_DIR,
            java_class_dir=self.class_dir,
            timeout=10,
        )

    def test_build_client_normalizes_querydict_scalar_values(self):
        # GET endpoints pass request.query_params (a QueryDict). Values must
        # stay scalars, not lists, or the signed headers break ("cust_id" as
        # ['taxmatetest']). Regresses the 502 seen on /vanaya/search/.
        data = QueryDict(
            "gstin=27AAACR5055K1Z7&username=TN_NT2.21614&cust_id=taxmatetest&ip_usr=137.232.3.35"
        )
        client = VanayaViewSet()._build_client(data)
        self.assertIsInstance(client.gstin, str)
        self.assertEqual(client.gstin, "27AAACR5055K1Z7")
        self.assertEqual(client.username, "TN_NT2.21614")
        self.assertEqual(client.cust_id, "taxmatetest")
        self.assertEqual(client.ip_usr, "137.232.3.35")

    def test_public_search_needs_no_session_and_base64_decodes(self):
        payload = {
            "gstin": "33CGFPA6633Q4Z4",
            "dty": "Regular",
            "sts": "Active",
        }
        body = {
            "status_cd": "1",
            "data": base64.b64encode(json.dumps(payload).encode()).decode(),
            "rek": "",
            "hmac": "",
        }
        with mock.patch(
            "vanaya.services.requests.get",
            return_value=mock.Mock(json=lambda: body, raise_for_status=lambda: None),
        ) as mocked:
            result = self.client.search_gstin()

        headers = mocked.call_args.kwargs["headers"]
        self.assertEqual(headers.get("auth-token"), None)
        self.assertNotIn("username", headers)
        self.assertNotIn("gstin", headers)
        self.assertEqual(headers["cust_id"], "taxmatetest")
        self.assertEqual(result["data"], payload)

    def test_authenticated_get_requires_session_and_decrypts_payload(self):
        # Simulate a two-step encrypted response with a cached dek.
        data_key = b"K" * 32
        rek = base64.b64encode(_aes_ecb_encrypt(base64.b64decode(self.ek), data_key)).decode()
        plain = base64.b64encode(b'{"ok": true, "n": 3}')
        data = base64.b64encode(_aes_ecb_encrypt(data_key, plain)).decode()
        body = {"status_cd": "1", "data": data, "rek": rek, "hmac": "x"}
        self.client._cache_set("dek", self.ek)
        self.client._cache_set("auth_token", "tok123")

        with mock.patch(
            "vanaya.services.requests.get",
            return_value=mock.Mock(json=lambda: body, raise_for_status=lambda: None),
        ) as mocked:
            result = self.client.get(
                RETURNS_PATH, "GETPREF", params={"action": "GETPREF", "gstin": self.client.gstin}
            )

        headers = mocked.call_args.kwargs["headers"]
        self.assertEqual(headers["auth-token"], "tok123")
        self.assertEqual(headers["username"], "TN_NT2.21614")
        self.assertEqual(headers["gstin"], "33CGFPA6633Q4Z4")
        self.assertEqual(result["data"], {"ok": True, "n": 3})

    def test_authenticated_get_without_session_raises(self):
        body = {"status_cd": "1", "data": "", "rek": "", "hmac": ""}
        with mock.patch(
            "vanaya.services.requests.get",
            return_value=mock.Mock(json=lambda: body, raise_for_status=lambda: None),
        ):
            with self.assertRaises(VanayaError) as ctx:
                self.client.get(
                    RETURNS_PATH,
                    "GETPREF",
                    params={"action": "GETPREF", "gstin": "33CGFPA6633Q4Z4"},
                )
        self.assertEqual(ctx.exception.status_code, 401)

    def test_otp_flow_does_not_require_prior_session(self):
        with mock.patch(
            "vanaya.services.requests.post",
            return_value=mock.Mock(json=lambda: {"status_cd": "1"}, raise_for_status=lambda: None),
        ) as mocked:
            result = self.client.send_otp()

        headers = mocked.call_args.kwargs["headers"]
        url = mocked.call_args.args[0]
        self.assertEqual(url, "https://yoda.api.vayanagsp.in" + AUTHENTICATE_PATH)
        self.assertNotIn("auth-token", headers)
        self.assertEqual(mocked.call_args.kwargs["json"]["action"], "OTPREQUEST")
        self.assertEqual(result, {"status_cd": "1"})

    def test_send_otp_regenerates_temp_app_key_every_call(self):
        with mock.patch(
            "vanaya.services.requests.post",
            return_value=mock.Mock(json=lambda: {"status_cd": "1"}, raise_for_status=lambda: None),
        ):
            self.client.send_otp()
            first = self.client._cache_get("tmp:app_key")
            self.client.send_otp()  # re-send discards any failed attempt
            second = self.client._cache_get("tmp:app_key")

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertNotEqual(first, second)
        # Nothing promoted to the permanent tier yet.
        self.assertIsNone(self.client._cache_get("app_key"))
        self.assertIsNone(self.client.get_auth_token())

    def test_authenticate_without_prior_send_otp_raises(self):
        with mock.patch("vanaya.services.requests.post"):
            with self.assertRaises(VanayaError) as ctx:
                self.client.authenticate("575757")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_authenticate_promotes_temp_key_to_permanent_session(self):
        expiry_minutes = 180
        body = {
            "status_cd": "1",
            "auth_token": "tok123",
            "sek": "sek-encrypted",
            "expiry": expiry_minutes,
        }
        with mock.patch(
            "vanaya.services.requests.post",
            return_value=mock.Mock(json=lambda: body, raise_for_status=lambda: None),
        ):
            self.client.send_otp()
            with (
                mock.patch("vanaya.services.crypto.decrypt_sek", return_value="sek") as dek_mock,
                mock.patch("vanaya.services.crypto.encrypt_otp", return_value="otp-enc"),
            ):
                result = self.client.authenticate("575757")

        # Temp pair is consumed by a successful verification.
        self.assertIsNone(self.client._cache_get("tmp:app_key"))
        self.assertIsNone(self.client._cache_get("tmp:app_key_enc"))
        # Permanent tier holds the same raw key and the session metadata.
        self.assertEqual(self.client._cache_get("app_key"), result["app_key"])
        self.assertEqual(self.client._cache_get("auth_token"), "tok123")
        self.assertEqual(self.client._cache_get("expiry"), expiry_minutes)
        self.assertEqual(self.client._cache_get("dek"), "sek")
        self.assertEqual(self.client._cache_get("auth_response"), body)
        dek_mock.assert_called_once()

    def test_clear_session_removes_temp_and_permanent_keys(self):
        body = {
            "status_cd": "1",
            "auth_token": "tok123",
            "sek": "sek-encrypted",
            "expiry": 60,
        }
        with mock.patch(
            "vanaya.services.requests.post",
            return_value=mock.Mock(json=lambda: body, raise_for_status=lambda: None),
        ):
            self.client.send_otp()
            with (
                mock.patch("vanaya.services.crypto.decrypt_sek", return_value="sek"),
                mock.patch("vanaya.services.crypto.encrypt_otp", return_value="otp-enc"),
            ):
                self.client.authenticate("575757")

        self.assertTrue(self.client.has_active_session())
        self.client.clear_session()
        self.assertFalse(self.client.has_active_session())
        self.assertIsNone(self.client._cache_get("tmp:app_key"))
        for suffix in ("app_key", "app_key_enc", "dek", "expiry", "auth_response"):
            self.assertIsNone(self.client._cache_get(suffix))
