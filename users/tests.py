"""
Automated unit & integration tests for Users, Authentication, Payment, and Dashboard.
"""
from django.test import TestCase, Client
from django.urls import reverse
import json
from users.models import Tenant, ApiKey, PaymentTransaction
from users.dashboard import get_tenant_dashboard_stats


class TenantAuthAndBillingTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_tenant_registration_and_api_key(self):
        # 1. Register new tenant
        payload = {"name": "Test Company", "email": "test@company.com"}
        response = self.client.post(
            reverse('tenant_register'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('api_key', data['data'])
        self.assertEqual(data['data']['name'], 'Test Company')
        self.assertEqual(data['data']['token_balance'], 0)

        api_key = data['data']['api_key']

        # 2. Access tenant profile with API key
        profile_res = self.client.get(
            reverse('tenant_profile'),
            HTTP_X_API_KEY=api_key
        )
        self.assertEqual(profile_res.status_code, 200)
        p_data = profile_res.json()
        self.assertEqual(p_data['data']['email'], 'test@company.com')

    def test_unauthorized_access_rejected(self):
        # Access protected endpoint without API key
        response = self.client.get(reverse('tenant_profile'))
        self.assertEqual(response.status_code, 401)

        # Access with invalid API key
        response_invalid = self.client.get(reverse('tenant_profile'), HTTP_X_API_KEY='sk_live_invalidkey123')
        self.assertEqual(response_invalid.status_code, 401)

    def test_password_login_returns_api_key(self):
        tenant = Tenant.objects.create(name="Password Tenant", email="password@tenant.com")
        tenant.set_password("correct horse battery staple")
        tenant.save(update_fields=['password'])

        invalid_res = self.client.post(
            reverse('tenant_login'),
            data=json.dumps({"email": tenant.email, "password": "wrong"}),
            content_type='application/json'
        )
        self.assertEqual(invalid_res.status_code, 401)

        login_res = self.client.post(
            reverse('tenant_login'),
            data=json.dumps({"email": tenant.email, "password": "correct horse battery staple"}),
            content_type='application/json'
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertEqual(login_res.json()['data']['api_key'], tenant.api_keys.get().key)

    def test_payment_adapter_credits_5m_tokens(self):
        tenant = Tenant.objects.create(name="Billing Tenant", email="billing@tenant.com", token_balance=0)
        api_key = ApiKey.objects.create(tenant=tenant)

        # Checkout
        checkout_res = self.client.post(reverse('payment_checkout'), HTTP_X_API_KEY=api_key.key)
        self.assertEqual(checkout_res.status_code, 200)
        checkout_data = checkout_res.json()['data']
        self.assertEqual(checkout_data['tokens_granted'], 5_000_000)

        # Confirm payment
        confirm_res = self.client.post(
            reverse('payment_confirm'),
            data=json.dumps({"order_id": checkout_data['order_id'], "transaction_id": "TXN-TEST-12345"}),
            content_type='application/json',
            HTTP_X_API_KEY=api_key.key
        )
        self.assertEqual(confirm_res.status_code, 200)
        c_data = confirm_res.json()['data']
        self.assertEqual(c_data['new_balance'], 5_000_000)

        tenant.refresh_from_db()
        self.assertEqual(tenant.token_balance, 5_000_000)
        self.assertEqual(PaymentTransaction.objects.filter(tenant=tenant).count(), 1)

    def test_dashboard_stats(self):
        tenant = Tenant.objects.create(name="Stats Tenant", email="stats@tenant.com", token_balance=5000)
        api_key = ApiKey.objects.create(tenant=tenant)

        stats = get_tenant_dashboard_stats(tenant)
        self.assertEqual(stats['tokens']['balance'], 5000)
        self.assertEqual(stats['storage']['max_mb'], 200)

        # Test API endpoint
        res = self.client.get(reverse('dashboard_stats_api'), HTTP_X_API_KEY=api_key.key)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
