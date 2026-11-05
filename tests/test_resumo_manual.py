import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hsds import resumo_ia, resumo_manual

PATCH = "patches/2026-11-03-37.0.2.json"
TEXTO = "A Blizzard ajustou várias cartas do Padrão e do Livre neste patch e também mexeu na Arena."
TOPICOS = ["⚔️ Arena: ajustes pontuais no modo.", "🃏 Cartas: várias cartas mudaram de força.", "🛠️ Livre: o modo também recebeu mudanças."]


def lista(identificador, titulo, conteudo):
    return json.dumps({"blogList": [{"id": identificador, "title": titulo, "summary": "r", "content": conteudo, "publish": 1792774800000, "defaultUrl": f"https://hearthstone.blizzard.com/pt-br/news/{identificador}"}]}).encode()


def baixador(pt=None, en=None):
    def baixar(url, **kwargs):
        resposta = pt if "/pt-br/" in url else en
        if resposta is None:
            raise resumo_manual.ErroFonte("blizzard", "site fora do ar ou sem resposta")
        return resposta

    return baixar


@pytest.fixture(autouse=True)
def sem_pausa(monkeypatch):
    monkeypatch.setattr(resumo_manual, "INTERVALO", 0)
    monkeypatch.setattr(resumo_manual, "_ULTIMA_REQUISICAO", [None])


ESTADO = {"build": 1, "noticias_vistas": [], "pendentes": [], "falhas": {}}


@pytest.fixture
def raiz(tmp_path):
    pasta = tmp_path / "dados"
    (pasta / "patches").mkdir(parents=True)
    patch = {
        "versao": "37.0.2",
        "noticia": {"id": 24307311, "titulo": "Notas do patch 37.0.2", "link": "https://hearthstone.blizzard.com/pt-br/news/24307311"},
        "noticia_en": None,
        "cartas": {"buffs": [{"nome": "Isiset", "formato": "padrao", "mudancas": [{"campo": "custo"}]}], "nerfs": [], "alteradas": [], "revisadas": []},
        "resumo_ia": None,
    }
    (pasta / PATCH).write_text(json.dumps(patch), encoding="utf-8")
    (pasta / "estado.json").write_text(json.dumps(ESTADO), encoding="utf-8")
    return pasta


def test_pedido_usa_a_instrucao_e_a_mensagem_do_modulo(raiz):
    instrucao, mensagem = resumo_manual.pedido(raiz, PATCH, baixador(pt=lista(24307311, "Notas do patch 37.0.2", f"<p>{TEXTO}</p>")))
    assert instrucao == resumo_ia.INSTRUCAO
    assert mensagem.startswith("Notícia oficial (português): Notas do patch 37.0.2\n\n" + TEXTO)
    assert "Padrão, Buffs: Isiset (custo)" in mensagem


def test_pedido_cai_para_o_texto_em_ingles_quando_o_pt_vem_sem_conteudo(raiz):
    pt = lista(24307311, "Notas do patch 37.0.2", "")
    en = lista(24307311, "37.0.2 Patch Notes", "<p>English body.</p>").replace(b"/pt-br/", b"/en-us/")
    _, mensagem = resumo_manual.pedido(raiz, PATCH, baixador(pt=pt, en=en))
    assert mensagem.startswith("Notícia oficial (inglês): 37.0.2 Patch Notes")


def test_pedido_sem_texto_em_nenhuma_lingua_falha(raiz):
    sem_texto = lista(24307311, "Notas", "")
    with pytest.raises(resumo_manual.ErroManual, match="páginas lidas"):
        resumo_manual.pedido(raiz, PATCH, baixador(pt=sem_texto, en=sem_texto))


@pytest.mark.parametrize("arquivo", ["../estado.json", "patches/../estado.json", "dados/x.json", "patches/a b.json", "/etc/passwd", "patches/x.json/../../y.json"])
def test_nome_de_arquivo_fora_do_padrao_e_recusado(raiz, arquivo):
    with pytest.raises(resumo_manual.ErroManual, match="arquivo inválido"):
        resumo_manual.pedido(raiz, arquivo, baixador())


def test_topicos_aceitam_linhas_barras_e_marcadores():
    assert resumo_manual.topicos_do_texto("- um\n2. dois | • três\n\n  ") == ["um", "dois", "três"]


