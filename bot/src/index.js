import { responder } from "./comandos.js";
import { criarLeitor } from "./dados.js";
import { enviar } from "./telegram.js";
import { mensagemIndisponivel } from "./formatador.js";

function iguaisEmTempoConstante(primeiro, segundo) {
  const a = new TextEncoder().encode(String(primeiro ?? ""));
  const b = new TextEncoder().encode(String(segundo ?? ""));
  let diferenca = a.length ^ b.length;
  const tamanho = Math.max(a.length, b.length);

  for (let indice = 0; indice < tamanho; indice += 1) {
    diferenca |= (a[indice] ?? 0) ^ (b[indice] ?? 0);
  }

  return diferenca === 0;
}

function respostaVazia() {
  return new Response(null, { status: 200 });
}

async function lerTexto(url, limite, tempo) {
  const resposta = await fetch(url, {
    headers: { "User-Agent": "HearthstoneDS/0.1 (monitor pessoal; github.com/Sera-DAI)" },
    cf: { cacheTtl: 1800, cacheEverything: true },
    signal: AbortSignal.timeout(tempo)
  });

  if (resposta.status !== 200) {
    throw new Error("O hearthstone-decks.net respondeu com status diferente de 200.");
  }

  if (Number(resposta.headers.get("Content-Length") ?? 0) > limite) {
    throw new Error("A resposta do hearthstone-decks.net excedeu o limite.");
  }

  const texto = await resposta.text();

  if (new TextEncoder().encode(texto).byteLength > limite) {
    throw new Error("A resposta do hearthstone-decks.net excedeu o limite.");
  }

  return texto;
}

function lerFeed(url) {
  return lerTexto(url, 512 * 1024, 8000);
}

function lerPagina(url) {
  return lerTexto(url, 1024 * 1024, 6000);
}

export default {
  async fetch(request, env, ctx) {
    const segredo = request.headers.get("X-Telegram-Bot-Api-Secret-Token");

    if (request.method !== "POST" || !segredo || !env.TELEGRAM_WEBHOOK_SECRET || !iguaisEmTempoConstante(segredo, env.TELEGRAM_WEBHOOK_SECRET)) {
      return new Response(null, { status: 401 });
    }

    let update;

    try {
      update = await request.json();
    } catch {
      return respostaVazia();
    }

    const mensagem = update?.message;

    if (typeof mensagem?.text !== "string" || String(mensagem.chat?.id) !== String(env.TELEGRAM_CHAT_ID)) {
      return respostaVazia();
    }

    try {
      const lerJson = criarLeitor(fetch, env.DADOS_URL);
      const textos = await responder(mensagem.text, lerJson, {
        dashboard: env.DASHBOARD_URL,
        lerFeed,
        lerPagina
      });

      for (const texto of textos) {
        await enviar(fetch, env.TELEGRAM_TOKEN, env.TELEGRAM_CHAT_ID, texto);
      }
    } catch {
      try {
        await enviar(fetch, env.TELEGRAM_TOKEN, env.TELEGRAM_CHAT_ID, mensagemIndisponivel());
      } catch {
        return respostaVazia();
      }
    }

    return respostaVazia();
  }
};
