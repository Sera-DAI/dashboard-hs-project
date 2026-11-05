"""Resumo manual (D48): prepara o pedido e grava o resumo escrito por uma pessoa ou por outro assistente.

Não usa chave nem API paga. A ação `preparar` imprime a mesma instrução e a mesma mensagem que o Gemini recebe;
quem escreve o resumo (o Claude na thread, ou o responsável no app do Gemini ou do ChatGPT) devolve os tópicos; a ação
`gravar` passa por `resumo_ia.validar`, guarda em dados/ e tira o item da fila. O texto da Blizzard só aparece no
log do Actions (privado), nunca em dados/ (D25).
"""

import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from hsds import blizzard, gravacao, http, resumo_ia
from hsds.http import ErroFonte
from hsds.monitor import LISTA

RAIZ = Path("dados")
ARQUIVO_VALIDO = re.compile(r"^(patches|noticias)/[0-9A-Za-z._-]+\.json$")
MODELO_MANUAL = "manual"


class ErroManual(Exception):
    """Mensagem curta e segura para o log (sem texto da Blizzard)."""


def _registro(raiz: Path, arquivo: str) -> dict:
    if not ARQUIVO_VALIDO.fullmatch(arquivo) or ".." in arquivo:
        raise ErroManual("arquivo inválido: use o nome como está em resumos_pendentes, por exemplo patches/2026-11-03-37.0.2.json")
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


def _fonte(identificador: int, baixar=None) -> blizzard.Noticia:
    """A notícia com texto: pt-BR se a lista trouxe o conteúdo, senão a versão em inglês (mesmo id)."""
    baixar = baixar or http.baixar
    for idioma in ("pt-br", "en-us"):
        try:
            lista = blizzard.noticias(baixar(LISTA.format(idioma=idioma)), idioma)
        except ErroFonte:
            continue
        noticia = next((item for item in lista if item.id == identificador and item.texto), None)
        if noticia:
            return noticia
    raise ErroManual("a notícia não está (ou veio sem texto) na lista atual da Blizzard")


def pedido(raiz: Path, arquivo: str, baixar=None) -> tuple[str, str]:
    """Devolve (instrução, mensagem) iguais às enviadas ao Gemini."""
    registro = _registro(raiz, arquivo)
    fonte = _fonte(_identificador(arquivo, registro), baixar)
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
        "Para este pedido, responda só com os tópicos, um por linha, sem numeração, sem markdown e sem texto extra.\n\n"
        f"{mensagem}\n"
        "=== FIM DO PEDIDO ===\n\n"
        f"Para gravar: rode o workflow resumo-manual com acao=gravar, arquivo={arquivo} e os tópicos separados por ' | '."
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
    for pedaco in re.split(r"[\n|]", bruto):
        pedaco = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", pedaco).strip()
        if pedaco:
            itens.append(pedaco)
    return itens


def gravar(raiz: Path, arquivo: str, bruto: str, agora: datetime | None = None, baixar=None) -> list[str]:
    registro = _registro(raiz, arquivo)
    # Sem reler a notícia não dá para checar cópia (D25): recusa em vez de gravar às cegas.
    original = blizzard.sem_html(_fonte(_identificador(arquivo, registro), baixar).texto)
    topicos = resumo_ia.validar(topicos_do_texto(bruto), original)
    if registro.get("resumo_ia"):
        print(f"Aviso: {arquivo} já tinha resumo; ele será substituído.")
    instante = (agora or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")
    registro["resumo_ia"] = {"topicos": topicos, "modelo": MODELO_MANUAL, "gerado": instante}
    estado = gravacao.ler(raiz / "estado.json", {})
    estado["resumos_pendentes"] = [item for item in estado.get("resumos_pendentes", []) if item["arquivo"] != arquivo]
    gravacao.gravar({raiz / arquivo: registro, raiz / "estado.json": estado})
    return topicos


def main() -> int:
    acao = os.environ.get("ACAO", "preparar")
    arquivo = os.environ.get("ARQUIVO", "").strip()
    try:
        if not arquivo:
            fila = [item["arquivo"] for item in gravacao.ler(RAIZ / "estado.json", {}).get("resumos_pendentes", [])]
            print("Fila de resumos pendentes: " + (", ".join(fila) if fila else "vazia"))
            if acao != "preparar" or not fila:
                return 0 if acao == "preparar" else 1
            arquivo = fila[0]
        if acao == "preparar":
            instrucao, mensagem = pedido(RAIZ, arquivo)
            _imprimir_pedido(arquivo, instrucao, mensagem)
        elif acao == "gravar":
            topicos = gravar(RAIZ, arquivo, os.environ.get("TOPICOS", ""))
            print(f"Resumo gravado em {arquivo} com {len(topicos)} tópicos.")
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
