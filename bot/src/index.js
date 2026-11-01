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
        dashboard: env.DASHBOARD_URL
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
