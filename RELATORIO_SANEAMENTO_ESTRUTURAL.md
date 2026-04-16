# Relatório de saneamento estrutural

- Camada central de vínculos documentais criada em `eventos/services/documento_vinculos.py`.
- Fluxos de Ordem de Serviço e Ofício passaram a consumir vínculos diretos e herdados de forma explícita.
- Formulários de Termo de Autorização passaram a limitar vínculo a um único ofício por termo.
- Foram adicionados testes de regressão para cardinalidade e herança de vínculos.

## Fase 2

- Termo de autorização saneado para vínculo canônico de ofício, com migração de reconciliação em `eventos/migrations/0052_termoautorizacao_saneia_oficio_canonico.py`.
- Extração de selectors documentais de `views_global.py` para `eventos/services/documento_selectors.py`.
- Tela de detalhe de evento voltou a ser página real com bloco de vínculos documentais, usando resolver central.
- Cobertura de testes ampliada para resolver de vínculos de ofício e evento.

## Fase 3

- Suite impactada de vínculo documental estabilizada:
  - `eventos.tests.test_pt_os_desacoplado` em verde após atualização de expectativas para o fluxo canônico atual.
  - novos testes de selectors e explicitação do contexto híbrido do Plano em `eventos/tests/test_documento_selectors.py`.
- `views_global.py` reduzido com extração adicional para `eventos/services/documento_presenters.py` (vínculos semânticos de OS/PT).
- Plano de Trabalho ganhou semântica explícita em model:
  - `get_evento_canonico()`
  - `get_evento_herdado()`
  - `get_contexto_vinculo()`
