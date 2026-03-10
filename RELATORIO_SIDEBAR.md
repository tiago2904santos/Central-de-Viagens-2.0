# Relatório — Ajuste da Sidebar (Menu Lateral)

## 1. Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `templates/base.html` | Reordenação dos itens do menu, inclusão de Planos de Trabalho e Ordens de Serviço, novo bloco inferior (usuário + Sair) com divisor |
| `static/css/style.css` | Estilos da sidebar: rodapé fixo, divisores, bloco do usuário, espaçamento |
| `core/urls.py` | Novas rotas: `planos-trabalho/` e `ordens-servico/` (placeholders) |
| `core/views/placeholder.py` | Inclusão de `planos-trabalho` e `ordens-servico` em `MODULO_TITULOS` |

---

## 2. O que foi ajustado no template/layout

- **Ordem do menu** passou a ser exatamente: Painel → Simulação de Diárias → Eventos → Roteiros → Ofícios → Planos de Trabalho → Ordens de Serviço → Justificativas → Termos de Autorização.
- **Primeiro divisor** entre “Termos de Autorização” e “Viajantes” (separando módulos operacionais de cadastros/configurações).
- **Novos itens**: “Planos de Trabalho” e “Ordens de Serviço”, com links para placeholders e ícones (`bi-clipboard2-check`, `bi-card-checklist`).
- **Remoção** do item “Documentos” da lista solicitada (mantidos apenas os itens do escopo do relatório).
- **Bloco inferior da sidebar**:
  - Divisor visual acima do bloco (classe `sidebar-footer-divider`).
  - Nome do usuário logado (`sidebar-user-name`).
  - Link “Sair” logo abaixo (`sidebar-logout`), sem botão, apenas texto/link.
- **Acessibilidade**: `aria-hidden="true"` nos divisores.

---

## 3. O que foi ajustado no CSS

- **Sidebar**:
  - `height: 100vh` e `max-height: 100vh` para altura fixa da viewport e rodapé sempre visível no fim.
  - `sidebar-header` e `sidebar-footer` com `flex-shrink: 0` para não encolherem.
- **sidebar-nav**:
  - `min-height: 0` para o flex permitir scroll correto; `overflow-x: hidden` para evitar barra horizontal.
  - `padding` e espaçamento vertical mantidos.
- **sidebar-divider**:
  - Margem vertical `0.75rem 1rem`, linha mais visível `rgba(255, 255, 255, 0.2)`.
- **sidebar-footer**:
  - `margin-top: auto` para fixar no fim da sidebar; `padding: 0` e sem `border-top` (divisor próprio).
- **sidebar-footer-divider**:
  - Linha de 1px entre o último item de menu e o bloco do usuário.
- **sidebar-user-block**:
  - Padding e `gap` para nome do usuário e “Sair” bem separados.
- **sidebar-user-name**:
  - Fonte e cor para destaque do usuário; `word-break: break-word` para nomes longos.
- **sidebar-logout**:
  - Estilo de link (cor, hover), sem aparência de botão.

---

## 4. Hierarquia final do menu

1. **Painel**
2. **Simulação de Diárias**
3. **Eventos**
4. **Roteiros**
5. **Ofícios**
6. **Planos de Trabalho**
7. **Ordens de Serviço**
8. **Justificativas**
9. **Termos de Autorização**
10. **—————————————** (divisor)
11. **Viajantes**
12. **Veículos**
13. **Configurações**
14. **—————————————** (espaço/divisor inferior)
15. **Nome do usuário logado**
16. **Sair**

---

## 5. Como testar manualmente

1. Subir o projeto: `python manage.py runserver`.
2. Acessar `http://127.0.0.1:8000/` e fazer login.
3. **Ordem e itens**: Verificar se a sidebar exibe os itens na ordem acima, com os dois divisores (após Termos e antes do bloco do usuário).
4. **Rodapé**: Confirmar que o nome do usuário e “Sair” ficam no fim da sidebar, sem serem cortados; em janela alta, o espaço em branco deve ficar entre “Configurações” e o divisor do rodapé.
5. **Links**: Clicar em cada item (Painel, Simulação de Diárias, Eventos, etc.) e em Viajantes, Veículos e Configurações; as páginas de placeholder devem abrir com o título correto.
6. **Destaque**: Navegar para diferentes módulos e conferir se o item ativo fica destacado (fundo e borda lateral).
7. **Responsivo**: Reduzir a largura da janela até o breakpoint mobile; o botão de toggle deve abrir/fechar a sidebar e o rodapé (usuário + Sair) deve continuar visível no fim do menu.
