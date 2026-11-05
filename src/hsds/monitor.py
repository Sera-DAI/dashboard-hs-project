"""Orquestra uma coleta; persiste somente após todos os envios terem sucesso."""

import copy
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hsds import blizzard, busca, diff, formatador, formatos, gravacao, hearthstonejson, http, telegram

LISTA = "https://hearthstone.blizzard.com/{idioma}/api/blog/articleList/?page=1&pageSize=12"
CARTAS = "https://api.hearthstonejson.com/v1/{build}/ptBR/cards.collectible.json"


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _data(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def _enviar(textos: list[str]) -> None:
    for texto in textos:
        telegram.enviar_mensagem(
            os.environ.get("TELEGRAM_TOKEN", ""),
            os.environ.get("TELEGRAM_CHAT_ID", ""),
            texto,
        )


def _noticias(idioma: str) -> list[blizzard.Noticia]:
    return blizzard.noticias(http.baixar(LISTA.format(idioma=idioma)), idioma)


def _pendente(estado: dict, patches: dict, falta: str, versao=None):
    candidatos = [item for item in estado["pendentes"] if item["falta"] == falta]
    if versao is not None:
        exatos = [item for item in candidatos if patches[item["arquivo"]]["versao"] == versao]
        if len(exatos) == 1:
            return exatos[0]
        # Uma notícia sem versão em inglês também pode ser completada pelo único pt-BR.
        candidatos = [item for item in candidatos if patches[item["arquivo"]]["versao"] is None]
    return candidatos[0] if len(candidatos) == 1 else None


def _novo(noticia, build: int, hoje: str, cartas: dict | None, ingles=False) -> dict:
    return {
        "versao": noticia.versao if noticia else None,
        "data": hoje,
        "build": build,
        "noticia": noticia.dados() if noticia and not ingles else None,
        "noticia_en": noticia.dados() if noticia and ingles else None,
        "cartas": cartas,
        "resumo_ia": None,
    }


def _nome(patch: dict) -> str:
    versao = patch["versao"] or f"b{patch['build']}"
    return f"patches/{patch['data']}-{versao}.json"


def _nome_noticia(noticia) -> str:
    return f"noticias/{noticia.publicada[:10]}-{noticia.id}.json"


def _planejar(raiz: Path, estado: dict, noticias: list, build: int, cartas, agora: datetime):
    estado = copy.deepcopy(estado)
    # D54: não há mais fila de resumo automático; o resumo é pedido pelo workflow resumo-manual.
    estado.pop("resumos_pendentes", None)
    instante = agora.isoformat().replace("+00:00", "Z")
    hoje = agora.date().isoformat()
    estado["pendentes"] = [
        item for item in estado["pendentes"]
        if agora - _data(item["desde"]) < timedelta(days=7)
    ]
    patches = {item["arquivo"]: gravacao.ler(raiz / item["arquivo"]) for item in estado["pendentes"]}
    alterados = {}
    textos = []
    padrao = formatos.carregar(raiz)
    mudancas = diff.comparar(gravacao.ler(raiz / "cartas.json"), cartas, padrao) if cartas else None
    tem_diff = mudancas is not None and any(mudancas.values())
    novas = sorted(
        (item for item in noticias if item.id not in estado["noticias_vistas"] and blizzard.e_patch(item)),
        key=lambda item: (item.publicada, item.id),
    )
    novas_notas = sorted(
        (item for item in noticias if item.id not in estado["noticias_vistas"] and not blizzard.e_patch(item)),
        key=lambda item: (item.publicada, item.id),
    )
    lista_ingles = []

    def ingles():
        # Uma só leitura da lista em inglês por execução, e só quando alguém precisa dela.
        if not lista_ingles:
            lista_ingles.append(_noticias("en-us"))
        return lista_ingles[0]

    indice_noticias = gravacao.ler(raiz / "noticias.json", {"noticias": []})
    alteradas_noticias = {}

    def guardar(arquivo, patch, falta=None):
        if arquivo not in patches and (raiz / arquivo).exists():
            raise ValueError("arquivo de patch já existe")
        patches[arquivo] = patch
        alterados[arquivo] = patch
        if falta:
            estado["pendentes"].append({"arquivo": arquivo, "falta": falta, "desde": instante})

    for noticia in novas:
        pendente = _pendente(estado, patches, "noticia_ptbr", noticia.versao)
        if pendente:
            arquivo = pendente["arquivo"]
            patch = patches[arquivo]
            patch["noticia"] = noticia.dados()
            if patch["versao"] is None:
                patch["versao"] = noticia.versao
            estado["pendentes"].remove(pendente)
            guardar(arquivo, patch)
            textos.extend(formatador.noticia_portugues(patch))
            continue
        # Um diff pertence a um único aviso. Notícias anteriores não consomem o atual.
        atuais = mudancas if noticia == novas[-1] else None
        pendente_cartas = _pendente(estado, patches, "cartas")
        if pendente_cartas:
            atuais = None
        patch = _novo(noticia, build, hoje, atuais)
        arquivo = _nome(patch)
        guardar(arquivo, patch, "cartas" if atuais is None else None)
        textos.extend(formatador.patch_novo(patch))
        if atuais is not None:
            mudancas = None
            tem_diff = False

    if tem_diff:
        pendente = _pendente(estado, patches, "cartas")
        if pendente:
            arquivo = pendente["arquivo"]
            patch = patches[arquivo]
            patch["cartas"] = mudancas
            patch["build"] = build
            estado["pendentes"].remove(pendente)
            guardar(arquivo, patch)
            textos.extend(formatador.cartas_atualizadas(patch))
        else:
            ingles_patches = sorted(
                (item for item in ingles() if blizzard.e_patch(item)),
                key=lambda item: (item.publicada, item.id),
                reverse=True,
            )
            indice = gravacao.ler(raiz / "indice.json", {"patches": []})
            versoes = {item["versao"] for item in indice["patches"] if item["versao"]}
            noticia = ingles_patches[0] if ingles_patches else None
            if noticia and noticia.versao in versoes:
                noticia = None
            patch = _novo(noticia, build, hoje, mudancas, ingles=True)
            arquivo = _nome(patch)
            guardar(arquivo, patch, "noticia_ptbr")
            textos.extend(formatador.sem_portugues(patch))

    for noticia in novas_notas:
        arquivo = _nome_noticia(noticia)
        if (raiz / arquivo).exists():
            continue
        registro = {
            "id": noticia.id,
            "titulo": noticia.titulo,
            "link": noticia.link,
            "publicada": noticia.publicada,
            "resumo_ia": None,
        }
        alteradas_noticias[arquivo] = registro
        entrada = {"arquivo": arquivo, "id": noticia.id, "titulo": noticia.titulo, "data": noticia.publicada[:10]}
        indice_noticias["noticias"] = [entrada, *[item for item in indice_noticias["noticias"] if item["arquivo"] != arquivo]]
        textos.extend(formatador.noticia_nova(noticia.dados()))

    # Patches gravados com uma regra de texto mais antiga (por exemplo, o 37.0 antes de 26/10/2026) ou sem o
    # formato das cartas (D46): o monitor regrava com a regra atual, sem aviso.
    atuais = cartas or gravacao.ler(raiz / "cartas.json")
    for entrada in gravacao.ler(raiz / "indice.json", {"patches": []})["patches"]:
        patch = alterados.get(entrada["arquivo"]) or patches.get(entrada["arquivo"]) or gravacao.ler(raiz / entrada["arquivo"])
        cartas_limpas = diff.reaplicar(patch.get("cartas"))
        if cartas_limpas is not None:
            patch["cartas"] = cartas_limpas
            alterados[entrada["arquivo"]] = patch
        com_formato = diff.completar_formatos(patch.get("cartas"), atuais, padrao)
        if com_formato is not None:
            patch["cartas"] = com_formato
            alterados[entrada["arquivo"]] = patch

    estado["build"] = build
    vistas = sorted(noticias, key=lambda item: (item.publicada, item.id), reverse=True)
    estado["noticias_vistas"] = list(dict.fromkeys([item.id for item in vistas] + estado["noticias_vistas"]))[:100]
    arquivos = {raiz / arquivo: patch for arquivo, patch in alterados.items()}
    arquivos.update({raiz / arquivo: noticia for arquivo, noticia in alteradas_noticias.items()})
    if alteradas_noticias:
        def publicada(entrada):
            noticia = alteradas_noticias.get(entrada["arquivo"])
            if noticia is None:
                noticia = gravacao.ler(raiz / entrada["arquivo"], {})
            return noticia.get("publicada", entrada["data"])

        indice_noticias["noticias"].sort(key=publicada, reverse=True)
        arquivos[raiz / "noticias.json"] = indice_noticias
    if alterados:
        indice = gravacao.ler(raiz / "indice.json", {"patches": []})
        entradas = [item for item in indice["patches"] if item["arquivo"] not in alterados]
        for arquivo, patch in alterados.items():
            contagens = {grupo: len((patch["cartas"] or {}).get(grupo, [])) for grupo in diff.GRUPOS}
            entradas.insert(0, {"arquivo": arquivo, "versao": patch["versao"], "data": patch["data"], **contagens})
        entradas.sort(key=lambda item: item["data"], reverse=True)
        arquivos[raiz / "indice.json"] = {"patches": entradas}
    if cartas is not None:
        arquivos[raiz / "cartas.json"] = cartas
        arquivos.update(busca.arquivos(raiz, cartas))
    else:
        arquivos.update(busca.desatualizados(raiz, gravacao.ler))
    arquivos[raiz / "estado.json"] = estado
    return arquivos, textos


def main() -> int:
    raiz = Path("dados")
    estado = gravacao.ler(raiz / "estado.json", {"falhas": {}})
    agora = _agora()
    try:
        noticias = _noticias("pt-br")
        build = http.build_atual()
        cartas = None
        if estado.get("build") != build:
            cartas = hearthstonejson.cartas(http.baixar(CARTAS.format(build=build)), build)
        if "build" not in estado:
            linha_base = {
                "build": build,
                "noticias_vistas": [item.id for item in sorted(noticias, key=lambda item: (item.publicada, item.id), reverse=True)][:100],
                "pendentes": [],
                "falhas": estado.get("falhas", {}),
            }
            gravacao.gravar({raiz / "cartas.json": cartas, **busca.arquivos(raiz, cartas), raiz / "estado.json": linha_base})
            return 0
        arquivos, textos = _planejar(raiz, estado, noticias, build, cartas, agora)
        _enviar(textos)
        gravacao.gravar(arquivos)
        return 0
    except http.ErroFonte as erro:
        ultima = estado.get("falhas", {}).get(erro.fonte)
        if ultima is None or agora - _data(ultima) >= timedelta(hours=24):
            try:
                _enviar(formatador.falha(erro.fonte, erro.motivo))
                falhas = copy.deepcopy(estado)
                falhas.setdefault("falhas", {})[erro.fonte] = agora.isoformat().replace("+00:00", "Z")
                gravacao.gravar({raiz / "estado.json": falhas})
            except (telegram.ErroTelegram, ValueError, OSError):
                return 1
        return 1
    except (telegram.ErroTelegram, ValueError, OSError):
        # Não imprimir a exceção: respostas do Telegram podem conter dados sensíveis.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