def test_gravar_valida_grava_e_nao_mexe_no_estado(raiz):
    baixar = baixador(pt=lista(24307311, "Notas do patch 37.0.2", TEXTO))
    agora = datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc)
    gravados = resumo_manual.gravar(raiz, PATCH, " | ".join(TOPICOS), agora, baixar)
    assert gravados == TOPICOS
    patch = json.loads((raiz / PATCH).read_text(encoding="utf-8"))
    assert patch["resumo_ia"] == {"topicos": TOPICOS, "modelo": "manual", "gerado": "2026-11-05T06:00:00Z"}
    assert patch["cartas"]["buffs"][0]["nome"] == "Isiset"
    assert json.loads((raiz / "estado.json").read_text(encoding="utf-8")) == ESTADO


@pytest.mark.parametrize("bruto", ["um | dois", "<b>a</b> | b | c", "veja http://x.com | b | c"])
def test_gravar_recusa_resumo_invalido_sem_alterar_arquivos(raiz, bruto):
    antes = {p: p.read_bytes() for p in raiz.rglob("*.json")}
    with pytest.raises(resumo_ia.ErroResumo):
        resumo_manual.gravar(raiz, PATCH, bruto, baixar=baixador(pt=lista(24307311, "N", TEXTO)))
    assert {p: p.read_bytes() for p in raiz.rglob("*.json")} == antes


def test_gravar_recusa_resumo_que_copia_a_noticia(raiz):
    copia = [TEXTO, TEXTO + " Mais uma.", TEXTO + " Outra."]
    with pytest.raises(resumo_ia.ErroResumo, match="copiou"):
        resumo_manual.gravar(raiz, PATCH, "\n".join(copia), baixar=baixador(pt=lista(24307311, "N", TEXTO)))


def test_gravar_sem_reler_a_noticia_recusa_e_nao_altera_arquivos(raiz):
    antes = {p: p.read_bytes() for p in raiz.rglob("*.json")}

    def baixar(url, **kwargs):
        raise resumo_manual.ErroFonte("blizzard", "site fora do ar ou sem resposta")

    with pytest.raises(resumo_manual.ErroManual, match="páginas lidas"):
        resumo_manual.gravar(raiz, PATCH, "\n".join(TOPICOS), baixar=baixar)
    assert {p: p.read_bytes() for p in raiz.rglob("*.json")} == antes


def test_gravar_substitui_resumo_existente_e_avisa(raiz, capsys):
    caminho = raiz / PATCH
    patch = json.loads(caminho.read_text(encoding="utf-8"))
    patch["resumo_ia"] = {"topicos": ["antigo"], "modelo": "m", "gerado": "x"}
    caminho.write_text(json.dumps(patch), encoding="utf-8")
    resumo_manual.gravar(raiz, PATCH, "\n".join(TOPICOS), baixar=baixador(pt=lista(24307311, "N", TEXTO)))
    assert "será substituído" in capsys.readouterr().out
    assert json.loads(caminho.read_text(encoding="utf-8"))["resumo_ia"]["topicos"] == TOPICOS


def test_noticia_avulsa_usa_o_proprio_id_e_nao_envia_cartas(raiz):
    (raiz / "noticias").mkdir()
    (raiz / "noticias/2026-10-02-24307307.json").write_text(json.dumps({"id": 24307307, "titulo": "Evento", "resumo_ia": None}), encoding="utf-8")
    _, mensagem = resumo_manual.pedido(raiz, "noticias/2026-10-02-24307307.json", baixador(pt=lista(24307307, "Evento", TEXTO)))
    assert "Cartas alteradas" not in mensagem


def test_registro_inexistente_ou_sem_noticia_associada(raiz):
    with pytest.raises(resumo_manual.ErroManual, match="não existe"):
        resumo_manual.pedido(raiz, "patches/nao-existe.json", baixador())
    (raiz / "patches/sem.json").write_text(json.dumps({"versao": "1", "noticia": None, "noticia_en": None}), encoding="utf-8")
    with pytest.raises(resumo_manual.ErroManual, match="notícia da Blizzard associada"):
        resumo_manual.pedido(raiz, "patches/sem.json", baixador())


