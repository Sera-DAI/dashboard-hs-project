import json

import pytest

from hsds import diff, formatos, gravacao, imagens
from hsds.http import ErroFonte


def servidor_padrao(paginas, registro=None):
    def pedir(requisicao):
        if registro is not None:
            registro.append(requisicao)
        numero = int(requisicao.full_url.split("page=")[1].split("&")[0])
        return {"cards": paginas[numero - 1], "pageCount": len(paginas), "page": numero}

    return pedir


def cartas_ids(inicio, fim):
    return [{"id": numero} for numero in range(inicio, fim)]


def test_baixar_padrao_pagina_filtra_e_ordena():
    registro = []
    paginas = [cartas_ids(400, 700), cartas_ids(100, 250) + [{"id": "x"}, {"id": True}, {"nome": "sem id"}]]
    ids = formatos.baixar_padrao("token", servidor_padrao(paginas, registro))
    assert ids == sorted(set(range(100, 250)) | set(range(400, 700)))
    assert len(registro) == 2
    assert "set=standard" in registro[0].full_url
    assert registro[0].get_header("Authorization") == "Bearer token"


@pytest.mark.parametrize("resposta", [{"cards": "x", "pageCount": 1}, {"cards": [], "pageCount": 0}, {"pageCount": 1}])
def test_baixar_padrao_fora_do_formato(resposta):
    with pytest.raises(ErroFonte):
        formatos.baixar_padrao("token", lambda requisicao: resposta)


def test_baixar_padrao_pequeno_demais_nao_vale():
    with pytest.raises(ErroFonte):
        formatos.baixar_padrao("token", servidor_padrao([cartas_ids(1, 20)]))


def test_baixar_padrao_nao_pagina_sem_fim():
    with pytest.raises(ErroFonte):
        formatos.baixar_padrao("token", lambda requisicao: {"cards": cartas_ids(1, 5), "pageCount": 10_000})


def test_carregar(tmp_path):
    assert formatos.carregar(tmp_path) is None
    gravacao.gravar({tmp_path / "formatos.json": {"padrao": list(range(350))}})
    assert formatos.carregar(tmp_path) == frozenset(str(n) for n in range(350))
    gravacao.gravar({tmp_path / "formatos.json": {"padrao": [1, 2, 3]}})
    assert formatos.carregar(tmp_path) is None
    gravacao.gravar({tmp_path / "formatos.json": {"padrao": ["a"] * 400}})
    assert formatos.carregar(tmp_path) is None


def test_imagens_grava_formatos_e_sobrevive_a_falha(tmp_path, capsys):
    gravacao.gravar({tmp_path / "dados" / "cartas.json": {"build": 1, "cartas": {"2": {}, "3": {}}}})
    imagem = "https://d15f34w2p8l1cc.cloudfront.net/hearthstone/" + "a" * 64 + ".png"

    def abrir(requisicao):
        if requisicao.full_url == imagens.URL_TOKEN:
            return json.dumps({"access_token": "t"}).encode()
        if "set=standard" in requisicao.full_url:
            return json.dumps({"cards": cartas_ids(1000, 1400), "pageCount": 1}).encode()
        return json.dumps({"cards": [{"id": 2, "image": imagem}], "pageCount": 1}).encode()

    ambiente = {"BLIZZARD_CLIENT_ID": "i", "BLIZZARD_CLIENT_SECRET": "s"}
    assert imagens.executar(ambiente, abrir=abrir, raiz=tmp_path) == 0
    assert gravacao.ler(tmp_path / "dados" / "formatos.json") == {"padrao": list(range(1000, 1400))}

    def abrir_sem_padrao(requisicao):
        if "set=standard" in requisicao.full_url:
            return b"{}"
        return abrir(requisicao)

    assert imagens.executar(ambiente, abrir=abrir_sem_padrao, raiz=tmp_path) == 0
    assert gravacao.ler(tmp_path / "dados" / "formatos.json") == {"padrao": list(range(1000, 1400))}
    assert "Formatos não atualizados" in capsys.readouterr().err


