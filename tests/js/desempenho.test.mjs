import test from "node:test";
import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import vm from "node:vm";
import { carregarBase, carregarCatalogo, combinarDados, carregarDados } from "../../site/js/dados.js";
import { prepararPatches } from "../../site/js/logica.js";

const raiz = new URL("../../site/", import.meta.url);
const ler = (caminho) => readFile(new URL(caminho, raiz), "utf8");

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

const documentos = {
  "dados/indice.json": { patches: [{ arquivo: "patches/1.0.json", data: "2026-04-28", versao: "1.0" }] },
  "dados/noticias.json": { noticias: [{ arquivo: "noticias/a.json", data: "2026-04-28", titulo: "A" }] },
  "dados/cartas.json": { cartas: { 7: { id: "TEST_007", nome: "Sete", classe: "MAGE", custo: 3, texto: "Texto atual" } } },
  "dados/imagens.json": { imagens: { 7: "d".repeat(64) } },
  "dados/patches/1.0.json": {
    versao: "1.0",
    data: "2026-04-28",
    cartas: { buffs: [{ dbfId: 7, nome: "Sete", classe: "MAGE", mudancas: [{ campo: "custo", antes: 4, depois: 3 }] }] }
  },
  "dados/noticias/a.json": { resumo_ia: { topicos: ["Resumo próprio"] } }
};

test("D50: a base não pede o catálogo nem as imagens oficiais", async () => {
  const chamadas = [];
  const base = await carregarBase(leitorLocal(documentos, chamadas));
  assert.deepEqual(chamadas.sort(), [
    "dados/indice.json", "dados/noticias.json", "dados/noticias/a.json", "dados/patches/1.0.json"
  ]);
  const dados = combinarDados(base);
  assert.equal(dados.patches[0].buffs, 1);
  assert.equal(dados.patches[0].cartas[0].nome, "Sete");
  assert.equal(dados.patches[0].cartas[0].id, undefined);
  assert.deepEqual(dados.cartas, {});
  assert.deepEqual(dados.imagens, {});
  assert.deepEqual(dados.noticias[0].topicos, ["Resumo próprio"]);
});

test("D50: o catálogo só entra na segunda etapa e completa as cartas dos patches", async () => {
  const chamadas = [];
  const leitor = leitorLocal(documentos, chamadas);
  const base = await carregarBase(leitor);
  const catalogo = await carregarCatalogo(leitor);
  assert.deepEqual(chamadas.slice(-2).sort(), ["dados/cartas.json", "dados/imagens.json"]);
  const dados = combinarDados(base, catalogo);
  assert.equal(dados.patches[0].cartas[0].id, "TEST_007");
  assert.equal(dados.patches[0].cartas[0].depois.custo, 3);
  assert.equal(dados.patches[0].cartas[0].antes.custo, 4);
  assert.deepEqual(dados.imagens, { 7: "d".repeat(64) });
  // carregarDados continua sendo as duas etapas juntas.
  const junto = await carregarDados(leitorLocal(documentos));
  assert.deepEqual(junto.patches, dados.patches);
});

test("D50: catálogo inválido ou ausente falha em voz alta, sem derrubar a base", async () => {
  const base = await carregarBase(leitorLocal({ ...documentos, "dados/cartas.json": { cartas: [] } }));
  assert.equal(base.patches.length, 1);
  await assert.rejects(carregarCatalogo(leitorLocal({ ...documentos, "dados/cartas.json": { cartas: [] } })), /Catálogo inválido/);
  await assert.rejects(carregarCatalogo(async () => ({ ok: false, status: 503 })), (erro) => erro.status === 503);
});

test("D50: o estado das cartas é copiado só para as que aparecem nos patches", () => {
  const cartas = {};
  for (let id = 1; id <= 5000; id += 1) {
    cartas[id] = { id: "C" + id, nome: "Carta " + id, custo: 1, texto: "x" };
  }
  const patches = [
    { versao: "2", data: "2026-06-01", cartas: { buffs: [{ dbfId: 7, nome: "Carta 7", mudancas: [{ campo: "custo", antes: 2, depois: 1 }] }] } },
    { versao: "1", data: "2026-05-01", cartas: { nerfs: [{ dbfId: 7, nome: "Carta 7", mudancas: [{ campo: "custo", antes: 3, depois: 2 }] }] } }
  ];
  const preparados = prepararPatches(patches, cartas);
  assert.equal(preparados[0].cartas[0].depois.custo, 1);
  assert.equal(preparados[0].cartas[0].antes.custo, 2);
  assert.equal(preparados[1].cartas[0].depois.custo, 2);
  assert.equal(preparados[1].cartas[0].antes.custo, 3);
  assert.equal(cartas[7].custo, 1, "o catálogo não é alterado");
});

