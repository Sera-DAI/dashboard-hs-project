import { carregarJson, prepararPatches, topicosDoResumo } from "./logica.js";

async function indiceOpcional(url, chave, fetcher) {
  try {
    const dados = await carregarJson(url, fetcher);
    if (!Array.isArray(dados?.[chave])) {
      throw new Error(`Índice inválido: ${url}`);
    }
    return dados[chave];
  } catch (erro) {
    if (erro.status === 404) {
      return [];
    }
    throw erro;
  }
}

async function imagensOpcionais(fetcher) {
  // As imagens oficiais são um extra: sem o arquivo, o site usa o HearthstoneJSON.
  try {
    const dados = await carregarJson("dados/imagens.json", fetcher);
    const imagens = dados?.imagens;
    return imagens && typeof imagens === "object" && !Array.isArray(imagens) ? imagens : {};
  } catch {
    return {};
  }
}

export async function carregarDados(fetcher = fetch) {
  const [indice, noticias, catalogo, imagens] = await Promise.all([
    indiceOpcional("dados/indice.json", "patches", fetcher),
    indiceOpcional("dados/noticias.json", "noticias", fetcher),
    carregarJson("dados/cartas.json", fetcher),
    imagensOpcionais(fetcher)
  ]);
  if (!catalogo?.cartas || typeof catalogo.cartas !== "object" || Array.isArray(catalogo.cartas)) {
    throw new Error("Catálogo inválido");
  }
  // Os índices são a única origem de caminhos; nunca usamos um hash em fetch.
  const lerItens = (itens, pasta) => Promise.all(itens.map(async (entrada) => {
    if (!new RegExp(`^${pasta}/[\\w.-]+\\.json$`).test(entrada?.arquivo)) {
      throw new Error(`Caminho inválido no índice de ${pasta}`);
    }
    const item = await carregarJson(`dados/${entrada.arquivo}`, fetcher);
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`Documento inválido: ${entrada.arquivo}`);
    }
    return { ...entrada, ...item };
  }));
  const [patches, documentos] = await Promise.all([
    lerItens(indice, "patches"),
    lerItens(noticias, "noticias")
  ]);
  return {
    cartas: catalogo.cartas,
    imagens,
    patches: prepararPatches(patches, catalogo.cartas),
    noticias: documentos.map((noticia) => ({ ...noticia, topicos: topicosDoResumo(noticia) }))
      .sort((a, b) => String(b.data).localeCompare(String(a.data)))
  };
}