def base(colecao_c="OUTRA"):
    def carta(nome, custo, colecao, texto=None):
        return {"nome": nome, "classe": "MAGE", "colecao": colecao, "custo": custo, "ataque": None, "vida": None, "durabilidade": None, "armadura": None, "texto": texto}

    antes = {"build": 1, "cartas": {
        "1": carta("Padrão A", 5, "NOVA"),
        "2": carta("Livre B", 5, "VELHA"),
        "3": carta("Núcleo C", 5, "CORE"),
        "4": carta("Núcleo C", 5, "EXPERT1"),
        "5": carta("Oculta D", 5, "CORE_HIDDEN"),
        "6": carta("Reescrita E", 3, "VELHA", "Destrua um lacaio."),
        "7": carta("Clássica F", 5, "VANILLA"),
    }}
    depois = json.loads(json.dumps(antes))
    for chave in ("1", "2", "3", "4", "5", "7"):
        depois["cartas"][chave]["custo"] = 6
    depois["cartas"]["6"]["texto"] = "Destrua um lacaio que não é <b>Lendário</b>."
    return antes, depois


def test_diff_marca_formato_junta_repetidas_e_ignora_ocultas():
    antes, depois = base()
    resultado = diff.comparar(antes, depois, frozenset({"1", "3", "5"}))
    nerfs = {carta["nome"]: carta for carta in resultado["nerfs"]}
    assert set(nerfs) == {"Padrão A", "Livre B", "Núcleo C"}
    assert nerfs["Padrão A"]["formato"] == "padrao" and "tambem_livre" not in nerfs["Padrão A"]
    assert nerfs["Livre B"]["formato"] == "livre"
    # A cópia do Núcleo (Padrão) e a da coleção original (Livre) são a mesma mudança.
    assert nerfs["Núcleo C"]["formato"] == "padrao" and nerfs["Núcleo C"]["tambem_livre"] is True
    assert [carta["dbfId"] for carta in resultado["nerfs"]].count(4) == 0
    # Texto alterado entra, no Livre.
    assert [(carta["nome"], carta["formato"]) for carta in resultado["revisadas"]] == [("Reescrita E", "livre")]
    assert all(carta["nome"] not in {"Oculta D", "Clássica F"} for grupo in resultado.values() for carta in grupo)


def test_diff_sem_padrao_nao_marca_formato():
    antes, depois = base()
    resultado = diff.comparar(antes, depois)
    assert all("formato" not in carta for grupo in resultado.values() for carta in grupo)
    assert "Oculta D" not in {carta["nome"] for carta in resultado["nerfs"]}


def test_completar_formatos_de_diff_antigo():
    antes, depois = base()
    antigo = diff.comparar(antes, depois)
    # Um diff gravado antes da D46 ainda carrega as ocultas.
    antigo["nerfs"].append({"dbfId": 5, "nome": "Oculta D", "classe": "MAGE", "mudancas": [{"campo": "custo", "antes": 5, "depois": 6}]})
    novo = diff.completar_formatos(antigo, depois, frozenset({"1", "3"}))
    nomes = {carta["nome"]: carta.get("formato") for carta in novo["nerfs"]}
    assert nomes == {"Padrão A": "padrao", "Livre B": "livre", "Núcleo C": "padrao"}
    assert novo["nerfs"][-1].get("tambem_livre") or any(carta.get("tambem_livre") for carta in novo["nerfs"])
    assert diff.completar_formatos(novo, depois, frozenset({"1", "3"})) is None
    assert diff.completar_formatos(None, depois, frozenset()) is None
    # Sem a lista do Padrão, só as ocultas saem; o formato fica para quando a lista existir.
    so_ocultas = diff.completar_formatos(antigo, depois, None)
    assert "Oculta D" not in {carta["nome"] for carta in so_ocultas["nerfs"]}
    assert all("formato" not in carta for carta in so_ocultas["nerfs"])
