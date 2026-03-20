"""
Regras de negócio do Plano de Trabalho: atividades, metas, unidade móvel.
Nomes técnicos sem acento: atividades_formatada, metas_formatada, etc.
"""
from __future__ import annotations

# Ordem oficial das atividades (código, nome, meta)
ATIVIDADES_CATALOGO = [
    {
        'codigo': 'CIN',
        'nome': 'Confecção da Carteira de Identidade Nacional (CIN)',
        'meta': (
            'Ampliar o acesso ao documento oficial de identificação civil, garantindo '
            'cidadania e inclusão social à população atendida.'
        ),
    },
    {
        'codigo': 'BO',
        'nome': 'Registro de Boletins de Ocorrência',
        'meta': (
            'Possibilitar o atendimento imediato de demandas policiais, promovendo '
            'orientação e formalização de ocorrências no próprio evento.'
        ),
    },
    {
        'codigo': 'AAC',
        'nome': 'Emissão de Atestado de Antecedentes Criminais',
        'meta': (
            'Facilitar a obtenção do documento, contribuindo para fins trabalhistas e '
            'demais necessidades legais dos cidadãos.'
        ),
    },
    {
        'codigo': 'PALESTRAS',
        'nome': 'Palestras e orientações preventivas',
        'meta': (
            'Desenvolver ações educativas voltadas à prevenção de crimes, conscientização '
            'sobre segurança pública e fortalecimento do vínculo comunitário.'
        ),
    },
    {
        'codigo': 'LUDICO',
        'nome': 'Atividades lúdicas e educativas para crianças',
        'meta': (
            'Promover aproximação institucional de forma didática, incentivando a cultura '
            'de respeito às leis e à cidadania desde a infância.'
        ),
    },
    {
        'codigo': 'NOC',
        'nome': 'Apresentação do trabalho do Núcleo de Operações com Cães (NOC)',
        'meta': (
            'Demonstrar as atividades operacionais desenvolvidas pela unidade especializada '
            'da Polícia Civil do Paraná, evidenciando técnicas e capacidades institucionais.'
        ),
    },
    {
        'codigo': 'TATICO',
        'nome': 'Exposição de material tático',
        'meta': (
            'Apresentar equipamentos utilizados nas atividades policiais, proporcionando '
            'transparência e conhecimento sobre os recursos empregados pela instituição.'
        ),
    },
    {
        'codigo': 'PAPILOSCOPIA',
        'nome': 'Exposição da atividade de perícia papiloscópica',
        'meta': (
            'Demonstrar os procedimentos técnicos de identificação humana, ressaltando a '
            'importância da papiloscopia na investigação criminal e na identificação civil.'
        ),
    },
    {
        'codigo': 'VIATURAS',
        'nome': 'Exposição de viaturas antigas e modernas',
        'meta': (
            'Apresentar a evolução histórica e tecnológica dos veículos operacionais da instituição.'
        ),
    },
    {
        'codigo': 'BANDA',
        'nome': 'Apresentação da banda institucional',
        'meta': (
            'Fortalecer a integração com a comunidade por meio de atividade cultural '
            'representativa da instituição.'
        ),
    },
    {
        'codigo': 'UNIDADE_MOVEL',
        'nome': 'Unidade móvel (ônibus ou caminhão)',
        'meta': (
            'Viabilizar a prestação descentralizada dos serviços acima descritos, assegurando '
            'estrutura adequada para atendimento ao público.'
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
    return [item for item in ATIVIDADES_CATALOGO if item['codigo'] in codigos_set]


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
    linhas = [
        (
            'Recursos operacionais, materiais de atendimento, equipamentos de apoio '
            'e suporte logístico compatíveis com as atividades selecionadas.'
        ),
        f'Escopo previsto: {atividades}.',
    ]
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
