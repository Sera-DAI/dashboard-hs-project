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

// Fora do Padrão e do Wild: cópias ocultas, heróis alternativos e o Formato Clássico.
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

  const pagina = valor.match(/^\/(patches|cartas|noticias|meta)(?:\/([^/]+))?\/?$/);
  if (pagina) {
    if (pagina[1] === "patches" && pagina[2]) {
      try {
        return { tipo: "patches", versao: decodeURIComponent(pagina[2]) };
      } catch {
        return { tipo: "patches" };
      }
    }
    return { tipo: pagina[1] };
  }
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
      return grupos && ["buffs", "nerfs", "alteradas", "revisadas"].some((grupo) =>
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
export const GRUPOS = [["buffs", "Buffs"], ["nerfs", "Nerfs"], ["alteradas", "Alteradas"]];
// D46: o texto alterado volta às listas, como quarto grupo, e cada patch separa o Padrão do Livre.
export const GRUPOS_COMPLETOS = [...GRUPOS, ["revisadas", "Texto alterado"]];
export const FORMATOS = [["padrao", "Padrão"], ["livre", "Livre"]];
const ROTULO_GRUPO = { buffs: "buff", nerfs: "nerf", alteradas: "alterada", revisadas: "texto" };

export function rotuloDoGrupo(grupo) {
  return ROTULO_GRUPO[grupo] ?? String(grupo);
}

// No histórico da carta o grupo aparece no plural, como sempre; só o texto alterado ganha nome legível.
export function nomeDoGrupo(grupo) {
  return grupo === "revisadas" ? "texto alterado" : String(grupo);
}

function contarGrupos(cartas) {
  return {
    cartas,
    buffs: cartas.filter((carta) => carta.grupo === "buffs").length,
    nerfs: cartas.filter((carta) => carta.grupo === "nerfs").length,
    alteradas: cartas.filter((carta) => carta.grupo === "alteradas").length,
    revisadas: cartas.filter((carta) => carta.grupo === "revisadas").length
  };
}

// As seções do patch: Padrão e Livre quando o diff traz o formato de cada carta; senão uma lista só.
export function secoesDoPatch(patch) {
  const cartas = patch?.cartas ?? [];
  if (!cartas.some((carta) => carta.formato)) {
    return [{ chave: "todas", rotulo: "Cartas alteradas", ...contarGrupos(cartas) }];
  }
  const secoes = FORMATOS.map(([chave, rotulo]) => ({
    chave,
    rotulo,
    ...contarGrupos(cartas.filter((carta) => carta.formato === chave))
  }));
  const sem = cartas.filter((carta) => !FORMATOS.some(([chave]) => chave === carta.formato));
  if (sem.length) {
    secoes.push({ chave: "sem", rotulo: "Sem formato definido", ...contarGrupos(sem) });
  }
  return secoes;
}

const ATRIBUTOS = ["custo", "ataque", "vida", "durabilidade", "armadura", "texto"];

export function rotaVersao(versao) {
  return `#/patches/${encodeURIComponent(versao)}`;
}

// O diff só guarda campos alterados. Desfazemos TODOS os diffs, inclusive
// revisadas, para reconstruir cada data sem emprestar números da build atual.
export function prepararPatches(patches, cartas = {}) {
  const estados = new Map(Object.entries(cartas).map(([id, carta]) => [String(id), { ...carta }]));
  return [...patches].sort((a, b) => String(b.data).localeCompare(String(a.data))).map((patch) => {
    const visiveis = [];
    for (const grupo of GRUPOS_COMPLETOS.map(([chave]) => chave)) {
      for (const carta of patch.cartas?.[grupo] ?? []) {
        const id = String(carta.dbfId);
        const atual = cartas[id] ?? {};
        const depois = { ...(estados.get(id) ?? carta) };
        for (const mudanca of carta.mudancas ?? []) {
          if (ATRIBUTOS.includes(mudanca.campo)) {
            depois[mudanca.campo] = mudanca.depois;
          }
        }
        const antes = { ...depois };
        for (const mudanca of carta.mudancas ?? []) {
          if (ATRIBUTOS.includes(mudanca.campo)) {
            antes[mudanca.campo] = mudanca.antes;
          }
        }
        estados.set(id, antes);
        visiveis.push({
          ...atual,
          ...carta,
          id: atual.id,
          grupo,
          versao: patch.versao,
          data: patch.data,
          antes,
          depois,
          historica: ATRIBUTOS.some((campo) => depois[campo] !== atual[campo])
        });
      }
    }
    return {
      ...patch,
      cartas: visiveis,
      topicos: topicosDoResumo(patch),
      link: patch.noticia?.link ?? patch.noticia_en?.link,
      buffs: visiveis.filter((carta) => carta.grupo === "buffs").length,
      nerfs: visiveis.filter((carta) => carta.grupo === "nerfs").length,
      alteradas: visiveis.filter((carta) => carta.grupo === "alteradas").length,
      revisadas: visiveis.filter((carta) => carta.grupo === "revisadas").length
    };
  });
}

const ENDERECO_OFICIAL = "https://d15f34w2p8l1cc.cloudfront.net/hearthstone/";

export function imagemDaCarta(carta, versao = "depois", densidade = 1, imagens = {}) {
  if (versao !== "depois") {
    return null;
  }
  // A imagem oficial (D40) vem de dados/imagens.json; só um hash exato de 64 caracteres vira endereço.
  const hash = carta.dbfId == null ? null : imagens?.[String(carta.dbfId)];
  if (typeof hash === "string" && /^[0-9a-f]{64}$/.test(hash)) {
    return `${ENDERECO_OFICIAL}${hash}.png`;
  }
  // O render do HearthstoneJSON só mostra a carta de hoje: em carta já alterada depois do patch, vale o desenho próprio.
  if (carta.historica || !/^[A-Za-z0-9_]+$/.test(carta.id ?? "")) {
    return null;
  }
  const tamanho = densidade > 1 ? "512x" : "256x";
  return `https://art.hearthstonejson.com/v1/render/latest/ptBR/${tamanho}/${carta.id}.png`;
}

export function marcaMudanca(carta, versao, campo) {
  const antes = carta.antes?.[campo];
  const depois = carta.depois?.[campo];
  if (versao === "antes" || antes == null || depois == null || antes === depois || !CAMPOS_NUMERICOS.has(campo)) {
    return "";
  }
  return (depois > antes) === (campo !== "custo") ? "buff" : "nerf";
}

export function filtrarCarta(carta, consulta, grupo = "todas") {
  // O filtro vale para o grupo (buffs, nerfs...) ou para o formato (padrao, livre).
  return (grupo === "todas" || carta.grupo === grupo || carta.formato === grupo) && normalizar(carta.nome).includes(normalizar(consulta).trim());
}

export function assuntoNoticia(titulo) {
  if (/campeonato|playoffs|e-sports|esports|mundial/i.test(titulo)) {
    return ["esports", "Esports"];
  }
  if (/campos de batalha|aberrações/i.test(titulo)) {
    return ["campos", "Campos de Batalha"];
  }
  if (/oferta|trilha|recompensa|loja|cofre/i.test(titulo)) {
    return ["loja", "Loja e recompensas"];
  }
  if (/evento|jornada|cards de teste/i.test(titulo)) {
    return ["evento", "Eventos"];
  }
  return ["expansao", "Expansões"];
}
