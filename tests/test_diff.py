import copy
from pathlib import Path

import pytest

from hsds import diff, hearthstonejson

DADOS = Path(__file__).parent / "dados"


@pytest.mark.parametrize("campo,antes,depois,grupo", [
    ("custo", 3, 2, "buffs"),
    ("custo", 2, 3, "nerfs"),
    ("ataque", 1, 2, "buffs"),
    ("ataque", 2, 1, "nerfs"),
    ("vida", 1, 2, "buffs"),
    ("vida", 2, 1, "nerfs"),
    ("durabilidade", 1, 2, "buffs"),
    ("durabilidade", 2, 1, "nerfs"),
    ("armadura", 1, 2, "buffs"),
    ("armadura", 2, 1, "nerfs"),
    ("custo", None, 2, "alteradas"),
    ("vida", 2, None, "alteradas"),
    ("texto", "antes", "depois", "alteradas"),
])
def test_tabela(campo, antes, depois, grupo):
    antiga = {"cartas": {"1": {"nome": "Carta fictícia", "classe": "MAGE", campo: antes}}}
    nova = copy.deepcopy(antiga)
    nova["cartas"]["1"][campo] = depois
    resultado = diff.comparar(antiga, nova)
    assert resultado[grupo] == [{"dbfId": 1, "nome": "Carta fictícia", "classe": "MAGE", "mudancas": [{"campo": campo, "antes": antes, "depois": depois}]}]
    assert sum(map(len, resultado.values())) == 1


@pytest.mark.parametrize("alteracoes,grupo", [
    ({"custo": 2, "ataque": 3}, "buffs"),
    ({"custo": 4, "ataque": 1}, "nerfs"),
    ({"custo": 2, "ataque": 1}, "alteradas"),
    ({"custo": 2, "texto": "novo"}, "alteradas"),
])
def test_sentidos_mistos(alteracoes, grupo):
    antiga = {"cartas": {"1": {"nome": "Fictícia", "custo": 3, "ataque": 2, "texto": "antigo"}}}
    nova = copy.deepcopy(antiga)
    nova["cartas"]["1"].update(alteracoes)
    assert len(diff.comparar(antiga, nova)[grupo]) == 1


def test_fixture_sem_novas_ou_removidas():
    antes = hearthstonejson.cartas((DADOS / "cartas-antes.json").read_bytes(), 1)
    depois = hearthstonejson.cartas((DADOS / "cartas-depois.json").read_bytes(), 2)
    resultado = diff.comparar(antes, depois)
    assert [carta["dbfId"] for carta in resultado["buffs"]] == [1]
    assert [carta["dbfId"] for carta in resultado["nerfs"]] == [2]
    depois["cartas"]["3"] = depois["cartas"].pop("2")
    assert not diff.comparar(antes, depois)["nerfs"]
    assert not any(diff.comparar(antes, antes).values())


def test_marcas_de_quebra_de_linha_e_espacos_nao_contam_como_mudanca_de_texto():
    antiga = {"cartas": {"1": {"nome": "Fictícia", "texto": "No início do seu turno, destrua TODOS os lacaios."}}}
    nova = {"cartas": {"1": {"nome": "Fictícia", "texto": "[x]No início do seu turno,& destrua TODOS os lacaios."}}}
    assert diff.comparar(antiga, nova) == {"buffs": [], "nerfs": [], "alteradas": []}


def test_mudanca_real_de_texto_com_marca_nova_continua_alterada():
    antiga = {"cartas": {"1": {"nome": "Fictícia", "texto": "Cause 2 de dano."}}}
    nova = {"cartas": {"1": {"nome": "Fictícia", "texto": "Cause& 3 de dano."}}}
    resultado = diff.comparar(antiga, nova)
    assert resultado["alteradas"][0]["mudancas"] == [{"campo": "texto", "antes": "Cause 2 de dano.", "depois": "Cause& 3 de dano."}]
