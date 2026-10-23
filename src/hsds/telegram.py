"""Envio de mensagens pela API de bots do Telegram, sem dependências externas."""

import json
import urllib.error
import urllib.request
from collections.abc import Callable

API = "https://api.telegram.org"


class ErroTelegram(Exception):
    """Falha ao enviar mensagem. Nunca carrega o token."""


def _abrir_padrao(requisicao: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(requisicao, timeout=20) as resposta:
        return resposta.read()


def enviar_mensagem(
    token: str,
    chat_id: str,
    texto: str,
    abrir: Callable[[urllib.request.Request], bytes] = _abrir_padrao,
) -> dict:
    """Envia `texto` ao `chat_id` e devolve a mensagem criada pela API."""
    if not token or not chat_id:
        raise ErroTelegram("token ou chat id ausente")
    corpo = json.dumps({"chat_id": chat_id, "text": texto}).encode("utf-8")
    requisicao = urllib.request.Request(
        f"{API}/bot{token}/sendMessage",
        data=corpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        bruto = abrir(requisicao)
    except urllib.error.HTTPError as erro:
        raise ErroTelegram(f"a API do Telegram respondeu HTTP {erro.code}") from None
    except urllib.error.URLError:
        # O motivo pode citar a URL, que contém o token.
        raise ErroTelegram("sem conexão com a API do Telegram") from None
    resposta = json.loads(bruto)
    if not resposta.get("ok"):
        descricao = resposta.get("description", "sem descrição")
        raise ErroTelegram(f"a API do Telegram recusou a mensagem: {descricao}")
    return resposta["result"]
