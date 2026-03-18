from datetime import datetime

from cadastros.models import ConfiguracaoSistema
from eventos.services.oficio_schema import oficio_justificativa_schema_available


DEFAULT_PRAZO_JUSTIFICATIVA_DIAS = 10


def get_prazo_justificativa_dias():
    config = (
        ConfiguracaoSistema.objects.order_by('pk')
        .values_list('prazo_justificativa_dias', flat=True)
        .first()
    )
    try:
        prazo = int(config)
    except (TypeError, ValueError):
        return DEFAULT_PRAZO_JUSTIFICATIVA_DIAS
    if prazo < 0:
        return DEFAULT_PRAZO_JUSTIFICATIVA_DIAS
    return prazo


def get_primeira_saida_oficio(oficio):
    primeira_saida = None
    for trecho in oficio.trechos.filter(saida_data__isnull=False, saida_hora__isnull=False).order_by('ordem', 'id'):
        saida = datetime.combine(trecho.saida_data, trecho.saida_hora)
        if primeira_saida is None or saida < primeira_saida:
            primeira_saida = saida
    return primeira_saida


def get_dias_antecedencia_oficio(oficio):
    if not oficio.data_criacao:
        return None
    primeira_saida = get_primeira_saida_oficio(oficio)
    if not primeira_saida:
        return None
    return (primeira_saida.date() - oficio.data_criacao).days


def oficio_exige_justificativa(oficio):
    dias_antecedencia = get_dias_antecedencia_oficio(oficio)
    if dias_antecedencia is None:
        return False
    return dias_antecedencia < get_prazo_justificativa_dias()


def oficio_tem_justificativa(oficio):
    if not oficio_justificativa_schema_available():
        return False
    return bool((oficio.justificativa_texto or '').strip())
