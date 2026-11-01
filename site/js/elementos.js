import { higienizarTexto, nomeClasse } from "./logica.js";

export const CLASSES = {
  DEATHKNIGHT: ["cavaleiro-da-morte", "#7fd6ff"],
  DEMONHUNTER: ["cacador-de-demonios", "#6ff0b8"],
  DRUID: ["druida", "#8be06b"],
  HUNTER: ["cacador", "#4fd18b"],
  MAGE: ["mago", "#b98bff"],
  PALADIN: ["paladino", "#f3d36b"],
  PRIEST: ["sacerdote", "#ffffff"],
  ROGUE: ["ladino", "#c9c4d6"],
  SHAMAN: ["xama", "#7fb0ff"],
  WARLOCK: ["bruxo", "#d36bff"],
  WARRIOR: ["guerreiro", "#ff7a5c"]
};

export const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
export const $$ = (seletor, raiz = document) => [...raiz.querySelectorAll(seletor)];

export function elemento(tag, classe = "", texto) {
  const no = document.createElement(tag);
  no.className = classe;
  if (texto !== undefined) {
    no.textContent = String(texto ?? "");
  }
  return no;
}

export function icone(nome) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("aria-hidden", "true");
  const uso = document.createElementNS(svg.namespaceURI, "use");
  uso.setAttribute("href", "#i-" + nome);
  svg.append(uso);
  return svg;
}

export function iconeClasse(classe) {
  const dados = CLASSES[classe];
  if (!dados) {
    return icone("lis");
  }
  const img = document.createElement("img");
  img.src = "img/classes/" + dados[0] + ".webp";
  img.alt = "";
  img.width = 34;
  img.height = 34;
  img.style.objectFit = "contain";
  img.setAttribute("aria-hidden", "true");
  return img;
}

export function botao(texto, classe = "") {
  const no = elemento("button", classe, texto);
  no.type = "button";
  return no;
}

export function link(texto, href, classe = "") {
  const no = elemento("a", classe, texto);
  if (/^https?:\/\//i.test(href ?? "")) {
    no.href = href;
    no.target = "_blank";
    no.rel = "noopener noreferrer";
  } else if (String(href ?? "").startsWith("#/")) {
    no.href = href;
  } else {
    no.hidden = true;
  }
  return no;
}

export function dataBR(data) {
  return String(data ?? "").slice(0, 10).split("-").reverse().join(".");
}

export function dataElemento(data) {
  const no = elemento("time", "", dataBR(data));
  no.dateTime = String(data ?? "").slice(0, 10);
  return no;
}

export function textoCarta(raiz, texto) {
  const pilha = [raiz];
  for (const token of higienizarTexto(texto)) {
    if (token.tipo === "texto") {
      pilha.at(-1).append(document.createTextNode(token.texto));
    } else if (!token.fechar) {
      const no = document.createElement(token.nome);
      pilha.at(-1).append(no);
      pilha.push(no);
    } else if (pilha.length > 1 && pilha.at(-1).localName === token.nome) {
      pilha.pop();
    }
  }
}

const TERMOS = /Reinado dos Deuses Antigos|Deus Antigo|Montar|Monge|Aberrações|Prestígio da Taverna|Cofre de Recompensas|\d{1,2}(?: a \d{1,2})? de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?: de \d{4})?|\d{1,2}\/\d{1,2}(?:\/\d{4})?|palavra-chave \S+/gi;

export function marcar(raiz, texto) {
  const valor = String(texto ?? "");
  let inicio = 0;
  let indice = 0;
  for (const parte of valor.matchAll(TERMOS)) {
    raiz.append(valor.slice(inicio, parte.index));
    const marca = elemento("mark", "mt mt" + (indice % 3 + 1), parte[0]);
    marca.style.setProperty("--k", indice % 5);
    raiz.append(marca);
    inicio = parte.index + parte[0].length;
    indice += 1;
  }
  raiz.append(valor.slice(inicio));
  raiz.classList.add("marcavel");
}

export function descricaoCarta(carta, versao) {
  const estado = carta[versao] ?? carta;
  const numeros = ["custo", "ataque", "vida", "durabilidade", "armadura"]
    .filter((campo) => estado[campo] != null)
    .map((campo) => campo + " " + estado[campo]);
  return [carta.nome, nomeClasse(carta.classe), ...numeros].filter(Boolean).join(", ");
}
