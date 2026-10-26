"""Arquivos derivados de cartas.json para o bot (M3): índice de busca e cartas por letra.

O Worker do Cloudflare tem 10 ms de CPU por pedido no plano gratuito, e ler o
cartas.json inteiro passa disso. O bot lê o busca.json, pequeno, e só o arquivo
da letra da carta escolhida.
"""

import unicodedata
from pathlib import Path

# Coleções fora do Padrão e do Selvagem: cópias ocultas, heróis alternativos e o Formato Clássico.
FORA_DA_BUSCA = frozenset({"CORE_HIDDEN", "HERO_SKINS", "VANILLA"})
# Sobe quando muda o que entra nos derivados, para o monitor gravá-los de novo na mesma build.
FORMATO = 2


def normalizar(nome: str) -> str:
    decomposto = unicodedata.normalize("NFD", nome)
    sem_acento = "".join(caractere for caractere in decomposto if not "̀" <= caractere <= "ͯ")
    return sem_acento.lower()


def letra(busca: str) -> str:
    inicial = busca[:1]
    if "a" <= inicial <= "z":
        return inicial
    return "outros"


def arquivos(raiz: Path, cartas: dict) -> dict[Path, dict]:
    build = cartas["build"]
    indice = []
    grupos = {}
    for dbf_id, carta in cartas["cartas"].items():
        if carta.get("colecao") in FORA_DA_BUSCA:
            continue
        busca = normalizar(carta["nome"])
        indice.append([dbf_id, carta["nome"], busca])
        grupos.setdefault(letra(busca), {})[dbf_id] = carta
    indice.sort(key=lambda item: (item[2], int(item[0])))
    resultado = {raiz / "busca.json": {"build": build, "formato": FORMATO, "cartas": indice}}
    for nome in sorted(grupos):
        resultado[raiz / "cartas" / f"{nome}.json"] = {"build": build, "cartas": grupos[nome]}
    return resultado


def desatualizados(raiz: Path, ler) -> dict[Path, dict]:
    """Gera de novo os derivados quando faltam, são de outra build que a do cartas.json ou de outro formato."""
    cartas = ler(raiz / "cartas.json")
    if cartas is None:
        return {}
    indice = ler(raiz / "busca.json", {})
    if indice.get("build") == cartas["build"] and indice.get("formato") == FORMATO:
        return {}
    return arquivos(raiz, cartas)
