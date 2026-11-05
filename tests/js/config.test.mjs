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
