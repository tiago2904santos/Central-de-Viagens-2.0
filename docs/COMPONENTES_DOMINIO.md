# Componentes de dominio

## Congelamento provisorio (aceite arquitetural)

**Roteiros** e o modulo **referencia provisorio** para estes blocos de dominio:

- destinos (sede + pernas);
- trechos;
- retorno;
- calculadora / diarias no wizard;
- resumo de rota (leitura).

Proximos modulos devem **reaproveitar este padrao** (selectors/services/presenters + `templates/components/domain/` + `domain.css`) onde o conceito for o mesmo.

**Regra:** quando o **segundo** modulo passar a usar o mesmo bloco na pratica, pode ser necessaria **nova extracao** (HTML/CSS) a partir dos partials de Roteiros — isso nao invalida o padrao atual; apenas marca o momento de fundir duplicacao real.

---

Roteiros e o **modulo referencia**: os blocos abaixo devem ser reutilizados por Oficios, Planos, OS, etc., quando o fluxo exigir os mesmos conceitos (sem acoplar modelo `Roteiro` na camada de template além do contrato documentado).

Convencoes globais:

- Nao consultar banco no component.
- Nao calcular rota nem diarias no component.
- Nao salvar dados no component.
- Sem `href="#"`, sem CSS inline, sem JS inline.
- Parametros opcionais: `title`, `description`, `readonly`, `empty_message`, `actions` (quando o partial filho suportar).

CSS: `static/css/domain.css` + estilos do form em `roteiros.css` quando o partial usar `roteiro-editor__*`.

---

## sede_destinos.html

**Objetivo:** Bloco de sede (origem) e lista de destinos do wizard.

**Quando usar:** Formularios que replicam o passo "sede + destinos" do legacy.

**Parametros:** Herdados do contexto do formulario (`form`, `destinos_atuais`, `estados`, `step3_state`, `destino_estado_fixo_*`, etc.) via `roteiros/partials/roteiro/sede_destinos.html`.

**Exemplo:**

```django
{% include "components/domain/sede_destinos.html" %}
```

**Nao deve:** Executar queries; depender de URL nomeada fora do contexto ja montado pelo presenter/logica.

**Paginas agora:** Wizard avulso em `roteiros/partials/roteiro_form.html`.

**Paginas futuras:** Oficios (step roteiro), Planos com deslocamento, OS com trechos.

---

## destinos.html

**Objetivo:** Ponto unico de include para o bloco de destinos (hoje delega ao mesmo partial de sede+destinos usado no wizard).

**Quando usar:** Quando um modulo quiser so o bloco de destinos sem renomear paths internos; hoje equivalente a `sede_destinos` no fluxo atual.

**Parametros:** Mesmos de `sede_destinos.html` (contexto do form).

**Exemplo:**

```django
{% include "components/domain/destinos.html" %}
```

**Nao deve:** Introduzir HTML divergente do partial canon sem atualizar documentacao.

**Paginas agora:** Inclusao indireta via `destinos` == `sede_destinos` no mesmo form.

**Paginas futuras:** Telas que listem apenas pernas de destino com o mesmo markup.

---

## trechos.html

**Objetivo:** Secao de trechos (tabela dinamica, estimativa, IDs de cidade).

**Quando usar:** Qualquer form que monte trechos com o mesmo contrato POST do legacy.

**Parametros:** Contexto do wizard (`trechos`, `trechos_json`, `initial_trechos_data`, URLs em `data-*` no form pai).

**Exemplo:**

```django
{% include "components/domain/trechos.html" %}
```

**Nao deve:** Chamar API diretamente no template; o JS global le `data-url-trechos-estimar` do form.

**Paginas agora:** `roteiro_form.html`.

**Paginas futuras:** Oficios step 3, documentos com trechos persistidos.

---

## trecho_card.html

**Objetivo:** Card de leitura de um `RoteiroTrecho` (ordem, tipo, origem/destino, datas, distancia).

**Quando usar:** Detalhe de roteiro ou listagem compacta de trechos persistidos.

**Parametros:**

- `trecho` — instancia com `get_tipo_display`, FKs de cidade/estado, `saida_dt`, `chegada_dt`, `distancia_km`.

**Exemplo:**

```django
{% include "components/domain/trecho_card.html" with trecho=trecho only %}
```

**Nao deve:** Gerar links de edicao sem URL real; nao embutir regra de negocio.

**Paginas agora:** `roteiros/detail.html`.

**Paginas futuras:** Resumo em Oficio, OS, relatorios.

---

## retorno.html

**Objetivo:** Secao "Retorno final" (datas, cidade de saida readonly, campos de chegada).

**Quando usar:** Wizard com retorno simetrico ao legacy.

**Parametros:** `retorno_state` (dict no contexto do form).

**Exemplo:**

```django
{% include "components/domain/retorno.html" %}
```

**Nao deve:** Duplicar o partial (uma unica inclusao).

**Paginas agora:** `roteiro_form.html`.

**Paginas futuras:** Fluxos com retorno obrigatorio no mesmo modelo mental.

---

## calculadora_rota.html

**Objetivo:** Painel de diarias e resumo financeiro (include do partial de diarias).

**Quando usar:** Apos trechos/retorno no wizard, quando o POST expoe campos de diarias.

**Parametros:** `step3_diarias_resultado`, IDs e campos hidden ja definidos no form pai.

**Exemplo:**

```django
{% include "components/domain/calculadora_rota.html" %}
```

**Nao deve:** Substituir o endpoint `calcular_diarias`; apenas exibe e envia campos.

**Paginas agora:** `roteiro_form.html`.

**Paginas futuras:** Qualquer tela que reuse o mesmo bloco de diarias periodizadas.

---

## resumo_rota.html

**Objetivo:** Resumo estatico (origem, quantidade de trechos, diarias, observacoes).

**Quando usar:** Pagina de detalhe ou preview read-only.

**Parametros:**

- `roteiro` — instancia persistida.
- `trechos` — iterable (para `length`).

**Exemplo:**

```django
{% include "components/domain/resumo_rota.html" with roteiro=roteiro trechos=trechos only %}
```

**Nao deve:** Exibir `updated_at` ou "Atualizado em".

**Paginas agora:** `roteiros/detail.html`.

**Paginas futuras:** Cabecalho de resumo em impressao/PDF de documentos de viagem.
