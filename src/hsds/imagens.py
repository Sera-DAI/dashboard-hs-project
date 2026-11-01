"""Guarda o endereço da imagem oficial de cada carta, vindo da API de dados do Hearthstone (D40).

Só o hash da imagem entra em dados/imagens.json; nenhuma imagem é baixada nem guardada.
Segredos só são lidos do ambiente e nunca aparecem em mensagem de erro ou log.
"""

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.client import HTTPException
from pathlib import Path

from hsds import gravacao
from hsds.http import AGENTE, ErroFonte

URL_TOKEN = "https://oauth.battle.net/token"
URL_CARTAS = "https://us.api.blizzard.com/hearthstone/cards"
PREFIXO_IMAGEM = "https://d15f34w2p8l1cc.cloudfront.net/hearthstone/"
PADRAO_IMAGEM = re.compile(r"^https://d15f34w2p8l1cc\.cloudfront\.net/hearthstone/([0-9a-f]{64})\.png$")
TAMANHO_PAGINA = 500
LIMITE_PAGINAS = 100
RAIZ = Path(__file__).resolve().parents[2]


def _abrir_padrao(requisicao: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(requisicao, timeout=30) as resposta:
        return resposta.read()


def _pedir(requisicao: urllib.request.Request, abrir) -> dict:
    try:
        bruto = abrir(requisicao)
    except (urllib.error.URLError, OSError, HTTPException):
        raise ErroFonte("blizzard", "API fora do ar ou sem resposta") from None
    try:
        dados = json.loads(bruto)
    except (ValueError, TypeError):
        raise ErroFonte("blizzard", "formato da resposta mudou") from None
    if not isinstance(dados, dict):
        raise ErroFonte("blizzard", "formato da resposta mudou")
    return dados


def pedir_token(cliente: str, segredo: str, abrir=_abrir_padrao) -> str:
    credencial = base64.b64encode(f"{cliente}:{segredo}".encode()).decode()
    requisicao = urllib.request.Request(
        URL_TOKEN,
        data=b"grant_type=client_credentials",
        headers={
            "User-Agent": AGENTE,
            "Authorization": f"Basic {credencial}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    token = _pedir(requisicao, abrir).get("access_token")
    if not isinstance(token, str) or not token:
        raise ErroFonte("blizzard", "login recusado ou resposta fora do formato")
    return token


def hash_da_imagem(url) -> str | None:
    if not isinstance(url, str):
        return None
    achado = PADRAO_IMAGEM.match(url)
    return achado.group(1) if achado else None


def baixar_catalogo(token: str, abrir=_abrir_padrao) -> dict[str, str]:
    """Devolve {dbfId: hash} de todas as cartas do catálogo que têm imagem válida."""
    imagens: dict[str, str] = {}
    pagina = 1
    total = 1
    while pagina <= total:
        if pagina > LIMITE_PAGINAS:
            raise ErroFonte("blizzard", "formato da resposta mudou")
        consulta = urllib.parse.urlencode({"locale": "pt_BR", "page": pagina, "pageSize": TAMANHO_PAGINA})
        requisicao = urllib.request.Request(
            f"{URL_CARTAS}?{consulta}",
            headers={"User-Agent": AGENTE, "Authorization": f"Bearer {token}"},
            method="GET",
        )
        dados = _pedir(requisicao, abrir)
        cartas = dados.get("cards")
        total = dados.get("pageCount")
        if not isinstance(cartas, list) or not isinstance(total, int) or total < 1:
            raise ErroFonte("blizzard", "formato da resposta mudou")
        for carta in cartas:
            if not isinstance(carta, dict) or not isinstance(carta.get("id"), int):
                continue
            hash_ = hash_da_imagem(carta.get("image"))
            if hash_:
                imagens[str(carta["id"])] = hash_
        pagina += 1
    return imagens


def montar(catalogo: dict[str, str], cartas: dict) -> dict:
    """Mantém só as cartas de dados/cartas.json, em ordem estável.

    As cartas CORE_ que o catálogo não lista (saíram do Core) herdam a imagem da carta original,
    que tem o mesmo desenho e o id sem o prefixo.
    """
    por_id = {carta.get("id"): chave for chave, carta in cartas.items() if isinstance(carta, dict)}
    escolhidas = {}
    for chave in sorted(cartas, key=int):
        hash_ = catalogo.get(chave)
        if hash_ is None:
            id_ = cartas[chave].get("id") if isinstance(cartas[chave], dict) else None
            if isinstance(id_, str) and id_.startswith("CORE_"):
                hash_ = catalogo.get(por_id.get(id_[len("CORE_"):], ""))
        if hash_ is not None:
            escolhidas[chave] = hash_
    return {"imagens": escolhidas}


def executar(ambiente=None, abrir=_abrir_padrao, raiz: Path = RAIZ) -> int:
    ambiente = os.environ if ambiente is None else ambiente
    cliente = ambiente.get("BLIZZARD_CLIENT_ID", "")
    segredo = ambiente.get("BLIZZARD_CLIENT_SECRET", "")
    if not cliente or not segredo:
        print("Faltam os segredos BLIZZARD_CLIENT_ID e BLIZZARD_CLIENT_SECRET.", file=sys.stderr)
        return 1
    cartas = gravacao.ler(raiz / "dados" / "cartas.json")
    if not isinstance(cartas, dict) or not isinstance(cartas.get("cartas"), dict) or not cartas["cartas"]:
        print("dados/cartas.json ausente ou fora do formato.", file=sys.stderr)
        return 1
    try:
        token = pedir_token(cliente, segredo, abrir=abrir)
        catalogo = baixar_catalogo(token, abrir=abrir)
    except ErroFonte as erro:
        print(f"Imagens não atualizadas: {erro.motivo}.", file=sys.stderr)
        return 1
    resultado = montar(catalogo, cartas["cartas"])
    if not resultado["imagens"]:
        print("Imagens não atualizadas: nenhuma carta casou com o catálogo.", file=sys.stderr)
        return 1
    destino = raiz / "dados" / "imagens.json"
    if gravacao.ler(destino) != resultado:
        gravacao.gravar({destino: resultado})
    print(f"Imagens: {len(resultado['imagens'])} de {len(cartas['cartas'])} cartas.")
    return 0


def main() -> None:
    sys.exit(executar())


if __name__ == "__main__":
    main()
