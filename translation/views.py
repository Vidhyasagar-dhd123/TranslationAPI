"""
Translation and PDF processing API views.
"""
import json
from django.views.decorators.csrf import csrf_exempt
from users.auth.authentication import tenant_auth_required
from core.utils.response import api_response, api_error
from translation.models import Document
from translation.services.pdf_service import PDFService, StorageLimitExceededException
from translation.services.translation_service import TranslationService, InsufficientTokensException


pdf_service = PDFService()
translation_service = TranslationService()


@csrf_exempt
@tenant_auth_required
def translate_raw_text(request):
    """
    Translates raw text input.
    POST /api/translate/raw/
    Body: {"text": "...", "source_lang": "eng_Latn", "target_lang": "hin_Deva"}
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    try:
        data = json.loads(request.body) if request.body else request.POST
        text = data.get('text', '')
        source_lang = data.get('source_lang', 'eng_Latn')
        target_lang = data.get('target_lang', 'hin_Deva')

        if not text:
            return api_error(message="Field 'text' is required.", error_code="VALIDATION_ERROR", status=400)

        result = translation_service.translate_raw(
            tenant=request.tenant,
            text=text,
            source_lang=source_lang,
            target_lang=target_lang
        )
        return api_response(data=result, message="Text translated successfully.")

    except InsufficientTokensException as e:
        return api_error(message=str(e), error_code="INSUFFICIENT_TOKENS", status=402)
    except Exception as e:
        return api_error(message=str(e), error_code="TRANSLATION_FAILED", status=400)


@csrf_exempt
@tenant_auth_required
def upload_pdf(request):
    """
    Uploads a PDF file with auto or manual extraction mode.
    POST /api/pdf/upload/
    Form data: file (PDF), mode ('auto' or 'manual'), title (optional)
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    if 'file' not in request.FILES:
        return api_error(message="PDF 'file' is required in form-data.", error_code="MISSING_FILE", status=400)

    uploaded_file = request.FILES['file']
    if not uploaded_file.name.lower().endswith('.pdf'):
        return api_error(message="Uploaded file must be a PDF document.", error_code="INVALID_FILE_TYPE", status=400)

    mode = request.POST.get('mode', 'auto').lower()
    if mode not in ['auto', 'manual']:
        mode = 'auto'

    title = request.POST.get('title', uploaded_file.name)

    try:
        doc = pdf_service.upload_pdf(
            tenant=request.tenant,
            file=uploaded_file,
            title=title,
            mode=mode
        )
        return api_response(
            data={
                "document_id": doc.id,
                "title": doc.title,
                "file_name": doc.file_name,
                "file_size_mb": doc.file_size_mb,
                "total_pages": doc.total_pages,
                "extracted_pages_count": doc.extracted_pages_count,
                "extraction_mode": doc.extraction_mode,
                "status": doc.status,
                "tenant_storage_used_mb": request.tenant.storage_used_mb,
                "tenant_max_storage_mb": request.tenant.max_storage_mb,
            },
            message=f"PDF uploaded successfully in {mode} mode.",
            status=201
        )
    except StorageLimitExceededException as e:
        return api_error(message=str(e), error_code="STORAGE_QUOTA_EXCEEDED", status=413)
    except Exception as e:
        return api_error(message=str(e), error_code="UPLOAD_FAILED", status=400)


