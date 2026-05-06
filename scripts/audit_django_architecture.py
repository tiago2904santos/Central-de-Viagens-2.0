from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PY_RULES = [
    ("query_direta_view", ("views.py", ".objects.filter(")),
    ("query_direta_view", ("views.py", ".objects.get(")),
    ("query_direta_view", ("views.py", ".objects.all(")),
    ("get_object_or_404_em_view", ("views.py", "get_object_or_404(")),
    ("html_em_presenter", ("presenters.py", "mark_safe")),
    ("html_em_presenter", ("presenters.py", "<")),
    ("protectederror_fora_service", (".py", "ProtectedError")),
    ("atomic_em_view", ("views.py", "transaction.atomic")),
]

HTML_RULES = [
    ("href_falso_template", 'href="#"'),
    ("javascript_void_template", "javascript:void"),
    ("updated_at_exibido", "updated_at"),
    ("atualizado_em_exibido", "Atualizado em"),
    ("css_inline_template", 'style="'),
    ("script_inline_template", "<script>"),
    ("onclick_inline_template", "onclick="),
    ("onchange_inline_template", "onchange="),
    ("oninput_inline_template", "oninput="),
]

ALLOWLIST = {
    "core/deletion.py": {"protectederror_fora_service"},
    "scripts/audit_django_architecture.py": {"protectederror_fora_service"},
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_allowed(path: str, rule_name: str) -> bool:
    return rule_name in ALLOWLIST.get(path, set())


def iter_files(ext: str):
    for path in ROOT.rglob(f"*{ext}"):
        if ".venv" in path.parts or ".git" in path.parts or "legacy" in path.parts:
            continue
        if path.is_file():
            yield path


def audit_python():
    findings = []
    for path in iter_files(".py"):
        path_rel = rel(path)
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            for rule_name, (filename_suffix, needle) in PY_RULES:
                if not path_rel.endswith(filename_suffix):
                    continue
                if rule_name == "protectederror_fora_service" and "/services" in path_rel:
                    continue
                if is_allowed(path_rel, rule_name):
                    continue
                if needle in line:
                    findings.append((path_rel, idx, rule_name, line.strip()))
    return findings


def audit_templates():
    findings = []
    for path in iter_files(".html"):
        path_rel = rel(path)
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            for rule_name, needle in HTML_RULES:
                if is_allowed(path_rel, rule_name):
                    continue
                if needle in line:
                    findings.append((path_rel, idx, rule_name, line.strip()))
    return findings


def main():
    findings = [*audit_python(), *audit_templates()]
    print("== Auditoria Django Arquitetura (suspeitas) ==")
    if not findings:
        print("Nenhuma suspeita encontrada.")
        return
    for file_path, line_no, rule_name, line in findings:
        print(f"{file_path}:{line_no} [{rule_name}] {line}")
    print(f"Total de suspeitas: {len(findings)}")


if __name__ == "__main__":
    main()
