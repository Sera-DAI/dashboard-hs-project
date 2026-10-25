import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  buscar,
  carregarJson,
  higienizarTexto,
  historicoDaCarta,
  lerRota,
  nomeClasse,
  normalizar,
  rotaPatch
} from "../../site/js/logica.js";

const cartasDados = JSON.parse(await readFile(new URL("./dados/cartas.json", import.meta.url), "utf8"));
const patches = JSON.parse(await readFile(new URL("./dados/patches.json", import.meta.url), "utf8"));

test("normaliza acentos e maiúsculas", () => {
  assert.equal(normalizar("POÇÃO Volátil"), "pocao volatil");
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
  assert.equal(rotaPatch("patches/2026-10-23-36.6.json"), "#patch/patches/2026-10-23-36.6.json");
});

test("retorna histórico da carta em ordem do mais novo para o mais antigo", () => {
  assert.deepEqual(historicoDaCarta("559", patches).map((patch) => patch.versao), ["36.6", "36.5"]);
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

test("rota desconhecida volta ao início e histórico ignora patches sem cartas", () => {
  assert.deepEqual(lerRota("#patch/outro.json"), { tipo: "inicio" });
  assert.deepEqual(historicoDaCarta("559", [{ cartas: null }]), []);
});

test("traduz a classe da carta e mantém valores desconhecidos", () => {
  assert.equal(nomeClasse("NEUTRAL"), "Neutra");
  assert.equal(nomeClasse("DEMONHUNTER"), "Caçador de Demônios");
  assert.equal(nomeClasse("WHIZBANG"), "WHIZBANG");
  assert.equal(nomeClasse(null), "");
});
