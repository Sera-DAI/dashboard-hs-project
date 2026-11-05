import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hsds import blizzard, gravacao, http, monitor, resumo_ia, telegram

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
        "chamadas_resumo": [],
    }

    def gerar(titulo, texto, idioma, cartas, chave, **kwargs):
        contexto["chamadas_resumo"].append((titulo, idioma, cartas))
        return ["Arena recebe ajustes.", "Novo evento chega.", "Bugs importantes corrigidos."]

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
    monkeypatch.setattr(resumo_ia, "gerar", gerar)
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


def adicionar_noticia(ambiente, identificador, titulo, publicada):
    dados = json.loads(ambiente["pt"])
    dados["blogList"].append({
        "id": identificador,
        "title": titulo,
        "summary": f"Resumo oficial fictício {identificador}.",
        "content": f"Conteúdo original fictício da notícia {identificador}.",
        "publish": publicada,
    })
    ambiente["pt"] = json.dumps(dados).encode()


def test_linha_base_sem_aviso(ambiente):
    assert monitor.main() == 0
    estado = ler("estado.json")
    assert estado == {"build": 255130, "noticias_vistas": [11, 10], "pendentes": [], "falhas": {}, "resumos_pendentes": []}
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
    assert patch["resumo_ia"]["modelo"] == resumo_ia.MODELO
    assert patch["resumo_ia"]["topicos"]
    assert "texto" not in patch["noticia"]
    assert len(patch["cartas"]["buffs"]) == 1
    assert len(patch["cartas"]["nerfs"]) == 1
    assert ler("indice.json")["patches"] == [{"arquivo": "patches/2026-10-23-36.6.json", "versao": "36.6", "data": "2026-10-23", "buffs": 1, "nerfs": 1, "alteradas": 0, "revisadas": 0}]
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


def test_noticia_nova_grava_sem_texto_blizzard_e_atualiza_indice(ambiente):
    assert monitor.main() == 0
    adicionar_noticia(ambiente, 99, "Uma novidade fictícia", 1792760000000)
    ambiente["chamadas"].clear()
    assert monitor.main() == 0
    assert 99 in ler("estado.json")["noticias_vistas"]
    arquivo = "noticias/2026-10-23-99.json"
    noticia = ler(arquivo)
    assert noticia["id"] == 99
    assert noticia["titulo"] == "Uma novidade fictícia"
    assert "content" not in noticia and "resumo" not in noticia
    assert noticia["resumo_ia"]["topicos"]
    assert ler("noticias.json")["noticias"] == [{
        "arquivo": arquivo,
        "id": 99,
        "titulo": "Uma novidade fictícia",
        "data": "2026-10-23",
    }]
    assert ambiente["envios"][0].startswith("Hearthstone DS: notícia nova")
    assert ambiente["chamadas"] == [monitor.LISTA.format(idioma="pt-br"), http.ULTIMA_BUILD]


def test_noticias_ja_vistas_nao_geram_avisos(ambiente):
    assert monitor.main() == 0
    assert monitor.main() == 0
    assert not ambiente["envios"]
    assert ler("noticias.json") is None


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


def test_falha_do_resumo_nao_bloqueia_aviso_e_tenta_novamente(ambiente, monkeypatch):
    assert monitor.main() == 0
    noticia_pt(ambiente)

    def falhar(*_args, **_kwargs):
        raise resumo_ia.ErroResumo("serviço fora do ar ou sem resposta")

    monkeypatch.setattr(resumo_ia, "gerar", falhar)
    assert monitor.main() == 0
    arquivo = "patches/2026-10-23-36.6.json"
    patch = ler(arquivo)
    assert patch["resumo_ia"] is None
    assert ler("estado.json")["resumos_pendentes"] == [{"arquivo": arquivo, "desde": "2026-10-23T18:17:00Z"}]
    assert "saiu o patch 36.6" in ambiente["envios"][0]
    assert "Resumo gerado por IA" not in ambiente["envios"][0]

    monkeypatch.setattr(resumo_ia, "gerar", lambda *args, **kwargs: ["Arena recebe ajustes.", "Novo evento chega.", "Bugs importantes corrigidos."])
    ambiente["agora"] += timedelta(minutes=30)
    assert monitor.main() == 0
    assert ler("estado.json")["resumos_pendentes"] == []
    assert len(ambiente["envios"]) == 2
    assert ambiente["envios"][1].startswith("Hearthstone DS: resumo do patch 36.6")


