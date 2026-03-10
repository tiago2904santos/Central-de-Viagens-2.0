# Relatório: Correção da persistência de datas na Etapa 1 (Evento guiado)

## 1) Causa exata do bug

O problema tinha duas origens possíveis, ambas tratadas:

- **Backend**: As datas (`data_unica`, `data_inicio`, `data_fim`) dependiam apenas do `form.save(commit=False)` para serem aplicadas à instância antes do `ev.save()`. Não havia garantia explícita de que `form.cleaned_data` fosse a fonte única antes do primeiro `save()`, e as chamadas posteriores a `obj.save(update_fields=['descricao'])`, `obj.save(update_fields=['titulo'])` e `obj.save(update_fields=['status'])` não alteram as datas, mas a persistência das datas no primeiro `save()` ficou explícita para evitar qualquer perda.

- **Checkbox no teste**: No Django Test Client, ao enviar `{'data_unica': False}` no POST, a chave `data_unica` vai no corpo da requisição (ex.: valor `"False"`). No formulário, um `BooleanField` com `CheckboxInput` considera **qualquer valor presente** como “marcado” (True). Assim, em testes que enviavam `data_unica: False`, o form recebia na prática `data_unica=True`, o que podia fazer `data_fim` ser sobrescrito por `data_inicio` no `clean()` e mascarar falhas de persistência ou de validação. No navegador, checkbox desmarcado não envia a chave, então o form recebe corretamente `False`.

- **Template**: O valor dos inputs de data era renderizado com `{{ form.data_inicio.value|default:'' }}`. Para objetos `date`, isso pode não gerar sempre o formato ISO `YYYY-MM-DD` esperado por `<input type="date">`. Em alguns contextos/locale, a exibição ao reabrir a Etapa 1 podia ficar incorreta ou vazia.

**Resumo**: A causa principal tratada foi garantir no backend a atribuição explícita das datas a partir de `form.cleaned_data` e um único `ev.save()` que persiste o evento (incluindo datas). Ajustes no template (formato da data) e nos testes (não enviar `data_unica` quando for False) eliminam efeitos colaterais e reproduzem o comportamento real do navegador.

---

## 2) Arquivos alterados

| Arquivo | Alteração |
|--------|-----------|
| `eventos/views.py` | Atribuição explícita de `data_inicio`, `data_fim` e `data_unica` a partir de `form.cleaned_data` antes de `ev.save()`. Regra: se `data_unica` e `data_inicio` preenchidos, `data_fim = data_inicio`; senão usa `data_fim` do form. |
| `templates/eventos/guiado/etapa_1.html` | Valores dos inputs `data_inicio` e `data_fim` passam a usar `{% firstof form.data_inicio.value|date:'Y-m-d' form.data_inicio.value %}` (e equivalente para `data_fim`) para garantir formato `Y-m-d` quando for objeto date e fallback para string (ex.: reexibição após erro). |
| `eventos/tests/test_eventos.py` | (1) Testes que precisam de `data_unica=False` deixam de enviar a chave `data_unica` no POST. (2) Novos testes: `test_etapa_1_datas_persistidas_data_unica_true`, `test_etapa_1_datas_persistidas_data_unica_false`, `test_etapa_1_reabrir_mostra_datas_salvas`, `test_detalhe_evento_mostra_datas_corretas`. (3) `test_reabrir_etapa_1_apos_salvar_mantem_tipos_destinos_datas` passa a assertar datas persistidas e presença de `2025-05-10`/`2025-05-12` no HTML ao reabrir. (4) `test_etapa_1_salva_corretamente` passa a assertar `data_inicio`, `data_fim` e `data_unica` após `refresh_from_db`. (5) `test_etapa1_data_fim_menor_que_data_inicio_rejeita` deixa de enviar `data_unica` para que a validação `data_fim >= data_inicio` seja aplicada. |

---

## 3) O que foi corrigido no frontend

- **Valor dos inputs de data**: Uso de `{% firstof form.data_inicio.value|date:'Y-m-d' form.data_inicio.value %}` (e o mesmo para `data_fim`) para que:
  - Com valor vindo do banco (objeto `date`), o input receba sempre `YYYY-MM-DD`.
  - Com valor vindo do POST (string), o valor seja reexibido corretamente em caso de erro de validação.
- **Comportamento de “Evento em um único dia”**: Mantido como antes: ao marcar, o JS esconde `#wrap-data-fim` e sincroniza `data_fim` com `data_inicio`; ao desmarcar, mostra de novo. O input `data_fim` continua no DOM (só oculto), então segue sendo enviado no submit; o backend continua sendo a fonte da verdade (regra `data_unica` → `data_fim = data_inicio`).

---

## 4) O que foi corrigido no backend

- Na view `guiado_etapa_1`, após `form.save(commit=False)` e antes de `ev.save()`:
  - Leitura de `data_inicio`, `data_fim` e `data_unica` de `form.cleaned_data`.
  - Se `data_inicio` não for None: `ev.data_inicio = data_inicio`.
  - Se `data_unica` e `data_inicio` não forem None: `ev.data_fim = data_inicio`.
  - Caso contrário, se `data_fim` não for None: `ev.data_fim = data_fim`.
  - `ev.data_unica = data_unica`.
- Assim, as datas passam a ser sempre definidas a partir do formulário validado e persistidas no primeiro `ev.save()`; os `obj.save(update_fields=[...])` seguintes não alteram datas.

---

## 5) Como testar manualmente

1. **Evento em um único dia**
   - Abrir um evento na Etapa 1 (ou criar novo pelo fluxo guiado).
   - Marcar “Evento em um único dia”.
   - Informar “Data do evento” (ex.: 15/03/2026).
   - Preencher tipos de demanda e pelo menos um destino; salvar.
   - Reabrir a Etapa 1: deve mostrar a mesma data e o checkbox marcado.
   - Abrir o detalhe do evento: deve mostrar a data uma vez com “(evento em um único dia)”.

2. **Evento com intervalo**
   - Desmarcar “Evento em um único dia”.
   - Preencher “Data do evento” e “Data de término” (ex.: 10/03/2026 e 14/03/2026).
   - Salvar.
   - Reabrir a Etapa 1: as duas datas devem aparecer preenchidas.
   - Detalhe do evento: deve mostrar “Data de início” e “Data de término” com os valores salvos.

3. **Validação**
   - Com “Evento em um único dia” desmarcado, colocar data de término anterior à data de início e salvar: deve aparecer erro de validação e as datas informadas devem continuar nos campos.

---

## 6) Checklist de aceite

| Item | Status |
|------|--------|
| data_unica=True: data_inicio e data_fim persistidas; data_fim = data_inicio | OK |
| data_unica=False: data_inicio e data_fim persistidas com valores distintos | OK |
| Reabrir Etapa 1 exibe as datas já salvas nos inputs | OK |
| Detalhe do evento exibe as datas corretas (d/m/Y) | OK |
| Frontend: “Evento em um único dia” esconde/mostra data_fim e mantém valor no submit | OK |
| Backend: datas atribuídas explicitamente de form.cleaned_data e salvas no primeiro save() | OK |
| Testes: persistência com data_unica True/False, reabrir e detalhe | OK |
