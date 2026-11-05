<p align="center">
  <img src="docs/imagens/banner.svg" alt="Dash'board HS: patches, notícias e decks do meta de Hearthstone" width="100%">
</p>

<p align="center"><b>Português</b> · <a href="README.en.md">English</a></p>

<p align="center">
  <a href="https://dashboard-hs.pages.dev"><img src="https://img.shields.io/badge/dashboard-dashboard--hs.pages.dev-7c3aed?style=for-the-badge&labelColor=07080f&logo=cloudflarepages&logoColor=f5f2ea" alt="Dashboard"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-7c3aed?style=flat-square&labelColor=07080f&logo=python&logoColor=f5f2ea" alt="Python">
  <img src="https://img.shields.io/badge/github%20actions-a%20cada%20hora-7c3aed?style=flat-square&labelColor=07080f&logo=githubactions&logoColor=f5f2ea" alt="GitHub Actions">
  <img src="https://img.shields.io/badge/bot-cloudflare%20worker-7c3aed?style=flat-square&labelColor=07080f&logo=cloudflareworkers&logoColor=f5f2ea" alt="Cloudflare Workers">
  <img src="https://img.shields.io/badge/avisos-telegram-7c3aed?style=flat-square&labelColor=07080f&logo=telegram&logoColor=f5f2ea" alt="Telegram">
  <img src="https://img.shields.io/badge/resumo-gemini-7c3aed?style=flat-square&labelColor=07080f&logo=googlegemini&logoColor=f5f2ea" alt="Gemini">
  <img src="https://img.shields.io/badge/marcos-M0%20a%20M5%20conclu%C3%ADdos-2fae79?style=flat-square&labelColor=07080f" alt="Marcos">
</p>

<p align="center">
  <img src="docs/imagens/stack/claude.svg" width="44" alt="Claude" title="Claude">
  <img src="docs/imagens/stack/python.svg" width="44" alt="Python" title="Python">
  <img src="docs/imagens/stack/pytest.svg" width="44" alt="pytest" title="pytest">
  <img src="docs/imagens/stack/javascript.svg" width="44" alt="JavaScript" title="JavaScript">
  <img src="docs/imagens/stack/nodedotjs.svg" width="44" alt="Node.js" title="Node.js">
  <img src="docs/imagens/stack/html5.svg" width="44" alt="HTML5" title="HTML5">
  <img src="docs/imagens/stack/css.svg" width="44" alt="CSS" title="CSS">
  <img src="docs/imagens/stack/githubactions.svg" width="44" alt="GitHub Actions" title="GitHub Actions">
  <img src="docs/imagens/stack/cloudflare.svg" width="44" alt="Cloudflare Pages" title="Cloudflare Pages">
  <img src="docs/imagens/stack/cloudflareworkers.svg" width="44" alt="Cloudflare Workers" title="Cloudflare Workers">
  <img src="docs/imagens/stack/telegram.svg" width="44" alt="Telegram" title="Telegram">
  <img src="docs/imagens/stack/googlegemini.svg" width="44" alt="Gemini" title="Gemini">
</p>

<p align="center"><sub>Feito com Claude · Python · JavaScript · GitHub Actions · Cloudflare · Telegram</sub></p>

<p align="center"><img src="docs/imagens/divisor.svg" width="420" alt=""></p>

> **Repositório de vitrine, somente leitura.** Este é um recorte do projeto: só o código, os testes e os workflows. Não tem dados nem segredos, os workflows ficam só como referência e **não aceita contribuições**. O código pode ser lido, mas não copiado nem reutilizado sem permissão por escrito: veja a [LICENSE](LICENSE).

# Dash'board HS

**Dash'board HS** reúne as informações de Hearthstone num só lugar: patches, notícias e os decks do meta Padrão e Selvagem. Avisa no Telegram quando sai um patch ou uma notícia, com um resumo em português e a lista das cartas alteradas, guarda todo o histórico num dashboard com as cartas oficiais em 3D e responde a comandos direto no Telegram.

