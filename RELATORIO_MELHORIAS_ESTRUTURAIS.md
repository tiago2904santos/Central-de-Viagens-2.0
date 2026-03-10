# Relatório – Melhorias Estruturais (Cadastros)

Pacote de padronização aplicado antes do próximo módulo: status, máscaras, querysets operacionais, buscas, exclusões e aviso de rascunho.

---

## 1) Arquivos alterados

### Novos
| Arquivo | Descrição |
|---------|-----------|
| `cadastros/utils/status.py` | Constantes RASCUNHO/FINALIZADO e helpers de label/badge |
| `cadastros/utils/masks.py` | Já existia; foram adicionados `format_phone`, `format_cep` e uso de `only_digits` |
| `templates/cadastros/_aviso_rascunho.html` | Include reutilizável para aviso quando status = RASCUNHO |
| `static/js/masks.js` | Máscaras JS globais (CPF, RG, telefone, CEP, onlyDigits) |

### Alterados
| Arquivo | Alteração |
|---------|-----------|
| `cadastros/templatetags/cadastros_extras.py` | Filtros `status_label` e `status_badge_class` usando `utils.status` |
| `cadastros/forms.py` | Uso de `utils.masks` (format_cpf, format_telefone, format_cep, only_digits); `_viajantes_operacionais_queryset()` e `_veiculos_operacionais_queryset()`; ConfiguracaoSistemaForm e admin usam os querysets operacionais |
| `cadastros/admin.py` | Uso de `_viajantes_operacionais_queryset()` nos inlines de assinaturas |
| `templates/base.html` | Inclusão de `static/js/masks.js` |
| `templates/cadastros/viajantes/lista.html` | Coluna Status com `status_badge_class` e `status_label` |
| `templates/cadastros/viajantes/form.html` | Aviso de rascunho via `{% include 'cadastros/_aviso_rascunho.html' %}` |
| `templates/cadastros/veiculos/lista.html` | Coluna Status com `status_badge_class` e `status_label` |
| `templates/cadastros/veiculos/form.html` | Aviso de rascunho via `{% include 'cadastros/_aviso_rascunho.html' %}` |
| `cadastros/tests/test_cadastros.py` | Uso de `_veiculos_operacionais_queryset`; teste de lista de veículos ajustado para assertar labels "Finalizado"/"Rascunho" em vez de constantes |

---

## 2) Helpers criados

### Status (`cadastros/utils/status.py`)
- **Constantes:** `RASCUNHO`, `FINALIZADO`
- **Funções:**  
  - `get_status_label(status)` → "Rascunho" / "Finalizado" (ou valor desconhecido)  
  - `get_status_badge_class(status)` → `badge bg-warning text-dark` / `badge bg-success` (Bootstrap 5)

### Templatetags (`cadastros/templatetags/cadastros_extras.py`)
- **Filtros:** `{{ obj.status|status_label }}`, `{{ obj.status|status_badge_class }}`

### Máscaras backend (`cadastros/utils/masks.py`)
- `only_digits(s)`
- `format_cpf(digits)`
- `format_telefone(digits)` e alias `format_phone(digits)`
- `format_cep(digits)`
- `format_rg(digits)` (já existia)

### Máscaras frontend (`static/js/masks.js`)
- `Masks.onlyDigits(s)`
- `Masks.formatCpf(digits)`
- `Masks.formatRg(digits)`
- `Masks.formatPhone(digits)`
- `Masks.formatCep(digits)`  
Exposto em `window.Masks`; carregado em `base.html`.

### Querysets operacionais (`cadastros/forms.py`)
- `_viajantes_operacionais_queryset()` → `Viajante.objects.filter(status=FINALIZADO)` (usa constante de `utils.status`)
- `_veiculos_operacionais_queryset()` → `Veiculo.objects.filter(status=FINALIZADO)`  

Usados em: `ConfiguracaoSistemaForm` (choices de viajante/veículo), admin de configuração (inlines de assinaturas) e testes.

---

## 3) O que foi padronizado

