"""
Translation Service handling raw text translation, PDF page translations,
translation caching / language mapping, token quota deductions, and audit logging.
"""
import logging
from typing import Optional, Dict, Any, List
from django.db import transaction
from core.adapters.translation import TranslationEngineAdapter
from core.utils.token_counter import count_tokens
from translation.models import Document, ExtractedPage, TranslatedPage, TokenUsageLog
from users.models import Tenant

logger = logging.getLogger(__name__)


class InsufficientTokensException(Exception):
    def __init__(self, required_tokens: int, available_tokens: int):
        self.required_tokens = required_tokens
        self.available_tokens = available_tokens
        super().__init__(
            f"Insufficient tokens. Required: {required_tokens:,}, Available: {available_tokens:,}. Please top up your balance."
        )


class TranslationService:
    def __init__(self, engine_adapter: Optional[TranslationEngineAdapter] = None):
        self.engine = engine_adapter or TranslationEngineAdapter.get_instance()

    def translate_raw(self, tenant: Tenant, text: str, source_lang: str = "eng_Latn", target_lang: str = "hin_Deva") -> Dict[str, Any]:
        """
        Translates raw input text, counts word tokens, enforces token balance,
        deducts balance and records usage log.
        """
        if not text or not text.strip():
            return {
                "translated_text": "",
                "tokens_used": 0,
                "remaining_balance": tenant.token_balance,
                "source_lang": source_lang,
                "target_lang": target_lang,
            }

        required_tokens = count_tokens(text)

        if tenant.token_balance < required_tokens:
            raise InsufficientTokensException(required_tokens, tenant.token_balance)

        # Perform translation
        translated_text = self.engine.translate_paragraph(text, source_lang=source_lang, tgt_lang=target_lang)

        with transaction.atomic():
            tenant.token_balance -= required_tokens
            tenant.total_tokens_used += required_tokens
            tenant.save(update_fields=['token_balance', 'total_tokens_used', 'updated_at'])

            TokenUsageLog.objects.create(
                tenant=tenant,
                request_type='raw_translate',
                token_count=required_tokens,
                source_lang=source_lang,
                target_lang=target_lang,
                details={"text_snippet": text[:100]}
            )

        return {
            "translated_text": translated_text,
            "tokens_used": required_tokens,
            "remaining_balance": tenant.token_balance,
            "source_lang": source_lang,
            "target_lang": target_lang,
        }

    def translate_pdf_page(self, tenant: Tenant, document: Document, page_number: int,
                           target_lang: str = "hin_Deva", source_lang: str = "eng_Latn") -> Dict[str, Any]:
        """
        Translates a single extracted page of a PDF document.
        If a translation for (extracted_page, target_language) already exists,
        returns the cached translation without re-translating or deducting tokens!
        """
        try:
            extracted_page = document.pages.get(page_number=page_number)
        except ExtractedPage.DoesNotExist:
            raise ValueError(f"Page {page_number} has not been extracted yet. Please extract it first.")

        # Check existing cached translation
        existing = TranslatedPage.objects.filter(extracted_page=extracted_page, target_language=target_lang).first()
        if existing:
            return {
                "document_id": document.id,
                "page_number": page_number,
                "source_lang": existing.source_language,
                "target_lang": existing.target_language,
                "translated_text": existing.translated_text,
                "tokens_used": 0,
                "cached": True,
                "remaining_balance": tenant.token_balance,
            }

        page_text = extracted_page.combined_text
        if not page_text.strip():
            # Empty page
            translated_obj = TranslatedPage.objects.create(
                extracted_page=extracted_page,
                source_language=source_lang,
                target_language=target_lang,
                translated_text="",
                tokens_used=0
            )
            return {
                "document_id": document.id,
                "page_number": page_number,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "translated_text": "",
                "tokens_used": 0,
                "cached": False,
                "remaining_balance": tenant.token_balance,
            }

        required_tokens = count_tokens(page_text)
        if tenant.token_balance < required_tokens:
            raise InsufficientTokensException(required_tokens, tenant.token_balance)

        # Translate page
        translated_text = self.engine.translate_paragraph(page_text, source_lang=source_lang, tgt_lang=target_lang)

        with transaction.atomic():
            tenant.token_balance -= required_tokens
            tenant.total_tokens_used += required_tokens
            tenant.save(update_fields=['token_balance', 'total_tokens_used', 'updated_at'])

            translated_obj = TranslatedPage.objects.create(
                extracted_page=extracted_page,
                source_language=source_lang,
                target_language=target_lang,
                translated_text=translated_text,
                tokens_used=required_tokens
            )

            TokenUsageLog.objects.create(
                tenant=tenant,
                document=document,
                request_type='pdf_page_translate',
                token_count=required_tokens,
                source_lang=source_lang,
                target_lang=target_lang,
                details={"page_number": page_number, "document_title": document.title}
            )

        return {
            "document_id": document.id,
            "page_number": page_number,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "translated_text": translated_text,
            "tokens_used": required_tokens,
            "cached": False,
            "remaining_balance": tenant.token_balance,
        }

    def translate_pdf_all(self, tenant: Tenant, document: Document,
                          target_lang: str = "hin_Deva", source_lang: str = "eng_Latn") -> Dict[str, Any]:
        """
        Translates all currently extracted pages of the document.
        Uses cached translations where available and only charges tokens for new translations.
        """
        extracted_pages = list(document.pages.all().order_by('page_number'))
        if not extracted_pages:
            raise ValueError("No extracted pages found in this document. Please extract pages first.")

        # Calculate tokens needed for uncached pages
        uncached_pages = []
        cached_count = 0
        total_required_tokens = 0

        for ep in extracted_pages:
            if TranslatedPage.objects.filter(extracted_page=ep, target_language=target_lang).exists():
                cached_count += 1
            else:
                uncached_pages.append(ep)
                total_required_tokens += count_tokens(ep.combined_text)

        if tenant.token_balance < total_required_tokens:
            raise InsufficientTokensException(total_required_tokens, tenant.token_balance)

        results = []
        total_tokens_deducted = 0

        for ep in extracted_pages:
            res = self.translate_pdf_page(tenant, document, ep.page_number, target_lang, source_lang)
            results.append(res)
            if not res['cached']:
                total_tokens_deducted += res['tokens_used']

        return {
            "document_id": document.id,
            "document_title": document.title,
            "target_lang": target_lang,
            "total_pages_translated": len(results),
            "cached_pages_count": cached_count,
            "newly_translated_count": len(uncached_pages),
            "total_tokens_deducted": total_tokens_deducted,
            "remaining_balance": tenant.token_balance,
            "pages": results,
        }

    def translate_pdf_range(self, tenant: Tenant, document: Document, start_page: int, end_page: int,
                            target_lang: str = "hin_Deva", source_lang: str = "eng_Latn") -> Dict[str, Any]:
        """
        Translates a range of pages [start_page, end_page].
        """
        if start_page > end_page:
            raise ValueError(f"start_page ({start_page}) cannot be greater than end_page ({end_page}).")

        pages = list(document.pages.filter(page_number__gte=start_page, page_number__lte=end_page).order_by('page_number'))
        if not pages:
            raise ValueError(f"No extracted pages found in range {start_page} to {end_page}.")

        results = []
        total_tokens_deducted = 0
        cached_count = 0

        for ep in pages:
            res = self.translate_pdf_page(tenant, document, ep.page_number, target_lang, source_lang)
            results.append(res)
            if res['cached']:
                cached_count += 1
            else:
                total_tokens_deducted += res['tokens_used']

        return {
            "document_id": document.id,
            "range": f"{start_page}-{end_page}",
            "target_lang": target_lang,
            "pages_translated": len(results),
            "cached_pages_count": cached_count,
            "total_tokens_deducted": total_tokens_deducted,
            "remaining_balance": tenant.token_balance,
            "pages": results,
        }

    def get_translations(self, document: Document, target_lang: str,
                         page_number: Optional[int] = None, start_page: Optional[int] = None,
                         end_page: Optional[int] = None, all_pages: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves existing translated pages for a document and target language.
        Supports single page, page range, and all pages.
        """
        qs = TranslatedPage.objects.filter(
            extracted_page__document=document,
            target_language=target_lang
        ).select_related('extracted_page').order_by('extracted_page__page_number')

        if page_number is not None:
            qs = qs.filter(extracted_page__page_number=page_number)
        elif start_page is not None and end_page is not None:
            qs = qs.filter(extracted_page__page_number__gte=start_page, extracted_page__page_number__lte=end_page)

        return [
            {
                "page_number": tp.extracted_page.page_number,
                "source_language": tp.source_language,
                "target_language": tp.target_language,
                "translated_text": tp.translated_text,
                "tokens_used": tp.tokens_used,
                "translated_at": tp.translated_at.isoformat(),
            }
            for tp in qs
        ]
