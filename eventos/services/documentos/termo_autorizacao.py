from types import SimpleNamespace

from cadastros.models import ConfiguracaoSistema
from eventos.services.justificativa import get_primeira_saida_oficio

from .context import build_termo_autorizacao_document_context
from .renderer import (
    get_termo_autorizacao_template_path,
    iter_all_paragraphs,
    render_docx_template_bytes,
    replace_paragraph_text,
)


MESES_PTBR = {
    1: 'janeiro',
    2: 'fevereiro',
    3: 'março',
    4: 'abril',
    5: 'maio',
    6: 'junho',
    7: 'julho',
    8: 'agosto',
    9: 'setembro',
    10: 'outubro',
    11: 'novembro',
    12: 'dezembro',
}

TERMO_MODALIDADE_COMPLETO = 'COMPLETO'
TERMO_MODALIDADE_SEMIPREENCHIDO = 'SEMIPREENCHIDO'


def _format_intervalo_datas(inicio, fim):
    if not inicio and not fim:
        return ''
    inicio = inicio or fim
    fim = fim or inicio
    if inicio == fim:
        return f"dia {inicio.day} de {MESES_PTBR.get(inicio.month, inicio.month)} de {inicio.year}"
    if inicio.year == fim.year and inicio.month == fim.month:
        return f"dias {inicio.day} a {fim.day} de {MESES_PTBR.get(inicio.month, inicio.month)} de {inicio.year}"
    if inicio.year == fim.year:
        return (
            f"dias {inicio.day} de {MESES_PTBR.get(inicio.month, inicio.month)} "
            f"a {fim.day} de {MESES_PTBR.get(fim.month, fim.month)} de {fim.year}"
        )
    return (
        f"dias {inicio.day} de {MESES_PTBR.get(inicio.month, inicio.month)} de {inicio.year} "
        f"a {fim.day} de {MESES_PTBR.get(fim.month, fim.month)} de {fim.year}"
    )


def _build_data_do_evento_from_dates(data_inicio, data_fim):
    return _format_intervalo_datas(data_inicio, data_fim)


def _normalize_destinos_texto(destinos_qs):
    destinos = []
    seen = set()
    for destino in destinos_qs.select_related('cidade', 'estado').order_by('ordem', 'id'):
        if destino.cidade_id and destino.estado_id:
            label = f'{destino.cidade.nome}/{destino.estado.sigla}'
        elif destino.cidade_id:
            label = destino.cidade.nome
        elif destino.estado_id:
            label = destino.estado.sigla
        else:
            label = ''
        label = (label or '').strip()
        if label and label not in seen:
            seen.add(label)
            destinos.append(label)
    return ', '.join(destinos)


def _extract_viatura_data(*, placa='', modelo='', combustivel=''):
    placa_val = (placa or '').strip()
    modelo_val = (modelo or '').strip()
    combustivel_val = (combustivel or '').strip()
    has_viatura = bool(placa_val or modelo_val or combustivel_val)
    viatura = modelo_val or placa_val
    return {
        'has_viatura': has_viatura,
        'placa': placa_val,
        'viatura': viatura,
        'combustivel': combustivel_val,
    }


def _build_viatura_data_from_oficio(oficio):
    if oficio is None:
        return _extract_viatura_data()
    return _extract_viatura_data(
        placa=getattr(oficio, 'placa_formatada', ''),
        modelo=getattr(oficio, 'modelo', ''),
        combustivel=getattr(oficio, 'combustivel', ''),
    )


def _build_viatura_data_from_evento(evento, oficios_relacionados):
    for oficio in oficios_relacionados:
        data = _build_viatura_data_from_oficio(oficio)
        if data['has_viatura']:
            return data
    if getattr(evento, 'veiculo_id', None):
        veiculo = evento.veiculo
        return _extract_viatura_data(
            placa=getattr(veiculo, 'placa_formatada', ''),
            modelo=getattr(veiculo, 'modelo', ''),
            combustivel=(getattr(getattr(veiculo, 'combustivel', None), 'nome', '') if veiculo else ''),
        )
    return _extract_viatura_data()


def _build_viatura_data_from_veiculo(veiculo):
    if veiculo is None:
        return _extract_viatura_data()
    combustivel = ''
    combustivel_obj = getattr(veiculo, 'combustivel', None)
    if combustivel_obj is not None:
        combustivel = getattr(combustivel_obj, 'nome', '') or ''
    return _extract_viatura_data(
        placa=getattr(veiculo, 'placa_formatada', ''),
        modelo=getattr(veiculo, 'modelo', ''),
        combustivel=combustivel,
    )


