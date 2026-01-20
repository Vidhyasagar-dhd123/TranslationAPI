
from django.urls import path, include
from .views import translate_text

urlpatterns = [
    path('translate/',translate_text, name='translate'),
]