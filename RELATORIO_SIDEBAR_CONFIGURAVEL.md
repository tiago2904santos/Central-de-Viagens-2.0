# Relatório — Sidebar configurável por estrutura de dados

## 1. Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| **core/navigation.py** | Novo. Define a estrutura do menu (`get_sidebar_config`, `get_sidebar_menu`), resolução de URLs, active/expand e context processor. |
| **config/settings.py** | Inclusão do context processor `core.navigation.get_sidebar_menu` em `TEMPLATES['OPTIONS']['context_processors']`. |
| **templates/base.html** | Sidebar passou a ser renderizada em loop a partir de `sidebar_menu.groups` (itens, submenus, divisores, rodapé fixo). |
| **static/css/style.css** | Estilos para submenus: `.sidebar-toggle-sub`, `.sidebar-sub`, `.sidebar-sub-link`, `.sidebar-sub-chevron`, `.sidebar-badge`, “apenas um aberto” via collapse. |
| **core/urls.py** | Novas rotas módulo+ação: `eventos/<action>/`, `roteiros/<action>/`, `oficios/<action>/`, `planos-trabalho/<action>/`, `ordens-servico/<action>/`, `justificativas/<action>/`, `termos/<action>/` (name `*-sub`). Mantidas rotas antigas para compatibilidade. |
| **core/views/placeholder.py** | Nova view `placeholder_module_action_view(request, module, action)` e mapeamentos para títulos. |
| **core/views/__init__.py** | Export de `placeholder_module_action_view`. |
| **cadastros/urls.py** | Rotas `viajantes/<slug:action>/` e `veiculos/<slug:action>/` (name `viajantes-sub`, `veiculos-sub`). |
| **cadastros/views.py** | View `placeholder_module_action_view(request, action)` e mapeamento de títulos por módulo. |

---

## 2. Como ficou a estrutura configurável

A configuração fica em **core/navigation.py**.

- **`get_sidebar_config()`**  
  Retorna uma lista de **grupos**. Cada grupo tem `id` e `items`. Cada item é um dicionário com:
  - `id` — identificador (ex.: `'eventos'`, `'eventos-lista'`)
  - `label` — texto do menu
  - `icon` — classe do ícone (ex.: `'bi bi-grid-1x2-fill'`)
  - `url_name` — name da URL (ex.: `'core:dashboard'`) ou `None` se for só pai de submenu
  - `url_kwargs` — kwargs para `reverse` (ex.: `{'action': 'lista'}`)
  - `children` — lista de itens filhos (mesma estrutura), ou `None`
  - `order` — ordem no grupo
  - `enabled` — se o item está habilitado
  - `visible` — se o item aparece no menu
  - `has_config` — se o item tem “Configurações” (para uso futuro)
  - `badge` — texto opcional de badge

- **`get_sidebar_menu(request)`**  
  Usa a config, resolve as URLs com `reverse`, marca `active` e `expand` conforme a URL atual e devolve um dicionário no formato:
  - `sidebar_menu`: `{ 'groups': [ { 'id': '...', 'items': [ ... ] } ] }`  
  Cada item já vem com `url` (resolvida), `active`, `expand` e `children` (recursivo) prontos para o template.

- **Context processor**  
  `get_sidebar_menu` está registrado como context processor; em toda resposta o template recebe `sidebar_menu` (com `groups` vazio se o usuário não estiver autenticado).

Assim, ordem, grupos, submenus, visibilidade e habilitação são controlados só pela estrutura em **core/navigation.py**, sem alterar HTML.

---

## 3. Como adicionar novos itens/submenus no futuro

1. **Novo item sem filhos**  
   No grupo desejado em `get_sidebar_config()`, acrescentar um item com `_item('id', 'Label', 'bi bi-...', 'app:url-name', order=N)` (e opcionalmente `visible`, `enabled`, `badge`).  
   Criar a rota e a view no app correspondente.

2. **Novo item com subitens (Lista / Cadastrar)**  
   Usar o padrão já usado (ex.: Eventos, Roteiros):
   - No grupo, algo como:  
     `_item('meu-modulo', 'Meu Módulo', 'bi bi-...', None, children=_children_lista_cadastrar('meu-modulo', 'core:meu-modulo-sub'), order=N)`
   - Em **core/urls.py**:  
     `path('meu-modulo/<slug:action>/', login_required(placeholder_module_action_view), {'module': 'meu-modulo'}, name='meu-modulo-sub')`
   - Se for em outro app (ex.: cadastros), usar o `url_name` desse app (ex.: `cadastros:meu-sub`) e a view correspondente.

3. **Subitem “Configurações”**  
   Igual ao de Justificativas: no `children` do item, incluir um item com `has_config=True` e `url_name`/`url_kwargs` apontando para a rota de configurações. Não é preciso mudar o template; o sistema já está preparado para exibir e destacar esse subitem.

4. **Ocultar ou desabilitar**  
   No item da config: `visible=False` (some do menu) ou `enabled=False` (pode ser mostrado desabilitado, dependendo do template).

5. **Badge**  
   No item: `badge='12'` (ou outro texto). O template já renderiza `.sidebar-badge` quando `item.badge` existe.

---

## 4. Itens já configurados

- **Grupo principal (`main`)**  
  - Painel  
  - Simulação de Diárias  
  - Eventos → Lista, Cadastrar  
  - Roteiros → Lista, Cadastrar  
  - Ofícios → Lista, Cadastrar  
  - Planos de Trabalho → Lista, Cadastrar  
  - Ordens de Serviço → Lista, Cadastrar  
  - Justificativas → Lista, Cadastrar, Configurações (`has_config=True`)  
  - Termos de Autorização → Lista, Cadastrar  

- **Grupo cadastros**  
  - Viajantes → Lista, Cadastrar  
  - Veículos → Lista, Cadastrar  
  - Configurações (item único, sem filhos)  

- **Rodapé (fora da config)**  
  - Nome do usuário logado e link “Sair” (fixos no template).

Todas as rotas de submenu (Lista/Cadastrar/Configurações) estão implementadas; as que ainda não têm fluxo real usam a view de placeholder (módulo + ação) sem quebrar a navegação.

---

## 5. Como testar manualmente

1. Subir o projeto: `python manage.py runserver`.
2. Acessar `http://127.0.0.1:8000/`, fazer login.
3. **Ordem e grupos**  
   Verificar se a ordem é: Painel, Simulação de Diárias, Eventos, Roteiros, Ofícios, Planos de Trabalho, Ordens de Serviço, Justificativas, Termos de Autorização; depois do divisor: Viajantes, Veículos, Configurações; rodapé com usuário e Sair.
4. **Submenus**  
   Clicar em Eventos, Roteiros, Ofícios, etc.: o submenu deve abrir com “Lista” e “Cadastrar”; em Justificativas, também “Configurações”. Abrir outro item com filhos: o submenu anterior deve fechar (apenas um aberto por vez).
5. **Links**  
   Clicar em “Lista” e “Cadastrar” de cada módulo: deve abrir a página placeholder com título correto (ex.: “Eventos — Lista”, “Justificativas — Configurações”).
6. **Item ativo**  
   Navegar para uma subpágina (ex.: Eventos → Lista): o item “Lista” e o pai “Eventos” devem aparecer destacados/expandidos.
7. **Responsivo**  
   Reduzir a janela até o menu mobile: botão de toggle deve abrir/fechar a sidebar; submenus e rodapé devem continuar usáveis.
8. **Testes automatizados**  
   `python manage.py test core` deve passar (incluindo login, dashboard e placeholders).