| Item | Antes | Depois |
|------|--------|--------|
| **Status** | Strings "RASCUNHO"/"FINALIZADO" e labels/badges repetidos em templates | Constantes em `utils.status`; labels e classes de badge centralizados; listas de viajantes e veículos usam filtros `status_label` e `status_badge_class` |
| **Máscaras backend** | Lógica duplicada em forms (ex.: _format_cpf, _format_telefone, _sanitize_cep) | Uso único em `utils.masks` (format_cpf, format_telefone, format_cep, only_digits) nos forms |
| **Querysets “finalizados”** | `filter(status="FINALIZADO")` em vários pontos | `_viajantes_operacionais_queryset()` e `_veiculos_operacionais_queryset()` reutilizados em form, admin e testes |
| **Aviso de rascunho** | Texto inline em cada formulário de viajante/veículo | Include `_aviso_rascunho.html` com mensagem única: *"Este cadastro está em rascunho e não pode ser usado em outros módulos até ser finalizado. Preencha todos os dados obrigatórios e salve."* |
| **Buscas** | Já existentes por cargo, unidade e combustível | Mantidas; nenhuma alteração necessária |
| **Exclusão** | Mensagens já padronizadas (sucesso + "em uso" quando bloqueado) | Mantidas; verificação de consistência (cargos, unidades, combustíveis, veículos, viajantes) |

---

## 4) Como testar manualmente

1. **Status na lista**  
   - Lista de Viajantes e de Veículos: coluna Status deve exibir "Rascunho" (badge amarelo) ou "Finalizado" (badge verde), sem strings "RASCUNHO"/"FINALIZADO" cruas.

2. **Aviso de rascunho**  
   - Editar um viajante ou veículo com status Rascunho: deve aparecer o alerta amarelo com o texto do include.  
   - Salvar como Finalizado e reabrir: o aviso não deve aparecer.

3. **Máscaras (backend)**  
   - Cadastro/Configuração: CPF, telefone e CEP salvos/exibidos formatados (pontos, hífens, parênteses) conforme `utils.masks`.

4. **Querysets operacionais**  
   - Configurações do sistema: nos campos de assinatura (viajante) e onde houver escolha de veículo, devem aparecer apenas viajantes e veículos com status Finalizado.

5. **Buscas**  
   - Viajantes: buscar por nome de cargo ou unidade de lotação.  
   - Veículos: buscar por nome de combustível.

6. **Exclusão**  
   - Cargo/Unidade/Combustível em uso: tentar excluir e verificar mensagem do tipo "Não é possível excluir ... pois está em uso por ...".  
   - Excluir quando não estiver em uso: mensagem de sucesso "excluído(a) com sucesso".

7. **JS de máscaras**  
   - Abrir um formulário que use CPF/telefone/CEP; conferir no `base.html` que `masks.js` está carregado. Formulários podem continuar com lógica inline onde já existia; o JS global fica disponível para novos usos.

---

## 5) Checklist de aceite

| Critério | Status |
|----------|--------|
| Status centralizado (RASCUNHO/FINALIZADO) em `utils.status` | OK |
| Labels e badges de status reutilizados em Viajantes e Veículos (templatetags) | OK |
| Helpers de máscara no backend em `cadastros/utils/masks.py` (only_digits, format_cpf, format_rg, format_phone, format_cep) | OK |
| JS global `static/js/masks.js` com funções equivalentes e carregado em `base.html` | OK |
| Querysets `_viajantes_operacionais_queryset` e `_veiculos_operacionais_queryset` criados e usados (form, admin, testes) | OK |
| Buscas: viajantes por cargo/unidade; veículos por combustível (já existentes, mantidas) | OK |
| Mensagens de exclusão consistentes (sucesso + "em uso" quando bloqueado) | OK |
| Aviso de rascunho padronizado (include reutilizável em formulários de Viajante e Veículo) | OK |
| Testes automatizados passando (incl. status na lista e querysets operacionais) | OK |
| Nenhum módulo novo criado; sem mudança de regra de negócio nem de navegação principal | OK |

**Pendente (opcional):**  
- Refatorar formulários que ainda usam máscaras inline para usar `window.Masks` onde for desejável (não obrigatório para este pacote).

---

*Relatório gerado após implementação do pacote de melhorias estruturais.*
