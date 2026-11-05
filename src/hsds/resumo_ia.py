"""Geração e validação do resumo por IA via Gemini."""

import json
import re
import urllib.error
import time
import urllib.request
from collections.abc import Callable

from hsds import blizzard, http

MODELO = "gemini-3.8-flash"
# Reservas, na ordem, quando o modelo principal recusa por limite de uso (429) ou não responde (5xx, conexão). Cada modelo tem a sua cota.
MODELOS_RESERVA = ("gemini-3.6-flash", "gemini-3.5-flash-lite")
# Se o modelo anterior já gastou mais que isto, o serviço está lento e outra tentativa só alonga a execução: desiste.
LIMITE_PARA_RESERVA = 60.0
_relogio = time.monotonic
ENDERECO = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
INSTRUCAO = """Você escreve resumos de notícias e patches do jogo Hearthstone para um monitor pessoal em português do Brasil.

Regras:
1. Escreva de 4 a 12 tópicos, cada um com no máximo 260 caracteres, em português do Brasil.
2. Cubra todas as seções da notícia, não só as cartas. Confira uma por uma, quando houver: mudanças de cartas e classes; modos de jogo (Campos de Batalha, Arena, Mercenários e outros); loja e itens à venda, como o Cofre da Taverna e pacotes; recompensas, presentes gratuitos e brindes no Battle.net; receitas de deck; eventos, temporadas e datas; correções de bugs e problemas conhecidos.
3. Comece cada tópico por um emoji que combine com o assunto daquele tópico, um espaço e o assunto seguido de dois-pontos, por exemplo "🛒 Loja: ...", "🎁 Presente: ...", "📜 Receitas de deck: ...", "⚔️ Arena: ...", "🐛 Correções: ...". Use um emoji só por tópico, sempre no começo. Um assunto grande pode ocupar mais de um tópico.
4. Use as suas próprias palavras. Nunca copie frases da notícia; reescreva a ideia.
5. Não cite custo, ataque, vida, durabilidade, armadura nem outros números de cartas: esses números são mostrados à parte. Pode citar o nome das cartas e dizer se ficaram mais fortes ou mais fracas. Datas, preços e quantidades de recompensas podem ser citados.
6. Sem HTML, sem markdown, sem links, sem emojis fora do começo do tópico e sem opinião sobre o meta.
7. Se a notícia não trouxer informação suficiente, escreva menos tópicos, nunca invente.
8. Responda só com o JSON pedido."""
ESQUEMA = {
    "type": "OBJECT",
    "properties": {"topicos": {"type": "ARRAY", "items": {"type": "STRING"}}},
    "required": ["topicos"],
}


class ErroResumo(Exception):
    """Falha segura sem detalhes da requisição, resposta ou chave."""

    def __init__(self, motivo: str, tentar_outro_modelo: bool = False):
        super().__init__(motivo)
        self.motivo = motivo
        # Verdadeiro só para falha do serviço (limite, 5xx, conexão); resposta inválida ou chave recusada não melhoram trocando o modelo.
        self.tentar_outro_modelo = tentar_outro_modelo


class Topicos(list):
    """Os tópicos do resumo, com o nome do modelo que os gerou em `.modelo`."""

    modelo: str = MODELO


def _abrir_padrao(requisicao: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(requisicao, timeout=180) as resposta:
        return resposta.read()


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
    """A mensagem do usuário enviada ao modelo; o resumo manual (D48) usa a mesma, para o resultado ser comparável."""
    idioma_prompt = "português" if idioma in {"pt-br", "pt", "português"} else "inglês"
    mensagem = f"Notícia oficial ({idioma_prompt}): {titulo}\n\n{blizzard.sem_html(texto)[:60000]}"
    if com_cartas:
        mensagem += f"\n\nCartas alteradas segundo o diff dos dados:\n{_cartas(cartas)}"
    return mensagem


def gerar(
    titulo: str,
    texto: str,
    idioma: str,
    cartas: dict | None,
    chave: str,
    abrir: Callable[[urllib.request.Request], bytes] = _abrir_padrao,
    com_cartas: bool = True,
) -> list[str]:
    if not chave:
        raise ErroResumo("chave GEMINI_API_KEY ausente")
    mensagem = montar_mensagem(titulo, texto, idioma, cartas, com_cartas)
    corpo = {
        "systemInstruction": {"parts": [{"text": INSTRUCAO}]},
        "contents": [{"role": "user", "parts": [{"text": mensagem}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": ESQUEMA,
            "temperature": 0.3,
        },
    }
    erro_final: ErroResumo | None = None
    inicio = _relogio()
    for modelo in (MODELO, *MODELOS_RESERVA):
        if erro_final is not None and _relogio() - inicio > LIMITE_PARA_RESERVA:
            break
        try:
            topicos = Topicos(_pedir(modelo, corpo, chave, abrir, blizzard.sem_html(texto)))
        except ErroResumo as erro:
            # O motivo mostrado é sempre o do modelo principal; a reserva só entra em ação, não no diagnóstico.
            erro_final = erro_final or erro
            if not erro.tentar_outro_modelo:
                raise erro_final
            continue
        topicos.modelo = modelo
        return topicos
    raise erro_final


def _pedir(modelo: str, corpo: dict, chave: str, abrir: Callable[[urllib.request.Request], bytes], texto_limpo: str) -> list[str]:
    requisicao = urllib.request.Request(
        ENDERECO.format(modelo=modelo),
        data=json.dumps(corpo, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": http.AGENTE, "x-goog-api-key": chave},
        method="POST",
    )
    try:
        bruto = abrir(requisicao)
    except urllib.error.HTTPError as erro:
        # O código HTTP não é segredo e separa modelo inexistente (404) de chave recusada (401/403) e de serviço fora do ar (5xx).
        if erro.code == 429:
            raise ErroResumo(f"limite de uso atingido (HTTP {erro.code})", True) from None
        if erro.code >= 500:
            raise ErroResumo(f"serviço fora do ar ou sem resposta (HTTP {erro.code})", True) from None
        # 404 é modelo que deixou de existir: vale tentar a reserva. Os demais 4xx (chave, pedido) não mudam com o modelo.
        if erro.code == 404:
            raise ErroResumo(f"modelo indisponível (HTTP {erro.code})", True) from None
        raise ErroResumo(f"chave recusada ou pedido inválido (HTTP {erro.code})") from None
    except (urllib.error.URLError, OSError):
        raise ErroResumo("serviço fora do ar ou sem resposta (falha de conexão)", True) from None
    try:
        resposta = json.loads(bruto)
        texto_resposta = resposta["candidates"][0]["content"]["parts"][0]["text"]
        dados = json.loads(texto_resposta)
    except (ValueError, KeyError, IndexError, TypeError, UnicodeError):
        raise ErroResumo("resposta inválida") from None
    return validar(dados.get("topicos") if isinstance(dados, dict) else None, texto_limpo)
