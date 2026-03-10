# Relatório: Viajantes e Cargos — máscaras, nome maiúsculo, bug RG, lista

## Resumo

- **Nome:** Salvo e exibido em MAIÚSCULO (backend + frontend).
- **RG:** Corrigido bug que limpava o valor ao carregar a edição; RG persiste e aparece mascarado no form e na lista.
- **CPF/Telefone na lista:** Sempre mascarados (view define `cpf_display` e `telefone_display`).
- **CPF no form:** Máscara progressiva durante a digitação e no carregamento (DOMContentLoaded).
- **Cargos:** CRUD ativo (rotas, views, forms, templates); exclusão bloqueada quando o cargo está em uso.
- **Menu:** Cargos e Viajantes com Lista/Cadastrar habilitados.

---

## 1. Arquivos alterados/criados

| Arquivo | Alteração |
|--------|-----------|
| `cadastros/forms.py` | `clean_nome`: retorna `value.upper()` após strip e redução de espaços. |
| `cadastros/models.py` | `Viajante.save()`: nome com `.upper()` ao normalizar. |
| `cadastros/utils/masks.py` | `only_digits` movido para o topo; adicionados `format_cpf` e `format_telefone`. |
| `cadastros/views/viajantes.py` | `_cpf_display`, `_telefone_display`; na lista, preenchimento de `obj.cpf_display` e `obj.telefone_display`. |
| `templates/cadastros/viajantes/lista.html` | Coluna Telefone; uso de `obj.cpf_display` e `obj.telefone_display`; colspan 6. |
| `templates/cadastros/viajantes/form.html` | **Bug RG:** `toggleRg(clearValue)`: no load chama `toggleRg(false)` (não limpa); no `change` chama `toggleRg(true)` (limpa ao desmarcar). Nome: `input` + `DOMContentLoaded` aplicam `.toUpperCase()`. CPF: `formatCpfProgressivo(d)` e máscara progressiva no `input` (até 3, 4–6, 7–9, 10–11 dígitos). |
| `cadastros/templatetags/masks.py` | **Novo.** Filtros `cpf_mask`, `rg_mask`, `phone_mask` para uso em templates. |
| `cadastros/tests/test_cadastros.py` | Nome em maiúsculo nos asserts; testes para lista com CPF/telefone mascarados e nome salvo em uppercase. |

---

## 2. Causa do bug do RG “não persistir” / vir vazio ao editar

**Causa:** No template do form de viajantes, o JS da opção “Não possui RG” chama `toggleRg()` no carregamento da página. Quando `sem_rg` está **desmarcado**, o código fazia `rgInput.value = ''`, apagando o valor que o backend tinha colocado no campo (ex.: `12.345.678-9`). Assim, ao abrir a edição, o usuário via o RG vazio mesmo estando salvo no banco.

**Correção:**  
- `toggleRg(clearValue)`: ao **habilitar** o campo (sem_rg desmarcado), só limpa o valor se `clearValue === true`.  
- No **load** chama-se `toggleRg(false)`: não limpa, mantém o valor vindo do servidor.  
- No evento **change** do checkbox chama-se `toggleRg(true)`: ao desmarcar “Não possui RG” o campo é limpo para o usuário digitar de novo.

Com isso, o RG continua sendo enviado no POST (campo habilitado), o `clean_rg` normaliza e grava só dígitos (ou "NAO POSSUI RG"), e ao reabrir a edição o valor mascarado aparece corretamente.

---

## 3. Máscara progressiva do CPF (JS)

No form de viajantes, o CPF passou a usar máscara progressiva no evento `input`:

- Função `formatCpfProgressivo(d)` (apenas dígitos):
  - até 3: `"123"`
  - 4–6: `"123.4"`, `"123.45"`, `"123.456"`
  - 7–9: `"123.456.7"`, … , `"123.456.789"`
  - 10–11: `"123.456.789-0"`, `"123.456.789-01"`

