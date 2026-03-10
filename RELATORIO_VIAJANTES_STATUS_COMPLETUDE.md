# Relatório — Lógica de status e completude do módulo Viajantes

## 1. Campos que definem completude

Para um viajante poder ser usado no sistema (status **FINALIZADO**), todos os dados obrigatórios devem estar preenchidos e válidos:

| Campo | Regra |
|-------|--------|
| **nome** | Preenchido (não vazio após trim) |
| **cargo** | FK definida (cargo_id não nulo) |
| **cpf** | Exatamente 11 dígitos |
| **telefone** | 10 ou 11 dígitos |
| **unidade_lotacao** | FK definida (unidade_lotacao_id não nula) |
| **RG** | **OU** `sem_rg=True` (rg = 'NAO POSSUI RG') **OU** rg preenchido com valor válido (não vazio e diferente de 'NAO POSSUI RG') |

A regra está centralizada no model **`Viajante.esta_completo()`**, que retorna `True` apenas quando todas as condições acima são atendidas.

---

## 2. Onde foi implementada a regra de status automático

- **Model** (`cadastros/models.py`): método **`Viajante.esta_completo()`** que verifica nome, cargo_id, cpf (11 dígitos), telefone (10 ou 11 dígitos), unidade_lotacao_id e (sem_rg ou rg preenchido).
- **Form** (`cadastros/forms.py`): campo **nome** deixou de ser obrigatório no `clean_nome` (pode retornar `''`); os demais campos já permitiam vazio quando aplicável. O formulário continua validando **formato** e **unicidade** quando o valor é informado (ex.: CPF 11 dígitos e válido, telefone 10/11 dígitos).
- **Views** (`cadastros/views/viajantes.py`):
  - **viajante_cadastrar** (POST): após `form.save(commit=False)`, define `obj.status = STATUS_FINALIZADO if obj.esta_completo() else STATUS_RASCUNHO` e em seguida `obj.save()`.
  - **viajante_editar** (POST): após `form.save()`, define `obj.status = STATUS_FINALIZADO if obj.esta_completo() else STATUS_RASCUNHO` e `obj.save(update_fields=['status'])`.

Assim, o **Salvar** nunca é bloqueado por falta de dados obrigatórios: o registro é sempre salvo e o status é definido automaticamente conforme a completude (FINALIZADO ou RASCUNHO).

---

## 3. Querysets ajustados para esconder RASCUNHO

RASCUNHO não deve aparecer em uso operacional (ofícios, termos, assinaturas, configurações). Ajustes feitos:

| Local | Ajuste |
|-------|--------|
| **cadastros/forms.py** | **`_viajantes_queryset()`** já retornava `Viajante.objects.filter(status=STATUS_FINALIZADO).order_by('nome')`. É usada nos campos de assinatura do **ConfiguracaoSistemaForm** (assinatura_oficio, assinatura_justificativas, etc.). |
| **cadastros/admin.py** | **AssinaturaConfiguracaoInline**: `formfield_for_foreignkey` para o campo `viajante` com `queryset=Viajante.objects.filter(status=Viajante.STATUS_FINALIZADO).order_by('nome')`. |
| **cadastros/admin.py** | **AssinaturaConfiguracaoAdmin**: `formfield_for_foreignkey` para o campo `viajante` com o mesmo filtro. |

**Mantidos sem filtro (RASCUNHO pode aparecer):**

- **viajante_lista** (view): lista todos os viajantes (lista de cadastro).
- **viajante_editar**: edição do próprio viajante (por pk).
- **ViajanteAdmin**: listagem e busca no admin mostram todos (incluindo RASCUNHO).

---

## 4. Como testar manualmente

1. **Salvar incompleto → RASCUNHO**
   - Cadastrar viajante preenchendo só nome e cargo. Clicar em Salvar.
   - Verificar na lista: status **Rascunho**.
   - Abrir edição: deve aparecer o aviso em amarelo sobre rascunho não utilizável em outros módulos.

2. **Salvar completo → FINALIZADO**
   - Cadastrar ou editar preenchendo: nome, cargo, CPF (válido), telefone (10 ou 11 dígitos), unidade de lotação e RG **ou** “Não possui RG”.
   - Salvar.
   - Na lista, status deve ser **Finalizado**.

3. **RASCUNHO não aparece em assinaturas**
   - Deixar um viajante em RASCUNHO (só nome/cargo, por exemplo).
   - Ir em Configurações e abrir o formulário de configurações (assinaturas).
   - No select de “Assinatura (Ofícios)” (e demais), o viajante em rascunho **não** deve aparecer na lista.

4. **FINALIZADO aparece em assinaturas**
   - Ter pelo menos um viajante FINALIZADO.
   - Em Configurações, no select de assinaturas, esse viajante deve aparecer.

5. **RG ou “Não possui RG”**
   - Cadastro com todos os outros campos preenchidos mas sem RG e sem marcar “Não possui RG” → deve salvar como RASCUNHO.
   - Marcar “Não possui RG” (e salvar com o restante completo) → deve ficar FINALIZADO.

---

## 5. Checklist de aceite

| Item | Status |
|------|--------|
| Campos obrigatórios definidos: nome, cargo, cpf, telefone, unidade_lotacao, RG ou sem_rg | OK |
| `Viajante.esta_completo()` implementado e usado para definir status | OK |
| Salvar incompleto → status RASCUNHO (save não bloqueado) | OK |
| Salvar completo e válido → status FINALIZADO | OK |
| RASCUNHO não aparece em selects/querysets de assinaturas e configurações | OK |
| RASCUNHO não aparece no admin em FKs de assinatura (formfield_for_foreignkey) | OK |
| Lista de viajantes mostra todos (RASCUNHO e FINALIZADO) com coluna Status e badges | OK |
| Na edição, aviso exibido quando status é RASCUNHO | OK |
| Testes: incompleto→RASCUNHO, completo→FINALIZADO, RASCUNHO fora do queryset de assinaturas, FINALIZADO no queryset, RG/sem_rg | OK |
