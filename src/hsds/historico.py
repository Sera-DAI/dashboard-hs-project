"""Preenche em lotes o histórico anterior à linha de base do monitor."""

import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from hsds import blizzard, diff, formatador, gravacao, hearthstonejson, http, monitor, resumo_ia, telegram

CORTE = "2026-04-25"
LIMITE_RESUMOS = 10
LIMITE_TENTATIVAS = 3
INTERVALO = 2
CARTAS = "https://api.hearthstonejson.com/v1/{build}/ptBR/cards.collectible.json"
LISTAGEM = "https://api.hearthstonejson.com/v1/"


def _nome_patch(noticia) -> str:
    versao = noticia.versao or str(noticia.id)
    return f"patches/{noticia.publicada[:10]}-{versao}.json"


def _nome_noticia(noticia) -> str:
    return f"noticias/{noticia.publicada[:10]}-{noticia.id}.json"


def _ja_gravada(noticia, raiz: Path, indice: dict, noticias: dict) -> bool:
    if noticia.id in noticias:
        return True
    if blizzard.e_patch(noticia):
        for entrada in indice["patches"]:
            patch = gravacao.ler(raiz / entrada["arquivo"], {})
            noticia_pt = patch.get("noticia") or {}
            noticia_en = patch.get("noticia_en") or {}
            if noticia.id in {noticia_pt.get("id"), noticia_en.get("id")}:
                return True
    return (raiz / (_nome_patch(noticia) if blizzard.e_patch(noticia) else _nome_noticia(noticia))).exists()


def _pausar(ultimo: list[float], dormir) -> None:
    agora = time.monotonic()
    if ultimo[0] is not None:
        dormir(max(0, INTERVALO - (agora - ultimo[0])))
    ultimo[0] = time.monotonic()


def _ler_pagina(numero: int, ultimo: list[float], dormir) -> list:
    url = monitor.LISTA.replace("page=1", f"page={numero}").format(idioma="pt-br")
    _pausar(ultimo, dormir)
    return blizzard.noticias(http.baixar(url), "pt-br")


def _itens_para_processar(estado: dict, raiz: Path, indice: dict, indice_noticias: dict, dormir, vistas=frozenset()):
    ultimo = [None]
    encontrados = {}
    if not estado["paginado"]:
        pagina = 1
        while True:
            itens = _ler_pagina(pagina, ultimo, dormir)
            if not itens:
                estado["paginado"] = True
                break
            # Na primeira página, o que o monitor ainda não viu é dele: gravar aqui duplicaria o aviso e o arquivo.
            if pagina == 1:
                itens_do_historico = [item for item in itens if item.id in vistas]
            else:
                itens_do_historico = itens
            encontrados.update({item.id: item for item in itens_do_historico if item.publicada[:10] >= CORTE})
            if min(item.publicada[:10] for item in itens) < CORTE:
                estado["paginado"] = True
                break
            pagina += 1
    elif estado["fila"]:
        faltam = {item["id"] for item in estado["fila"][:LIMITE_RESUMOS]}
        pagina = 1
        while faltam:
            itens = _ler_pagina(pagina, ultimo, dormir)
            if not itens:
                break
            encontrados.update({item.id: item for item in itens if item.id in faltam})
            faltam.difference_update(encontrados)
            if min(item.publicada[:10] for item in itens) < CORTE:
                break
            pagina += 1

    novos = [item for item in encontrados.values() if not _ja_gravada(item, raiz, indice, indice_noticias)]
    patches = sorted((item for item in novos if blizzard.e_patch(item)), key=lambda item: (item.publicada, item.id), reverse=True)
    noticias = sorted((item for item in novos if not blizzard.e_patch(item)), key=lambda item: (item.publicada, item.id), reverse=True)
    return encontrados, patches + noticias, ultimo


def _builds(ultimo: list[float], dormir, estado: dict) -> list[tuple[int, str]]:
    _pausar(ultimo, dormir)
    bruto = http.baixar(LISTAGEM)
    identificadores = sorted({int(item) for item in re.findall(rb"/v1/(\d+)/", bruto)})
    if not identificadores:
        raise http.ErroFonte("hearthstonejson", "formato da resposta mudou")
    builds = estado["builds"]
    resultado = []
    # Da mais nova para a mais antiga; a primeira build anterior ao corte ainda entra, como par do patch mais antigo.
    for build in reversed(identificadores):
        chave = str(build)
        if chave not in builds:
            _pausar(ultimo, dormir)
            builds[chave] = http.data_modificacao(CARTAS.format(build=build), abrir=http._abrir_cabecalho_padrao)
        resultado.append((build, builds[chave]))
        if builds[chave][:10] < CORTE:
            break
    return sorted(resultado, key=lambda item: (item[1], item[0]))


