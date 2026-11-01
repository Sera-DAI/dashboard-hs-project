import json
import urllib.error

import pytest

from hsds import gravacao, imagens
from hsds.http import ErroFonte

H1 = "a" * 64
H2 = "b" * 64


def url(h):
    return f"https://d15f34w2p8l1cc.cloudfront.net/hearthstone/{h}.png"


def servidor(paginas, token="segredo-do-token", registro=None):
    def abrir(requisicao):
        if registro is not None:
            registro.append(requisicao)
        if requisicao.full_url == imagens.URL_TOKEN:
            return json.dumps({"access_token": token}).encode()
        numero = int(requisicao.full_url.split("page=")[1].split("&")[0])
        return json.dumps({"cards": paginas[numero - 1], "pageCount": len(paginas), "page": numero}).encode()

    return abrir


def test_pedido_do_token():
    registro = []
    assert imagens.pedir_token("id", "seg", abrir=servidor([[]], registro=registro)) == "segredo-do-token"
    pedido = registro[0]
    assert pedido.get_method() == "POST"
    assert pedido.data == b"grant_type=client_credentials"
    assert pedido.get_header("Authorization").startswith("Basic ")


def test_token_ausente_falha():
    with pytest.raises(ErroFonte):
        imagens.pedir_token("id", "seg", abrir=lambda r: b'{"erro": 1}')


def test_catalogo_pagina_e_filtra_imagem_invalida():
    paginas = [
        [{"id": 2, "image": url(H1)}, {"id": 1, "image": "https://exemplo.com/x.png"}],
        [{"id": 3, "image": url(H2)}, {"id": 4, "image": url("Z" * 64)}, {"id": "5", "image": url(H1)}, {"id": 6}],
    ]
    registro = []
    catalogo = imagens.baixar_catalogo("tk", abrir=servidor(paginas, registro=registro))
    assert catalogo == {"2": H1, "3": H2}
    assert len(registro) == 2
    assert registro[0].get_header("Authorization") == "Bearer tk"
    assert "page=2" in registro[1].full_url


def test_catalogo_fora_do_formato():
    with pytest.raises(ErroFonte):
        imagens.baixar_catalogo("tk", abrir=lambda r: b'{"cards": 1}')


def test_montar_ordena_filtra_e_herda_imagem_do_core():
    cartas = {
        "10": {"id": "X_1"},
        "9": {"id": "X_2"},
        "11": {"id": "CORE_X_1"},
        "12": {"id": "CORE_Y_9"},
    }
    saida = imagens.montar({"10": H1, "9": H2, "99": H1}, cartas)
    assert saida == {"imagens": {"9": H2, "10": H1, "11": H1}}
    assert list(saida["imagens"]) == ["9", "10", "11"]


def preparar(tmp_path):
    gravacao.gravar({tmp_path / "dados" / "cartas.json": {"build": 1, "cartas": {"2": {}, "3": {}}}})


AMBIENTE = {"BLIZZARD_CLIENT_ID": "id-secreto", "BLIZZARD_CLIENT_SECRET": "senha-secreta"}


def test_executar_grava_ordenado(tmp_path):
    preparar(tmp_path)
    paginas = [[{"id": 3, "image": url(H2)}, {"id": 2, "image": url(H1)}, {"id": 8, "image": url(H1)}]]
    assert imagens.executar(AMBIENTE, abrir=servidor(paginas), raiz=tmp_path) == 0
    assert gravacao.ler(tmp_path / "dados" / "imagens.json") == {"imagens": {"2": H1, "3": H2}}


def test_executar_sem_segredos(tmp_path, capsys):
    preparar(tmp_path)
    assert imagens.executar({}, abrir=servidor([[]]), raiz=tmp_path) == 1
    assert not (tmp_path / "dados" / "imagens.json").exists()


def test_falha_de_rede_nao_grava_nem_vaza_segredo(tmp_path, capsys):
    preparar(tmp_path)

    def abrir(requisicao):
        raise urllib.error.URLError("senha-secreta segredo-do-token")

    assert imagens.executar(AMBIENTE, abrir=abrir, raiz=tmp_path) == 1
    saida = capsys.readouterr()
    assert not (tmp_path / "dados" / "imagens.json").exists()
    for texto in (saida.out, saida.err):
        assert "senha-secreta" not in texto and "id-secreto" not in texto and "segredo-do-token" not in texto


def test_sem_cartas_casadas_nao_grava(tmp_path):
    preparar(tmp_path)
    assert imagens.executar(AMBIENTE, abrir=servidor([[{"id": 77, "image": url(H1)}]]), raiz=tmp_path) == 1
    assert not (tmp_path / "dados" / "imagens.json").exists()
