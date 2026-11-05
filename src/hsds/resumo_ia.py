"""Instrução, pedido e validação do resumo por IA (D54: o resumo é sempre manual; não há chamada de API)."""

import re

from hsds import blizzard

# D53: só a expansão atual (Reinado dos Deuses Antigos, anunciada em 12/09/2026) recebe resumo.
INICIO_EXPANSAO = "2026-09-12"
INSTRUCAO = """Você escreve resumos de notícias e patches do jogo Hearthstone para um monitor pessoal em português do Brasil.

Regras:
1. Escreva de 8 a 14 tópicos, cada um com no máximo 280 caracteres, em português do Brasil. O resumo deve ser completo: use todos os tópicos de que precisar para não perder nenhum detalhe relevante.
2. Cubra todas as seções da notícia, não só as cartas. Confira uma por uma, quando houver: mudanças de cartas e classes; modos de jogo (Campos de Batalha, Arena, Mercenários e outros); loja e itens à venda, como o Cofre da Taverna e pacotes; recompensas, presentes gratuitos e brindes no Battle.net; receitas de deck; eventos, temporadas e datas; correções de bugs e problemas conhecidos.
3. Comece cada tópico por um emoji que combine com o assunto daquele tópico, um espaço e o assunto seguido de dois-pontos, por exemplo "🛒 Loja: ...", "🎁 Presente: ...", "📜 Receitas de deck: ...", "⚔️ Arena: ...", "🐛 Correções: ...". Use um emoji só por tópico, sempre no começo. Um assunto grande pode ocupar mais de um tópico.
4. Use as suas próprias palavras. Nunca copie frases da notícia; reescreva a ideia.
5. Não cite custo, ataque, vida, durabilidade, armadura nem outros números de cartas: esses números são mostrados à parte. Pode citar o nome das cartas e dizer se ficaram mais fortes ou mais fracas. Datas, preços e quantidades de recompensas podem ser citados.
6. Sem HTML, sem markdown, sem links, sem emojis fora do começo do tópico e sem opinião sobre o meta.
7. Não deixe passar mudanças de regras e de interações. Quando uma carta ou missão muda porque outras cartas deixam de contribuir para ela (por exemplo, cartas que deixam de ajudar a cumprir uma missão), diga qual é a mudança e quais cartas estão envolvidas. Cite os nomes das cartas, listas de cartas removidas ou reforçadas, reembolsos, prazos e correções. Agrupe só o que for do mesmo assunto, classe ou modo, e não troque várias mudanças por uma frase genérica.
8. Se a notícia trouxer pouca informação, escreva menos tópicos (nunca menos de 3) e nunca invente.
9. Responda só com os tópicos, no formato pedido."""


class ErroResumo(Exception):
    """Resumo recusado pela validação; o motivo é um texto fixo, sem trecho da notícia."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


def _cartas(cartas: dict | None) -> str:
    grupos = (("buffs", "Buffs"), ("nerfs", "Nerfs"), ("alteradas", "Alteradas"), ("revisadas", "Texto alterado"))
    if not cartas or not any(cartas.get(grupo) for grupo, _ in grupos):
        return "Nenhuma carta alterada nos dados ainda."
    linhas = []
    for formato, rotulo in (("padrao", "Padrão"), ("livre", "Livre"), (None, "")):
        for grupo, titulo in grupos:
            itens = [carta for carta in cartas.get(grupo) or [] if carta.get("formato") == formato]
            if not itens:
                continue
            nomes = []
            for carta in itens:
                campos = [mudanca["campo"] for mudanca in carta.get("mudancas", [])]
                nomes.append(f"{carta.get('nome', '')} ({', '.join(campos)})")
            prefixo = f"{rotulo}, " if rotulo else ""
            linhas.append(f"{prefixo}{titulo}: " + "; ".join(nomes))
    return "\n".join(linhas)


def validar(topicos, texto_original: str) -> list[str]:
    if not isinstance(topicos, list) or not 3 <= len(topicos) <= 15:
        raise ErroResumo("resposta inválida")
    limpos = []
    palavras_originais = [palavra.casefold() for palavra in re.findall(r"\w+", texto_original)]
    for topico in topicos:
        if not isinstance(topico, str):
            raise ErroResumo("resposta inválida")
        topico = topico.strip()
        if not topico or len(topico) > 300 or re.search(r"<|>|http|www\.", topico, re.IGNORECASE):
            raise ErroResumo("resposta inválida")
        palavras = [palavra.casefold() for palavra in re.findall(r"\w+", topico)]
        copiou = any(
            palavras_originais[inicio:inicio + 10] == palavras[indice:indice + 10]
            for indice in range(max(0, len(palavras) - 9))
            for inicio in range(max(0, len(palavras_originais) - 9))
        )
        if not copiou:
            limpos.append(topico)
    if len(limpos) < 3:
        raise ErroResumo("resumo copiou a notícia")
    return limpos


def montar_mensagem(titulo: str, texto: str, idioma: str, cartas: dict | None, com_cartas: bool = True) -> str:
    """A mensagem que acompanha a instrução no pedido do resumo manual."""
    idioma_prompt = "português" if idioma in {"pt-br", "pt", "português"} else "inglês"
    mensagem = f"Notícia oficial ({idioma_prompt}): {titulo}\n\n{blizzard.sem_html(texto)[:60000]}"
    if com_cartas:
        mensagem += f"\n\nCartas alteradas segundo o diff dos dados:\n{_cartas(cartas)}"
    return mensagem
