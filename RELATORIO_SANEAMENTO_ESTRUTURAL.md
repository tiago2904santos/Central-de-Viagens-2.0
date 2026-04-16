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
