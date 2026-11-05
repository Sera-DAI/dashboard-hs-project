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

// A carga é em duas etapas (D50): a base (patches e notícias, poucos KB) monta a página; o catálogo de cartas e
// as imagens oficiais (mais de 500 KB) só entram quando a página precisa de uma carta.
export async function carregarBase(fetcher = fetch) {
  const [indice, noticias] = await Promise.all([
    indiceOpcional("dados/indice.json", "patches", fetcher),
    indiceOpcional("dados/noticias.json", "noticias", fetcher)
  ]);
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
  return { patches, noticias: documentos };
}

export async function carregarCatalogo(fetcher = fetch) {
  const [catalogo, imagens] = await Promise.all([
    carregarJson("dados/cartas.json", fetcher),
    imagensOpcionais(fetcher)
  ]);
  if (!catalogo?.cartas || typeof catalogo.cartas !== "object" || Array.isArray(catalogo.cartas)) {
    throw new Error("Catálogo inválido");
  }
  return { cartas: catalogo.cartas, imagens };
}

// Sem o catálogo, os patches saem só com o que o próprio documento traz (nome, classe e mudanças): basta para as contagens.
export function combinarDados(base, catalogo = { cartas: {}, imagens: {} }) {
  return {
    cartas: catalogo.cartas,
    imagens: catalogo.imagens,
    patches: prepararPatches(base.patches, catalogo.cartas),
    noticias: base.noticias.map((noticia) => ({ ...noticia, topicos: topicosDoResumo(noticia) }))
      .sort((a, b) => String(b.data).localeCompare(String(a.data)))
  };
}

export async function carregarDados(fetcher = fetch) {
  const [base, catalogo] = await Promise.all([carregarBase(fetcher), carregarCatalogo(fetcher)]);
  return combinarDados(base, catalogo);
}
