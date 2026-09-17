"""
URL configuration for users and billing.
"""
from django.urls import path
from users.views import (
    register_tenant,
    login_tenant,
    generate_api_key,
    get_tenant_profile,
    payment_checkout,
    payment_confirm,
)
from users.dashboard import (
    dashboard_stats_api,
    dashboard_view,
    dashboard_widget_view,
)

urlpatterns = [
    path('tenant/register/', register_tenant, name='tenant_register'),
    path('tenant/login/', login_tenant, name='tenant_login'),
    path('tenant/api-keys/', generate_api_key, name='generate_api_key'),
    path('tenant/me/', get_tenant_profile, name='tenant_profile'),
    path('payment/checkout/', payment_checkout, name='payment_checkout'),
    path('payment/confirm/', payment_confirm, name='payment_confirm'),
    path('dashboard/stats/', dashboard_stats_api, name='dashboard_stats_api'),
]
