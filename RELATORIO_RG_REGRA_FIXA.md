# Relatório: RG do módulo Viajantes — regra fixa de máscara

## Objetivo

Garantir que o RG **sempre** apareça com máscara ao abrir/editar e na lista (nunca “cru”), com persistência padronizada e opção “NÃO POSSUI RG” (`sem_rg`).

---

## 1. Migrations criadas

| Migration | Descrição |
|-----------|-----------|
| `0009_rg_nao_possui_padrao.py` | Data migration: atualiza `Viajante` com `rg='NÃO POSSUI RG'` para `rg='NAO POSSUI RG'` (padrão de armazenamento sem acento). |

**Model:** `Viajante.save()` passou a gravar `rg = 'NAO POSSUI RG'` quando `sem_rg=True`. O campo `sem_rg` já existia; não foi criada migration de schema para ele.

---

## 2. Onde ficou `format_rg` (backend) e onde é aplicado

### Backend — função única

- **Arquivo:** `cadastros/utils/masks.py`
- **Funções:**  
  - `only_digits(s)` — remove não dígitos.  
  - `format_rg(digits)` — formata RG para exibição:
    - `""` → `""`
    - 7 dígitos → `1.234.567`
    - 8 dígitos → `1.234.567-8` (X.XXX.XXX-X)
    - 9 dígitos → `12.345.678-9` (XX.XXX.XXX-X)
    - outro tamanho → devolve os dígitos sem formatação

### Onde é usado

- **Form (`cadastros/forms.py`):** importa `only_digits` e `format_rg` de `cadastros.utils.masks`. No `__init__` (GET/editar, sem POST): se `instance.sem_rg` ou `instance.rg == 'NAO POSSUI RG'` → `initial['rg'] = 'NAO POSSUI RG'`; se `instance.rg` for só dígitos → `initial['rg'] = format_rg(instance.rg)`. No `clean_rg`: se `sem_rg` → `'NAO POSSUI RG'`; senão → `only_digits(rg)` ou `''`.
- **Lista (`cadastros/views/viajantes.py`):** importa `format_rg` de `..utils.masks`. Em `_rg_display(obj)`: se `sem_rg` ou `rg == 'NAO POSSUI RG'` → retorna `'NÃO POSSUI RG'` (exibição); se `rg` vazio → `'—'`; se `rg` só dígitos → `format_rg(obj.rg)`; senão → `obj.rg`. Cada item da lista recebe `obj.rg_display` com esse valor.
- **Template lista:** usa `obj.rg_display`; se for `"NÃO POSSUI RG"` mostra o badge; senão mostra o texto mascarado.

### Template do form (frontend)

- **Arquivo:** `templates/cadastros/viajantes/form.html`
- **JS:** `formatRg(val)` com a mesma regra (7 → 1.234.567, 8 → 1.234.567-8, 9 → 12.345.678-9).
- **DOMContentLoaded:** aplica máscara ao valor atual do input RG (exceto quando for "NAO POSSUI RG" / "NÃO POSSUI RG").
- **Input (digitação):** evento `input` formata em tempo real (até 9 dígitos).
- **sem_rg:** ao marcar “Não possui RG”, o input RG é desabilitado e o valor exibido é "NÃO POSSUI RG"; ao desmarcar, o campo é habilitado e o valor limpo.

---

## 3. Regras de persistência (model + form)

- **sem_rg=True:** no `Model.save()` e no `clean_rg` → `rg = 'NAO POSSUI RG'`.
- **sem_rg=False:** no `clean_rg` → `rg = only_digits(valor)` (string só com dígitos) ou `''` se vazio; o model não altera `rg` nesse caso.

---

## 4. Como testar manualmente

1. **Criar com RG (9 dígitos)**  
   Cadastros → Viajantes → Cadastrar. Preencher nome, cargo e RG (ex.: 12.345.678-9 ou 123456789). Salvar.  
   - Lista: RG deve aparecer como **12.345.678-9**.  
   - Editar: campo RG deve carregar já com **12.345.678-9** (e após F5 também).

2. **Criar com RG (8 dígitos)**  
   Cadastrar com RG 1.234.567-8 ou 12345678.  
   - Lista e editar: exibir **1.234.567-8**.

3. **“Não possui RG”**  
   Cadastrar ou editar com “Não possui RG” marcado. Salvar.  
   - Lista: badge **NÃO POSSUI RG**.  
   - Editar: checkbox marcada, campo RG desabilitado com **NÃO POSSUI RG**.  
   - No banco: `rg = 'NAO POSSUI RG'`.

4. **Máscara ao carregar**  
   Editar um viajante que já tem RG em dígitos (7, 8 ou 9).  
   - Ao abrir a tela e após F5, o RG deve aparecer sempre mascarado (nunca só números).

---

## 5. Checklist de aceite

| Item | Status |
|------|--------|
| RG com máscara no form (ao carregar e ao digitar) | OK |
| RG com máscara na lista de viajantes | OK |
| Opção “NÃO POSSUI RG” (sem_rg) persiste e exibe corretamente | OK |
| Persistência: sem_rg → "NAO POSSUI RG"; senão só dígitos ou "" | OK |
| format_rg em utils (7: 1.234.567; 8: 1.234.567-8; 9: 12.345.678-9) | OK |
| Migration 0009 (padronizar NAO POSSUI RG) | OK |
| Testes: RG dígitos, máscara no edit/lista, sem_rg, 8 dígitos, editar sem_rg | OK |

---

## 6. Arquivos alterados/criados

| Arquivo | Alteração |
|--------|-----------|
| `cadastros/utils/__init__.py` | Novo (pacote). |
| `cadastros/utils/masks.py` | Novo: `only_digits(s)`, `format_rg(digits)` (regra RG BR 7/8/9). |
| `cadastros/models.py` | Em `Viajante.save()`: `rg = 'NAO POSSUI RG'` quando `sem_rg`. |
| `cadastros/migrations/0009_rg_nao_possui_padrao.py` | Nova: data migration NÃO→NAO. |
| `cadastros/forms.py` | Import de `only_digits` e `format_rg` de utils; remoção do `format_rg` local; `__init__` e `clean_rg` com regra NAO POSSUI RG e dígitos. |
| `cadastros/views/viajantes.py` | Import de `format_rg` de utils; `_rg_display` considera `'NAO POSSUI RG'` e exibe "NÃO POSSUI RG". |
| `templates/cadastros/viajantes/form.html` | `formatRg` JS com 8→1.234.567-8, 9→12.345.678-9; sem_rg marca campo com "NÃO POSSUI RG" e desabilita; DOMContentLoaded aplica máscara ao RG. |
| `cadastros/tests/test_cadastros.py` | Testes atualizados para `rg='NAO POSSUI RG'`; novo teste RG 8 dígitos (editar e lista); novo teste editar com sem_rg (indicativo travado). |
