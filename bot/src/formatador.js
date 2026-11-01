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

const CAMPOS = [
  ["custo", "custo"],
  ["ataque", "ataque"],
  ["vida", "vida"],
  ["durabilidade", "durabilidade"],
  ["armadura", "armadura"]
];

export function normalizar(texto) {
  return String(texto ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR");
}

export function semMarcacao(texto) {
  return String(texto ?? "")
    .replace(/^\s*\[x\]\s*/i, "")
    .replace(/<\/?(?:b|i)\s*>/gi, "")
    .replace(/&(?=\s|$)/g, "")
    .replace(/([$#])(?=\d)/g, "")
    .replace(/\r?\n/g, " ");
}

export function blocoResumo(dado) {
  const topicos = dado?.resumo_ia?.topicos;

  if (!Array.isArray(topicos) || topicos.length === 0 || topicos.some((item) => typeof item !== "string")) {
    return "";
  }

  return `Resumo gerado por IA\n\n${topicos.join("\n\n")}`;
}

function formatarMudanca(mudanca) {
  if (mudanca.campo === "texto") {
    return `texto novo: ${semMarcacao(mudanca.depois)}`;
  }

  return `${mudanca.campo} ${mudanca.antes} → ${mudanca.depois}`;
}

function linhaCarta(carta) {
  return `• ${carta.nome}: ${(carta.mudancas ?? []).map(formatarMudanca).join(", ")}`;
}

export function blocoCartas(cartas) {
  if (!cartas) {
    return "Lista de cartas indisponível para este patch.";
  }

  const grupos = [
    ["buffs", "Buffs"],
    ["nerfs", "Nerfs"],
    ["alteradas", "Alteradas"]
  ];
  const partes = [];

  for (const [chave, titulo] of grupos) {
    const lista = [...(cartas[chave] ?? [])].sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));

    if (lista.length > 0) {
      partes.push(`${titulo} (${lista.length})\n${lista.map(linhaCarta).join("\n")}`);
    }
  }

  return partes.length > 0 ? partes.join("\n\n") : "Nenhuma carta colecionável mudou.";
}

function dataPt(data) {
  const [ano, mes, dia] = String(data ?? "").slice(0, 10).split("-");
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : String(data ?? "");
}

function noticiaDoPatch(patch) {
  return patch.noticia ?? patch.noticia_en ?? null;
}

export function formatarPatch(patch, arquivo, dashboard) {
  const noticia = noticiaDoPatch(patch);
  const cabecalho = `Hearthstone DS: patch ${patch.versao} (${dataPt(patch.data)})`;
  const tituloLink = noticia
    ? `${noticia.titulo}\n${noticia.link}`
    : "Notícias: https://hearthstone.blizzard.com/pt-br/news";
  const resumo = patch.noticia?.resumo ? semMarcacao(patch.noticia.resumo) : "";
  const partes = [cabecalho, tituloLink, resumo, blocoResumo(patch), blocoCartas(patch.cartas)];

  partes.push(`Ver no dashboard: ${dashboard}/#patch/${arquivo}`);
  return partes.filter((parte) => parte !== "").join("\n\n");
}

// Fora do Padrão e do Wild: cópias ocultas, heróis alternativos e o Formato Clássico.
const FORA_DA_BUSCA = new Set(["CORE_HIDDEN", "HERO_SKINS", "VANILLA"]);

export function letra(busca) {
  const inicial = String(busca ?? "").slice(0, 1);
  return inicial >= "a" && inicial <= "z" ? inicial : "outros";
}

function preferida(a, b) {
  if ((a.colecao === "CORE") !== (b.colecao === "CORE")) {
    return a.colecao === "CORE" ? a : b;
  }

  return Number(a.dbfId) >= Number(b.dbfId) ? a : b;
}

export function versaoAtual(cartas) {
  const jogaveis = cartas.filter((carta) => !FORA_DA_BUSCA.has(carta.colecao));
  const candidatas = jogaveis.length > 0 ? jogaveis : cartas;

  return {
    carta: candidatas.reduce(preferida),
    ids: candidatas.map((carta) => String(carta.dbfId))
  };
}

function linhaAtributos(carta) {
  return CAMPOS
    .filter(([campo]) => carta[campo] !== null && carta[campo] !== undefined)
    .map(([campo, nome]) => `${nome[0].toLocaleUpperCase("pt-BR")}${nome.slice(1)} ${carta[campo]}`)
    .join(" · ");
}

function mudancasDaCarta(ids, patch) {
  const grupos = [
    ["buffs", "buff"],
    ["nerfs", "nerf"],
    ["alteradas", "alterada"]
  ];
  const linhas = [];

  for (const [chave, tipo] of grupos) {
    const carta = (patch.cartas?.[chave] ?? []).find((item) => ids.includes(String(item.dbfId)));

    if (carta) {
      linhas.push(`• Patch ${patch.versao} (${dataPt(patch.data)}), ${tipo}: ${(carta.mudancas ?? []).map(formatarMudanca).join(", ")}`);
    }
  }

  return linhas;
}

export function formatarCarta(versao, patches, dashboard, dataMaisAntiga) {
  const carta = versao.carta;
  const classe = CLASSES[carta.classe] ?? String(carta.classe ?? "");
  const mudancas = patches
    .slice()
    .sort((a, b) => String(b.data).localeCompare(String(a.data)))
    .flatMap((patch) => mudancasDaCarta(versao.ids, patch));
  const linhas = [`${carta.nome} · ${classe}`, linhaAtributos(carta)];

  if (carta.texto) {
    linhas.push(semMarcacao(carta.texto));
  }

  linhas.push("", "Mudanças nos patches gravados");
  linhas.push(...(mudancas.length > 0
    ? mudancas
    : [`Nenhuma mudança nos patches gravados desde ${dataPt(dataMaisAntiga)}.`]));
  linhas.push("", `Ver no dashboard: ${dashboard}/#carta/${carta.dbfId}`);
  return linhas.filter((linha, indice) => linha !== "" || (indice > 0 && linhas[indice - 1] !== "")).join("\n");
}

export function formatarListaCartas(consulta, resultados, total) {
  if (total === 0) {
    return `Não achei carta com "${consulta}". Confira o nome ou tente só uma parte dele.`;
  }

  const aviso = total > 10 ? " Mostrando 10." : "";
  return `Achei ${total} cartas com "${consulta}". Mande /carta com o nome completo:${aviso}\n${resultados.map((carta) => `• ${carta.nome}`).join("\n")}`;
}

export function formatarHistorico(patches, dashboard) {
  const linhas = ["Hearthstone DS: últimos patches", ""];

  for (const patch of patches.slice(0, 10)) {
    if (patch.cartasIndisponiveis) {
      linhas.push(`• ${patch.versao} (${dataPt(patch.data)}): lista de cartas indisponível`);
      continue;
    }

    const grupos = [
      [patch.buffs ?? 0, "buff", "buffs"],
      [patch.nerfs ?? 0, "nerf", "nerfs"],
      [patch.alteradas ?? 0, "alterada", "alteradas"]
    ];
    linhas.push(`• ${patch.versao} (${dataPt(patch.data)}): ${grupos.map(([quantidade, singular, plural]) => `${quantidade} ${quantidade === 1 ? singular : plural}`).join(", ")}`);
  }

  linhas.push("", "Use /patch <versão> para ver um deles.", dashboard);
  return linhas.join("\n");
}

function itemNoticia(numero, noticia) {
  return `${numero}. ${noticia.titulo}\n📅 ${dataPt(noticia.data)}`;
}

export function formatarListaNoticias(noticias) {
  const itens = noticias.slice(0, 10).map((noticia, indice) => itemNoticia(indice + 1, noticia));
  return [
    "Hearthstone DS: últimas notícias",
    ...itens,
    "Para ler o resumo de uma delas, mande /noticias com o número (por exemplo, /noticias 1) ou com uma palavra do título."
  ].join("\n\n");
}

export function formatarNoticia(noticia, arquivo, dashboard) {
  const resumo = blocoResumo(noticia) || "O resumo por IA desta notícia ainda não foi gerado.";
  return `${noticia.titulo}\n${dataPt(noticia.publicada ?? noticia.data)}\n${noticia.link}\n\n${resumo}\n\nVer no dashboard: ${dashboard}/#noticia/${arquivo}`;
}

export function formatarResultadosNoticias(busca, resultados, total) {
  if (total === 0) {
    return `Não achei notícia com "${busca}" no título. Use /noticias para ver as mais recentes.`;
  }

  const itens = resultados.slice(0, 10).map((noticia) => itemNoticia(noticia.numero, noticia));
  return [
    `Achei ${total} notícias com "${busca}":`,
    ...itens,
    "Para ler o resumo de uma delas, mande /noticias com o número."
  ].join("\n\n");
}

export function mensagemAjuda(dashboard, desconhecido = false) {
  const aviso = desconhecido ? "Não conheço esse comando.\n\n" : "";
  return `${aviso}Hearthstone DS: comandos\n\n/patch: último patch, ou /patch 36.4 para outro\n/carta <nome>: ficha da carta e as mudanças dela\n/historico: últimos 10 patches\n/noticias: últimas notícias, ou /noticias <número ou palavra>\n/decks <classe>: links de decks no HSReplay e no HSGuru, Padrão e Wild, ou /decks <classe> wild\n/meta: links das estatísticas do meta\n/ajuda: esta lista\n\nDashboard: ${dashboard}`;
}

function dataBrasilia(data) {
  const dataObjeto = new Date(data);

  if (Number.isNaN(dataObjeto.getTime())) {
    return String(data ?? "");
  }

  const dataBrasilia = new Date(dataObjeto.getTime() - 3 * 60 * 60 * 1000);

  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: "UTC",
    day: "2-digit",
    month: "2-digit",
    year: "numeric"
  }).format(dataBrasilia);
}

