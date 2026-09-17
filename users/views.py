"""
Tenant registration, API key management, and payment views.
"""
import json
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from users.models import Tenant, ApiKey, PaymentTransaction
from users.auth.authentication import tenant_auth_required
from core.adapters.payment import DummyPaymentAdapter, DEFAULT_PAYMENT_TOKENS
from core.utils.response import api_response, api_error


@csrf_exempt
def register_tenant(request):
    """
    Registers a new tenant and returns an API key.
    POST /api/tenant/register/
    Body: {"name": "Tenant Name", "email": "tenant@example.com"}
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    try:
        data = json.loads(request.body) if request.body else request.POST
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not name or not email:
            return api_error(message="Fields 'name' and 'email' are required.", error_code="VALIDATION_ERROR", status=400)

        tenant, created = Tenant.objects.get_or_create(
            email=email,
            defaults={'name': name, 'token_balance': 0}
        )

        if created and password:
            tenant.set_password(password)
            tenant.save(update_fields=['password', 'updated_at'])

        if not created:
            # If tenant already exists, create and return an active API key
            api_key = tenant.api_keys.filter(is_active=True).first()
            if not api_key:
                api_key = ApiKey.objects.create(tenant=tenant, name="Primary Key")
        else:
            api_key = ApiKey.objects.create(tenant=tenant, name="Primary Key")

        return api_response(
            data={
                "tenant_id": tenant.id,
                "name": tenant.name,
                "email": tenant.email,
                "token_balance": tenant.token_balance,
                "storage_used_mb": tenant.storage_used_mb,
                "max_storage_mb": tenant.max_storage_mb,
                "api_key": api_key.key,
                "is_new": created,
            },
            message="Tenant registered successfully." if created else "Existing tenant retrieved."
        )

    except IntegrityError:
        return api_error(message="Tenant with this email already exists.", error_code="DUPLICATE_EMAIL", status=400)
    except Exception as e:
        return api_error(message=str(e), error_code="REGISTRATION_FAILED", status=400)


@csrf_exempt
def login_tenant(request):
    """
    Authenticates a tenant with email and password and returns an API key.
    POST /api/tenant/login/
    Body: {"email": "tenant@example.com", "password": "..."}
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    try:
        data = json.loads(request.body) if request.body else request.POST
        email = data.get('email', '').strip()
        password = data.get('password', '')
        tenant = Tenant.objects.filter(email=email).first()

        if not tenant or not tenant.check_password(password):
            return api_error(message="Invalid email or password.", error_code="INVALID_CREDENTIALS", status=401)
        if not tenant.is_active:
            return api_error(message="Tenant account is disabled. Please contact support.", error_code="TENANT_DISABLED", status=403)

        api_key = tenant.api_keys.filter(is_active=True).first()
        if not api_key:
            api_key = ApiKey.objects.create(tenant=tenant, name="Primary Key")

        return api_response(
            data={"tenant_id": tenant.id, "name": tenant.name, "email": tenant.email, "api_key": api_key.key},
            message="Login successful."
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return api_error(message="Request body must be valid JSON.", error_code="VALIDATION_ERROR", status=400)


@csrf_exempt
@tenant_auth_required
def generate_api_key(request):
    """
    Generates a new API key for the authenticated tenant.
    POST /api/tenant/api-keys/
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    try:
        data = json.loads(request.body) if request.body else request.POST
        key_name = data.get('name', f"API Key {request.tenant.api_keys.count() + 1}")
        api_key = ApiKey.objects.create(tenant=request.tenant, name=key_name)

        return api_response(
            data={
                "key_id": api_key.id,
                "name": api_key.name,
                "api_key": api_key.key,
                "created_at": api_key.created_at.isoformat(),
            },
            message="New API key generated successfully."
        )
    except Exception as e:
        return api_error(message=str(e), error_code="KEY_GENERATION_FAILED", status=400)


@csrf_exempt
@tenant_auth_required
def get_tenant_profile(request):
    """
    Returns current tenant profile, token balance, and storage quota stats.
    GET /api/tenant/me/
    """
    tenant = request.tenant
    return api_response(
        data={
            "tenant_id": tenant.id,
            "name": tenant.name,
            "email": tenant.email,
            "token_balance": tenant.token_balance,
            "total_tokens_used": tenant.total_tokens_used,
            "storage_used_bytes": tenant.storage_used_bytes,
            "storage_used_mb": tenant.storage_used_mb,
            "max_storage_mb": tenant.max_storage_mb,
            "storage_percentage": tenant.storage_percentage,
            "is_active": tenant.is_active,
            "active_keys_count": tenant.api_keys.filter(is_active=True).count(),
        },
        message="Tenant profile fetched successfully."
    )


@csrf_exempt
@tenant_auth_required
def payment_checkout(request):
    """
    Creates a payment checkout order using the payment adapter.
    POST /api/payment/checkout/
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    adapter = DummyPaymentAdapter()
    order = adapter.create_order(tenant_id=request.tenant.id)
    return api_response(data=order, message="Payment checkout order created.")


@csrf_exempt
@tenant_auth_required
def payment_confirm(request):
    """
    Confirms payment, awards 5M tokens, and creates a PaymentTransaction record.
    POST /api/payment/confirm/
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    try:
        data = json.loads(request.body) if request.body else request.POST
        order_id = data.get('order_id', '')
        transaction_id = data.get('transaction_id', '')

        adapter = DummyPaymentAdapter()
        result = adapter.verify_and_credit(request.tenant, transaction_id=transaction_id, order_id=order_id)

        PaymentTransaction.objects.create(
            tenant=request.tenant,
            transaction_id=result["transaction_id"],
            order_id=result.get("order_id"),
            amount=result["amount"],
            currency=result["currency"],
            tokens_granted=result["tokens_credited"],
            status="completed"
        )

        return api_response(data=result, message=result["message"])

    except Exception as e:
        return api_error(message=str(e), error_code="PAYMENT_CONFIRMATION_FAILED", status=400)
