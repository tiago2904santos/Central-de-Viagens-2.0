from types import SimpleNamespace

from django.db import transaction
from django.db.models.deletion import ProtectedError

from cadastros.models import ConfiguracaoSistema

from roteiros import roteiro_logic
from roteiros.models import Roteiro


def obter_initial_roteiro():
    initial = {}
    config = ConfiguracaoSistema.get_singleton()
    if getattr(config, "cidade_sede_padrao", None):
        initial["origem_cidade"] = config.cidade_sede_padrao_id
        if config.cidade_sede_padrao.estado_id:
            initial["origem_estado"] = config.cidade_sede_padrao.estado_id
    return initial


def preparar_querysets_formulario_roteiro(form, *, method, post, instance=None):
    """Limita-se a preencher querysets do form (sede); não monta contexto de template."""
    fake_request = SimpleNamespace(method=method.upper(), POST=post)
    roteiro_logic._setup_roteiro_querysets(form, fake_request, instance)


def carregar_opcoes_rotas_avulsas_salvas():
    """Lista opções de duplicação de roteiros avulsos e mapa de estado serializável (step3)."""
    return roteiro_logic._build_roteiro_avulso_route_options()


def preparar_estado_editor_roteiro_para_get(initial=None, roteiro=None):
    if roteiro:
        destinos_atuais = roteiro_logic._destinos_roteiro_para_template(roteiro) or [
            {"estado_id": None, "cidade_id": None, "cidade": None, "estado": None}
        ]
        destinos_list = [
            (d.get("estado_id"), d.get("cidade_id"))
            for d in destinos_atuais
            if d.get("estado_id") and d.get("cidade_id")
        ]
        trechos_list = roteiro_logic._estrutura_trechos(roteiro, destinos_list) if destinos_list else []
        step3_state = roteiro_logic._build_step3_state_from_roteiro_evento(roteiro)
        step3_state["roteiro_modo"] = "ROTEIRO_PROPRIO"
        return destinos_atuais, trechos_list, step3_state

    initial = initial or {}
    destinos_atuais = [{"estado_id": None, "cidade_id": None, "cidade": None, "estado": None}]
    trechos_list = []
    step3_state = roteiro_logic._build_step3_state_from_estrutura(
        trechos_list,
        [{"estado_id": None, "cidade_id": None}],
        initial.get("origem_estado"),
        initial.get("origem_cidade"),
        "",
    )
    step3_state["roteiro_modo"] = "ROTEIRO_PROPRIO"
    return destinos_atuais, trechos_list, step3_state


def normalizar_destinos_e_trechos_apos_erro_post(step3_state):
    """Após POST inválido, reconstrói listas exibidas no form a partir do step3 parseado."""
    destinos_atuais = [
        {
            "estado_id": item.get("estado_id"),
            "cidade_id": item.get("cidade_id"),
            "cidade": None,
            "estado": None,
        }
        for item in (step3_state.get("destinos_atuais") or [])
    ]
    if not destinos_atuais:
        destinos_atuais = [
            {"estado_id": None, "cidade_id": None, "cidade": None, "estado": None}
        ]
    trechos_list = step3_state.get("trechos", [])
    return destinos_atuais, trechos_list


def validar_submissao_editor_roteiro(post, route_state_map, roteiro=None):
    """Validação e cálculo de diárias a partir do POST; sem render nem redirect."""
    fake_request = SimpleNamespace(method="POST", POST=post)
    step3_state = roteiro_logic._build_avulso_step3_state_from_post(
        fake_request, route_state_map=route_state_map
    )
    fake_oficio = SimpleNamespace(evento_id=None, roteiro_evento_id=None, evento=None)
    validated = roteiro_logic._validate_step3_state(step3_state, oficio=fake_oficio)
    try:
        _, _, _, diarias_resultado = roteiro_logic._build_roteiro_diarias_from_request(
            fake_request, roteiro=roteiro
        )
    except ValueError as exc:
        mensagem = str(exc) or "Revise os dados de datas e horas para calcular as diárias."
        errors = list(validated.get("errors") or [])
        if mensagem not in errors:
            errors.append(mensagem)
        validated["ok"] = False
        validated["errors"] = errors
        diarias_resultado = None
    return step3_state, validated, diarias_resultado


@transaction.atomic
def criar_roteiro(form, step3_state, validated, diarias_resultado):
    roteiro = form.save(commit=False)
    roteiro.tipo = Roteiro.TIPO_AVULSO
    roteiro.origem_estado = validated.get("sede_estado")
    roteiro.origem_cidade = validated.get("sede_cidade")
    roteiro.save()
    roteiro_logic._salvar_roteiro_avulso_from_step3_state(
        roteiro, step3_state, validated, diarias_resultado=diarias_resultado
    )
    return roteiro


@transaction.atomic
def atualizar_roteiro(instance, form, step3_state, validated, diarias_resultado):
    roteiro = form.save(commit=False)
    roteiro.tipo = instance.tipo or Roteiro.TIPO_AVULSO
    roteiro.origem_estado = validated.get("sede_estado")
    roteiro.origem_cidade = validated.get("sede_cidade")
    roteiro.save()
    roteiro_logic._salvar_roteiro_avulso_from_step3_state(
        roteiro, step3_state, validated, diarias_resultado=diarias_resultado
    )
    return roteiro


@transaction.atomic
def excluir_roteiro(instance):
    try:
        instance.delete()
    except ProtectedError:
        return False
    return True