def test_resumo_pendente_expira_em_7_dias(ambiente, monkeypatch):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    monkeypatch.setattr(resumo_ia, "gerar", lambda *args, **kwargs: (_ for _ in ()).throw(resumo_ia.ErroResumo("resposta inválida")))
    assert monitor.main() == 0
    ambiente["agora"] += timedelta(hours=24)
    assert monitor.main() == 0
    assert len(ler("estado.json")["resumos_pendentes"]) == 1
    ambiente["agora"] += timedelta(days=7)
    assert monitor.main() == 0
    assert ler("estado.json")["resumos_pendentes"] == []
    # O patch ainda é recente (menos de 14 dias): a revisão o põe de volta na fila na execução seguinte.
    ambiente["agora"] += timedelta(hours=1)
    assert monitor.main() == 0
    assert [item["desde"] for item in ler("estado.json")["resumos_pendentes"]] == ["2026-10-31T19:17:00Z"]
    ambiente["agora"] += timedelta(days=8)
    assert monitor.main() == 0
    assert ler("estado.json")["resumos_pendentes"] == []


def lista_ingles(ambiente, identificador, titulo, conteudo, publicada=1792771200000):
    ambiente["en"] = json.dumps({"blogList": [{
        "id": identificador,
        "title": titulo,
        "summary": "Official summary.",
        "content": conteudo,
        "publish": publicada,
    }]}).encode()


def test_resumo_sai_depois_de_a_traducao_demorar_mais_de_24_horas(ambiente, monkeypatch):
    # O caso do 37.0.2: aviso em inglês, resumo falha, e a notícia pt-BR só aparece dias depois.
    assert monitor.main() == 0
    lista_ingles(ambiente, 20, "36.6 Patch Notes", "<p>English body of the notes.</p>")
    nova_build(ambiente)
    monkeypatch.setattr(resumo_ia, "gerar", lambda *args, **kwargs: (_ for _ in ()).throw(resumo_ia.ErroResumo("limite de uso atingido")))
    assert monitor.main() == 0
    arquivo = "patches/2026-10-23-36.6.json"
    assert ler(arquivo)["resumo_ia"] is None
    assert [item["arquivo"] for item in ler("estado.json")["resumos_pendentes"]] == [arquivo]

    chamadas = []

    def gerar(titulo, texto, idioma, cartas, chave, **kwargs):
        chamadas.append((titulo, idioma))
        return ["Arena recebe ajustes.", "Novo evento chega.", "Bugs importantes corrigidos."]

    monkeypatch.setattr(resumo_ia, "gerar", gerar)
    ambiente["agora"] += timedelta(days=2)
    assert monitor.main() == 0
    assert chamadas == [("36.6 Patch Notes", "en-us")]
    assert ler(arquivo)["resumo_ia"]["topicos"]
    assert ler("estado.json")["resumos_pendentes"] == []
    assert ambiente["envios"][-1].startswith("Hearthstone DS: resumo do patch 36.6")


def test_patch_recente_sem_resumo_e_sem_pendencia_volta_para_a_fila(ambiente, monkeypatch):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    monkeypatch.setattr(resumo_ia, "gerar", lambda *args, **kwargs: (_ for _ in ()).throw(resumo_ia.ErroResumo("resposta inválida")))
    assert monitor.main() == 0
    arquivo = "patches/2026-10-23-36.6.json"
    estado = ler("estado.json")
    estado["resumos_pendentes"] = []
    gravacao.gravar({Path("dados/estado.json"): estado})
    monkeypatch.setattr(resumo_ia, "gerar", lambda *args, **kwargs: ["Arena recebe ajustes.", "Novo evento chega.", "Bugs importantes corrigidos."])
    ambiente["agora"] += timedelta(hours=2)
    assert monitor.main() == 0
    assert ler(arquivo)["resumo_ia"]["topicos"]
    assert ler("estado.json")["resumos_pendentes"] == []


def test_retroativo_sem_resumo_nao_volta_para_a_fila_do_monitor(ambiente, monkeypatch):
    assert monitor.main() == 0
    patch = {"versao": "35.4", "data": "2026-10-20", "build": 1, "noticia": {"id": 10, "titulo": "Notas do patch 35.4", "link": "x", "publicada": "2026-10-20T10:00:00Z"}, "noticia_en": None, "cartas": None, "retroativo": True, "resumo_ia": None}
    gravacao.gravar({
        Path("dados/patches/2026-10-20-35.4.json"): patch,
        Path("dados/indice.json"): {"patches": [{"arquivo": "patches/2026-10-20-35.4.json", "versao": "35.4", "data": "2026-10-20", "buffs": 0, "nerfs": 0, "alteradas": 0, "revisadas": 0}]},
    })
    assert monitor.main() == 0
    assert ler("estado.json")["resumos_pendentes"] == []


