from eventos.services.oficio_schema import get_oficio_justificativa_schema_status

from .backends import get_document_backend_availability
from .context import (
    build_justificativa_document_context,
    build_oficio_document_context,
    build_ordem_servico_document_context,
    build_plano_trabalho_document_context,
    build_termo_autorizacao_document_context,
)
from .types import DocumentoFormato, DocumentoOficioTipo, get_document_type_meta


def _normalize_validation(errors, sections=None):
    normalized_errors = list(dict.fromkeys([error for error in (errors or []) if error]))
    return {
        'ok': not normalized_errors,
        'errors': normalized_errors,
        'sections': sections or [],
    }


def _merge_document_validation(base_validation, section_id, section_label, extra_errors):
    sections = list(base_validation.get('sections') or [])
    errors = list(base_validation.get('errors') or [])
    normalized_extra = list(dict.fromkeys([error for error in (extra_errors or []) if error]))
    if normalized_extra:
        sections.append(
            {
                'id': section_id,
                'label': section_label,
                'errors': normalized_extra,
            }
        )
        errors.extend(normalized_extra)
    return _normalize_validation(errors, sections=sections)


def _validate_base_travel_document(oficio):
    from eventos.views import _validate_oficio_for_finalize

    finalize_validation = _validate_oficio_for_finalize(oficio)
    return _normalize_validation(
        finalize_validation.get('errors'),
        sections=finalize_validation.get('sections') or [],
    )


def _get_primary_signature(context):
    return (context.get('assinaturas') or [{}])[0]


def _build_signature_and_config_errors(context, *, signature_label, required_fields):
    errors = []
    assinatura = _get_primary_signature(context)
    if not (assinatura.get('nome') or '').strip() or not (assinatura.get('cargo') or '').strip():
        errors.append(f'Configure uma assinatura ativa do tipo {signature_label} com nome e cargo.')
    for field_name, field_label in required_fields:
        if not (context['institucional'].get(field_name) or '').strip():
            errors.append(f'Informe {field_label} nas configurações do sistema.')
    return errors


def _validate_termo_viajante_min_fields(viajante):
    nome = (getattr(viajante, 'nome', '') or '').strip()
    rg = (getattr(viajante, 'rg', '') or '').strip()
    cpf = (getattr(viajante, 'cpf', '') or '').strip()
    telefone = (getattr(viajante, 'telefone', '') or '').strip()
    sem_rg = bool(getattr(viajante, 'sem_rg', False))
    unidade_lotacao_id = getattr(viajante, 'unidade_lotacao_id', None)

    if not nome:
        return 'Há participante sem nome completo para o termo preenchido.'
    if not sem_rg and not rg:
        return f'Preencha o RG de {nome} para gerar o termo preenchido.'
    if not cpf:
        return f'Preencha o CPF de {nome} para gerar o termo preenchido.'
    if not telefone:
        return f'Preencha o telefone de {nome} para gerar o termo preenchido.'
    if not unidade_lotacao_id:
        return f'Preencha a lotação/unidade de {nome} para gerar o termo preenchido.'
    return ''


def _validate_oficio_document(oficio):
    base_validation = _validate_base_travel_document(oficio)
    context = build_oficio_document_context(oficio)
    extra_errors = _build_signature_and_config_errors(
        context,
        signature_label='OFICIO',
        required_fields=(('unidade', 'a unidade institucional'),),
    )
    return _merge_document_validation(base_validation, 'oficio_documento', 'Ofício', extra_errors)


def _validate_justificativa_document(oficio):
    context = build_justificativa_document_context(oficio)
    errors = []
    if not (oficio.justificativa_texto or '').strip():
        errors.append('Preencha o texto da justificativa antes de gerar o documento.')
    errors.extend(
        _build_signature_and_config_errors(
            context,
            signature_label='JUSTIFICATIVA',
            required_fields=(
                ('divisao', 'a divisão institucional'),
                ('unidade', 'a unidade institucional'),
                ('endereco', 'o endereço institucional'),
                ('email', 'o e-mail institucional'),
            ),
        )
    )
    return _normalize_validation(errors)


def _validate_termo_autorizacao_document(oficio):
    base_validation = _validate_base_travel_document(oficio)
    context = build_termo_autorizacao_document_context(oficio)
    extra_errors = []
    if not context['roteiro']['destinos']:
        extra_errors.append('Defina ao menos um destino para gerar o termo de autorização.')
    if not context['roteiro']['periodo_viagem']['resumo']:
        extra_errors.append('Defina o período do deslocamento para gerar o termo de autorização.')
    if not context['resumos']['participantes_nomes']:
        extra_errors.append('Selecione ao menos um viajante para gerar o termo de autorização.')
    for viajante in oficio.viajantes.all():
        viajante_error = _validate_termo_viajante_min_fields(viajante)
        if viajante_error:
            extra_errors.append(viajante_error)
    return _merge_document_validation(
        base_validation,
        'termo_autorizacao',
        'Termo de autorização',
        extra_errors,
    )


