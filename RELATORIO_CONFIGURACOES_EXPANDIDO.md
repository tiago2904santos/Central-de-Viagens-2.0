# Relatório — Expansão da aba Configurações do sistema

## 1. Campos adicionados no model + migration

### Model `ConfiguracaoSistema` (cadastros/models.py)

**Cabeçalho (sempre maiúsculo, server-side):**
- `divisao` — CharField, max_length=120, blank=True, default=''
- `unidade` — CharField, max_length=120, blank=True, default=''

**Rodapé — Endereço (preenchido via CEP):**
- `cep` — CharField, max_length=9, blank=True, default='' (formato 00000-000)
- `logradouro` — CharField, max_length=160, blank=True, default=''
- `bairro` — CharField, max_length=120, blank=True, default=''
- `cidade_endereco` — CharField, max_length=120, blank=True, default='' (Cidade do endereço)
- `uf` — CharField, max_length=2, blank=True, default=''
- `numero` — CharField, max_length=20, blank=True, default=''

**Contato:**
- `telefone` — CharField, max_length=20, blank=True, default=''
- `email` — EmailField, blank=True, default=''

**Assinaturas (FK Viajante, null=True, blank=True, on_delete=SET_NULL):**
- `assinatura_oficio_1` — Assinatura Ofícios 1
- `assinatura_oficio_2` — Assinatura Ofícios 2
- `assinatura_justificativas` — Assinatura Justificativas
- `assinatura_planos_trabalho` — Assinatura Planos de Trabalho
- `assinatura_ordens_servico` — Assinatura Ordens de Serviço

**Migration:** `cadastros/migrations/0003_expand_configuracao_sistema.py`

---

## 2. Rotas criadas (API CEP)

| Método | Rota | Nome | Descrição |
|--------|------|------|-----------|
| GET | `/cadastros/api/cep/<cep>/` | `cadastros:api-consulta-cep` | Consulta ViaCEP; autenticado; retorna JSON padronizado ou 400/404 |

**Comportamento da API CEP:**
- Sanitiza o CEP (remove não dígitos).
- Se não tiver 8 dígitos → **400** com `{ "erro": "CEP deve ter 8 dígitos." }`.
- Chama ViaCEP (`https://viacep.com.br/ws/<cep>/json/`) com timeout 5s.
- Se ViaCEP retornar `erro: true` → **404** com `{ "erro": "CEP não encontrado." }`.
- Sucesso → **200** com `{ "cep", "logradouro", "bairro", "cidade", "uf" }` (campo `cidade` mapeado de `localidade` do ViaCEP).

---

## 3. Máscaras (CEP, telefone, uppercase)

**DIVISÃO e UNIDADE (client-side):**
- No `input`, evento `input`: `this.value = this.value.toUpperCase()`.
- Persistência em maiúsculo é garantida no servidor em `clean_divisao` e `clean_unidade` (`.strip().upper()`).

**CEP:**
- Máscara na digitação: só números; ao atingir 6+ dígitos exibe hífen (formato `00000-000`).
- Ao **blur** ou ao completar **8 dígitos** no `input`: chama `GET /cadastros/api/cep/<cep>/` e preenche logradouro, bairro, cidade (endereço), UF.
- Erro da API (400/404/502): mensagem exibida em um `div` de alerta (`#cep-erro-alert`) acima do formulário.

**TELEFONE:**
- Máscara na digitação: só números; formatação progressiva:
  - até 2 dígitos → `(XX`
  - até 6 → `(XX) XXXX`
  - até 10 → `(XX) XXXX-XXXX`
  - até 11 → `(XX) XXXXX-XXXX`
- Validação no servidor: 10 ou 11 dígitos (apenas números).

Implementação em JS puro, sem bibliotecas externas, no template `templates/cadastros/configuracao_form.html`.

---

## 4. Preenchimento automático por CEP

1. Usuário informa o CEP (com ou sem hífen).
2. Ao sair do campo (blur) ou ao digitar o 8º dígito, o front chama a API interna `GET /cadastros/api/cep/<cep>/`.
3. A view sanitiza o CEP, valida 8 dígitos e chama o ViaCEP.
4. Resposta 200: o JS preenche os campos `logradouro`, `bairro`, `cidade_endereco`, `uf` e atualiza o campo `cep` com o formato retornado.
5. Resposta 400/404/502: o JS exibe a mensagem de `erro` no `#cep-erro-alert`.
6. Ao salvar o formulário, todos os campos de endereço (incluindo os preenchidos pelo CEP) são validados e persistidos no singleton.

---

## 5. Testes criados e como rodar

**Novos/ajustes em `cadastros/tests/test_cadastros.py`:**

- **ConfiguracoesViewTest**
  - `test_configuracoes_post_atualiza_singleton` — POST com payload completo (novos campos vazios ou preenchidos) e verificação de persistência.
  - `test_configuracoes_post_divisao_unidade_maiusculo` — garante que `divisao` e `unidade` são salvos em MAIÚSCULO.
  - `test_configuracoes_post_telefone_valido` — telefone 11 dígitos é salvo.
  - `test_configuracoes_post_cep_valido_salva` — CEP 8 dígitos é salvo no formato `00000-000`.
  - `test_configuracoes_post_assinatura_oficio_1_salva_fk` — seleção de viajante em `assinatura_oficio_1` persiste a FK.

- **ApiConsultaCepTest** (mock de `requests.get`, sem chamada real ao ViaCEP):
  - `test_api_cep_requer_login` — não autenticado → 302.
  - `test_api_cep_invalido_retorna_400` — CEP com menos de 8 dígitos → 400.
  - `test_api_cep_nao_encontrado_retorna_404` — ViaCEP retorna `erro: true` → 404.
  - `test_api_cep_valido_retorna_200_json` — ViaCEP retorna endereço → 200 e JSON com `cep`, `logradouro`, `bairro`, `cidade`, `uf`.

**Como rodar:**

```bash
python manage.py test cadastros.tests.test_cadastros
```

Ou apenas os testes de configurações e da API CEP:

```bash
python manage.py test cadastros.tests.test_cadastros.ConfiguracoesViewTest cadastros.tests.test_cadastros.ApiConsultaCepTest
```

---

## 6. Checklist de aceite

| Critério | Status |
|----------|--------|
| Configurações salva Divisão/Unidade sempre em maiúsculo (server-side + client-side) | OK |
| CEP preenche automaticamente endereço e persiste os dados | OK |
| Telefone e e-mail validados (10/11 dígitos; EmailField) | OK |
| Assinaturas selecionam Viajantes do banco e salvam no singleton | OK |
| API CEP: 400 (inválido), 404 (não encontrado), 200 (JSON) com mock em testes | OK |
| Testes passam | OK |
| Menu/Sidebar: apenas Painel e Configurações habilitados | OK (mantido) |

---

## 7. Dependência

- **requests** adicionado em `requirements.txt` para a consulta ao ViaCEP na API de CEP.