def _normalize_termo_modalidade(modalidade):
    normalized = (modalidade or '').strip().upper()
    if normalized == TERMO_MODALIDADE_SEMIPREENCHIDO:
        return TERMO_MODALIDADE_SEMIPREENCHIDO
    return TERMO_MODALIDADE_COMPLETO


def _resolve_termo_template_variant(modalidade, has_viatura):
    modalidade = _normalize_termo_modalidade(modalidade)
    if modalidade == TERMO_MODALIDADE_SEMIPREENCHIDO:
        return 'SEMIPREENCHIDO'
    if has_viatura:
        return 'COMPLETO_COM_VIATURA'
    return 'COMPLETO_SEM_VIATURA'


def _build_viajante_mapping(viajante, modalidade):
    modalidade = _normalize_termo_modalidade(modalidade)
    if viajante is None:
        viajante_nome = ''
        rg = ''
        cpf = ''
        telefone = ''
        lotacao = ''
    else:
        viajante_nome = (getattr(viajante, 'nome', '') or '').strip()
        rg = (getattr(viajante, 'rg_formatado', '') or getattr(viajante, 'rg', '') or '').strip()
        cpf = (getattr(viajante, 'cpf_formatado', '') or getattr(viajante, 'cpf', '') or '').strip()
        telefone = (getattr(viajante, 'telefone_formatado', '') or getattr(viajante, 'telefone', '') or '').strip()
        lotacao = (
            getattr(getattr(viajante, 'unidade_lotacao', None), 'nome', '') or ''
        ).strip()
    if modalidade == TERMO_MODALIDADE_SEMIPREENCHIDO:
        return {
            'nome_servidor': '',
            'rg_servidor': '',
            'cpf_servidor': '',
            'telefone': '',
            'lotacao': '',
        }
    return {
        'nome_servidor': viajante_nome,
        'rg_servidor': rg,
        'cpf_servidor': cpf,
        'telefone': telefone,
        'lotacao': lotacao,
    }


def _build_termo_placeholder_mapping(
    *,
    modalidade,
    data_do_evento,
    destino,
    viatura_data,
    viajante=None,
    institucional=None,
):
    unidade = (
        (institucional or {}).get('unidade')
        or (institucional or {}).get('orgao')
        or (institucional or {}).get('sigla_orgao')
        or ''
    )
    mapping = {
        'data_do_evento': data_do_evento or '',
        'destino': destino or '',
        'viatura': viatura_data.get('viatura') or '',
        'combustivel': viatura_data.get('combustivel') or '',
        'placa': viatura_data.get('placa') or '',
        'unidade': unidade,
        'unidade_rodape': unidade,
        'divisao': (institucional or {}).get('divisao') or '',
        'email': (institucional or {}).get('email') or '',
        'endereco': (institucional or {}).get('endereco') or '',
        'telefone_institucional': (institucional or {}).get('telefone') or '',
    }
    mapping.update(_build_viajante_mapping(viajante, modalidade))
    return mapping


def _build_institucional_context():
    config = ConfiguracaoSistema.objects.order_by('pk').first()
    if not config:
        return {}
    endereco_partes = [
        (getattr(config, 'logradouro', '') or '').strip(),
        (getattr(config, 'numero', '') or '').strip(),
        (getattr(config, 'bairro', '') or '').strip(),
    ]
    cidade_uf = ' / '.join(
        [
            part
            for part in [
                (getattr(config, 'cidade_endereco', '') or '').strip(),
                (getattr(config, 'uf', '') or '').strip(),
            ]
            if part
        ]
    )
    if cidade_uf:
        endereco_partes.append(cidade_uf)
    cep = (getattr(config, 'cep_formatado', '') or getattr(config, 'cep', '') or '').strip()
    if cep:
        endereco_partes.append(f'CEP {cep}')
    endereco = ', '.join(part for part in endereco_partes if part)
    return {
        'orgao': (getattr(config, 'nome_orgao', '') or '').strip(),
        'sigla_orgao': (getattr(config, 'sigla_orgao', '') or '').strip(),
        'divisao': (getattr(config, 'divisao', '') or '').strip(),
        'unidade': (getattr(config, 'unidade', '') or '').strip(),
        'endereco': endereco,
        'telefone': (getattr(config, 'telefone_formatado', '') or getattr(config, 'telefone', '') or '').strip(),
        'email': (getattr(config, 'email', '') or '').strip(),
    }


