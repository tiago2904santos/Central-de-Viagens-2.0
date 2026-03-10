import re
import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from ..models import Cidade


@login_required
@require_GET
def api_cidades_por_estado(request, estado_id):
    """Retorna JSON com as cidades do estado, ordenadas por nome. Base para formulários."""
    cidades = Cidade.objects.filter(estado_id=estado_id, ativo=True).order_by('nome').values('id', 'nome')
    return JsonResponse(list(cidades), safe=False)


def _sanitize_cep(cep):
    """Remove não-dígitos do CEP."""
    return re.sub(r'\D', '', str(cep).strip())


@login_required
@require_GET
def api_consulta_cep(request, cep):
    """
    Consulta ViaCEP e retorna endereço padronizado.
    GET /cadastros/api/cep/<cep>/
    Retorna 400 se CEP inválido (não 8 dígitos), 404 se não encontrado, 200 com JSON.
    """
    cep_limpo = _sanitize_cep(cep)
    if len(cep_limpo) != 8:
        return JsonResponse({'erro': 'CEP deve ter 8 dígitos.'}, status=400)
    url = f'https://viacep.com.br/ws/{cep_limpo}/json/'
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        return JsonResponse({'erro': 'Erro ao consultar CEP.'}, status=502)
    if data.get('erro') is True:
        return JsonResponse({'erro': 'CEP não encontrado.'}, status=404)
    cep_formatado = f"{data.get('cep', '')[:5]}-{data.get('cep', '')[-3:]}" if data.get('cep') else ''
    return JsonResponse({
        'cep': cep_formatado or data.get('cep', ''),
        'logradouro': data.get('logradouro', '') or '',
        'bairro': data.get('bairro', '') or '',
        'cidade': data.get('localidade', '') or '',
        'uf': (data.get('uf', '') or '').upper(),
    })
