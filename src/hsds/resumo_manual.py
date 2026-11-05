"""Resumo manual (D48, único modo desde a D54): prepara o pedido e grava o resumo escrito por uma pessoa.

Não usa chave nem API. A ação `preparar` imprime a instrução e a mensagem do resumo; quem escreve (uma pessoa no app
do Gemini, ou o Claude na thread) devolve os tópicos; a ação `gravar` passa por `resumo_ia.validar`, guarda em
dados/ e manda o resumo ao Telegram. O texto da Blizzard só aparece no log do Actions (privado), nunca em dados/ (D25).
"""

import os
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from hsds import blizzard, formatador, gravacao, http, resumo_ia, telegram
from hsds.http import ErroFonte
from hsds.monitor import LISTA

RAIZ = Path("dados")
ARQUIVO_VALIDO = re.compile(r"^(patches|noticias)/[0-9A-Za-z._-]+\.json$")
MODELO_MANUAL = "manual"
ESCRITORES = ("gemini", "claude", "outro")
INICIO_EXPANSAO = resumo_ia.INICIO_EXPANSAO  # D52 e D53: só a expansão atual recebe resumo
MAX_PAGINAS = 4
INTERVALO = 2


class ErroManual(Exception):
    """Mensagem curta e segura para o log (sem texto da Blizzard)."""


def _registro(raiz: Path, arquivo: str) -> dict:
    if not ARQUIVO_VALIDO.fullmatch(arquivo) or ".." in arquivo:
        raise ErroManual("arquivo inválido: use o nome como está em dados/, por exemplo patches/2026-11-03-37.0.2.json")
    registro = gravacao.ler(raiz / arquivo)
    if not isinstance(registro, dict):
        raise ErroManual(f"{arquivo} não existe em dados/")
    return registro


def _identificador(arquivo: str, registro: dict) -> int:
    if arquivo.startswith("patches/"):
        noticia = registro.get("noticia") or registro.get("noticia_en") or {}
        identificador = noticia.get("id")
    else:
        identificador = registro.get("id")
    if not isinstance(identificador, int) or isinstance(identificador, bool):
        raise ErroManual("o registro não tem a notícia da Blizzard associada ainda")
    return identificador


_ULTIMA_REQUISICAO: list[float | None] = [None]


def _pausar() -> None:
    """Garante `INTERVALO` segundos entre duas requisições à Blizzard na mesma execução (como o M2c-01)."""
    agora = time.monotonic()
    if _ULTIMA_REQUISICAO[0] is not None:
        time.sleep(max(0, INTERVALO - (agora - _ULTIMA_REQUISICAO[0])))
    _ULTIMA_REQUISICAO[0] = time.monotonic()


DATA_NO_NOME = re.compile(r"(?:patches|noticias)/(\d{4}-\d{2}-\d{2})-")


def _data_do_arquivo(arquivo: str) -> str:
    """A data AAAA-MM-DD do nome do arquivo (patches/2026-11-03-37.0.2.json)."""
    achado = DATA_NO_NOME.match(arquivo)
    if not achado:
        raise ErroManual("arquivo inválido: o nome precisa começar com a data, como patches/2026-11-03-37.0.2.json")
    return achado.group(1)


def _noticias_da_lista(idioma: str, baixar, desde: str):
    """Notícias da lista da Blizzard, página a página (12 por página), até passar da data `desde`.

    Para na primeira página cuja notícia mais antiga é anterior a `desde`, ou em `MAX_PAGINAS`, com `INTERVALO`
    segundos entre quaisquer duas requisições (também entre idiomas e entre a escolha e o pedido). Assume a lista em ordem de data decrescente; uma notícia fora de ordem pode fazer a leitura parar cedo. Falha na primeira página levanta ErroFonte; nas seguintes, só encerra a leitura.
    """
    for pagina in range(1, MAX_PAGINAS + 1):
        _pausar()
        url = LISTA.replace("page=1", f"page={pagina}").format(idioma=idioma)
        try:
            itens = blizzard.noticias(baixar(url), idioma)
        except ErroFonte:
            if pagina == 1:
                raise
            print(f"::warning::A leitura da lista da Blizzard ({idioma}) parou na página {pagina} por erro de rede; o resultado pode estar incompleto.")
            return
        yield from itens
        if not itens or min(item.publicada[:10] for item in itens) < desde:
            return