const FILTROS_HSGURU = "Filtros do HSGuru: Diamante até Lenda, últimas 2 semanas, mínimo de 100 jogos.";

function nomeDoFormato(formato) {
  return formato === "wild" ? "Wild" : "Padrão";
}

// formatos: { padrao: links, wild: links } com o que deve aparecer; um só quando o responsável pede o formato
export function formatarDecks(classe, formatos, comFormato = false) {
  const entradas = Object.entries(formatos);
  const titulo = comFormato
    ? `Hearthstone DS: decks de ${classe} no ${nomeDoFormato(entradas[0][0])}`
    : `Hearthstone DS: decks de ${classe}`;
  const blocos = entradas.map(([formato, dados]) => [
    ...(comFormato ? [] : [nomeDoFormato(formato)]),
    `HSReplay: ${dados.hsreplayDecks}`,
    `HSGuru: ${dados.hsguruDecks}`
  ].join("\n"));
  const dica = comFormato ? "" : `\n\nSó um formato: /decks ${classe.toLocaleLowerCase("pt-BR")} wild ou /decks ${classe.toLocaleLowerCase("pt-BR")} padrão.`;

  return [titulo, ...blocos, FILTROS_HSGURU].join("\n\n") + dica;
}

export function mensagemUsoDecks(desconhecida = "") {
  const aviso = desconhecida ? `Não conheço a classe "${desconhecida}".\n` : "";
  return `${aviso}Use /decks com uma classe, por exemplo /decks mago ou /decks dh wild.\nClasses: cavaleiro da morte (dk), caçador de demônios (dh), druida, caçador, mago, paladino, sacerdote, ladino, xamã, bruxo, guerreiro.`;
}

