"""Orquestra uma coleta; persiste somente após todos os envios terem sucesso."""

import copy
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hsds import blizzard, diff, formatador, gravacao, hearthstonejson, http, telegram

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
    }


def _nome(patch: dict) -> str:
    versao = patch["versao"] or f"b{patch['build']}"
    return f"patches/{patch['data']}-{versao}.json"


def _planejar(raiz: Path, estado: dict, noticias: list, build: int, cartas, agora: datetime):
    estado = copy.deepcopy(estado)
    instante = agora.isoformat().replace("+00:00", "Z")
    hoje = agora.date().isoformat()
    estado["pendentes"] = [
        item for item in estado["pendentes"]
        if agora - _data(item["desde"]) < timedelta(days=7)
    ]
    patches = {item["arquivo"]: gravacao.ler(raiz / item["arquivo"]) for item in estado["pendentes"]}
    alterados = {}
    textos = []
    mudancas = diff.comparar(gravacao.ler(raiz / "cartas.json"), cartas) if cartas else None
    tem_diff = mudancas is not None and any(mudancas.values())
    novas = sorted(
        (item for item in noticias if item.id not in estado["noticias_vistas"] and blizzard.e_patch(item)),
        key=lambda item: (item.publicada, item.id),
    )

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
            ingles = sorted(
                (item for item in _noticias("en-us") if blizzard.e_patch(item)),
                key=lambda item: (item.publicada, item.id),
                reverse=True,
            )
            indice = gravacao.ler(raiz / "indice.json", {"patches": []})
            versoes = {item["versao"] for item in indice["patches"] if item["versao"]}
            noticia = ingles[0] if ingles else None
            if noticia and noticia.versao in versoes:
                noticia = None
            patch = _novo(noticia, build, hoje, mudancas, ingles=True)
            guardar(_nome(patch), patch, "noticia_ptbr")
            textos.extend(formatador.sem_portugues(patch))

    estado["build"] = build
    vistas = sorted(noticias, key=lambda item: (item.publicada, item.id), reverse=True)
    estado["noticias_vistas"] = list(dict.fromkeys([item.id for item in vistas] + estado["noticias_vistas"]))[:100]
    arquivos = {raiz / arquivo: patch for arquivo, patch in alterados.items()}
    if alterados:
        indice = gravacao.ler(raiz / "indice.json", {"patches": []})
        entradas = [item for item in indice["patches"] if item["arquivo"] not in alterados]
        for arquivo, patch in alterados.items():
            contagens = {grupo: len((patch["cartas"] or {}).get(grupo, [])) for grupo in ("buffs", "nerfs", "alteradas")}
            entradas.insert(0, {"arquivo": arquivo, "versao": patch["versao"], "data": patch["data"], **contagens})
        entradas.sort(key=lambda item: item["data"], reverse=True)
        arquivos[raiz / "indice.json"] = {"patches": entradas}
    if cartas is not None:
        arquivos[raiz / "cartas.json"] = cartas
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
            gravacao.gravar({raiz / "cartas.json": cartas, raiz / "estado.json": linha_base})
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
