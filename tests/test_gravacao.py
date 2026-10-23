import json

import pytest

from hsds import gravacao


def test_utf8_json_completo_e_temporario_no_mesmo_diretorio(tmp_path, monkeypatch):
    destino = tmp_path / "patches" / "patch.json"
    substituir = gravacao.os.replace
    chamadas = []

    def conferir(origem, alvo):
        assert origem.parent == alvo.parent
        assert json.loads(origem.read_text(encoding="utf-8")) == {"nome": "Ação"}
        chamadas.append(alvo)
        substituir(origem, alvo)

    monkeypatch.setattr(gravacao.os, "replace", conferir)
    gravacao.gravar({destino: {"nome": "Ação"}})
    assert chamadas == [destino]
    assert destino.read_bytes() == '{\n  "nome": "Ação"\n}\n'.encode()
    assert not list(tmp_path.rglob(".hsds-*"))


def test_falha_na_preparacao_nao_substitui_nada(tmp_path):
    antigo = tmp_path / "estado.json"
    antigo.write_text('{"antigo": true}', encoding="utf-8")
    with pytest.raises(TypeError):
        gravacao.gravar({antigo: {"novo": True}, tmp_path / "outro.json": {"erro": object()}})
    assert json.loads(antigo.read_bytes()) == {"antigo": True}
    assert not (tmp_path / "outro.json").exists()
    assert not list(tmp_path.rglob(".hsds-*"))


@pytest.mark.parametrize("primeiro_novo", [True, False])
def test_falha_na_segunda_substituicao_desfaz_a_primeira(tmp_path, monkeypatch, primeiro_novo):
    primeiro = tmp_path / "patch.json"
    segundo = tmp_path / "estado.json"
    if not primeiro_novo:
        primeiro.write_bytes(b'{"antigo": true}\n')
    segundo.write_bytes(b'{"build": 1}\n')
    substituir = gravacao.os.replace
    chamadas = 0

    def falhar_uma_vez(origem, destino):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 2:
            raise OSError("falha fictícia")
        substituir(origem, destino)

    monkeypatch.setattr(gravacao.os, "replace", falhar_uma_vez)
    with pytest.raises(OSError):
        gravacao.gravar({primeiro: {"novo": True}, segundo: {"build": 2}})
    if primeiro_novo:
        assert not primeiro.exists()
    else:
        assert primeiro.read_bytes() == b'{"antigo": true}\n'
    assert segundo.read_bytes() == b'{"build": 1}\n'
    assert not list(tmp_path.rglob(".hsds-*"))
