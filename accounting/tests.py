from unittest import mock
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from tenants.models import Tenant
from vanaya.services import VanayaClient, VanayaError

from .models import CompanySetting

User = get_user_model()

DUMMY_KEY = "C:/does-not-exist/private.pem"


def _body(payload: dict) -> dict:
    # Shape returned by VanayaClient._decrypt_response(public=True): the
    # ``data`` field is already base64-decoded into a dict.
    return {"status_cd": "1", "data": payload, "rek": "", "hmac": ""}


@override_settings(
    VANAYA_PRIVATE_KEY_PATH=DUMMY_KEY,
    VANAYA_PUBLIC_KEY_PATH=DUMMY_KEY,
    VANAYA_GSTIN="33CGFPA6633Q4Z4",
)
class GstLookupViewSetTests(APITestCase):
    """Real-Vanaya-backed GST lookup: field mapping + credential resolution."""

    def setUp(self):
        self.user = User.objects.create_user(email="lookup@test.com", password="testpass123")
        self.client.force_authenticate(user=self.user)

        self.gstin = "33CGFPA6633Q4Z4"
        self.url = reverse("gst-lookup-detail", args=[self.gstin])

        payload = {
            "lgnm": "Taxmate Technology Private Limited",
            "tradeNam": "GSTN",
            "sts": "Active",
            "gstin": self.gstin,
            "pradr": {
                "addr": {
                    "bno": "252",
                    "bnm": "Gold Hill Supreme",
                    "st": "Shantipura Cross Roads",
                    "loc": "Electronic City Phase 2",
                    "pncd": "600123",
                    "stcd": "Tamil Nadu",
                }
            },
            "adadr": [{"addr": {"bno": "12", "bnm": "Branch Office", "stcd": "Karnataka"}}],
        }
        self.body = _body(payload)

    def test_maps_vanaya_payload_using_env_defaults_when_unauthenticated(self):
        self.client.force_authenticate(user=None)  # company-creation page

        with mock.patch.object(
            VanayaClient, "search_gstin", autospec=True, return_value=dict(self.body)
        ) as mocked:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue(data["success"])
        self.assertEqual(data["company_name"], "Taxmate Technology Private Limited")
        self.assertEqual(data["name"], "Taxmate Technology Private Limited")
        self.assertEqual(data["gstin"], self.gstin)
        self.assertEqual(
            data["address"],
            "252, Gold Hill Supreme, Shantipura Cross Roads, Electronic City Phase 2, 600123",
        )
        self.assertEqual(data["branch_address"], "12, Branch Office")
        self.assertEqual(data["state"], "Tamil Nadu")
        self.assertEqual(data["status"], "ACTIVE")
        for field in ("country", "email", "website", "contact_person", "contact_no"):
            self.assertEqual(data[field], "")

        client, gstin = mocked.call_args.args
        self.assertEqual(gstin, self.gstin)
        self.assertEqual(client.gstin, "33CGFPA6633Q4Z4")

    def test_uses_all_four_credentials_when_passed(self):
        creds = {
            "gstin": "29AABCT1331L1Z2",
            "username": "KA_NT3.12345",
            "ip": "10.0.0.1",
            "cust_id": "mycust",
        }
        url = f"{self.url}?{urlencode(creds)}"
        with mock.patch.object(
            VanayaClient, "search_gstin", autospec=True, return_value=dict(self.body)
        ) as mocked:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        client, _ = mocked.call_args.args
        self.assertEqual(client.gstin, "29AABCT1331L1Z2")
        self.assertEqual(client.username, "KA_NT3.12345")
        self.assertEqual(client.ip_usr, "10.0.0.1")
        self.assertEqual(client.cust_id, "mycust")

    def test_uses_tenant_company_gstin_when_tenant_header_present(self):
        tenant = Tenant.objects.create(name="Acme", subdomain_name="acme")
        CompanySetting.objects.create(
            tenant=tenant, company_name="Acme Pvt Ltd", gstin="29AABCT1331L1Z2", is_active=True
        )
        with mock.patch.object(
            VanayaClient, "search_gstin", autospec=True, return_value=dict(self.body)
        ) as mocked:
            response = self.client.get(self.url, HTTP_X_TENANT_ID=str(tenant.id))

        self.assertEqual(response.status_code, 200)
        client, _ = mocked.call_args.args
        self.assertEqual(client.gstin, "29AABCT1331L1Z2")

    def test_returns_error_shape_when_gateway_fails(self):
        with mock.patch.object(
            VanayaClient,
            "search_gstin",
            side_effect=VanayaError("GSTIN not found", error_cd="404", status_code=422),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["detail"], "GSTIN not found")
        self.assertEqual(response.data["error_cd"], "404")

    def test_empty_payload_maps_to_empty_strings(self):
        with mock.patch.object(
            VanayaClient, "search_gstin", autospec=True, return_value=_body({})
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        for field in (
            "company_name",
            "name",
            "address",
            "branch_address",
            "state",
            "country",
            "email",
            "website",
            "contact_person",
            "contact_no",
        ):
            self.assertEqual(response.data[field], "")
        self.assertEqual(response.data["gstin"], self.gstin)
