# Checklist de migracao V2 -> V3

## Regra geral

- [ ] Nao copiar modulo antigo inteiro.
- [ ] Entender regra de negocio primeiro.
- [ ] Criar model limpo na V3.
- [ ] Criar service limpo na V3.
- [ ] Criar forms limpos na V3.
- [ ] Criar templates componentizados.
- [ ] Criar testes.
- [ ] Validar comportamento contra a V2.
- [ ] Nao repetir CSS/JS inline.
- [ ] Nao repetir views gigantes.

## Ordem recomendada

1. Cadastros base
2. Roteiros
3. Oficios
4. Termos
5. Justificativas
6. Planos de Trabalho
7. Ordens de Servico
8. Prestacao de Contas
9. Diario de Bordo
10. Documentos DOCX/PDF
11. Assinaturas
12. Integracoes

## Para cada modulo

- [ ] Mapear campos da V2.
- [ ] Mapear regras de negocio da V2.
- [ ] Mapear telas da V2.
- [ ] Mapear bugs conhecidos.
- [ ] Desenhar model novo.
- [ ] Desenhar URLs novas.
- [ ] Desenhar services.
- [ ] Desenhar selectors.
- [ ] Desenhar presenters, se necessario.
- [ ] Criar templates com componentes.
- [ ] Criar testes.
- [ ] Validar manualmente.
