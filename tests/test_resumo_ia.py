import json
import urllib.error
from pathlib import Path

import pytest

from hsds import resumo_ia

TEXTO = "A Blizzard anunciou mudanças importantes para Arena, Campos de Batalha e eventos sazonais." \
    "Jogadores poderão aproveitar novos modos e correções de bugs nesta atualização."
TOPICOS = ["Arena recebe ajustes importantes.", "Campos de Batalha têm mudanças.", "Evento sazonal chega ao jogo."]
DADOS = Path(__file__).parent / "dados"


def test_gera_chamada_com_cabecalho_seguro_e_prompt_contratado():
    chamadas = []

    def abrir(requisicao):
        chamadas.append(requisicao)
        return (DADOS / "resposta-gemini.json").read_bytes()

    assert resumo_ia.gerar("Notas do patch", TEXTO, "pt-br", None, "chave-ficticia", abrir) == TOPICOS
    requisicao = chamadas[0]
    assert requisicao.get_header("X-goog-api-key") == "chave-ficticia"
    assert "chave-ficticia" not in requisicao.full_url
    assert requisicao.get_method() == "POST"
    assert requisicao.get_header("User-agent")
    corpo = json.loads(requisicao.data)
    assert corpo["generationConfig"] == {
        "responseMimeType": "application/json",
        "responseSchema": resumo_ia.ESQUEMA,
        "temperature": 0.3,
    }
    assert "Nenhuma carta alterada nos dados ainda." in corpo["contents"][0]["parts"][0]["text"]


def test_noticia_sem_cartas_termina_apos_o_texto():
    chamadas = []

    def abrir(requisicao):
        chamadas.append(json.loads(requisicao.data))
        return (DADOS / "resposta-gemini.json").read_bytes()

    resumo_ia.gerar("Novidades", "Texto fictício.", "pt-br", None, "chave-ficticia", abrir, com_cartas=False)
    mensagem = chamadas[0]["contents"][0]["parts"][0]["text"]
    assert mensagem == "Notícia oficial (português): Novidades\n\nTexto fictício."


def test_timeout_do_gemini_e_180_segundos(monkeypatch):
    chamadas = []

    class Resposta:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return (DADOS / "resposta-gemini.json").read_bytes()

    def abrir(requisicao, timeout):
        chamadas.append(timeout)
        return Resposta()

    monkeypatch.setattr(resumo_ia.urllib.request, "urlopen", abrir)
    assert resumo_ia.gerar("título", TEXTO, "pt-br", None, "chave-ficticia") == TOPICOS
    assert chamadas == [180]


@pytest.mark.parametrize("topicos", [[], TOPICOS[:2], TOPICOS + [f"tópico {numero}" for numero in range(4, 17)]])
def test_rejeita_quantidade_de_topicos_invalida(topicos):
    with pytest.raises(resumo_ia.ErroResumo, match="resposta inválida"):
        resumo_ia.validar(topicos, TEXTO)


@pytest.mark.parametrize("topico", ["x" * 301, "<b>perigoso", "https://exemplo.invalid", "www.exemplo.invalid"])
def test_rejeita_topico_longo_html_ou_link(topico):
    with pytest.raises(resumo_ia.ErroResumo, match="resposta inválida"):
        resumo_ia.validar([topico, *TOPICOS[:2]], TEXTO)


def test_remove_topico_que_copia_dez_palavras_e_rejeita_se_restam_menos_de_tres():
    noticia = "palavra um dois tres quatro cinco seis sete oito nove dez restante"
    topicos = ["palavra um dois tres quatro cinco seis sete oito nove dez", "Resumo novo um", "Resumo novo dois", "Resumo novo três"]
    assert resumo_ia.validar(topicos, noticia) == topicos[1:]
    with pytest.raises(resumo_ia.ErroResumo, match="resumo copiou a notícia"):
        resumo_ia.validar(topicos[:3], noticia)


def test_chave_ausente_nao_abre_requisicao():
    with pytest.raises(resumo_ia.ErroResumo, match="chave GEMINI_API_KEY ausente"):
        resumo_ia.gerar("título", TEXTO, "pt-br", None, "")


@pytest.mark.parametrize(
    ("codigo", "motivo"),
    [(429, "limite de uso atingido"), (500, "serviço fora do ar ou sem resposta"), (400, "chave recusada ou pedido inválido")],
)
def test_mapeia_erros_http_sem_expor_detalhes(codigo, motivo):
    def abrir(_):
        raise urllib.error.HTTPError("https://exemplo.invalid", codigo, "secreto", {}, None)

    with pytest.raises(resumo_ia.ErroResumo) as erro:
        resumo_ia.gerar("título", TEXTO, "pt-br", None, "chave-ficticia", abrir)
    assert str(erro.value) == motivo


def test_resposta_json_invalida_e_mapeada():
    with pytest.raises(resumo_ia.ErroResumo, match="resposta inválida"):
        resumo_ia.gerar("título", TEXTO, "pt-br", None, "chave-ficticia", lambda _: b"{")
