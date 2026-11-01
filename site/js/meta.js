import { $, $$, CLASSES, elemento, botao, iconeClasse, link } from "./elementos.js";
import { nomeClasse } from "./logica.js";

// Só atalhos públicos (D38): HSReplay e HSGuru, com os filtros do HSGuru (Diamante até Lenda, 2 semanas, 100 jogos)
export function linksMeta(classe, formato) {
  if (!CLASSES[classe]) {
    return [];
  }
  const wild = formato === "selvagem";
  return [
    ["HSReplay", "https://hsreplay.net/decks/#playerClasses=" + classe + "&gameType=" + (wild ? "RANKED_WILD" : "RANKED_STANDARD")],
    ["HSGuru", "https://www.hsguru.com/decks?format=" + (wild ? "1" : "2") + "&player_class=" + classe + "&rank=diamond_to_legend&period=past_2_weeks&min_games=100"]
  ];
}

function constelacao(semente) {
  let estado = [...semente].reduce((valor, letra) => (valor * 31 + letra.charCodeAt(0)) >>> 0, 7);
  const aleatorio = () => {
    estado = (estado * 1664525 + 1013904223) >>> 0;
    return estado / 4294967296;
  };
  const pontos = Array.from({ length: 6 }, (_, indice) => [
    14 + indice % 3 * 28 + aleatorio() * 14,
    14 + Math.floor(indice / 3) * 70 + aleatorio() * 36
  ]);
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "const");
  svg.setAttribute("viewBox", "0 0 100 130");
  svg.setAttribute("aria-hidden", "true");
  const linha = document.createElementNS(ns, "polyline");
  linha.setAttribute("pathLength", "1");
  linha.setAttribute("points", pontos.map((ponto) => ponto.join(",")).join(" "));
  svg.append(linha);
  for (const [x, y] of pontos) {
    const ponto = document.createElementNS(ns, "circle");
    ponto.setAttribute("cx", x);
    ponto.setAttribute("cy", y);
    ponto.setAttribute("r", "1.7");
    svg.append(ponto);
  }
  return svg;
}

export function montarBrasoes(efeitos) {
  const janela = $("#janela-deck");
  let classeAberta = "MAGE";
  let formato = "padrao";
  let troca;
  const desenhar = () => {
    $$("[data-formato]", janela).forEach((no) => no.setAttribute("aria-pressed", String(no.dataset.formato === formato)));
    // D33: não existem decks publicados em dados/. Só atalhos, sem coleta
    // pública nem os cinco nomes fictícios do protótipo.
    $("#decks").replaceChildren(...linksMeta(classeAberta, formato).map(([nome, href], indice) => {
      const item = elemento("li", "deck");
      item.style.setProperty("--i", indice);
      item.append(link(nome, href, "deck-caixa"));
      return item;
    }));
    $("#decks").classList.remove("saindo");
  };
  $$("[data-brasoes]").forEach((lista) => {
    lista.replaceChildren(...Object.entries(CLASSES).map(([classe, [, cor]]) => {
      const item = elemento("li");
      const brasao = botao("", "brasao revela");
      brasao.dataset.classe = classe;
      brasao.style.setProperty("--c", cor);
      brasao.append(iconeClasse(classe), elemento("span", "", nomeClasse(classe)), elemento("small", "", "Ver decks"), constelacao(classe));
      brasao.addEventListener("click", () => {
        clearTimeout(troca);
        classeAberta = classe;
        formato = "padrao";
        $("#deck-titulo").replaceChildren(iconeClasse(classe), document.createTextNode(nomeClasse(classe)));
        desenhar();
        janela.showModal();
      });
      item.append(brasao);
      return item;
    }));
  });
  $$("[data-formato]", janela).forEach((no) => no.addEventListener("click", () => {
    if (formato === no.dataset.formato) {
      return;
    }
    formato = no.dataset.formato;
    clearTimeout(troca);
    if (efeitos.reduzir) {
      desenhar();
    } else {
      $("#decks").classList.add("saindo");
      troca = setTimeout(desenhar, 280);
    }
  }));
  janela.addEventListener("close", () => clearTimeout(troca));
}