Roda sozinho, sem servidor e em planos gratuitos: a coleta é um workflow agendado do GitHub Actions, o dashboard é uma página estática no Cloudflare Pages e o bot de comandos é um Cloudflare Worker.

## Sumário

- [I. O que ele faz](#i-o-que-ele-faz)
- [II. Comandos do bot](#ii-comandos-do-bot)
- [III. Como funciona](#iii-como-funciona)
- [IV. Estrutura do repositório](#iv-estrutura-do-repositório)
- [V. Desenvolvimento e testes](#v-desenvolvimento-e-testes)
- [VI. Como foi construído: o fluxo de agentes](#vi-como-foi-construído-o-fluxo-de-agentes)
- [VII. Marcos](#vii-marcos)
- [VIII. Fontes e limites](#viii-fontes-e-limites)

## I. O que ele faz

<table>
  <tr>
    <td width="72" align="center"><img src="docs/imagens/icones/aviso.svg" width="44" alt=""></td>
    <td><b>Aviso de patch no Telegram</b><br>Verifica a cada hora o site oficial da Blizzard (pt-BR) e o HearthstoneJSON. Quando sai patch, manda a mensagem com o link da notícia e as cartas alteradas; se a coleta falhar, avisa em vez de ficar em silêncio.</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/imagens/icones/cartas.svg" width="44" alt=""></td>
    <td><b>Diff de cartas</b><br>Compara as builds do HearthstoneJSON e lista buff, nerf, custo, ataque, vida e texto de cada carta alterada.</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/imagens/icones/resumo.svg" width="44" alt=""></td>
    <td><b>Resumo próprio por IA</b><br>Notícias e patches de Hearthstone ganham um resumo em tópicos, escrito com o Gemini a partir da notícia e do diff de cartas, usado no Telegram e no dashboard.</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/imagens/icones/painel.svg" width="44" alt=""></td>
    <td><b>Dashboard</b><br>Histórico de patches e notícias, detalhe de cada patch, busca por carta e seção Meta, em <a href="https://dashboard-hs.pages.dev">dashboard-hs.pages.dev</a>. As cartas alteradas aparecem com a imagem oficial em pt-BR, inclinam com o mouse ou o dedo, viram para mostrar o verso e, em buffs e nerfs, trocam entre a versão anterior e a atual. HTML, CSS e JavaScript puros, sem framework.</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/imagens/icones/bot.svg" width="44" alt=""></td>
    <td><b>Bot de comandos</b><br>Consulta patches, cartas, notícias e decks do meta direto no Telegram.</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/imagens/icones/meta.svg" width="44" alt=""></td>
    <td><b>Decks do meta</b><br>Atalhos por classe, em Padrão e Wild, para os decks e as estatísticas do HSReplay e do HSGuru. O projeto não lê nenhum desses sites: só monta os links.</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/imagens/icones/seguranca.svg" width="44" alt=""></td>
    <td><b>Segurança do site</b><br>Cabeçalhos de segurança em <a href="site/_headers"><code>site/_headers</code></a> (política de conteúdo restrita ao próprio domínio, ao Google Fonts e aos CDNs de imagem, sem <code>unsafe-inline</code> em scripts), com testes que travam o hash da política.</td>
  </tr>
</table>

## II. Comandos do bot

| Comando | O que responde |
| --- | --- |
| `/patch [versão]` | O patch mais recente, ou a versão pedida, com resumo e cartas alteradas |
| `/carta <nome>` | A carta atual e o histórico de mudanças dela nos patches |
| `/historico` | Os 10 patches mais recentes |
| `/noticias [busca ou número]` | As notícias recentes, uma notícia específica com resumo ou a busca por assunto |
| `/decks <classe> [padrão\|wild]` | Links dos decks da classe no HSReplay e no HSGuru, nos dois formatos ou só no pedido |
| `/meta [classe] [padrão\|wild]` | Links das estatísticas do meta no HSGuru e no HSReplay |
| `/ajuda` | A lista de comandos e o link do dashboard |

## III. Como funciona

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#4c1d95", "primaryTextColor": "#f5f2ea", "primaryBorderColor": "#e9b949", "lineColor": "#a78bfa", "secondaryColor": "#100c1f", "tertiaryColor": "#07080f", "fontFamily": "Georgia, serif"}}}%%
flowchart LR
    B["Blizzard<br>notícias pt-BR"] --> M
    J["HearthstoneJSON<br>dados de cartas"] --> M
    A["API da Blizzard<br>imagens das cartas"] --> I["GitHub Actions<br>imagens a cada 6 h"]
    I -->|hash das imagens| D
    G["Gemini<br>resumo escrito à mão"] -->|grava o resumo| D
    M["GitHub Actions<br>monitor a cada hora"] -->|grava JSON| D[("JSON versionados<br>(fora deste recorte)")]
    M -->|aviso| T["Telegram"]
    G -->|aviso do resumo| T
    D --> P["Cloudflare Pages<br>dashboard"]
    D --> W["Cloudflare Worker<br>bot de comandos"]
    W --> T
    C["CDN da Blizzard"] -->|imagem de cada carta| P
```

| Peça | Onde | O que faz |
| --- | --- | --- |
| Monitor | [`docs/workflows/monitor.yml`](docs/workflows/monitor.yml), [`src/hsds/`](src/hsds/) | Coleta, compara as cartas, avisa no Telegram e grava os JSON |
| Dashboard | [`site/`](site/) | HTML, CSS e JavaScript puros, sem framework; a imagem de cada carta vem direto do CDN da Blizzard, com o HearthstoneJSON de reserva |
| Bot | [`bot/`](bot/), [`docs/workflows/bot.yml`](docs/workflows/bot.yml) | Worker que só lê os JSON publicados, sem banco próprio |
| Testes | [`tests/`](tests/), [`docs/workflows/testes.yml`](docs/workflows/testes.yml) | pytest e node --test a cada mudança, sem acesso à rede |

## IV. Estrutura do repositório

<table>
  <tr>
    <td width="72" align="center"><img src="docs/imagens/icones/estrutura.svg" width="44" alt=""></td>
    <td>

```text
dashboard-hs-project/
├── src/hsds/            coletores, diff de cartas, resumo e envio ao Telegram (Python)
├── bot/                 Cloudflare Worker do Telegram (JavaScript)
├── site/                dashboard estático (HTML, CSS e site/js)
├── tests/               testes em pytest e em node --test, sem acesso à rede
├── docs/workflows/      workflows do GitHub Actions, só como referência
└── docs/imagens/        ilustrações deste README
```

</td>
  </tr>
</table>

## V. Desenvolvimento e testes

<table>
  <tr>
    <td width="72" align="center"><img src="docs/imagens/icones/testes.svg" width="44" alt=""></td>
    <td>Requer Python 3.12 e, para os testes do dashboard e do bot, Node 22. Os testes nunca acessam a rede: usam páginas e JSON salvos em <code>tests/dados/</code>. Teste que falha não se desliga: vira correção.</td>
  </tr>
</table>

```bash
python -m pip install -e ".[teste]"
python -m pytest
node --test tests/js/*.test.mjs
```

Os segredos (token do bot, chat id e chaves do Cloudflare) ficam nos Secrets do GitHub e do Cloudflare, nunca no repositório.

## VI. Como foi construído: o fluxo de agentes

<table>
  <tr>
    <td width="72" align="center"><img src="docs/imagens/icones/agentes.svg" width="44" alt=""></td>
    <td>O projeto foi desenvolvido com <b>agentes de IA orquestrados por um humano</b>: um agente de desenvolvimento escreve o código, e especialistas de leitura (que não editam arquivos) fazem a revisão independente. Cada camada do repositório tem fronteiras de arquivos que não se cruzam, e a integração só acontece com aprovação humana.</td>
  </tr>
</table>

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#4c1d95", "primaryTextColor": "#f5f2ea", "primaryBorderColor": "#e9b949", "lineColor": "#a78bfa", "secondaryColor": "#100c1f", "tertiaryColor": "#07080f", "fontFamily": "Georgia, serif"}}}%%
flowchart LR
    C["Critérios de aceite<br>aprovados antes do código"] --> P["Plano curto<br>com contrato e exemplos"]
    P --> I["Implementação<br>agente de desenvolvimento"]
    I --> R{"Revisão independente"}
    R --> R1["Coleta e fontes externas"]
    R --> R2["Fronteiras de arquivos"]
    R --> R3["Segurança"]
    R --> R4["Testes e cobertura"]
    R --> R5["Documentação"]
    R1 & R2 & R3 & R4 & R5 --> H["Aprovação humana<br>e integração"]
```

| Etapa | O que acontece |
| --- | --- |
| **Critérios de aceite** | Cada marco começa com uma tabela curta "critério → como verificar", aprovada antes de qualquer código. |
| **Plano e contrato** | Arquivos que a tarefa pode tocar, assinaturas e exemplos concretos, para evitar desvio de escopo. |
| **Implementação** | Um agente escreve o código e os testes dentro das fronteiras da tarefa; uma mudança lógica por commit. |
| **Revisão independente** | Cinco especialistas de leitura (coleta, fronteiras de arquivos, segurança, testes e documentação) examinam o diff antes da integração; achado que bloqueia vira correção, achado que sugere é aplicado ou justificado. |
| **Aprovação** | Nada entra na `main` sem aprovação humana explícita. |

Regras que o processo impõe: teste que falha não se desliga; segredos só nos Secrets; fontes externas só depois de ler os termos de uso; decisões registradas com data, motivo e aprovação.

## VII. Marcos

| Marco | Entrega |
| --- | --- |
| M0 · Fundação | Repositório, documentação, workflow e mensagem de teste |
| M1 · Patch notes | Coleta pt-BR, diff de cartas, JSON e aviso no Telegram |
| M2 · Dashboard | Página com histórico, detalhe e busca de carta |
| M2b · Resumo por IA | Resumo em tópicos para patches e notícias |
| M2c · Histórico retroativo | Patches e notícias antigos no dashboard |
| M3 · Bot | Worker com `/patch`, `/carta`, `/historico` e `/noticias` |
| M4 · Meta | `/decks`, `/meta` e seção Meta no dashboard |
| M5 · Visual | Cartas oficiais em 3D com antes e depois, ícones próprios e a identidade visual da D'arc |

## VIII. Fontes e limites

<table>
  <tr>
    <td width="72" align="center"><img src="docs/imagens/icones/licenca.svg" width="44" alt=""></td>
    <td>
      <ul>
        <li>Fontes: notícias oficiais da Blizzard, dados abertos do <a href="https://hearthstonejson.com">HearthstoneJSON</a> e a API de dados do Hearthstone da Blizzard, só para o endereço das imagens das cartas. O HSGuru e o HSReplay aparecem só como atalhos, porque os termos deles vetam a coleta.</li>
        <li>O dashboard não republica texto da Blizzard: mostra o resumo próprio e o link da notícia original. Este repositório não guarda as imagens das cartas: o dashboard as carrega do CDN da Blizzard, com o render do HearthstoneJSON de reserva, e credita a Blizzard no rodapé.</li>
        <li>Projeto pessoal e sem fins comerciais. Hearthstone é marca da Blizzard Entertainment; este projeto não é afiliado nem endossado por ela.</li>
        <li>Os ícones das tecnologias vêm do <a href="https://simpleicons.org">Simple Icons</a> (CC0); cada marca pertence ao seu dono.</li>
        <li>Licença de visualização, somente leitura: veja a <a href="LICENSE">LICENSE</a>.</li>
      </ul>
    </td>
  </tr>
</table>