def test_nome_com_quebra_de_linha_no_fim_e_recusado(raiz):
    with pytest.raises(resumo_manual.ErroManual, match="arquivo inválido"):
        resumo_manual.pedido(raiz, PATCH + "\n", baixador())


def test_main_sem_arquivo_escolhe_o_primeiro_e_imprime_o_pedido(raiz, monkeypatch, capsys):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "preparar")
    monkeypatch.setenv("ARQUIVO", "")
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas do patch 37.0.2", TEXTO)))
    assert resumo_manual.main() == 0
    saida = capsys.readouterr().out
    assert f"Escolhido {PATCH}" in saida
    assert "::stop-commands::" in saida
    assert "=== COLE ISTO NO ASSISTENTE ===" in saida
    assert TEXTO in saida


def test_pedido_impresso_fica_entre_as_marcas_do_stop_commands_e_no_resumo_do_job(raiz, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    resumo_job = tmp_path / "resumo.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumo_job))
    monkeypatch.setenv("ACAO", "preparar")
    monkeypatch.setenv("ARQUIVO", PATCH)
    perigosa = TEXTO + " ``````````` fim"
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas", perigosa)))
    assert resumo_manual.main() == 0
    linhas = capsys.readouterr().out.splitlines()
    inicio = next(i for i, linha in enumerate(linhas) if linha.startswith("::stop-commands::"))
    marca = linhas[inicio].split("::")[2]
    fim = linhas.index(f"::{marca}::")
    assert inicio < linhas.index("=== COLE ISTO NO ASSISTENTE ===") < linhas.index("=== FIM DO PEDIDO ===") < fim
    gravado = resumo_job.read_text(encoding="utf-8")
    assert gravado.startswith("## Pedido de resumo\n\n" + "`" * 12 + "text\n")


def test_main_gravar_com_arquivo_grava_e_sai_com_zero(raiz, monkeypatch, capsys):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "gravar")
    monkeypatch.setenv("ARQUIVO", PATCH)
    monkeypatch.setenv("TOPICOS", " | ".join(TOPICOS))
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas", TEXTO)))
    assert resumo_manual.main() == 0
    assert "3 tópicos" in capsys.readouterr().out
    assert json.loads((raiz / PATCH).read_text(encoding="utf-8"))["resumo_ia"]["modelo"] == "manual"


def test_main_recusa_resumo_invalido_com_codigo_um(raiz, monkeypatch, capsys):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "gravar")
    monkeypatch.setenv("ARQUIVO", PATCH)
    monkeypatch.setenv("TOPICOS", "só um")
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas", TEXTO)))
    assert resumo_manual.main() == 1
    assert "recusado: resposta inválida" in capsys.readouterr().out


def test_main_escolhe_o_primeiro_sem_resumo_que_esta_na_lista(raiz, monkeypatch, capsys):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "preparar")
    monkeypatch.setenv("ARQUIVO", "")
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas do patch 37.0.2", TEXTO)))
    assert resumo_manual.main() == 0
    saida = capsys.readouterr().out
    assert f"Escolhido {PATCH}" in saida and "=== COLE ISTO NO ASSISTENTE ===" in saida


def test_main_sem_nada_na_lista_avisa_com_notice_e_sai_com_zero(raiz, monkeypatch, capsys):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "preparar")
    monkeypatch.setenv("ARQUIVO", "")
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(1, "Outra", TEXTO)))
    assert resumo_manual.main() == 0
    saida = capsys.readouterr().out
    assert "::notice::Nenhum patch ou notícia da expansão atual" in saida and "nada a preparar" in saida
    assert "COLE ISTO" not in saida


def test_main_gravar_exige_arquivo(raiz, monkeypatch):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "gravar")
    monkeypatch.setenv("ARQUIVO", "")
    monkeypatch.setenv("TOPICOS", "a | b | c")
    assert resumo_manual.main() == 1


def test_main_acao_desconhecida(raiz, monkeypatch):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "apagar")
    monkeypatch.setenv("ARQUIVO", PATCH)
    assert resumo_manual.main() == 1


