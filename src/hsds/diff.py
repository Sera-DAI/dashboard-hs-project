"""Comparação somente das cartas presentes nas duas builds."""

import re

from hsds.formatos import FORA_DOS_FORMATOS

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
    # Só texto vai para "revisadas" (decisão de projeto em 26/10/2026): a reescrita da
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


def _formato(chave, padrao):
    return None if padrao is None else ("padrao" if chave in padrao else "livre")


def _unir_repetidas(resultado: dict) -> None:
    """Uma carta do Livre igual a uma do Padrão (mesmo nome e mesmas mudanças) é a mesma mudança vista pelos dois formatos.

    Acontece com as cartas do Núcleo, que têm uma cópia na coleção original: fica só a do Padrão, marcada
    com `tambem_livre`, em vez de a mesma linha aparecer nas duas seções.
    """
    padrao = {}
    for grupo in GRUPOS:
        for carta in resultado[grupo]:
            if carta.get("formato") == "padrao":
                padrao[(carta["nome"], repr(carta["mudancas"]))] = carta
    for grupo in GRUPOS:
        mantidas = []
        for carta in resultado[grupo]:
            gemea = padrao.get((carta["nome"], repr(carta["mudancas"]))) if carta.get("formato") == "livre" else None
            if gemea is None:
                mantidas.append(carta)
            else:
                gemea["tambem_livre"] = True
        resultado[grupo] = mantidas


def comparar(antes: dict, depois: dict, padrao=None) -> dict:
    """Compara as duas builds. `padrao` (opcional) é o conjunto de dbfId do Padrão, como texto; com ele cada carta ganha `formato`."""
    resultado = {grupo: [] for grupo in GRUPOS}
    for chave in sorted(antes["cartas"].keys() & depois["cartas"].keys(), key=int):
        antiga = antes["cartas"][chave]
        nova = depois["cartas"][chave]
        if nova.get("colecao") in FORA_DOS_FORMATOS:
            continue
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
        carta = {
            "dbfId": int(chave),
            "nome": nova.get("nome"),
            "classe": nova.get("classe"),
            "mudancas": mudancas,
        }
        formato = _formato(chave, padrao)
        if formato:
            carta["formato"] = formato
        resultado[_grupo(mudancas)].append(carta)
    _unir_repetidas(resultado)
    return resultado


def completar_formatos(cartas: dict | None, atuais: dict | None, padrao) -> dict | None:
    """Põe `formato` nas cartas de um diff já gravado e tira as que não valem em nenhum formato; None se nada muda.

    `atuais` é o cartas.json mais novo (dá a coleção de cada carta) e `padrao`, o conjunto do Padrão de hoje.
    Em patches antigos, uma carta que já saiu do Padrão aparece como Livre: o arquivo não guarda o formato da época.
    """
    if cartas is None or atuais is None:
        return None
    resultado = {grupo: [] for grupo in GRUPOS}
    mudou = False
    for grupo in GRUPOS:
        for carta in cartas.get(grupo, []):
            chave = str(carta["dbfId"])
            colecao = (atuais["cartas"].get(chave) or {}).get("colecao")
            if colecao in FORA_DOS_FORMATOS:
                mudou = True
                continue
            if "formato" not in carta and padrao is not None:
                carta = {**carta, "formato": _formato(chave, padrao)}
                mudou = True
            resultado[grupo].append(carta)
    if not mudou:
        return None
    _unir_repetidas(resultado)
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
