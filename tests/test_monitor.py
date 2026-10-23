import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hsds import gravacao, http, monitor, telegram

DADOS = Path(__file__).parent / "dados"


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_TOKEN", "token-ficticio")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "destino-ficticio")
    contexto = {
        "agora": datetime(2026, 10, 23, 18, 17, tzinfo=timezone.utc),
        "build": 255130,
        "pt": (DADOS / "noticias-base.json").read_bytes(),
        "en": (DADOS / "noticias-ingles.json").read_bytes(),
        "cartas": (DADOS / "cartas-antes.json").read_bytes(),
        "chamadas": [],
        "envios": [],
        "erros": {},
        "telegram_falha": False,
    }

    def baixar(url, **kwargs):
        contexto["chamadas"].append(url)
        if url in contexto["erros"]:
            raise contexto["erros"][url]
        if url == http.ULTIMA_BUILD:
            return f'<a href="/v1/{contexto["build"]}/ptBR/">ptBR</a>'.encode()
        if url == monitor.LISTA.format(idioma="pt-br"):
            return contexto["pt"]
        if url == monitor.LISTA.format(idioma="en-us"):
            return contexto["en"]
        assert url == monitor.CARTAS.format(build=contexto["build"])
        return contexto["cartas"]

    def enviar(token, chat_id, texto):
        assert token == "token-ficticio"
        assert chat_id == "destino-ficticio"
        if contexto["telegram_falha"]:
            raise telegram.ErroTelegram("falha fictícia")
        contexto["envios"].append(texto)
        return {"message_id": len(contexto["envios"])}

    monkeypatch.setattr(http, "baixar", baixar)
    monkeypatch.setattr(telegram, "enviar_mensagem", enviar)
    monkeypatch.setattr(monitor, "_agora", lambda: contexto["agora"])
    return contexto


def ler(nome):
    return gravacao.ler(Path("dados") / nome)


def arquivos():
    return {str(arquivo): arquivo.read_bytes() for arquivo in Path("dados").rglob("*.json")}


def nova_build(ambiente):
    ambiente["build"] += 1
    ambiente["cartas"] = (DADOS / "cartas-depois.json").read_bytes()


def noticia_pt(ambiente):
    ambiente["pt"] = (DADOS / "noticias-patch.json").read_bytes()


def test_linha_base_sem_aviso(ambiente):
    assert monitor.main() == 0
    estado = ler("estado.json")
    assert estado == {"build": 255130, "noticias_vistas": [11, 10], "pendentes": [], "falhas": {}}
    assert ler("cartas.json")["build"] == 255130
    assert ambiente["envios"] == []
    assert len(ambiente["chamadas"]) == 3
    assert ler("indice.json") is None


def test_rotina_duas_requisicoes_sem_regravar_cartas(ambiente):
    assert monitor.main() == 0
    antes = arquivos()
    ambiente["chamadas"].clear()
    assert monitor.main() == 0
    assert ambiente["chamadas"] == [monitor.LISTA.format(idioma="pt-br"), http.ULTIMA_BUILD]
    assert arquivos() == antes
    assert not ambiente["envios"]


def test_patch_completo_e_sem_segundo_aviso(ambiente):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    nova_build(ambiente)
    ambiente["chamadas"].clear()
    assert monitor.main() == 0
    assert len(ambiente["chamadas"]) == 3
    assert len(ambiente["envios"]) == 1
    assert "saiu o patch 36.6" in ambiente["envios"][0]
    patch = ler("patches/2026-10-23-36.6.json")
    assert patch["noticia"]["id"] == 12
    assert "content" not in patch["noticia"]
    assert patch["noticia_en"] is None
    assert len(patch["cartas"]["buffs"]) == 1
    assert len(patch["cartas"]["nerfs"]) == 1
    assert ler("indice.json")["patches"] == [{"arquivo": "patches/2026-10-23-36.6.json", "versao": "36.6", "data": "2026-10-23", "buffs": 1, "nerfs": 1, "alteradas": 0}]
    assert ler("estado.json")["pendentes"] == []
    antes = arquivos()
    assert monitor.main() == 0
    assert len(ambiente["envios"]) == 1
    assert arquivos() == antes