@csrf_exempt
@tenant_auth_required
def list_documents(request):
    """
    Lists all uploaded documents for the tenant.
    GET /api/pdf/documents/
    """
    if request.method == 'DELETE':
        deleted_count = pdf_service.delete_all_documents(request.tenant)
        return api_response(
            data={"deleted_count": deleted_count},
            message="All documents and related pages and translations deleted."
        )
    if request.method != 'GET':
        return api_error(message="Method not allowed. Use GET or DELETE.", error_code="METHOD_NOT_ALLOWED", status=405)

    docs = Document.objects.filter(tenant=request.tenant).order_by('-created_at')
    data = [
        {
            "id": d.id,
            "title": d.title,
            "file_name": d.file_name,
            "file_size_mb": d.file_size_mb,
            "total_pages": d.total_pages,
            "extracted_pages_count": d.extracted_pages_count,
            "extraction_mode": d.extraction_mode,
            "status": d.status,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]
    return api_response(data=data, message="Documents retrieved.")


@csrf_exempt
@tenant_auth_required
def delete_document_view(request, doc_id: int):
    """Deletes one tenant-owned PDF and all of its related data."""
    if request.method != 'DELETE':
        return api_error(message="Method not allowed. Use DELETE.", error_code="METHOD_NOT_ALLOWED", status=405)

    try:
        doc = Document.objects.get(id=doc_id, tenant=request.tenant)
    except Document.DoesNotExist:
        return api_error(message="Document not found.", error_code="NOT_FOUND", status=404)

    pdf_service.delete_document(doc)
    return api_response(data={"document_id": doc_id}, message="Document, pages, and translations deleted.")


@csrf_exempt
@tenant_auth_required
def extract_page_view(request, doc_id: int):
    """
    Manual mode: Extracts a single page or next page for a document.
    POST /api/pdf/<doc_id>/extract-page/
    Body: {"page_number": 2} or {"mode": "next"}
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    try:
        doc = Document.objects.get(id=doc_id, tenant=request.tenant)
    except Document.DoesNotExist:
        return api_error(message="Document not found.", error_code="NOT_FOUND", status=404)

    try:
        data = json.loads(request.body) if request.body else request.POST
        page_num = data.get('page_number')

        if page_num is not None and str(page_num).isdigit():
            page_obj = pdf_service.extract_single_page(doc, int(page_num))
        else:
            page_obj = pdf_service.extract_next_page(doc)
            if page_obj is None:
                return api_response(
                    data={"all_extracted": True, "total_pages": doc.total_pages},
                    message="All pages have already been extracted."
                )

        return api_response(
            data={
                "document_id": doc.id,
                "page_number": page_obj.page_number,
                "raw_text": page_obj.raw_text,
                "ocr_text": page_obj.ocr_text,
                "combined_text": page_obj.combined_text,
                "has_images": page_obj.has_images,
                "image_count": page_obj.image_count,
                "images": [
                    {
                        "image_number": img.image_number,
                        "image_name": img.image_name,
                        "image_url": img.image_url,
                        "width": img.width,
                        "height": img.height,
                        "file_size_bytes": img.file_size_bytes,
                        "ocr_text": img.ocr_text,
                    }
                    for img in page_obj.images.all()
                ],
                "word_count": page_obj.word_count,
                "total_extracted": doc.extracted_pages_count,
                "total_pages": doc.total_pages,
            },
            message=f"Page {page_obj.page_number} extracted successfully."
        )
    except Exception as e:
        return api_error(message=str(e), error_code="EXTRACTION_FAILED", status=400)


@csrf_exempt
@tenant_auth_required
def get_pages_view(request, doc_id: int):
    """
    Retrieves extracted pages for a document: single page, range, or all.
    GET /api/pdf/<doc_id>/pages/?page_number=1 OR ?start=1&end=5 OR ?all=true
    """
    try:
        doc = Document.objects.get(id=doc_id, tenant=request.tenant)
    except Document.DoesNotExist:
        return api_error(message="Document not found.", error_code="NOT_FOUND", status=404)

    page_num = request.GET.get('page_number') or request.GET.get('page')
    start_page = request.GET.get('start')
    end_page = request.GET.get('end')
    all_pages = request.GET.get('all', 'false').lower() in ['true', '1', 'yes']

    p_num = int(page_num) if (page_num and page_num.isdigit()) else None
    s_page = int(start_page) if (start_page and start_page.isdigit()) else None
    e_page = int(end_page) if (end_page and end_page.isdigit()) else None

    pages = pdf_service.get_pages(doc, page_number=p_num, start_page=s_page, end_page=e_page, all_pages=all_pages)
    data = [
        {
            "page_number": p.page_number,
            "raw_text": p.raw_text,
            "ocr_text": p.ocr_text,
            "combined_text": p.combined_text,
            "has_images": p.has_images,
            "image_count": p.image_count,
            "images": [
                {
                    "image_number": img.image_number,
                    "image_name": img.image_name,
                    "image_url": img.image_url,
                    "width": img.width,
                    "height": img.height,
                    "file_size_bytes": img.file_size_bytes,
                    "ocr_text": img.ocr_text,
                }
                for img in p.images.all()
            ],
            "word_count": p.word_count,
            "extracted_at": p.extracted_at.isoformat(),
        }
        for p in pages
    ]
    return api_response(data={"document_id": doc.id, "total_extracted": len(data), "pages": data}, message="Pages retrieved.")


@csrf_exempt
@tenant_auth_required
def get_page_images_view(request, doc_id: int):
    """
    Retrieves extracted images for a document or specific page.
    GET /api/pdf/<doc_id>/images/?page=1
    """
    try:
        doc = Document.objects.get(id=doc_id, tenant=request.tenant)
    except Document.DoesNotExist:
        return api_error(message="Document not found.", error_code="NOT_FOUND", status=404)

    page_num = request.GET.get('page') or request.GET.get('page_number')
    from translation.models import PageImage
    qs = PageImage.objects.filter(extracted_page__document=doc).select_related('extracted_page')

    if page_num and str(page_num).isdigit():
        qs = qs.filter(extracted_page__page_number=int(page_num))

    data = [
        {
            "page_number": img.extracted_page.page_number,
            "image_number": img.image_number,
            "image_name": img.image_name,
            "image_url": img.image_url,
            "width": img.width,
            "height": img.height,
            "file_size_bytes": img.file_size_bytes,
            "ocr_text": img.ocr_text,
        }
        for img in qs
    ]
    return api_response(data={"document_id": doc.id, "count": len(data), "images": data}, message="Images retrieved.")



@csrf_exempt
@tenant_auth_required
def translate_page_view(request, doc_id: int):
    """
    Translates a single extracted page of a PDF document.
    POST /api/pdf/<doc_id>/translate-page/
    Body: {"page_number": 1, "target_lang": "hin_Deva", "source_lang": "eng_Latn"}
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    try:
        doc = Document.objects.get(id=doc_id, tenant=request.tenant)
    except Document.DoesNotExist:
        return api_error(message="Document not found.", error_code="NOT_FOUND", status=404)

    try:
        data = json.loads(request.body) if request.body else request.POST
        page_number = int(data.get('page_number', 1))
        target_lang = data.get('target_lang', 'hin_Deva')
        source_lang = data.get('source_lang', 'eng_Latn')

        res = translation_service.translate_pdf_page(
            tenant=request.tenant,
            document=doc,
            page_number=page_number,
            target_lang=target_lang,
            source_lang=source_lang
        )
        return api_response(data=res, message="Page translation completed.")

    except InsufficientTokensException as e:
        return api_error(message=str(e), error_code="INSUFFICIENT_TOKENS", status=402)
    except Exception as e:
        return api_error(message=str(e), error_code="TRANSLATION_FAILED", status=400)


@csrf_exempt
@tenant_auth_required
def translate_all_pages_view(request, doc_id: int):
    """
    Translates all extracted pages of a document.
    POST /api/pdf/<doc_id>/translate-all/
    Body: {"target_lang": "hin_Deva", "source_lang": "eng_Latn"}
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    try:
        doc = Document.objects.get(id=doc_id, tenant=request.tenant)
    except Document.DoesNotExist:
        return api_error(message="Document not found.", error_code="NOT_FOUND", status=404)

    try:
        data = json.loads(request.body) if request.body else request.POST
        target_lang = data.get('target_lang', 'hin_Deva')
        source_lang = data.get('source_lang', 'eng_Latn')

        res = translation_service.translate_pdf_all(
            tenant=request.tenant,
            document=doc,
            target_lang=target_lang,
            source_lang=source_lang
        )
        return api_response(data=res, message="All extracted pages translated successfully.")

    except InsufficientTokensException as e:
        return api_error(message=str(e), error_code="INSUFFICIENT_TOKENS", status=402)
    except Exception as e:
        return api_error(message=str(e), error_code="TRANSLATION_FAILED", status=400)


@csrf_exempt
@tenant_auth_required
def translate_range_view(request, doc_id: int):
    """
    Translates a range of pages in a document.
    POST /api/pdf/<doc_id>/translate-range/
    Body: {"start_page": 1, "end_page": 3, "target_lang": "hin_Deva", "source_lang": "eng_Latn"}
    """
    if request.method != 'POST':
        return api_error(message="Method not allowed. Use POST.", error_code="METHOD_NOT_ALLOWED", status=405)

    try:
        doc = Document.objects.get(id=doc_id, tenant=request.tenant)
    except Document.DoesNotExist:
        return api_error(message="Document not found.", error_code="NOT_FOUND", status=404)

    try:
        data = json.loads(request.body) if request.body else request.POST
        start_page = int(data.get('start_page', 1))
        end_page = int(data.get('end_page', 1))
        target_lang = data.get('target_lang', 'hin_Deva')
        source_lang = data.get('source_lang', 'eng_Latn')

        res = translation_service.translate_pdf_range(
            tenant=request.tenant,
            document=doc,
            start_page=start_page,
            end_page=end_page,
            target_lang=target_lang,
            source_lang=source_lang
        )
        return api_response(data=res, message="Page range translated successfully.")

    except InsufficientTokensException as e:
        return api_error(message=str(e), error_code="INSUFFICIENT_TOKENS", status=402)
    except Exception as e:
        return api_error(message=str(e), error_code="TRANSLATION_FAILED", status=400)


@csrf_exempt
@tenant_auth_required
def get_translations_view(request, doc_id: int):
    """
    Retrieves stored translations for a document in a target language.
    GET /api/pdf/<doc_id>/translations/?lang=hin_Deva&page=1 OR ?lang=hin_Deva&start=1&end=5 OR ?lang=hin_Deva&all=true
    """
    try:
        doc = Document.objects.get(id=doc_id, tenant=request.tenant)
    except Document.DoesNotExist:
        return api_error(message="Document not found.", error_code="NOT_FOUND", status=404)

    target_lang = request.GET.get('lang') or request.GET.get('target_lang')
    if not target_lang:
        return api_error(message="Query parameter 'lang' or 'target_lang' is required.", error_code="MISSING_LANG", status=400)

    page_num = request.GET.get('page') or request.GET.get('page_number')
    start_page = request.GET.get('start')
    end_page = request.GET.get('end')
    all_pages = request.GET.get('all', 'false').lower() in ['true', '1', 'yes']

    p_num = int(page_num) if (page_num and page_num.isdigit()) else None
    s_page = int(start_page) if (start_page and start_page.isdigit()) else None
    e_page = int(end_page) if (end_page and end_page.isdigit()) else None

    translations = translation_service.get_translations(
        document=doc,
        target_lang=target_lang,
        page_number=p_num,
        start_page=s_page,
        end_page=e_page,
        all_pages=all_pages
    )
    return api_response(
        data={"document_id": doc.id, "target_lang": target_lang, "count": len(translations), "translations": translations},
        message="Translations retrieved successfully."
    )