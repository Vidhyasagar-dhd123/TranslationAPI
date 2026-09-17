"""
Dashboard and Usage Analytics module.
Exposes JSON stats API and renders interactive HTML Dashboard & Widget views.
"""
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from users.models import Tenant, ApiKey, PaymentTransaction
from translation.models import Document, ExtractedPage, TranslatedPage, TokenUsageLog
from users.auth.authentication import tenant_auth_required, get_api_key_from_request
from core.utils.response import api_response, api_error


def get_tenant_dashboard_stats(tenant: Tenant) -> dict:
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)

    # Token stats
    tokens_today = tenant.usage_logs.filter(timestamp__gte=today_start).aggregate(total=Sum('token_count'))['total'] or 0
    tokens_7d = tenant.usage_logs.filter(timestamp__gte=seven_days_ago).aggregate(total=Sum('token_count'))['total'] or 0

    # Documents & Pages
    docs_qs = tenant.documents.all()
    total_docs = docs_qs.count()
    total_pages_extracted = ExtractedPage.objects.filter(document__tenant=tenant).count()
    total_pages_translated = TranslatedPage.objects.filter(extracted_page__document__tenant=tenant).count()

    # Language breakdown
    lang_stats = list(
        TranslatedPage.objects.filter(extracted_page__document__tenant=tenant)
        .values('target_language')
        .annotate(count=Count('id'), total_tokens=Sum('tokens_used'))
        .order_by('-count')
    )

    # Recent activity
    recent_logs = [
        {
            "request_type": log.request_type,
            "tokens": log.token_count,
            "source_lang": log.source_lang,
            "target_lang": log.target_lang,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "details": log.details,
        }
        for log in tenant.usage_logs.all()[:15]
    ]

    # Payment transactions
    recent_payments = [
        {
            "transaction_id": txn.transaction_id,
            "amount": float(txn.amount),
            "currency": txn.currency,
            "tokens_granted": txn.tokens_granted,
            "status": txn.status,
            "created_at": txn.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for txn in tenant.payments.all()[:5]
    ]

    return {
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "email": tenant.email,
        },
        "tokens": {
            "balance": tenant.token_balance,
            "total_used": tenant.total_tokens_used,
            "used_today": tokens_today,
            "used_7_days": tokens_7d,
        },
        "storage": {
            "used_bytes": tenant.storage_used_bytes,
            "used_mb": tenant.storage_used_mb,
            "max_mb": tenant.max_storage_mb,
            "percentage": tenant.storage_percentage,
            "total_documents": total_docs,
        },
        "activity": {
            "extracted_pages_count": total_pages_extracted,
            "translated_pages_count": total_pages_translated,
            "language_distribution": lang_stats,
            "recent_logs": recent_logs,
            "recent_payments": recent_payments,
        }
    }


@tenant_auth_required
def dashboard_stats_api(request):
    """
    JSON API for tenant dashboard analytics.
    GET /api/dashboard/stats/
    """
    stats = get_tenant_dashboard_stats(request.tenant)
    return api_response(data=stats, message="Dashboard stats retrieved successfully.")


def dashboard_view(request):
    """
    Full HTML Dashboard page.
    """
    api_key_str = get_api_key_from_request(request)
    tenant = None
    stats = None
    all_tenants = Tenant.objects.all().order_by('-created_at')

    if api_key_str:
        api_key_obj = ApiKey.objects.filter(key=api_key_str, is_active=True).first()
        if api_key_obj:
            tenant = api_key_obj.tenant
            stats = get_tenant_dashboard_stats(tenant)
    elif all_tenants.exists():
        tenant = all_tenants.first()
        api_key_obj = tenant.api_keys.filter(is_active=True).first()
        api_key_str = api_key_obj.key if api_key_obj else ""
        stats = get_tenant_dashboard_stats(tenant)

    context = {
        "tenant": tenant,
        "api_key": api_key_str,
        "stats": stats,
        "all_tenants": all_tenants,
    }
    return render(request, "dashboard.html", context)


def dashboard_widget_view(request):
    """
    Compact embeddable HTML widget.
    """
    api_key_str = get_api_key_from_request(request)
    tenant = None
    stats = None

    if api_key_str:
        api_key_obj = ApiKey.objects.filter(key=api_key_str, is_active=True).first()
        if api_key_obj:
            tenant = api_key_obj.tenant
            stats = get_tenant_dashboard_stats(tenant)
    else:
        tenant = Tenant.objects.first()
        if tenant:
            api_key_obj = tenant.api_keys.filter(is_active=True).first()
            api_key_str = api_key_obj.key if api_key_obj else ""
            stats = get_tenant_dashboard_stats(tenant)

    context = {
        "tenant": tenant,
        "api_key": api_key_str,
        "stats": stats,
    }
    return render(request, "dashboard_widget.html", context)