def test_cartas_antes_do_ptbr_completa_uma_vez(ambiente):
    assert monitor.main() == 0
    nova_build(ambiente)
    ambiente["chamadas"].clear()
    assert monitor.main() == 0
    assert len(ambiente["chamadas"]) == 4
    assert "ainda não publicada" in ambiente["envios"][0]
    estado = ler("estado.json")
    assert estado["pendentes"][0]["falta"] == "noticia_ptbr"
    arquivo = estado["pendentes"][0]["arquivo"]
    assert ler(arquivo)["noticia_en"]["id"] == 20
    assert ler(arquivo)["noticia"] is None
    assert monitor.main() == 0
    assert len(ambiente["envios"]) == 1
    noticia_pt(ambiente)
    assert monitor.main() == 0
    assert ambiente["envios"][1].startswith("Hearthstone DS: notícia em português do patch 36.6")
    assert ler(arquivo)["noticia"]["id"] == 12
    assert ler("estado.json")["pendentes"] == []
    assert len(ler("indice.json")["patches"]) == 1
    assert monitor.main() == 0
    assert len(ambiente["envios"]) == 2


def test_noticia_antes_das_cartas_completa_uma_vez(ambiente):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    assert monitor.main() == 0
    assert "As cartas alteradas chegam em outra mensagem" in ambiente["envios"][0]
    assert ler("patches/2026-10-23-36.6.json")["cartas"] is None
    assert ler("estado.json")["pendentes"][0]["falta"] == "cartas"
    nova_build(ambiente)
    ambiente["chamadas"].clear()
    assert monitor.main() == 0
    assert len(ambiente["chamadas"]) == 3
    assert ambiente["envios"][1].startswith("Hearthstone DS: cartas alteradas no patch 36.6")
    assert ler("patches/2026-10-23-36.6.json")["build"] == ambiente["build"]
    assert ler("estado.json")["pendentes"] == []
    assert monitor.main() == 0
    assert len(ambiente["envios"]) == 2


def test_build_sem_diff_so_atualiza_base(ambiente):
    assert monitor.main() == 0
    ambiente["build"] += 1
    ambiente["chamadas"].clear()
    assert monitor.main() == 0
    assert len(ambiente["chamadas"]) == 3
    assert ler("estado.json")["build"] == ambiente["build"]
    assert ler("cartas.json")["build"] == ambiente["build"]
    assert ler("indice.json") is None
    assert not ambiente["envios"]


def test_sem_noticia_ingles_e_versao_fallback(ambiente):
    assert monitor.main() == 0
    nova_build(ambiente)
    ambiente["en"] = b'{"blogList": []}'
    assert monitor.main() == 0
    arquivo = f"patches/2026-10-23-b{ambiente['build']}.json"
    assert ler(arquivo)["versao"] is None
    assert "Notícias: https://hearthstone.blizzard.com/pt-br/news" in ambiente["envios"][0]
    noticia_pt(ambiente)
    assert monitor.main() == 0
    assert ler(arquivo)["versao"] == "36.6"
    assert ler("estado.json")["pendentes"] == []


def test_sem_versao_no_ptbr_completa_unico_pendente(ambiente):
    assert monitor.main() == 0
    nova_build(ambiente)
    assert monitor.main() == 0
    noticia_pt(ambiente)
    dados = json.loads(ambiente["pt"])
    dados["blogList"][0]["title"] = "Notas do patch"
    ambiente["pt"] = json.dumps(dados).encode()
    assert monitor.main() == 0
    assert ler("estado.json")["pendentes"] == []
    assert len(ler("indice.json")["patches"]) == 1


