"""
Regras de negócio do Plano de Trabalho: atividades, metas, unidade móvel.
Nomes técnicos sem acento: atividades_formatada, metas_formatada, etc.
"""
from __future__ import annotations

from django.db.utils import OperationalError, ProgrammingError

from eventos.models import AtividadePlanoTrabalho

# Ordem oficial das atividades (código, nome, meta)
ATIVIDADES_CATALOGO = [
    {
        'codigo': 'CIN',
        'nome': 'Confecção da Carteira de Identidade Nacional (CIN)',
        'meta': (
            'Ampliar o acesso ao documento oficial de identificação civil, garantindo '
            'cidadania e inclusão social à população atendida.'
        ),
        'recurso_necessario': (
            'Kit de captura biométrica, estação de atendimento, conectividade e equipe '
            'técnica para triagem e emissão.'
        ),
    },
    {
        'codigo': 'BO',
        'nome': 'Registro de Boletins de Ocorrência',
        'meta': (
            'Possibilitar o atendimento imediato de demandas policiais, promovendo '
            'orientação e formalização de ocorrências no próprio evento.'
        ),
        'recurso_necessario': (
            'Posto de atendimento com sistema de registro, insumos administrativos e '
            'equipe para orientação ao cidadão.'
        ),
    },
    {
        'codigo': 'AAC',
        'nome': 'Emissão de Atestado de Antecedentes Criminais',
        'meta': (
            'Facilitar a obtenção do documento, contribuindo para fins trabalhistas e '
            'demais necessidades legais dos cidadãos.'
        ),
        'recurso_necessario': (
            'Terminal com acesso aos sistemas institucionais, impressão e equipe de '
            'apoio para validação de dados.'
        ),
    },
    {
        'codigo': 'PALESTRAS',
        'nome': 'Palestras e orientações preventivas',
        'meta': (
            'Desenvolver ações educativas voltadas à prevenção de crimes, conscientização '
            'sobre segurança pública e fortalecimento do vínculo comunitário.'
        ),
        'recurso_necessario': (
            'Espaço para apresentação, sistema de áudio, material didático e equipe de '
            'facilitação.'
        ),
    },
    {
        'codigo': 'LUDICO',
        'nome': 'Atividades lúdicas e educativas para crianças',
        'meta': (
            'Promover aproximação institucional de forma didática, incentivando a cultura '
            'de respeito às leis e à cidadania desde a infância.'
        ),
        'recurso_necessario': (
            'Materiais lúdicos, apoio pedagógico e área segura para dinâmicas com crianças.'
        ),
    },
    {
        'codigo': 'NOC',
        'nome': 'Apresentação do trabalho do Núcleo de Operações com Cães (NOC)',
        'meta': (
            'Demonstrar as atividades operacionais desenvolvidas pela unidade especializada '
            'da Polícia Civil do Paraná, evidenciando técnicas e capacidades institucionais.'
        ),
        'recurso_necessario': (
            'Área controlada para exibição operacional, equipe especializada, equipamentos '
            'de segurança e suporte logístico.'
        ),
    },
    {
        'codigo': 'TATICO',
        'nome': 'Exposição de material tático',
        'meta': (
            'Apresentar equipamentos utilizados nas atividades policiais, proporcionando '
            'transparência e conhecimento sobre os recursos empregados pela instituição.'
        ),
        'recurso_necessario': (
            'Bancadas de exposição, controle de acesso, equipe de apresentação e '
            'sinalização informativa.'
        ),
    },
    {
        'codigo': 'PAPILOSCOPIA',
        'nome': 'Exposição da atividade de perícia papiloscópica',
        'meta': (
            'Demonstrar os procedimentos técnicos de identificação humana, ressaltando a '
            'importância da papiloscopia na investigação criminal e na identificação civil.'
        ),
        'recurso_necessario': (
            'Estação demonstrativa, kits de coleta, materiais visuais e equipe técnica '
            'especializada.'
        ),
    },
    {
        'codigo': 'VIATURAS',
        'nome': 'Exposição de viaturas antigas e modernas',
        'meta': (
            'Apresentar a evolução histórica e tecnológica dos veículos operacionais da instituição.'
        ),
        'recurso_necessario': (
            'Área de exposição, apoio de segurança patrimonial e equipe para conduzir '
            'apresentações ao público.'
        ),
    },
    {
        'codigo': 'BANDA',
        'nome': 'Apresentação da banda institucional',
        'meta': (
            'Fortalecer a integração com a comunidade por meio de atividade cultural '
            'representativa da instituição.'
        ),
        'recurso_necessario': (
            'Estrutura de palco, sonorização, logística de montagem e suporte técnico '
            'para apresentação musical.'
        ),
    },
    {
        'codigo': 'UNIDADE_MOVEL',
        'nome': 'Unidade móvel (ônibus ou caminhão)',
        'meta': (
            'Viabilizar a prestação descentralizada dos serviços acima descritos, assegurando '
            'estrutura adequada para atendimento ao público.'
        ),
        'recurso_necessario': (
            'Unidade móvel institucional, equipe de operação, energia, conectividade e '
            'manutenção de suporte.'
        ),
    },
]