def _fonte(identificador: int, baixar=None, desde: str = INICIO_EXPANSAO) -> blizzard.Noticia:
    """A notícia com texto: pt-BR se a lista trouxe o conteúdo, senão a versão em inglês (mesmo id)."""
    baixar = baixar or http.baixar
    for idioma in ("pt-br", "en-us"):
        try:
            for item in _noticias_da_lista(idioma, baixar, desde):
                if item.id == identificador and item.texto:
                    return item
        except ErroFonte:
            continue
    raise ErroManual("a notícia não está (ou veio sem texto) nas páginas lidas da lista da Blizzard")


def _ids_na_lista(baixar=None, desde: str = INICIO_EXPANSAO) -> set[int]:
    """Ids das notícias da lista da Blizzard (páginas até `desde`) que vieram com texto, em pt-BR ou em inglês."""
    baixar = baixar or http.baixar
    ids: set[int] = set()
    falhas = 0
    for idioma in ("pt-br", "en-us"):
        try:
            ids.update(item.id for item in _noticias_da_lista(idioma, baixar, desde) if item.texto)
        except ErroFonte:
            falhas += 1
    if falhas == 2:
        raise ErroManual("a lista da Blizzard não respondeu; tente de novo mais tarde")
    return ids


def proximo_disponivel(raiz: Path, baixar=None) -> str | None:
    """Primeiro patch ou notícia da expansão atual, sem resumo, cuja notícia a lista da Blizzard ainda traz (D25 exige o texto).

    Só entram itens com data a partir de `INICIO_EXPANSAO`, do mais novo para o mais antigo.
    """
    candidatos = sorted(
        (caminho.relative_to(raiz).as_posix() for pasta in ("patches", "noticias") for caminho in (raiz / pasta).glob("*.json")),
        key=lambda nome: nome.split("/", 1)[1],
        reverse=True,
    )
    ids = _ids_na_lista(baixar, INICIO_EXPANSAO)
    for arquivo in candidatos:
        try:
            if _data_do_arquivo(arquivo) < INICIO_EXPANSAO:
                continue
            registro = _registro(raiz, arquivo)
            if registro.get("resumo_ia"):
                continue
            if _identificador(arquivo, registro) in ids:
                return arquivo
        except (ErroManual, KeyError, TypeError, AttributeError, ValueError):
            continue  # registro malformado ou fora do padrão: pula o candidato
    return None


def pedido(raiz: Path, arquivo: str, baixar=None) -> tuple[str, str]:
    """Devolve (instrução, mensagem) do pedido de resumo."""
    registro = _registro(raiz, arquivo)
    fonte = _fonte(_identificador(arquivo, registro), baixar, _data_do_arquivo(arquivo))
    idioma = "pt-br" if "/pt-br/" in fonte.link else "en-us"
    mensagem = resumo_ia.montar_mensagem(
        fonte.titulo, fonte.texto, idioma, registro.get("cartas"), com_cartas=arquivo.startswith("patches/")
    )
    return resumo_ia.INSTRUCAO, mensagem


def _imprimir_pedido(arquivo: str, instrucao: str, mensagem: str) -> None:
    # stop-commands impede que uma linha da notícia começando com "::" vire comando do Actions.
    marca = secrets.token_hex(8)
    saida = (
        f"PEDIDO DE RESUMO PARA {arquivo}\n\n"
        "=== COLE ISTO NO ASSISTENTE ===\n"
        f"{instrucao}\n\n"
        "Para este pedido, responda só com os tópicos, todos em uma única linha, separados por ' | ' (espaço, barra, espaço), "
        "sem numeração e sem texto extra; nenhum tópico pode conter a barra '|'. Sem markdown, exceto o bloco de código que envolve "
        "essa linha, para eu copiar de uma vez.\n\n"
        f"{mensagem}\n"
        "=== FIM DO PEDIDO ===\n\n"
        f"Para gravar: rode o workflow resumo-manual com acao=gravar, arquivo={arquivo}, escritor=gemini (ou o que escreveu) "
        "e, em topicos, a linha que o assistente devolveu (o campo do Actions aceita só uma linha, por isso o ' | ')."
    )
    print(f"::stop-commands::{marca}")
    print(saida)
    print(f"::{marca}::")
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as destino:
            maior = max((len(trecho) for trecho in re.findall(r"`+", saida)), default=0)
            cerca = "`" * max(3, maior + 1)
            destino.write(f"## Pedido de resumo\n\n{cerca}text\n{saida}\n{cerca}\n")


