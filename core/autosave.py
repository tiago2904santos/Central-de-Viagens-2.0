import json
from dataclasses import dataclass

from django.http import JsonResponse
from django.utils import timezone


class AutosavePayloadError(ValueError):
    """Erro de contrato do payload de autosave."""


@dataclass
class AutosavePayload:
    object_id: str
    form_id: str
    model: str
    dirty_fields: list
    fields: dict
    snapshots: dict


def parse_autosave_payload(request, *, expected_model=None):
    if request.method != "POST":
        raise AutosavePayloadError("Método inválido para autosave.")
    try:
        raw = json.loads(request.body or "{}")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AutosavePayloadError("Payload JSON inválido.") from exc

    if not isinstance(raw, dict):
        raise AutosavePayloadError("Payload JSON inválido.")

    model = str(raw.get("model") or "").strip()
    if expected_model and model != expected_model:
        raise AutosavePayloadError("Modelo de autosave inválido para este endpoint.")

    dirty_fields = raw.get("dirty_fields") or []
    if not isinstance(dirty_fields, list):
        raise AutosavePayloadError("dirty_fields deve ser uma lista.")
    dirty_fields = [str(item).strip() for item in dirty_fields if str(item).strip()]

    fields = raw.get("fields") or {}
    snapshots = raw.get("snapshots") or {}
    if not isinstance(fields, dict) or not isinstance(snapshots, dict):
        raise AutosavePayloadError("Campos de autosave inválidos.")

    return AutosavePayload(
        object_id=str(raw.get("object_id") or "").strip(),
        form_id=str(raw.get("form_id") or "").strip(),
        model=model,
        dirty_fields=dirty_fields,
        fields=fields,
        snapshots=snapshots,
    )


def filter_allowed_fields(payload_fields, dirty_fields, allowed_fields):
    safe = {}
    dirty = set(dirty_fields or [])
    for key, value in (payload_fields or {}).items():
        if key not in allowed_fields:
            continue
        if key not in dirty:
            continue
        safe[key] = value
    return safe


def autosave_json_response(*, ok, object_id=None, created=False, message="", errors=None, version=0):
    if ok:
        now = timezone.localtime()
        return JsonResponse(
            {
                "ok": True,
                "object_id": object_id,
                "created": bool(created),
                "saved_at": now.isoformat(),
                "saved_at_display": now.strftime("%d/%m/%Y %H:%M"),
                "version": int(version or 0),
            }
        )
    return JsonResponse(
        {
            "ok": False,
            "errors": errors or {},
            "message": message or "Não foi possível salvar automaticamente.",
        },
        status=400,
    )
