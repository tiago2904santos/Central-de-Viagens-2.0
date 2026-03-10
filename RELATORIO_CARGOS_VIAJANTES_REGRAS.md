# Relatório — Ajustes Cargos e Viajantes (regras novas)

## Resumo

Implementadas as regras: nomes em MAIÚSCULO (viajante e cargo), Cargo sem ativo/inativo e com opção "Padrão" (único), acesso a cargos apenas por botão na lista de viajantes, cargo padrão pré-selecionado no cadastro de viajante. Máscaras (CPF/telefone/RG) mantidas.

---

## 1. Migrations geradas

- **Arquivo:** `cadastros/migrations/0010_cargo_is_padrao_remove_ativo.py`
- **Operações:**
  - `AddField`: `Cargo.is_padrao` (BooleanField, default=False, verbose_name='Padrão')
  - `RemoveField`: `Cargo.ativo`
- **Comando:** `python manage.py migrate cadastros`

---

## 2. Garantia de “apenas 1 padrão”

- **No model (`cadastros/models.py`):** No `Cargo.save()`, após `super().save()`, se `self.is_padrao` for `True`, é executado:
  - `Cargo.objects.exclude(pk=self.pk).update(is_padrao=False)`
  Assim, só o cargo atual permanece como padrão.
- **Na view “Definir como padrão”:** Em `cargo_definir_padrao` (POST), antes de salvar o cargo escolhido como padrão, é feito:
  - `Cargo.objects.exclude(pk=pk).update(is_padrao=False)`
  - Depois `obj.is_padrao = True` e `obj.save(update_fields=['is_padrao'])`.
- **No form:** Ao marcar “Definir como padrão” e salvar, o `save()` do model já desmarca os demais.

---

## 3. Botão “Gerenciar cargos” na lista de viajantes

- **Onde:** `templates/cadastros/viajantes/lista.html`
- **Alteração:** No header da página (ao lado de “Cadastrar”), foi adicionado o botão **“Gerenciar cargos”** com link para `{% url 'cadastros:cargo-lista' %}` (rota `/cadastros/cargos/`).
- **Trecho:**  
  `<a href="{% url 'cadastros:cargo-lista' %}" class="btn btn-outline-secondary">Gerenciar cargos</a>`

---

## 4. Botão “Voltar para viajantes” na tela de cargos

- **Onde:** `templates/cadastros/cargos/lista.html`
- **Alteração:** No header da lista de cargos, foi adicionado o botão **“Voltar para viajantes”** com link para `{% url 'cadastros:viajante-lista' %}` (rota `/cadastros/viajantes/`).

---

## 5. Cargo padrão no cadastro de viajante

- **Onde:** `cadastros/forms.py`, `ViajanteForm.__init__`
- **Lógica:** Se for novo viajante (`not self.instance.pk`) ou não tiver cargo (`self.instance.cargo_id is None`) e não for submissão POST (`not self.data`), o valor inicial do campo `cargo` é definido com o cargo padrão:
  - `padrao = Cargo.objects.filter(is_padrao=True).first()`
  - Se existir, `self.initial['cargo'] = padrao.pk`
- **Efeito:** Ao abrir o formulário de **cadastrar** viajante (ou editar um que ainda não tem cargo), o select de cargo já vem com o cargo padrão selecionado.

---

## 6. Menu lateral — Cargos removido

- **Onde:** `core/navigation.py`
- **Alteração:** O item de menu **“Cargos”** foi removido da seção Cadastros. Permanecem apenas Viajantes, Veículos e Configurações. O acesso a Cargos é somente pelo botão “Gerenciar cargos” na lista de viajantes.

---

## 7. Nomes em MAIÚSCULO

- **Cargo (nome):**
  - **Backend:** `Cargo.save()` normaliza com `' '.join(self.nome.strip().upper().split())`. `CargoForm.clean_nome` retorna o nome em maiúsculo e sem espaços duplos.
  - **Frontend:** Em `templates/cadastros/cargos/form.html`, script em `id_nome` aplica `toUpperCase()` no `input` e no carregamento da página.
- **Viajante (nome):**
  - **Backend:** `Viajante.save()` e `ViajanteForm.clean_nome` já mantêm nome em maiúsculo.
  - **Frontend:** Em `templates/cadastros/viajantes/form.html`, o campo nome já tinha JS para maiúsculo; mantido.

---

## 8. Máscaras (CPF / telefone / RG)

- **Regra:** Não foi alterada: ao abrir/editar e na lista os valores aparecem mascarados; no banco ficam apenas dígitos (e “NAO POSSUI RG” quando aplicável).
- **Arquivos:** `cadastros/forms.py` (clean e initial), `cadastros/views/viajantes.py` (rg_display, cpf_display, telefone_display), `cadastros/utils/masks.py` e templates do viajante continuam como antes.

