# Relatório — Lógica de status e completude do módulo Veículos

## 1. Campos que definem completude do veículo

Para um veículo poder ser usado no sistema (status **FINALIZADO**), todos os dados obrigatórios devem estar preenchidos e válidos:

| Campo | Regra |
|-------|--------|
| **placa** | Preenchida, 7 caracteres, formato antigo (3 letras + 4 dígitos) ou Mercosul (3 letras + 1 dígito + 1 letra + 2 dígitos) |
| **modelo** | Preenchido (não vazio após trim) |
| **combustivel** | FK definida (combustivel_id não nula) |
| **tipo** | CARACTERIZADO ou DESCARACTERIZADO |

A regra está centralizada no model **`Veiculo.esta_completo()`**, que retorna `True` apenas quando todas as condições acima são atendidas. O método auxiliar **`_placa_valida()`** verifica o formato da placa.

---

## 2. Onde foi implementada a regra de status automático

- **Model** (`cadastros/models.py`): método **`Veiculo.esta_completo()`** que verifica placa (via `_placa_valida()`), modelo, combustivel_id e tipo.
- **Form** (`cadastros/forms.py`): **placa** e **modelo** deixaram de ser obrigatórios no `clean_placa` e `clean_modelo` (podem retornar `''`); quando preenchidos, continuam validação de formato e unicidade (placa).
- **Views** (`cadastros/views/veiculos.py`):
  - **veiculo_cadastrar** (POST): após `form.save(commit=False)`, define `obj.status = STATUS_FINALIZADO if obj.esta_completo() else STATUS_RASCUNHO` e em seguida `obj.save()`.
  - **veiculo_editar** (POST): após `form.save()`, define `obj.status = STATUS_FINALIZADO if obj.esta_completo() else STATUS_RASCUNHO` e `obj.save(update_fields=['status'])`.

Assim, o **Salvar** nunca é bloqueado por falta de dado obrigatório: o registro é sempre salvo e o status é definido automaticamente conforme a completude (FINALIZADO ou RASCUNHO).

---

## 3. Querysets ajustados para esconder RASCUNHO

RASCUNHO não deve aparecer em uso operacional (ofícios, termos, documentos, configurações). Ajustes feitos:

| Local | Ajuste |
|-------|--------|
| **cadastros/forms.py** | Função **`_veiculos_finalizados_queryset()`** que retorna `Veiculo.objects.filter(status=Veiculo.STATUS_FINALIZADO).order_by('placa', 'modelo')`. Deve ser usada em qualquer ModelChoiceField ou select que liste veículos para uso operacional (ofícios, termos, documentos, configurações futuras). |

**Situação atual:** No projeto não há hoje formulários/selects que listem veículos para escolha (configurações, ofícios etc.). Quando forem implementados, devem usar **`_veiculos_finalizados_queryset()`** (ou equivalente) para exibir apenas veículos FINALIZADO.

**Mantidos sem filtro (RASCUNHO pode aparecer):**

- **veiculo_lista** (view): lista todos os veículos.
- **veiculo_editar**: edição do próprio veículo.
- **VeiculoAdmin**: listagem e busca no admin mostram todos.

---

## 4. Como testar manualmente

1. **Salvar incompleto → RASCUNHO**
   - Cadastrar veículo preenchendo só modelo e tipo (sem placa, sem combustível). Salvar.
   - Verificar na lista: status **Rascunho**.
   - Abrir edição: deve aparecer o aviso em amarelo sobre veículo em rascunho não utilizável em outros módulos.

2. **Salvar completo → FINALIZADO**
   - Cadastrar ou editar preenchendo: placa (válida, ex.: ABC1234 ou ABC1D23), modelo, combustível e tipo.
   - Salvar.
   - Na lista, status deve ser **Finalizado**.

3. **Tipo padrão sozinho não finaliza**
   - Abrir cadastro novo (tipo já vem DESCARACTERIZADO). Deixar placa, modelo e combustível vazios e salvar.
   - O registro deve ser salvo com status **Rascunho**.

4. **Lista e edição**
   - Verificar coluna **Status** e badges Rascunho / Finalizado na lista.
   - Na edição de um veículo em rascunho, verificar o aviso de que não pode ser usado em outros módulos até ser finalizado.

---

## 5. Checklist de aceite

| Item | Status |
|------|--------|
| Campos obrigatórios definidos: placa (válida), modelo, combustivel, tipo | OK |
| `Veiculo.esta_completo()` e `_placa_valida()` implementados e usados para definir status | OK |
| Salvar incompleto → status RASCUNHO (save não bloqueado) | OK |
| Salvar completo e válido → status FINALIZADO | OK |
| Helper `_veiculos_finalizados_queryset()` para uso operacional | OK |
| Lista de veículos mostra todos (RASCUNHO e FINALIZADO) com coluna Status e badges | OK |
| Na edição, aviso exibido quando status é RASCUNHO | OK |
| Testes: incompleto→RASCUNHO, completo→FINALIZADO, RASCUNHO fora do queryset finalizados, FINALIZADO no queryset, tipo padrão sozinho não finaliza | OK |
