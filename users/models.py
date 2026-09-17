"""
Tenant, ApiKey, and PaymentTransaction models.
"""
from django.db import models
from django.contrib.auth.hashers import check_password, make_password
import secrets


def generate_api_key_str() -> str:
    return f"sk_live_{secrets.token_urlsafe(32)}"


class Tenant(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, db_index=True)
    password = models.CharField(max_length=128, blank=True, default='')
    token_balance = models.BigIntegerField(default=0, help_text="Available tokens balance")
    total_tokens_used = models.BigIntegerField(default=0, help_text="Lifetime tokens consumed")
    storage_used_bytes = models.BigIntegerField(default=0, help_text="Current total storage used in bytes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.email})"

    def set_password(self, raw_password: str):
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return bool(self.password) and check_password(raw_password, self.password)

    @property
    def storage_used_mb(self) -> float:
        return round(self.storage_used_bytes / (1024 * 1024), 2)

    @property
    def max_storage_mb(self) -> int:
        return 200

    @property
    def storage_percentage(self) -> float:
        max_bytes = 200 * 1024 * 1024
        if max_bytes == 0:
            return 0.0
        return min(100.0, round((self.storage_used_bytes / max_bytes) * 100, 2))


class ApiKey(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='api_keys', on_delete=models.CASCADE)
    key = models.CharField(max_length=128, unique=True, db_index=True, default=generate_api_key_str)
    name = models.CharField(max_length=100, default='Primary Key')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        masked_key = f"{self.key[:10]}...{self.key[-4:]}" if len(self.key) > 14 else self.key
        return f"{self.name} ({masked_key}) - {self.tenant.name}"


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    tenant = models.ForeignKey(Tenant, related_name='payments', on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=128, unique=True, db_index=True)
    order_id = models.CharField(max_length=128, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=49.99)
    currency = models.CharField(max_length=10, default='USD')
    tokens_granted = models.BigIntegerField(default=5_000_000)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='completed')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Txn {self.transaction_id}: +{self.tokens_granted:,} tokens for {self.tenant.name}"