def test_lista_ptbr_sem_texto_usa_o_texto_em_ingles(ambiente, monkeypatch, capsys):
    assert monitor.main() == 0
    dados = json.loads((DADOS / "noticias-patch.json").read_bytes())
    dados["blogList"][0]["content"] = ""
    ambiente["pt"] = json.dumps(dados).encode()
    lista_ingles(ambiente, 12, "36.6 Patch Notes", "<p>English body of the notes.</p>")
    chamadas = []

    def gerar(titulo, texto, idioma, cartas, chave, **kwargs):
        chamadas.append((titulo, texto, idioma))
        return ["Arena recebe ajustes.", "Novo evento chega.", "Bugs importantes corrigidos."]

    monkeypatch.setattr(resumo_ia, "gerar", gerar)
    assert monitor.main() == 0
    assert chamadas == [("36.6 Patch Notes", "English body of the notes.", "en-us")]
    assert ler("patches/2026-10-23-36.6.json")["resumo_ia"]["topicos"]


def test_sem_texto_em_nenhuma_lingua_fica_pendente_e_avisa_no_log(ambiente, monkeypatch, capsys):
    assert monitor.main() == 0
    dados = json.loads((DADOS / "noticias-patch.json").read_bytes())
    dados["blogList"][0]["content"] = ""
    ambiente["pt"] = json.dumps(dados).encode()
    lista_ingles(ambiente, 12, "36.6 Patch Notes", None)
    monkeypatch.setattr(resumo_ia, "gerar", lambda *args, **kwargs: pytest.fail("não há texto para resumir"))
    assert monitor.main() == 0
    arquivo = "patches/2026-10-23-36.6.json"
    assert ler(arquivo)["resumo_ia"] is None
    assert [item["arquivo"] for item in ler("estado.json")["resumos_pendentes"]] == [arquivo]
    assert "sem o texto da notícia" in capsys.readouterr().out


def test_limita_tres_geracoes_prioriza_patch_e_noticias_mais_novas(ambiente):
    assert monitor.main() == 0
    dados = json.loads((DADOS / "noticias-patch.json").read_bytes())
    for identificador, publicada in ((31, 1792785600000), (32, 1792789200000), (33, 1792792800000)):
        dados["blogList"].append({
            "id": identificador,
            "title": f"Notícia fictícia {identificador}",
            "summary": "Resumo oficial fictício.",
            "content": f"Conteúdo original fictício {identificador}.",
            "publish": publicada,
        })
    ambiente["pt"] = json.dumps(dados).encode()
    ambiente["chamadas_resumo"].clear()
    assert monitor.main() == 0
    assert [chamada[0] for chamada in ambiente["chamadas_resumo"]] == [
        "[Atualizado em 30/09/2026] Notas do patch 36.6",
        "Notícia fictícia 33",
        "Notícia fictícia 32",
    ]
    assert ambiente["envios"][0].startswith("Hearthstone DS: saiu o patch 36.6")
    pendentes_noticias = ler("estado.json")["resumos_pendentes"]
    assert [item["arquivo"] for item in pendentes_noticias] == ["noticias/2026-10-23-31.json"]


def test_nova_tentativa_de_noticia_envia_mensagem_9(ambiente, monkeypatch):
    assert monitor.main() == 0
    adicionar_noticia(ambiente, 77, "Novidade que falha", 1792760000000)

    def falhar(*_args, **_kwargs):
        raise resumo_ia.ErroResumo("serviço fora do ar ou sem resposta")

    monkeypatch.setattr(resumo_ia, "gerar", falhar)
    assert monitor.main() == 0
    assert ler("noticias/2026-10-23-77.json")["resumo_ia"] is None
    assert "Resumo gerado por IA" not in ambiente["envios"][0]
    monkeypatch.setattr(resumo_ia, "gerar", lambda *args, **kwargs: ["Loja: itens novos.", "Evento: começa hoje.", "Bugs: correções aplicadas."])
    ambiente["agora"] += timedelta(minutes=30)
    assert monitor.main() == 0
    assert ambiente["envios"][1].startswith("Hearthstone DS: resumo da notícia\n\nNovidade que falha")
    assert ler("noticias/2026-10-23-77.json")["resumo_ia"]["topicos"]
    assert ler("estado.json")["resumos_pendentes"] == []



def test_falha_ao_gerar_de_novo_mantem_resumo_anterior(ambiente, monkeypatch):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    assert monitor.main() == 0
    arquivo = ler("estado.json")["pendentes"][0]["arquivo"]
    anterior = ler(arquivo)["resumo_ia"]
    assert anterior["topicos"]

    def falhar(*_args, **_kwargs):
        raise resumo_ia.ErroResumo("limite de uso atingido")

    monkeypatch.setattr(resumo_ia, "gerar", falhar)
    nova_build(ambiente)
    assert monitor.main() == 0
    assert ler(arquivo)["resumo_ia"] == anterior
    assert ler("estado.json")["resumos_pendentes"] == []
    assert ambiente["envios"][1].startswith("Hearthstone DS: cartas alteradas no patch 36.6")
    assert "Resumo gerado por IA" in ambiente["envios"][1]