def test_gravar_marca_o_escritor_no_modelo(raiz):
    baixar = baixador(pt=lista(24307311, "Notas do patch 37.0.2", TEXTO))
    resumo_manual.gravar(raiz, PATCH, " | ".join(TOPICOS), baixar=baixar, escritor="gemini")
    assert json.loads((raiz / PATCH).read_text(encoding="utf-8"))["resumo_ia"]["modelo"] == "manual-gemini"


def test_escritor_desconhecido_e_recusado_sem_alterar_arquivos(raiz):
    antes = {p: p.read_bytes() for p in raiz.rglob("*.json")}
    with pytest.raises(resumo_manual.ErroManual, match="escritor"):
        resumo_manual.gravar(raiz, PATCH, " | ".join(TOPICOS), baixar=baixador(pt=lista(24307311, "N", TEXTO)), escritor="x")
    assert {p: p.read_bytes() for p in raiz.rglob("*.json")} == antes


def test_pedido_impresso_pede_uma_linha_com_barras(raiz, capsys):
    resumo_manual._imprimir_pedido(PATCH, "INSTRUCAO", "MENSAGEM")
    saida = capsys.readouterr().out
    assert "todos em uma única linha" in saida and "separados por ' | '" in saida and "bloco de código" in saida
    assert f"arquivo={PATCH}, escritor=gemini (ou o que escreveu)" in saida


def test_topicos_tiram_as_cercas_do_bloco_de_codigo():
    bruto = "```text\n" + " | ".join(TOPICOS) + "\n```"
    assert resumo_manual.topicos_do_texto(bruto) == TOPICOS
    assert resumo_manual.topicos_do_texto("```" + " | ".join(TOPICOS) + "```") == TOPICOS


@pytest.mark.parametrize("escritor,modelo", [(" Gemini ", "manual-gemini"), ("claude", "manual-claude"), ("outro", "manual-outro"), ("", "manual")])
def test_modelo_do_escritor(escritor, modelo):
    assert resumo_manual.modelo_do_escritor(escritor) == modelo


def test_main_le_o_escritor_da_variavel_de_ambiente(raiz, monkeypatch, capsys):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "gravar")
    monkeypatch.setenv("ARQUIVO", PATCH)
    monkeypatch.setenv("TOPICOS", " | ".join(TOPICOS))
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas", TEXTO)))
    monkeypatch.setenv("ESCRITOR", "x")
    assert resumo_manual.main() == 1
    monkeypatch.setenv("ESCRITOR", "claude")
    assert resumo_manual.main() == 0
    assert json.loads((raiz / PATCH).read_text(encoding="utf-8"))["resumo_ia"]["modelo"] == "manual-claude"


def test_blizzard_fora_do_ar_nao_vira_nada_disponivel(raiz, monkeypatch, capsys):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "preparar")
    monkeypatch.setenv("ARQUIVO", "")
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador())
    assert resumo_manual.main() == 1
    saida = capsys.readouterr().out
    assert "não respondeu" in saida and "::notice::" not in saida


def test_proximo_pula_registro_malformado(raiz):
    (raiz / "patches/quebrado.json").write_text(json.dumps({"versao": "1", "noticia": "texto"}), encoding="utf-8")
    ids = json.dumps({"blogList": [{"id": 24307311, "title": "t", "summary": "r", "content": TEXTO, "publish": 1792774800000, "defaultUrl": "https://hearthstone.blizzard.com/pt-br/news/24307311"}]}).encode()
    assert resumo_manual.proximo_disponivel(raiz, baixador(pt=ids)) == PATCH


def lista_com(*ids, idioma="pt-br"):
    return json.dumps({"blogList": [{"id": i, "title": "t", "summary": "r", "content": TEXTO, "publish": 1792774800000, "defaultUrl": f"https://hearthstone.blizzard.com/{idioma}/news/{i}"} for i in ids]}).encode()


def noticia(raiz, nome, identificador, resumido=False):
    (raiz / "noticias").mkdir(exist_ok=True)
    resumo = {"topicos": ["a", "b", "c"], "modelo": "m", "gerado": "x"} if resumido else None
    (raiz / f"noticias/{nome}.json").write_text(json.dumps({"id": identificador, "titulo": "t", "resumo_ia": resumo}), encoding="utf-8")


