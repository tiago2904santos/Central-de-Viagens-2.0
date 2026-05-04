# Legado V2

## O que e o legado V2

O legado V2 e o projeto anterior da Central de Viagens, disponivel em:

https://github.com/tiago2904santos/Central-de-Viagens-2.0.git

Ele deve ser usado apenas como referencia funcional, visual e de regras de negocio para a construcao da Central de Viagens 3.0.

## Regra principal

A V2 nao deve ser copiada inteira para a V3.

Nao importar automaticamente codigo da V2. Nao copiar apps antigos inteiros, templates gigantes, CSS antigo inteiro, JS antigo, scripts soltos ou migrations antigas. O legado existe para validar comportamento esperado, nomes de campos, fluxos e regras de negocio, nao para definir a arquitetura da V3.

## Diretrizes para a V3

A V3 deve nascer limpa, componentizada e document-centric.

Na V2, o app `eventos` concentrava responsabilidades demais. Esse desenho nao deve ser repetido. Na V3, `Evento` deve ser apenas um agrupador opcional, nao o centro obrigatorio de todos os documentos e fluxos.

`Roteiro` na V3 deve ser reutilizavel e nao preso a uma estrutura monolitica de evento. Cada documento deve ter app e CRUD proprios, com services, forms, templates e regras isoladas conforme a necessidade do dominio.

CSS e JS inline da V2 nao devem ser repetidos. Templates gigantes da V2 nao devem ser migrados diretamente. Scripts soltos da V2 nao devem ser trazidos para a nova base. Migrations da V2 nao devem ser copiadas ou misturadas com migrations da V3.

A V2 deve servir para validar comportamento, nao arquitetura.

## Remote Git

O repositorio legado deve ser configurado como remote chamado `legacy-v2`:

```bash
git remote add legacy-v2 https://github.com/tiago2904santos/Central-de-Viagens-2.0.git
git fetch legacy-v2
```

Nao fazer merge, rebase ou checkout do legado por cima da branch atual da V3.

## Consulta local opcional

Se o desenvolvedor quiser ter o legado lado a lado para consulta local, deve clonar manualmente em uma pasta ignorada pelo Git:

```bat
mkdir .legacy
git clone https://github.com/tiago2904santos/Central-de-Viagens-2.0.git .legacy/Central-de-Viagens-2.0
```

A pasta `.legacy/` nao deve ser versionada.

Tambem existem scripts auxiliares opcionais:

```bat
scripts\dev\clone_legacy_v2.bat
scripts\dev\update_legacy_v2.bat
```

Esses scripts servem apenas para consulta local e nao afetam a V3.

## Mapa de consulta

- Cadastros antigos:
  consultar `cadastros/models.py`, `cadastros/forms.py` e `cadastros/views.py` da V2.

- Oficios antigos:
  consultar `eventos/models.py`, `eventos/views.py`, `eventos/views_global.py` e `templates/eventos/oficio/` da V2.

- Roteiros antigos:
  consultar `RoteiroEvento`, `RoteiroEventoDestino` e trechos em `eventos/models.py` da V2.

- Termos antigos:
  consultar `TermoAutorizacao`, `eventos/termos.py` e `templates/eventos/documentos/termos*` da V2.

- Justificativas antigas:
  consultar `Justificativa`, `ModeloJustificativa` e services de justificativa da V2.

- Plano de Trabalho antigo:
  consultar `PlanoTrabalho`, `PlanoTrabalhoForm`, `views_global.py` e `templates/eventos/documentos/planos_trabalho_form.html` da V2.

- Ordem de Servico antiga:
  consultar `OrdemServico`, `OrdemServicoForm` e `templates/eventos/documentos/ordens_servico_form.html` da V2.

- Geracao documental:
  consultar `eventos/services/documentos/` da V2.

- CSS antigo:
  consultar `static/css/style.css` da V2 apenas como referencia visual, nao copiar inteiro.

- JS antigo:
  consultar `static/js/` da V2 apenas para entender comportamento.
