"""Acesso às fontes, com identificação e erros sem detalhes da conexão."""

import re
from http.client import HTTPException
import urllib.error
import urllib.request

AGENTE = "HearthstoneDS/0.1 (monitor pessoal; github.com/Sera-DAI)"
ULTIMA_BUILD = "https://api.hearthstonejson.com/v1/latest/"


class ErroFonte(Exception):
    def __init__(self, fonte: str, motivo: str):
        super().__init__(motivo)
        self.fonte = fonte
        self.motivo = motivo


def _abrir_padrao(requisicao: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(requisicao, timeout=20) as resposta:
        return resposta.read()


def baixar(url: str, abrir=_abrir_padrao) -> bytes:
    fonte = "hearthstonejson" if url.startswith("https://api.hearthstonejson.com/") else "blizzard"
    requisicao = urllib.request.Request(url, headers={"User-Agent": AGENTE}, method="GET")
    try:
        return abrir(requisicao)
    except (urllib.error.URLError, OSError, HTTPException):
        raise ErroFonte(fonte, "site fora do ar ou sem resposta") from None


def build_atual(abrir=_abrir_padrao) -> int:
    bruto = baixar(ULTIMA_BUILD, abrir=abrir)
    builds = set(re.findall(rb"/v1/(\d+)/", bruto))
    if len(builds) != 1:
        raise ErroFonte("hearthstonejson", "formato da resposta mudou")
    return int(builds.pop())
