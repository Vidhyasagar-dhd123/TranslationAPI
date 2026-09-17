"""translationapi URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users.dashboard import dashboard_view, dashboard_widget_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # Dashboard and Widget Views
    path('', dashboard_view, name='root_dashboard'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('dashboard/widget/', dashboard_widget_view, name='dashboard_widget'),

    # API endpoints
    path('api/', include('users.urls')),
    path('api/', include('translation.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
