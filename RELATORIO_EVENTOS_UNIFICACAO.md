# Relatório — Unificação do módulo Eventos

## 1) Arquivos alterados

| Arquivo | Alterações |
|---------|------------|
| `eventos/views.py` | `evento_editar`: redireciona para `guiado-etapa-1`. `evento_cadastrar`: redireciona para `guiado-novo`. `evento_lista`: queryset com `prefetch_related('tipos_demanda', 'destinos', ...)`; filtro só por `tipo_id` (tipos_demanda). Removido uso de `EventoForm`. Após criar destinos na Etapa 1, limpa cache de prefetch de `destinos` para `gerar_titulo()` enxergar os novos. |
| `eventos/urls.py` | Sem alteração (rotas `editar` e `cadastrar` mantidas; passam a redirecionar). |
| `templates/eventos/evento_detalhe.html` | Reescrito: título, tipo(s) de demanda, data início/término (com indicação de “evento em um único dia”), destinos, tem convite/ofício, status. Descrição só se `object.descricao` preenchida. Removidos cidade_base, estado_principal, cidade_principal, tipo legado. Botão "Editar" → "Editar Etapa 1" (link para `guiado-etapa-1`). |
| `templates/eventos/evento_lista.html` | Lista unificada: colunas Título, Tipos, Status, Início, Término, Destinos. Filtro por tipo usa `tipos_demanda_list` e `tipo_id`. Ações: "Abrir fluxo guiado", "Editar Etapa 1", "Ver". Removido botão "Cadastrar evento" (só "Novo (fluxo guiado)"). |
| `templates/eventos/guiado/etapa_1.html` | Bloco da descrição (OUTROS) movido para logo abaixo de "Tipos de demanda": ordem fica Tipos de demanda → Descrição (se OUTROS) → Datas → Destinos → tem_convite. Removido o bloco de descrição que ficava após Destinos. |
| `eventos/tests/test_eventos.py` | `EventoCRUDTest`: `test_cadastrar_redireciona_para_fluxo_guiado`, `test_editar_redireciona_para_etapa_1`. `EventoValidacaoTest`: `test_etapa1_data_fim_menor_que_data_inicio_rejeita` (valida na Etapa 1). `EventoDetalheTest`: `test_detalhe_ok_mostra_dados_do_modelo_novo` (sem cidade_base, com "Editar Etapa 1"). `EventoListaAuthTest`: `test_lista_exibe_titulo_destinos_editar_etapa_1`. `EventoEtapa1RefatoradoTest`: `test_reabrir_etapa_1_apos_salvar_mantem_tipos_destinos_datas`. Ajuste em `test_etapa_1_salva_corretamente` (descrição vazia quando não é OUTROS). |

---

## 2) O que foi unificado entre editar e Etapa 1

- **Fonte única**: Não existe mais tela de edição “modelo antigo”.  
  - `eventos:editar` (GET ou POST) redireciona para `eventos:guiado-etapa-1` com o mesmo `pk`.  
  - Quem edita dados da Etapa 1 (tipos, datas, destinos, descrição, etc.) usa apenas a tela da Etapa 1 do fluxo guiado.
- **Cadastro**: `eventos:cadastrar` redireciona para `eventos:guiado-novo`, que cria o evento e envia para a Etapa 1. Criação e primeira edição usam a mesma tela (Etapa 1).
- **Formulário**: Só há um formulário para esses dados: `EventoEtapa1Form` na view `guiado_etapa_1`. Não há dois formulários diferentes para o mesmo dado.

---

## 3) O que foi corrigido na persistência

- **Cache de destinos**: Após `obj.destinos.all().delete()` e criação dos novos `EventoDestino`, o prefetch de `destinos` no objeto era mantido. Foi adicionada a limpeza do cache (`_prefetched_objects_cache['destinos']`) para que `gerar_titulo()` use os destinos recém-criados no mesmo request.
- **Fluxo de save na Etapa 1**: Ordem mantida e conferida:  
  1) `form.save(commit=False)` + ajuste `data_fim` se `data_unica`;  
  2) `ev.save()`;  
  3) `form.save_m2m()` (tipos_demanda);  
  4) remoção dos destinos antigos e criação dos novos;  
  5) limpeza de cache de destinos;  
  6) descrição zerada quando não há OUTROS;  
  7) título gerado e salvo.  