- No `input` do CPF: `onlyDigits(this.value).slice(0, 11)` e aplicação de `formatCpfProgressivo(d)` a cada digitação.
- No `DOMContentLoaded`: se o campo já tiver valor (edição), aplica `formatCpf` completo (11 dígitos) para exibir `000.000.000-00`.

Assim a máscara aparece desde o início da digitação e também ao carregar a página.

---

## 4. Rotas e telas de Cargos (confirmado)

- **Rotas** (`cadastros/urls.py`):  
  `GET /cadastros/cargos/` (lista),  
  `GET+POST /cadastros/cargos/cadastrar/`,  
  `GET+POST /cadastros/cargos/<pk>/editar/`,  
  `GET+POST /cadastros/cargos/<pk>/excluir/` (POST para excluir; se houver viajante com o cargo, redireciona com mensagem de erro).

- **Views:** `cadastros/views/cargos.py` (lista, cadastrar, editar, excluir).
- **Form:** `CargoForm` em `cadastros/forms.py` (nome em UPPER, validação de duplicidade).
- **Templates:** `cadastros/cargos/lista.html`, `form.html`, `excluir_confirm.html`.
- **Menu:** Cargos e Viajantes com subitens Lista e Cadastrar, `enabled=True`, apontando para essas rotas.

---

## 5. Como testar manualmente (passo a passo)

1. **Nome em maiúsculo**  
   Cadastros → Viajantes → Cadastrar. Nome: "Fulano Silva". Salvar. Ver na lista e ao editar: "FULANO SILVA". Digitar em minúsculo e conferir que o campo vai para maiúsculo.

2. **RG persiste e aparece ao editar**  
   Cadastrar viajante com RG "12.345.678-9", sem marcar “Não possui RG”. Salvar. Abrir a lista: RG "12.345.678-9". Clicar em Editar: campo RG deve vir preenchido com "12.345.678-9". Salvar de novo e editar outra vez: valor mantido.

3. **CPF na lista e no form**  
   Cadastrar com CPF completo. Na lista, conferir "000.000.000-00". Ao cadastrar/editar, digitar o CPF e conferir máscara progressiva (pontos e hífen); recarregar a página de edição e conferir CPF mascarado.

4. **Telefone na lista**  
   Viajante com telefone 10 ou 11 dígitos. Na lista, conferir "(XX) XXXX-XXXX" ou "(XX) XXXXX-XXXX". Vazio deve aparecer como "—".

5. **“Não possui RG”**  
   Marcar “Não possui RG”, salvar. Na lista: "NÃO POSSUI RG". Editar: checkbox marcada, campo RG desabilitado com "NÃO POSSUI RG". Desmarcar: campo habilitado e limpo para digitar.

6. **Cargos**  
   Cadastros → Cargos → Lista / Cadastrar. Criar cargo "ANALISTA", editar, excluir (cargo sem viajante). Criar cargo, associar a um viajante, tentar excluir o cargo: deve aparecer mensagem de impedimento e o cargo permanecer.

---

## 6. Checklist de aceite

| Item | Status |
|------|--------|
| Campos com máscara (CPF, telefone, RG) sempre mascarados ao abrir/editar e na lista | OK |
| Persistência: CPF/telefone/RG só dígitos (exceto "NAO POSSUI RG") | OK |
| Nome travado em maiúsculo no input e salvo em maiúsculo | OK |
| RG persiste e aparece mascarado no GET editar | OK |
| Nenhum JS limpando RG antes do submit (apenas ao desmarcar sem_rg) | OK |
| CPF na lista mascarado (XXX.XXX.XXX-XX) | OK |
| Telefone na lista mascarado; vazio como "—" | OK |
| CPF no form com máscara progressiva e no carregamento | OK |
| Cargos: rotas, views, forms, templates e exclusão bloqueada quando em uso | OK |
| Menu Cargos e Viajantes com Lista/Cadastrar habilitados | OK |
| Testes: RG, CPF/telefone na lista, nome uppercase, CRUD cargos | OK |