def patch_ja_resumido(raiz):
    patch = json.loads((raiz / PATCH).read_text(encoding="utf-8"))
    patch["resumo_ia"] = {"topicos": ["a", "b", "c"], "modelo": "m", "gerado": "x"}
    (raiz / PATCH).write_text(json.dumps(patch), encoding="utf-8")


def test_proximo_pula_o_que_esta_fora_da_lista_e_escolhe_o_mais_novo_dos_demais(raiz):
    patch_ja_resumido(raiz)
    noticia(raiz, "2026-10-25-24300003", 24300003)  # mais novo, mas fora da lista: tem de ser pulado
    noticia(raiz, "2026-10-26-24300002", 24300002, resumido=True)  # na lista, mas já resumido
    noticia(raiz, "2026-10-20-24300001", 24300001)  # o esperado
    noticia(raiz, "2026-09-14-24200001", 24200001)  # mais antigo, também na lista: só vem depois
    ids = lista_com(24300001, 24300002, 24200001, 24307311)
    assert resumo_manual.proximo_disponivel(raiz, baixador(pt=ids)) == "noticias/2026-10-20-24300001.json"


def test_proximo_com_so_o_pt_br_fora_do_ar_usa_a_lista_em_ingles(raiz):
    assert resumo_manual.proximo_disponivel(raiz, baixador(en=lista_com(24307311, idioma="en-us"))) == PATCH


def pagina_da_lista(url):
    return int(url.split("page=")[1].split("&")[0])


def lista_em(itens):
    """itens: (id, publicada em segundos). Texto fixo, link pt-BR."""
    return json.dumps({"blogList": [{"id": i, "title": "t", "summary": "r", "content": TEXTO, "publish": segundos * 1000, "defaultUrl": f"https://hearthstone.blizzard.com/pt-br/news/{i}"} for i, segundos in itens]}).encode()


DIA = 86400
SET_20 = 1789862400  # 2026-09-20, depois do início da expansão
AGO_20 = 1787184000  # 2026-08-20, antes do início da expansão


def test_proximo_ignora_o_que_e_anterior_a_expansao_mesmo_estando_na_lista(raiz):
    patch_ja_resumido(raiz)
    noticia(raiz, "2026-08-20-24200009", 24200009)
    assert resumo_manual.proximo_disponivel(raiz, baixador(pt=lista_com(24200009, 24307311))) is None


def test_fonte_acha_a_noticia_em_pagina_mais_funda_e_para_de_paginar(raiz):
    pedidas = []

    def baixar(url, **kwargs):
        if "/en-us/" in url:
            raise resumo_manual.ErroFonte("blizzard", "fora")
        pedidas.append(pagina_da_lista(url))
        paginas = {1: lista_em([(1, SET_20 + 9 * DIA)]), 2: lista_em([(24300001, SET_20 + DIA)]), 3: lista_em([(3, SET_20)])}
        return paginas[pagina_da_lista(url)]

    noticia_achada = resumo_manual._fonte(24300001, baixar, "2026-09-12")
    assert noticia_achada.id == 24300001
    assert pedidas == [1, 2]


def test_paginacao_para_na_pagina_que_passa_da_data_de_inicio(raiz):
    pedidas = []

    def baixar(url, **kwargs):
        if "/en-us/" in url:
            raise resumo_manual.ErroFonte("blizzard", "fora")
        pedidas.append(pagina_da_lista(url))
        return lista_em([(pagina_da_lista(url), SET_20 - (pagina_da_lista(url) - 2) * 10 * DIA)])  # a partir da página 3 é anterior a 12/09

    ids = resumo_manual._ids_na_lista(baixar, "2026-09-12")
    assert pedidas == [1, 2, 3]
    assert ids == {1, 2, 3}


def test_paginacao_respeita_o_maximo_de_paginas(raiz):
    pedidas = []

    def baixar(url, **kwargs):
        if "/en-us/" in url:
            raise resumo_manual.ErroFonte("blizzard", "fora")
        pedidas.append(pagina_da_lista(url))
        return lista_em([(pagina_da_lista(url), SET_20 + 30 * DIA)])  # nunca passa da data de início

    resumo_manual._ids_na_lista(baixar, "2026-09-12")
    assert pedidas == [1, 2, 3, 4]


