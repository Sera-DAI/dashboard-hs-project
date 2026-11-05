import {
  dividir,
  formatarCarta,
  formatarHistorico,
  formatarListaCartas,
  formatarListaNoticias,
  formatarNoticia,
  formatarPatch,
  formatarResultadosNoticias,
  formatarDecks,
  formatarMeta,
  letra,
  mensagemAjuda,
  mensagemIndisponivel,
  mensagemUsoDecks,
  normalizar,
  tituloDaResposta,
  versaoAtual
} from "./formatador.js";
import { lerClasse, links, nomeClasse } from "./meta.js";

const DASHBOARD_PADRAO = "https://dashboard-hs.pages.dev";

export function lerComando(texto) {
  const correspondencia = String(texto ?? "").trim().match(/^\/([\p{L}\p{M}]+)(?:@[\w]+)?(?:\s+([\s\S]*))?$/u);

  if (!correspondencia) {
    return { comando: "", argumento: "" };
  }

  return {
    comando: normalizar(correspondencia[1]),
    argumento: String(correspondencia[2] ?? "").trim()
  };
}

function arquivoPatch(patch) {
  return patch.arquivo;
}

function dataMaisAntiga(indice) {
  return [...(indice.patches ?? [])]
    .map((patch) => patch.data)
    .filter(Boolean)
    .sort()[0] ?? "";
}

async function patchesParaCarta(lerJson, indice) {
  return Promise.all((indice.patches ?? []).map((item) => lerJson(arquivoPatch(item))));
}

async function comandoPatch(argumento, lerJson, dashboard) {
  const indice = await lerJson("indice.json");
  const patches = indice.patches ?? [];
  const escolhido = argumento
    ? patches.find((item) => String(item.versao).toLocaleLowerCase("pt-BR") === argumento.toLocaleLowerCase("pt-BR"))
    : patches[0];

  if (!escolhido) {
    const recentes = patches.slice(0, 5).map((item) => item.versao).join(", ");
    return `Não achei o patch ${argumento}. Os mais recentes: ${recentes}.\nUse /patch para o mais recente ou /historico para a lista.`;
  }

  const patch = await lerJson(arquivoPatch(escolhido));
  return formatarPatch(patch, arquivoPatch(escolhido), dashboard);
}

async function comandoCarta(argumento, lerJson, dashboard) {
  if (argumento.length < 2) {
    return "Use /carta seguido do nome, por exemplo: /carta Leeroy Jenkins";
  }

  const [indiceBusca, indice] = await Promise.all([
    lerJson("busca.json"),
    lerJson("indice.json")
  ]);
  const consulta = normalizar(argumento);
  const nomes = new Map();

  for (const [dbfId, nome, busca] of indiceBusca.cartas ?? []) {
    if (!busca.includes(consulta)) {
      continue;
    }

    if (!nomes.has(busca)) {
      nomes.set(busca, { nome, busca, ids: [] });
    }

    nomes.get(busca).ids.push(String(dbfId));
  }

  const grupos = [...nomes.values()];
  const escolhido = nomes.get(consulta) ?? (grupos.length === 1 ? grupos[0] : null);

  if (!escolhido) {
    grupos.sort((a, b) => {
      const aComeca = a.busca.startsWith(consulta);
      const bComeca = b.busca.startsWith(consulta);
      return Number(bComeca) - Number(aComeca) || a.nome.localeCompare(b.nome, "pt-BR");
    });
    return formatarListaCartas(argumento, grupos.slice(0, 10), grupos.length);
  }

  const [arquivoLetra, patches] = await Promise.all([
    lerJson(`cartas/${letra(escolhido.busca)}.json`),
    patchesParaCarta(lerJson, indice)
  ]);
  const cartas = escolhido.ids
    .filter((dbfId) => arquivoLetra.cartas?.[dbfId])
    .map((dbfId) => ({ ...arquivoLetra.cartas[dbfId], dbfId }));

  if (cartas.length === 0) {
    throw new Error("Carta ausente no arquivo da letra.");
  }

  return formatarCarta(versaoAtual(cartas), patches, dashboard, dataMaisAntiga(indice));
}

async function comandoHistorico(lerJson, dashboard) {
  const indice = await lerJson("indice.json");
  const patches = await Promise.all((indice.patches ?? []).slice(0, 10).map(async (item) => {
    if ((item.buffs ?? 0) + (item.nerfs ?? 0) + (item.alteradas ?? 0) + (item.revisadas ?? 0) !== 0) {
      return item;
    }

    const patch = await lerJson(arquivoPatch(item));
    return { ...item, cartasIndisponiveis: patch.cartas === null };
  }));

  return formatarHistorico(patches, dashboard);
}

async function comandoNoticias(argumento, lerJson, dashboard) {
  const indice = await lerJson("noticias.json");
  const noticias = indice.noticias ?? [];

  if (!argumento) {
    return formatarListaNoticias(noticias);
  }

  if (/^\d+$/.test(argumento)) {
    const posicao = Number(argumento);
    const noticia = noticias[posicao - 1];

    if (!noticia) {
      return `A lista tem ${noticias.length} notícias. Use /noticias para ver os números.`;
    }

    const detalhe = await lerJson(noticia.arquivo);
    return formatarNoticia(detalhe, noticia.arquivo, dashboard);
  }

  const termo = normalizar(argumento);
  const resultados = noticias
    .map((noticia, indiceNoticia) => ({ ...noticia, numero: indiceNoticia + 1 }))
    .filter((noticia) => normalizar(noticia.titulo).includes(termo));

  if (resultados.length === 1) {
    const detalhe = await lerJson(resultados[0].arquivo);
    return formatarNoticia(detalhe, resultados[0].arquivo, dashboard);
  }

  return formatarResultadosNoticias(argumento, resultados.slice(0, 10), resultados.length);
}

function comandoDecks(argumento) {
  const resultado = lerClasse(argumento);

  if (!resultado.classe) {
    return mensagemUsoDecks(resultado.desconhecida);
  }

  const formatos = resultado.formato ? [resultado.formato] : ["padrao", "wild"];
  const dados = Object.fromEntries(formatos.map((formato) => [formato, links(resultado.classe, formato)]));
  return formatarDecks(nomeClasse(resultado.classe), dados, Boolean(resultado.formato));
}

export async function responder(texto, lerJson, config = {}) {
  const { comando, argumento } = lerComando(texto);
  const dashboard = config.dashboard ?? DASHBOARD_PADRAO;
  let resposta;

  try {
    if (comando === "patch") {
      resposta = await comandoPatch(argumento, lerJson, dashboard);
    } else if (comando === "carta") {
      resposta = await comandoCarta(argumento, lerJson, dashboard);
    } else if (comando === "historico") {
      resposta = await comandoHistorico(lerJson, dashboard);
    } else if (comando === "noticias") {
      resposta = await comandoNoticias(argumento, lerJson, dashboard);
    } else if (comando === "decks") {
      resposta = comandoDecks(argumento);
    } else if (comando === "meta") {
      const resultado = lerClasse(argumento);
      const formato = resultado.formato ?? "padrao";
      const dados = links(resultado.classe ?? "MAGE", formato);
      resposta = formatarMeta(
        formato,
        resultado.classe ? nomeClasse(resultado.classe) : "",
        dados,
        resultado.desconhecida
      );
    } else {
      resposta = mensagemAjuda(dashboard, comando !== "start" && comando !== "ajuda");
    }
  } catch {
    resposta = mensagemIndisponivel();
  }

  return dividir(resposta, tituloDaResposta(resposta));
}
