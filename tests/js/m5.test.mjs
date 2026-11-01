import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { prepararPatches, imagemDaCarta, marcaMudanca, filtrarCarta, lerRota, rotaVersao, assuntoNoticia } from "../../site/js/logica.js";
import { carregarDados } from "../../site/js/dados.js";
import { ligarImagem } from "../../site/js/cartas.js";
import { linksMeta } from "../../site/js/meta.js";
import { descricaoCarta } from "../../site/js/elementos.js";

const fixture = JSON.parse((await readFile(new URL("./dados/m5.json", import.meta.url), "utf8")).replace(/^\uFEFF/, ""));
const preparados = prepararPatches(fixture.patches, fixture.cartas);

test("M5 lê todas as rotas novas e preserva hashes antigos", () => {
  for (const tipo of ["patches", "cartas", "noticias", "meta"]) {
    assert.deepEqual(lerRota("#/" + tipo), { tipo });
  }
  assert.deepEqual(lerRota("#/"), { tipo: "inicio" });
  assert.deepEqual(lerRota("#/patches/36.6.3"), { tipo: "patches", versao: "36.6.3" });
  assert.deepEqual(lerRota("#/patches/%E0%A4"), { tipo: "patches" });
  assert.equal(rotaVersao("37.0"), "#/patches/37.0");
  assert.deepEqual(lerRota("#/outra"), { tipo: "inicio" });
  assert.equal(lerRota("#patch/patches/36.6.json").arquivo, "patches/36.6.json");
});

test("M5 reconstrói atributos não alterados, desfaz revisadas e não muda os JSON", () => {
  const original = structuredClone(fixture);
  const [vazia, revisada, nova, antiga] = preparados;
  assert.equal(vazia.cartas.length, 0);
  assert.equal(revisada.cartas.length, 0);
  assert.equal(nova.cartas[0].antes.custo, 2);
  assert.equal(nova.cartas[0].depois.custo, 3);
  assert.equal(nova.cartas[0].depois.texto, "<b>Texto antigo.</b>");
  assert.equal(antiga.cartas[0].antes.custo, 5);
  assert.equal(antiga.cartas[0].depois.custo, 2);
  assert.equal(antiga.cartas[0].depois.vida, 7);
  assert.equal(antiga.cartas[0].antes.ataque, 4);
  assert.equal(antiga.cartas[0].historica, true);
  assert.equal(antiga.buffs, 1);
  assert.deepEqual(fixture, original);
});

test("M5 usa id da carta, ptBR, densidade e reserva para antes, histórico ou id inválido", () => {
  const carta = { ...fixture.cartas[7], historica: false };
  assert.equal(imagemDaCarta(carta), "https://art.hearthstonejson.com/v1/render/latest/ptBR/256x/TEST_007.png");
  assert.match(imagemDaCarta(carta, "depois", 2), /\/512x\/TEST_007.png$/);
  assert.equal(imagemDaCarta(carta, "antes", 2), null);
  assert.equal(imagemDaCarta(preparados[3].cartas[0]), null);
  const hash = "c".repeat(64);
  const oficial = { ...carta, dbfId: 77 };
  assert.equal(imagemDaCarta(oficial, "depois", 2, { 77: hash }), `https://d15f34w2p8l1cc.cloudfront.net/hearthstone/${hash}.png`);
  assert.match(imagemDaCarta(oficial, "depois", 1, { 77: "../x" }), /art\.hearthstonejson\.com/);
  assert.match(imagemDaCarta(oficial, "depois", 1, { 77: "C".repeat(64) }), /art\.hearthstonejson\.com/);
  assert.match(imagemDaCarta(oficial, "depois", 1, {}), /art\.hearthstonejson\.com/);
  assert.match(imagemDaCarta({ ...oficial, historica: true }, "depois", 1, { 77: hash }), /cloudfront\.net/);
  assert.equal(imagemDaCarta({ ...oficial, historica: true }, "depois", 1, {}), null);
  assert.equal(imagemDaCarta(oficial, "antes", 1, { 77: hash }), null);
  for (const id of [undefined, "", "../../segredo", 'x" onerror="x', "https://outro"]) {
    assert.equal(imagemDaCarta({ id }), null);
  }
});

test("M5 reserva sobrevive à falha de imagem sem fazer requisição no teste", () => {
  class Imagem extends EventTarget {
    style = {};
    atributos = new Map();
    removeAttribute(nome) {
      this.atributos.delete(nome);
    }
    set src(valor) {
      this.atributos.set("src", valor);
    }
  }
  const img = new Imagem();
  const reserva = { style: { display: "contents" } };
  ligarImagem(img, reserva, "imagem-local.png");
  img.dispatchEvent(new Event("error"));
  assert.equal(img.style.display, "none");
  assert.equal(reserva.style.display, "contents");
  assert.equal(img.atributos.has("src"), false);
  const sucesso = new Imagem();
  ligarImagem(sucesso, reserva, "imagem-local.png");
  sucesso.dispatchEvent(new Event("load"));
  assert.equal(sucesso.style.opacity, "1");
  assert.equal(reserva.style.display, "none");
});

test("M5 marca custo invertido, atributos maiores, zero e ausência sem inventar mudança", () => {
  const carta = preparados[3].cartas[0];
  assert.equal(marcaMudanca(carta, "depois", "custo"), "buff");
  assert.equal(marcaMudanca(carta, "antes", "custo"), "");
  assert.equal(marcaMudanca(carta, "depois", "ataque"), "");
  assert.equal(marcaMudanca({ antes: { custo: 1 }, depois: { custo: 0 } }, "depois", "custo"), "buff");
  assert.equal(marcaMudanca({ antes: { vida: 2 }, depois: { vida: 1 } }, "depois", "vida"), "nerf");
  assert.equal(marcaMudanca({ antes: {}, depois: { vida: 1 } }, "depois", "vida"), "");
  assert.match(descricaoCarta(carta, "antes"), /Poção Volátil, Mago, custo 5, ataque 4, vida 7/);
});

