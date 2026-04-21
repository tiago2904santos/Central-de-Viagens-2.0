from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from integracoes.models import GoogleDriveIntegration


class GoogleDriveServiceError(Exception):
    pass


class GoogleDriveIntegrationNotConfigured(GoogleDriveServiceError):
    pass


class GoogleDriveCredentialsError(GoogleDriveServiceError):
    pass


class GoogleDriveApiError(GoogleDriveServiceError):
    pass


@dataclass
class GoogleDriveClientContext:
    service: any
    integration: GoogleDriveIntegration


class GoogleDriveService:
    FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

    def get_active_integration(self, user: get_user_model()) -> GoogleDriveIntegration:
        integration = (
            GoogleDriveIntegration.objects.filter(user=user, is_active=True)
            .order_by("-updated_at")
            .first()
        )
        if not integration:
            raise GoogleDriveIntegrationNotConfigured(
                "Usuario sem integracao Google Drive ativa."
            )
        return integration

    def _build_credentials(self, integration: GoogleDriveIntegration) -> Credentials:
        payload = integration.credentials_payload()
        if not payload.get("token"):
            raise GoogleDriveCredentialsError("Access token ausente.")
        credentials = Credentials.from_authorized_user_info(payload, payload.get("scopes") or [])
        return credentials

    def _refresh_credentials_if_needed(
        self, integration: GoogleDriveIntegration, credentials: Credentials
    ) -> Credentials:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            integration.update_tokens_from_credentials(credentials)
            return credentials
        if credentials.expired:
            raise GoogleDriveCredentialsError(
                "Credenciais expiradas e sem refresh token."
            )
        return credentials

    def get_authenticated_service(self, user: get_user_model()) -> GoogleDriveClientContext:
        integration = self.get_active_integration(user)
        try:
            credentials = self._build_credentials(integration)
            credentials = self._refresh_credentials_if_needed(integration, credentials)
            service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        except HttpError as exc:
            raise GoogleDriveApiError("Falha de autenticacao com a API do Google Drive.") from exc
        return GoogleDriveClientContext(service=service, integration=integration)

    @staticmethod
    def _folder_query(parent_id: str | None, folder_name: str) -> str:
        escaped_name = folder_name.replace("'", "\\'")
        if parent_id:
            return (
                f"name = '{escaped_name}' and "
                f"mimeType = '{GoogleDriveService.FOLDER_MIME_TYPE}' and "
                f"'{parent_id}' in parents and trashed = false"
            )
        return (
            f"name = '{escaped_name}' and "
            f"mimeType = '{GoogleDriveService.FOLDER_MIME_TYPE}' and "
            f"'root' in parents and trashed = false"
        )

    def find_folder_by_name(self, service, parent_id: str | None, folder_name: str) -> dict | None:
        query = self._folder_query(parent_id, folder_name)
        try:
            response = (
                service.files()
                .list(
                    q=query,
                    spaces="drive",
                    pageSize=1,
                    fields="files(id, name)",
                    supportsAllDrives=False,
                )
                .execute()
            )
        except HttpError as exc:
            raise GoogleDriveApiError("Falha ao consultar pasta no Google Drive.") from exc
        files = response.get("files", [])
        return files[0] if files else None

    def create_folder(self, service, parent_id: str | None, folder_name: str) -> dict:
        payload = {"name": folder_name, "mimeType": self.FOLDER_MIME_TYPE}
        if parent_id:
            payload["parents"] = [parent_id]
        try:
            return (
                service.files()
                .create(body=payload, fields="id, name", supportsAllDrives=False)
                .execute()
            )
        except HttpError as exc:
            raise GoogleDriveApiError("Falha ao criar pasta no Google Drive.") from exc

    def ensure_folder(self, service, parent_id: str | None, folder_name: str) -> dict:
        existing = self.find_folder_by_name(service, parent_id, folder_name)
        if existing:
            return existing
        return self.create_folder(service, parent_id, folder_name)

    def upload_file(
        self,
        service,
        parent_id: str,
        local_path: str,
        mime_type: str,
        target_name: str,
    ) -> dict:
        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=False)
        metadata = {"name": target_name, "parents": [parent_id]}
        try:
            return (
                service.files()
                .create(
                    body=metadata,
                    media_body=media,
                    fields="id, name, webViewLink",
                    supportsAllDrives=False,
                )
                .execute()
            )
        except HttpError as exc:
            raise GoogleDriveApiError("Falha ao enviar arquivo para o Google Drive.") from exc

    def ensure_user_root_folder(
        self, user: get_user_model(), root_folder_name: str | None = None
    ) -> GoogleDriveIntegration:
        context = self.get_authenticated_service(user)
        integration = context.integration
        target_name = (root_folder_name or integration.root_folder_name or "").strip()
        if not target_name:
            raise GoogleDriveIntegrationNotConfigured(
                "Pasta raiz do Google Drive nao configurada."
            )
        folder = self.ensure_folder(context.service, None, target_name)
        integration.root_folder_id = folder["id"]
        integration.root_folder_name = folder["name"]
        integration.updated_at = timezone.now()
        integration.save(update_fields=["root_folder_id", "root_folder_name", "updated_at"])
        return integration

    def disconnect_user(self, user: get_user_model()) -> None:
        integration = self.get_active_integration(user)
        integration.mark_disconnected()
