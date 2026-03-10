# Relatório — Viajantes: exclusão real e remoção do campo ativo

## Resumo

- Toggle ativo/desativar removido; implementada exclusão real (DELETE) com página de confirmação.
- Campo `ativo` removido do model `Viajante`; todos os viajantes passam a ser considerados “sempre ativos”.
- Formulário: removidos checkboxes Ativo e ASCOM; ASCOM passou a ser select Sim/Não.
- Lista: removidos filtro e colunas Situação e ASCOM; mantidos busca e filtro ASCOM; ações Editar e Excluir.

---

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `cadastros/models.py` | Removido campo `ativo` do model `Viajante`. |
| `cadastros/migrations/0006_remove_viajante_ativo.py` | Nova migration: `RemoveField(ativo)` em Viajante. |
| `cadastros/forms.py` | ViajanteForm: removido `ativo`; `is_ascom` como `TypedChoiceField` (Sim/Não); `_viajantes_queryset()` passa a usar `Viajante.objects.all().order_by('nome')`. |
| `cadastros/views/viajantes.py` | Removidos filtro por `ativo` e view `viajante_desativar`; adicionada `viajante_excluir` (GET → confirmação, POST → delete + redirect + message). |
| `cadastros/views/__init__.py` | Export de `viajante_desativar` trocado por `viajante_excluir`. |
| `cadastros/urls.py` | Rota `desativar` trocada por `excluir`. |
| `cadastros/admin.py` | ViajanteAdmin: removidos `ativo` de list_display, list_filter e list_editable. |
| `templates/cadastros/viajantes/lista.html` | Removidos filtro “Situação” e colunas ASCOM e Situação; botão Desativar/Ativar trocado por link “Excluir” para página de confirmação. |
| `templates/cadastros/viajantes/form.html` | Removidos blocos dos checkboxes Ativo e ASCOM; ASCOM exibido como select (label + `{{ form.is_ascom }}`). |
| `templates/cadastros/viajantes/excluir_confirm.html` | **Novo:** página de confirmação com texto e form POST para excluir (CSRF + botão Excluir/Cancelar). |
| `cadastros/tests/test_cadastros.py` | Removido `test_viajante_toggle_ativo`; adicionado `test_viajante_excluir`; em todos os `Viajante.objects.create` e payloads de form removido `ativo`; `is_ascom` em POST como `'1'`. |

---

## 2) Migrations criadas

- **`cadastros/migrations/0006_remove_viajante_ativo.py`**  
  - Operação: `migrations.RemoveField(model_name='viajante', name='ativo')`.  
  - Dependência: `0005_viajante_sem_rg_ajustes`.

---

## 3) Rotas

| Antes | Depois |
|-------|--------|
| `GET/POST /cadastros/viajantes/<pk>/desativar/` → `viajante-desativar` | Removida. |
| — | `GET /cadastros/viajantes/<pk>/excluir/` → página de confirmação (`viajante-excluir`). |
| — | `POST /cadastros/viajantes/<pk>/excluir/` → exclui viajante, redirect para lista + message success. |

- Nome da rota: `cadastros:viajante-excluir`.  
- View: `viajante_excluir` (com `@login_required`); POST usa CSRF (form no template).

---

## 4) Onde foram removidas referências a `ativo=True` (Viajante)

| Local | Ajuste |
|-------|--------|
| `cadastros/forms.py` | `_viajantes_queryset()`: `Viajante.objects.filter(ativo=True).order_by('nome')` → `Viajante.objects.all().order_by('nome')`. |
| `cadastros/views/viajantes.py` | Filtros por `request.GET.get('ativo')` e `qs.filter(ativo=...)` removidos; `form_filter` sem chave `ativo`. |
| `cadastros/admin.py` | ViajanteAdmin: removidos `ativo` de list_display, list_filter e list_editable. |
| `cadastros/tests/test_cadastros.py` | Todos os `Viajante.objects.create(..., ativo=True)` → `Viajante.objects.create(...)`; payloads de POST sem `'ativo': 'on'`. |

Não há outros usos de `Viajante.objects.filter(ativo=True)` no projeto; Configurações e AssinaturaConfiguracao usam `_viajantes_queryset()`, que agora lista todos os viajantes.

---

## 5) Configurações / Assinaturas

- **AssinaturaConfiguracao.viajante** segue com `on_delete=SET_NULL`. Ao excluir um viajante, os registros de assinatura que apontavam para ele ficam com `viajante=None` (não quebra Configurações).
- Selects de assinatura em Configurações passam a mostrar todos os viajantes (sem filtro por ativo), via `_viajantes_queryset()`.

---

## 6) Como testar manualmente

1. **Login** e acesse **Cadastros → Viajantes** (ou **Lista**).
2. **Cadastrar:** clique em “Cadastrar”, preencha Nome e Cargo, escolha ASCOM Sim ou Não no select, salve. O viajante deve aparecer na lista (sem coluna Situação/ASCOM; apenas Nome, Cargo, RG, CPF e Ações).
3. **Excluir:** na linha do viajante, clique em **Excluir**. Deve abrir a página de confirmação (“Deseja realmente excluir o viajante …?”). Clique em **Excluir**. Deve redirecionar para a lista com mensagem de sucesso e o viajante não deve mais aparecer.
4. **Configurações:** em **Cadastros → Configurações**, os selects de assinatura devem listar todos os viajantes cadastrados (sem filtro por ativo).
5. **Excluir viajante usado em assinatura:** cadastre um viajante, use-o em uma assinatura em Configurações, salve. Depois exclua o viajante. A tela de Configurações deve continuar abrindo; a assinatura que apontava para ele fica sem viajante (null).

---

## 7) Checklist de aceite

| Item | Status |
|------|--------|
| Toggle ativo/desativar removido | OK |
| Rota/view desativar removida | OK |
| GET/POST excluir com página de confirmação | OK |
| CSRF e login obrigatório na exclusão | OK |
| Campo `ativo` removido do model Viajante | OK |
| Migration RemoveField ativo aplicada | OK |
| Onde havia `ativo=True` em Viajante → `Viajante.objects.all()` (via _viajantes_queryset) | OK |
| Admin Viajante sem ativo | OK |
| Formulário sem checkbox Ativo | OK |
| Formulário com ASCOM como select Sim/Não | OK |
| Lista sem filtro Situação e sem colunas ASCOM/Situação | OK |
| Lista com busca e filtro ASCOM; ações Editar e Excluir | OK |
| Configurações e Assinaturas continuam funcionando | OK |
| Excluir viajante não quebra Configurações (SET_NULL) | OK |
| Teste de toggle removido; teste de exclusão adicionado | OK |
| Testes existentes (listagem, criação, edição) passando | OK |
