# Relatório — Correções Etapa 1 do Evento Guiado

## 1) Arquivos alterados

| Arquivo | Alterações |
|---------|------------|
| `eventos/forms.py` | EventoEtapa1Form: `data_fim` e `descricao` não obrigatórios por padrão; em `clean`, quando `data_unica` preenche `data_fim = data_inicio`; quando não tem OUTROS limpa `descricao` e não exige. |
| `eventos/views.py` | Etapa 1: placeholder de destino quando não há destinos (sempre 1 bloco); passa `tipo_outros_pk` para o template; ao salvar, sem OUTROS zera `descricao` (não usa mais `montar_descricao_padrao`). |
| `templates/eventos/guiado/etapa_1.html` | Bloco descrição dentro de `#wrap-descricao` (inicialmente oculto); JS mostra só quando tipo OUTROS está marcado; JS data única esconde `data_fim` e sincroniza valor no submit; destinos: `estados_json|safe`, botão Remover só remove se houver mais de 1 linha; texto de ajuda dos destinos ajustado. |
| `eventos/tests/test_eventos.py` | Novos/ajustes: `test_etapa_1_data_unica_sem_enviar_data_fim_backend_preenche`, `test_etapa_1_sem_outros_descricao_nao_obrigatoria`, `test_etapa_1_formulario_abre_com_um_destino`, `test_etapa_1_nao_pode_salvar_sem_destino`, `test_excluir_tipo_quando_nao_em_uso_funciona`. |

Nenhuma alteração em models, urls ou migrações.

---

## 2) O que foi corrigido em DESCRIÇÃO

- **Regra**: Não há mais descrição por padrão. O campo descrição só aparece quando o tipo de demanda selecionado inclui **OUTROS**.
- **Frontend**: O bloco "Descrição" (`#wrap-descricao`) fica oculto por padrão. Só é exibido quando o checkbox do tipo com `is_outros=True` está marcado (via `tipo_outros_pk` e JS).
- **Backend**:  
  - Se **OUTROS** está selecionado: descrição obrigatória (validação em `EventoEtapa1Form.clean`).  
  - Se **OUTROS** não está selecionado: descrição não é exigida; no `clean` é forçado `data['descricao'] = ''` e na view, ao salvar, `obj.descricao = ''` quando não tem OUTROS.
- **Remoção de preenchimento automático**: Não é mais usada `montar_descricao_padrao()`; sem OUTROS a descrição fica vazia.

---

## 3) O que foi corrigido em DATA ÚNICA

- **Frontend**: Ao marcar "Evento em um único dia", o campo `data_fim` (e seu `#wrap-data-fim`) some; ao desmarcar, volta a aparecer. O label de `data_inicio` muda para "Data do evento" quando marcado e "Data de início" quando desmarcado. Ao marcar ou alterar a data de início, o JS mantém `id_data_fim.value = id_data_inicio.value` para o submit.
- **Backend**: `EventoEtapa1Form` tem `data_fim.required = False`. No `clean`, quando `data_unica` e `data_inicio` estão preenchidos, é definido `data['data_fim'] = data_inicio`. Na view, após `form.save()`, se `ev.data_unica` e `ev.data_inicio` existem, `ev.data_fim = ev.data_inicio` e `save(update_fields=['data_fim'])`. Assim o comportamento fica correto mesmo se o front não enviar `data_fim`.

---

## 4) O que foi corrigido em DESTINOS

- **Sempre 1 destino visível**: Na view, quando o evento não tem nenhum destino, é enviado um placeholder (objeto com `estado_id=PR` se existir, `cidade_id=None`). O template sempre renderiza pelo menos um bloco (estado + cidade + Remover).
- **Botão "Adicionar destino"**: Passa a funcionar: `estadosOptions` no JS usa `{{ estados_json|default:'[]'|safe }}` para ser um array válido; `criarRowDestino(estadoPrId, ...)` adiciona uma nova linha com estado padrão PR e cidade carregada via API.
- **Remoção**: O botão "Remover" só remove a linha se houver mais de uma; com uma única linha o clique não remove (função `removerDestino` verifica `container.querySelectorAll('.destino-row').length <= 1`).
- **Validação no backend**: Continua em `_validar_destinos`: pelo menos um destino (estado + cidade) e cidade pertencente ao estado; em caso de erro, `form.add_error(None, msg_destinos)`.

---

## 5) Como testar manualmente

1. **Descrição só com OUTROS**  
   - Abrir Etapa 1 de um evento.  
   - Sem marcar "Outros": o bloco "Descrição" não deve aparecer.  
   - Marcar "Outros": o bloco "Descrição" deve aparecer; salvar sem preencher deve dar erro.  
   - Preencher descrição e salvar: deve salvar.  
   - Desmarcar "Outros" e salvar: descrição deve ser limpa no evento.

2. **Data única**  
   - Marcar "Evento em um único dia": o campo "Data de término" some e o label da primeira data vira "Data do evento".  
   - Desmarcar: "Data de término" volta e o label vira "Data de início".  
   - Com "um único dia" marcado, preencher data e salvar: no banco `data_fim` deve ser igual a `data_inicio`.

3. **Destinos**  
   - Abrir Etapa 1 (evento novo ou sem destinos): deve haver 1 bloco estado/cidade (estado PR se existir).  
   - Clicar "Adicionar destino": deve aparecer outro bloco.  
   - Remover: com 2+ blocos, "Remover" tira a linha; com 1 bloco, "Remover" não faz nada.  
   - Salvar sem preencher estado/cidade (ou sem enviar destino válido): deve dar erro de "pelo menos um destino".  
   - Preencher estado e cidade válidos e salvar: deve gravar destinos.

4. **Gerenciador de tipos de demanda**  
   - Lista/editar/excluir em `/eventos/tipos-demanda/`.  
   - Excluir um tipo **não** usado: deve excluir e redirecionar.  
   - Excluir um tipo **em uso** por algum evento: deve manter o tipo e redirecionar para a edição com mensagem de erro (ex.: "Não é possível excluir: este tipo está em uso por pelo menos um evento.").

5. **Painel**  
   - Etapa 1 = OK quando: pelo menos 1 tipo de demanda, pelo menos 1 destino válido, datas válidas, se OUTROS selecionado descrição preenchida, título gerado.  
   - Conferir no painel do evento se o badge da Etapa 1 fica OK após preencher tudo corretamente.

---

## 6) Checklist de aceite

| Item | Status |
|------|--------|
| Descrição só aparece quando OUTROS está selecionado | OK |
| Com OUTROS: descrição visível e obrigatória | OK |
| Sem OUTROS: descrição oculta e não exigida; limpa ao salvar | OK |
| Data única: campo data_fim some no frontend | OK |
| Data única: backend garante data_fim = data_inicio | OK |
| Formulário abre já com 1 bloco de destino | OK |
| Botão "Adicionar destino" adiciona 2º, 3º... destino | OK |
| Não permite salvar sem nenhum destino válido | OK |
| Não permite remover o único destino (só extras) | OK |
| Excluir tipo de demanda quando não está em uso | OK |
| Exclusão de tipo em uso bloqueada com mensagem clara | OK |
| Critério Etapa 1 OK no painel (tipos, destinos, datas, descrição se OUTROS, título) | OK |
| Testes: descrição, data única, destinos, CRUD tipos | OK |

---

*Correções aplicadas na Etapa 1 do evento guiado; foco em funcionalidade.*
