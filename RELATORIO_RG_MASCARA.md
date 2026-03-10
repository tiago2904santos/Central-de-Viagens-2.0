# Relatório: RG com máscara (igual CPF/telefone)

## Resumo

- RG passou a ser tratado como campo mascarado em todo o fluxo: formulário (criar/editar), lista de viajantes e persistência.
- No banco: RG é salvo **apenas com dígitos** (string), exceto quando `sem_rg=True`, em que se grava `"NÃO POSSUI RG"`.
- Formato da máscara: 7 dígitos → `1.234.567`; 8 → `12.345.678`; 9 → `12.345.678-9`.

---

## 1. Arquivos alterados

| Arquivo | Alteração |
|--------|-----------|
| `cadastros/forms.py` | Função `format_rg(digits)` (7/8/9 dígitos). Em `ViajanteForm.clean_rg`: se não for `sem_rg`, sanitiza com `re.sub(r'\D', '', value)` e retorna só dígitos (ou vazio). Em `__init__`: para edição, preenche `self.initial['rg']` com `format_rg(instance.rg)` quando for só dígitos, ou `''` quando for "NÃO POSSUI RG". |
| `cadastros/templatetags/__init__.py` | **Novo** (pacote templatetags). |
| `cadastros/templatetags/cadastros_extras.py` | **Novo.** Filtro `format_rg`: valor vazio → `'—'`; "NÃO POSSUI RG" → mantido; só dígitos → mesma regra de formatação (7/8/9). |
| `templates/cadastros/viajantes/form.html` | Campo RG: `value="{% firstof form.initial.rg form.instance.rg '' %}"`, placeholder "Ex.: 12.345.678-9". JS: `formatRg(val)` (7/8/9); máscara no `input` do RG (limite 9 dígitos); no `DOMContentLoaded` aplica `formatRg` ao valor atual do RG quando não estiver `sem_rg`. Comportamento de `sem_rg` (desabilitar e limpar) mantido. |
| `templates/cadastros/viajantes/lista.html` | `{% load cadastros_extras %}`. Coluna RG: se `sem_rg` ou `rg == "NÃO POSSUI RG"` → badge "NÃO POSSUI RG"; senão → `{{ obj.rg|format_rg }}` (nunca valor “cru”). |
| `cadastros/tests/test_cadastros.py` | `test_viajante_rg_salvo_como_digitos_editar_mostra_mascarado`: cria com `rg='12.345.678-9'`, confere banco `'123456789'` e GET editar com `'12.345.678-9'`. `test_viajante_lista_mostra_rg_mascarado`: viajante com `rg='123456789'`, lista deve conter `'12.345.678-9'`. `test_viajante_sem_rg_lista_mostra_nao_possui_rg`: sem_rg=True, lista exibe "NÃO POSSUI RG" e banco com "NÃO POSSUI RG". |

---

## 2. Onde foi implementado `format_rg`

- **Backend (Python):** `cadastros/forms.py` — função `format_rg(digits)`:
  - 7 dígitos: `X.XXX.XXX`
  - 8 dígitos: `XX.XXX.XXX`
  - 9 dígitos: `XX.XXX.XXX-X`
  - Outros: retorna o valor recebido.

- **Template (lista):** `cadastros/templatetags/cadastros_extras.py` — filtro `format_rg` com a mesma lógica para exibição na tabela (e tratamento de vazio e "NÃO POSSUI RG").

- **Frontend (formulário):** `templates/cadastros/viajantes/form.html` — função JS `formatRg(val)` com a mesma regra; usada no `input` (digitação) e no `DOMContentLoaded` (valor vindo do backend).

---

## 3. Regras de persistência e exibição

- **Salvar:**  
  - `sem_rg=True` → `rg = "NÃO POSSUI RG"`.  
  - `sem_rg=False` → RG sanitizado (só dígitos), gravado como string de dígitos; vazio permitido.

- **Editar (form):**  
  - Se `instance.rg` for só dígitos → campo do form com `initial['rg']` já formatado (máscara).  
  - Se for "NÃO POSSUI RG" → `initial['rg'] = ''`, checkbox "Não possui RG" marcado e campo RG desabilitado/limpo.

- **Lista:**  
  - "NÃO POSSUI RG" ou `sem_rg` → badge "NÃO POSSUI RG".  
  - RG com dígitos → exibido com `format_rg` (nunca valor cru).

---

## 4. Como testar manualmente

1. **Criar viajante com RG**  
   - Cadastros → Viajantes → Cadastrar.  
   - Preencher nome, cargo e RG (ex.: `12.345.678-9` ou só dígitos).  
   - Salvar.  
   - Conferir na lista: RG deve aparecer como `12.345.678-9`.  
   - Editar o mesmo viajante: campo RG deve abrir já com a máscara (e após F5 também).

2. **RG na lista**  
   - Incluir viajantes com RG 7, 8 e 9 dígitos.  
   - Verificar na lista: `1.234.567`, `12.345.678`, `12.345.678-9` (nunca valor só com números).

3. **“Não possui RG”**  
   - Cadastrar/editar com "Não possui RG" marcado.  
   - Salvar.  
   - Na lista: deve aparecer apenas o badge "NÃO POSSUI RG".  
   - No banco: `rg = "NÃO POSSUI RG"`.

4. **Máscara ao carregar**  
   - Editar um viajante que já tem RG em dígitos.  
   - Ver máscara no campo ao abrir a tela e após F5.

---

## 5. Testes automatizados

- `test_viajante_rg_salvo_como_digitos_editar_mostra_mascarado`: cria com RG formatado, confere banco com dígitos e GET editar com máscara.  
- `test_viajante_lista_mostra_rg_mascarado`: lista contém RG formatado.  
- `test_viajante_sem_rg_lista_mostra_nao_possui_rg`: sem_rg salva "NÃO POSSUI RG" e lista exibe "NÃO POSSUI RG".  
- Demais testes de viajante (sem_rg, RG vazio, CPF/telefone) seguem passando.