def test_falha_numa_pagina_funda_encerra_a_leitura_sem_erro(raiz):
    def baixar(url, **kwargs):
        if "/en-us/" in url or pagina_da_lista(url) > 1:
            raise resumo_manual.ErroFonte("blizzard", "fora")
        return lista_em([(7, SET_20 + 5 * DIA)])

    assert resumo_manual._ids_na_lista(baixar, "2026-09-12") == {7}


def test_ha_pausa_entre_quaisquer_duas_requisicoes_inclusive_entre_idiomas(monkeypatch):
    pausas = []
    relogio = [100.0]
    monkeypatch.setattr(resumo_manual, "INTERVALO", 2)
    monkeypatch.setattr(resumo_manual, "_ULTIMA_REQUISICAO", [None])
    monkeypatch.setattr(resumo_manual.time, "monotonic", lambda: relogio[0])
    monkeypatch.setattr(resumo_manual.time, "sleep", lambda segundos: (pausas.append(segundos), relogio.__setitem__(0, relogio[0] + segundos)))

    def baixar(url, **kwargs):
        return lista_em([(1, SET_20 + 30 * DIA)])  # nunca passa da data de início: lê as 4 páginas de cada idioma

    resumo_manual._ids_na_lista(baixar, "2026-09-12")
    assert len(pausas) == 2 * resumo_manual.MAX_PAGINAS - 1  # 8 requisições, 7 pausas (inclusive entre pt-BR e en-US)
    assert all(pausa == 2 for pausa in pausas)


SET_12 = 1789171200  # 2026-09-12 00:00 UTC
SET_11 = SET_12 - DIA


def lista_por_pagina(paginas):
    def baixar(url, **kwargs):
        if "/en-us/" in url:
            raise resumo_manual.ErroFonte("blizzard", "fora")
        return paginas.get(pagina_da_lista(url), lista_em([]))

    return baixar


def test_pagina_cuja_mais_antiga_e_do_dia_12_ainda_exige_a_seguinte():
    pedidas = []
    base = lista_por_pagina({1: lista_em([(1, SET_20), (2, SET_12)]), 2: lista_em([(3, SET_11)])})

    def baixar(url, **kwargs):
        pedidas.append(pagina_da_lista(url))
        return base(url)

    ids = resumo_manual._ids_na_lista(baixar, "2026-09-12")
    assert ids == {1, 2, 3} and pedidas[:2] == [1, 2]


def test_pagina_vazia_encerra_a_leitura_sem_erro():
    pedidas = []
    base = lista_por_pagina({1: lista_em([(1, SET_20 + 9 * DIA)])})

    def baixar(url, **kwargs):
        if "/pt-br/" in url:
            pedidas.append(pagina_da_lista(url))
        return base(url)

    assert resumo_manual._ids_na_lista(baixar, "2026-09-12") == {1}
    assert pedidas == [1, 2]


def test_falha_em_pagina_funda_avisa_com_warning(capsys):
    def baixar(url, **kwargs):
        if "/en-us/" in url or pagina_da_lista(url) > 1:
            raise resumo_manual.ErroFonte("blizzard", "fora")
        return lista_em([(7, SET_20 + 5 * DIA)])

    resumo_manual._ids_na_lista(baixar, "2026-09-12")
    assert "::warning::" in capsys.readouterr().out


def test_proximo_inclui_o_dia_12_e_exclui_o_dia_11(raiz):
    patch_ja_resumido(raiz)
    noticia(raiz, "2026-09-11-24200011", 24200011)
    noticia(raiz, "2026-09-12-24200012", 24200012)
    ids = lista_com(24200011, 24200012)
    assert resumo_manual.proximo_disponivel(raiz, baixador(pt=ids)) == "noticias/2026-09-12-24200012.json"
    (raiz / "noticias/2026-09-12-24200012.json").unlink()
    assert resumo_manual.proximo_disponivel(raiz, baixador(pt=ids)) is None


def test_proximo_acha_item_so_na_pagina_dois(raiz):
    patch_ja_resumido(raiz)
    noticia(raiz, "2026-09-15-24300015", 24300015)
    baixar = lista_por_pagina({1: lista_em([(1, SET_20 + 40 * DIA)]), 2: lista_em([(24300015, SET_20 - 5 * DIA)]), 3: lista_em([(2, SET_11)])})
    assert resumo_manual.proximo_disponivel(raiz, baixar) == "noticias/2026-09-15-24300015.json"


