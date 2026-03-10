# Relatório — Cadastro de Veículos e Combustíveis

## Resumo

Implementado o cadastro de **Veículos** (placa antiga e Mercosul, modelo em maiúsculo, combustível como FK, tipo Caracterizado/Descaracterizado) e o gerenciador de **Combustíveis** (igual Cargos: um único padrão, bloqueio de exclusão se em uso). Placa sempre exibida formatada (lista, edição e máscara ao digitar). Sem prefixo, patrimônio ou observações.

---

## 1. Models e migrations

### CombustivelVeiculo (`cadastros/models.py`)
- **nome** — CharField(max_length=60, unique=True), normalizado no `save()` (strip + UPPER + colapsar espaços)
- **is_padrao** — BooleanField(default=False); no `save()`, se `is_padrao=True`, os demais são desmarcados
- **created_at**, **updated_at**

### Veiculo
- **placa** — CharField(10, unique), persistida sem hífen/espaço, UPPER (antiga: ABC1234, mercosul: ABC1D23)
- **modelo** — CharField(120), UPPER no `save()`
- **combustivel** — FK(CombustivelVeiculo, null=True, blank=True, on_delete=SET_NULL, related_name='veiculos')
- **tipo** — CharField(20, choices CARACTERIZADO/DESCARACTERIZADO, default=CARACTERIZADO)
- **created_at**, **updated_at**
- Removidos: prefixo, ativo

### Migrations
- **0015_combustivel_veiculo.py** — CreateModel CombustivelVeiculo
- **0016_veiculo_combustivel_fk_refactor.py** — AddField combustivel_fk; RunPython (cria CombustivelVeiculo a partir dos textos de combustível existentes e associa); RemoveField combustivel (CharField); RenameField combustivel_fk → combustivel; RemoveField prefixo e ativo; AddField tipo (default CARACTERIZADO); AlterField modelo max_length=120

---

## 2. Rotas criadas

| Rota | Método | Nome | Descrição |
|------|--------|------|-----------|
| `/cadastros/veiculos/` | GET | veiculo-lista | Lista de veículos |
| `/cadastros/veiculos/cadastrar/` | GET, POST | veiculo-cadastrar | Cadastro |
| `/cadastros/veiculos/<pk>/editar/` | GET, POST | veiculo-editar | Edição |
| `/cadastros/veiculos/<pk>/excluir/` | GET, POST | veiculo-excluir | Confirmação e exclusão |
| `/cadastros/veiculos/combustiveis/` | GET | combustivel-lista | Lista de combustíveis |
| `/cadastros/veiculos/combustiveis/cadastrar/` | GET, POST | combustivel-cadastrar | Cadastro |
| `/cadastros/veiculos/combustiveis/<pk>/editar/` | GET, POST | combustivel-editar | Edição |
| `/cadastros/veiculos/combustiveis/<pk>/excluir/` | GET, POST | combustivel-excluir | Confirmação e exclusão (bloqueada se em uso) |
| `/cadastros/veiculos/combustiveis/<pk>/definir-padrao/` | POST | combustivel-definir-padrao | Define como padrão |

---

## 3. Máscara da placa

### Ao digitar (form)
- **JavaScript** em `cadastros/veiculos/form.html`: apenas letras e números (até 7), UPPER; formato antigo (3 letras + 4 dígitos) recebe hífen após a 3ª letra → ex.: `ABC1234` vira `ABC-1234`; Mercosul (3 letras + 1 dígito + 1 letra + 2 dígitos) permanece sem hífen → `ABC1D23`.
- Envio: o valor pode ir com ou sem hífen; no backend `clean_placa` usa `_normalizar_placa` (remove hífen e espaços) e grava normalizado.

### No GET de edição
- No `VeiculoForm.__init__`, para instância existente (e sem POST), é definido `self.initial['placa'] = format_placa(self.instance.placa)`.
- **format_placa** (em `cadastros/utils/masks.py`): antiga → `ABC-1234`; mercosul → `ABC1D23`.
- O template usa um input com `value="{% firstof form.initial.placa form.placa.value '' %}"`, então a placa já aparece formatada ao abrir o formulário de edição.

