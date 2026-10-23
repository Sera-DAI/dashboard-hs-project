import io
import json
import urllib.error

import pytest

from hsds.telegram import ErroTelegram, enviar_mensagem

TOKEN = "123456:token-ficticio"


def resposta(dados):
    return lambda requisicao: json.dumps(dados).encode("utf-8")


def test_monta_chamada_send_message():
    chamadas = []

    def abrir(requisicao):
        chamadas.append(requisicao)
        return json.dumps({"ok": True, "result": {"message_id": 7}}).encode("utf-8")

    resultado = enviar_mensagem(TOKEN, "42", "olá", abrir=abrir)

    assert resultado == {"message_id": 7}
    requisicao = chamadas[0]
    assert requisicao.full_url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert requisicao.get_method() == "POST"
    assert json.loads(requisicao.data) == {"chat_id": "42", "text": "olá"}


def test_recusa_da_api_vira_erro_claro():
    with pytest.raises(ErroTelegram, match="chat not found"):
        enviar_mensagem(TOKEN, "42", "olá", abrir=resposta({"ok": False, "description": "Bad Request: chat not found"}))


def test_token_ou_chat_ausente():
    with pytest.raises(ErroTelegram, match="ausente"):
        enviar_mensagem("", "42", "olá")
    with pytest.raises(ErroTelegram, match="ausente"):
        enviar_mensagem(TOKEN, "", "olá")


@pytest.mark.parametrize(
    "erro",
    [
        urllib.error.HTTPError(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 401, "Unauthorized", {}, io.BytesIO()),
        urllib.error.URLError(f"falha ao abrir https://api.telegram.org/bot{TOKEN}/sendMessage"),
    ],
)
def test_token_nunca_aparece_no_erro(erro):
    def abrir(requisicao):
        raise erro

    with pytest.raises(ErroTelegram) as capturado:
        enviar_mensagem(TOKEN, "42", "olá", abrir=abrir)
    assert TOKEN not in str(capturado.value)
    assert capturado.value.__cause__ is None