def test_pendente_expira_em_sete_dias(ambiente):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    assert monitor.main() == 0
    ambiente["agora"] += timedelta(days=7)
    assert monitor.main() == 0
    assert ler("estado.json")["pendentes"] == []
    assert ler("patches/2026-10-23-36.6.json")["cartas"] is None


@pytest.mark.parametrize("com_cartas", [True, False])
def test_falha_telegram_nada_gravado_e_tentativa_posterior(ambiente, com_cartas):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    if com_cartas:
        nova_build(ambiente)
    antes = arquivos()
    ambiente["telegram_falha"] = True
    assert monitor.main() == 1
    assert arquivos() == antes
    ambiente["telegram_falha"] = False
    assert monitor.main() == 0
    assert len(ambiente["envios"]) == 1


def test_envia_antes_de_gravar(ambiente, monkeypatch):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    nova_build(ambiente)
    antes = arquivos()
    enviar = telegram.enviar_mensagem

    def conferir(*args):
        assert arquivos() == antes
        return enviar(*args)

    monkeypatch.setattr(telegram, "enviar_mensagem", conferir)
    assert monitor.main() == 0


@pytest.mark.parametrize("fonte", ["blizzard", "hearthstonejson"])
@pytest.mark.parametrize("motivo", ["site fora do ar ou sem resposta", "formato da resposta mudou", "JSON inválido"])
def test_falha_por_fonte_so_grava_falhas_e_limita_24h(ambiente, fonte, motivo):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    nova_build(ambiente)
    url = monitor.LISTA.format(idioma="pt-br") if fonte == "blizzard" else http.ULTIMA_BUILD
    ambiente["erros"][url] = http.ErroFonte(fonte, motivo)
    antes = arquivos()
    estado_antes = copy.deepcopy(ler("estado.json"))
    assert monitor.main() == 1
    depois = arquivos()
    assert {nome: bruto for nome, bruto in antes.items() if not nome.endswith("estado.json")} == {nome: bruto for nome, bruto in depois.items() if not nome.endswith("estado.json")}
    estado_depois = ler("estado.json")
    assert estado_depois.pop("falhas")[fonte].endswith("Z")
    estado_antes.pop("falhas")
    assert estado_depois == estado_antes
    assert motivo in ambiente["envios"][0]
    ambiente["agora"] += timedelta(hours=23, minutes=59)
    assert monitor.main() == 1
    assert len(ambiente["envios"]) == 1
    ambiente["agora"] += timedelta(minutes=1)
    assert monitor.main() == 1
    assert len(ambiente["envios"]) == 2


def test_falhas_independentes_e_primeira_coleta_depois_de_falha(ambiente):
    url = monitor.LISTA.format(idioma="pt-br")
    ambiente["erros"][url] = http.ErroFonte("blizzard", "JSON inválido")
    assert monitor.main() == 1
    assert set(ler("estado.json")) == {"falhas"}
    ambiente["erros"].clear()
    ambiente["erros"][http.ULTIMA_BUILD] = http.ErroFonte("hearthstonejson", "formato da resposta mudou")
    assert monitor.main() == 1
    assert len(ambiente["envios"]) == 2
    assert set(ler("estado.json")["falhas"]) == {"blizzard", "hearthstonejson"}
    ambiente["erros"].clear()
    assert monitor.main() == 0
    assert len(ambiente["envios"]) == 2
    assert ler("estado.json")["build"] == 255130


def test_falha_fonte_com_telegram_indisponivel_nao_marca_aviso(ambiente):
    assert monitor.main() == 0
    antes = arquivos()
    ambiente["pt"] = b"JSON quebrado"
    ambiente["telegram_falha"] = True
    assert monitor.main() == 1
    assert arquivos() == antes