def _normalize_assinatura_visual(document):
    for paragraph in iter_all_paragraphs(document):
        text = ''.join(run.text for run in paragraph.runs).strip()
        if not text:
            continue
        if text.startswith('Autorização da Chefia:'):
            # Regra inegociável: termo impresso, sem identificação automática de chefia/assinante.
            replace_paragraph_text(paragraph, 'Autorização da Chefia:')


def _post_process_termo(document, mapping, viatura_data):
    has_viatura = bool(viatura_data.get('has_viatura'))
    if has_viatura:
        for paragraph in iter_all_paragraphs(document):
            text = ''.join(run.text for run in paragraph.runs).strip()
            if not text:
                continue
            if text.startswith('Viatura: Modelo:'):
                replace_paragraph_text(
                    paragraph,
                    f"Viatura: Modelo: {mapping.get('viatura') or mapping.get('placa') or '—'}",
                )
            elif text.startswith('Placa / Combustível:'):
                replace_paragraph_text(
                    paragraph,
                    f"Placa / Combustível: {mapping.get('placa') or '—'} / {mapping.get('combustivel') or '—'}",
                )
    _normalize_assinatura_visual(document)


def build_termo_autorizacao_template_context(oficio, modalidade=TERMO_MODALIDADE_COMPLETO, viajante=None):
    context = build_termo_autorizacao_document_context(oficio)
    primeira_saida = get_primeira_saida_oficio(oficio)
    data_inicio = primeira_saida.date() if primeira_saida else None
    data_fim = oficio.retorno_chegada_data or oficio.retorno_saida_data or data_inicio
    data_do_evento = _build_data_do_evento_from_dates(data_inicio, data_fim)
    viatura_data = _build_viatura_data_from_oficio(oficio)
    if viajante is None:
        viajante = oficio.viajantes.order_by('nome').first()
    mapping = _build_termo_placeholder_mapping(
        modalidade=modalidade,
        data_do_evento=data_do_evento,
        destino=context['termo']['destinos_texto'],
        viatura_data=viatura_data,
        viajante=viajante,
        institucional=context.get('institucional') or {},
    )
    return mapping, viatura_data


def render_termo_autorizacao_docx(oficio):
    mapping, viatura_data = build_termo_autorizacao_template_context(
        oficio,
        modalidade=TERMO_MODALIDADE_COMPLETO,
    )
    template_variant = _resolve_termo_template_variant(TERMO_MODALIDADE_COMPLETO, viatura_data['has_viatura'])
    template_path = get_termo_autorizacao_template_path(template_variant)
    return render_docx_template_bytes(
        template_path,
        mapping,
        post_processor=lambda document: _post_process_termo(document, mapping, viatura_data),
    )


def validate_evento_participante_termo_data(evento, viajante, modalidade):
    errors = []
    modalidade = _normalize_termo_modalidade(modalidade)
    if evento is None:
        return ['Evento não informado para geração do termo.']
    if not evento.data_inicio:
        errors.append('Defina a data de início do evento para gerar o termo.')
    if not evento.data_fim:
        errors.append('Defina a data de término do evento para gerar o termo.')
    destinos_texto = _normalize_destinos_texto(evento.destinos.all())
    if not destinos_texto:
        errors.append('Defina ao menos um destino no evento para gerar o termo.')
    if modalidade == TERMO_MODALIDADE_COMPLETO:
        if viajante is None:
            errors.append('Selecione o servidor para gerar termo completo.')
            return list(dict.fromkeys([e for e in errors if e]))
        nome = (getattr(viajante, 'nome', '') or '').strip()
        rg = (getattr(viajante, 'rg', '') or '').strip()
        cpf = (getattr(viajante, 'cpf', '') or '').strip()
        telefone = (getattr(viajante, 'telefone', '') or '').strip()
        sem_rg = bool(getattr(viajante, 'sem_rg', False))
        unidade_lotacao_id = getattr(viajante, 'unidade_lotacao_id', None)
        if not nome:
            errors.append('Preencha o nome do servidor para gerar o termo completo.')
        if not sem_rg and not rg:
            errors.append('Preencha o RG do servidor para gerar o termo completo.')
        if not cpf:
            errors.append('Preencha o CPF do servidor para gerar o termo completo.')
        if not telefone:
            errors.append('Preencha o telefone do servidor para gerar o termo completo.')
        if not unidade_lotacao_id:
            errors.append('Preencha a lotação/unidade do servidor para gerar o termo completo.')
    return list(dict.fromkeys([e for e in errors if e]))