def test_noticia_sem_texto_continua_valida():
    bruto = json.dumps({"blogList": [{"id": 1, "title": "Notas do patch 36.6", "summary": "Resumo.", "content": None, "publish": 1792771200000}]}).encode()
    noticia = blizzard.noticias(bruto, "pt-br")[0]
    assert noticia.texto == ""


def test_patch_gravado_com_regra_antiga_de_texto_e_regravado(ambiente):
    assert monitor.main() == 0
    patch = {
        "versao": "37.0",
        "data": "2026-10-12",
        "build": 1,
        "noticia": None,
        "noticia_en": None,
        "cartas": {"buffs": [], "nerfs": [], "alteradas": [
            {"dbfId": 1, "nome": "Só pontuação", "classe": "MAGE", "mudancas": [{"campo": "texto", "antes": "<b>Provocar</b>\nCompre", "depois": "<b>Provocar</b>. Compre"}]},
            {"dbfId": 2, "nome": "Reescrita", "classe": "MAGE", "mudancas": [{"campo": "texto", "antes": "Compre um card.", "depois": "Compre o card."}]},
        ]},
        "retroativo": True,
    }
    indice = {"patches": [{"arquivo": "patches/2026-10-12-37.0.json", "versao": "37.0", "data": "2026-10-12", "buffs": 0, "nerfs": 0, "alteradas": 2}]}
    gravacao.gravar({Path("dados/patches/2026-10-12-37.0.json"): patch, Path("dados/indice.json"): indice})
    assert monitor.main() == 0
    regravado = ler("patches/2026-10-12-37.0.json")
    assert regravado["cartas"]["alteradas"] == []
    assert [carta["nome"] for carta in regravado["cartas"]["revisadas"]] == ["Reescrita"]
    assert regravado["retroativo"] is True
    assert ler("indice.json")["patches"][0]["alteradas"] == 0
    assert ler("indice.json")["patches"][0]["revisadas"] == 1
    assert ambiente["envios"] == []
    antes = arquivos()
    assert monitor.main() == 0
    assert arquivos() == antes


def gravar_formatos(ids):
    # A carta 1 do Padrão mais um bloco de ids distantes, para passar do mínimo que valida o arquivo.
    gravacao.gravar({Path("dados/formatos.json"): {"padrao": sorted(set(ids) | set(range(1000, 1400)))}})


def test_diff_novo_ganha_formato_quando_a_lista_do_padrao_existe(ambiente):
    assert monitor.main() == 0
    gravar_formatos([1])
    noticia_pt(ambiente)
    nova_build(ambiente)
    assert monitor.main() == 0
    cartas = ler("patches/2026-10-23-36.6.json")["cartas"]
    formatos = {carta["dbfId"]: carta["formato"] for grupo in cartas.values() for carta in grupo}
    assert formatos == {1: "padrao", 2: "livre"}
    texto = ambiente["envios"][0]
    assert "Padrão\n\n" in texto and "Livre\n\n" in texto


def test_patch_gravado_sem_formato_e_regravado_quando_a_lista_do_padrao_aparece(ambiente):
    assert monitor.main() == 0
    noticia_pt(ambiente)
    nova_build(ambiente)
    assert monitor.main() == 0
    arquivo = "patches/2026-10-23-36.6.json"
    assert all("formato" not in carta for grupo in ler(arquivo)["cartas"].values() for carta in grupo)
    envios = len(ambiente["envios"])
    gravar_formatos([1])
    assert monitor.main() == 0
    formatos = {carta["dbfId"]: carta["formato"] for grupo in ler(arquivo)["cartas"].values() for carta in grupo}
    assert formatos == {1: "padrao", 2: "livre"}
    assert len(ambiente["envios"]) == envios
    antes = arquivos()
    assert monitor.main() == 0
    assert arquivos() == antes


def test_patch_grava_o_modelo_reserva_que_respondeu(ambiente, monkeypatch):
    def gerar(*args, **kwargs):
        topicos = resumo_ia.Topicos(["Arena recebe ajustes.", "Novo evento chega.", "Bugs importantes corrigidos."])
        topicos.modelo = resumo_ia.MODELOS_RESERVA[0]
        return topicos

    monkeypatch.setattr(resumo_ia, "gerar", gerar)
    assert monitor.main() == 0
    noticia_pt(ambiente)
    nova_build(ambiente)
    assert monitor.main() == 0
    assert ler("patches/2026-10-23-36.6.json")["resumo_ia"]["modelo"] == resumo_ia.MODELOS_RESERVA[0]
