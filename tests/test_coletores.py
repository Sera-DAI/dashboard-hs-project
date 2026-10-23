import json
import socket
import urllib.error
from pathlib import Path

import pytest

from hsds import blizzard, hearthstonejson, http

DADOS = Path(__file__).parent / "dados"


def test_build_no_corpo_em_uma_requisicao():
    chamadas = []

    def abrir(requisicao):
        chamadas.append(requisicao)
        return (DADOS / "build-atual.html").read_bytes()

    assert http.build_atual(abrir=abrir) == 255130
    assert len(chamadas) == 1
    assert chamadas[0].full_url == http.ULTIMA_BUILD
    assert chamadas[0].get_method() == "GET"
    assert chamadas[0].get_header("User-agent") == http.AGENTE


@pytest.mark.parametrize("bruto", [b"<html>mudou</html>", b"/v1/123/ /v1/456/", b"/v1/latest/", b""])
def test_build_sem_numero_unico_falha(bruto):
    with pytest.raises(http.ErroFonte, match="formato da resposta mudou") as erro:
        http.build_atual(abrir=lambda requisicao: bruto)
    assert erro.value.fonte == "hearthstonejson"


@pytest.mark.parametrize("url,fonte", [(http.ULTIMA_BUILD, "hearthstonejson"), ("https://hearthstone.blizzard.com/pt-br/api/blog/articleList/", "blizzard")])
@pytest.mark.parametrize("falha", [urllib.error.URLError("endereço privado"), TimeoutError(), urllib.error.HTTPError("url", 503, "erro", {}, None)])
def test_erro_de_rede_sem_detalhes(url, fonte, falha):
    def abrir(requisicao):
        raise falha

    with pytest.raises(http.ErroFonte) as erro:
        http.baixar(url, abrir=abrir)
    assert erro.value.fonte == fonte
    assert str(erro.value) == "site fora do ar ou sem resposta"


def test_timeout_padrao(monkeypatch):
    chamadas = []

    class Resposta:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"ok"

    def abrir(requisicao, timeout):
        chamadas.append((requisicao, timeout))
        return Resposta()

    monkeypatch.setattr(http.urllib.request, "urlopen", abrir)
    assert http.baixar(http.ULTIMA_BUILD) == b"ok"
    assert chamadas[0][1] == 20


@pytest.mark.parametrize("titulo,versao", [
    ("Notas do patch 36.6.3:", "36.6.3"),
    ("[Atualizado em 30/09/2026] Notas do patch 36.6", "36.6"),
    ("36.6 Patch Notes", "36.6"),
    ("PATCH NOTES 36.6.2", "36.6.2"),
    ("Notas do patch", None),
    ("[30/09/2026] Novidades", None),
])
def test_titulos_e_versoes(titulo, versao):
    dados = json.loads((DADOS / "noticias-base.json").read_bytes())
    dados["blogList"][0]["title"] = titulo
    noticia = blizzard.noticias(json.dumps(dados).encode(), "pt-br")[0]
    assert noticia.versao == versao
    assert blizzard.e_patch(noticia) == ("Novidades" not in titulo)


def test_noticia_sem_content_e_sem_html():
    noticia = blizzard.noticias((DADOS / "noticias-base.json").read_bytes(), "pt-br")[0]
    assert noticia.link == "https://hearthstone.blizzard.com/pt-br/news/10"
    assert noticia.resumo == "Resumo fictício & curto."
    assert noticia.publicada.endswith("Z")
    assert "content" not in noticia.dados()
    assert "versao" not in noticia.dados()


@pytest.mark.parametrize("leitor,fonte", [(lambda bruto: blizzard.noticias(bruto, "pt-br"), "blizzard"), (lambda bruto: hearthstonejson.cartas(bruto, 1), "hearthstonejson")])
@pytest.mark.parametrize("bruto,motivo", [(b"{", "JSON inválido"), (b"\xff", "JSON inválido"), (b"{}", "formato da resposta mudou"), (b"[{}]", "formato da resposta mudou")])
def test_formatos_invalidos(leitor, fonte, bruto, motivo):
    with pytest.raises(http.ErroFonte, match=motivo) as erro:
        leitor(bruto)
    assert erro.value.fonte == fonte


def test_cartas_reduzidas_e_null():
    resultado = hearthstonejson.cartas((DADOS / "cartas-antes.json").read_bytes(), 255130)
    assert resultado["build"] == 255130
    carta = resultado["cartas"]["1"]
    assert carta["durabilidade"] is None
    assert carta["armadura"] is None
    assert carta["texto"].startswith("<b>")
    assert set(carta) == set(hearthstonejson.CAMPOS)


def test_socket_bloqueado():
    with pytest.raises(AssertionError, match="rede proibida"):
        socket.create_connection(("example.com", 443))
