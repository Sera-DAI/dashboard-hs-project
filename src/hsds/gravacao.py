"""Prepara todos os JSON antes de substituir arquivos; desfaz falhas de escrita."""

import json
import os
import tempfile
from pathlib import Path


def ler(caminho: Path, padrao=None):
    if not caminho.exists():
        return padrao
    return json.loads(caminho.read_text(encoding="utf-8"))


def _temporario(caminho: Path, bruto: bytes) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descritor, nome = tempfile.mkstemp(prefix=".hsds-", dir=caminho.parent)
    temporario = Path(nome)
    try:
        with os.fdopen(descritor, "wb") as arquivo:
            arquivo.write(bruto)
            arquivo.flush()
            os.fsync(arquivo.fileno())
    except BaseException:
        temporario.unlink(missing_ok=True)
        raise
    return temporario


def gravar(arquivos: dict[Path, dict]) -> None:
    preparados = {}
    anteriores = {}
    substituidos = []
    try:
        for caminho, dados in arquivos.items():
            bruto = (json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
            anteriores[caminho] = caminho.read_bytes() if caminho.exists() else None
            preparados[caminho] = _temporario(caminho, bruto)
        for caminho, temporario in preparados.items():
            os.replace(temporario, caminho)
            substituidos.append(caminho)
    except BaseException:
        for caminho in reversed(substituidos):
            bruto = anteriores[caminho]
            if bruto is None:
                caminho.unlink(missing_ok=True)
            else:
                restauracao = _temporario(caminho, bruto)
                try:
                    os.replace(restauracao, caminho)
                finally:
                    restauracao.unlink(missing_ok=True)
        raise
    finally:
        for temporario in preparados.values():
            temporario.unlink(missing_ok=True)
