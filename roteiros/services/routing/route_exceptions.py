# -*- coding: utf-8 -*-


class RouteServiceError(Exception):
    """Erro base do serviço de rotas (mensagem segura para o cliente)."""

    user_message = "Não foi possível calcular a rota automaticamente. Você pode preencher a distância e o tempo manualmente."

    def __init__(self, message=None, *, user_message=None):
        self.user_message = user_message or self.user_message
        super().__init__(message or self.user_message)


class RouteConfigurationError(RouteServiceError):
    user_message = (
        "API de rotas não configurada. Defina OPENROUTESERVICE_API_KEY no arquivo .env "
        "para habilitar o cálculo automático."
    )


class RouteAuthenticationError(RouteServiceError):
    user_message = (
        "Chave da API de rotas inválida ou sem autorização. Verifique OPENROUTESERVICE_API_KEY no .env."
    )


class RouteValidationError(RouteServiceError):
    user_message = "Dados do roteiro insuficientes ou inválidos para calcular a rota."


class RouteProviderUnavailable(RouteServiceError):
    user_message = "O serviço de rotas está temporariamente indisponível. Tente novamente mais tarde."


class RouteRateLimitError(RouteServiceError):
    user_message = "Limite de uso do serviço de rotas foi atingido. Tente mais tarde ou preencha manualmente."


class RouteNotFoundError(RouteServiceError):
    user_message = "Não foi encontrado caminho viável entre os pontos informados."


class RouteTimeoutError(RouteServiceError):
    user_message = "O serviço de rotas demorou demais para responder. Tente novamente."


class RouteCoordinateError(RouteServiceError):
    user_message = (
        "Não foi possível calcular a rota porque um dos municípios selecionados "
        "não possui latitude/longitude cadastrada."
    )
