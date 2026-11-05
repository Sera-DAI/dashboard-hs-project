import pytest

from hsds import formatador


def patch(cartas=None):
    return {
        "versao": "36.6",
        "data": "2026-10-23",
        "noticia": {"titulo": "Notas do patch 36.6", "link": "https://exemplo.invalid/pt", "resumo": "Resumo fictício."},
        "noticia_en": {"titulo": "36.6 Patch Notes", "link": "https://exemplo.invalid/en"},
        "cartas": cartas,
    }


def test_textos_exatos():
    dado = patch({"buffs": [], "nerfs": [], "alteradas": []})
    assert formatador.patch_novo(dado) == [
        "Hearthstone DS: saiu o patch 36.6\n\nNotas do patch 36.6\nhttps://exemplo.invalid/pt\n\nResumo fictício.\n\nNenhuma carta colecionável mudou."
    ]
    assert formatador.noticia_portugues(dado) == [
        "Hearthstone DS: notícia em português do patch 36.6\n\nNotas do patch 36.6\nhttps://exemplo.invalid/pt\n\nResumo fictício."
    ]
    assert formatador.cartas_atualizadas(dado) == [
        "Hearthstone DS: cartas alteradas no patch 36.6\n\nNenhuma carta colecionável mudou."
    ]
    assert formatador.sem_portugues(dado) == [
        "Hearthstone DS: saiu o patch 36.6 (notícia em português ainda não publicada)\n\n36.6 Patch Notes\nhttps://exemplo.invalid/en\n\nNenhuma carta colecionável mudou.\n\nQuando a notícia em português sair, aviso."
    ]
    assert formatador.falha("blizzard", "JSON inválido") == [
        "Hearthstone DS: a coleta de notícias da Blizzard falhou\nMotivo: JSON inválido\nNada foi gravado. Se continuar falhando, aviso de novo em 24 horas."
    ]


def test_sem_versao_noticia_ingles_ou_cartas():
    dado = patch()
    dado["versao"] = None
    dado["noticia_en"] = None
    texto = formatador.patch_novo(dado)[0]
    assert texto.startswith("Hearthstone DS: saiu o patch de 23/10/2026\n")
    assert texto.endswith("As cartas alteradas chegam em outra mensagem quando os dados forem publicados.")
    assert "Notícias: https://hearthstone.blizzard.com/pt-br/news\n\n" in formatador.sem_portugues(dado)[0]


def test_grupos_campos_ordenacao_e_limpeza():
    carta = {"nome": "Quarta Carta", "mudancas": [
        {"campo": "texto", "antes": "velho", "depois": "[x]<b>Grito de Guerra:</b> compre $uma #carta."},
        {"campo": "custo", "antes": 2, "depois": 3},
    ]}
    dado = patch({
        "buffs": [
            {"nome": "Outra Carta", "mudancas": [{"campo": "vida", "antes": 4, "depois": 5}, {"campo": "ataque", "antes": 2, "depois": 3}]},
            {"nome": "Nome da Carta", "mudancas": [{"campo": "custo", "antes": 3, "depois": 2}]},
        ],
        "nerfs": [{"nome": "Terceira Carta", "mudancas": [{"campo": "custo", "antes": 4, "depois": 5}]}],
        "alteradas": [carta],
    })
    assert formatador.cartas_atualizadas(dado) == [
        "Hearthstone DS: cartas alteradas no patch 36.6\n\n"
        "Buffs (2)\n• Nome da Carta: custo 3 → 2\n• Outra Carta: ataque 2 → 3, vida 4 → 5\n\n"
        "Nerfs (1)\n• Terceira Carta: custo 4 → 5\n\n"
        "Alteradas (1)\n• Quarta Carta: custo 2 → 3; texto novo: Grito de Guerra: compre uma carta."
    ]


def test_divisao_sem_cortar_cartas_e_contagem_de_partes():
    cartas = [
        {"nome": f"Carta {numero:04}", "mudancas": [{"campo": "texto", "antes": "a", "depois": "b" * 150}]}
        for numero in range(300)
    ]
    partes = formatador.cartas_atualizadas(patch({"buffs": [], "nerfs": [], "alteradas": cartas}))
    assert len(partes) > 9
    assert all(len(parte) <= 4096 for parte in partes)
    assert partes[0].splitlines()[0].endswith(f" (1/{len(partes)})")
    for numero, parte in enumerate(partes[1:], 2):
        assert parte.startswith(f"Hearthstone DS: patch 36.6 (continuação {numero}/{len(partes)})\n")
    linhas = [linha for parte in partes for linha in parte.splitlines() if linha.startswith("•")]
    assert len(linhas) == 300
    assert all(linha.endswith("b" * 150) for linha in linhas)


def test_limite_exato():
    assert formatador.mensagens("a" * 4096, "36.6") == ["a" * 4096]


