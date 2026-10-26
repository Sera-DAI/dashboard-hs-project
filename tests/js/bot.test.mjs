import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import worker from "../../bot/src/index.js";
import { lerComando, responder } from "../../bot/src/comandos.js";
import { criarLeitor, ErroDados } from "../../bot/src/dados.js";
import { dividir } from "../../bot/src/formatador.js";
import { codigoDaPagina, lerClasse, lerFeed, links, paginaDoDeck, ErroFeed } from "../../bot/src/meta.js";

const diretorioFixtures = new URL("./dados/bot/", import.meta.url);
const ambiente = {
  DADOS_URL: "https://dados.example.test/dados/",
  DASHBOARD_URL: "https://hearthstone-ds.pages.dev",
  TELEGRAM_TOKEN: "token-ficticio",
  TELEGRAM_CHAT_ID: "12345",
  TELEGRAM_WEBHOOK_SECRET: "segredo-ficticio"
};

async function lerFixtures(diretorio = diretorioFixtures, prefixo = "") {
  const itens = await readdir(diretorio, { withFileTypes: true });
  const arquivos = new Map();

  for (const item of itens) {
    const caminho = new URL(item.isDirectory() ? `${item.name}/` : item.name, diretorio);
    const relativo = prefixo ? `${prefixo}/${item.name}` : item.name;

    if (item.isDirectory()) {
      for (const [nome, conteudo] of await lerFixtures(caminho, relativo)) {
        arquivos.set(nome, conteudo);
      }
    } else {
      const conteudo = await readFile(caminho, "utf8");
      arquivos.set(relativo, item.name.endsWith(".json") ? JSON.parse(conteudo) : conteudo);
    }
  }

  return arquivos;
}

const fixtures = await lerFixtures();

function criarFetchDados(registro = []) {
  return async (url, opcoes) => {
    registro.push({ url: String(url), opcoes });
    const caminho = String(url).replace("https://dados.example.test/dados/", "");

    if (!fixtures.has(caminho)) {
      return { status: 404, ok: false, json: async () => ({}) };
    }

    const conteudo = fixtures.get(caminho);
    return { status: 200, ok: true, json: async () => structuredClone(conteudo) };
  };
}

async function executar(texto, fetcher = criarFetchDados(), config = {}) {
  const lerJson = criarLeitor(fetcher, ambiente.DADOS_URL);
  return responder(texto, lerJson, { dashboard: ambiente.DASHBOARD_URL, ...config });
}

function pedidoTelegram(texto = "/ajuda", chatId = "12345") {
  return new Request("https://worker.example.test/telegram", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Bot-Api-Secret-Token": ambiente.TELEGRAM_WEBHOOK_SECRET
    },
    body: JSON.stringify({ message: { text: texto, chat: { id: chatId } } })
  });
}

test("lerComando aceita nome do bot, maiúsculas e remove espaços do argumento", () => {
  assert.deepEqual(lerComando("  /Patch@NomeDoBot   36.4  "), {
    comando: "patch",
    argumento: "36.4"
  });
  assert.deepEqual(lerComando("/CARTA Leeroy Jenkins"), {
    comando: "carta",
    argumento: "Leeroy Jenkins"
  });
  assert.deepEqual(lerComando("texto sem comando"), { comando: "", argumento: "" });
});