def test_pedido_e_gravar_leem_ate_a_pagina_dois_pela_data_do_arquivo(raiz):
    noticia(raiz, "2026-09-15-24300015", 24300015)
    baixar = lista_por_pagina({1: lista_em([(1, SET_20 + 40 * DIA)]), 2: lista_em([(24300015, SET_20 - 5 * DIA)])})
    arquivo = "noticias/2026-09-15-24300015.json"
    _, mensagem = resumo_manual.pedido(raiz, arquivo, baixar)
    assert TEXTO in mensagem
    assert resumo_manual.gravar(raiz, arquivo, " | ".join(TOPICOS), baixar=baixar) == TOPICOS


def test_main_sem_nada_menciona_a_data_de_inicio_e_as_paginas(raiz, monkeypatch, capsys):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "preparar")
    monkeypatch.setenv("ARQUIVO", "")
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista_com(1)))
    assert resumo_manual.main() == 0
    saida = capsys.readouterr().out
    assert resumo_manual.INICIO_EXPANSAO in saida and f"{resumo_manual.MAX_PAGINAS} primeiras páginas" in saida


def test_fila_antiga_no_estado_nao_muda_a_escolha(raiz):
    # D54: a ordem é só "o mais novo sem resumo da expansão atual"; dados/estado.json não é lido.
    noticia(raiz, "2026-09-14-24200001", 24200001)
    (raiz / "estado.json").write_text(json.dumps({**ESTADO, "resumos_pendentes": [{"arquivo": "noticias/2026-09-14-24200001.json", "desde": "x"}]}), encoding="utf-8")
    assert resumo_manual.proximo_disponivel(raiz, baixador(pt=lista_com(24307311, 24200001))) == PATCH


def ambiente_telegram(monkeypatch, falhar=False):
    monkeypatch.setenv("TELEGRAM_TOKEN", "token-ficticio")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "destino-ficticio")
    envios = []

    def enviar(token, chat_id, texto):
        assert (token, chat_id) == ("token-ficticio", "destino-ficticio")
        if falhar:
            raise resumo_manual.telegram.ErroTelegram("a API respondeu com token-ficticio no motivo")
        envios.append(texto)

    return enviar, envios


REGISTRO_RESUMIDO = {
    "versao": "37.0.2",
    "noticia": {"id": 1, "titulo": "Notas do patch 37.0.2", "link": "https://exemplo.invalid/pt"},
    "resumo_ia": {"topicos": TOPICOS, "modelo": "manual-gemini", "gerado": "x"},
}


def test_avisar_manda_o_resumo_do_patch_ao_telegram(monkeypatch):
    enviar, envios = ambiente_telegram(monkeypatch)
    assert resumo_manual.avisar(PATCH, REGISTRO_RESUMIDO, enviar)
    assert len(envios) == 1 and envios[0].startswith("Hearthstone DS: resumo do patch 37.0.2")
    assert "Resumo gerado por IA\n\n" + TOPICOS[0] in envios[0]


def test_avisar_manda_o_resumo_da_noticia_ao_telegram(monkeypatch):
    enviar, envios = ambiente_telegram(monkeypatch)
    registro = {"id": 5, "titulo": "Novidade", "link": "https://exemplo.invalid/n", "resumo_ia": REGISTRO_RESUMIDO["resumo_ia"]}
    assert resumo_manual.avisar("noticias/2026-10-20-5.json", registro, enviar)
    assert envios[0].startswith("Hearthstone DS: resumo da notícia\n\nNovidade")


