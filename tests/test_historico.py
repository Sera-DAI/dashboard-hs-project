import json
from pathlib import Path

from hsds import blizzard, formatador, historico, http, resumo_ia

DADOS = Path(__file__).parent / "dados"


def noticia(id=24319999, publicada="2026-10-24T17:00:00Z", titulo="Notícias fictícias"):
    return blizzard.Noticia(id, titulo, f"https://exemplo.invalid/{id}", "Resumo oficial.", publicada, None, "Texto fictício para resumo.")


def test_historico_paginado_vazio_nao_faz_requisicao(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "historico.json").write_text(json.dumps({"corte": historico.CORTE, "paginado": True, "fila": [], "builds": {}}), encoding="utf-8")
    monkeypatch.setattr(http, "baixar", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("houve requisição")))
    assert historico.main(dormir=lambda _: None) == 0


def test_para_na_primeira_pagina_que_passou_do_corte(monkeypatch, tmp_path):
    chamadas = []
    pagina = [noticia(publicada="2026-04-24T17:00:00Z"), noticia(id=24320000, publicada="2026-04-26T17:00:00Z")]
    monkeypatch.setattr(historico, "_ler_pagina", lambda numero, ultimo, dormir: chamadas.append(numero) or pagina)
    estado = {"corte": historico.CORTE, "paginado": False, "fila": [], "builds": {}}
    encontrados, novos, _ = historico._itens_para_processar(
        estado, tmp_path, {"patches": []}, {"noticias": set()}, lambda _: None, frozenset({24319999, 24320000})
    )
    assert chamadas == [1]
    assert estado["paginado"] is True
    assert [item.id for item in novos] == [24320000]


def test_notícia_de_patch_ja_presente_no_indice_nao_volta_para_a_fila(tmp_path):
    (tmp_path / "patches").mkdir()
    (tmp_path / "patches" / "gravado.json").write_text(
        json.dumps({"noticia": {"id": 24319999}, "noticia_en": None}),
        encoding="utf-8",
    )
    assert historico._ja_gravada(
        noticia(titulo="Notas do patch 36.6"),
        tmp_path,
        {"patches": [{"arquivo": "patches/gravado.json"}]},
        {"noticias": set()},
    )


def test_build_da_nota_usa_data_gerada_antes_da_publicacao():
    builds = [(100, "2026-10-10"), (200, "2026-10-15"), (300, "2026-10-23")]
    assert historico._build_ate(builds, "2026-10-23") == 300
    assert historico._build_ate(builds, "2026-10-14") == 200


def test_patch_usa_par_de_builds_e_remove_summary_do_arquivo(monkeypatch):
    respostas = {
        100: (DADOS / "cartas-antes.json").read_bytes(),
        200: (DADOS / "cartas-depois.json").read_bytes(),
    }
    monkeypatch.setattr(http, "baixar", lambda url: respostas[int(url.split("/v1/")[1].split("/")[0])])
    cache = {}
    patch = historico._gravar_patch(
        noticia(titulo="Notas do patch 36.6"),
        {"data": "2026-10-10T12:00:00Z"},
        [(100, "2026-10-10"), (200, "2026-10-15")],
        cache,
        [None],
        lambda _: None,
    )
    assert patch["build"] == 200
    assert patch["cartas"]["buffs"][0]["dbfId"] == 1
    assert "resumo" not in patch["noticia"]
    assert patch["retroativo"] is True


def test_patch_sem_par_de_builds_fica_sem_cartas():
    patch = historico._gravar_patch(noticia(titulo="Notas do patch 36.6"), None, [(100, "2026-10-10")], {}, [None], lambda _: None)
    assert patch["build"] is None
    assert patch["cartas"] is None


def test_http_le_last_modified_por_head():
    chamadas = []

    class Cabecalhos(dict):
        pass

    def abrir(requisicao):
        chamadas.append(requisicao)
        return Cabecalhos({"Last-Modified": "Thu, 15 Oct 2026 00:00:00 GMT"})

    assert http.data_modificacao("https://api.hearthstonejson.com/v1/200/", abrir=abrir) == "2026-10-15"
    assert chamadas[0].get_method() == "HEAD"
    assert chamadas[0].get_header("User-agent") == http.AGENTE


def test_fixtures_de_pagina_e_listagem_sao_lidos_sem_rede(monkeypatch):
    pagina = blizzard.noticias((DADOS / "historico-pagina.json").read_bytes(), "pt-br")
    assert pagina[0].id == 24319999
    chamadas = []
    monkeypatch.setattr(http, "baixar", lambda url: (chamadas.append(url), (DADOS / "historico-builds.html").read_bytes())[1])
    monkeypatch.setattr(http, "data_modificacao", lambda url, abrir: {"100": "2026-10-01", "200": "2026-10-02", "300": "2026-10-03"}[url.split("/v1/")[1].split("/")[0]])
    estado = {"builds": {}}
    builds = historico._builds([None], lambda _: None, estado)
    assert builds == [(100, "2026-10-01"), (200, "2026-10-02"), (300, "2026-10-03")]
    assert chamadas == [historico.LISTAGEM]