test("lerClasse reconhece nomes, acentos, apelidos e o formato selvagem em qualquer posição", () => {
  const classes = [
    ["Cavaleiro da Morte", "dk", "DEATHKNIGHT", "death-knight-standard", "death-knight-wild"],
    ["Caçador de Demônios", "dh", "DEMONHUNTER", "demon-hunter", "demon-hunter-wild-decks"],
    ["Druida", "druida", "DRUID", "druid", "druid-wild-decks"],
    ["Caçador", "cacador", "HUNTER", "hunter", "hunter-wild-decks"],
    ["Mago", "maga", "MAGE", "mage", "mage-wild-decks"],
    ["Paladino", "paladino", "PALADIN", "paladin", "paladin-wild-decks"],
    ["Sacerdote", "sacerdote", "PRIEST", "priest", "priest-wild-decks"],
    ["Ladino", "ladino", "ROGUE", "rogue", "rogue-wild-decks"],
    ["Xamã", "xama", "SHAMAN", "shaman", "shaman-wild-decks"],
    ["Bruxo", "bruxo", "WARLOCK", "warlock", "warlock-wild-decks"],
    ["Guerreiro", "guerreiro", "WARRIOR", "warrior", "warrior-wild-decks"]
  ];

  for (const [nome, apelido, codigo, slugPadrao, slugSelvagem] of classes) {
    assert.equal(lerClasse(nome.toLocaleUpperCase("pt-BR")).classe, codigo);
    assert.equal(lerClasse(apelido).classe, codigo);
    assert.deepEqual(lerClasse(`${apelido} selvagem`), { classe: codigo, formato: "selvagem", desconhecida: "" });
    assert.deepEqual(lerClasse(`selvagem ${apelido}`), { classe: codigo, formato: "selvagem", desconhecida: "" });
    assert.equal(links(codigo, "padrao").pagina, `https://hearthstone-decks.net/standard-decks/${slugPadrao}/`);
    assert.equal(links(codigo, "padrao").feed, `https://hearthstone-decks.net/standard-decks/${slugPadrao}/feed/`);
    assert.equal(links(codigo, "selvagem").pagina, `https://hearthstone-decks.net/wild-decks/${slugSelvagem}/`);
    assert.equal(links(codigo, "selvagem").feed, `https://hearthstone-decks.net/wild-decks/${slugSelvagem}/feed/`);
  }

  assert.deepEqual(lerClasse(""), { classe: null, formato: "padrao", desconhecida: "" });
  assert.deepEqual(lerClasse("mistério selvagem"), { classe: null, formato: "selvagem", desconhecida: "mistério" });
});

test("links montam destinos de classe e formato para todas as classes", () => {
  const classes = ["DEATHKNIGHT", "DEMONHUNTER", "DRUID", "HUNTER", "MAGE", "PALADIN", "PRIEST", "ROGUE", "SHAMAN", "WARLOCK", "WARRIOR"];

  for (const classe of classes) {
    const padrao = links(classe, "padrao");
    const selvagem = links(classe, "selvagem");
    assert.equal(padrao.hsguruDecks, `https://www.hsguru.com/decks?format=2&player_class=${classe}&rank=diamond_to_legend`);
    assert.equal(padrao.hsreplayDecks, `https://hsreplay.net/decks/#playerClasses=${classe}&gameType=RANKED_STANDARD`);
    assert.equal(padrao.hsguruMeta, "https://www.hsguru.com/meta?format=2");
    assert.equal(padrao.hsreplayMeta, "https://hsreplay.net/meta/#gameType=RANKED_STANDARD");
    assert.match(padrao.pagina, /^https:\/\/hearthstone-decks\.net\/standard-decks\/.+\/$/);
    assert.equal(padrao.feed, `${padrao.pagina}feed/`);
    assert.equal(selvagem.hsguruDecks, `https://www.hsguru.com/decks?format=1&player_class=${classe}&rank=diamond_to_legend`);
    assert.equal(selvagem.hsreplayDecks, `https://hsreplay.net/decks/#playerClasses=${classe}&gameType=RANKED_WILD`);
    assert.equal(selvagem.hsguruMeta, "https://www.hsguru.com/meta?format=1");
    assert.equal(selvagem.hsreplayMeta, "https://hsreplay.net/meta/#gameType=RANKED_WILD");
    assert.match(selvagem.pagina, /^https:\/\/hearthstone-decks\.net\/wild-decks\/.+\/$/);
    assert.equal(selvagem.feed, `${selvagem.pagina}feed/`);
  }

});

test("lerFeed lê campos RSS, código, data e entidades, e rejeita XML quebrado", async () => {
  const xml = fixtures.get("feeds/classe.xml");
  const itens = lerFeed(xml);
  assert.equal(itens.length, 5);
  assert.deepEqual(itens[0], {
    titulo: "Summoner Mage #832 Legend – Sgt_Tbag & friends",
    data: "Mon, 26 Oct 2026 02:30:00 +0000",
    link: "https://decks.example.test/1",
    codigo: "AAECAf0EBJbUBMreBfuyBvW6BvG/Bw=="
  });
  assert.equal(itens[1].codigo, "");
  assert.equal(itens[1].titulo, 'Deck dois "Mago"');
  assert.equal(itens[2].titulo, "Deck três <teste> 'ok'");
  const [escapado] = lerFeed("<rss><channel><item><title>A &amp;lt;b&amp;gt; &#x2013; B</title></item></channel></rss>");
  assert.equal(escapado.titulo, "A &lt;b&gt; – B");
  const [especial] = lerFeed("<rss><channel><item><title> <![CDATA[Deck &#99999999; ok]]> </title><description>sem</description><content:encoded><![CDATA[<p>AAECAf0EBJbUBMreBfuyBvW6</p>]]></content:encoded></item></channel></rss>");
  assert.equal(especial.titulo, "Deck &#99999999; ok");
  assert.equal(especial.codigo, "AAECAf0EBJbUBMreBfuyBvW6");
  const hostil = `<rss><channel><item>${"<description>".repeat(25000)}</item></channel></rss>`;
  const inicio = performance.now();
  lerFeed(hostil);
  assert.ok(performance.now() - inicio < 200);
  assert.throws(() => lerFeed(fixtures.get("feeds/quebrado.xml")), ErroFeed);
  assert.throws(() => lerFeed("<channel></channel>"), ErroFeed);
});