def _validate_plano_trabalho_document(oficio):
    base_validation = _validate_base_travel_document(oficio)
    context = build_plano_trabalho_document_context(oficio)
    extra_errors = []
    if not context['plano_trabalho']['objetivo']:
        extra_errors.append('Informe a finalidade da viagem antes de gerar o plano de trabalho.')
    if not context['plano_trabalho']['roteiro_resumo']:
        extra_errors.append('Salve um roteiro válido antes de gerar o plano de trabalho.')
    if not context['plano_trabalho']['participantes_texto']:
        extra_errors.append('Selecione ao menos um participante para gerar o plano de trabalho.')
    return _merge_document_validation(
        base_validation,
        'plano_trabalho',
        'Plano de trabalho',
        extra_errors,
    )


def _validate_ordem_servico_document(oficio):
    base_validation = _validate_base_travel_document(oficio)
    context = build_ordem_servico_document_context(oficio)
    extra_errors = []
    if not context['ordem_servico']['destinos_texto']:
        extra_errors.append('Defina o destino da missão antes de gerar a ordem de serviço.')
    if not context['ordem_servico']['periodo_viagem']:
        extra_errors.append('Defina o período do deslocamento antes de gerar a ordem de serviço.')
    if not context['ordem_servico']['participantes_texto']:
        extra_errors.append('Selecione ao menos um servidor para gerar a ordem de serviço.')
    extra_errors.extend(
        _build_signature_and_config_errors(
            context,
            signature_label='ORDEM_SERVICO',
            required_fields=(
                ('divisao', 'a divisão institucional'),
                ('unidade', 'a unidade institucional'),
            ),
        )
    )
    return _merge_document_validation(
        base_validation,
        'ordem_servico',
        'Ordem de serviço',
        extra_errors,
    )


def validate_oficio_for_document_generation(oficio, tipo_documento):
    meta = get_document_type_meta(tipo_documento)
    schema_status = get_oficio_justificativa_schema_status()
    if not schema_status['available']:
        return _normalize_validation([schema_status['message']])
    if meta.tipo == DocumentoOficioTipo.OFICIO:
        return _validate_oficio_document(oficio)
    if meta.tipo == DocumentoOficioTipo.JUSTIFICATIVA:
        return _validate_justificativa_document(oficio)
    if meta.tipo == DocumentoOficioTipo.TERMO_AUTORIZACAO:
        return _validate_termo_autorizacao_document(oficio)
    if meta.tipo == DocumentoOficioTipo.PLANO_TRABALHO:
        return _validate_plano_trabalho_document(oficio)
    if meta.tipo == DocumentoOficioTipo.ORDEM_SERVICO:
        return _validate_ordem_servico_document(oficio)
    return _normalize_validation(['Tipo documental ainda não implementado nesta fase.'])


def get_document_generation_status(oficio, tipo_documento, formato=DocumentoFormato.DOCX):
    meta = get_document_type_meta(tipo_documento)
    formato = DocumentoFormato(formato)
    if not meta.implemented:
        return {
            'status': 'planned',
            'ok': False,
            'errors': ['Ainda não implementado nesta fase.'],
            'format': formato.value,
            'meta': meta,
        }
    if not meta.supports(formato):
        return {
            'status': 'unavailable',
            'ok': False,
            'errors': [f'Formato {formato.value.upper()} ainda não disponível nesta fase.'],
            'format': formato.value,
            'meta': meta,
        }
    schema_status = get_oficio_justificativa_schema_status()
    if not schema_status['available']:
        return {
            'status': 'unavailable',
            'ok': False,
            'errors': [schema_status['message']],
            'format': formato.value,
            'meta': meta,
        }
    from .renderer import get_document_template_availability

    template_status = get_document_template_availability(meta.tipo)
    if not template_status['available']:
        return {
            'status': 'unavailable',
            'ok': False,
            'errors': [template_status['message']],
            'format': formato.value,
            'meta': meta,
        }
    backend_status = get_document_backend_availability(formato)
    if not backend_status['available']:
        return {
            'status': 'unavailable',
            'ok': False,
            'errors': [backend_status['message']],
            'backend_status': backend_status,
            'format': formato.value,
            'meta': meta,
        }
    validation = validate_oficio_for_document_generation(oficio, meta.tipo)
    return {
        'status': 'available' if validation['ok'] else 'pending',
        'ok': validation['ok'],
        'errors': validation['errors'],
        'sections': validation.get('sections') or [],
        'backend_status': backend_status,
        'format': formato.value,
        'meta': meta,
    }
