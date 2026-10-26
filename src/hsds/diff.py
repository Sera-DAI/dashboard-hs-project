"""Comparação somente das cartas presentes nas duas builds."""

import re

CAMPOS = ("custo", "ataque", "vida", "durabilidade", "armadura", "texto")


def _texto_comparavel(texto):
    # O HearthstoneJSON marca quebras de linha sugeridas com "&" e "[x]"; isso não muda a carta.
    if texto is None:
        return None
    texto = re.sub(r"^\s*\[x\]", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"&(?=\s|$)", "", texto)
    return " ".join(texto.split())


def comparar(antes: dict, depois: dict) -> dict:
    resultado = {"buffs": [], "nerfs": [], "alteradas": []}
    for chave in sorted(antes["cartas"].keys() & depois["cartas"].keys(), key=int):
        antiga = antes["cartas"][chave]
        nova = depois["cartas"][chave]
        mudancas = []
        sentidos = set()
        for campo in CAMPOS:
            anterior = antiga.get(campo)
            atual = nova.get(campo)
            if anterior == atual:
                continue
            if campo == "texto" and _texto_comparavel(anterior) == _texto_comparavel(atual):
                continue
            mudancas.append({"campo": campo, "antes": anterior, "depois": atual})
            if campo == "texto" or anterior is None or atual is None:
                sentidos.add("alteradas")
            else:
                melhora = atual < anterior if campo == "custo" else atual > anterior
                sentidos.add("buffs" if melhora else "nerfs")
        if not mudancas:
            continue
        grupo = sentidos.pop() if len(sentidos) == 1 else "alteradas"
        resultado[grupo].append({
            "dbfId": int(chave),
            "nome": nova.get("nome"),
            "classe": nova.get("classe"),
            "mudancas": mudancas,
        })
    return resultado
