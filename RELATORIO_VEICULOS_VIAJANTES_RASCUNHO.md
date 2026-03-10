# Relatório — Correções funcionais: Veículos, Viajantes, Unidades de Lotação e Rascunho

## 1. Arquivos alterados

### Models / Forms
- **cadastros/forms.py** — Remoção de `format_placa` no `VeiculoForm`; placa em edição exibida sem máscara; `UnidadeLotacaoForm` novo; `ViajanteForm` e `VeiculoForm`: não sobrescrever `initial` quando há rascunho (`kwargs.get('initial')`); placeholder placa 7 caracteres.
- **cadastros/models.py** — Nenhuma alteração (UnidadeLotacao já existia).

### Views
- **cadastros/views/veiculos.py** — Remoção de `format_placa` na lista; sessão `veiculo_form_rascunho` e `veiculo_form_return_url`; view `veiculo_salvar_rascunho_ir_combustiveis`; em `veiculo_cadastrar` e `veiculo_editar`: restaurar rascunho no GET, limpar sessão ao salvar com sucesso, passar `return_url` ao template; `combustivel_lista` passa `return_url` da sessão.
- **cadastros/views/viajantes.py** — Sessão `viajante_form_rascunho` e `viajante_form_return_url`; views `viajante_salvar_rascunho_ir_cargos` e `viajante_salvar_rascunho_ir_unidades`; em `viajante_cadastrar` e `viajante_editar`: restaurar rascunho, limpar sessão ao salvar, passar `return_url`.
- **cadastros/views/cargos.py** — Leitura de `return_url` da sessão e envio ao template da lista de cargos.
- **cadastros/views/unidades.py** — Novo: CRUD Unidade de Lotação (lista, cadastrar, editar, excluir; bloqueio de exclusão se em uso).

### URLs
- **cadastros/urls.py** — Rotas: `veiculo-rascunho-ir-combustiveis`, `viajante-rascunho-ir-cargos`, `viajante-rascunho-ir-unidades`, `unidade-lotacao-lista`, `unidade-lotacao-cadastrar`, `unidade-lotacao-editar`, `unidade-lotacao-excluir`.

### Templates
- **templates/cadastros/veiculos/form.html** — Placa sem máscara (input 7 chars, só UPPER/alfanumérico no JS); botão “Gerenciar combustíveis” com `formaction` para salvar rascunho; campo oculto `return_url`.
- **templates/cadastros/veiculos/lista.html** — Sem alteração (já usa `placa_display`; na view passa a ser a placa bruta).
- **templates/cadastros/veiculos/combustiveis_lista.html** — Botão “Voltar”: se existir `return_url` na sessão, link para ele; senão “Voltar para veículos”.
- **templates/cadastros/viajantes/form.html** — Campos Cargo e Unidade de Lotação separados, cada um com select e botão “Gerenciar Cargos” / “Gerenciar Unidades de Lotação” (submit com `formaction`); campo oculto `return_url`.
- **templates/cadastros/viajantes/lista.html** — Dois botões no header: “Gerenciar Cargos” e “Gerenciar Unidades de Lotação”.
- **templates/cadastros/cargos/lista.html** — Botão “Voltar”: se existir `return_url`, link para ele; senão “Voltar para viajantes”.
- **templates/cadastros/unidades/lista.html** — Novo: lista de unidades, busca, “Voltar” (return_url ou “Voltar para viajantes”), Cadastrar.
- **templates/cadastros/unidades/form.html** — Novo: formulário nome (maiúsculo).
- **templates/cadastros/unidades/excluir_confirm.html** — Novo: confirmação de exclusão.

### Outros
- **cadastros/views/__init__.py** — Export de `veiculo_salvar_rascunho_ir_combustiveis`, `viajante_salvar_rascunho_ir_cargos`, `viajante_salvar_rascunho_ir_unidades`, views de unidades.
- **cadastros/utils/masks.py** — Sem alteração (continua com `format_placa`; não é usado na lista/edição de veículo).
- **cadastros/tests/test_cadastros.py** — Testes de placa sem máscara; rascunho veículo (salvar e restaurar); tipo editável; rascunho viajante (cargos/unidades e restaurar); cargo e unidade como campos separados; `UnidadeLotacaoViewTest`: criar, editar, excluir sem uso, bloquear exclusão em uso.

