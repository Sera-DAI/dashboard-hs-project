import { imagemDaCarta, marcaMudanca, formatarCampo } from "./logica.js";
import { CLASSES, elemento, icone, iconeClasse, descricaoCarta, textoCarta } from "./elementos.js";

// Endereços das imagens oficiais (dados/imagens.json); sem eles, vale o render do HearthstoneJSON.
let imagensOficiais = {};

export function definirImagens(imagens) {
  imagensOficiais = imagens ?? {};
}

// A reserva já existe antes de começar a requisição; falhar nunca deixa um buraco.
export function ligarImagem(img, reserva, fonte) {
  img.addEventListener("load", () => {
    // Com a carta oficial na face, a moldura desenhada some: fica só a carta.
    img.parentElement?.classList.add("com-imagem");
    reserva.style.display = "none";
    img.style.opacity = "1";
  });
  img.addEventListener("error", () => {
    img.style.display = "none";
    reserva.style.display = "contents";
    img.removeAttribute("src");
  });
  img.src = fonte;
}

export function desenharCarta(alvo, carta, versao = "depois", densidade = window.devicePixelRatio) {
  const dados = carta[versao] ?? {};
  const cor = CLASSES[carta.classe]?.[1] ?? "#e9b949";
  const frente = elemento("div", "face frente");
  frente.style.setProperty("--c", cor);
  const reserva = elemento("div");
  // display:contents mantém a grade e a moldura do CSS do protótipo.
  reserva.style.display = "contents";
  const arte = elemento("div", "arte");
  arte.style.background = "radial-gradient(circle at 50% 62%, " + cor + ", #4c1d95 40%, #07080f)";
  const simbolo = iconeClasse(carta.classe);
  Object.assign(simbolo.style, {
    position: "absolute",
    inset: "0",
    margin: "auto",
    width: "42%",
    height: "42%",
    objectFit: "contain"
  });
  arte.append(simbolo);
  const caixa = elemento("div", "caixa");
  const texto = elemento("span");
  textoCarta(texto, dados.texto);
  caixa.append(texto);
  reserva.append(arte, elemento("div", "faixa-nome", carta.nome), caixa);
  for (const campo of ["custo", "ataque", "vida", "durabilidade", "armadura"]) {
    if (dados[campo] == null) {
      continue;
    }
    const posicao = campo === "durabilidade" ? "vida" : campo === "armadura" ? "ataque" : campo;
    const gema = elemento("span", "gema " + posicao);
    gema.dataset.campo = campo;
    gema.dataset.mudou = marcaMudanca(carta, versao, campo);
    const simbolo = campo === "custo" ? "mana" : posicao;
    gema.append(icone(simbolo), String(dados[campo]));
    reserva.append(gema);
  }
  frente.append(reserva);
  const fonte = imagemDaCarta(carta, versao, densidade, imagensOficiais);
  if (fonte) {
    const img = document.createElement("img");
    img.alt = descricaoCarta(carta, versao);
    img.loading = "lazy";
    img.decoding = "async";
    img.width = 256;
    img.height = 358;
    img.style.opacity = "0";
    // A imagem oficial ocupa a face inteira; a reserva usa a grade existente.
    Object.assign(img.style, { position: "absolute", inset: "0", width: "100%", height: "100%", objectFit: "contain" });
    // O render do HearthstoneJSON deixa um recorte transparente nas cartas com Preparar: o remendo cobre esse trecho.
    // A imagem oficial da Blizzard vem íntegra e dispensa o remendo.
    if (fonte.startsWith("https://art.hearthstonejson.com/")) {
      const remendo = elemento("span", "remendo");
      for (let i = 0; i < 3; i++) {
        const faixa = elemento("span");
        faixa.style.backgroundImage = 'url("' + fonte + '")';
        remendo.append(faixa);
      }
      frente.append(remendo);
    }
    frente.append(img);
    ligarImagem(img, reserva, fonte);
  }
  frente.append(elemento("span", "brilho"));
  const verso = elemento("div", "face verso");
  const arteVerso = document.createElement("img");
  arteVerso.src = "img/verso-carta.webp";
  arteVerso.alt = "";
  arteVerso.decoding = "async";
  verso.append(arteVerso);
  alvo.replaceChildren(frente, verso);
  alvo.setAttribute("aria-label", descricaoCarta(carta, versao) + ", " + versao + ". Enter vira a carta.");
  alvo.dataset.versao = versao;
}

export function linhasMudanca(carta) {
  const lista = elemento("ul", "mudancas");
  for (const mudanca of carta.mudancas ?? []) {
    const linha = elemento("li");
    if (mudanca.campo === "texto") {
      linha.append(icone("alterada"), "texto alterado");
    } else {
      const marca = marcaMudanca(carta, "depois", mudanca.campo);
      const simbolo = icone(marca || "alterada");
      simbolo.style.color = marca === "buff" ? "var(--buff-neon)" : marca === "nerf" ? "var(--nerf)" : "var(--ouro-claro)";
      const novo = elemento("b", "", formatarCampo(mudanca.campo, mudanca.depois));
      novo.style.color = simbolo.style.color;
      linha.append(simbolo, mudanca.campo + " ", elemento("s", "", formatarCampo(mudanca.campo, mudanca.antes)), " → ", novo);
    }
    lista.append(linha);
  }
  return lista;
}

export function iniciarCarta(alvo, efeitos) {
  if (alvo.dataset.interativa) {
    return;
  }
  alvo.dataset.interativa = "true";
  alvo.setAttribute("aria-pressed", "false");
  const virar = () => {
    const virada = alvo.classList.toggle("virada");
    alvo.setAttribute("aria-pressed", String(virada));
    alvo.querySelector(".frente")?.setAttribute("aria-hidden", String(virada));
    alvo.querySelector(".verso")?.setAttribute("aria-hidden", String(!virada));
  };
  alvo.addEventListener("click", virar);
  alvo.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" || evento.key === " ") {
      evento.preventDefault();
      virar();
    }
  });
  alvo.addEventListener("pointermove", (evento) => {
    // O dedo pode inclinar a carta; efeitos decorativos continuam desligados.
    if (efeitos.reduzir) {
      return;
    }
    const caixa = alvo.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (evento.clientX - caixa.left) / caixa.width));
    const y = Math.max(0, Math.min(1, (evento.clientY - caixa.top) / caixa.height));
    alvo.classList.add("segue");
    alvo.style.setProperty("--ry", (x - 0.5) * 30 + "deg");
    alvo.style.setProperty("--rx", (0.5 - y) * 24 + "deg");
    alvo.style.setProperty("--mx", x * 100 + "%");
    alvo.style.setProperty("--my", y * 100 + "%");
  });
  const parar = () => {
    alvo.classList.remove("segue");
    alvo.style.setProperty("--rx", "0deg");
    alvo.style.setProperty("--ry", "0deg");
  };
  alvo.addEventListener("pointerleave", parar);
  alvo.addEventListener("pointerup", parar);
  alvo.addEventListener("pointercancel", parar);
}

export function atualizarCarta(alvo, carta, versao, efeitos, animar = true) {
  alvo.classList.remove("virada");
  alvo.setAttribute("aria-pressed", "false");
  desenharCarta(alvo, carta, versao);
  alvo.querySelector(".verso").setAttribute("aria-hidden", "true");
  if (animar && !efeitos.reduzir) {
    alvo.classList.remove("troca");
    void alvo.offsetWidth;
    alvo.classList.add("troca");
    alvo.querySelectorAll('.gema[data-mudou="buff"], .gema[data-mudou="nerf"]').forEach((gema) => gema.classList.add("pula"));
  }
}
