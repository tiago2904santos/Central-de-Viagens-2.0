from decimal import Decimal, InvalidOperation


def valor_por_extenso_ptbr(valor):
    try:
        from num2words import num2words  # type: ignore
    except ImportError:
        return "(preencher manualmente)"

    try:
        if isinstance(valor, str):
            valor = valor.replace("R$", "").replace("r$", "")
            valor = valor.replace(" ", "").replace(".", "").replace(",", ".").strip()
            valor = Decimal(valor)
        else:
            valor = Decimal(valor)

        return num2words(valor, lang="pt_BR", to="currency")
    except (InvalidOperation, TypeError, ValueError):
        return "(preencher manualmente)"
    except Exception:
        return "(preencher manualmente)"