def _build_ate(builds: list[tuple[int, str]], publicada: str) -> int | None:
    limite = date.fromisoformat(publicada) + timedelta(days=1)
    candidatos = [build for build, gerada in builds if date.fromisoformat(gerada[:10]) <= limite]
    return candidatos[-1] if candidatos else None


def _patches_existentes(raiz: Path, indice: dict) -> list[dict]:
    resultado = []
    for entrada in indice["patches"]:
        patch = gravacao.ler(raiz / entrada["arquivo"], {})
        noticia = patch.get("noticia") or patch.get("noticia_en")
        if noticia and noticia.get("publicada"):
            resultado.append({"data": noticia["publicada"], "build": patch.get("build")})
    return resultado


def _gravar_patch(noticia, patch_anterior: dict | None, builds: list[tuple[int, str]], cartas_cache: dict, ultimo: list[float], dormir):
    atual = _build_ate(builds, noticia.publicada[:10])
    anterior = _build_ate(builds, (patch_anterior["data"][:10] if patch_anterior else "0001-01-01")) if patch_anterior else None
    if patch_anterior is None:
        posicao = next((i for i, (identificador, _) in enumerate(builds) if identificador == atual), -1)
        anterior = builds[posicao - 1][0] if posicao > 0 else None
    if atual is None or anterior is None or atual == anterior:
        cartas = None
        build = None
    else:
        for identificador in (anterior, atual):
            if identificador not in cartas_cache:
                _pausar(ultimo, dormir)
                cartas_cache[identificador] = hearthstonejson.cartas(http.baixar(CARTAS.format(build=identificador)), identificador)
        cartas = diff.comparar(cartas_cache[anterior], cartas_cache[atual])
        build = atual
    noticia_dados = noticia.dados()
    noticia_dados.pop("resumo", None)
    return {
        "versao": noticia.versao,
        "data": noticia.publicada[:10],
        "build": build,
        "noticia": noticia_dados,
        "noticia_en": None,
        "cartas": cartas,
        "retroativo": True,
        "resumo_ia": None,
    }


def _resumo(noticia, patch, com_cartas: bool, chave: str):
    if not noticia.texto:
        return None
    try:
        topicos = resumo_ia.gerar(noticia.titulo, noticia.texto, "pt-br", patch.get("cartas"), chave, com_cartas=com_cartas)
    except resumo_ia.ErroResumo:
        return None
    return {"topicos": topicos, "modelo": resumo_ia.MODELO, "gerado": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}


def _enviar(textos: list[str]) -> None:
    for texto in textos:
        telegram.enviar_mensagem(os.environ.get("TELEGRAM_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", ""), texto)


