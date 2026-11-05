import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  buscar,
  carregarJson,
  fatia,
  higienizarTexto,
  historicoDaCarta,
  lerRota,
  nomeClasse,
  normalizar,
  rotaNoticia,
  rotaPatch,
  rotuloDoGrupo,
  secoesDoPatch,
  topicosDoResumo
} from "../../site/js/logica.js";

const cartasDados = JSON.parse(await readFile(new URL("./dados/cartas.json", import.meta.url), "utf8"));
const patches = JSON.parse(await readFile(new URL("./dados/patches.json", import.meta.url), "utf8"));

test("normaliza acentos e maiúsculas", () => {
  assert.equal(normalizar("POÇÃO Volátil"), "pocao volatil");
});

test("fatia listas por quantidade sem alterar a lista original", () => {
  const lista = [1, 2, 3, 4];
  assert.deepEqual(fatia(lista, 2), [1, 2]);
  assert.deepEqual(fatia(lista, 10), lista);
  assert.deepEqual(fatia(null, 10), []);
  assert.deepEqual(lista, [1, 2, 3, 4]);
});

test("busca sem acento e prioriza nomes que começam pela consulta", () => {
  assert.deepEqual(buscar(cartasDados.cartas, "leeroy").map((carta) => carta.nome), [
    "Leeroy Aprendiz",
    "Leeroy Jenkins"
  ]);
  assert.equal(buscar(cartasDados.cartas, "pocao")[0].nome, "Poção Volátil");
  assert.deepEqual(buscar(cartasDados.cartas, "l"), []);
});

