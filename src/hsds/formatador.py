"""Textos do contrato de mensagens, com divisão somente entre linhas."""

from datetime import date

from hsds.blizzard import sem_html
from hsds.diff import CAMPOS

LIMITE = 4096


def _versao(patch: dict) -> str:
    return patch["versao"] or f"de {date.fromisoformat(patch['data']).strftime('%d/%m/%Y')}"


def _limpar(texto) -> str:
    return sem_html(texto or "").replace("[x]", "").replace("$", "").replace("#", "").strip()


GRUPOS_AVISO = (("buffs", "Buffs"), ("nerfs", "Nerfs"), ("alteradas", "Alteradas"), ("revisadas", "Texto alterado"))
FORMATOS_AVISO = (("padrao", "Padrão"), ("livre", "Livre"))


def _linha_carta(carta: dict) -> str:
    numeros = []
    texto = None
    for mudanca in sorted(carta["mudancas"], key=lambda item: CAMPOS.index(item["campo"])):
        if mudanca["campo"] == "texto":
            texto = f"texto novo: {_limpar(mudanca['depois'])}"
        else:
            numeros.append(f"{mudanca['campo']} {mudanca['antes']} → {mudanca['depois']}")
    descricao = ", ".join(numeros)
    if texto is not None:
        descricao = f"{descricao}; {texto}" if descricao else texto
    nota = " (vale também no Livre)" if carta.get("tambem_livre") else ""
    return f"• {_limpar(carta['nome'])}: {descricao}{nota}"


def _grupos(cartas: dict, formato) -> list[str]:
    blocos = []
    for chave, titulo in GRUPOS_AVISO:
        itens = [carta for carta in cartas.get(chave, []) if carta.get("formato") == formato]
        if not itens:
            continue
        linhas = [f"{titulo} ({len(itens)})"]
        linhas.extend(_linha_carta(carta) for carta in sorted(itens, key=lambda item: (item["nome"] or "").casefold()))
        blocos.append("\n".join(linhas))
    return blocos


def _bloco(cartas: dict | None) -> str:
    if cartas is None:
        return "As cartas alteradas chegam em outra mensagem quando os dados forem publicados."
    # D46: cada patch separa o Padrão do Livre; sem a lista de formatos (dados antigos), uma lista só, como antes.
    if any(carta.get("formato") for grupo in cartas.values() for carta in grupo):
        partes = []
        for formato, nome in FORMATOS_AVISO:
            blocos = _grupos(cartas, formato)
            partes.append(f"{nome}\n\n" + "\n\n".join(blocos) if blocos else f"{nome}\nNenhuma alteração relevante.")
        sem_formato = _grupos(cartas, None)
        if sem_formato:
            partes.append("Sem formato definido\n\n" + "\n\n".join(sem_formato))
        return "\n\n".join(partes)
    return "\n\n".join(_grupos(cartas, None)) or "Nenhuma carta colecionável mudou."


def _bloco_resumo(patch: dict) -> str:
    resumo = patch.get("resumo_ia")
    if not isinstance(resumo, dict) or not isinstance(resumo.get("topicos"), list):
        return ""
    return "Resumo gerado por IA\n\n" + "\n\n".join(resumo["topicos"])


def _anexar_resumo(texto: str, patch: dict) -> str:
    bloco = _bloco_resumo(patch)
    return f"{texto}\n\n{bloco}" if bloco else texto


def mensagens(texto: str, versao: str) -> list[str]:
    if len(texto) <= LIMITE:
        return [texto]
    linhas = texto.split("\n")
    total = 2
    while True:
        partes = []
        atual = linhas[0] + f" (1/{total})"
        if len(atual) > LIMITE:
            raise ValueError("título excede o limite do Telegram")
        for linha in linhas[1:]:
            if len(atual) + 1 + len(linha) <= LIMITE:
                atual += "\n" + linha
                continue
            partes.append(atual)
            atual = f"Hearthstone DS: patch {versao} (continuação {len(partes) + 1}/{total})\n{linha}"
            if len(atual) > LIMITE:
                raise ValueError("linha excede o limite do Telegram; não é possível dividir uma carta")
        partes.append(atual)
        if len(partes) == total:
            return partes
        total = len(partes)


def patch_novo(patch: dict) -> list[str]:
    noticia = patch["noticia"]
    versao = _versao(patch)
    partes = [
        f"Hearthstone DS: saiu o patch {versao}",
        f"{noticia['titulo']}\n{noticia['link']}",
        noticia["resumo"],
    ]
    if _bloco_resumo(patch):
        partes.append(_bloco_resumo(patch))
    partes.append(_bloco(patch["cartas"]))
    texto = "\n\n".join(partes)
    return mensagens(texto, versao)


def sem_portugues(patch: dict) -> list[str]:
    noticia = patch["noticia_en"]
    versao = _versao(patch)
    referencia = f"{noticia['titulo']}\n{noticia['link']}" if noticia else "Notícias: https://hearthstone.blizzard.com/pt-br/news"
    partes = [f"Hearthstone DS: saiu o patch {versao} (notícia em português ainda não publicada)", referencia]
    if _bloco_resumo(patch):
        partes.append(_bloco_resumo(patch))
    partes.extend([_bloco(patch["cartas"]), "Quando a notícia em português sair, aviso."])
    texto = "\n\n".join(partes)
    return mensagens(texto, versao)


def noticia_portugues(patch: dict) -> list[str]:
    noticia = patch["noticia"]
    versao = _versao(patch)
    texto = (
        f"Hearthstone DS: notícia em português do patch {versao}\n\n"
        f"{noticia['titulo']}\n{noticia['link']}\n\n{noticia['resumo']}"
    )
    return mensagens(_anexar_resumo(texto, patch), versao)


def cartas_atualizadas(patch: dict) -> list[str]:
    versao = _versao(patch)
    partes = [f"Hearthstone DS: cartas alteradas no patch {versao}"]
    if _bloco_resumo(patch):
        partes.append(_bloco_resumo(patch))
    partes.append(_bloco(patch["cartas"]))
    return mensagens("\n\n".join(partes), versao)


def resumo_atrasado(patch: dict) -> list[str]:
    versao = _versao(patch)
    noticia = patch.get("noticia") or patch.get("noticia_en")
    link = noticia.get("link", "") if noticia else ""
    texto = f"Hearthstone DS: resumo do patch {versao}\n\n{_bloco_resumo(patch)}\n\n{link}"
    return mensagens(texto, versao)


def noticia_nova(noticia: dict) -> list[str]:
    partes = [
        "Hearthstone DS: notícia nova",
        f"{noticia['titulo']}\n{noticia['link']}",
        noticia.get("resumo", ""),
    ]
    return mensagens("\n\n".join(parte for parte in partes if parte), "notícia")


def resumo_noticia(noticia: dict) -> list[str]:
    bloco = _bloco_resumo(noticia)
    texto = (
        "Hearthstone DS: resumo da notícia\n\n"
        f"{noticia['titulo']}\n{noticia['link']}\n\n{bloco}"
    )
    return mensagens(texto, "notícia")


def falha(fonte: str, motivo: str) -> list[str]:
    nome = {"blizzard": "notícias da Blizzard", "hearthstonejson": "HearthstoneJSON"}[fonte]
    return [
        f"Hearthstone DS: a coleta de {nome} falhou\n"
        f"Motivo: {motivo}\n"
        "Nada foi gravado. Se continuar falhando, aviso de novo em 24 horas."
    ]