---

## 9. Rotas e funcionalidades de Cargos

| Rota | Método | Descrição |
|------|--------|-----------|
| `/cadastros/cargos/` | GET | Lista de cargos (Nome, Padrão, Ações) |
| `/cadastros/cargos/cadastrar/` | GET, POST | Cadastro de cargo |
| `/cadastros/cargos/<pk>/editar/` | GET, POST | Edição de cargo |
| `/cadastros/cargos/<pk>/excluir/` | GET, POST | Confirmação e exclusão (bloqueada se houver viajante usando) |
| `/cadastros/cargos/<pk>/definir-padrao/` | POST | Define o cargo como padrão e desmarca os demais |

---

## 10. Como testar manualmente

1. **Login:** Acesse o sistema e faça login.
2. **Viajantes:** Vá em Cadastros → Viajantes. Confirme o botão **“Gerenciar cargos”** no topo.
3. **Cargos:** Clique em “Gerenciar cargos”. Deve abrir a lista de cargos. Confirme o botão **“Voltar para viajantes”**.
4. **Cargo padrão:** Cadastre um cargo (ex.: “ANALISTA”) e marque “Definir como padrão”. Salve. Cadastre outro com “Definir como padrão”. Salve e confira que só o último fica com badge “Padrão”.
5. **Definir como padrão na lista:** Na lista de cargos, use “Definir como padrão” em outro cargo. Confirme que apenas esse fica como padrão.
6. **Nome cargo em maiúsculo:** No form de cargo, digite “coordenador” e salve; na lista deve aparecer “COORDENADOR”.
7. **Viajante novo com cargo padrão:** Cadastros → Viajantes → Cadastrar. O select “Cargo” deve vir com o cargo padrão já selecionado.
8. **Exclusão bloqueada:** Tente excluir um cargo que esteja em uso por algum viajante; deve aparecer mensagem de impedimento.
9. **Máscaras:** Na lista e no formulário de viajante, confira CPF, telefone e RG mascarados; ao salvar, no banco devem estar só dígitos (e “NAO POSSUI RG” quando for o caso).

---

## 11. Checklist de aceite

| Item | Status |
|------|--------|
| Nomes (viajante e cargo) em MAIÚSCULO no input e no banco | OK |
| Cargo sem campo ativo/inativo | OK |
| Cargo com “Padrão”; só um padrão por vez (form e botão “Definir como padrão”) | OK |
| Cargos fora do menu lateral | OK |
| Botão “Gerenciar cargos” na lista de viajantes → lista de cargos | OK |
| Botão “Voltar para viajantes” na lista de cargos | OK |
| Cargo padrão pré-selecionado ao cadastrar viajante | OK |
| Exclusão de cargo bloqueada se usado por viajante | OK |
| Máscaras CPF/telefone/RG inalteradas | OK |
| Migração 0010 aplicada (is_padrao, remoção de ativo) | OK |
| Testes Cargo e Viajante passando (26 testes) | OK |

---

## 12. Arquivos alterados/criados

- `cadastros/models.py` — Cargo: ativo removido, is_padrao adicionado; save() com unicidade do padrão e normalização do nome.
- `cadastros/migrations/0010_cargo_is_padrao_remove_ativo.py` — Nova migração.
- `cadastros/forms.py` — CargoForm: campos `nome`, `is_padrao`; ViajanteForm: cargo padrão no initial e queryset sem filtro por ativo.
- `cadastros/views/cargos.py` — View `cargo_definir_padrao` (POST).
- `cadastros/views/__init__.py` — Export de `cargo_definir_padrao`.
- `cadastros/urls.py` — Rota `cargos/<int:pk>/definir-padrao/`.
- `cadastros/admin.py` — CargoAdmin: list_display e list_filter com `is_padrao` em vez de `ativo`.
- `core/navigation.py` — Remoção do item de menu “Cargos”.
- `templates/cadastros/cargos/lista.html` — Colunas Nome e Padrão; ações Editar, Excluir, “Definir como padrão”; botão “Voltar para viajantes”.
- `templates/cadastros/cargos/form.html` — Campos nome e “Definir como padrão”; JS para nome em maiúsculo.
- `templates/cadastros/viajantes/lista.html` — Botão “Gerenciar cargos”.
- `cadastros/tests/test_cadastros.py` — Cargo: testes com is_padrao, teste de padrão único e de “Definir como padrão”; Viajante: teste de cargo padrão pré-selecionado no formulário de cadastro.
