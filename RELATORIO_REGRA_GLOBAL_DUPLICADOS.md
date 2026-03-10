# Relatório — Regra global: proibir informações repetidas (Cargos, Viajantes, Veículos)

## Resumo

Implementada validação de unicidade com normalização em Cargos (nome), Viajantes (nome, CPF, RG, telefone) e Veículos (placa). Validação no backend (forms/model) e, quando aplicável, constraints no banco. Ao editar, o próprio registro é excluído da checagem de duplicidade.

---

## 1. Constraints criadas (models)

### Cargo
- **Já existia:** `nome` com `unique=True` no campo.
- Nenhuma constraint nova; nome continua único e normalizado em `save()`.

### Viajante (`cadastros/models.py`)
- **nome:** `CharField(..., unique=True)` — único por nome (sempre normalizado em maiúsculo no `save()`).
- **cpf:** `UniqueConstraint(fields=['cpf'], condition=Q(cpf__gt=''), name='cadastros_viajante_cpf_unique')` — único quando preenchido.
- **rg:** `UniqueConstraint(fields=['rg'], condition=Q(rg__gt='') & ~Q(rg='NAO POSSUI RG'), name='cadastros_viajante_rg_unique')` — único quando preenchido e diferente de "NAO POSSUI RG".
- **telefone:** `UniqueConstraint(fields=['telefone'], condition=Q(telefone__gt=''), name='cadastros_viajante_telefone_unique')` — único quando preenchido.

### Veículo
- **Já existia:** `placa` com `unique=True`.
- Nenhuma constraint nova; placa é normalizada em `save()` (sem espaços/hífens, UPPER).

---

## 2. Validações nos forms

### CargoForm (`cadastros/forms.py`)
- **clean_nome:** normaliza (strip + UPPER + colapsar espaços), valida obrigatório e unicidade. Exclui `self.instance.pk` ao editar. Mensagem: *"Já existe um cargo com este nome."*

### ViajanteForm
- **clean_nome:** normaliza (strip + UPPER + colapsar espaços), valida obrigatório e unicidade (exclui próprio registro). Mensagem: *"Já existe um cadastro com este nome."*
- **clean_cpf:** além da validação de formato e dígitos verificadores, valida unicidade (exclui próprio registro). Mensagem: *"Já existe um cadastro com este CPF."*
- **clean_rg:** quando não é "NAO POSSUI RG", valida unicidade do RG normalizado (só dígitos), excluindo próprio registro. Mensagem: *"Já existe um cadastro com este RG."*
- **clean_telefone:** valida formato (10/11 dígitos) e unicidade (exclui próprio registro). Mensagem: *"Já existe um cadastro com este telefone."*

### VeiculoForm
- **clean_placa:** normaliza com `_normalizar_placa` (remove espaços e hífens, UPPER), valida obrigatório e unicidade (exclui próprio registro). Mensagem: *"Já existe um cadastro com esta placa."*

---

## 3. Normalizações aplicadas e onde

| Campo / Modelo | Onde | Regra |
|----------------|------|--------|
| **Cargo.nome** | Model `save()` + `CargoForm.clean_nome` | strip + colapsar espaços + UPPER |
| **Viajante.nome** | Model `save()` + `ViajanteForm.clean_nome` | strip + colapsar espaços + UPPER |
| **Viajante.cpf** | Form `clean_cpf` (e máscaras) | only_digits (11 dígitos) |
| **Viajante.rg** | Form `clean_rg` | only_digits quando não "NAO POSSUI RG" |
| **Viajante.telefone** | Form `clean_telefone` | only_digits (10 ou 11) |
| **Veiculo.placa** | Model `save()` + `VeiculoForm.clean_placa` (função `_normalizar_placa`) | remove espaços e hífens + UPPER; salva sem hífen (ex.: ABC1D23) |

---

## 4. Migrations

### 0011_normalizar_dados_unicos.py (dados)
- **Tipo:** `RunPython`
- **Função:** normalizar dados já existentes:
  - **Cargo:** `nome` → strip + UPPER + colapsar espaços.
  - **Viajante:** `nome` (idem), `cpf`/`rg`/`telefone` → only_digits (rg só quando não for "NAO POSSUI RG").
  - **Veiculo:** `placa` → sem espaços/hífens, UPPER.
- **Reversão:** `reverter` é no-op.

### 0012_viajante_unique_constraints.py (schema)
- **AlterField:** `Viajante.nome` → `unique=True`.
- **AddConstraint:** `cadastros_viajante_rg_unique` (condition: rg não vazio e ≠ "NAO POSSUI RG").
- **AddConstraint:** `cadastros_viajante_telefone_unique` (condition: telefone não vazio).
- **Dependência:** 0011 (para dados já normalizados antes de aplicar unique/constraints).

**Comando:** `python manage.py migrate cadastros`

---

## 5. UI

