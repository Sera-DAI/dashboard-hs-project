from pathlib import Path

from hsds import busca, gravacao, monitor

from test_monitor import ambiente, ler, nova_build  # noqa: F401


CARTAS = {
    "build": 7,
    "cartas": {
        "559": {"id": "EX1_116", "nome": "Leeroy Jenkins", "classe": "NEUTRAL", "custo": 5},
        "69501": {"id": "CORE_EX1_116", "nome": "Leeroy Jenkins", "classe": "NEUTRAL", "custo": 4},
        "2539": {"id": "AT_001", "nome": "Lança de Fogo", "classe": "MAGE", "custo": 5},
        "90": {"id": "X_1", "nome": "Ágil Arqueira", "classe": "HUNTER", "custo": 1},
        "91": {"id": "X_2", "nome": "\"Chefe\" Bico", "classe": "NEUTRAL", "custo": 2},
        "69852": {"id": "VAN_EX1_116", "nome": "Leeroy Jenkins", "classe": "NEUTRAL", "colecao": "VANILLA", "custo": 4},
        "111462": {"id": "CORE_EX1_116", "nome": "Leeroy Jenkins", "classe": "NEUTRAL", "colecao": "CORE_HIDDEN", "custo": 5},
        "83395": {"id": "HERO_04u", "nome": "Leeroy Jenkins", "classe": "PALADIN", "colecao": "HERO_SKINS", "custo": None},
    },
}


def test_normalizar_tira_acentos_e_maiusculas():
    assert busca.normalizar("Lança de Fogo") == "lanca de fogo"
    assert busca.normalizar("Ágil Arqueira") == "agil arqueira"


def test_arquivos_indice_ordenado_e_cartas_por_letra():
    gerados = busca.arquivos(Path("dados"), CARTAS)
    assert gerados[Path("dados/busca.json")] == {
        "build": 7,
        "formato": busca.FORMATO,
        "cartas": [
            ["91", "\"Chefe\" Bico", "\"chefe\" bico"],
            ["90", "Ágil Arqueira", "agil arqueira"],
            ["2539", "Lança de Fogo", "lanca de fogo"],
            ["559", "Leeroy Jenkins", "leeroy jenkins"],
            ["69501", "Leeroy Jenkins", "leeroy jenkins"],
        ],
    }
    assert set(gerados[Path("dados/cartas/l.json")]["cartas"]) == {"559", "69501", "2539"}
    assert set(gerados[Path("dados/cartas/a.json")]["cartas"]) == {"90"}
    assert set(gerados[Path("dados/cartas/outros.json")]["cartas"]) == {"91"}
    assert gerados[Path("dados/cartas/l.json")]["cartas"]["559"] == CARTAS["cartas"]["559"]


def test_arquivos_deixam_fora_colecoes_fora_do_padrao_e_do_selvagem():
    gerados = busca.arquivos(Path("dados"), CARTAS)
    ids = {item[0] for item in gerados[Path("dados/busca.json")]["cartas"]}
    assert not ids & {"69852", "111462", "83395"}
    assert not set(gerados[Path("dados/cartas/l.json")]["cartas"]) & {"69852", "111462", "83395"}


def test_desatualizados_so_quando_falta_ou_muda_a_build(tmp_path):
    raiz = tmp_path / "dados"
    assert busca.desatualizados(raiz, gravacao.ler) == {}
    gravacao.gravar({raiz / "cartas.json": CARTAS})
    gerados = busca.desatualizados(raiz, gravacao.ler)
    assert raiz / "busca.json" in gerados
    gravacao.gravar(gerados)
    assert busca.desatualizados(raiz, gravacao.ler) == {}
    gravacao.gravar({raiz / "cartas.json": {**CARTAS, "build": 8}})
    assert busca.desatualizados(raiz, gravacao.ler)[raiz / "busca.json"]["build"] == 8


def test_desatualizados_quando_muda_o_formato(tmp_path):
    raiz = tmp_path / "dados"
    gravacao.gravar({raiz / "cartas.json": CARTAS, raiz / "busca.json": {"build": 7, "cartas": []}})
    assert busca.desatualizados(raiz, gravacao.ler)[raiz / "busca.json"]["formato"] == busca.FORMATO


def test_monitor_grava_derivados_na_linha_base_e_na_build_nova(ambiente):  # noqa: F811
    assert monitor.main() == 0
    assert ler("busca.json")["build"] == 255130
    fora = [carta for carta in ler("cartas.json")["cartas"].values() if carta.get("colecao") in busca.FORA_DA_BUSCA]
    assert len(ler("busca.json")["cartas"]) == len(ler("cartas.json")["cartas"]) - len(fora)
    nova_build(ambiente)
    assert monitor.main() == 0
    assert ler("busca.json")["build"] == 255131
    assert all(ler(f"cartas/{arquivo.stem}.json")["build"] == 255131 for arquivo in Path("dados/cartas").glob("*.json"))


def test_monitor_gera_derivados_que_faltam_sem_build_nova(ambiente):  # noqa: F811
    assert monitor.main() == 0
    Path("dados/busca.json").unlink()
    assert monitor.main() == 0
    assert ler("busca.json")["build"] == 255130
