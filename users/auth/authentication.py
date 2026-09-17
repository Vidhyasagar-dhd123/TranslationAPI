"""
API Key Authentication decorator and helper for Tenants.
"""
from functools import wraps
from django.http import JsonResponse
from users.models import ApiKey
from core.utils.response import api_error


def get_api_key_from_request(request) -> str:
    """
    Extracts API key from headers or query parameters.
    Supports:
    - Header 'X-API-KEY: sk_live_...'
    - Header 'Authorization: Bearer sk_live_...'
    - Query param '?api_key=sk_live_...'
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:].strip()
    
    x_api_key = request.META.get('HTTP_X_API_KEY', '')
    if x_api_key:
        return x_api_key.strip()

    query_key = request.GET.get('api_key', '')
    if query_key:
        return query_key.strip()

    return ''


def tenant_auth_required(view_func):
    """
    Decorator to ensure request is authenticated with a valid Tenant API Key.
    Attaches `request.tenant` and `request.api_key` to the request object.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        key_str = get_api_key_from_request(request)
        if not key_str:
            return api_error(
                message="Authentication required. Please provide a valid API Key in the 'X-API-KEY' header or 'Authorization: Bearer <key>' header.",
                error_code="UNAUTHORIZED",
                status=401
            )

        try:
            api_key_obj = ApiKey.objects.select_related('tenant').get(key=key_str, is_active=True)
            if not api_key_obj.tenant.is_active:
                return api_error(
                    message="Tenant account is disabled. Please contact support.",
                    error_code="TENANT_DISABLED",
                    status=403
                )
            
            request.tenant = api_key_obj.tenant
            request.api_key = api_key_obj
            return view_func(request, *args, **kwargs)

        except ApiKey.DoesNotExist:
            return api_error(
                message="Invalid or revoked API Key.",
                error_code="INVALID_API_KEY",
                status=401
            )

    return _wrapped_view
