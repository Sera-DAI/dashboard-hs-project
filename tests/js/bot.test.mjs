import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import worker from "../../bot/src/index.js";
import { lerComando, responder } from "../../bot/src/comandos.js";
import { criarLeitor, ErroDados } from "../../bot/src/dados.js";
import { dividir } from "../../bot/src/formatador.js";
import { lerClasse, links } from "../../bot/src/meta.js";

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

test("lerClasse reconhece nomes, acentos, apelidos e o formato wild ou padrão em qualquer posição", () => {
  const classes = [
    ["Cavaleiro da Morte", "dk", "DEATHKNIGHT"],
    ["Caçador de Demônios", "dh", "DEMONHUNTER"],
    ["Druida", "druida", "DRUID"],
    ["Caçador", "cacador", "HUNTER"],
    ["Mago", "maga", "MAGE"],
    ["Paladino", "paladino", "PALADIN"],
    ["Sacerdote", "sacerdote", "PRIEST"],
    ["Ladino", "ladino", "ROGUE"],
    ["Xamã", "xama", "SHAMAN"],
    ["Bruxo", "bruxo", "WARLOCK"],
    ["Guerreiro", "guerreiro", "WARRIOR"]
  ];

  for (const [nome, apelido, codigo] of classes) {
    assert.deepEqual(lerClasse(nome.toLocaleUpperCase("pt-BR")), { classe: codigo, formato: null, desconhecida: "" });
    assert.equal(lerClasse(apelido).classe, codigo);
    assert.deepEqual(lerClasse(`${apelido} wild`), { classe: codigo, formato: "wild", desconhecida: "" });
    assert.deepEqual(lerClasse(`WILD ${apelido}`), { classe: codigo, formato: "wild", desconhecida: "" });
    assert.deepEqual(lerClasse(`${apelido} padrão`), { classe: codigo, formato: "padrao", desconhecida: "" });
    assert.deepEqual(lerClasse(`${apelido} standard`), { classe: codigo, formato: "padrao", desconhecida: "" });
  }

  assert.deepEqual(lerClasse(""), { classe: null, formato: null, desconhecida: "" });
  assert.deepEqual(lerClasse("mistério wild"), { classe: null, formato: "wild", desconhecida: "mistério" });
  assert.deepEqual(lerClasse("mago selvagem"), { classe: null, formato: null, desconhecida: "mago selvagem" });
});

test("links montam destinos de classe e formato para todas as classes", () => {
  const classes = ["DEATHKNIGHT", "DEMONHUNTER", "DRUID", "HUNTER", "MAGE", "PALADIN", "PRIEST", "ROGUE", "SHAMAN", "WARLOCK", "WARRIOR"];

  for (const classe of classes) {
    const padrao = links(classe, "padrao");
    const wild = links(classe, "wild");
    assert.equal(padrao.hsguruDecks, `https://www.hsguru.com/decks?format=2&player_class=${classe}&rank=diamond_to_legend&period=past_2_weeks&min_games=100`);
    assert.equal(padrao.hsreplayDecks, `https://hsreplay.net/decks/#playerClasses=${classe}&gameType=RANKED_STANDARD`);
    assert.equal(padrao.hsguruMeta, "https://www.hsguru.com/meta?format=2");
    assert.equal(padrao.hsreplayMeta, "https://hsreplay.net/meta/#gameType=RANKED_STANDARD");
    assert.equal(wild.hsguruDecks, `https://www.hsguru.com/decks?format=1&player_class=${classe}&rank=diamond_to_legend&period=past_2_weeks&min_games=100`);
    assert.equal(wild.hsreplayDecks, `https://hsreplay.net/decks/#playerClasses=${classe}&gameType=RANKED_WILD`);
    assert.equal(wild.hsguruMeta, "https://www.hsguru.com/meta?format=1");
    assert.equal(wild.hsreplayMeta, "https://hsreplay.net/meta/#gameType=RANKED_WILD");
    assert.equal(Object.keys(padrao).sort().join(), "hsguruDecks,hsguruMeta,hsreplayDecks,hsreplayMeta");
  }
});

