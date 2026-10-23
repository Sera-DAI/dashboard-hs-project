"""Comparação somente das cartas presentes nas duas builds."""

CAMPOS = ("custo", "ataque", "vida", "durabilidade", "armadura", "texto")


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
