from types import SimpleNamespace

from django.db import transaction
from django.db.models.deletion import ProtectedError

from cadastros.models import ConfiguracaoSistema

from . import roteiro_logic
from .models import Roteiro


def obter_initial_roteiro():
    initial = {}
    config = ConfiguracaoSistema.get_singleton()
    if getattr(config, "cidade_sede_padrao", None):
        initial["origem_cidade"] = config.cidade_sede_padrao_id
        if config.cidade_sede_padrao.estado_id:
            initial["origem_estado"] = config.cidade_sede_padrao.estado_id
    return initial


def montar_contexto_formulario(form, instance=None, request=None):
    roteiro_logic._setup_roteiro_querysets(form, request, instance)
    route_options, route_state_map = roteiro_logic._build_roteiro_avulso_route_options()
    return route_options, route_state_map


def construir_estado_get(initial=None, roteiro=None):
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


def validar_payload_roteiro(request, route_state_map, roteiro=None):
    step3_state = roteiro_logic._build_avulso_step3_state_from_post(
        request, route_state_map=route_state_map
    )
    fake = SimpleNamespace(evento_id=None, roteiro_evento_id=None, evento=None)
    validated = roteiro_logic._validate_step3_state(step3_state, oficio=fake)
    _, _, _, diarias_resultado = roteiro_logic._build_roteiro_diarias_from_request(
        request, roteiro=roteiro
    )
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


def montar_contexto_roteiro_form(*, evento, form, obj, destinos_atuais, trechos_list, step3_state, route_options):
    return roteiro_logic._build_roteiro_form_context(
        evento=evento,
        form=form,
        obj=obj,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=True,
        step3_state=step3_state,
        route_options=route_options,
    )
