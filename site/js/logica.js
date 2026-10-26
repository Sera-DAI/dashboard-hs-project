const CAMPOS_NUMERICOS = new Set([
  "custo",
  "ataque",
  "vida",
  "durabilidade",
  "armadura"
]);

const CLASSES = {
  DEATHKNIGHT: "Cavaleiro da Morte",
  DEMONHUNTER: "Caçador de Demônios",
  DRUID: "Druida",
  HUNTER: "Caçador",
  MAGE: "Mago",
  PALADIN: "Paladino",
  PRIEST: "Sacerdote",
  ROGUE: "Ladino",
  SHAMAN: "Xamã",
  WARLOCK: "Bruxo",
  WARRIOR: "Guerreiro",
  NEUTRAL: "Neutra"
};

export function nomeClasse(classe) {
  return CLASSES[classe] ?? String(classe ?? "");
}

export function normalizar(texto) {
  return String(texto ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR");
}

// Fora do Padrão e do Selvagem: cópias ocultas, heróis alternativos e o Formato Clássico.
const FORA_DA_BUSCA = new Set(["CORE_HIDDEN", "HERO_SKINS", "VANILLA"]);

function preferida(a, b) {
  if ((a.colecao === "CORE") !== (b.colecao === "CORE")) {
    return a.colecao === "CORE" ? a : b;
  }

  return Number(a.dbfId) >= Number(b.dbfId) ? a : b;
}

export function buscar(cartas, consulta, limite = 8) {
  const termo = normalizar(consulta.trim());

  if (termo.length < 2) {
    return [];
  }

  const porNome = new Map();

  for (const [dbfId, carta] of Object.entries(cartas ?? {})) {
    const nome = normalizar(carta.nome);

    if (FORA_DA_BUSCA.has(carta.colecao) || !nome.includes(termo)) {
      continue;
    }

    const atual = porNome.get(nome);
    porNome.set(nome, atual ? preferida(atual, { ...carta, dbfId }) : { ...carta, dbfId });
  }

  return [...porNome.values()]
    .sort((a, b) => {
      const aComeca = normalizar(a.nome).startsWith(termo);
      const bComeca = normalizar(b.nome).startsWith(termo);
      return Number(bComeca) - Number(aComeca) || a.nome.localeCompare(b.nome, "pt-BR");
    })
    .slice(0, limite);
}

export function higienizarTexto(marcacao) {
  const texto = String(marcacao ?? "")
    .replace(/^\s*\[x\]\s*/i, "")
    .replace(/&(?=\s|$)/g, "")
    .replace(/([$#])(?=\d)/g, "")
    .replace(/\r?\n/g, " ");
  const tokens = [];
  const regex = /<\/?(?:b|i)\s*>/gi;
  let inicio = 0;
  let atual;

  while ((atual = regex.exec(texto)) !== null) {
    if (atual.index > inicio) {
      tokens.push({ tipo: "texto", texto: texto.slice(inicio, atual.index) });
    }

    const tag = atual[0].match(/^<\/?([bi])/i)[1].toLowerCase();
    tokens.push({
      tipo: "tag",
      nome: tag,
      fechar: atual[0][1] === "/"
    });
    inicio = regex.lastIndex;
  }

  if (inicio < texto.length) {
    tokens.push({ tipo: "texto", texto: texto.slice(inicio) });
  }

  return tokens;
}

export function lerRota(hash) {
  const valor = String(hash ?? "").replace(/^#/, "");

  if (!valor) {
    return { tipo: "inicio" };
  }

  const patch = valor.match(/^patch\/(patches\/[^/]+\.json)$/);
  if (patch) {
    return { tipo: "patch", arquivo: patch[1] };
  }

  const noticia = valor.match(/^noticia\/(noticias\/[^/]+\.json)$/);
  if (noticia) {
    return { tipo: "noticia", arquivo: noticia[1] };
  }

  const carta = valor.match(/^carta\/(\d+)$/);
  if (carta) {
    return { tipo: "carta", dbfId: carta[1] };
  }

  return { tipo: "inicio" };
}

export function rotaPatch(arquivo) {
  return `#patch/${String(arquivo).replace(/^\/+/, "")}`;
}

export function rotaNoticia(arquivo) {
  return `#noticia/${String(arquivo).replace(/^\/+/, "")}`;
}

export function historicoDaCarta(dbfId, patches) {
  return [...(patches ?? [])]
    .filter((patch) => {
      const grupos = patch.cartas;
      return grupos && ["buffs", "nerfs", "alteradas"].some((grupo) =>
        (grupos[grupo] ?? []).some((carta) => String(carta.dbfId) === String(dbfId))
      );
    })
    .sort((a, b) => String(b.data).localeCompare(String(a.data)));
}

export function topicosDoResumo(patch) {
  const topicos = patch?.resumo_ia?.topicos;
  if (!Array.isArray(topicos) || topicos.some((topico) => typeof topico !== "string")) {
    return [];
  }
  return topicos;
}

export function fatia(lista, mostrados) {
  return (lista ?? []).slice(0, Math.max(0, mostrados));
}

export function formatarCampo(campo, valor) {
  if (valor === null || valor === undefined) {
    return "—";
  }

  if (campo === "texto") {
    return valor;
  }

  if (CAMPOS_NUMERICOS.has(campo)) {
    return String(valor);
  }

  return String(valor);
}

export async function carregarJson(url, fetcher = fetch) {
  const resposta = await fetcher(url);
  if (!resposta.ok) {
    const erro = new Error(`Falha ao carregar ${url}`);
    erro.status = resposta.status;
    throw erro;
  }
  return resposta.json();
}
