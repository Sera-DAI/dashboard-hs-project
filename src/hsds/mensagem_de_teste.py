"""Envia a mensagem de teste do M0. Lê o token e o chat id do ambiente."""

import os
import sys

from hsds.telegram import ErroTelegram, enviar_mensagem

TEXTO = "Hearthstone DS: mensagem de teste"


def main() -> int:
    try:
        enviar_mensagem(
            os.environ.get("TELEGRAM_TOKEN", ""),
            os.environ.get("TELEGRAM_CHAT_ID", ""),
            TEXTO,
        )
    except ErroTelegram as erro:
        print(f"Falha no envio: {erro}", file=sys.stderr)
        return 1
    print("Mensagem de teste enviada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
