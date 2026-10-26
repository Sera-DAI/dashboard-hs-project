export async function enviar(fetcher, token, chatId, texto) {
  const resposta = await fetcher(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text: texto,
      disable_web_page_preview: true
    })
  });

  if (!resposta.ok) {
    throw new Error("Falha ao enviar mensagem.");
  }
}