CODIGO_UNIDADE_MOVEL = 'UNIDADE_MOVEL'

TEXTO_UNIDADE_MOVEL = (
    'Estrutura: Unidade móvel da PCPR equipada para atendimento e confecção de documentos.'
)


def _codigos_from_string(value: str | None) -> list[str]:
    """Retorna lista de códigos únicos a partir de string (ex: 'CIN,BO,NOC')."""
    if not value or not (value := (value or '').strip()):
        return []
    seen = set()
    out = []
    for part in value.replace('，', ',').split(','):
        codigo = part.strip().upper()
        if codigo and codigo not in seen:
            seen.add(codigo)
            out.append(codigo)
    return out


def _codigos_validos_na_ordem(codigos: list[str]) -> list[dict]:
    """Retorna itens do catálogo na ordem oficial, apenas os que existem em codigos."""
    codigos_set = set(codigos)
    return [item for item in get_atividades_catalogo() if item['codigo'] in codigos_set]


def get_atividades_catalogo() -> list[dict]:
    """Retorna catálogo de atividades ativo no banco; fallback para catálogo padrão."""
    try:
        itens = list(
            AtividadePlanoTrabalho.objects.filter(ativo=True)
            .order_by('ordem', 'nome')
            .values('codigo', 'nome', 'meta', 'recurso_necessario')
        )
    except (OperationalError, ProgrammingError):
        itens = []
    if not itens:
        return [item.copy() for item in ATIVIDADES_CATALOGO]
    return itens


def build_atividades_formatada(codigos_raw: str | None) -> str:
    """
    Gera texto formatado das atividades selecionadas, na ordem oficial, sem duplicar.
    codigos_raw: string com códigos separados por vírgula (ex: 'CIN,BO,NOC').
    """
    codigos = _codigos_from_string(codigos_raw)
    itens = _codigos_validos_na_ordem(codigos)
    if not itens:
        return ''
    return '\n'.join(f"• {item['nome']}" for item in itens)


def build_metas_formatada(codigos_raw: str | None) -> str:
    """
    Gera texto formatado das metas correspondentes às atividades, na ordem oficial, sem duplicar.
    """
    codigos = _codigos_from_string(codigos_raw)
    itens = _codigos_validos_na_ordem(codigos)
    if not itens:
        return ''
    return '\n\n'.join(item['meta'] for item in itens)


def build_recursos_necessarios_formatado(codigos_raw: str | None) -> str:
    """
    Gera um texto-base de recursos a partir das atividades selecionadas.
    A estrutura fica pronta para detalhamento futuro sem deixar o PT com bloco morto.
    """
    codigos = _codigos_from_string(codigos_raw)
    itens = _codigos_validos_na_ordem(codigos)
    if not itens:
        return ''
    atividades = '; '.join(item['nome'] for item in itens)
    recursos_itens = []
    seen = set()
    for item in itens:
        recurso = (item.get('recurso_necessario') or '').strip()
        if not recurso or recurso in seen:
            continue
        seen.add(recurso)
        recursos_itens.append(f'• {recurso}')
    linhas = [
        (
            'Recursos operacionais, materiais de atendimento, equipamentos de apoio '
            'e suporte logístico compatíveis com as atividades selecionadas.'
        ),
        f'Escopo previsto: {atividades}.',
    ]
    if recursos_itens:
        linhas.append('Recursos específicos por atividade:')
        linhas.extend(recursos_itens)
    if CODIGO_UNIDADE_MOVEL in codigos:
        linhas.append('Prever unidade móvel institucional e o suporte operacional associado.')
    return '\n'.join(linhas)


def has_unidade_movel(codigos_raw: str | None) -> bool:
    """True se a atividade Unidade móvel (ônibus ou caminhão) estiver selecionada."""
    return CODIGO_UNIDADE_MOVEL in _codigos_from_string(codigos_raw)


def get_unidade_movel_text(codigos_raw: str | None) -> str:
    """
    Retorna o texto do placeholder {{unidade_movel}}.
    Preenchido apenas se a atividade Unidade móvel estiver marcada; senão vazio.
    """
    return TEXTO_UNIDADE_MOVEL if has_unidade_movel(codigos_raw) else ''
