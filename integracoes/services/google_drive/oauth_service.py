import secrets
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from integracoes.models import GoogleDriveIntegration


GOOGLE_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file", "openid", "email", "profile"]


class OAuthStateError(Exception):
    pass


@dataclass(frozen=True)
class OAuthAuthorizationData:
    authorization_url: str
    state: str


class GoogleOAuthService:
    session_state_key = "google_oauth_state"

    @staticmethod
    def _get_client_config() -> dict:
        client_id = (settings.GOOGLE_OAUTH_CLIENT_ID or "").strip()
        client_secret = (settings.GOOGLE_OAUTH_CLIENT_SECRET or "").strip()
        redirect_uri = (settings.GOOGLE_OAUTH_REDIRECT_URI or "").strip()
        if not (client_id and client_secret and redirect_uri):
            raise ImproperlyConfigured("Variaveis GOOGLE_OAUTH_* nao configuradas.")
        return {
            "web": {
                "client_id": client_id,
                "project_id": "central-viagens",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": client_secret,
                "redirect_uris": [redirect_uri],
            }
        }

    @classmethod
    def build_flow(cls, state: str | None = None) -> Flow:
        flow = Flow.from_client_config(
            cls._get_client_config(),
            scopes=GOOGLE_DRIVE_SCOPES,
            state=state,
        )
        flow.redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI
        return flow

    @classmethod
    def build_authorization_url(cls) -> OAuthAuthorizationData:
        state = secrets.token_urlsafe(32)
        flow = cls.build_flow(state=state)
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return OAuthAuthorizationData(authorization_url=authorization_url, state=state)

    @classmethod
    def persist_state_in_session(cls, request, state: str) -> None:
        request.session[cls.session_state_key] = {
            "state": state,
            "user_id": getattr(request.user, "pk", None),
        }

    @classmethod
    def pop_and_validate_state(cls, request, received_state: str | None) -> None:
        payload = request.session.pop(cls.session_state_key, None) or {}
        stored_state = payload.get("state")
        stored_user_id = payload.get("user_id")
        current_user_id = getattr(request.user, "pk", None)
        if (
            not stored_state
            or not received_state
            or stored_state != received_state
            or stored_user_id != current_user_id
        ):
            raise OAuthStateError("State OAuth invalido ou ausente.")

    @classmethod
    def exchange_code_for_credentials(cls, authorization_response: str, state: str) -> Credentials:
        flow = cls.build_flow(state=state)
        flow.fetch_token(authorization_response=authorization_response)
        return flow.credentials

    @staticmethod
    def _extract_email_from_id_token(credentials: Credentials) -> str:
        id_token = credentials.id_token or {}
        if isinstance(id_token, dict):
            return id_token.get("email", "") or ""
        return ""

    @classmethod
    def save_user_credentials(cls, user: get_user_model(), credentials: Credentials) -> GoogleDriveIntegration:
        integration, _ = GoogleDriveIntegration.objects.get_or_create(user=user)
        integration.google_email = cls._extract_email_from_id_token(credentials)
        if credentials.expiry and timezone.is_naive(credentials.expiry):
            credentials.expiry = timezone.make_aware(credentials.expiry, timezone.get_current_timezone())
        integration.update_tokens_from_credentials(credentials)
        return integration
