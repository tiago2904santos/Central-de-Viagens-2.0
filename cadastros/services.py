from django.db import transaction

from core.deletion import DelecaoProtegidaError
from core.deletion import excluir_com_protecao
from core.normalizers import normalize_spaces
from core.normalizers import remove_accents
from .models import AssinaturaConfiguracao
from .models import Cargo
from .models import Cidade
from .models import Combustivel
from .models import Estado


class CadastroVinculadoError(Exception):
    pass


def _normalize_for_match(value):
    return remove_accents(normalize_spaces(value).lower())


def _traduz_delecao_protegida(instance):
    try:
        excluir_com_protecao(instance)
    except DelecaoProtegidaError as exc:
        raise CadastroVinculadoError from exc


def resolver_cidade_sede_por_endereco(uf, cidade_endereco):
    uf = (uf or "").strip().upper()
    cidade_nome = (cidade_endereco or "").strip()
    if not uf or not cidade_nome:
        return None

    estado = Estado.objects.filter(sigla=uf).first()
    if not estado:
        return None

    alvo = _normalize_for_match(cidade_nome)
    for cidade in Cidade.objects.filter(estado=estado).only("id", "nome", "estado_id"):
        if _normalize_for_match(cidade.nome) == alvo:
            return cidade
    return None


@transaction.atomic
def salvar_configuracao_sistema(form):
    configuracao = form.save(commit=False)
    if "assinatura_planos_trabalho" in form.cleaned_data:
        configuracao.coordenador_adm_plano_trabalho = form.cleaned_data.get(
            "assinatura_planos_trabalho"
        )

    cidade_ok = False
    if "uf" in form.cleaned_data:
        uf = form.cleaned_data.get("uf") or ""
        cidade_txt = form.cleaned_data.get("cidade_endereco") or ""
        if uf and cidade_txt:
            cidade_sede = resolver_cidade_sede_por_endereco(uf, cidade_txt)
            configuracao.cidade_sede_padrao = cidade_sede
            cidade_ok = cidade_sede is not None
        else:
            configuracao.cidade_sede_padrao = None

    configuracao.save()
    form.save_m2m()
    salvar_assinaturas_configuracao(configuracao, form.cleaned_data)
    return configuracao, cidade_ok


def salvar_assinaturas_configuracao(configuracao, cleaned_data):
    mapping = [
        ("assinatura_oficio", AssinaturaConfiguracao.TIPO_OFICIO, 1),
        ("assinatura_justificativas", AssinaturaConfiguracao.TIPO_JUSTIFICATIVA, 1),
        ("assinatura_planos_trabalho", AssinaturaConfiguracao.TIPO_PLANO_TRABALHO, 1),
        ("assinatura_ordens_servico", AssinaturaConfiguracao.TIPO_ORDEM_SERVICO, 1),
    ]
    for field_name, tipo, ordem in mapping:
        servidor = cleaned_data.get(field_name)
        AssinaturaConfiguracao.objects.update_or_create(
            configuracao=configuracao,
            tipo=tipo,
            ordem=ordem,
            defaults={"servidor": servidor, "ativo": bool(servidor)},
        )

    AssinaturaConfiguracao.objects.filter(
        configuracao=configuracao,
        tipo=AssinaturaConfiguracao.TIPO_OFICIO,
        ordem=2,
    ).delete()
    AssinaturaConfiguracao.objects.filter(
        configuracao=configuracao,
        tipo=AssinaturaConfiguracao.TIPO_TERMO_AUTORIZACAO,
    ).delete()


@transaction.atomic
def definir_cargo_padrao(cargo: Cargo) -> Cargo:
    """Marca o cargo como padrão; o `save()` do modelo garante um único padrão."""
    cargo.is_padrao = True
    cargo.save()
    return cargo


@transaction.atomic
def definir_combustivel_padrao(combustivel: Combustivel) -> Combustivel:
    """Marca o combustível como padrão; o `save()` do modelo garante um único padrão."""
    combustivel.is_padrao = True
    combustivel.save()
    return combustivel


def criar_estado(form):
    return form.save()


def atualizar_estado(instance, form):
    return form.save()


def excluir_estado(instance):
    _traduz_delecao_protegida(instance)


def criar_unidade(form):
    return form.save()


def atualizar_unidade(instance, form):
    return form.save()


def excluir_unidade(instance):
    _traduz_delecao_protegida(instance)


def criar_cidade(form):
    return form.save()


def atualizar_cidade(instance, form):
    return form.save()


def excluir_cidade(instance):
    _traduz_delecao_protegida(instance)


def criar_cargo(form):
    return form.save()


def atualizar_cargo(instance, form):
    return form.save()


def excluir_cargo(instance):
    _traduz_delecao_protegida(instance)


def criar_combustivel(form):
    return form.save()


def atualizar_combustivel(instance, form):
    return form.save()


def excluir_combustivel(instance):
    _traduz_delecao_protegida(instance)


def criar_servidor(form):
    return form.save()


def atualizar_servidor(instance, form):
    return form.save()


def excluir_servidor(instance):
    _traduz_delecao_protegida(instance)


def criar_viatura(form):
    return form.save()


def atualizar_viatura(instance, form):
    return form.save()


def excluir_viatura(instance):
    _traduz_delecao_protegida(instance)