- Erros de duplicidade aparecem no campo correspondente (form errors).
- Mensagens são as descritas acima; Django messages não foram alterados (opcional conforme escopo).

---

## 6. Testes criados/ajustados

### Cargo
- `test_cargo_nome_duplicado_rejeitado`: não permite nome duplicado (ex.: "  analista  " e "ANALISTA" com cargo já "ANALISTA").
- `test_cargo_editar_mesmo_nome_nao_acusa_duplicado`: editar mantendo o mesmo nome não acusa duplicidade.

### Viajante
- `test_viajante_nome_duplicado_rejeitado`: nome duplicado (normalizado) rejeitado.
- `test_viajante_cpf_duplicado_rejeitado`: CPF duplicado rejeitado.
- `test_viajante_rg_duplicado_rejeitado`: RG duplicado rejeitado.
- `test_viajante_telefone_duplicado_rejeitado`: telefone duplicado rejeitado.
- `test_viajante_editar_mesmo_nome_nao_acusa_duplicado`: editar mantendo o mesmo nome não acusa duplicidade.
- `test_viajante_editar_mesmo_cpf_nao_acusa_duplicado`: editar mantendo o mesmo CPF não acusa duplicidade.

### Veículo
- `test_veiculo_placa_duplicada_rejeitada`: placa duplicada rejeitada (ABC-1D23 e abc1d23 considerados iguais).
- `test_veiculo_placa_normalizada_salva`: placa salva normalizada (ex.: ABC-1D23 → ABC1D23).
- `test_veiculo_editar_mesma_placa_nao_acusa_duplicado`: editar mantendo a mesma placa não acusa duplicidade.

Rotas de veículos usadas nos testes: `veiculo-lista`, `veiculo-cadastrar`, `veiculo-editar` em `cadastros/urls.py`.

---

## 7. Como testar manualmente

1. **Cargos**
   - Cadastrar cargo "ANALISTA". Tentar cadastrar outro "analista" ou "  ANALISTA  " → deve exibir "Já existe um cargo com este nome."
   - Editar um cargo sem mudar o nome → deve salvar sem erro.

2. **Viajantes**
   - Cadastrar viajante com CPF 529.982.247-25. Cadastrar outro com o mesmo CPF → "Já existe um cadastro com este CPF."
   - Repetir para RG (ex.: 12.345.678-9) e telefone (ex.: (41) 99999-8888).
   - Cadastrar "João Silva"; tentar outro "joão silva" → "Já existe um cadastro com este nome."
   - Editar um viajante mantendo nome, CPF, RG ou telefone → deve salvar sem erro.

3. **Veículos**
   - Cadastrar veículo com placa ABC-1D23. Tentar outro com "ABC-1D23" ou "abc1d23" → "Já existe um cadastro com esta placa."
   - Verificar na lista/admin que a placa aparece normalizada (ex.: ABC1D23).
   - Editar veículo mantendo a mesma placa (ex.: "XYZ-1234" para placa já "XYZ1234") → deve salvar sem erro.

---

## 8. Checklist de aceite

| Item | Status |
|------|--------|
| Validação no backend (forms/model) | OK |
| Constraints no banco (Viajante: nome, cpf, rg, telefone) | OK |
| Normalização nome (Cargo, Viajante): strip + UPPER + colapsar espaços | OK |
| Normalização cpf/rg/telefone: only_digits | OK |
| Normalização placa: sem espaços/hífens, UPPER | OK |
| Mensagens de erro claras por campo | OK |
| Edição não acusa duplicidade contra o próprio registro | OK |
| Migração de dados 0011 (normalizar existentes) | OK |
| Migração de schema 0012 (unique nome + constraints rg/telefone) | OK |
| Testes Cargo (nome duplicado + editar mesmo nome) | OK |
| Testes Viajante (nome, cpf, rg, telefone duplicados + editar) | OK |
| Testes Veículo (placa duplicada, normalização, editar mesma placa) | OK |

---

## 9. Arquivos alterados/criados

- **cadastros/models.py:** Viajante.nome `unique=True`; constraints rg e telefone; Veiculo.save() normalizando placa; `import re`.
- **cadastros/forms.py:** CargoForm.clean_nome (reforço); ViajanteForm.clean_nome (unicidade), clean_cpf/clean_rg/clean_telefone (unicidade); remoção da duplicidade de CPF do clean(); VeiculoForm.clean_placa + _normalizar_placa.
- **cadastros/migrations/0011_normalizar_dados_unicos.py:** migração de dados (RunPython).
- **cadastros/migrations/0012_viajante_unique_constraints.py:** AlterField nome unique + AddConstraint rg e telefone.
- **cadastros/urls.py:** rotas veiculo-lista, veiculo-cadastrar, veiculo-editar (para testes e uso futuro).
- **cadastros/tests/test_cadastros.py:** testes de duplicidade para Cargo, Viajante e Veículo (create + edit).
