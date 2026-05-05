# Configuracoes do sistema

## Visao geral

`ConfiguracaoSistema` e um singleton (`pk=1`, acesso por `get_singleton()`) mantido em `cadastros`. Ele centraliza dados institucionais que alimentarao documentos DOCX/PDF, como Oficios, Justificativas, Termos, Planos de Trabalho e Ordens de Servico.

Esta etapa copia/adapta do legacy a configuracao institucional, a resolucao da cidade sede por endereco, a consulta interna de CEP, as mascaras e as assinaturas por tipo documental. Nao implementa assinatura digital.

## Campos institucionais

- Orgao: `nome_orgao`, `sigla_orgao`.
- Cabecalho: `divisao`, `unidade`.
- Rodape/endereco: `cep`, `logradouro`, `numero`, `bairro`, `cidade_endereco`, `uf`.
- Contato: `telefone`, `email`.
- Sede e chefia: `sede`, `nome_chefia`, `cargo_chefia`, `cidade_sede_padrao`.
- Plano de Trabalho: `coordenador_adm_plano_trabalho`, `pt_ultimo_numero`, `pt_ano`.
- Justificativas: `prazo_justificativa_dias`.

Campos de orgao, sigla, divisao e unidade sao normalizados em maiusculo no backend. CEP e telefone sao persistidos apenas com digitos; a mascara e aplicada na UI e nas propriedades de exibicao.

## CEP e cidade sede

A tela chama a API interna autenticada:

```text
/cadastros/api/cep/<cep>/
```

A API remove caracteres nao numericos, exige 8 digitos, consulta ViaCEP com timeout curto e retorna JSON padronizado. Erros retornam 400 para CEP invalido, 404 para CEP nao encontrado e 502 para falha externa.

Ao salvar, o service `salvar_configuracao_sistema()` tenta resolver `cidade_sede_padrao` por `uf + cidade_endereco`, usando comparacao tolerante a acentos. Se a base geografica nao estiver importada ou a cidade nao for encontrada, a configuracao e salva e a tela exibe o warning:

```text
Base geografica nao importada ou cidade nao encontrada; cidade sede padrao nao foi definida.
```

## Assinaturas por documento

`AssinaturaConfiguracao` guarda assinantes por `configuracao`, `tipo` e `ordem`, apontando para `Servidor`. O campo `ativo` e tecnico: fica `True` quando ha servidor configurado e `False` quando o slot esta vazio.

Tipos suportados:

- `OFICIO`: ordem 1 e ordem 2 na tela.
- `JUSTIFICATIVA`: ordem 1.
- `PLANO_TRABALHO`: ordem 1.
- `ORDEM_SERVICO`: ordem 1.
- `TERMO_AUTORIZACAO`: ordem 1.

A persistencia usa `update_or_create`, preservando a chave unica `configuracao + tipo + ordem`.

## Contexto documental

`cadastros.selectors.build_configuracao_context()` retorna os dados institucionais e as assinaturas ativas em um dicionario reutilizavel por geradores futuros. Nesta etapa a funcao foi preparada, mas ainda nao foi ligada aos apps de Oficios, Justificativas, Termos, Planos ou Ordens.

## Adaptado do legacy

- Singleton de configuracao institucional.
- Campos de cabecalho, rodape, contato, chefia, prazo e numeracao PT.
- Consulta ViaCEP por API interna, sem chamada externa direta no front.
- Resolucao de cidade sede por UF e nome da cidade, tolerante a acentos.
- Assinaturas por tipo documental e ordem.
- Mascaras por `data-mask` e JavaScript centralizado.

## Etapas futuras

- Integrar `build_configuracao_context()` nos geradores DOCX/PDF.
- Consumir assinaturas configuradas nas regras de renderizacao de documentos.
- Definir politica de assinatura digital/autenticacao quando o modulo de assinaturas for implementado.