def main(raiz: Path | None = None, dormir=time.sleep) -> int:
    raiz = raiz or Path("dados")
    estado = gravacao.ler(raiz / "historico.json", {"corte": CORTE, "paginado": False, "fila": [], "builds": {}})
    estado.setdefault("builds", {})
    if estado.get("paginado") and not estado.get("fila"):
        return 0
    indice = gravacao.ler(raiz / "indice.json", {"patches": []})
    indice_noticias = gravacao.ler(raiz / "noticias.json", {"noticias": []})
    existentes = {item["id"] for item in indice_noticias["noticias"]}
    vistas = frozenset(gravacao.ler(raiz / "estado.json", {}).get("noticias_vistas", []))
    procurados = {item["id"] for item in estado["fila"][:LIMITE_RESUMOS]} if estado.get("paginado") else set()
    try:
        encontrados, novos, ultimo = _itens_para_processar(estado, raiz, indice, {"noticias": existentes}, dormir, vistas)
        patches_novos = [item for item in novos if blizzard.e_patch(item)]
        patch_dates = _patches_existentes(raiz, indice)
        patch_dates.extend({"data": item.publicada, "build": None, "noticia_id": item.id} for item in patches_novos)
        patch_dates.sort(key=lambda item: (item["data"], item.get("noticia_id", 0)))
        patches_a_construir = [item for item in patches_novos if not (raiz / _nome_patch(item)).exists()]
        precisa_build = bool(patches_a_construir)
        builds = _builds(ultimo, dormir, estado) if precisa_build else []
        cartas_cache = {}
        arquivos = {}
        gravados_patches = 0
        gravadas_noticias = 0

        for noticia in novos:
            if blizzard.e_patch(noticia):
                posicao = next(i for i, item in enumerate(patch_dates) if item.get("noticia_id") == noticia.id)
                anterior = patch_dates[posicao - 1] if posicao else None
                patch = _gravar_patch(noticia, anterior, builds, cartas_cache, ultimo, dormir)
                arquivo = _nome_patch(noticia)
                arquivos[raiz / arquivo] = patch
                indice["patches"] = [item for item in indice["patches"] if item["arquivo"] != arquivo]
                contagens = {grupo: len((patch["cartas"] or {}).get(grupo, [])) for grupo in ("buffs", "nerfs", "alteradas")}
                indice["patches"].append({"arquivo": arquivo, "versao": patch["versao"], "data": patch["data"], **contagens})
                gravados_patches += 1
                estado["fila"].append({"arquivo": arquivo, "id": noticia.id})
            else:
                arquivo = _nome_noticia(noticia)
                arquivos[raiz / arquivo] = {"id": noticia.id, "titulo": noticia.titulo, "link": noticia.link, "publicada": noticia.publicada, "retroativo": True, "resumo_ia": None}
                indice_noticias["noticias"] = [item for item in indice_noticias["noticias"] if item["arquivo"] != arquivo]
                indice_noticias["noticias"].append({"arquivo": arquivo, "id": noticia.id, "titulo": noticia.titulo, "data": noticia.publicada[:10]})
                gravadas_noticias += 1
                estado["fila"].append({"arquivo": arquivo, "id": noticia.id})

        indice["patches"].sort(key=lambda item: item["data"], reverse=True)
        indice_noticias["noticias"].sort(key=lambda item: item["data"], reverse=True)
        fila = []
        resumos = 0
        chamadas = 0

        def tentar_de_novo(item):
            # Depois de LIMITE_TENTATIVAS lotes sem resumo, o item sai da fila e fica com resumo_ia null.
            tentativas = item.get("tentativas", 0) + 1
            if tentativas < LIMITE_TENTATIVAS:
                fila.append({**item, "tentativas": tentativas})

        for item in estado["fila"]:
            if chamadas >= LIMITE_RESUMOS:
                fila.append(item)
                continue
            noticia = encontrados.get(item["id"])
            if noticia is None:
                # Só conta como tentativa quando o item foi procurado na lista e não estava lá.
                if item["id"] in procurados:
                    tentar_de_novo(item)
                else:
                    fila.append(item)
                continue
            if not noticia.texto:
                # Sem texto não há o que resumir; esperar não muda isso.
                continue
            chamadas += 1
            _pausar(ultimo, dormir)
            registro = arquivos.get(raiz / item["arquivo"]) or gravacao.ler(raiz / item["arquivo"], {})
            resumo = _resumo(noticia, registro, item["arquivo"].startswith("patches/"), os.environ.get("GEMINI_API_KEY", ""))
            if resumo is None:
                tentar_de_novo(item)
                continue
            registro["resumo_ia"] = resumo
            arquivos[raiz / item["arquivo"]] = registro
            resumos += 1
        estado["fila"] = fila
        if novos:
            arquivos[raiz / "indice.json"] = indice
            arquivos[raiz / "noticias.json"] = indice_noticias
        arquivos[raiz / "historico.json"] = estado
        houve_mudanca = bool(novos or resumos)
        if houve_mudanca:
            completo = estado["paginado"] and not estado["fila"]
            _enviar(formatador.historico(gravados_patches, gravadas_noticias, resumos, len(estado["fila"]), completo, CORTE))
        gravacao.gravar(arquivos)
        return 0
    except http.ErroFonte as erro:
        try:
            _enviar(formatador.falha(erro.fonte, erro.motivo))
        except (telegram.ErroTelegram, ValueError, OSError):
            pass
        return 1
    except (telegram.ErroTelegram, ValueError, OSError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