def topicos_do_texto(bruto: str) -> list[str]:
    """Separa por quebra de linha ou por '|'; tira marcadores de lista e numeração no começo."""
    itens = []
    # O assistente costuma devolver a linha dentro de um bloco de código: tira as cercas (```), que não são tópico.
    bruto = re.sub(r"```[A-Za-z]*", "\n", bruto)
    for pedaco in re.split(r"[\n|]", bruto):
        pedaco = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", pedaco).strip()
        if pedaco:
            itens.append(pedaco)
    return itens


def modelo_do_escritor(escritor: str) -> str:
    """`manual-gemini`, `manual-claude` ou `manual-outro`; em branco, `manual` (D48)."""
    escritor = escritor.strip().lower()
    if not escritor:
        return MODELO_MANUAL
    if escritor not in ESCRITORES:
        raise ErroManual("escritor deve ser gemini, claude ou outro")
    return f"{MODELO_MANUAL}-{escritor}"


def gravar(raiz: Path, arquivo: str, bruto: str, agora: datetime | None = None, baixar=None, escritor: str = "") -> list[str]:
    modelo = modelo_do_escritor(escritor)
    registro = _registro(raiz, arquivo)
    # Sem reler a notícia não dá para checar cópia (D25): recusa em vez de gravar às cegas.
    original = blizzard.sem_html(_fonte(_identificador(arquivo, registro), baixar, _data_do_arquivo(arquivo)).texto)
    topicos = resumo_ia.validar(topicos_do_texto(bruto), original)
    if registro.get("resumo_ia"):
        print(f"Aviso: {arquivo} já tinha resumo; ele será substituído.")
    instante = (agora or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")
    registro["resumo_ia"] = {"topicos": topicos, "modelo": modelo, "gerado": instante}
    gravacao.gravar({raiz / arquivo: registro})
    return topicos


def avisar(arquivo: str, registro: dict, enviar=None) -> bool:
    """Manda o resumo gravado ao Telegram (uma mensagem por item). Falha de envio não desfaz a gravação.

    Devolve se o envio aconteceu. O log traz só um texto fixo: nada da resposta do Telegram, que pode citar o token.
    """
    enviar = enviar or telegram.enviar_mensagem
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        print("::warning::Resumo gravado, mas o Telegram não recebeu o aviso: TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID ausente.")
        return False
    textos = formatador.resumo_atrasado(registro) if arquivo.startswith("patches/") else formatador.resumo_noticia(registro)
    try:
        for texto in textos:
            enviar(token, chat, texto)
    except Exception:  # qualquer falha de envio (rede, resposta fora do formato): o resumo já está gravado e o log não leva a causa
        print("::warning::Resumo gravado, mas o aviso ao Telegram falhou; o resumo já está no dashboard.")
        return False
    return True


def main() -> int:
    acao = os.environ.get("ACAO", "preparar")
    arquivo = os.environ.get("ARQUIVO", "").strip()
    try:
        if not arquivo:
            if acao != "preparar":
                return 1
            arquivo = proximo_disponivel(RAIZ)
            if not arquivo:
                print("::notice::Nenhum patch ou notícia da expansão atual sem resumo está na lista da Blizzard.")
                print(
                    f"Nenhum patch ou notícia sem resumo desde {INICIO_EXPANSAO} (Reinado dos Deuses Antigos) tem texto nas "
                    f"{MAX_PAGINAS} primeiras páginas da lista da Blizzard; nada a preparar. As expansões anteriores ficam "
                    "de fora do resumo manual (D52)."
                )
                return 0
            print(f"Escolhido {arquivo}: o primeiro sem resumo da expansão atual com texto na lista da Blizzard.")
        if acao == "preparar":
            instrucao, mensagem = pedido(RAIZ, arquivo)
            _imprimir_pedido(arquivo, instrucao, mensagem)
        elif acao == "gravar":
            topicos = gravar(RAIZ, arquivo, os.environ.get("TOPICOS", ""), escritor=os.environ.get("ESCRITOR", ""))
            print(f"Resumo gravado em {arquivo} com {len(topicos)} tópicos.")
            avisar(arquivo, gravacao.ler(RAIZ / arquivo))
        else:
            raise ErroManual("acao deve ser preparar ou gravar")
    except ErroManual as erro:
        print(f"Resumo manual: {erro}.")
        return 1
    except resumo_ia.ErroResumo as erro:
        print(f"Resumo manual recusado: {erro.motivo}.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