export function formatarMeta(formato, classe, links, desconhecida = "") {
  const nomeFormato = nomeDoFormato(formato);
  const aviso = desconhecida ? `Não conheço a classe "${desconhecida}".\n\n` : "";
  const linhas = [
    `${aviso}Hearthstone DS: meta do ${nomeFormato}`,
    "",
    `Tier list de arquétipos (HSGuru): ${links.hsguruMeta}`,
    `Meta por classe (HSReplay): ${links.hsreplayMeta}`
  ];

  if (classe) {
    linhas.push(
      "",
      `${classe} no HSGuru: ${links.hsguruDecks}`,
      `${classe} no HSReplay: ${links.hsreplayDecks}`
    );
  }

  linhas.push("", "Para os decks de uma classe, mande /decks <classe>, por exemplo /decks mago.");
  return linhas.join("\n");
}

export function mensagemIndisponivel() {
  return "Não consegui ler os dados do Hearthstone DS agora. Tente de novo em alguns minutos.";
}

export function tituloDaResposta(texto) {
  const primeiraLinha = String(texto).split("\n")[0];
  return primeiraLinha.startsWith("Hearthstone DS:")
    ? primeiraLinha
    : primeiraLinha.split(" · ")[0];
}

export function dividir(texto, titulo = tituloDaResposta(texto)) {
  const linhas = String(texto).split("\n");

  if (texto.length <= 4096) {
    return [texto];
  }

  const grupos = [];
  let grupo = [];
  let tamanho = 0;

  for (const linha of linhas) {
    const incremento = linha.length + (grupo.length > 0 ? 1 : 0);

    if (grupo.length > 0 && tamanho + incremento > 3900) {
      grupos.push(grupo);
      grupo = [];
      tamanho = 0;
    }

    grupo.push(linha);
    tamanho += linha.length + (grupo.length > 1 ? 1 : 0);
  }

  if (grupo.length > 0) {
    grupos.push(grupo);
  }

  const total = grupos.length;
  const primeiraLinha = linhas[0];
  const primeira = grupos[0].join("\n").replace(primeiraLinha, `${primeiraLinha} (1/${total})`);
  const partes = [primeira];

  for (let indice = 1; indice < total; indice += 1) {
    partes.push(`${titulo} (continuação ${indice + 1}/${total})\n${grupos[indice].join("\n")}`);
  }

  return partes;
}
