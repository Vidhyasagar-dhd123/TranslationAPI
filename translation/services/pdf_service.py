"""
PDF Service handling PDF uploads, 200MB tenant storage limit enforcement,
Auto vs Manual extraction modes, image extraction + Tesseract OCR, and page retrieval.
"""
import os
import io
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import pypdf
from django.conf import settings
from django.db import transaction
from core.adapters.storage import LocalStorageAdapter
from core.adapters.ocr import OCRAdapter
from core.utils.token_counter import count_tokens
from translation.models import Document, ExtractedPage
from users.models import Tenant

logger = logging.getLogger(__name__)

MAX_STORAGE_BYTES = 200 * 1024 * 1024  # 200 MB


class StorageLimitExceededException(Exception):
    pass


class PDFService:
    def __init__(self, storage_adapter: Optional[LocalStorageAdapter] = None):
        self.storage = storage_adapter or LocalStorageAdapter()

    def upload_pdf(self, tenant: Tenant, file, title: str = None, mode: str = 'auto') -> Document:
        """
        Uploads PDF document, validates 200MB tenant limit, stores file,
        and runs extraction according to mode (auto vs manual).
        """
        file_size = file.size
        # Check tenant storage limit (200MB)
        if tenant.storage_used_bytes + file_size > MAX_STORAGE_BYTES:
            remaining_mb = max(0.0, round((MAX_STORAGE_BYTES - tenant.storage_used_bytes) / (1024 * 1024), 2))
            raise StorageLimitExceededException(
                f"Storage limit of 200MB exceeded. File size is {round(file_size / (1024*1024), 2)}MB, but only {remaining_mb}MB remaining."
            )

        saved_info = self.storage.save(tenant.id, file)
        abs_path = saved_info['file_path']
        rel_path = saved_info['relative_path']
        doc_title = title or file.name

        try:
            reader = pypdf.PdfReader(abs_path)
            total_pages = len(reader.pages)
        except Exception as e:
            self.storage.delete(rel_path)
            raise ValueError(f"Invalid PDF file: {str(e)}")

        with transaction.atomic():
            # Update tenant storage usage
            tenant.storage_used_bytes += file_size
            tenant.save(update_fields=['storage_used_bytes', 'updated_at'])

            document = Document.objects.create(
                tenant=tenant,
                title=doc_title,
                file_name=saved_info['file_name'],
                file_path=rel_path,
                file_size_bytes=file_size,
                total_pages=total_pages,
                extraction_mode=mode,
                status='processing' if mode == 'auto' else 'uploaded'
            )

        if mode == 'auto':
            self._extract_all_pages(document, reader)

        return document

    def delete_document(self, document: Document) -> int:
        """Deletes a document, its extracted files, and all related records."""
        file_size = document.file_size_bytes
        document_dir = Path(getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))) / f"tenant_{document.tenant_id}" / "extracted_images" / f"doc_{document.id}"
        self.storage.delete(document.file_path)
        if document_dir.exists():
            import shutil
            shutil.rmtree(document_dir, ignore_errors=True)

        tenant = document.tenant
        document.delete()
        tenant.storage_used_bytes = max(0, tenant.storage_used_bytes - file_size)
        tenant.save(update_fields=['storage_used_bytes', 'updated_at'])
        return file_size

    def delete_all_documents(self, tenant: Tenant) -> int:
        """Deletes every document belonging to a tenant and returns the count."""
        documents = list(Document.objects.filter(tenant=tenant))
        for document in documents:
            self.delete_document(document)
        return len(documents)

    def _save_page_images(self, document: Document, extracted_page: ExtractedPage, processed_images: List[dict]):
        """
        Saves extracted images to disk under media storage and creates PageImage database records.
        """
        if not processed_images:
            return

        media_root = Path(getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media')))
        tenant_id = document.tenant.id
        images_dir = media_root / f"tenant_{tenant_id}" / "extracted_images" / f"doc_{document.id}"
        images_dir.mkdir(parents=True, exist_ok=True)

        media_url_base = getattr(settings, 'MEDIA_URL', '/media/')
        if not media_url_base.endswith('/'):
            media_url_base += '/'

        for img_info in processed_images:
            idx = img_info['image_index']
            ext = img_info.get('format', 'png').lower()
            if ext == 'jpeg':
                ext = 'jpg'

            img_filename = f"page_{extracted_page.page_number}_img_{idx}.{ext}"
            img_file_path = images_dir / img_filename

            try:
                with open(img_file_path, 'wb') as f:
                    f.write(img_info['bytes'])

                rel_path = f"tenant_{tenant_id}/extracted_images/doc_{document.id}/{img_filename}"
                img_url = f"{media_url_base}{rel_path}"

                from translation.models import PageImage
                PageImage.objects.update_or_create(
                    extracted_page=extracted_page,
                    image_number=idx,
                    defaults={
                        "image_name": img_filename,
                        "image_path": rel_path,
                        "image_url": img_url,
                        "width": img_info.get('width', 0),
                        "height": img_info.get('height', 0),
                        "file_size_bytes": img_info.get('size_bytes', len(img_info['bytes'])),
                        "ocr_text": img_info.get('ocr_text', ''),
                    }
                )
            except Exception as e:
                logger.error(f"Failed to save extracted image {img_filename}: {e}")

    def _extract_page_content(self, page: pypdf.PageObject, page_number: int) -> Dict[str, Any]:
        """
        Extracts direct text and images from a single PDF page and runs OCR on images.
        """
        raw_text = (page.extract_text() or "").strip()

        # Extract embedded images
        image_bytes_list = []
        try:
            if hasattr(page, 'images'):
                for img_obj in page.images:
                    image_bytes_list.append(img_obj.data)
        except Exception as img_err:
            logger.warning(f"Error inspecting page {page_number} images: {img_err}")

        processed_images = OCRAdapter.process_images(image_bytes_list)
        image_count = len(processed_images)
        has_images = image_count > 0

        ocr_parts = [
            f"[Image {item['image_index']} OCR Text]:\n{item['ocr_text']}"
            for item in processed_images if item['ocr_text'] and not item['ocr_text'].startswith('(')
        ]
        ocr_text = "\n\n".join(ocr_parts).strip()

        # Build combined text: Raw text + OCR section at the end if images were found
        combined_parts = []
        if raw_text:
            combined_parts.append(raw_text)

        if ocr_text:
            combined_parts.append(f"\nExtracted Text (From Images via OCR): \n{ocr_text}")

        combined_text = "\n\n".join(combined_parts).strip()
        word_count = count_tokens(combined_text)

        return {
            "page_number": page_number,
            "raw_text": raw_text,
            "ocr_text": ocr_text,
            "combined_text": combined_text,
            "has_images": has_images,
            "image_count": image_count,
            "processed_images": processed_images,
            "word_count": word_count,
        }

    def _extract_all_pages(self, document: Document, reader: Optional[pypdf.PdfReader] = None):
        """
        Auto mode: Extracts all pages and writes them to ExtractedPage table.
        """
        abs_path = self.storage.get_absolute_path(document.file_path)
        if reader is None:
            reader = pypdf.PdfReader(abs_path)

        extracted_count = 0
        for idx, page in enumerate(reader.pages, start=1):
            page_data = self._extract_page_content(page, idx)
            extracted_page, _ = ExtractedPage.objects.update_or_create(
                document=document,
                page_number=idx,
                defaults={
                    "raw_text": page_data["raw_text"],
                    "ocr_text": page_data["ocr_text"],
                    "combined_text": page_data["combined_text"],
                    "has_images": page_data["has_images"],
                    "image_count": page_data["image_count"],
                    "word_count": page_data["word_count"],
                }
            )
            if page_data["has_images"]:
                self._save_page_images(document, extracted_page, page_data["processed_images"])
            extracted_count += 1

        document.extracted_pages_count = extracted_count
        document.status = 'extracted'
        document.save(update_fields=['extracted_pages_count', 'status', 'updated_at'])

    def extract_single_page(self, document: Document, page_number: int) -> ExtractedPage:
        """
        Manual mode: Extracts a specific page on demand.
        """
        if page_number < 1 or page_number > document.total_pages:
            raise ValueError(f"Page number {page_number} out of range (1 to {document.total_pages}).")

        abs_path = self.storage.get_absolute_path(document.file_path)
        reader = pypdf.PdfReader(abs_path)
        page = reader.pages[page_number - 1]

        page_data = self._extract_page_content(page, page_number)

        extracted_page, _ = ExtractedPage.objects.update_or_create(
            document=document,
            page_number=page_number,
            defaults={
                "raw_text": page_data["raw_text"],
                "ocr_text": page_data["ocr_text"],
                "combined_text": page_data["combined_text"],
                "has_images": page_data["has_images"],
                "image_count": page_data["image_count"],
                "word_count": page_data["word_count"],
            }
        )

        if page_data["has_images"]:
            self._save_page_images(document, extracted_page, page_data["processed_images"])

        # Update count on document
        document.extracted_pages_count = document.pages.count()
        if document.extracted_pages_count == document.total_pages:
            document.status = 'extracted'
        else:
            document.status = 'processing'
        document.save(update_fields=['extracted_pages_count', 'status', 'updated_at'])

        return extracted_page


    def extract_next_page(self, document: Document) -> Optional[ExtractedPage]:
        """
        Manual mode: Finds the next unextracted page and extracts it.
        """
        extracted_nums = set(document.pages.values_list('page_number', flat=True))
        for p in range(1, document.total_pages + 1):
            if p not in extracted_nums:
                return self.extract_single_page(document, p)
        return None

    def get_pages(self, document: Document, page_number: Optional[int] = None,
                  start_page: Optional[int] = None, end_page: Optional[int] = None,
                  all_pages: bool = False) -> List[ExtractedPage]:
        """
        Retrieves extracted pages by single page number, page range, or all extracted pages.
        """
        qs = document.pages.all().order_by('page_number')
        if page_number is not None:
            return list(qs.filter(page_number=page_number))
        elif start_page is not None and end_page is not None:
            return list(qs.filter(page_number__gte=start_page, page_number__lte=end_page))
        elif all_pages or (start_page is None and end_page is None and page_number is None):
            return list(qs)
        return []