@pytest.mark.parametrize("faltando", [("TELEGRAM_TOKEN",), ("TELEGRAM_CHAT_ID",), ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")])
def test_avisar_sem_token_ou_chat_nao_envia_e_avisa_no_log(monkeypatch, capsys, faltando):
    monkeypatch.setenv("TELEGRAM_TOKEN", "token-ficticio")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "destino-ficticio")
    for nome in faltando:
        monkeypatch.delenv(nome)
    enviar = lambda *args: pytest.fail("não deveria enviar")
    assert not resumo_manual.avisar(PATCH, REGISTRO_RESUMIDO, enviar)
    assert "::warning::Resumo gravado, mas o Telegram não recebeu o aviso" in capsys.readouterr().out


@pytest.mark.parametrize("erro", [OSError("rede"), ValueError("limite"), KeyError("formato")])
def test_falha_de_outro_tipo_no_envio_tambem_nao_desfaz_a_gravacao(raiz, monkeypatch, capsys, erro):
    monkeypatch.setenv("TELEGRAM_TOKEN", "token-ficticio")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "destino-ficticio")

    def quebrar(*args):
        raise erro

    monkeypatch.setattr(resumo_manual.telegram, "enviar_mensagem", quebrar)
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "gravar")
    monkeypatch.setenv("ARQUIVO", PATCH)
    monkeypatch.setenv("TOPICOS", " | ".join(TOPICOS))
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas", TEXTO)))
    assert resumo_manual.main() == 0
    assert "o aviso ao Telegram falhou" in capsys.readouterr().out
    assert json.loads((raiz / PATCH).read_text(encoding="utf-8"))["resumo_ia"]["topicos"] == TOPICOS


def test_falha_na_segunda_parte_da_mensagem_devolve_falso(monkeypatch, capsys):
    ambiente_telegram(monkeypatch)
    registro = {**REGISTRO_RESUMIDO, "resumo_ia": {**REGISTRO_RESUMIDO["resumo_ia"], "topicos": [f"Tópico {i}: " + "x" * 290 for i in range(15)]}}
    chamadas = []

    def enviar(token, chat_id, texto):
        chamadas.append(texto)
        if len(chamadas) == 2:
            raise resumo_manual.telegram.ErroTelegram("falha")

    assert not resumo_manual.avisar(PATCH, registro, enviar)
    assert len(chamadas) == 2 and "o aviso ao Telegram falhou" in capsys.readouterr().out


def test_falha_do_telegram_nao_desfaz_a_gravacao_e_nao_vaza_o_motivo(raiz, monkeypatch, capsys):
    enviar, _ = ambiente_telegram(monkeypatch, falhar=True)
    monkeypatch.setattr(resumo_manual.telegram, "enviar_mensagem", enviar)
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "gravar")
    monkeypatch.setenv("ARQUIVO", PATCH)
    monkeypatch.setenv("TOPICOS", " | ".join(TOPICOS))
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas", TEXTO)))
    assert resumo_manual.main() == 0
    saida = capsys.readouterr().out
    assert "o aviso ao Telegram falhou" in saida and "token-ficticio" not in saida
    assert json.loads((raiz / PATCH).read_text(encoding="utf-8"))["resumo_ia"]["topicos"] == TOPICOS


def test_falha_inesperada_do_envio_tambem_nao_derruba_o_gravar(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_TOKEN", "token-ficticio")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "destino-ficticio")

    def quebrar(*args):
        raise KeyError("resposta fora do formato com token-ficticio")

    assert not resumo_manual.avisar(PATCH, REGISTRO_RESUMIDO, quebrar)
    saida = capsys.readouterr().out
    assert "o aviso ao Telegram falhou" in saida and "token-ficticio" not in saida


def test_main_gravar_envia_o_resumo_gravado_ao_telegram(raiz, monkeypatch):
    enviar, envios = ambiente_telegram(monkeypatch)
    monkeypatch.setattr(resumo_manual.telegram, "enviar_mensagem", enviar)
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "gravar")
    monkeypatch.setenv("ARQUIVO", PATCH)
    monkeypatch.setenv("ESCRITOR", "gemini")
    monkeypatch.setenv("TOPICOS", " | ".join(TOPICOS))
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas", TEXTO)))
    assert resumo_manual.main() == 0
    assert len(envios) == 1 and "Resumo gerado por IA" in envios[0]


def test_recusa_nao_envia_nada_ao_telegram(raiz, monkeypatch):
    enviar, envios = ambiente_telegram(monkeypatch)
    monkeypatch.setattr(resumo_manual.telegram, "enviar_mensagem", enviar)
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "gravar")
    monkeypatch.setenv("ARQUIVO", PATCH)
    monkeypatch.setenv("TOPICOS", "só um")
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas", TEXTO)))
    assert resumo_manual.main() == 1
    assert envios == []
