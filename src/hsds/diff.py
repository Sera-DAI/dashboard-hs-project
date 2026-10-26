"""Comparação somente das cartas presentes nas duas builds."""

import re

CAMPOS = ("custo", "ataque", "vida", "durabilidade", "armadura", "texto")
GRUPOS = ("buffs", "nerfs", "alteradas", "revisadas")


def _texto_comparavel(texto):
    # O HearthstoneJSON marca quebras de linha sugeridas com "&" e "[x]"; isso não muda a carta.
    # Marcação, maiúsculas e pontuação também não (no 37.0, 61 cartas mudaram só nisso).
    if texto is None:
        return None
    texto = re.sub(r"^\s*\[x\]", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"&(?=\s|$)", "", texto)
    texto = re.sub(r"</?[bi]>", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"[.,;:]", " ", texto)
    return " ".join(texto.lower().split())


def _grupo(mudancas: list[dict]) -> str:
    # Só texto vai para "revisadas" (decisão do responsável em 26/10/2026): a reescrita da
    # tradução não muda o efeito, e uma mudança de efeito só no texto continua visível ali.
    # Com números junto, o texto acompanha o sentido dos números.
    numericas = [mudanca for mudanca in mudancas if mudanca["campo"] != "texto"]
    if not numericas:
        return "revisadas"
    sentidos = set()
    for mudanca in numericas:
        campo = mudanca["campo"]
        anterior = mudanca["antes"]
        atual = mudanca["depois"]
        if anterior is None or atual is None:
            sentidos.add("alteradas")
        else:
            melhora = atual < anterior if campo == "custo" else atual > anterior
            sentidos.add("buffs" if melhora else "nerfs")
    return sentidos.pop() if len(sentidos) == 1 else "alteradas"


def comparar(antes: dict, depois: dict) -> dict:
    resultado = {grupo: [] for grupo in GRUPOS}
    for chave in sorted(antes["cartas"].keys() & depois["cartas"].keys(), key=int):
        antiga = antes["cartas"][chave]
        nova = depois["cartas"][chave]
        mudancas = []
        for campo in CAMPOS:
            anterior = antiga.get(campo)
            atual = nova.get(campo)
            if anterior == atual:
                continue
            if campo == "texto" and _texto_comparavel(anterior) == _texto_comparavel(atual):
                continue
            mudancas.append({"campo": campo, "antes": anterior, "depois": atual})
        if not mudancas:
            continue
        resultado[_grupo(mudancas)].append({
            "dbfId": int(chave),
            "nome": nova.get("nome"),
            "classe": nova.get("classe"),
            "mudancas": mudancas,
        })
    return resultado


def reaplicar(cartas: dict | None) -> dict | None:
    """Aplica a regra atual de texto e de grupos a um diff já gravado; devolve None se nada muda."""
    if cartas is None:
        return None
    resultado = {grupo: [] for grupo in GRUPOS}
    mudou = "revisadas" not in cartas
    for grupo in GRUPOS:
        for carta in cartas.get(grupo, []):
            mudancas = [
                mudanca for mudanca in carta["mudancas"]
                if mudanca["campo"] != "texto" or _texto_comparavel(mudanca["antes"]) != _texto_comparavel(mudanca["depois"])
            ]
            if not mudancas:
                mudou = True
                continue
            novo_grupo = _grupo(mudancas)
            if len(mudancas) != len(carta["mudancas"]) or novo_grupo != grupo:
                mudou = True
            resultado[novo_grupo].append({**carta, "mudancas": mudancas})
    if not mudou:
        return None
    for grupo in resultado.values():
        grupo.sort(key=lambda carta: carta["dbfId"])
    return resultado
