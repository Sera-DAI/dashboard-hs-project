"""Leitura da lista oficial; nunca retém o conteúdo completo da notícia."""

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser

from hsds.http import ErroFonte

PADRAO_PATCH = re.compile(r"(?:Notas do patch|Patch Notes)\b", re.IGNORECASE)


class _Texto(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []

    def handle_data(self, data):
        self.partes.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "p", "div"}:
            self.partes.append(" ")

    def handle_endtag(self, tag):
        if tag in {"p", "div"}:
            self.partes.append(" ")


def sem_html(texto: str) -> str:
    leitor = _Texto()
    leitor.feed(texto)
    return " ".join("".join(leitor.partes).split())


@dataclass(frozen=True)
class Noticia:
    id: int
    titulo: str
    link: str
    resumo: str
    publicada: str
    versao: str | None
    texto: str = ""

    def dados(self) -> dict:
        dados = asdict(self)
        dados.pop("versao")
        dados.pop("texto")
        return dados


def e_patch(noticia: Noticia) -> bool:
    return PADRAO_PATCH.search(noticia.titulo) is not None


def noticias(bruto: bytes, idioma: str) -> list[Noticia]:
    try:
        dados = json.loads(bruto)
    except (ValueError, UnicodeError):
        raise ErroFonte("blizzard", "JSON inválido") from None
    try:
        if isinstance(dados, dict):
            artigos = dados["blogList"] if "blogList" in dados else dados["articles"]
        else:
            artigos = dados
        if not isinstance(artigos, list):
            raise ValueError
        resultado = []
        for artigo in artigos:
            identificador = artigo["id"]
            titulo = artigo["title"]
            resumo = artigo["summary"]
            texto = artigo.get("content")
            # O texto só alimenta o resumo por IA; sem ele, a notícia continua válida.
            if not isinstance(texto, str):
                texto = ""
            publicada = artigo["publish"]
            if isinstance(identificador, bool) or not isinstance(identificador, int):
                raise ValueError
            if not isinstance(titulo, str) or not isinstance(resumo, str):
                raise ValueError
            if isinstance(publicada, bool) or not isinstance(publicada, (int, float)):
                raise ValueError
            trecho = PADRAO_PATCH.search(titulo)
            versao = re.search(r"\d+(?:\.\d+)+", titulo[trecho.end():]) if trecho else None
            if trecho and versao is None:
                versao = re.search(r"\d+(?:\.\d+)+(?=\s*$)", titulo[:trecho.start()])
            resultado.append(Noticia(
                identificador,
                titulo,
                f"https://hearthstone.blizzard.com/{idioma}/news/{identificador}",
                sem_html(resumo),
                datetime.fromtimestamp(publicada / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
                versao.group() if versao else None,
                sem_html(texto),
            ))
        return resultado
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        raise ErroFonte("blizzard", "formato da resposta mudou") from None