---

## 2. Rascunho em Veículos e Viajantes

### Veículos
- **Chaves de sessão:** `veiculo_form_rascunho` (dict do POST do formulário), `veiculo_form_return_url` (URL do formulário de onde saiu).
- **Fluxo:** Usuário preenche o form (novo ou edição) e clica em “Gerenciar combustíveis”. O formulário é enviado por POST para `cadastros:veiculo-rascunho-ir-combustiveis`. A view grava `request.POST` em `request.session['veiculo_form_rascunho']` e a URL atual em `request.session['veiculo_form_return_url']`, exibe “Rascunho salvo temporariamente.” e redireciona para a lista de combustíveis.
- **Restauração:** Ao abrir de novo o formulário (GET em cadastrar ou editar), a view chama `_dados_rascunho_veiculo(request)`. Se houver rascunho, o form é instanciado com `initial=dados` e é exibida “Rascunho restaurado.”.
- **Limpeza:** Ao salvar o veículo com sucesso (POST válido), a view remove `veiculo_form_rascunho` e `veiculo_form_return_url` da sessão.

### Viajantes
- **Chaves de sessão:** `viajante_form_rascunho`, `viajante_form_return_url`.
- **Fluxo:** Dois botões com `formaction`: “Gerenciar Cargos” → `viajante-rascunho-ir-cargos` (redireciona para lista de cargos); “Gerenciar Unidades de Lotação” → `viajante-rascunho-ir-unidades` (redireciona para lista de unidades). Em ambos, o POST é salvo em `viajante_form_rascunho` e a URL em `viajante_form_return_url`, e é exibida “Rascunho salvo temporariamente.”.
- **Restauração:** Em GET de cadastrar/editar, se existir rascunho, o form usa `initial=dados` e é exibida “Rascunho restaurado.”. Máscaras (CPF, RG, telefone) continuam aplicadas pelo JS ao carregar os valores restaurados.
- **Limpeza:** Ao salvar o viajante com sucesso, a view remove as duas chaves da sessão.
- **Prioridade:** Em edição, se houver rascunho (`kwargs.get('initial')`), o `__init__` do form não sobrescreve com dados da instance (cpf/telefone/rg/cargo), para que o rascunho prevaleça.

---

## 3. Rotas / páginas de gerenciamento

| Rota (name) | Uso |
|-------------|-----|
| `cadastros:veiculo-rascunho-ir-combustiveis` | POST: salva rascunho veículo e redireciona para combustíveis |
| `cadastros:combustivel-lista` | Lista combustíveis; botão “Voltar” usa `return_url` da sessão quando vindo do form de veículo |
| `cadastros:viajante-rascunho-ir-cargos` | POST: salva rascunho viajante e redireciona para cargos |
| `cadastros:viajante-rascunho-ir-unidades` | POST: salva rascunho viajante e redireciona para unidades de lotação |
| `cadastros:cargo-lista` | Lista cargos; “Voltar” usa `return_url` quando vindo do form de viajante |
| `cadastros:unidade-lotacao-lista` | Lista unidades de lotação; “Voltar” usa `return_url` quando vindo do form de viajante |
| `cadastros:unidade-lotacao-cadastrar` | Cadastrar unidade |
| `cadastros:unidade-lotacao-editar` | Editar unidade |
| `cadastros:unidade-lotacao-excluir` | Excluir unidade (bloqueado se houver viajante vinculado) |

Unidades de lotação não estão no menu lateral; acesso apenas por “Gerenciar Unidades de Lotação” na lista ou no formulário de viajantes.

---

## 4. Retorno ao formulário

- **Combustíveis:** Na lista, o botão “Voltar” aponta para `request.session.get('veiculo_form_return_url')` quando existir (ex.: URL do form de veículo). Caso contrário, “Voltar para veículos” (lista de veículos).
- **Cargos:** Na lista, “Voltar” usa `request.session.get('viajante_form_return_url')` quando existir; senão “Voltar para viajantes”.
- **Unidades de lotação:** Na lista, “Voltar” usa o mesmo `viajante_form_return_url` quando existir; senão “Voltar para viajantes”.
- Ao acessar a URL de retorno (formulário), a view detecta rascunho na sessão, preenche o form com `initial` e exibe “Rascunho restaurado.”. Máscaras (viajante) são reaplicadas pelo JS no carregamento.

