import pytest

from hsds import resumo_ia

TEXTO = "A Blizzard anunciou mudanças importantes para Arena, Campos de Batalha e eventos sazonais." \
    "Jogadores poderão aproveitar novos modos e correções de bugs nesta atualização."
TOPICOS = ["Arena recebe ajustes importantes.", "Campos de Batalha têm mudanças.", "Evento sazonal chega ao jogo."]

def test_noticia_sem_cartas_termina_apos_o_texto():
    mensagem = resumo_ia.montar_mensagem("Novidades", "Texto fictício.", "pt-br", None, com_cartas=False)
    assert mensagem == "Notícia oficial (português): Novidades\n\nTexto fictício."


def test_patch_leva_as_cartas_alteradas_ao_fim_da_mensagem():
    mensagem = resumo_ia.montar_mensagem("Patch", "Texto.", "en-us", None)
    assert mensagem.startswith("Notícia oficial (inglês): Patch\n\nTexto.")
    assert mensagem.endswith("Nenhuma carta alterada nos dados ainda.")


def test_modulo_nao_chama_api_nem_guarda_chave():
    # D54: o resumo é sempre manual; nada de rede, modelo ou chave neste módulo.
    assert not any(hasattr(resumo_ia, nome) for nome in ("gerar", "MODELO", "MODELOS_RESERVA", "ENDERECO"))


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


def test_cartas_do_prompt_separam_formato_e_incluem_texto_alterado():
    cartas = {
        "buffs": [{"nome": "Isiset", "formato": "padrao", "mudancas": [{"campo": "custo"}]}],
        "nerfs": [{"nome": "Leeroy", "formato": "livre", "mudancas": [{"campo": "ataque"}, {"campo": "vida"}]}],
        "alteradas": [],
        "revisadas": [{"nome": "Reencarnar", "formato": "livre", "mudancas": [{"campo": "texto"}]}, {"nome": "Antiga", "mudancas": [{"campo": "texto"}]}],
    }
    assert resumo_ia._cartas(cartas) == (
        "Padrão, Buffs: Isiset (custo)\n"
        "Livre, Nerfs: Leeroy (ataque, vida)\n"
        "Livre, Texto alterado: Reencarnar (texto)\n"
        "Texto alterado: Antiga (texto)"
    )
    assert resumo_ia._cartas({"buffs": [], "nerfs": [], "alteradas": [], "revisadas": []}) == "Nenhuma carta alterada nos dados ainda."


def test_prompt_pede_menos_que_o_teto_da_validacao():
    assert "de 8 a 14 tópicos" in resumo_ia.INSTRUCAO and "280 caracteres" in resumo_ia.INSTRUCAO
    assert resumo_ia.validar([f"Tópico {i} com texto próprio." + "x" * 250 for i in range(14)], "")