def render_evento_participante_termo_docx(evento, viajante, modalidade, oficios_relacionados, veiculo_override=None):
    modalidade = _normalize_termo_modalidade(modalidade)
    destino = _normalize_destinos_texto(evento.destinos.all())
    data_do_evento = _build_data_do_evento_from_dates(evento.data_inicio, evento.data_fim)
    if veiculo_override is not None:
        viatura_data = _build_viatura_data_from_veiculo(veiculo_override)
    else:
        viatura_data = _build_viatura_data_from_evento(evento, oficios_relacionados)
    institucional = _build_institucional_context()
    mapping = _build_termo_placeholder_mapping(
        modalidade=modalidade,
        data_do_evento=data_do_evento,
        destino=destino,
        viatura_data=viatura_data,
        viajante=viajante,
        institucional=institucional,
    )
    template_variant = _resolve_termo_template_variant(modalidade, viatura_data['has_viatura'])
    template_path = get_termo_autorizacao_template_path(template_variant)
    return render_docx_template_bytes(
        template_path,
        mapping,
        post_processor=lambda document: _post_process_termo(document, mapping, viatura_data),
    )


def render_evento_termo_padrao_branco_docx(evento, veiculo_override=None):
    destino = _normalize_destinos_texto(evento.destinos.all())
    data_do_evento = _build_data_do_evento_from_dates(evento.data_inicio, evento.data_fim)
    if veiculo_override is not None:
        viatura_data = _build_viatura_data_from_veiculo(veiculo_override)
    else:
        viatura_data = _extract_viatura_data()
    mapping = _build_termo_placeholder_mapping(
        modalidade=TERMO_MODALIDADE_SEMIPREENCHIDO,
        data_do_evento=data_do_evento,
        destino=destino,
        viatura_data=viatura_data,
        viajante=None,
        institucional=_build_institucional_context(),
    )
    template_path = get_termo_autorizacao_template_path('SEMIPREENCHIDO')
    return render_docx_template_bytes(
        template_path,
        mapping,
        post_processor=lambda document: _post_process_termo(document, mapping, viatura_data),
    )


def _build_saved_termo_viajante_snapshot(termo):
    if getattr(termo, 'viajante_id', None) and getattr(termo, 'viajante', None):
        return termo.viajante
    if not any(
        [
            getattr(termo, 'servidor_nome', ''),
            getattr(termo, 'servidor_rg', ''),
            getattr(termo, 'servidor_cpf', ''),
            getattr(termo, 'servidor_telefone', ''),
            getattr(termo, 'servidor_lotacao', ''),
        ]
    ):
        return None
    unidade = None
    if getattr(termo, 'servidor_lotacao', ''):
        unidade = SimpleNamespace(nome=getattr(termo, 'servidor_lotacao', ''))
    return SimpleNamespace(
        nome=getattr(termo, 'servidor_nome', ''),
        rg=getattr(termo, 'servidor_rg', ''),
        cpf=getattr(termo, 'servidor_cpf', ''),
        telefone=getattr(termo, 'servidor_telefone', ''),
        unidade_lotacao=unidade,
    )


def build_saved_termo_autorizacao_template_context(termo):
    modalidade = (
        TERMO_MODALIDADE_SEMIPREENCHIDO
        if getattr(termo, 'modo_geracao', '') == 'RAPIDO'
        else TERMO_MODALIDADE_COMPLETO
    )
    data_do_evento = _build_data_do_evento_from_dates(
        getattr(termo, 'data_evento', None),
        getattr(termo, 'data_evento_fim', None) or getattr(termo, 'data_evento', None),
    )
    viatura_data = _extract_viatura_data(
        placa=getattr(termo, 'veiculo_placa', ''),
        modelo=getattr(termo, 'veiculo_modelo', ''),
        combustivel=getattr(termo, 'veiculo_combustivel', ''),
    )
    mapping = _build_termo_placeholder_mapping(
        modalidade=modalidade,
        data_do_evento=data_do_evento,
        destino=getattr(termo, 'destino', ''),
        viatura_data=viatura_data,
        viajante=_build_saved_termo_viajante_snapshot(termo),
        institucional=_build_institucional_context(),
    )
    template_variant = getattr(termo, 'template_variant', '') or 'SEMIPREENCHIDO'
    return mapping, viatura_data, template_variant


def render_saved_termo_autorizacao_docx(termo):
    mapping, viatura_data, template_variant = build_saved_termo_autorizacao_template_context(termo)
    template_path = get_termo_autorizacao_template_path(template_variant)
    return render_docx_template_bytes(
        template_path,
        mapping,
        post_processor=lambda document: _post_process_termo(document, mapping, viatura_data),
    )
