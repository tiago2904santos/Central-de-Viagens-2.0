from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"

RULES = [
    ("href_falso", 'href="#"'),
    ("javascript_void", "javascript:void"),
    ("css_inline", 'style="'),
    ("script_inline", "<script>"),
    ("onclick_inline", "onclick="),
    ("onchange_inline", "onchange="),
    ("oninput_inline", "oninput="),
]

ALLOWLIST = {
    # "templates/exemplo.html": {"script_inline"},
}


def iter_templates():
    for path in TEMPLATES_DIR.rglob("*.html"):
        if path.is_file():
            yield path


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main():
    findings = []
    for path in iter_templates():
        text = path.read_text(encoding="utf-8")
        rel_path = rel(path)
        allowed = ALLOWLIST.get(rel_path, set())
        lines = text.splitlines()
        for idx, line in enumerate(lines, start=1):
            for rule_name, needle in RULES:
                if rule_name in allowed:
                    continue
                if needle in line:
                    findings.append((rel_path, idx, rule_name, line.strip()))

    print("== Auditoria Frontend (suspeitas) ==")
    if not findings:
        print("Nenhuma suspeita encontrada.")
        return
    for file_path, line_no, rule_name, line in findings:
        print(f"{file_path}:{line_no} [{rule_name}] {line}")
    print(f"Total de suspeitas: {len(findings)}")


if __name__ == "__main__":
    main()