def test_resumo_aparece_nas_mensagens_de_patch_e_atrasado():
    dado = patch({"buffs": [], "nerfs": [], "alteradas": []})
    dado["resumo_ia"] = {"topicos": ["Arena recebe ajustes.", "Novo evento chega.", "Bugs importantes corrigidos."]}
    bloco = "Resumo gerado por IA\n\nArena recebe ajustes.\n\nNovo evento chega.\n\nBugs importantes corrigidos."
    assert f"Resumo fictício.\n\n{bloco}\n\n" in formatador.patch_novo(dado)[0]
    assert formatador.noticia_portugues(dado)[0].endswith(f"Resumo fictício.\n\n{bloco}")
    assert f"{bloco}\n\nNenhuma carta colecionável mudou." in formatador.cartas_atualizadas(dado)[0]
    assert formatador.resumo_atrasado(dado)[0].endswith("https://exemplo.invalid/pt")


def test_noticia_nova_sai_sem_resumo():
    # D54: o aviso sai logo; o resumo vem depois, pelo resumo manual (mensagem de resumo_noticia).
    noticia = {"titulo": "Novidades fictícias", "link": "https://exemplo.invalid/noticia", "resumo": "Resumo oficial."}
    assert formatador.noticia_nova(noticia) == [
        "Hearthstone DS: notícia nova\n\nNovidades fictícias\nhttps://exemplo.invalid/noticia\n\nResumo oficial."
    ]


def test_resumo_atrasado_de_noticia_segue_mensagem_9():
    noticia = {
        "titulo": "Novidades fictícias",
        "link": "https://exemplo.invalid/noticia",
        "resumo_ia": {"topicos": ["Loja: chegam itens.", "Evento: começa hoje.", "Bugs: ajustes aplicados."]},
    }
    assert formatador.resumo_noticia(noticia)[0] == (
        "Hearthstone DS: resumo da notícia\n\nNovidades fictícias\nhttps://exemplo.invalid/noticia\n\n"
        "Resumo gerado por IA\n\nLoja: chegam itens.\n\nEvento: começa hoje.\n\nBugs: ajustes aplicados."
    )


def test_carta_que_excede_uma_parte_nao_e_truncada():
    with pytest.raises(ValueError, match="não é possível dividir uma carta"):
        formatador.mensagens("Título\n• " + "a" * 4096, "36.6")


def test_bloco_de_cartas_mostra_texto_alterado_sem_formato():
    # Dados sem `formato` (anteriores à D46): uma lista só, agora com o texto alterado (D46 reverte parte da D32).
    cartas = {
        "buffs": [{"dbfId": 1, "nome": "Isiset", "mudancas": [{"campo": "custo", "antes": 7, "depois": 6}]}],
        "nerfs": [],
        "alteradas": [],
        "revisadas": [{"dbfId": 2, "nome": "Gnomaferatu", "mudancas": [{"campo": "texto", "antes": "Remova um card.", "depois": "<b>Grito de Guerra:</b> Remova o card."}]}],
    }
    assert formatador._bloco(cartas) == (
        "Buffs (1)\n• Isiset: custo 7 → 6\n\n"
        "Texto alterado (1)\n• Gnomaferatu: texto novo: Grito de Guerra: Remova o card."
    )
    sem_grupo = {"buffs": [], "nerfs": [], "alteradas": [], "revisadas": []}
    assert formatador._bloco(sem_grupo) == "Nenhuma carta colecionável mudou."


def test_bloco_de_cartas_separa_padrao_e_livre():
    cartas = {
        "buffs": [
            {"dbfId": 1, "nome": "Isiset", "formato": "padrao", "tambem_livre": True, "mudancas": [{"campo": "custo", "antes": 7, "depois": 6}]},
            {"dbfId": 3, "nome": "Leeroy", "formato": "livre", "mudancas": [{"campo": "ataque", "antes": 6, "depois": 7}]},
        ],
        "nerfs": [],
        "alteradas": [],
        "revisadas": [{"dbfId": 2, "nome": "Reencarnar", "formato": "livre", "mudancas": [{"campo": "texto", "antes": "a", "depois": "<b>Lendário</b> não"}]}],
    }
    assert formatador._bloco(cartas) == (
        "Padrão\n\nBuffs (1)\n• Isiset: custo 7 → 6 (vale também no Livre)\n\n"
        "Livre\n\nBuffs (1)\n• Leeroy: ataque 6 → 7\n\nTexto alterado (1)\n• Reencarnar: texto novo: Lendário não"
    )
    so_livre = {"buffs": [], "nerfs": [], "alteradas": [], "revisadas": [{**cartas["revisadas"][0]}]}
    assert formatador._bloco(so_livre).startswith("Padrão\nNenhuma alteração relevante.\n\nLivre\n\nTexto alterado (1)")
