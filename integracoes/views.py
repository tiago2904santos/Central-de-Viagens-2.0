import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.views.decorators.http import require_http_methods
from django.shortcuts import redirect
from django.urls import reverse

from integracoes.services.google_drive.drive_service import (
    GoogleDriveIntegrationNotConfigured,
    GoogleDriveService,
    GoogleDriveServiceError,
)
from integracoes.services.google_drive.oauth_service import GoogleOAuthService, OAuthStateError

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def google_drive_connect(request):
    try:
        oauth_data = GoogleOAuthService.build_authorization_url()
    except ImproperlyConfigured:
        messages.error(
            request,
            "Integracao Google Drive nao configurada no servidor. Defina GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET e GOOGLE_OAUTH_REDIRECT_URI no .env.",
        )
        logger.warning("OAuth Google Drive sem configuracao", extra={"user_id": request.user.pk})
        return redirect(reverse("eventos:documentos-hub"))
    GoogleOAuthService.persist_state_in_session(request, oauth_data.state)
    return redirect(oauth_data.authorization_url)


@login_required
@require_http_methods(["GET"])
def google_drive_callback(request):
    state = request.GET.get("state")
    try:
        GoogleOAuthService.pop_and_validate_state(request, state)
        credentials = GoogleOAuthService.exchange_code_for_credentials(
            authorization_response=request.build_absolute_uri(),
            state=state or "",
        )
        GoogleOAuthService.save_user_credentials(request.user, credentials)
        messages.success(request, "Google Drive conectado com sucesso.")
    except OAuthStateError:
        messages.error(request, "Falha de seguranca no retorno do Google OAuth.")
        logger.warning("OAuth state invalido no callback Google Drive", extra={"user_id": request.user.pk})
    except ImproperlyConfigured:
        messages.error(
            request,
            "Integracao Google Drive nao configurada no servidor. Revise as variaveis GOOGLE_OAUTH_* no .env.",
        )
        logger.warning("OAuth callback sem configuracao valida", extra={"user_id": request.user.pk})
    except Exception:
        messages.error(request, "Nao foi possivel concluir a conexao com o Google Drive.")
        logger.exception("Falha no callback OAuth Google Drive", extra={"user_id": request.user.pk})
    return redirect(reverse("eventos:documentos-hub"))


@login_required
@require_http_methods(["POST"])
def google_drive_disconnect(request):
    drive_service = GoogleDriveService()
    try:
        drive_service.disconnect_user(request.user)
        messages.success(request, "Google Drive desconectado com sucesso.")
    except GoogleDriveIntegrationNotConfigured:
        messages.info(request, "Nenhuma integracao ativa para desconectar.")
    return redirect(reverse("eventos:documentos-hub"))


@login_required
@require_http_methods(["POST"])
def google_drive_root_folder_update(request):
    root_folder_name = (request.POST.get("root_folder_name") or "").strip()
    if not root_folder_name:
        messages.error(request, "Informe o nome da pasta raiz do Google Drive.")
        return redirect(reverse("eventos:documentos-hub"))
    drive_service = GoogleDriveService()
    try:
        drive_service.ensure_user_root_folder(request.user, root_folder_name=root_folder_name)
        messages.success(request, "Pasta raiz do Google Drive configurada com sucesso.")
    except GoogleDriveServiceError as exc:
        messages.error(request, str(exc))
        logger.warning("Falha ao configurar pasta raiz Google Drive", extra={"user_id": request.user.pk})
    return redirect(reverse("eventos:documentos-hub"))