test("M5 filtros de cartas combinam grupo e nome sem acento", () => {
  const carta = preparados[3].cartas[0];
  assert.equal(filtrarCarta(carta, " POCAO ", "buffs"), true);
  assert.equal(filtrarCarta(carta, "volatil", "nerfs"), false);
  assert.equal(filtrarCarta(carta, "outra"), false);
});

test("M5 notícias reconhecem os assuntos do protótipo", () => {
  assert.equal(assuntoNoticia("Campeonato mundial")[0], "esports");
  assert.equal(assuntoNoticia("Aberrações nos Campos de Batalha")[0], "campos");
  assert.equal(assuntoNoticia("Trilha da Recompensa")[0], "loja");
  assert.equal(assuntoNoticia("Evento da comunidade")[0], "evento");
  assert.equal(assuntoNoticia("Nova expansão")[0], "expansao");
});

function leitorLocal(documentos, chamadas = []) {
  return async (url) => {
    chamadas.push(url);
    return {
      ok: Object.hasOwn(documentos, url),
      status: Object.hasOwn(documentos, url) ? 200 : 404,
      json: async () => structuredClone(documentos[url])
    };
  };
}

test("M5 carrega o contrato real uma vez, ordena notícias e aceita resumo na fila", async () => {
  const chamadas = [];
  const documentos = {
    "dados/indice.json": { patches: [{ arquivo: "patches/1.0.json", data: "2026-04-28", versao: "1.0" }] },
    "dados/noticias.json": { noticias: [
      { arquivo: "noticias/antiga.json", data: "2026-04-28", titulo: "Antiga" },
      { arquivo: "noticias/nova.json", data: "2026-06-01", titulo: "Nova" }
    ] },
    "dados/cartas.json": { cartas: fixture.cartas },
    "dados/imagens.json": { imagens: { 7: "d".repeat(64) } },
    "dados/patches/1.0.json": fixture.patches[0],
    "dados/noticias/antiga.json": { resumo_ia: { topicos: ["Resumo próprio"] } },
    "dados/noticias/nova.json": { resumo_ia: null }
  };
  const dados = await carregarDados(leitorLocal(documentos, chamadas));
  assert.equal(dados.patches[0].cartas[0].id, "TEST_007");
  assert.equal(dados.noticias[0].titulo, "Nova");
  assert.deepEqual(dados.noticias[0].topicos, []);
  assert.deepEqual(dados.noticias[1].topicos, ["Resumo próprio"]);
  assert.equal(new Set(chamadas).size, 7);
  assert.equal(chamadas.length, 7);
  assert.deepEqual(dados.imagens, { 7: "d".repeat(64) });
});

test("M5 índices vazios ou 404 não derrubam a página; falhas reais não viram sucesso vazio", async () => {
  const catalogo = { "dados/cartas.json": { cartas: fixture.cartas } };
  const vazio = await carregarDados(leitorLocal(catalogo));
  assert.deepEqual(vazio.patches, []);
  assert.deepEqual(vazio.noticias, []);
  assert.deepEqual(vazio.imagens, {});
  const invalido = await carregarDados(leitorLocal({ ...catalogo, "dados/imagens.json": { imagens: [1] } }));
  assert.deepEqual(invalido.imagens, {});
  await assert.rejects(carregarDados(async () => ({ ok: false, status: 503 })), (erro) => erro.status === 503);
  await assert.rejects(carregarDados(leitorLocal({ ...catalogo, "dados/indice.json": { patches: "inválido" } })), /Índice inválido/);
  await assert.rejects(carregarDados(leitorLocal({ ...catalogo, "dados/indice.json": { patches: [{ arquivo: "../estado.json" }] } })), /Caminho inválido/);
});

test("M5 classe ausente mantém diff legível e arma inclui durabilidade no texto alternativo", () => {
  const patch = prepararPatches([{ versao: "5", cartas: { buffs: [{ dbfId: 999, nome: "Removida", mudancas: [{ campo: "vida", antes: 1, depois: 2 }] }] } }], {});
  assert.equal(patch[0].cartas[0].antes.vida, 1);
  assert.equal(imagemDaCarta(patch[0].cartas[0]), null);
  assert.match(descricaoCarta({ ...fixture.cartas[8], depois: fixture.cartas[8] }, "depois"), /durabilidade 3/);
});

test("M5 meta oferece só links públicos da D33, por classe e formato, sem fonte de coleta", () => {
  assert.deepEqual(linksMeta("EVOKER", "padrao"), []);
  assert.deepEqual(linksMeta("MAGE", "padrao").map(([nome]) => nome), ["HSReplay", "HSGuru"]);
  assert.match(linksMeta("MAGE", "padrao")[0][1], /playerClasses=MAGE&gameType=RANKED_STANDARD$/);
  assert.match(linksMeta("MAGE", "selvagem")[0][1], /gameType=RANKED_WILD$/);
  assert.match(linksMeta("MAGE", "selvagem")[1][1], /format=1&player_class=MAGE&rank=diamond_to_legend&period=past_2_weeks&min_games=100$/);
  assert.ok(linksMeta("MAGE", "padrao").every(([, href]) => !href.includes("hearthstone-decks")));
});
