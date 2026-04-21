from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse

from integracoes.services.google_drive.oauth_service import GoogleOAuthService, OAuthStateError


@login_required
def google_drive_connect(request):
    oauth_data = GoogleOAuthService.build_authorization_url()
    GoogleOAuthService.persist_state_in_session(request, oauth_data.state)
    return redirect(oauth_data.authorization_url)


@login_required
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
    except Exception:
        messages.error(request, "Nao foi possivel concluir a conexao com o Google Drive.")
    return redirect(reverse("eventos:documentos-hub"))
