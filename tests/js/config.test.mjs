import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

const raiz = new URL("../../", import.meta.url);
const ler = (caminho) => readFile(new URL(caminho, raiz), "utf8");

test("o hash da CSP em site/_headers bate com o onload das fontes em index.html", async () => {
  const [html, cabecalhos] = await Promise.all([ler("site/index.html"), ler("site/_headers")]);
  const handlers = [...html.matchAll(/\son[a-z]+="([^"]*)"/g)].map((m) => m[1]);

  assert.deepEqual(handlers, ["this.media='all'"], "index.html só pode ter o onload das fontes");

  const hash = createHash("sha256").update(handlers[0]).digest("base64");
  assert.match(cabecalhos, new RegExp(`script-src-attr 'unsafe-hashes' 'sha256-${hash.replace(/[+/=]/g, "\\$&")}'`));
});

test("site/_headers mantém as proteções essenciais", async () => {
  const cabecalhos = await ler("site/_headers");

  assert.match(cabecalhos, /^\/\*$/m);
  for (const diretiva of ["frame-ancestors 'none'", "object-src 'none'", "base-uri 'none'", "form-action 'none'", "connect-src 'self'"]) {
    assert.ok(cabecalhos.includes(diretiva), `faltou ${diretiva}`);
  }
  assert.doesNotMatch(cabecalhos, /script-src[^;]*'unsafe-inline'/);
});

test.skip("o menu do bot em bot.yml bate com docs/mensagens.md e com o roteador", async () => {
  const [workflow, mensagens, comandos] = await Promise.all([
    ler(".github/workflows/bot.yml"),
    ler("docs/mensagens.md"),
    ler("bot/src/comandos.js")
  ]);
  const json = workflow.match(/'commands=(\[.*?\])'/)?.[1];
  assert.ok(json, "bot.yml sem o JSON de commands");
  const menu = JSON.parse(json);
  const linha = mensagens.split("\n").find((l) => l.startsWith("Menu do Telegram (`setMyCommands`)"));
  assert.ok(linha, "mensagens.md sem a linha do menu");
  const documentado = [...linha.matchAll(/`(\w+)` "([^"]+)"/g)].map((m) => ({ command: m[1], description: m[2] }));

  assert.deepEqual(menu, documentado);
  for (const { command } of menu) {
    if (command !== "ajuda") {
      assert.ok(comandos.includes(`comando === "${command}"`), `o roteador não trata /${command}`);
    }
  }
  assert.ok(!menu.some((c) => /Top 500/.test(c.description)), "o menu não pode prometer Top 500 (D38)");
});