---

## 5. Placa sem máscara (veículos)

- **Formulário:** Input da placa sem máscara visual; apenas validação (JS: só letras/números, até 7 caracteres, UPPER). Placeholder: “ABC1234 ou ABC1D23”.
- **Backend:** Validação antiga (AAA1234) e Mercosul (AAA1A23); persistência normalizada (UPPER, sem hífen/espaço).
- **Lista e edição:** Exibição igual ao valor salvo (ex.: ABC1234, ABC1D23), sem hífen.

---

## 6. Como testar manualmente

### Veículos
1. Cadastrar ou editar veículo; preencher placa (ex.: ABC1234), modelo, tipo, combustível.
2. Clicar em “Gerenciar combustíveis”: deve aparecer “Rascunho salvo temporariamente.” e ir para a lista de combustíveis.
3. Na lista de combustíveis, clicar em “Voltar”: deve voltar ao formulário de veículo com os dados preenchidos e “Rascunho restaurado.”.
4. Confirmar que a placa aparece sem hífen (ex.: ABC1234) na lista e no form.
5. Salvar o veículo com sucesso: ao ir de novo em “Gerenciar combustíveis” e “Voltar”, o rascunho não deve ser restaurado (sessão limpa).
6. Editar um veículo e alterar o tipo (Caracterizado/Descaracterizado); salvar e conferir na lista.

### Viajantes
1. Cadastrar ou editar viajante; preencher nome, cargo, unidade, CPF/telefone/RG (com máscara).
2. Clicar em “Gerenciar Cargos”: mensagem de rascunho e redirecionamento para a lista de cargos. “Voltar” deve retornar ao form com dados e máscaras.
3. Repetir com “Gerenciar Unidades de Lotação”: redirecionamento para a lista de unidades; “Voltar” restaura o form.
4. Salvar o viajante: rascunho deve ser limpo.
5. Na lista de viajantes, conferir os dois botões: “Gerenciar Cargos” e “Gerenciar Unidades de Lotação”.

### Unidades de lotação
1. Pela lista ou pelo form de viajante, acessar “Gerenciar Unidades de Lotação”.
2. Cadastrar unidade (ex.: “NOVA UNIDADE”); editar e excluir uma que não tenha viajante.
3. Criar um viajante vinculado a uma unidade; tentar excluir essa unidade: deve aparecer mensagem de bloqueio e a unidade permanecer.

---

## 7. Checklist de aceite

| Item | Status |
|------|--------|
| **PART 1 — Veículos** | |
| Placa sem máscara no form; só validação (AAA1234 / AAA1A23) | OK |
| Placa salva e exibida normalizada (UPPER, sem hífen) na lista e edição | OK |
| “Gerenciar combustíveis” salva rascunho e redireciona | OK |
| Voltar da lista de combustíveis restaura rascunho no form | OK |
| Rascunho limpo ao salvar veículo com sucesso | OK |
| Tipo (CARACTERIZADO/DESCARACTERIZADO) editável no form e na listagem | OK |
| **PART 2 — Viajantes** | |
| “Gerenciar Cargos” e “Gerenciar Unidades de Lotação” salvam rascunho e redirecionam | OK |
| Voltar restaura rascunho; máscaras (CPF, RG, telefone) ao restaurar | OK |
| Rascunho limpo ao salvar viajante | OK |
| Lista: botões “Gerenciar Cargos” e “Gerenciar Unidades de Lotação” | OK |
| Form: Cargo e Unidade de Lotação separados, cada um com botão de gerenciamento | OK |
| **PART 3 — Unidades de Lotação** | |
| CRUD: lista, cadastrar, editar, excluir | OK |
| Exclusão bloqueada quando unidade está em uso por viajante | OK |
| Acesso apenas por “Gerenciar Unidades de Lotação” (fora do menu lateral) | OK |
| **PART 4 — Retorno** | |
| Botão “Voltar” nos três gerenciadores leva ao form de origem quando há return_url | OK |
| Mensagens “Rascunho salvo temporariamente” e “Rascunho restaurado” | OK |
| **PART 5 — Testes** | OK |
