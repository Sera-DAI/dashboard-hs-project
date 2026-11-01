const CLASSES = {
  DEATHKNIGHT: { nome: "Cavaleiro da Morte", apelidos: ["cavaleiro da morte", "dk"] },
  DEMONHUNTER: { nome: "Caçador de Demônios", apelidos: ["caçador de demônios", "dh"] },
  DRUID: { nome: "Druida", apelidos: ["druida"] },
  HUNTER: { nome: "Caçador", apelidos: ["caçador"] },
  MAGE: { nome: "Mago", apelidos: ["mago", "maga"] },
  PALADIN: { nome: "Paladino", apelidos: ["paladino"] },
  PRIEST: { nome: "Sacerdote", apelidos: ["sacerdote"] },
  ROGUE: { nome: "Ladino", apelidos: ["ladino"] },
  SHAMAN: { nome: "Xamã", apelidos: ["xamã"] },
  WARLOCK: { nome: "Bruxo", apelidos: ["bruxo"] },
  WARRIOR: { nome: "Guerreiro", apelidos: ["guerreiro"] }
};

const FORMATOS = { wild: "wild", padrao: "padrao", standard: "padrao" };

function normalizar(texto) {
  return String(texto ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLocaleLowerCase("pt-BR")
    .trim()
    .replace(/\s+/g, " ");
}

// O formato pode vir antes ou depois da classe. Sem formato, formato fica null:
// o /decks mostra os dois e o /meta usa o Padrão. "Selvagem" não vale mais: só "wild".
export function lerClasse(argumento) {
  const palavras = String(argumento ?? "").trim().split(/\s+/).filter(Boolean);
  const formatos = palavras.map((palavra) => FORMATOS[normalizar(palavra)]).filter(Boolean);
  const restantes = palavras.filter((palavra) => !FORMATOS[normalizar(palavra)]);
  const busca = normalizar(restantes.join(" "));
  const classe = Object.entries(CLASSES).find(([, dados]) => dados.apelidos.some((apelido) => normalizar(apelido) === busca));

  return {
    classe: classe?.[0] ?? null,
    formato: formatos.at(-1) ?? null,
    desconhecida: classe || !busca ? "" : restantes.join(" ")
  };
}

export function nomeClasse(codigo) {
  return CLASSES[codigo]?.nome ?? "";
}

// HSGuru: Diamante até Lenda, últimas 2 semanas e no mínimo 100 jogos
export function links(classe, formato) {
  const wild = formato === "wild";
  const modo = wild ? "RANKED_WILD" : "RANKED_STANDARD";
  const numeroFormato = wild ? "1" : "2";

  return {
    hsguruDecks: `https://www.hsguru.com/decks?format=${numeroFormato}&player_class=${classe}&rank=diamond_to_legend&period=past_2_weeks&min_games=100`,
    hsguruMeta: `https://www.hsguru.com/meta?format=${numeroFormato}`,
    hsreplayDecks: `https://hsreplay.net/decks/#playerClasses=${classe}&gameType=${modo}`,
    hsreplayMeta: `https://hsreplay.net/meta/#gameType=${modo}`
  };
}
