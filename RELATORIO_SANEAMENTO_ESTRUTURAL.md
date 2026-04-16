# Relatório de saneamento estrutural

- Camada central de vínculos documentais criada em `eventos/services/documento_vinculos.py`.
- Fluxos de Ordem de Serviço e Ofício passaram a consumir vínculos diretos e herdados de forma explícita.
- Formulários de Termo de Autorização passaram a limitar vínculo a um único ofício por termo.
- Foram adicionados testes de regressão para cardinalidade e herança de vínculos.
