"""
Translation models: Document, ExtractedPage, TranslatedPage, and TokenUsageLog.
"""
from django.db import models
from users.models import Tenant


class Document(models.Model):
    EXTRACTION_MODES = [
        ('auto', 'Auto (Extract All Immediately)'),
        ('manual', 'Manual (Extract Page-By-Page On Demand)'),
    ]

    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('extracted', 'Extracted'),
        ('failed', 'Failed'),
    ]

    tenant = models.ForeignKey(Tenant, related_name='documents', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500, help_text="Relative or storage path to PDF")
    file_size_bytes = models.BigIntegerField(default=0)
    total_pages = models.IntegerField(default=0)
    extracted_pages_count = models.IntegerField(default=0)
    extraction_mode = models.CharField(max_length=20, choices=EXTRACTION_MODES, default='auto')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='uploaded')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.tenant.name}] {self.title} ({self.total_pages} pages)"

    @property
    def file_size_mb(self) -> float:
        return round(self.file_size_bytes / (1024 * 1024), 2)


class ExtractedPage(models.Model):
    document = models.ForeignKey(Document, related_name='pages', on_delete=models.CASCADE)
    page_number = models.IntegerField(help_text="1-indexed page number")
    raw_text = models.TextField(blank=True, default='', help_text="Direct text extracted from PDF page")
    ocr_text = models.TextField(blank=True, default='', help_text="Text extracted from embedded images via OCR")
    combined_text = models.TextField(blank=True, default='', help_text="Raw text + appended OCR text")
    has_images = models.BooleanField(default=False)
    image_count = models.IntegerField(default=0)
    word_count = models.IntegerField(default=0)
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('document', 'page_number')
        ordering = ['document', 'page_number']

    def __str__(self):
        return f"{self.document.title} - Page {self.page_number}"


class PageImage(models.Model):
    extracted_page = models.ForeignKey(ExtractedPage, related_name='images', on_delete=models.CASCADE)
    image_number = models.IntegerField(help_text="1-indexed image index on page")
    image_name = models.CharField(max_length=255)
    image_path = models.CharField(max_length=500, help_text="Relative storage path")
    image_url = models.CharField(max_length=500, help_text="Accessible media URL")
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    file_size_bytes = models.BigIntegerField(default=0)
    ocr_text = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['extracted_page', 'image_number']

    def __str__(self):
        return f"{self.extracted_page} - Image {self.image_number}"



class TranslatedPage(models.Model):
    extracted_page = models.ForeignKey(ExtractedPage, related_name='translations', on_delete=models.CASCADE)
    source_language = models.CharField(max_length=32, default='eng_Latn')
    target_language = models.CharField(max_length=32, db_index=True)
    translated_text = models.TextField()
    tokens_used = models.IntegerField(default=0)
    translated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('extracted_page', 'target_language')
        ordering = ['extracted_page__page_number']

    def __str__(self):
        return f"{self.extracted_page} -> {self.target_language}"


class TokenUsageLog(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='usage_logs', on_delete=models.CASCADE)
    document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.SET_NULL)
    request_type = models.CharField(max_length=50)  # 'raw_translate', 'pdf_page_translate', 'pdf_all_translate', 'pdf_range_translate'
    token_count = models.IntegerField(default=0)
    source_lang = models.CharField(max_length=32, default='eng_Latn')
    target_lang = models.CharField(max_length=32, default='hin_Deva')
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.tenant.name} - {self.request_type}: {self.token_count} tokens ({self.target_lang})"
