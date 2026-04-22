import secrets
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from integracoes.models import GoogleDriveIntegration

logger = logging.getLogger(__name__)

GOOGLE_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file", "openid", "email", "profile"]


class OAuthStateError(Exception):
    pass


@dataclass(frozen=True)
class OAuthAuthorizationData:
    authorization_url: str
    state: str
    code_verifier: str


class GoogleOAuthService:
    @staticmethod
    def _is_local_http_uri(uri: str) -> bool:
        parsed = urlparse((uri or "").strip())
        return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}

    @classmethod
    def _enable_insecure_transport_if_local_dev(cls, uri: str) -> None:
        if not getattr(settings, "DEBUG", False):
            return
        if not cls._is_local_http_uri(uri):
            return
        if os.environ.get("OAUTHLIB_INSECURE_TRANSPORT") == "1":
            return
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        logger.warning(
            "OAuthlib insecure transport habilitado para desenvolvimento local (HTTP localhost/127.0.0.1)."
        )

    @staticmethod
    def _enable_relaxed_scope_check() -> None:
        if os.environ.get("OAUTHLIB_RELAX_TOKEN_SCOPE") == "1":
            return
        os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
        logger.warning(
            "OAuthlib relax token scope habilitado para aceitar escopos equivalentes retornados pelo Google."
        )

    session_state_key = "google_oauth_state"

    @staticmethod
    def _read_oauth_settings() -> tuple[str, str, str]:
        client_id = (getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "") or "").strip()
        redirect_uri = (getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "") or "").strip()
        return client_id, client_secret, redirect_uri

    @classmethod
    def _missing_required_settings(cls, include_token_key: bool = False) -> list[str]:
        client_id, client_secret, redirect_uri = cls._read_oauth_settings()
        missing = []
        if not client_id:
            missing.append("GOOGLE_OAUTH_CLIENT_ID")
        if not client_secret:
            missing.append("GOOGLE_OAUTH_CLIENT_SECRET")
        if not redirect_uri:
            missing.append("GOOGLE_OAUTH_REDIRECT_URI")
        if include_token_key:
            token_key = (getattr(settings, "GOOGLE_TOKEN_ENCRYPTION_KEY", "") or "").strip()
            if not token_key:
                missing.append("GOOGLE_TOKEN_ENCRYPTION_KEY")
        return missing

    @classmethod
    def _log_runtime_configuration_diagnostics(cls, missing_settings: list[str]) -> None:
        client_id, client_secret, redirect_uri = cls._read_oauth_settings()
        env_path = Path(getattr(settings, "BASE_DIR", ".")) / ".env"
        logger.warning(
            "Configuracao OAuth Google incompleta",
            extra={
                "missing_settings": missing_settings,
                "env_path": str(env_path),
                "env_exists": env_path.exists(),
                "google_oauth_client_id_present": bool(client_id),
                "google_oauth_client_id_len": len(client_id),
                "google_oauth_client_secret_present": bool(client_secret),
                "google_oauth_client_secret_len": len(client_secret),
                "google_oauth_redirect_uri_present": bool(redirect_uri),
                "google_oauth_redirect_uri_len": len(redirect_uri),
            },
        )

    @classmethod
    def _ensure_oauth_settings(cls) -> None:
        missing = cls._missing_required_settings(include_token_key=False)
        if not missing:
            return
        cls._log_runtime_configuration_diagnostics(missing)
        missing_text = " e ".join(missing) if len(missing) <= 2 else ", ".join(missing[:-1]) + f" e {missing[-1]}"
        raise ImproperlyConfigured(
            f"Configuracao Google OAuth incompleta: faltando {missing_text}."
        )

    @classmethod
    def _ensure_post_oauth_settings(cls) -> None:
        missing = cls._missing_required_settings(include_token_key=True)
        if not missing:
            return
        cls._log_runtime_configuration_diagnostics(missing)
        missing_text = " e ".join(missing) if len(missing) <= 2 else ", ".join(missing[:-1]) + f" e {missing[-1]}"
        raise ImproperlyConfigured(
            f"Configuracao Google OAuth incompleta: faltando {missing_text}."
        )

    @classmethod
    def _get_client_config(cls) -> dict:
        cls._ensure_oauth_settings()
        client_id, client_secret, redirect_uri = cls._read_oauth_settings()
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
        redirect_uri = (getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "") or "").strip()
        cls._enable_insecure_transport_if_local_dev(redirect_uri)
        cls._enable_relaxed_scope_check()
        flow.redirect_uri = redirect_uri
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
        code_verifier = getattr(flow, "code_verifier", "") or ""
        if not code_verifier:
            raise ImproperlyConfigured(
                "Falha ao preparar o fluxo OAuth Google: code_verifier ausente."
            )
        return OAuthAuthorizationData(
            authorization_url=authorization_url,
            state=state,
            code_verifier=code_verifier,
        )

    @classmethod
    def persist_state_in_session(cls, request, state: str, code_verifier: str) -> None:
        request.session[cls.session_state_key] = {
            "state": state,
            "user_id": getattr(request.user, "pk", None),
            "code_verifier": code_verifier,
        }

    @classmethod
    def pop_and_validate_state(cls, request, received_state: str | None) -> str:
        payload = request.session.pop(cls.session_state_key, None) or {}
        stored_state = payload.get("state")
        stored_user_id = payload.get("user_id")
        code_verifier = payload.get("code_verifier") or ""
        current_user_id = getattr(request.user, "pk", None)
        if (
            not stored_state
            or not received_state
            or stored_state != received_state
            or stored_user_id != current_user_id
            or not code_verifier
        ):
            raise OAuthStateError("State OAuth invalido ou ausente.")
        return code_verifier

    @classmethod
    def exchange_code_for_credentials(
        cls, authorization_response: str, state: str, code_verifier: str
    ) -> Credentials:
        flow = cls.build_flow(state=state)
        flow.code_verifier = code_verifier
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
        cls._ensure_post_oauth_settings()
        integration, _ = GoogleDriveIntegration.objects.get_or_create(user=user)
        integration.google_email = cls._extract_email_from_id_token(credentials)
        if credentials.expiry and timezone.is_naive(credentials.expiry):
            credentials.expiry = timezone.make_aware(credentials.expiry, timezone.get_current_timezone())
        integration.update_tokens_from_credentials(credentials)
        return integration
