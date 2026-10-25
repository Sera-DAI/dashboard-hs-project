from pathlib import Path

from hsds import resumo_de_teste, resumo_ia

DADOS = Path(__file__).parent / "dados"


def test_tipo_noticia_usa_noticia_mais_recente_sem_cartas(monkeypatch):
    chamadas = []
    envios = []
    monkeypatch.setenv("TIPO", "noticia")
    monkeypatch.setattr(resumo_de_teste.http, "baixar", lambda *_args, **_kwargs: (DADOS / "noticias-base.json").read_bytes())
    monkeypatch.setattr(
        resumo_ia,
        "gerar",
        lambda *args, **kwargs: chamadas.append((args, kwargs)) or ["Loja: itens novos.", "Evento: começa hoje.", "Bugs: ajustes feitos."],
    )
    monkeypatch.setattr(resumo_de_teste.telegram, "enviar_mensagem", lambda _token, _chat, texto: envios.append(texto))

    assert resumo_de_teste.main() == 0
    assert chamadas[0][0][0] == "Novidades da semana"
    assert chamadas[0][1]["com_cartas"] is False
    assert envios[0].startswith("Hearthstone DS: teste do resumo por IA")


def test_tipo_noticia_sem_noticia_retorna_motivo_contratado(monkeypatch):
    envios = []
    monkeypatch.setenv("TIPO", "noticia")
    monkeypatch.setattr(resumo_de_teste.http, "baixar", lambda *_args, **_kwargs: b'{"blogList": []}')
    monkeypatch.setattr(resumo_de_teste.telegram, "enviar_mensagem", lambda _token, _chat, texto: envios.append(texto))

    assert resumo_de_teste.main() == 1
    assert envios == ["Hearthstone DS: o teste do resumo por IA falhou\nMotivo: nenhuma notícia desse tipo na lista"]
