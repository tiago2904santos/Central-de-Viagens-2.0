from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from roteiros import roteiro_logic
from roteiros.models import Roteiro
from roteiros.services.roteiro_editor import _apply_saved_map_route_from_post


ROTEIRO_AUTOSAVE_FIELDS = {
    "origem_estado",
    "origem_cidade",
    "observacoes",
    "roteiro_modo",
    "roteiro_id",
    "bate_volta_diario_ativo",
}


def has_minimum_roteiro_content(fields, snapshots):
    observacoes = str((fields or {}).get("observacoes") or "").strip()
    origem_cidade = str((fields or {}).get("origem_cidade") or "").strip()
    origem_estado = str((fields or {}).get("origem_estado") or "").strip()
    state = (snapshots or {}).get("roteiro_state") or {}
    destinos = (state.get("destinos_atuais") or []) if isinstance(state, dict) else []
    trechos = (state.get("trechos") or []) if isinstance(state, dict) else []
    return bool(observacoes or origem_cidade or origem_estado or destinos or trechos)


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _persist_simple_fields(roteiro, clean_fields):
    update_fields = []
    if "origem_estado" in clean_fields:
        roteiro.origem_estado_id = _to_int(clean_fields.get("origem_estado"))
        update_fields.append("origem_estado")
    if "origem_cidade" in clean_fields:
        roteiro.origem_cidade_id = _to_int(clean_fields.get("origem_cidade"))
        update_fields.append("origem_cidade")
    if "observacoes" in clean_fields:
        roteiro.observacoes = str(clean_fields.get("observacoes") or "").strip().upper()
        update_fields.append("observacoes")
    if update_fields:
        roteiro.save(update_fields=[*update_fields, "updated_at"])


def _apply_map_snapshot(roteiro, snapshots):
    mapa = (snapshots or {}).get("mapa") or {}
    if not isinstance(mapa, dict):
        return
    payload = {
        "map_route_geometry_json": mapa.get("geometry_json") or "",
        "map_route_points_json": mapa.get("points_json") or "",
        "map_route_distance_km": mapa.get("distance_km") or "",
        "map_route_duration_minutes": mapa.get("duration_minutes") or "",
        "map_route_provider": mapa.get("provider") or "",
        "map_route_calculated_at": mapa.get("calculated_at") or "",
    }
    _apply_saved_map_route_from_post(roteiro, payload)


def _apply_diarias_snapshot(roteiro, snapshots):
    diarias = (snapshots or {}).get("diarias") or {}
    if not isinstance(diarias, dict):
        return
    qtd = str(diarias.get("quantidade_diarias") or "").strip()
    valor = str(diarias.get("valor_diarias") or "").strip()
    extenso = str(diarias.get("valor_diarias_extenso") or "").strip()
    if not qtd and not valor and not extenso:
        return
    roteiro.quantidade_diarias = qtd
    roteiro.valor_diarias_extenso = extenso
    if valor:
        try:
            roteiro.valor_diarias = Decimal(valor.replace(".", "").replace(",", "."))
        except (InvalidOperation, TypeError, ValueError):
            pass
    roteiro.save(update_fields=["quantidade_diarias", "valor_diarias", "valor_diarias_extenso", "updated_at"])


def _apply_step3_snapshot(roteiro, snapshots):
    state = (snapshots or {}).get("roteiro_state")
    if not isinstance(state, dict):
        return
    validated = roteiro_logic._validate_step3_state(state)
    if not validated.get("ok"):
        return
    roteiro_logic._salvar_roteiro_avulso_from_step3_state(roteiro, state, validated, diarias_resultado=None)


def apply_roteiro_autosave(roteiro, clean_fields, snapshots):
    _persist_simple_fields(roteiro, clean_fields)
    _apply_step3_snapshot(roteiro, snapshots)
    _apply_map_snapshot(roteiro, snapshots)
    _apply_diarias_snapshot(roteiro, snapshots)
    roteiro.refresh_from_db()
    version = int(datetime.timestamp(timezone.localtime(roteiro.updated_at)))
    return version


def build_roteiro_draft():
    roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)
    return roteiro