- **Reabrir Etapa 1**: `destinos_atuais` e `selected_tipos_pks` vêm do banco (destinos e tipos_demanda do evento), então ao reabrir a Etapa 1 os dados persistidos aparecem corretamente.

---

## 4) Como ficou detalhe e lista

- **Detalhe**  
  - Exibe: título (gerado), tipo(s) de demanda, data início/término (com texto “evento em um único dia” quando for o caso), destinos do evento, tem convite/ofício, status.  
  - Descrição só é exibida se `object.descricao` estiver preenchida (regra de negócio: só quando há tipo OUTROS).  
  - Não exibe mais: cidade_base, estado_principal, cidade_principal, “tipo de demanda legado”.  
  - Ação principal de edição: "Editar Etapa 1" → `guiado-etapa-1`.

- **Lista**  
  - Colunas: Título, Tipos (nomes dos tipos_demanda), Status, Início, Término, Destinos (nomes das cidades).  
  - Filtro por tipo usa `tipos_demanda_list` e parâmetro `tipo_id`.  
  - Ações por linha: "Abrir fluxo guiado", "Editar Etapa 1", "Ver".  
  - Único botão de criação: "Novo (fluxo guiado)".

---

## 5) Como ficou a descrição de OUTROS

- **Posição**: O campo de descrição fica **logo abaixo** do bloco "Tipos de demanda" no formulário da Etapa 1 (não mais no fim do formulário).
- **Visibilidade**: O bloco `#wrap-descricao` só é exibido quando o tipo com `is_outros=True` está marcado (JS usa `tipo_outros_pk`). Caso contrário fica oculto.
- **Validação**: Com tipo OUTROS selecionado, a descrição é obrigatória (`EventoEtapa1Form.clean`). Sem OUTROS, o form limpa `descricao` e não exige.
- **Backend**: Na view, se não houver OUTROS, `obj.descricao = ''` e `save(update_fields=['descricao'])`. Com OUTROS, o valor do form é mantido.

---

## 6) Como testar manualmente

1. **Edição = Etapa 1**  
   - Na lista, clicar "Editar Etapa 1" em um evento → deve abrir `/eventos/<id>/guiado/etapa-1/`.  
   - Alterar tipos, datas, destinos ou descrição (se OUTROS), salvar → deve persistir e, ao reabrir a Etapa 1, exibir os dados salvos.

2. **Detalhe**  
   - Abrir "Ver" em um evento com tipos, destinos e título preenchidos.  
   - Conferir título, tipos, datas, destinos, status e que não aparece cidade_base nem “tipo legado”.  
   - Se o evento tiver tipo OUTROS e descrição, a descrição deve aparecer.

3. **Lista**  
   - Verificar colunas Título, Tipos, Datas, Destinos e ações "Abrir fluxo guiado", "Editar Etapa 1", "Ver".  
   - Filtrar por tipo de demanda e conferir resultados.

4. **Descrição OUTROS**  
   - Na Etapa 1, sem marcar "Outros": o bloco de descrição deve ficar oculto.  
   - Marcar "Outros": o bloco deve aparecer logo abaixo de "Tipos de demanda"; salvar sem preencher deve dar erro.  
   - Preencher descrição e salvar → no detalhe do evento a descrição deve aparecer.

5. **Persistência**  
   - Preencher Etapa 1 com vários tipos, dois destinos e data intervalo; salvar.  
   - Reabrir a Etapa 1: tipos, destinos e datas devem vir preenchidos.  
   - Abrir o detalhe do evento: título, tipos, datas e destinos devem bater com o que foi salvo.

---

## 7) Checklist de aceite

| Item | Status |
|------|--------|
| Edição de evento usa a mesma tela/lógica da Etapa 1 (redirecionamento) | OK |
| Cadastrar evento redireciona para fluxo guiado | OK |
| Detalhe mostra título, tipos, datas, destinos, status (sem cidade_base/legado) | OK |
| Lista mostra título, tipos, datas, destinos; ações Editar Etapa 1 e Ver | OK |
| Descrição (OUTROS) fica logo abaixo de Tipos de demanda | OK |
| Descrição só aparece quando OUTROS está selecionado | OK |
| Persistência: tipos, destinos, datas, título e descrição salvos corretamente | OK |
| Reabrir Etapa 1 exibe dados persistidos | OK |
| Testes: editar → etapa 1, detalhe modelo novo, lista, descrição, persistência | OK |

---

*Módulo Eventos unificado ao padrão do evento guiado; uma única fonte de verdade para a Etapa 1.*
