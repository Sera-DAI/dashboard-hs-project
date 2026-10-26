const CLASSES = {
  DEATHKNIGHT: {
    nome: "Cavaleiro da Morte",
    apelidos: ["cavaleiro da morte", "dk"],
    padrao: "death-knight-standard",
    selvagem: "death-knight-wild"
  },
  DEMONHUNTER: {
    nome: "Caçador de Demônios",
    apelidos: ["caçador de demônios", "dh"],
    padrao: "demon-hunter",
    selvagem: "demon-hunter-wild-decks"
  },
  DRUID: { nome: "Druida", apelidos: ["druida"], padrao: "druid", selvagem: "druid-wild-decks" },
  HUNTER: { nome: "Caçador", apelidos: ["caçador"], padrao: "hunter", selvagem: "hunter-wild-decks" },
  MAGE: { nome: "Mago", apelidos: ["mago", "maga"], padrao: "mage", selvagem: "mage-wild-decks" },
  PALADIN: { nome: "Paladino", apelidos: ["paladino"], padrao: "paladin", selvagem: "paladin-wild-decks" },
  PRIEST: { nome: "Sacerdote", apelidos: ["sacerdote"], padrao: "priest", selvagem: "priest-wild-decks" },
  ROGUE: { nome: "Ladino", apelidos: ["ladino"], padrao: "rogue", selvagem: "rogue-wild-decks" },
  SHAMAN: { nome: "Xamã", apelidos: ["xamã"], padrao: "shaman", selvagem: "shaman-wild-decks" },
  WARLOCK: { nome: "Bruxo", apelidos: ["bruxo"], padrao: "warlock", selvagem: "warlock-wild-decks" },
  WARRIOR: { nome: "Guerreiro", apelidos: ["guerreiro"], padrao: "warrior", selvagem: "warrior-wild-decks" }
};

