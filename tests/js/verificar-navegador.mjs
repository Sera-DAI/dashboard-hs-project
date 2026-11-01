// Verificação opcional: node tests/js/verificar-navegador.mjs <playwright> <navegador>
// Todas as requisições são respondidas de arquivos locais ou bloqueadas.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2] ?? "playwright");
const navegador = await chromium.launch({
  headless: true,
  ...(process.argv[3] ? { executablePath: process.argv[3] } : {})
});
const raiz = fileURLToPath(new URL("../../", import.meta.url)).replace(/[\\\/]$/, "");
const tipos = { html: "text/html", js: "text/javascript", css: "text/css", json: "application/json", webp: "image/webp", svg: "image/svg+xml" };
let externas = 0;

async function contexto(opcoes = {}, falharImagem = true, vazio = false) {
  const ctx = await navegador.newContext(opcoes);
  await ctx.route("**/*", async (rota) => {
    const url = new URL(rota.request().url());
    if (url.hostname === "art.hearthstonejson.com" || url.hostname === "d15f34w2p8l1cc.cloudfront.net") {
      externas += 1;
      if (falharImagem) {
        await rota.fulfill({ status: 404, body: "" });
      } else {
        await rota.fulfill({
          contentType: "image/png",
          body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=", "base64")
        });
      }
      return;
    }
    if (url.hostname !== "hsds.local") {
      await rota.fulfill({ status: 200, body: "", contentType: "text/css" });
      return;
    }
    let caminho = decodeURIComponent(url.pathname).replace(/^\/site\/dados\//, "/dados/");
    if (vazio && caminho === "/dados/indice.json") {
      await rota.fulfill({ json: { patches: [] } });
      return;
    }
    if (vazio && caminho === "/dados/noticias.json") {
      await rota.fulfill({ json: { noticias: [] } });
      return;
    }
    const arquivo = resolve(raiz, "." + caminho);
    assert.ok(arquivo.startsWith(raiz + sep));
    try {
      const corpo = await readFile(arquivo);
      await rota.fulfill({ body: corpo, contentType: tipos[arquivo.split(".").at(-1)] ?? "application/octet-stream" });
    } catch {
      await rota.fulfill({ status: 404, body: "" });
    }
  });
  return ctx;
}

async function largura(page, esperado) {
  const tamanho = await page.evaluate(() => ({
    largura: document.documentElement.clientWidth,
    conteudo: document.documentElement.scrollWidth
  }));
  assert.equal(tamanho.largura, esperado);
  assert.ok(tamanho.conteudo <= esperado, JSON.stringify(tamanho));
}

try {
  for (const tamanho of [1440, 400]) {
    const ctx = await contexto({ viewport: { width: tamanho, height: 1000 }, reducedMotion: "reduce", ...(tamanho === 400 ? { isMobile: true, hasTouch: true, deviceScaleFactor: 2 } : {}) });
    const page = await ctx.newPage();
    const erros = [];
    page.on("pageerror", (erro) => erros.push(erro.message));
    page.on("console", (mensagem) => {
      if (mensagem.type() === "error" && mensagem.text().includes("Falha ao carregar o dashboard")) {
        erros.push(mensagem.text());
      }
    });
    await page.goto("http://hsds.local/site/index.html");
    await page.waitForFunction(() => document.body.dataset.estado === "pronto");
    for (const rota of ["", "patches", "cartas", "noticias", "meta"]) {
      await page.goto("http://hsds.local/site/index.html#/" + rota);
      await page.waitForFunction((ativa) => document.querySelector(".pagina:not([hidden])").dataset.pagina === ativa, rota || "inicio");
      assert.equal(await page.locator(".pagina:not([hidden])").count(), 1);
      await largura(page, tamanho);
    }
    await page.goto("http://hsds.local/site/index.html#/patches/37.0");
    await page.locator("#foco").scrollIntoViewIfNeeded();
    await page.waitForFunction(() => document.querySelector("#foco .frente > img")?.style.display === "none");
    assert.equal(await page.locator("#foco .frente > div").evaluate((no) => getComputedStyle(no).display), "contents");
    if (process.env.HSDS_CAPTURAS) {
      await page.screenshot({ path: resolve(raiz, "tests/js/dados/m5-" + tamanho + ".png") });
    }
    await page.locator("#foco").focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator("#foco").getAttribute("aria-pressed"), "true");
    await page.locator("#detalhe [data-v=antes]").click();
    assert.equal(await page.locator("#foco").getAttribute("data-versao"), "antes");
    assert.equal(await page.locator("#foco .frente > img").count(), 0);
    assert.equal(await page.locator('#foco .gema[data-campo="vida"]').innerText(), "3");
    await page.locator("#detalhe [data-v=depois]").click();
    assert.equal(await page.locator('#foco .gema[data-campo="vida"]').getAttribute("data-mudou"), "buff");
    await page.goto("http://hsds.local/site/index.html#/patches/36.6.3");
    assert.equal(await page.locator("#foco").getAttribute("data-versao"), "depois");
    assert.equal(await page.locator('#foco .gema[data-campo="custo"]').innerText(), "7");
    await page.locator("#detalhe [data-v=antes]").click();
    assert.equal(await page.locator('#foco .gema[data-campo="custo"]').innerText(), "6");

    await page.goto("http://hsds.local/site/index.html#/cartas");
    const quantidade = await page.locator(".grupo-patch").count();
    assert.ok(quantidade > 0);
    await page.locator("#busca-cartas").fill("isiset");
    assert.ok(await page.locator(".grupo-patch:not([hidden])").count() > 0);
    await page.locator('.grupo-patch:not([hidden]) .grade-cartas li:not([hidden]) button').first().click();
    assert.equal(await page.locator("#janela-carta").evaluate((no) => no.open), true);
    assert.equal(await page.locator("#carta-titulo").innerText(), "Isiset");
    await page.locator("#carta-grande").focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator("#carta-grande").getAttribute("aria-pressed"), "true");
    await page.keyboard.press("Escape");
    assert.equal(await page.locator("#janela-carta").evaluate((no) => no.open), false);
    await page.locator("#busca-cartas").fill("");
    await page.locator("#filtro-cartas [data-grupo=nerfs]").click();
    assert.equal(await page.locator('.grupo-patch:not([hidden]) .grade-cartas li:not([hidden]):not([data-grupo="nerfs"])').count(), 0);
    await page.locator("#recolher-todos").click();
    assert.equal(await page.locator(".grupo-patch:not([hidden])[open]").count(), 0);
    await page.locator("#recolher-todos").click();
    assert.ok(await page.locator(".grupo-patch:not([hidden])[open]").count() > 0);
    await page.locator("#busca").fill("leeroy");
    await page.locator("#busca").press("Enter");
    assert.equal(await page.locator("#janela-carta").evaluate((no) => no.open), true);
    assert.match(await page.locator("#carta-titulo").innerText(), /Leeroy/);
    await page.keyboard.press("Escape");

    await page.goto("http://hsds.local/site/index.html#/noticias");
    await page.locator("#filtros [data-assunto=esports]").click();
    assert.equal(await page.locator('#notas .nota:not([hidden]):not([data-tipo="esports"])').count(), 0);
    await page.locator("#filtros [data-assunto=todas]").click();
    assert.equal(await page.locator("#notas .nota:not([hidden])").count(), 22);
    await page.locator("#notas summary").first().click();
    assert.equal(await page.locator("#notas details[open]").count(), 1);

    await page.goto("http://hsds.local/site/index.html#/meta");
    assert.equal(await page.locator('[data-pagina=meta] .brasao img').count(), 11);
    await page.locator('[data-pagina=meta] .brasao[data-classe=MAGE]').click();
    assert.equal(await page.locator("#janela-deck").evaluate((no) => no.open), true);
    await page.locator("#janela-deck [data-formato=selvagem]").click();
    assert.match(await page.locator("#decks a").first().getAttribute("href"), /playerClasses=MAGE&gameType=RANKED_WILD/);
    assert.equal(await page.locator("#decks .deck").count(), 2);
    await largura(page, tamanho);
    await page.keyboard.press("Escape");
    assert.deepEqual(erros, []);
    console.log(tamanho + " px: cinco rotas, filtros, busca, carta, decks, teclado e reserva aprovados.");
    await ctx.close();
  }

  const sucesso = await contexto({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" }, false);
  const page = await sucesso.newPage();
  await page.goto("http://hsds.local/site/index.html#/patches/37.0");
  await page.waitForFunction(() => document.body.dataset.estado === "pronto");
  await page.locator("#foco").scrollIntoViewIfNeeded();
  await page.waitForFunction(() => document.querySelector("#foco .frente > img")?.style.opacity === "1");
  assert.equal(await page.locator("#foco .frente > div").evaluate((no) => getComputedStyle(no).display), "none");
  assert.equal(await page.locator("#foco .frente > img").getAttribute("loading"), "lazy");
  assert.match(await page.locator("#foco .frente > img").getAttribute("alt"), /Improvisador Ardiloso.*vida 4/);
  await sucesso.close();

  const vazio = await contexto({ viewport: { width: 400, height: 900 }, reducedMotion: "reduce" }, true, true);
  const semDados = await vazio.newPage();
  await semDados.goto("http://hsds.local/site/index.html#/patches");
  await semDados.waitForFunction(() => document.body.dataset.estado === "pronto");
  assert.equal(await semDados.locator("#indice-patches li").count(), 0);
  await vazio.close();

  const normal = await contexto({ viewport: { width: 1440, height: 1000 } });
  const animada = await normal.newPage();
  const erros = [];
  animada.on("pageerror", (erro) => erros.push(erro.message));
  await animada.goto("http://hsds.local/site/index.html#/patches/37.0");
  await animada.waitForFunction(() => document.body.dataset.estado === "pronto");
  await animada.locator("#foco").scrollIntoViewIfNeeded();
  await animada.locator("#foco").hover();
  assert.ok(await animada.locator("#foco").evaluate((no) => no.classList.contains("segue")));
  await animada.emulateMedia({ reducedMotion: "reduce" });
  assert.equal(await animada.locator("#foco").evaluate((no) => no.style.getPropertyValue("--ry")), "0deg");
  for (const tamanho of [360, 1920]) {
    await animada.setViewportSize({ width: tamanho, height: 1000 });
    for (const rota of ["", "patches", "cartas", "noticias", "meta"]) {
      await animada.goto("http://hsds.local/site/index.html#/" + rota);
      await largura(animada, tamanho);
    }
  }
  assert.deepEqual(erros, []);
  await normal.close();
  console.log("360–1920 px: sem rolagem lateral. Imagem simulada, ausência de dados e troca de movimento reduzido aprovadas.");
  console.log("Requisições externas reais: 0; imagens interceptadas: " + externas + ".");
} finally {
  await navegador.close();
}