test("higieniza a marcação da carta sem interpretar HTML perigoso", () => {
  const tokens = higienizarTexto(cartasDados.cartas["559"].texto);
  assert.deepEqual(tokens.filter((token) => token.tipo === "tag"), [
    { tipo: "tag", nome: "b", fechar: false },
    { tipo: "tag", nome: "b", fechar: true }
  ]);
  const texto = tokens.filter((token) => token.tipo === "texto").map((token) => token.texto).join("");
  assert.match(texto, /<script>alert\(1\)<\/script>/);
  assert.match(texto, /<img src=x onerror=alert\(1\)>/);
  assert.match(texto, /2 3 Fim/);
  assert.doesNotMatch(texto, /\[x\]|\$2|#3|\n/);
});

test("lê rotas de patch e carta e monta o hash do patch", () => {
  assert.deepEqual(lerRota(""), { tipo: "inicio" });
  assert.deepEqual(lerRota("#patch/patches/2026-10-23-36.6.json"), {
    tipo: "patch",
    arquivo: "patches/2026-10-23-36.6.json"
  });
  assert.deepEqual(lerRota("#carta/559"), { tipo: "carta", dbfId: "559" });
  assert.deepEqual(lerRota("#noticia/noticias/2026-10-24-24310001.json"), {
    tipo: "noticia",
    arquivo: "noticias/2026-10-24-24310001.json"
  });
  assert.equal(rotaPatch("patches/2026-10-23-36.6.json"), "#patch/patches/2026-10-23-36.6.json");
  assert.equal(rotaNoticia("noticias/2026-10-24-24310001.json"), "#noticia/noticias/2026-10-24-24310001.json");
});

test("retorna histórico da carta em ordem do mais novo para o mais antigo", () => {
  assert.deepEqual(historicoDaCarta("559", patches).map((patch) => patch.versao), ["36.6", "36.5"]);
});

test("histórico da carta mostra o texto alterado (D46)", () => {
  const revisado = [{ versao: "37.0", data: "2026-10-12", cartas: { buffs: [], nerfs: [], alteradas: [], revisadas: [{ dbfId: 7, mudancas: [] }] } }];
  assert.deepEqual(historicoDaCarta("7", revisado).map((patch) => patch.versao), ["37.0"]);
});

test("as seções do patch separam Padrão e Livre e contam cada grupo", () => {
  const cartas = [
    { grupo: "buffs", formato: "padrao" },
    { grupo: "revisadas", formato: "padrao" },
    { grupo: "nerfs", formato: "livre" },
    { grupo: "alteradas", formato: "livre" },
    { grupo: "revisadas", formato: "livre" },
    { grupo: "buffs" }
  ];
  const secoes = secoesDoPatch({ cartas });
  assert.deepEqual(secoes.map((secao) => secao.chave), ["padrao", "livre", "sem"]);
  assert.deepEqual(secoes.map((secao) => secao.rotulo), ["Padrão", "Livre", "Sem formato definido"]);
  const [padrao, livre] = secoes;
  assert.deepEqual([padrao.buffs, padrao.nerfs, padrao.alteradas, padrao.revisadas], [1, 0, 0, 1]);
  assert.deepEqual([livre.buffs, livre.nerfs, livre.alteradas, livre.revisadas], [0, 1, 1, 1]);
});

test("sem o formato nas cartas o patch tem uma seção só, e um formato vazio continua aparecendo", () => {
  assert.deepEqual(secoesDoPatch({ cartas: [{ grupo: "buffs" }] }).map((secao) => secao.chave), ["todas"]);
  assert.deepEqual(secoesDoPatch({ cartas: [] }).map((secao) => secao.chave), ["todas"]);
  const so_livre = secoesDoPatch({ cartas: [{ grupo: "nerfs", formato: "livre" }] });
  assert.deepEqual(so_livre.map((secao) => [secao.chave, secao.cartas.length]), [["padrao", 0], ["livre", 1]]);
});

test("rótulo do grupo para a etiqueta da carta", () => {
  assert.deepEqual(["buffs", "nerfs", "alteradas", "revisadas"].map(rotuloDoGrupo), ["buff", "nerf", "alterada", "texto"]);
});

test("busca mostra uma carta por nome, só do Padrão ou Selvagem, preferindo o Núcleo", () => {
  const cartas = {
    559: { nome: "Leeroy Jenkins", colecao: "EXPERT1" },
    69501: { nome: "Leeroy Jenkins", colecao: "CORE" },
    69852: { nome: "Leeroy Jenkins", colecao: "VANILLA" },
    111462: { nome: "Leeroy Jenkins", colecao: "CORE_HIDDEN" },
    98725: { nome: "Leeroy Torcedor", colecao: "HERO_SKINS" },
    40: { nome: "Leeroy Aprendiz", colecao: "LEGACY" },
    41: { nome: "Leeroy Aprendiz", colecao: "EXPERT1" }
  };
  assert.deepEqual(buscar(cartas, "leeroy").map((carta) => [carta.nome, carta.dbfId]), [
    ["Leeroy Aprendiz", "41"],
    ["Leeroy Jenkins", "69501"]
  ]);
});

test("uma resposta HTTP com erro gera falha carregável pela interface", async () => {
  await assert.rejects(
    carregarJson("dados/indice.json", async () => ({ ok: false, status: 503 })),
    (erro) => erro.status === 503
  );
});

test("JSON inválido também é propagado como erro", async () => {
  await assert.rejects(
    carregarJson("dados/indice.json", async () => ({ ok: true, json: async () => { throw new SyntaxError("inválido"); } })),
    SyntaxError
  );
});

test("busca limita os resultados e aceita dados ausentes", () => {
  assert.deepEqual(buscar(null, "leeroy"), []);
  assert.deepEqual(buscar(cartasDados.cartas, "leeroy", 1).map((carta) => carta.nome), [
    "Leeroy Aprendiz"
  ]);
  assert.deepEqual(buscar(cartasDados.cartas, "  ", 8), []);
});

test("higieniza marcação sem perder negrito, itálico ou texto de tags desconhecidas", () => {
  assert.deepEqual(higienizarTexto(" [x] <b>Negrito</b> <i>itálico</i>\n<script>x</script> $12 #3"), [
    { tipo: "tag", nome: "b", fechar: false },
    { tipo: "texto", texto: "Negrito" },
    { tipo: "tag", nome: "b", fechar: true },
    { tipo: "texto", texto: " " },
    { tipo: "tag", nome: "i", fechar: false },
    { tipo: "texto", texto: "itálico" },
    { tipo: "tag", nome: "i", fechar: true },
    { tipo: "texto", texto: " <script>x</script> 12 3" }
  ]);
});

test("higieniza a marca de quebra de linha do HearthstoneJSON", () => {
  assert.deepEqual(higienizarTexto("<b>Último Suspiro:</b>& Evoque um 5/5."), [
    { tipo: "tag", nome: "b", fechar: false },
    { tipo: "texto", texto: "Último Suspiro:" },
    { tipo: "tag", nome: "b", fechar: true },
    { tipo: "texto", texto: " Evoque um 5/5." }
  ]);
});

test("rota desconhecida volta ao início e histórico ignora patches sem cartas", () => {
  assert.deepEqual(lerRota("#patch/outro.json"), { tipo: "inicio" });
  assert.deepEqual(historicoDaCarta("559", [{ cartas: null }]), []);
});

test("retorna tópicos apenas quando o resumo tem o formato esperado", () => {
  assert.deepEqual(topicosDoResumo({ resumo_ia: { topicos: ["<script>alert(1)</script>"] } }), [
    "<script>alert(1)</script>"
  ]);
  assert.deepEqual(topicosDoResumo({ resumo_ia: null }), []);
  assert.deepEqual(topicosDoResumo({ resumo_ia: { topicos: "inválido" } }), []);
  assert.deepEqual(topicosDoResumo({ resumo_ia: { topicos: ["válido", 2] } }), []);
});

test("traduz a classe da carta e mantém valores desconhecidos", () => {
  assert.equal(nomeClasse("NEUTRAL"), "Neutra");
  assert.equal(nomeClasse("DEMONHUNTER"), "Caçador de Demônios");
  assert.equal(nomeClasse("WHIZBANG"), "WHIZBANG");
  assert.equal(nomeClasse(null), "");
});
