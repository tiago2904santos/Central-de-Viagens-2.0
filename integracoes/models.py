import json
from datetime import timezone as dt_timezone

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.utils import timezone


class GoogleDriveIntegration(models.Model):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="google_drive_integration",
        verbose_name="Usuario",
    )
    google_email = models.EmailField("Email Google", blank=True, default="")
    access_token_encrypted = models.TextField("Access token (criptografado)", blank=True, default="")
    refresh_token_encrypted = models.TextField("Refresh token (criptografado)", blank=True, default="")
    token_uri = models.URLField("Token URI", blank=True, default="")
    client_id = models.CharField("OAuth client ID", max_length=255, blank=True, default="")
    scopes = models.JSONField("Scopes", default=list, blank=True)
    expiry = models.DateTimeField("Expira em", null=True, blank=True)
    root_folder_id = models.CharField("Root folder ID", max_length=255, blank=True, default="")
    root_folder_name = models.CharField("Root folder name", max_length=255, blank=True, default="")
    is_active = models.BooleanField("Ativa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Integracao Google Drive"
        verbose_name_plural = "Integracoes Google Drive"

    def __str__(self):
        return f"Google Drive - {self.user}"

    @staticmethod
    def _build_cipher() -> Fernet:
        encryption_key = (settings.GOOGLE_TOKEN_ENCRYPTION_KEY or "").strip()
        if not encryption_key:
            raise ImproperlyConfigured("GOOGLE_TOKEN_ENCRYPTION_KEY nao configurada.")
        try:
            return Fernet(encryption_key.encode("utf-8"))
        except Exception as exc:
            raise ImproperlyConfigured(
                "GOOGLE_TOKEN_ENCRYPTION_KEY invalida. Gere com Fernet.generate_key()."
            ) from exc

    @classmethod
    def _encrypt_value(cls, value: str) -> str:
        if not value:
            return ""
        cipher = cls._build_cipher()
        return cipher.encrypt(value.encode("utf-8")).decode("utf-8")

    @classmethod
    def _decrypt_value(cls, encrypted_value: str) -> str:
        if not encrypted_value:
            return ""
        cipher = cls._build_cipher()
        try:
            return cipher.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            raise ImproperlyConfigured("Falha ao descriptografar token do Google Drive.")

    @property
    def access_token(self) -> str:
        return self._decrypt_value(self.access_token_encrypted)

    @access_token.setter
    def access_token(self, value: str) -> None:
        self.access_token_encrypted = self._encrypt_value(value)

    @property
    def refresh_token(self) -> str:
        return self._decrypt_value(self.refresh_token_encrypted)

    @refresh_token.setter
    def refresh_token(self, value: str) -> None:
        self.refresh_token_encrypted = self._encrypt_value(value)

    def mark_disconnected(self) -> None:
        self.is_active = False
        self.access_token_encrypted = ""
        self.refresh_token_encrypted = ""
        self.expiry = None
        self.save(update_fields=["is_active", "access_token_encrypted", "refresh_token_encrypted", "expiry", "updated_at"])

    def update_tokens_from_credentials(self, credentials) -> None:
        self.access_token = credentials.token or ""
        if credentials.refresh_token:
            self.refresh_token = credentials.refresh_token
        self.token_uri = credentials.token_uri or self.token_uri
        self.client_id = credentials.client_id or self.client_id
        self.scopes = list(credentials.scopes or [])
        self.expiry = credentials.expiry
        self.is_active = True
        self.save()

    def credentials_payload(self) -> dict:
        expiry = self.expiry
        if timezone.is_naive(expiry) if expiry else False:
            expiry = timezone.make_aware(expiry, timezone.get_current_timezone())
        expiry_str = None
        if expiry:
            expiry_utc = timezone.localtime(expiry, dt_timezone.utc)
            expiry_str = expiry_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_uri": self.token_uri,
            "client_id": self.client_id,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "scopes": list(self.scopes or []),
            "expiry": expiry_str,
        }

    def credentials_payload_json(self) -> str:
        return json.dumps(self.credentials_payload())