def test_fila_vazia_de_resumos_continua_pendente_apos_falha(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    pasta = tmp_path / "dados"
    pasta.mkdir()
    arquivo = "noticias/2026-10-24-24319999.json"
    (pasta / "noticias").mkdir()
    registro = {"id": 24319999, "titulo": "Notícias fictícias", "link": "https://exemplo.invalid/24319999", "publicada": "2026-10-24T17:00:00Z", "retroativo": True, "resumo_ia": None}
    (pasta / arquivo).write_text(json.dumps(registro), encoding="utf-8")
    estado = {"corte": historico.CORTE, "paginado": True, "fila": [{"arquivo": arquivo, "id": 24319999}], "builds": {}}
    (pasta / "historico.json").write_text(json.dumps(estado), encoding="utf-8")
    (pasta / "noticias.json").write_text('{"noticias": []}', encoding="utf-8")
    monkeypatch.setattr(historico, "_ler_pagina", lambda *args: [noticia()])
    monkeypatch.setattr(historico, "_resumo", lambda *args: None)
    monkeypatch.setattr(historico, "_enviar", lambda texto: None)
    assert historico.main(pasta, dormir=lambda _: None) == 0
    atualizado = json.loads((pasta / "historico.json").read_text(encoding="utf-8"))
    assert atualizado["fila"] == [{"arquivo": arquivo, "id": 24319999, "tentativas": 1}]
    assert json.loads((pasta / arquivo).read_text(encoding="utf-8"))["resumo_ia"] is None


def test_limita_a_dez_chamadas_e_mantem_o_resto_da_fila(monkeypatch, tmp_path):
    pasta = tmp_path / "dados"
    (pasta / "noticias").mkdir(parents=True)
    fila = []
    encontrados = {}
    for identificador in range(24320000, 24320012):
        arquivo = f"noticias/2026-10-24-{identificador}.json"
        registro = {"id": identificador, "titulo": "Notícia fictícia", "publicada": "2026-10-24T17:00:00Z", "resumo_ia": None}
        (pasta / arquivo).write_text(json.dumps(registro), encoding="utf-8")
        fila.append({"arquivo": arquivo, "id": identificador})
        encontrados[identificador] = noticia(identificador)
    (pasta / "historico.json").write_text(json.dumps({"corte": historico.CORTE, "paginado": True, "fila": fila, "builds": {}}), encoding="utf-8")
    monkeypatch.setattr(historico, "_itens_para_processar", lambda *args: (encontrados, [], [None]))
    chamadas = []
    monkeypatch.setattr(historico, "_resumo", lambda *args: chamadas.append(args[0].id) or {"topicos": ["Resumo"]})
    monkeypatch.setattr(historico, "_enviar", lambda texto: None)
    assert historico.main(pasta, dormir=lambda _: None) == 0
    assert len(chamadas) == 10
    estado = json.loads((pasta / "historico.json").read_text(encoding="utf-8"))
    assert len(estado["fila"]) == 2


def test_mensagem_de_fim_de_lote_com_itens_e_completa():
    assert formatador.historico(2, 1, 10, 3, False, historico.CORTE) == [
        "Hearthstone DS: histórico antigo\n\n3 itens gravados neste lote (2 patches e 1 notícias)\n"
        "10 resumos por IA feitos; faltam 3.\n\nhttps://dashboard-hs.pages.dev"
    ]
    assert formatador.historico(0, 0, 2, 0, True, historico.CORTE) == [
        "Hearthstone DS: histórico antigo\n\nHistórico completo desde 25/04/2026.\n\nhttps://dashboard-hs.pages.dev"
    ]


def test_mensagem_de_fim_de_lote_so_com_resumos_nao_tem_linha_de_itens():
    assert formatador.historico(0, 0, 4, 6, False, historico.CORTE) == [
        "Hearthstone DS: histórico antigo\n\n4 resumos por IA feitos; faltam 6.\n\nhttps://dashboard-hs.pages.dev"
    ]


def test_primeira_pagina_deixa_para_o_monitor_o_que_ele_ainda_nao_viu(monkeypatch, tmp_path):
    pagina = [noticia(id=24320001, publicada="2026-10-25T09:30:00Z"), noticia(id=24320000, publicada="2026-10-20T17:00:00Z"), noticia(id=1, publicada="2026-04-01T17:00:00Z")]
    monkeypatch.setattr(historico, "_ler_pagina", lambda numero, ultimo, dormir: pagina)
    estado = {"corte": historico.CORTE, "paginado": False, "fila": [], "builds": {}}
    _, novos, _ = historico._itens_para_processar(estado, tmp_path, {"patches": []}, {"noticias": set()}, lambda _: None, frozenset({24320000}))
    assert [item.id for item in novos] == [24320000]


def test_builds_param_na_primeira_anterior_ao_corte_e_usam_o_arquivo_de_cartas(monkeypatch):
    monkeypatch.setattr(http, "baixar", lambda url: b'<a href="/v1/100/">100</a><a href="/v1/200/">200</a><a href="/v1/300/">300</a><a href="/v1/400/">400</a>')
    consultadas = []
    datas = {"100": "2026-01-01", "200": "2026-04-01", "300": "2026-06-01", "400": "2026-10-15"}

    def data_modificacao(url, abrir):
        consultadas.append(url)
        return datas[url.split("/v1/")[1].split("/")[0]]

    monkeypatch.setattr(http, "data_modificacao", data_modificacao)
    builds = historico._builds([None], lambda _: None, {"builds": {}})
    assert builds == [(200, "2026-04-01"), (300, "2026-06-01"), (400, "2026-10-15")]
    assert consultadas[0] == historico.CARTAS.format(build=400)


def _pasta_com_fila(tmp_path, tentativas):
    pasta = tmp_path / "dados"
    (pasta / "noticias").mkdir(parents=True)
    arquivo = "noticias/2026-10-24-24319999.json"
    (pasta / arquivo).write_text(json.dumps({"id": 24319999, "titulo": "Notícias fictícias", "publicada": "2026-10-24T17:00:00Z", "retroativo": True, "resumo_ia": None}), encoding="utf-8")
    item = {"arquivo": arquivo, "id": 24319999, "tentativas": tentativas}
    (pasta / "historico.json").write_text(json.dumps({"corte": historico.CORTE, "paginado": True, "fila": [item], "builds": {}}), encoding="utf-8")
    return pasta


def test_item_sai_da_fila_depois_do_limite_de_tentativas(monkeypatch, tmp_path):
    pasta = _pasta_com_fila(tmp_path, historico.LIMITE_TENTATIVAS - 1)
    monkeypatch.setattr(historico, "_ler_pagina", lambda *args: [noticia()])
    monkeypatch.setattr(historico, "_resumo", lambda *args: None)
    mensagens = []
    monkeypatch.setattr(historico, "_enviar", mensagens.append)
    assert historico.main(pasta, dormir=lambda _: None) == 0
    assert json.loads((pasta / "historico.json").read_text(encoding="utf-8"))["fila"] == []


def test_noticia_sem_texto_sai_da_fila_sem_chamar_o_gemini(monkeypatch, tmp_path):
    pasta = _pasta_com_fila(tmp_path, 0)
    sem_texto = blizzard.Noticia(24319999, "Notícias fictícias", "https://exemplo.invalid/24319999", "Resumo.", "2026-10-24T17:00:00Z", None, "")
    monkeypatch.setattr(historico, "_ler_pagina", lambda *args: [sem_texto])
    monkeypatch.setattr(historico, "_resumo", lambda *args: (_ for _ in ()).throw(AssertionError("chamou o Gemini")))
    monkeypatch.setattr(historico, "_enviar", lambda textos: None)
    assert historico.main(pasta, dormir=lambda _: None) == 0
    assert json.loads((pasta / "historico.json").read_text(encoding="utf-8"))["fila"] == []


def test_falha_de_fonte_avisa_e_nao_grava_nada(monkeypatch, tmp_path):
    pasta = tmp_path / "dados"
    pasta.mkdir()

    def falhar(*args):
        raise http.ErroFonte("blizzard", "site fora do ar ou sem resposta")

    monkeypatch.setattr(historico, "_ler_pagina", falhar)
    enviados = []
    monkeypatch.setattr(historico.telegram, "enviar_mensagem", lambda token, chat, texto: enviados.append(texto))
    assert historico.main(pasta, dormir=lambda _: None) == 1
    assert len(enviados) == 1 and isinstance(enviados[0], str)
    assert "falhou" in enviados[0]
    assert list(pasta.iterdir()) == []


def test_fim_de_lote_manda_texto_e_nao_lista_ao_telegram(monkeypatch, tmp_path):
    pasta = _pasta_com_fila(tmp_path, 0)
    monkeypatch.setattr(historico, "_ler_pagina", lambda *args: [noticia()])
    monkeypatch.setattr(historico, "_resumo", lambda *args: {"topicos": ["📰 Notícia: resumo."], "modelo": "m", "gerado": "2026-10-25T00:00:00Z"})
    enviados = []
    monkeypatch.setattr(historico.telegram, "enviar_mensagem", lambda token, chat, texto: enviados.append(texto))
    assert historico.main(pasta, dormir=lambda _: None) == 0
    assert len(enviados) == 1 and isinstance(enviados[0], str)
    assert "Histórico completo desde 25/04/2026." in enviados[0]


def test_resumo_do_historico_guarda_o_modelo_reserva(monkeypatch):
    def gerar(*args, **kwargs):
        topicos = resumo_ia.Topicos(["Resumo um.", "Resumo dois.", "Resumo três."])
        topicos.modelo = resumo_ia.MODELOS_RESERVA[1]
        return topicos

    monkeypatch.setattr(resumo_ia, "gerar", gerar)
    noticia = type("Noticia", (), {"texto": "Texto.", "titulo": "Título"})()
    resumo = historico._resumo(noticia, {"cartas": None}, False, "chave")
    assert resumo["modelo"] == resumo_ia.MODELOS_RESERVA[1]
    assert resumo["topicos"] == ["Resumo um.", "Resumo dois.", "Resumo três."]
    json.dumps(resumo)
