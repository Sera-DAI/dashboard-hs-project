"""Orquestra uma coleta; persiste somente após todos os envios terem sucesso."""

import copy
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hsds import blizzard, diff, formatador, gravacao, hearthstonejson, http, resumo_ia, telegram

LISTA = "https://hearthstone.blizzard.com/{idioma}/api/blog/articleList/?page=1&pageSize=12"
CARTAS = "https://api.hearthstonejson.com/v1/{build}/ptBR/cards.collectible.json"
LIMITE_RESUMOS = 3


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
    estado.setdefault("resumos_pendentes", [])
    instante = agora.isoformat().replace("+00:00", "Z")
    hoje = agora.date().isoformat()
    estado["pendentes"] = [
        item for item in estado["pendentes"]
        if agora - _data(item["desde"]) < timedelta(days=7)
    ]
    patches = {item["arquivo"]: gravacao.ler(raiz / item["arquivo"]) for item in estado["pendentes"]}
    alterados = {}
    textos = []
    chamadas_resumo = 0
    arquivos_com_resumo_tentado = set()
    pendentes_antes = {item["arquivo"] for item in estado["resumos_pendentes"]}
    mudancas = diff.comparar(gravacao.ler(raiz / "cartas.json"), cartas) if cartas else None
    tem_diff = mudancas is not None and any(mudancas.values())
    novas = sorted(
        (item for item in noticias if item.id not in estado["noticias_vistas"] and blizzard.e_patch(item)),
        key=lambda item: (item.publicada, item.id),
    )
    novas_notas = sorted(
        (item for item in noticias if item.id not in estado["noticias_vistas"] and not blizzard.e_patch(item)),
        key=lambda item: (item.publicada, item.id),
    )
    prioritarias = {item.id for item in novas[-LIMITE_RESUMOS:]}
    prioritarias_notas = {item.id for item in novas_notas[-LIMITE_RESUMOS:]}
    indice_noticias = gravacao.ler(raiz / "noticias.json", {"noticias": []})
    alteradas_noticias = {}

    def guardar(arquivo, patch, falta=None):
        if arquivo not in patches and (raiz / arquivo).exists():
            raise ValueError("arquivo de patch já existe")
        patches[arquivo] = patch
        alterados[arquivo] = patch
        if falta:
            estado["pendentes"].append({"arquivo": arquivo, "falta": falta, "desde": instante})

    def marcar_resumo_pendente(arquivo, patch):
        # Um resumo anterior continua valendo; só patch sem resumo volta para a fila.
        if patch.get("resumo_ia"):
            return
        patch["resumo_ia"] = None
        if not any(item["arquivo"] == arquivo for item in estado["resumos_pendentes"]):
            estado["resumos_pendentes"].append({"arquivo": arquivo, "desde": instante})

    def gerar_resumo(arquivo, patch, noticia, permitido=True):
        nonlocal chamadas_resumo
        if noticia is None or not noticia.texto:
            return False
        if chamadas_resumo >= LIMITE_RESUMOS or not permitido:
            marcar_resumo_pendente(arquivo, patch)
            return False
        chamadas_resumo += 1
        arquivos_com_resumo_tentado.add(arquivo)
        try:
            topicos = resumo_ia.gerar(
                noticia.titulo,
                noticia.texto,
                "pt-br" if noticia.link.find("/pt-br/") >= 0 else "en-us",
                patch.get("cartas"),
                os.environ.get("GEMINI_API_KEY", ""),
                com_cartas=patch.get("_com_cartas", True),
            )
        except resumo_ia.ErroResumo:
            marcar_resumo_pendente(arquivo, patch)
            return False
        patch["resumo_ia"] = {
            "topicos": topicos,
            "modelo": resumo_ia.MODELO,
            "gerado": instante,
        }
        estado["resumos_pendentes"] = [
            item for item in estado["resumos_pendentes"] if item["arquivo"] != arquivo
        ]
        return True

    for noticia in novas:
        pendente = _pendente(estado, patches, "noticia_ptbr", noticia.versao)
        if pendente:
            arquivo = pendente["arquivo"]
            patch = patches[arquivo]
            patch["noticia"] = noticia.dados()
            if patch["versao"] is None:
                patch["versao"] = noticia.versao
            gerar_resumo(arquivo, patch, noticia, noticia.id in prioritarias)
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
        gerar_resumo(arquivo, patch, noticia, noticia.id in prioritarias)
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
            id_noticia = (patch.get("noticia") or {}).get("id")
            noticia_atual = next(
                (item for item in noticias if item.id == id_noticia),
                None,
            )
            gerar_resumo(arquivo, patch, noticia_atual)
            estado["pendentes"].remove(pendente)
            guardar(arquivo, patch)
            textos.extend(formatador.cartas_atualizadas(patch))
        else:
            noticias_ingles = _noticias("en-us")
            ingles = sorted(
                (item for item in noticias_ingles if blizzard.e_patch(item)),
                key=lambda item: (item.publicada, item.id),
                reverse=True,
            )
            indice = gravacao.ler(raiz / "indice.json", {"patches": []})
            versoes = {item["versao"] for item in indice["patches"] if item["versao"]}
            noticia = ingles[0] if ingles else None
            if noticia and noticia.versao in versoes:
                noticia = None
            patch = _novo(noticia, build, hoje, mudancas, ingles=True)
            arquivo = _nome(patch)
            gerar_resumo(arquivo, patch, noticia)
            guardar(arquivo, patch, "noticia_ptbr")
            textos.extend(formatador.sem_portugues(patch))

    resumos_noticias = {}
    for noticia in reversed(novas_notas):
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
        registro_para_gerar = {**registro, "_com_cartas": False}
        gerar_resumo(arquivo, registro_para_gerar, noticia, noticia.id in prioritarias_notas)
        resumos_noticias[arquivo] = registro_para_gerar["resumo_ia"]

    for noticia in novas_notas:
        arquivo = _nome_noticia(noticia)
        if (raiz / arquivo).exists():
            continue
        registro = {
            "id": noticia.id,
            "titulo": noticia.titulo,
            "link": noticia.link,
            "publicada": noticia.publicada,
            "resumo_ia": resumos_noticias.get(arquivo),
        }
        alteradas_noticias[arquivo] = registro
        if registro["resumo_ia"]:
            estado["resumos_pendentes"] = [
                item for item in estado["resumos_pendentes"] if item["arquivo"] != arquivo
            ]
        elif not any(item["arquivo"] == arquivo for item in estado["resumos_pendentes"]):
            estado["resumos_pendentes"].append({"arquivo": arquivo, "desde": instante})
        entrada = {"arquivo": arquivo, "id": noticia.id, "titulo": noticia.titulo, "data": noticia.publicada[:10]}
        indice_noticias["noticias"] = [entrada, *[item for item in indice_noticias["noticias"] if item["arquivo"] != arquivo]]
        textos.extend(formatador.noticia_nova(noticia.dados(), registro["resumo_ia"]))

    estado["resumos_pendentes"] = [
        item for item in estado["resumos_pendentes"]
        if agora - _data(item["desde"]) < timedelta(hours=24)
    ]
    candidatos = sorted(
        (item for item in estado["resumos_pendentes"] if item["arquivo"] in pendentes_antes),
        key=lambda item: item["desde"],
        reverse=True,
    )
    for item in candidatos:
        if chamadas_resumo >= LIMITE_RESUMOS:
            break
        if item["arquivo"] in arquivos_com_resumo_tentado:
            continue
        is_noticia = item["arquivo"].startswith("noticias/")
        patch = gravacao.ler(raiz / item["arquivo"]) if is_noticia else patches.get(item["arquivo"])
        if patch is None:
            patch = gravacao.ler(raiz / item["arquivo"])
            patches[item["arquivo"]] = patch
        id_noticia = patch.get("id") if is_noticia else (patch.get("noticia") or {}).get("id")
        noticia_atual = next(
            (noticia for noticia in noticias if noticia.id == id_noticia),
            None,
        )
        if noticia_atual:
            registro_para_gerar = {**patch, "_com_cartas": not is_noticia}
            if gerar_resumo(item["arquivo"], registro_para_gerar, noticia_atual):
                patch["resumo_ia"] = registro_para_gerar["resumo_ia"]
                if is_noticia:
                    alteradas_noticias[item["arquivo"]] = patch
                    indice_noticias["noticias"] = [
                        entrada for entrada in indice_noticias["noticias"] if entrada["arquivo"] != item["arquivo"]
                    ]
                    indice_noticias["noticias"].insert(0, {"arquivo": item["arquivo"], "id": patch["id"], "titulo": patch["titulo"], "data": patch["publicada"][:10]})
                    textos.extend(formatador.resumo_noticia(patch))
                else:
                    alterados[item["arquivo"]] = patch
                    textos.extend(formatador.resumo_atrasado(patch))
            break

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
                "resumos_pendentes": [],
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
