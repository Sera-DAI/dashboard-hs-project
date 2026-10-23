"""Redução dos dados de cartas ao contrato público do projeto."""

import json

from hsds.http import ErroFonte

CAMPOS = {
    "id": "id",
    "nome": "name",
    "classe": "cardClass",
    "colecao": "set",
    "custo": "cost",
    "ataque": "attack",
    "vida": "health",
    "durabilidade": "durability",
    "armadura": "armor",
    "texto": "text",
}


def cartas(bruto: bytes, build: int) -> dict:
    try:
        dados = json.loads(bruto)
    except (ValueError, UnicodeError):
        raise ErroFonte("hearthstonejson", "JSON inválido") from None
    try:
        if not isinstance(dados, list) or not dados:
            raise ValueError
        compactas = {}
        for carta in dados:
            identificador = carta["dbfId"]
            if isinstance(identificador, bool) or not isinstance(identificador, int):
                raise ValueError
            chave = str(identificador)
            if chave in compactas:
                raise ValueError
            for campo in ("cost", "attack", "health", "durability", "armor"):
                valor = carta.get(campo)
                if valor is not None and (isinstance(valor, bool) or not isinstance(valor, int)):
                    raise ValueError
            for campo in ("id", "name", "cardClass", "set", "text"):
                valor = carta.get(campo)
                if valor is not None and not isinstance(valor, str):
                    raise ValueError
            compactas[chave] = {destino: carta.get(origem) for destino, origem in CAMPOS.items()}
        return {"build": build, "cartas": compactas}
    except (KeyError, TypeError, ValueError):
        raise ErroFonte("hearthstonejson", "formato da resposta mudou") from None