test("/decks formata até cinco itens, trata classe e erros de feed", async () => {
  const chamadas = [];
  const leitor = async (url) => {
    chamadas.push(url);
    return fixtures.get("feeds/classe.xml");
  };
  const [resposta] = await executar("/decks mago", undefined, { lerFeed: leitor });
  assert.equal(chamadas.length, 1);
  assert.equal(chamadas[0], links("MAGE", "padrao").feed);
  assert.match(resposta, /^Hearthstone DS: decks de Mago no Padrão\nTop 500 da Lenda, mais recentes primeiro/);
  assert.match(resposta, /1\. Summoner Mage #832 Legend – Sgt_Tbag & friends\n📅 25\/10\/2026\nhttps:\/\/decks\.example\.test\/1\nCódigo: AAECAf0EBJbUBMreBfuyBvW6BvG\/Bw==/);
  assert.match(resposta, /2\. Deck dois "Mago"\n📅 25\/10\/2026\nhttps:\/\/hearthstone-decks\.net\/deck-dois\/\n\n3\. Deck três <teste> 'ok'/);
  assert.doesNotMatch(resposta.match(/2\. Deck dois[\s\S]*?(?=\n\n3\.)/)?.[0] ?? "", /Código:/);
  assert.doesNotMatch(resposta, /Deck seis fora do limite/);
  assert.match(resposta, /Fonte: decks enviados ao hearthstone-decks\.net\nEstatísticas de Mago no HSGuru: https:\/\/www\.hsguru\.com\/decks\?format=2&player_class=MAGE&rank=diamond_to_legend$/);

  const [semClasse] = await executar("/decks");
  const [desconhecida] = await executar("/decks Paladino de Jade");
  assert.match(semClasse, /^Use \/decks com uma classe/);
  assert.match(desconhecida, /^Não conheço a classe "Paladino de Jade"\.\nUse \/decks/);

  const [vazio] = await executar("/decks mago", undefined, { lerFeed: async () => "<rss><channel></channel></rss>" });
  const [xmlRuim] = await executar("/decks mago", undefined, { lerFeed: async () => fixtures.get("feeds/quebrado.xml") });
  const [falha] = await executar("/decks mago", undefined, { lerFeed: async () => { throw new Error("rede"); } });
  assert.match(vazio, /^Não achei decks recentes de Mago no Padrão\. Veja a página da classe:/);
  assert.match(xmlRuim, /^Não consegui ler os decks de Mago agora\. Veja direto na página:/);
  assert.equal(falha, xmlRuim);
});

test("codigoDaPagina tira o código do link do HSReplay e paginaDoDeck só aceita o próprio site", () => {
  const codigo = "AAECAf0EBr2nB+SyB6TZB5HbB9jwB7v2BwzRpgfWvAeSxAeT2geU2wf79Qf89QeJ9geT9gfh9geAgQi/jAgAAA==";
  assert.equal(codigoDaPagina(fixtures.get("paginas/deck.html")), codigo);
  assert.equal(codigoDaPagina('<a href="https://hsreplay.net/decks/AAECAf0EBr2nB&#043;SyB6TZB5HbB9jwB7v2Bw==">x</a>'), "AAECAf0EBr2nB+SyB6TZB5HbB9jwB7v2Bw==");
  assert.equal(codigoDaPagina('<a href="https://hsreplay.net/decks/abc123/">x</a>'), "");
  assert.equal(codigoDaPagina('<a href="https://hsreplay.net/decks/AAE%E0%A4%A">x</a>'), "");
  assert.equal(codigoDaPagina("<p>Copy AAECAf0EBr2nB+SyB6TZB5HbB9jwB7v2Bw==</p>"), "");
  assert.equal(codigoDaPagina(""), "");

  const hostil = "hsreplay.net/decks/".repeat(20000);
  const inicio = performance.now();
  assert.equal(codigoDaPagina(hostil), "");
  assert.ok(performance.now() - inicio < 200);

  assert.equal(paginaDoDeck("https://hearthstone-decks.net/deck-dois/"), "https://hearthstone-decks.net/deck-dois/");
  assert.equal(paginaDoDeck("http://hearthstone-decks.net/deck-dois/"), "");
  assert.equal(paginaDoDeck("https://hearthstone-decks.net.evil.example.test/x/"), "");
  assert.equal(paginaDoDeck("https://hearthstone-decks.net:8443/x/"), "");
  assert.equal(paginaDoDeck("https://user" + "@hearthstone-decks.net/x/"), "");
  assert.equal(paginaDoDeck("https://www.hsguru.com/decks"), "");
  assert.equal(paginaDoDeck("não é link"), "");
});

test("/decks abre a página dos decks sem código no feed e tolera falha de uma página", async () => {
  const paginas = [];
  const lerPagina = async (url) => {
    paginas.push(url);

    if (url.endsWith("/deck-tres/")) {
      throw new Error("rede");
    }

    return url.endsWith("/deck-dois/") ? fixtures.get("paginas/deck.html") : "<html>sem código</html>";
  };
  const [resposta] = await executar("/decks mago", undefined, { lerFeed: async () => fixtures.get("feeds/classe.xml"), lerPagina });
  assert.deepEqual(paginas.sort(), [
    "https://hearthstone-decks.net/deck-cinco/",
    "https://hearthstone-decks.net/deck-dois/",
    "https://hearthstone-decks.net/deck-tres/"
  ]);
  assert.match(resposta, /1\. Summoner Mage[^\n]*\n📅 25\/10\/2026\nhttps:\/\/decks\.example\.test\/1\nCódigo: AAECAf0EBJbUBMreBfuyBvW6BvG\/Bw==\n\n2\./);
  assert.match(resposta, /2\. Deck dois "Mago"\n📅 25\/10\/2026\nhttps:\/\/hearthstone-decks\.net\/deck-dois\/\nCódigo: AAECAf0EBr2nB\+SyB6TZB5HbB9jwB7v2BwzRpgfWvAeSxAeT2geU2wf79Qf89QeJ9geT9gfh9geAgQi\/jAgAAA==\n\n3\./);
  assert.match(resposta, /deck-tres\/\n\n4\./);
  assert.match(resposta, /deck-quatro\/\n\n5\./);
  assert.match(resposta, /deck-cinco\/\n\nFonte:/);
});

test("/meta monta links gerais e de classe para Padrão e Selvagem", async () => {
  const [geral] = await executar("/meta");
  const [selvagem] = await executar("/meta selvagem");
  const [mago] = await executar("/meta mago");
  const [invalida] = await executar("/meta druida extra");
  assert.equal(geral, [
    "Hearthstone DS: meta do Padrão",
    "",
    "Tier list de arquétipos (HSGuru): https://www.hsguru.com/meta?format=2",
    "Meta por classe (HSReplay): https://hsreplay.net/meta/#gameType=RANKED_STANDARD",
    "",
    "Para os decks de uma classe, mande /decks <classe>, por exemplo /decks mago."
  ].join("\n"));
  assert.match(selvagem, /Hearthstone DS: meta do Selvagem/);
  assert.match(selvagem, /hsguru\.com\/meta\?format=1/);
  assert.match(selvagem, /gameType=RANKED_WILD/);
  assert.match(mago, /Mago no HSGuru: https:\/\/www\.hsguru\.com\/decks\?format=2&player_class=MAGE&rank=diamond_to_legend\nMago no HSReplay: https:\/\/hsreplay\.net\/decks\/#playerClasses=MAGE&gameType=RANKED_STANDARD/);
  assert.match(invalida, /^Não conheço a classe "druida extra"\.\n\nHearthstone DS: meta do Padrão/);
});

test("/patch mostra o mais recente com resumo, cartas e link do dashboard", async () => {
  const [texto] = await executar("/patch");
  assert.match(texto, /^Hearthstone DS: patch 36\.6 \(26\/10\/2026\)/);
  assert.match(texto, /Notas do patch 36\.6\nhttps:\/\/example\.test\/patch\/36\.6/);
  assert.match(texto, /Resumo gerado por IA\n\n⚔️ O Leeroy ficou mais barato\./);
  assert.match(texto, /Buffs \(1\)\n• Leeroy Jenkins: custo 5 → 4/);
  assert.doesNotMatch(texto, /Texto revisado|Poção Volátil/);
  assert.match(texto, /Ver no dashboard: https:\/\/hearthstone-ds\.pages\.dev\/#patch\/patches\/36\.6\.json$/);
});

test("/patch aceita versão sem diferenciar maiúsculas e fallback de notícia e resumo", async () => {
  const [texto] = await executar("/patch 36.5");
  assert.match(texto, /^Hearthstone DS: patch 36\.5 \(20\/10\/2026\)/);
  assert.match(texto, /Patch 36\.5 balance update\nhttps:\/\/example\.test\/patch\/36\.5/);
  assert.doesNotMatch(texto, /Resumo gerado por IA/);
});

test("/patch avisa sobre versão inexistente, notícia ausente e cartas nulas", async () => {
  const [inexistente] = await executar("/patch 99.1");
  const [semNoticia] = await executar("/patch 36.4");
  assert.match(inexistente, /Não achei o patch 99\.1\. Os mais recentes: 36\.6, 36\.5, 36\.4\./);
  assert.match(semNoticia, /Notícias: https:\/\/hearthstone\.blizzard\.com\/pt-br\/news/);
  assert.match(semNoticia, /Lista de cartas indisponível para este patch\./);
});

test("/carta prioriza nome exato e formata classe, atributos, texto e histórico", async () => {
  const [texto] = await executar("/carta leeroy jenkins");
  assert.match(texto, /^Leeroy Jenkins · Neutra\nCusto 4 · Ataque 6 · Vida 2/);
  assert.match(texto, /Investida\. Grito de Guerra: evoque 2 e 3\.  fim/);
  assert.match(texto, /Patch 36\.6 \(26\/10\/2026\), buff: custo 5 → 4/);
  assert.match(texto, /Patch 36\.5 \(20\/10\/2026\), nerf: ataque 7 → 6/);
  assert.ok(texto.indexOf("Patch 36.6") < texto.indexOf("Patch 36.5"));
});

test("/carta procura parcial sem acento e exibe várias opções com mais de dez resultados", async () => {
  const [semAcento] = await executar("/carta pocao");
  const [ambiguas] = await executar("/carta teste");
  assert.match(semAcento, /^Poção Volátil · Mago/);
  assert.match(semAcento, /Nenhuma mudança nos patches gravados desde 10\/10\/2026\./);
  assert.doesNotMatch(semAcento, /texto revisado/);
  assert.match(ambiguas, /^Achei 11 cartas com "teste"\. Mande \/carta com o nome completo: Mostrando 10\./);
  assert.equal((ambiguas.match(/^• /gm) ?? []).length, 10);
  assert.match(ambiguas, /• Teste Alfa/);
});

test("/carta trata busca inexistente, nome ausente e carta sem mudanças", async () => {
  const [inexistente] = await executar("/carta inexistente");
  const [semNome] = await executar("/carta x");
  const [semMudancas] = await executar("/carta Carta Sem Mudanças");
  assert.equal(inexistente, "Não achei carta com \"inexistente\". Confira o nome ou tente só uma parte dele.");
  assert.equal(semNome, "Use /carta seguido do nome, por exemplo: /carta Leeroy Jenkins");
  assert.match(semMudancas, /Nenhuma mudança nos patches gravados desde 10\/10\/2026\./);
  assert.doesNotMatch(semMudancas, /\n\n\n/);
});

test("/carta mostra só a versão atual do Padrão ou Selvagem e lê só o índice e a letra", async () => {
  const registro = [];
  const [leeroy] = await executar("/carta leeroy jenkins", criarFetchDados(registro));
  const [bola] = await executar("/carta bola", criarFetchDados());
  const lidos = registro.map((pedido) => pedido.url.replace(ambiente.DADOS_URL, ""));
  assert.match(leeroy, /Ver no dashboard: https:\/\/hearthstone-ds\.pages\.dev\/#carta\/69501$/);
  assert.doesNotMatch(leeroy, /Núcleo|Clássico/);
  assert.ok(lidos.includes("busca.json"));
  assert.ok(lidos.includes("cartas/l.json"));
  assert.ok(!lidos.includes("cartas.json"));
  assert.equal(bola, [
    "Bola de Fogo · Mago",
    "Custo 4",
    "Cause 6 de dano",
    "",
    "Mudanças nos patches gravados",
    "• Patch 36.6 (26/10/2026), nerf: custo 3 → 4",
    "",
    "Ver no dashboard: https://hearthstone-ds.pages.dev/#carta/703"
  ].join("\n"));
});

test("/carta sem atributos não deixa linha vazia e comando com acento vale", async () => {
  const [semMudancas] = await executar("/carta Carta Sem Mudanças");
  const [noticias] = await executar("/Notícias");
  assert.match(semMudancas, /^Carta Sem Mudanças · Sacerdote\n\nMudanças nos patches gravados/);
  assert.match(noticias, /^Hearthstone DS: últimas notícias/);
});

test("/historico usa singular e identifica patch com cartas indisponíveis", async () => {
  const [texto] = await executar("/historico");
  assert.match(texto, /• 36\.6 \(26\/10\/2026\): 1 buff, 1 nerf, 0 alteradas\n/);
  assert.match(texto, /• 36\.5 \(20\/10\/2026\): 0 buffs, 1 nerf, 0 alteradas/);
  assert.match(texto, /• 36\.4 \(10\/10\/2026\): lista de cartas indisponível/);
  assert.match(texto, /Use \/patch <versão> para ver um deles\.\nhttps:\/\/hearthstone-ds\.pages\.dev$/);
});

test("/noticias lista, abre por número e trata número fora da lista", async () => {
  const lista = (await executar("/noticias"))[0];
  const [detalhe] = await executar("/noticias 1");
  const [fora] = await executar("/noticias 4");
  assert.match(lista, /^Hearthstone DS: últimas notícias/);
  assert.match(lista, /^Hearthstone DS: últimas notícias\n\n1\. Novidades da Arena Mágica\n📅 26\/10\/2026\n\n2\. /);
  assert.match(lista, /\n\nPara ler o resumo de uma delas, mande \/noticias com o número \(por exemplo, \/noticias 1\) ou com uma palavra do título\.$/);
  assert.match(detalhe, /^Novidades da Arena Mágica\n26\/10\/2026/);
  assert.match(detalhe, /Resumo gerado por IA\n\n⚔️ A Arena recebeu mudanças\./);
  assert.equal(fora, "A lista tem 3 notícias. Use /noticias para ver os números.");
});

test("/noticias busca palavra sem acento, resultados ambíguos, inexistentes e sem resumo", async () => {
  const [semAcento] = await executar("/noticias TAVERNA");
  const [palavraUnica] = await executar("/noticias magica");
  const [varias] = await executar("/noticias taverna");
  const [nenhuma] = await executar("/noticias nada");
  const [semResumo] = await executar("/noticias 3");
  assert.match(semAcento, /^Achei 2 notícias com "TAVERNA":/);
  assert.match(palavraUnica, /^Novidades da Arena Mágica\n/);
  assert.match(varias, /:\n\n2\. Cofre da Taverna[^\n]*\n📅 25\/10\/2026\n\n/);
  assert.match(nenhuma, /Não achei notícia com "nada" no título/);
  assert.match(semResumo, /O resumo por IA desta notícia ainda não foi gerado\./);
});

test("/ajuda e comando desconhecido seguem os textos registrados", async () => {
  const [ajuda] = await executar("/start");
  const [desconhecido] = await executar("/desconhecido");
  const [semComando] = await executar("olá");
  assert.match(ajuda, /^Hearthstone DS: comandos/);
  assert.match(ajuda, /\/decks <classe>: decks Top 500 da Lenda/);
  assert.match(ajuda, /\/meta: links das estatísticas do meta/);
  assert.match(desconhecido, /^Não conheço esse comando\.\n\nHearthstone DS: comandos/);
  assert.equal(semComando, desconhecido);
});

test("falha de leitura dos JSON vira a mensagem 17", async () => {
  const falha = async () => ({ status: 503, ok: false, json: async () => ({}) });
  const respostas = await executar("/patch", falha);
  assert.deepEqual(respostas, ["Não consegui ler os dados do Hearthstone DS agora. Tente de novo em alguns minutos."]);
});

test("o leitor aplica cache de cinco minutos e converte status e JSON inválido em ErroDados", async () => {
  const chamadas = [];
  const lerJson = criarLeitor(criarFetchDados(chamadas), ambiente.DADOS_URL);
  await lerJson("indice.json");
  assert.deepEqual(chamadas[0].opcoes, { cf: { cacheTtl: 300, cacheEverything: true } });
  await assert.rejects(criarLeitor(async () => ({ status: 404 }), ambiente.DADOS_URL)("ausente.json"), ErroDados);
  await assert.rejects(criarLeitor(async () => ({ status: 200, json: async () => { throw new SyntaxError("inválido"); } }), ambiente.DADOS_URL)("ruim.json"), ErroDados);
  await assert.rejects(criarLeitor(async () => { throw new Error("rede"); }, ambiente.DADOS_URL)("erro.json"), ErroDados);
});

test("divide respostas longas entre linhas e identifica continuações", () => {
  const texto = `Hearthstone DS: patch 37.0\n${"a".repeat(2000)}\n${"b".repeat(2000)}\n${"c".repeat(2000)}`;
  const partes = dividir(texto, "Hearthstone DS: patch 37.0");
  assert.equal(partes.length, 3);
  assert.match(partes[0], / \(1\/3\)$/m);
  assert.match(partes[1], /^Hearthstone DS: patch 37\.0 \(continuação 2\/3\)/);
  assert.match(partes[2], /^Hearthstone DS: patch 37\.0 \(continuação 3\/3\)/);
  assert.ok(partes.every((parte) => parte.length <= 4096));
  assert.ok(partes.every((parte) => !parte.includes("a".repeat(1999) + "\nb")));
});

test("webhook rejeita método e segredo incorretos sem chamar serviços", async (context) => {
  const original = globalThis.fetch;
  const chamadas = [];
  globalThis.fetch = async (...argumentos) => {
    chamadas.push(argumentos);
    return { ok: true, status: 200, json: async () => ({}) };
  };
  context.after(() => { globalThis.fetch = original; });

  const semCabecalho = new Request("https://worker.example.test", { method: "POST", body: "{}" });
  const segredoErrado = new Request("https://worker.example.test", {
    method: "POST",
    headers: { "X-Telegram-Bot-Api-Secret-Token": "incorreto" },
    body: "{}"
  });
  const metodoErrado = new Request("https://worker.example.test", {
    method: "GET",
    headers: { "X-Telegram-Bot-Api-Secret-Token": ambiente.TELEGRAM_WEBHOOK_SECRET }
  });
  const respostas = await Promise.all([
    worker.fetch(semCabecalho, ambiente),
    worker.fetch(segredoErrado, ambiente),
    worker.fetch(metodoErrado, ambiente)
  ]);

  assert.deepEqual(respostas.map((resposta) => resposta.status), [401, 401, 401]);
  assert.deepEqual(await Promise.all(respostas.map((resposta) => resposta.text())), ["", "", ""]);
  assert.equal(chamadas.length, 0);
});

test("webhook ignora outro chat e update sem texto sem resposta", async (context) => {
  const original = globalThis.fetch;
  const chamadas = [];
  globalThis.fetch = async (...argumentos) => {
    chamadas.push(argumentos);
    return { ok: true, status: 200, json: async () => ({}) };
  };
  context.after(() => { globalThis.fetch = original; });

  const outraPessoa = await worker.fetch(pedidoTelegram("/ajuda", "99999"), ambiente);
  const semTexto = await worker.fetch(new Request("https://worker.example.test", {
    method: "POST",
    headers: { "X-Telegram-Bot-Api-Secret-Token": ambiente.TELEGRAM_WEBHOOK_SECRET },
    body: JSON.stringify({ message: { chat: { id: 12345 } } })
  }), ambiente);
  assert.equal(outraPessoa.status, 200);
  assert.equal(semTexto.status, 200);
  assert.equal(chamadas.length, 0);
});

test("webhook responde em texto puro ao chat permitido", async (context) => {
  const original = globalThis.fetch;
  const chamadas = [];
  globalThis.fetch = async (url, opcoes) => {
    chamadas.push({ url: String(url), opcoes });

    if (String(url).startsWith(ambiente.DADOS_URL)) {
      return criarFetchDados()(url, opcoes);
    }

    return { ok: true, status: 200, json: async () => ({ ok: true }) };
  };
  context.after(() => { globalThis.fetch = original; });

  const resposta = await worker.fetch(pedidoTelegram("/ajuda"), ambiente);
  assert.equal(resposta.status, 200);
  assert.equal(await resposta.text(), "");
  assert.equal(chamadas.length, 1);
  assert.match(chamadas[0].url, /\/sendMessage$/);
  const corpo = JSON.parse(chamadas[0].opcoes.body);
  assert.equal(corpo.chat_id, ambiente.TELEGRAM_CHAT_ID);
  assert.equal(corpo.disable_web_page_preview, true);
  assert.match(corpo.text, /\/decks <classe>/);
  assert.equal("parse_mode" in corpo, false);
  assert.match(chamadas[0].url, /bottoken-ficticio\/sendMessage$/);
  assert.doesNotMatch(chamadas[0].opcoes.body, /token-ficticio/);
});

test("Worker transforma status 500 e feed acima de 512 KB em indisponibilidade", async (context) => {
  const original = globalThis.fetch;
  const chamadas = [];
  const respostasTelegram = [];
  let statusFeed = 500;
  let corpoFeed = "erro";
  globalThis.fetch = async (url, opcoes) => {
    chamadas.push({ url: String(url), opcoes });

    if (String(url).startsWith("https://hearthstone-decks.net/")) {
      return new Response(corpoFeed, { status: statusFeed });
    }

    if (String(url).endsWith("/sendMessage")) {
      respostasTelegram.push(JSON.parse(opcoes.body));
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }

    throw new Error("Destino inesperado no teste.");
  };
  context.after(() => { globalThis.fetch = original; });

  await worker.fetch(pedidoTelegram("/decks mago"), ambiente);
  assert.match(respostasTelegram[0].text, /^Não consegui ler os decks de Mago agora\./);
  assert.equal(chamadas.filter((chamada) => chamada.url.startsWith("https://hearthstone-decks.net/")).length, 1);
  assert.equal(chamadas[0].opcoes.headers["User-Agent"], "HearthstoneDS/0.1 (monitor pessoal; github.com/Sera-DAI)");
  assert.deepEqual(chamadas[0].opcoes.cf, { cacheTtl: 1800, cacheEverything: true });

  chamadas.length = 0;
  statusFeed = 200;
  corpoFeed = "x".repeat(512 * 1024 + 1);
  await worker.fetch(pedidoTelegram("/decks mago"), ambiente);
  assert.match(respostasTelegram[1].text, /^Não consegui ler os decks de Mago agora\./);
  assert.equal(chamadas.filter((chamada) => chamada.url.startsWith("https://hearthstone-decks.net/")).length, 1);
});

test("Worker lê o feed e as páginas dos decks com cache e recusa página acima de 1 MB", async (context) => {
  const original = globalThis.fetch;
  const chamadas = [];
  const respostasTelegram = [];
  let corpoPagina = fixtures.get("paginas/deck.html");
  globalThis.fetch = async (url, opcoes) => {
    chamadas.push({ url: String(url), opcoes });

    if (String(url).endsWith("/feed/")) {
      return new Response(fixtures.get("feeds/classe.xml"), { status: 200 });
    }

    if (String(url).startsWith("https://hearthstone-decks.net/")) {
      return new Response(corpoPagina, { status: 200 });
    }

    if (String(url).endsWith("/sendMessage")) {
      respostasTelegram.push(JSON.parse(opcoes.body));
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }

    throw new Error("Destino inesperado no teste.");
  };
  context.after(() => { globalThis.fetch = original; });

  await worker.fetch(pedidoTelegram("/decks mago"), ambiente);
  const site = chamadas.filter((chamada) => chamada.url.startsWith("https://hearthstone-decks.net/"));
  assert.equal(site.length, 4);
  assert.ok(site.every((chamada) => chamada.opcoes.headers["User-Agent"] === "HearthstoneDS/0.1 (monitor pessoal; github.com/Sera-DAI)"));
  assert.ok(site.every((chamada) => chamada.opcoes.cf.cacheTtl === 1800 && chamada.opcoes.cf.cacheEverything === true));
  assert.ok(!chamadas.some((chamada) => chamada.url.includes("evil.example.test")));
  assert.equal((respostasTelegram[0].text.match(/Código: AAECAf0EBr2nB/g) ?? []).length, 3);

  chamadas.length = 0;
  corpoPagina = "x".repeat(1024 * 1024 + 1);
  await worker.fetch(pedidoTelegram("/decks mago"), ambiente);
  assert.match(respostasTelegram[1].text, /^Hearthstone DS: decks de Mago/);
  assert.equal((respostasTelegram[1].text.match(/Código:/g) ?? []).length, 1);
});

test("corpo inválido recebe 200 vazio sem resposta ao Telegram", async (context) => {
  const original = globalThis.fetch;
  let chamadas = 0;
  globalThis.fetch = async () => {
    chamadas += 1;
    return { ok: true, status: 200 };
  };
  context.after(() => { globalThis.fetch = original; });

  const resposta = await worker.fetch(new Request("https://worker.example.test", {
    method: "POST",
    headers: { "X-Telegram-Bot-Api-Secret-Token": ambiente.TELEGRAM_WEBHOOK_SECRET },
    body: "não é JSON"
  }), ambiente);
  assert.equal(resposta.status, 200);
  assert.equal(await resposta.text(), "");
  assert.equal(chamadas, 0);
});
