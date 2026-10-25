"""Testa o resumo mais recente sem gravar arquivos."""

import os
import sys

from hsds import blizzard, formatador, http, resumo_ia, telegram
from hsds.monitor import LISTA


def main() -> int:
    try:
        noticias = blizzard.noticias(http.baixar(LISTA.format(idioma="pt-br")), "pt-br")
        tipo = os.environ.get("TIPO", "patch")
        if tipo not in {"patch", "noticia"}:
            tipo = "patch"
        candidatos = sorted(
            (noticia for noticia in noticias if blizzard.e_patch(noticia) == (tipo == "patch")),
            key=lambda noticia: (noticia.publicada, noticia.id),
            reverse=True,
        )
        if not candidatos:
            raise resumo_ia.ErroResumo("nenhuma notícia desse tipo na lista")
        noticia = candidatos[0]
        topicos = resumo_ia.gerar(
            noticia.titulo,
            noticia.texto,
            "pt-br",
            None,
            os.environ.get("GEMINI_API_KEY", ""),
            com_cartas=tipo == "patch",
        )
        mensagens = formatador.resumo_teste(noticia.dados(), topicos)
    except resumo_ia.ErroResumo as erro:
        mensagens = formatador.resumo_teste_falhou(erro.motivo)
        codigo = 1
    except http.ErroFonte as erro:
        motivo = "serviço fora do ar ou sem resposta" if erro.motivo == "site fora do ar ou sem resposta" else "resposta inválida"
        mensagens = formatador.resumo_teste_falhou(motivo)
        codigo = 1
    else:
        codigo = 0
    try:
        for mensagem in mensagens:
            telegram.enviar_mensagem(
                os.environ.get("TELEGRAM_TOKEN", ""),
                os.environ.get("TELEGRAM_CHAT_ID", ""),
                mensagem,
            )
    except telegram.ErroTelegram:
        return 1
    return codigo


if __name__ == "__main__":
    sys.exit(main())