function normalizar(texto) {
  return String(texto ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR")
    .trim()
    .replace(/\s+/g, " ");
}

const MAXIMO_ITENS = 5;

function caractere(entidade, codigo) {
  return codigo >= 0 && codigo <= 0x10ffff ? String.fromCodePoint(codigo) : entidade;
}

function decodificarEntidades(texto) {
  return String(texto ?? "")
    .replace(/&#(\d{1,7});/g, (entidade, codigo) => caractere(entidade, Number(codigo)))
    .replace(/&#x([0-9a-f]{1,6});/gi, (entidade, codigo) => caractere(entidade, Number.parseInt(codigo, 16)))
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

// Busca linear com indexOf: o Worker gratuito tem 10 ms de CPU e um regex com [\s\S]*? fica quadrático em feed quebrado
function trechoEntre(texto, abertura, fechamento, inicio = 0) {
  const comeco = texto.indexOf(abertura, inicio);

  if (comeco === -1) {
    return null;
  }

  const fimAbertura = abertura.endsWith(">") ? comeco + abertura.length - 1 : texto.indexOf(">", comeco + abertura.length);

  if (fimAbertura === -1) {
    return null;
  }

  const fim = texto.indexOf(fechamento, fimAbertura + 1);

  if (fim === -1) {
    return null;
  }

  return { conteudo: texto.slice(fimAbertura + 1, fim), proximo: fim + fechamento.length };
}

function conteudoTag(xml, nome) {
  const trecho = trechoEntre(xml, `<${nome}>`, `</${nome}>`) ?? trechoEntre(xml, `<${nome} `, `</${nome}>`);

  if (!trecho) {
    return "";
  }

  const conteudo = trecho.conteudo.trim().replace(/^<!\[CDATA\[([\s\S]*)\]\]>$/, "$1");
  return decodificarEntidades(conteudo).trim();
}

function codigoDeck(texto) {
  return texto.match(/AAE[A-Za-z0-9+/=]{17,}/)?.[0] ?? "";
}

// Só abre páginas do próprio site: o link vem do feed e não deve levar o Worker a outro endereço
export function paginaDoDeck(link) {
  try {
    const url = new URL(link);
    return url.protocol === "https:" && url.hostname === "hearthstone-decks.net" && !url.port && !url.username ? url.href : "";
  } catch {
    return "";
  }
}

// O código fica no link "Deck Stats (HsReplay)" da página do deck; busca linear, como no feed
export function codigoDaPagina(html) {
  const texto = String(html ?? "");
  const marca = "hsreplay.net/decks/";
  let posicao = texto.indexOf(marca);

  while (posicao !== -1) {
    const inicio = posicao + marca.length;
    let caminho = decodificarEntidades(texto.slice(inicio, inicio + 400)).split(/["'<>\s#?]/)[0];

    try {
      caminho = decodeURIComponent(caminho).replace(/\/+$/, "");
    } catch {
      caminho = "";
    }

    if (/^AAE[A-Za-z0-9+/=]{17,}$/.test(caminho)) {
      return caminho;
    }

    posicao = texto.indexOf(marca, inicio);
  }

  return "";
}

export class ErroFeed extends Error {
  constructor(mensagem = "Feed RSS inválido.") {
    super(mensagem);
    this.name = "ErroFeed";
  }
}

export function lerClasse(argumento) {
  const palavras = String(argumento ?? "").trim().split(/\s+/).filter(Boolean);
  const selvagem = palavras.some((palavra) => normalizar(palavra) === "selvagem");
  const restantes = palavras.filter((palavra) => normalizar(palavra) !== "selvagem");
  const busca = normalizar(restantes.join(" "));
  const classe = Object.entries(CLASSES).find(([, dados]) => dados.apelidos.some((apelido) => normalizar(apelido) === busca));

  return {
    classe: classe?.[0] ?? null,
    formato: selvagem ? "selvagem" : "padrao",
    desconhecida: classe || !busca ? "" : restantes.join(" ")
  };
}

export function nomeClasse(codigo) {
  return CLASSES[codigo]?.nome ?? "";
}

export function links(classe, formato) {
  const dados = CLASSES[classe];
  const selvagem = formato === "selvagem";
  const modo = selvagem ? "RANKED_WILD" : "RANKED_STANDARD";
  const numeroFormato = selvagem ? "1" : "2";
  const pagina = `https://hearthstone-decks.net/${selvagem ? "wild-decks" : "standard-decks"}/${dados[formato]}/`;

  return {
    hsguruDecks: `https://www.hsguru.com/decks?format=${numeroFormato}&player_class=${classe}&rank=diamond_to_legend`,
    hsguruMeta: `https://www.hsguru.com/meta?format=${numeroFormato}`,
    hsreplayDecks: `https://hsreplay.net/decks/#playerClasses=${classe}&gameType=${modo}`,
    hsreplayMeta: `https://hsreplay.net/meta/#gameType=${modo}`,
    pagina,
    feed: `${pagina}feed/`
  };
}

export function lerFeed(xml) {
  const conteudo = String(xml ?? "");

  if (
    !/<rss(?:\s|>)/i.test(conteudo)
    || !/<\/rss\s*>/i.test(conteudo)
    || !/<channel(?:\s|>)/i.test(conteudo)
    || !/<\/channel\s*>/i.test(conteudo)
    || (conteudo.match(/<item(?:\s|>)/gi) ?? []).length !== (conteudo.match(/<\/item\s*>/gi) ?? []).length
  ) {
    throw new ErroFeed();
  }

  const itens = [];
  let posicao = 0;

  while (itens.length < MAXIMO_ITENS) {
    const trecho = trechoEntre(conteudo, "<item", "</item>", posicao);

    if (!trecho) {
      break;
    }

    const item = trecho.conteudo;
    posicao = trecho.proximo;
    itens.push({
      titulo: conteudoTag(item, "title"),
      data: conteudoTag(item, "pubDate"),
      link: conteudoTag(item, "link"),
      codigo: codigoDeck(conteudoTag(item, "description")) || codigoDeck(conteudoTag(item, "content:encoded"))
    });
  }

  return itens;
}
