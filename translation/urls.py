"""
URL routing for translation and PDF operations.
"""
from django.urls import path
from translation.views import (
    translate_raw_text,
    upload_pdf,
    list_documents,
    delete_document_view,
    extract_page_view,
    get_pages_view,
    get_page_images_view,
    translate_page_view,
    translate_all_pages_view,
    translate_range_view,
    get_translations_view,
)

urlpatterns = [
    # Raw text translation
    path('translate/raw/', translate_raw_text, name='translate_raw'),
    path('translate/', translate_raw_text, name='translate_legacy'), # legacy alias

    # PDF Document management & extraction
    path('pdf/upload/', upload_pdf, name='upload_pdf'),
    path('pdf/documents/', list_documents, name='list_documents'),
    path('pdf/<int:doc_id>/', delete_document_view, name='delete_document'),
    path('pdf/<int:doc_id>/extract-page/', extract_page_view, name='extract_page'),
    path('pdf/<int:doc_id>/pages/', get_pages_view, name='get_pages'),
    path('pdf/<int:doc_id>/images/', get_page_images_view, name='get_page_images'),

    # PDF Translation
    path('pdf/<int:doc_id>/translate-page/', translate_page_view, name='translate_page'),
    path('pdf/<int:doc_id>/translate-all/', translate_all_pages_view, name='translate_all_pages'),
    path('pdf/<int:doc_id>/translate-range/', translate_range_view, name='translate_range'),
    path('pdf/<int:doc_id>/translations/', get_translations_view, name='get_translations'),
]