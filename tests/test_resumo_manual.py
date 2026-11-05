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
        return pt if "/pt-br/" in url else en

    return baixar


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
    estado = {"build": 1, "noticias_vistas": [], "pendentes": [], "falhas": {}, "resumos_pendentes": [{"arquivo": PATCH, "desde": "2026-11-05T05:05:08Z"}, {"arquivo": "patches/outro.json", "desde": "x"}]}
    (pasta / "estado.json").write_text(json.dumps(estado), encoding="utf-8")
    return pasta


def test_pedido_usa_a_mesma_instrucao_e_mensagem_do_gemini(raiz):
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
    with pytest.raises(resumo_manual.ErroManual, match="lista atual"):
        resumo_manual.pedido(raiz, PATCH, baixador(pt=sem_texto, en=sem_texto))


@pytest.mark.parametrize("arquivo", ["../estado.json", "patches/../estado.json", "dados/x.json", "patches/a b.json", "/etc/passwd", "patches/x.json/../../y.json"])
def test_nome_de_arquivo_fora_do_padrao_e_recusado(raiz, arquivo):
    with pytest.raises(resumo_manual.ErroManual, match="arquivo inválido"):
        resumo_manual.pedido(raiz, arquivo, baixador())


def test_topicos_aceitam_linhas_barras_e_marcadores():
    assert resumo_manual.topicos_do_texto("- um\n2. dois | • três\n\n  ") == ["um", "dois", "três"]


def test_gravar_valida_grava_e_tira_da_fila(raiz):
    baixar = baixador(pt=lista(24307311, "Notas do patch 37.0.2", TEXTO))
    agora = datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc)
    gravados = resumo_manual.gravar(raiz, PATCH, " | ".join(TOPICOS), agora, baixar)
    assert gravados == TOPICOS
    patch = json.loads((raiz / PATCH).read_text(encoding="utf-8"))
    assert patch["resumo_ia"] == {"topicos": TOPICOS, "modelo": "manual", "gerado": "2026-11-05T06:00:00Z"}
    assert patch["cartas"]["buffs"][0]["nome"] == "Isiset"
    estado = json.loads((raiz / "estado.json").read_text(encoding="utf-8"))
    assert [item["arquivo"] for item in estado["resumos_pendentes"]] == ["patches/outro.json"]


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

    with pytest.raises(resumo_manual.ErroManual, match="lista atual"):
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


def test_main_sem_arquivo_lista_a_fila_e_usa_o_primeiro(raiz, monkeypatch, capsys):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    monkeypatch.setenv("ACAO", "preparar")
    monkeypatch.setenv("ARQUIVO", "")
    monkeypatch.setattr(resumo_manual.http, "baixar", baixador(pt=lista(24307311, "Notas do patch 37.0.2", TEXTO)))
    assert resumo_manual.main() == 0
    saida = capsys.readouterr().out
    assert "Fila de resumos pendentes: " + PATCH in saida
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


def test_main_com_fila_vazia_so_informa(raiz, monkeypatch, capsys):
    monkeypatch.setattr(resumo_manual, "RAIZ", raiz)
    (raiz / "estado.json").write_text(json.dumps({"resumos_pendentes": []}), encoding="utf-8")
    monkeypatch.setenv("ACAO", "preparar")
    monkeypatch.setenv("ARQUIVO", "")
    assert resumo_manual.main() == 0
    assert "vazia" in capsys.readouterr().out


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