### Na lista
- Na view `veiculo_lista`, cada objeto recebe `obj.placa_display = format_placa(obj.placa)`.
- O template lista usa `{{ obj.placa_display }}`, exibindo sempre ABC-1234 ou ABC1D23.

### Validação no backend
- **clean_placa**: normaliza; exige 7 caracteres; regex antiga `^[A-Z]{3}[0-9]{4}$` ou mercosul `^[A-Z]{3}[0-9][A-Z][0-9]{2}$`; unicidade (excluindo o próprio registro na edição).

---

## 4. Padrão de combustível

- **Um único padrão:** no `save()` de `CombustivelVeiculo`, se `is_padrao=True`, é executado `CombustivelVeiculo.objects.exclude(pk=self.pk).update(is_padrao=False)`.
- **Definir como padrão (lista):** a view `combustivel_definir_padrao` (POST) desmarca os demais e marca o escolhido.
- **Form de novo veículo:** no `VeiculoForm.__init__`, se for novo e não houver dados POST, o combustível padrão (`CombustivelVeiculo.objects.filter(is_padrao=True).first()`) é colocado em `initial['combustivel']`.
- **Exclusão:** a view `combustivel_excluir` verifica `obj.veiculos.exists()`; se existir veículo usando o combustível, a exclusão é bloqueada e uma mensagem de erro é exibida.

---

## 5. Como testar manualmente

1. **Login** e acessar Cadastros → Veículos.
2. **Combustíveis:** em “Gerenciar combustíveis”, cadastrar (ex.: GASOLINA, DIESEL). Marcar um como “Definir como padrão”. Na lista, usar “Definir como padrão” em outro e conferir que só o último fica com o badge “Padrão”. Tentar excluir um combustível usado por um veículo e conferir bloqueio e mensagem.
3. **Veículos:** Cadastrar com placa antiga (ex.: ABC-1234) e com Mercosul (ex.: ABC1D23). Conferir modelo em maiúsculo e combustível como select (padrão preselecionado se houver). Na lista, conferir placa formatada (ABC-1234 ou ABC1D23). Editar e conferir placa formatada no campo. Tentar placa inválida (ex.: 1234567) e duplicada; conferir mensagens. Excluir um veículo e conferir que foi removido.
4. **Menu:** Veículos → Lista e Cadastrar devem abrir as telas corretas; Combustíveis não aparece no menu, apenas via “Gerenciar combustíveis” na lista de veículos.

---

## 6. Checklist de aceite

| Item | Status |
|------|--------|
| CombustivelVeiculo: nome único, is_padrao, só um padrão no save | OK |
| Veiculo: placa, modelo, combustivel FK, tipo; sem prefixo/ativo | OK |
| Placa: antiga (ABC1234) e Mercosul (ABC1D23); validação regex | OK |
| Placa formatada ao digitar (máscara com hífen no antigo) | OK |
| Placa formatada no GET editar e na lista | OK |
| Modelo em maiúsculo (front e backend) | OK |
| Combustível: select; padrão preselecionado em novo veículo | OK |
| Tipo: select Caracterizado / Descaracterizado | OK |
| Rotas veículos e combustíveis (lista, cadastrar, editar, excluir, definir-padrao) | OK |
| Templates em cadastros/veiculos/ (lista, form, excluir, combustiveis_*) | OK |
| Lista veículos: placa formatada, modelo, combustível, tipo; busca; Editar/Excluir | OK |
| Botão “Gerenciar combustíveis” na lista e no form de veículo | OK |
| Combustíveis: lista com badge Padrão; Voltar para veículos; Definir padrão, Editar, Excluir | OK |
| Exclusão de combustível bloqueada se em uso | OK |
| Menu: Veículos habilitado (Lista, Cadastrar); combustíveis fora do menu | OK |
| Admin: Veiculo e CombustivelVeiculo com list_display e search_fields | OK |
| Testes: placa antiga/mercosul, inválida, duplicada, formatada na lista/editar, excluir, combustível CRUD/padrão/bloqueio, preseleção padrão | OK |
