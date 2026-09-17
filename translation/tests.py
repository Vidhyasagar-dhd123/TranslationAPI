"""
Automated unit & integration tests for Translation Service, PDF Service, OCR, and Caching.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
import json
import io
import pypdf
from users.models import Tenant, ApiKey
from translation.models import Document, ExtractedPage, TranslatedPage, TokenUsageLog


def create_dummy_pdf(pages_text: list) -> bytes:
    """Creates an in-memory multi-page PDF for testing."""
    writer = pypdf.PdfWriter()
    for text in pages_text:
        # Create a page with text
        page = pypdf.PageObject.create_blank_page(width=300, height=300)
        # Note: blank pages are valid PDF pages
        writer.add_page(page)
    
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class TranslationAndPDFTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.tenant = Tenant.objects.create(name="Acme Corp", email="acme@corp.com", token_balance=1000)
        self.api_key = ApiKey.objects.create(tenant=self.tenant)

    def test_raw_translation_token_accounting(self):
        # 1. Translate raw text: 7 words
        text = "Hello world, this is a translation test."
        res = self.client.post(
            reverse('translate_raw'),
            data=json.dumps({"text": text, "source_lang": "eng_Latn", "target_lang": "hin_Deva"}),
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        tokens_used = data['data']['tokens_used']
        self.assertEqual(tokens_used, 7) # 7 words

        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.token_balance, 1000 - 7)
        self.assertEqual(self.tenant.total_tokens_used, 7)

        # Check TokenUsageLog
        self.assertEqual(TokenUsageLog.objects.filter(tenant=self.tenant).count(), 1)

    def test_raw_translation_insufficient_tokens(self):
        # Tenant with 2 tokens tries to translate 5-word sentence
        self.tenant.token_balance = 2
        self.tenant.save()

        res = self.client.post(
            reverse('translate_raw'),
            data=json.dumps({"text": "One two three four five", "source_lang": "eng_Latn", "target_lang": "hin_Deva"}),
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(res.status_code, 402)
        data = res.json()
        self.assertEqual(data['error']['code'], 'INSUFFICIENT_TOKENS')

    def test_pdf_upload_auto_mode(self):
        pdf_bytes = create_dummy_pdf(["Page 1 content", "Page 2 content", "Page 3 content"])
        pdf_file = SimpleUploadedFile("sample_test.pdf", pdf_bytes, content_type="application/pdf")

        res = self.client.post(
            reverse('upload_pdf'),
            data={"file": pdf_file, "mode": "auto", "title": "Auto Test Document"},
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data['success'])
        doc_id = data['data']['document_id']
        self.assertEqual(data['data']['total_pages'], 3)
        self.assertEqual(data['data']['extracted_pages_count'], 3)

        doc = Document.objects.get(id=doc_id)
        self.assertEqual(doc.pages.count(), 3)
        self.tenant.refresh_from_db()
        self.assertGreater(self.tenant.storage_used_bytes, 0)

    def test_pdf_upload_manual_mode_and_page_by_page_extraction(self):
        pdf_bytes = create_dummy_pdf(["Page 1 content", "Page 2 content", "Page 3 content"])
        pdf_file = SimpleUploadedFile("manual_test.pdf", pdf_bytes, content_type="application/pdf")

        # Upload in manual mode
        res = self.client.post(
            reverse('upload_pdf'),
            data={"file": pdf_file, "mode": "manual", "title": "Manual Test Document"},
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(res.status_code, 201)
        doc_id = res.json()['data']['document_id']

        doc = Document.objects.get(id=doc_id)
        self.assertEqual(doc.pages.count(), 0) # Not extracted yet

        # Extract page 1
        ext_res1 = self.client.post(
            reverse('extract_page', kwargs={'doc_id': doc_id}),
            data=json.dumps({"page_number": 1}),
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(ext_res1.status_code, 200)
        self.assertEqual(doc.pages.count(), 1)

        # Extract next page
        ext_res2 = self.client.post(
            reverse('extract_page', kwargs={'doc_id': doc_id}),
            data=json.dumps({}),
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(ext_res2.status_code, 200)
        self.assertEqual(ext_res2.json()['data']['page_number'], 2)
        self.assertEqual(doc.pages.count(), 2)

    def test_pdf_translation_caching_and_mapping(self):
        # Setup document with extracted page
        doc = Document.objects.create(
            tenant=self.tenant,
            title="Translation Cache Test",
            file_name="test.pdf",
            file_path="dummy/test.pdf",
            total_pages=1,
            extracted_pages_count=1,
            status="extracted"
        )
        page = ExtractedPage.objects.create(
            document=doc,
            page_number=1,
            raw_text="This is page one text for translation test.",
            combined_text="This is page one text for translation test.",
            word_count=8
        )

        # 1. Translate Page 1 (First time -> Should deduct 8 tokens)
        res1 = self.client.post(
            reverse('translate_page', kwargs={'doc_id': doc.id}),
            data=json.dumps({"page_number": 1, "target_lang": "hin_Deva"}),
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()['data']
        self.assertFalse(data1['cached'])
        self.assertEqual(data1['tokens_used'], 8)

        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.token_balance, 1000 - 8)

        # 2. Request SAME translation again -> Must return CACHED translation with 0 tokens deducted!
        res2 = self.client.post(
            reverse('translate_page', kwargs={'doc_id': doc.id}),
            data=json.dumps({"page_number": 1, "target_lang": "hin_Deva"}),
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()['data']
        self.assertTrue(data2['cached'])
        self.assertEqual(data2['tokens_used'], 0)

        # Balance remains unchanged
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.token_balance, 1000 - 8)

        # 3. Retrieve stored translations
        get_res = self.client.get(
            reverse('get_translations', kwargs={'doc_id': doc.id}) + "?lang=hin_Deva&all=true",
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(get_res.status_code, 200)
        t_data = get_res.json()['data']
        self.assertEqual(t_data['count'], 1)
        self.assertEqual(t_data['translations'][0]['page_number'], 1)

    def test_delete_document_cascades_and_is_tenant_scoped(self):
        other_tenant = Tenant.objects.create(name="Other Corp", email="other@corp.com")
        other_key = ApiKey.objects.create(tenant=other_tenant)
        doc = Document.objects.create(
            tenant=self.tenant,
            title="Delete Me",
            file_name="delete-me.pdf",
            file_path="tenant_1/pdfs/delete-me.pdf",
            file_size_bytes=128,
            total_pages=1,
            extracted_pages_count=1,
        )
        page = ExtractedPage.objects.create(document=doc, page_number=1, combined_text="text")
        TranslatedPage.objects.create(
            extracted_page=page,
            target_language="hin_Deva",
            translated_text="translated",
        )
        self.tenant.storage_used_bytes = 128
        self.tenant.save(update_fields=['storage_used_bytes'])

        forbidden_res = self.client.delete(
            reverse('delete_document', kwargs={'doc_id': doc.id}),
            HTTP_X_API_KEY=other_key.key
        )
        self.assertEqual(forbidden_res.status_code, 404)
        self.assertTrue(Document.objects.filter(id=doc.id).exists())

        delete_res = self.client.delete(
            reverse('delete_document', kwargs={'doc_id': doc.id}),
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(delete_res.status_code, 200)
        self.assertFalse(Document.objects.filter(id=doc.id).exists())
        self.assertFalse(ExtractedPage.objects.filter(id=page.id).exists())
        self.assertEqual(TranslatedPage.objects.count(), 0)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.storage_used_bytes, 0)
