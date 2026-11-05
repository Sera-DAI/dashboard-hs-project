"""Quais cartas valem no Padrão (D46); as demais cartas jogáveis são do Livre.

A lista vem da API de dados oficial do Hearthstone (a mesma da D40, com os mesmos segredos) e fica em
dados/formatos.json. O monitor só lê esse arquivo: se ele faltar, as cartas ficam sem formato e as listas
continuam como antes, sem separação. Nenhuma carta é guardada, só os números (dbfId).
"""

import urllib.parse
import urllib.request
from pathlib import Path

from hsds import gravacao
from hsds.http import AGENTE, ErroFonte

URL_CARTAS = "https://us.api.blizzard.com/hearthstone/cards"
TAMANHO_PAGINA = 500
LIMITE_PAGINAS = 50
# Abaixo disto a resposta não pode ser o Padrão inteiro (o Núcleo sozinho passa de 280 cartas).
MINIMO_CARTAS = 300
# Coleções que não são jogáveis no Padrão nem no Livre: cópias ocultas do Núcleo, heróis alternativos e o Formato Clássico.
FORA_DOS_FORMATOS = frozenset({"CORE_HIDDEN", "HERO_SKINS", "VANILLA"})


def baixar_padrao(token: str, pedir) -> list[int]:
    """Devolve os dbfId das cartas do Padrão. `pedir` recebe a requisição e devolve o JSON já lido.

    A requisição leva o token no cabeçalho: `pedir` não pode imprimi-la nem pô-la em mensagem de erro.
    """
    ids: set[int] = set()
    pagina = 1
    total = 1
    while pagina <= total:
        if pagina > LIMITE_PAGINAS:
            raise ErroFonte("blizzard", "formato da resposta mudou")
        consulta = urllib.parse.urlencode({"locale": "pt_BR", "set": "standard", "page": pagina, "pageSize": TAMANHO_PAGINA})
        requisicao = urllib.request.Request(
            f"{URL_CARTAS}?{consulta}",
            headers={"User-Agent": AGENTE, "Authorization": f"Bearer {token}"},
            method="GET",
        )
        dados = pedir(requisicao)
        cartas = dados.get("cards")
        total = dados.get("pageCount")
        if not isinstance(cartas, list) or not isinstance(total, int) or total < 1:
            raise ErroFonte("blizzard", "formato da resposta mudou")
        for carta in cartas:
            if isinstance(carta, dict) and isinstance(carta.get("id"), int) and not isinstance(carta["id"], bool):
                ids.add(carta["id"])
        pagina += 1
    if len(ids) < MINIMO_CARTAS:
        raise ErroFonte("blizzard", "formato da resposta mudou")
    return sorted(ids)


def montar(ids: list[int]) -> dict:
    return {"padrao": ids}


def carregar(raiz: Path) -> frozenset[str] | None:
    """Os dbfId do Padrão como texto (as chaves de cartas.json), ou None se o arquivo não existe ou está fora do formato."""
    dados = gravacao.ler(raiz / "formatos.json")
    if not isinstance(dados, dict) or not isinstance(dados.get("padrao"), list):
        return None
    ids = dados["padrao"]
    if len(ids) < MINIMO_CARTAS or any(isinstance(item, bool) or not isinstance(item, int) for item in ids):
        return None
    return frozenset(str(item) for item in ids)