def test_json_cartas_invalido_e_falha_ingles_descartam_plano(ambiente):
    assert monitor.main() == 0
    antes = arquivos()
    nova_build(ambiente)
    ambiente["cartas"] = b"{"
    assert monitor.main() == 1
    assert "JSON inválido" in ambiente["envios"][0]
    assert ler("estado.json")["build"] == 255130
    ambiente["cartas"] = (DADOS / "cartas-depois.json").read_bytes()
    ambiente["en"] = b'{"formato": "mudou"}'
    assert monitor.main() == 1
    assert "notícias da Blizzard falhou" in ambiente["envios"][1]
    assert ler("estado.json")["build"] == 255130
    assert ler("cartas.json")["build"] == 255130
    assert ler("indice.json") is None
    caminho = str(Path("dados") / "cartas.json")
    assert arquivos()[caminho] == antes[caminho]


def test_aviso_de_falha_nao_avanca_noticias_e_build(ambiente):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    nova_build(ambiente)
    ambiente["erros"][http.ULTIMA_BUILD] = http.ErroFonte("hearthstonejson", "formato da resposta mudou")
    assert monitor.main() == 1
    assert 12 not in ler("estado.json")["noticias_vistas"]
    ambiente["erros"].clear()
    assert monitor.main() == 0
    assert "saiu o patch 36.6" in ambiente["envios"][1]
    assert ler("estado.json")["build"] == ambiente["build"]


def test_patch_com_versao_diferente_nao_completa_pendente(ambiente):
    assert monitor.main() == 0
    nova_build(ambiente)
    assert monitor.main() == 0
    noticia_pt(ambiente)
    noticias = json.loads(ambiente["pt"])
    noticias["blogList"][0]["title"] = "Notas do patch 36.6.3:"
    ambiente["pt"] = json.dumps(noticias).encode()
    assert monitor.main() == 0
    assert ler("patches/2026-10-23-36.6.json")["noticia"] is None
    assert ler("patches/2026-10-23-36.6.3.json")["noticia"]["id"] == 12
    assert len(ler("estado.json")["pendentes"]) == 2


def test_noticia_nao_patch_nao_envia_aviso(ambiente):
    assert monitor.main() == 0
    dados = json.loads(ambiente["pt"])
    dados["blogList"][0]["id"] = 99
    dados["blogList"][0]["title"] = "Uma novidade fictícia"
    ambiente["pt"] = json.dumps(dados).encode()
    assert monitor.main() == 0
    assert 99 in ler("estado.json")["noticias_vistas"]
    assert not ambiente["envios"]


def test_limita_noticias_vistas_a_cem(ambiente):
    assert monitor.main() == 0
    estado = ler("estado.json")
    estado["noticias_vistas"] = list(range(100, 250))
    gravacao.gravar({Path("dados/estado.json"): estado})
    assert monitor.main() == 0
    assert len(ler("estado.json")["noticias_vistas"]) == 100
    assert len(set(ler("estado.json")["noticias_vistas"])) == 100


def test_falha_na_ultima_parte_do_telegram_nao_grava(ambiente, monkeypatch):
    cartas = json.loads(ambiente["cartas"])
    cartas = [{**cartas[0], "dbfId": numero, "name": f"Carta fictícia {numero}"} for numero in range(1, 201)]
    ambiente["cartas"] = json.dumps(cartas).encode()
    assert monitor.main() == 0
    antes = arquivos()
    noticia_pt(ambiente)
    ambiente["build"] += 1
    ambiente["cartas"] = json.dumps([{**carta, "cost": 2} for carta in cartas]).encode()
    enviar = telegram.enviar_mensagem
    chamadas = 0

    def falhar_na_segunda(*args):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 2:
            raise telegram.ErroTelegram("falha fictícia na segunda parte")
        return enviar(*args)

    monkeypatch.setattr(telegram, "enviar_mensagem", falhar_na_segunda)
    assert monitor.main() == 1
    assert chamadas == 2
    assert arquivos() == antes