test("/decks <classe> traz HSReplay e HSGuru do Padrão e do Wild, sem rede", async () => {
  const [resposta] = await executar("/decks mago");
  const padrao = links("MAGE", "padrao");
  const wild = links("MAGE", "wild");
  assert.equal(resposta, [
    "Hearthstone DS: decks de Mago",
    `Padrão\nHSReplay: ${padrao.hsreplayDecks}\nHSGuru: ${padrao.hsguruDecks}`,
    `Wild\nHSReplay: ${wild.hsreplayDecks}\nHSGuru: ${wild.hsguruDecks}`,
    "Filtros do HSGuru: Diamante até Lenda, últimas 2 semanas, mínimo de 100 jogos.",
    "Só um formato: /decks mago wild ou /decks mago padrão."
  ].join("\n\n"));
  assert.doesNotMatch(resposta, /hearthstone-decks|Código:|Top 500/);
});

test("/decks <classe> <formato> traz só o formato pedido, em qualquer ordem", async () => {
  const [wild] = await executar("/decks dh wild");
  const [ordemTroca] = await executar("/decks wild dh");
  const [padrao] = await executar("/decks Caçador de Demônios padrão");
  const dados = links("DEMONHUNTER", "wild");
  assert.equal(wild, `Hearthstone DS: decks de Caçador de Demônios no Wild\n\nHSReplay: ${dados.hsreplayDecks}\nHSGuru: ${dados.hsguruDecks}\n\nFiltros do HSGuru: Diamante até Lenda, últimas 2 semanas, mínimo de 100 jogos.`);
  assert.equal(ordemTroca, wild);
  assert.match(padrao, /^Hearthstone DS: decks de Caçador de Demônios no Padrão\n\nHSReplay: https:\/\/hsreplay\.net\/decks\/#playerClasses=DEMONHUNTER&gameType=RANKED_STANDARD\nHSGuru: https:\/\/www\.hsguru\.com\/decks\?format=2&player_class=DEMONHUNTER&rank=diamond_to_legend&period=past_2_weeks&min_games=100\n\nFiltros/);
  assert.doesNotMatch(padrao, /Wild|RANKED_WILD/);
});

test("/decks sem classe ou com classe desconhecida ensina o uso com wild", async () => {
  const [semClasse] = await executar("/decks");
  const [desconhecida] = await executar("/decks Paladino de Jade");
  const [selvagem] = await executar("/decks mago selvagem");
  assert.match(semClasse, /^Use \/decks com uma classe, por exemplo \/decks mago ou \/decks dh wild\./);
  assert.match(desconhecida, /^Não conheço a classe "Paladino de Jade"\.\nUse \/decks/);
  assert.match(selvagem, /^Não conheço a classe "mago selvagem"\.\nUse \/decks/);
});

test("/meta monta links gerais e de classe para Padrão e Selvagem", async () => {
  const [geral] = await executar("/meta");
  const [selvagem] = await executar("/meta wild");
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
  assert.match(selvagem, /Hearthstone DS: meta do Wild/);
  assert.match(selvagem, /hsguru\.com\/meta\?format=1/);
  assert.match(selvagem, /gameType=RANKED_WILD/);
  assert.match(mago, /Mago no HSGuru: https:\/\/www\.hsguru\.com\/decks\?format=2&player_class=MAGE&rank=diamond_to_legend&period=past_2_weeks&min_games=100\nMago no HSReplay: https:\/\/hsreplay\.net\/decks\/#playerClasses=MAGE&gameType=RANKED_STANDARD/);
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
  assert.match(ajuda, /\/decks <classe>: links de decks no HSReplay e no HSGuru, Padrão e Wild, ou \/decks <classe> wild/);
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

test("Worker responde /decks só com links, sem ler nenhum site de decks", async (context) => {
  const original = globalThis.fetch;
  const chamadas = [];
  const respostasTelegram = [];
  globalThis.fetch = async (url, opcoes) => {
    chamadas.push(String(url));

    if (String(url).endsWith("/sendMessage")) {
      respostasTelegram.push(JSON.parse(opcoes.body));
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }

    throw new Error("Destino inesperado no teste.");
  };
  context.after(() => { globalThis.fetch = original; });

  await worker.fetch(pedidoTelegram("/decks mago"), ambiente);
  assert.equal(chamadas.length, 1);
  assert.ok(chamadas[0].endsWith("/sendMessage"));
  assert.match(respostasTelegram[0].text, /^Hearthstone DS: decks de Mago\n\nPadrão\nHSReplay: https:\/\/hsreplay\.net\/decks\/#playerClasses=MAGE&gameType=RANKED_STANDARD/);
  assert.match(respostasTelegram[0].text, /Wild\nHSReplay: .*RANKED_WILD\nHSGuru: .*format=1&player_class=MAGE/);
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