function rodarRota(hash) {
  const links = [];
  const atributos = {};
  const documento = {
    documentElement: { setAttribute: (chave, valor) => { atributos[chave] = valor; } },
    head: { appendChild: (no) => links.push(no) },
    createElement: () => {
      const no = { atributos: {}, setAttribute(chave, valor) { this.atributos[chave] = valor; } };
      return no;
    }
  };
  return ler("js/rota.js").then((codigo) => {
    vm.runInNewContext(codigo, { location: { hash }, document: documento, String });
    return { atributos, links };
  });
}

test("D50: rota.js marca a rota e pede cedo só o que a página precisa", async () => {
  const inicio = await rodarRota("");
  assert.equal(inicio.atributos["data-rota"], "inicio");
  assert.equal(inicio.links.length, 1);
  assert.equal(inicio.links[0].atributos.as, "image");

  const patch = await rodarRota("#/patches/37.0");
  assert.equal(patch.atributos["data-rota"], "patches");
  assert.deepEqual(patch.links.map((no) => no.atributos.href ?? no.atributos.as), ["image", "dados/cartas.json", "dados/imagens.json"]);

  for (const [hash, pagina] of [["#patch/patches/2026-10-12-37.0.json", "patches"], ["#carta/126253", "cartas"], ["#noticia/noticias/x.json", "noticias"], ["#/noticias", "noticias"], ["#/meta", "meta"], ["#/qualquer", "inicio"]]) {
    const { atributos, links } = await rodarRota(hash);
    assert.equal(atributos["data-rota"], pagina, hash);
    assert.equal(links.some((no) => no.atributos.href === "dados/cartas.json"), pagina === "patches" || pagina === "cartas", hash);
  }
});

test("D50: o srcset e o sizes de rota.js são os mesmos das <img> de index.html, e os arquivos existem", async () => {
  const html = await ler("index.html");
  const artes = new Map();
  for (const [, tag] of html.matchAll(/<img ([^>]*srcset="[^"]*"[^>]*)>/g)) {
    const srcset = /srcset="([^"]*)"/.exec(tag)[1];
    const sizes = /sizes="([^"]*)"/.exec(tag)[1];
    const nome = /src="img\/([a-z]+)-darc\.webp"/.exec(tag)[1];
    artes.set(nome === "bot" ? "bot" : nome, { srcset, sizes });
    for (const candidato of srcset.split(",")) {
      await access(new URL(candidato.trim().split(" ")[0], raiz));
    }
  }
  const paginas = ["inicio", "patches", "cartas", "noticias", "meta"];
  const codigo = await ler("js/rota.js");
  for (const pagina of paginas) {
    const arte = artes.get(pagina);
    assert.ok(arte, `index.html não tem a arte de ${pagina}`);
    assert.ok(codigo.includes(`"${arte.srcset}"`), `rota.js não repete o srcset de ${pagina}`);
    const sizes = arte.sizes === "(max-width: 760px) 640px, 100vw" ? "faixa" : `"${arte.sizes}"`;
    assert.ok(codigo.includes(`${pagina}: ["${arte.srcset}", ${sizes}]`), `rota.js não repete o sizes de ${pagina}`);
  }
});

test("D50: rota.js entra no <head> antes do CSS e o início só some quando a rota é outra", async () => {
  const [html, css] = await Promise.all([ler("index.html"), ler("css/darc.css")]);
  const cabeca = html.slice(0, html.indexOf("</head>"));
  assert.ok(cabeca.indexOf('<script src="js/rota.js"></script>') > 0, "rota.js fora do <head>");
  assert.ok(cabeca.indexOf("js/rota.js") < cabeca.indexOf("css/darc.css"));
  assert.doesNotMatch(html, /<script(?![^>]*src=)[^>]*>/, "nenhum script embutido em index.html (a CSP não tem unsafe-inline)");
  assert.match(css, /html\[data-rota\]:not\(\[data-rota="inicio"\]\) \.pagina\[data-pagina="inicio"\] \{ display: none; \}/);
  const app = await ler("js/app.js");
  assert.match(app, /delete document\.documentElement\.dataset\.rota/);
});
