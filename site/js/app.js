import { $, $$, elemento, botao, icone, link, dataBR, dataElemento, marcar, CLASSES } from "./elementos.js";
import { nomeClasse, GRUPOS_COMPLETOS, FORMATOS, secoesDoPatch, rotuloDoGrupo, nomeDoGrupo, buscar, filtrarCarta, lerRota, rotaVersao, assuntoNoticia } from "./logica.js";
import { carregarBase, carregarCatalogo, combinarDados } from "./dados.js";
import { definirImagens, desenharCarta, iniciarCarta, atualizarCarta, linhasMudanca } from "./cartas.js";
import { iniciarEfeitos } from "./efeitos.js";
import { montarBrasoes } from "./meta.js";

const efeitos = iniciarEfeitos();
const janelaCarta = $("#janela-carta");
let dados;
let base;
let catalogo;
let catalogoPendente;
let rotaAtual = "";
let grupoAtivo = "todas";
let cartaAberta;
let versaoCarta = "depois";

configurarDialogos();
iniciarCarta($("#carta-grande"), efeitos);
window.addEventListener("hashchange", navegar);
navegar();
iniciar();

// O catálogo de cartas (mais de 500 KB com as imagens oficiais) só é pedido quando a rota precisa de uma carta (D50).
function rotaPrecisaCatalogo(rota) {
  return rota.tipo === "patches" || rota.tipo === "patch" || rota.tipo === "cartas" || rota.tipo === "carta";
}

function garantirCatalogo() {
  catalogoPendente ??= carregarCatalogo().then((pronto) => {
    catalogo = pronto;
    definirImagens(pronto.imagens);
    if (base) {
      const falas = dados?.falas;
      dados = combinarDados(base, catalogo);
      dados.falas = falas;
    }
  }).catch((erro) => {
    catalogoPendente = undefined;
    throw erro;
  });
  return catalogoPendente;
}

async function iniciar() {
  document.body.dataset.estado = "carregando";
  try {
    if (rotaPrecisaCatalogo(lerRota(window.location.hash))) {
      garantirCatalogo().catch(() => {});
    }
    base = await carregarBase();
    dados = combinarDados(base, catalogo);
    // Só a página aberta é montada na hora; as outras esperam o primeiro acesso (D50).
    montarInicio();
    configurarBusca();
    document.body.dataset.estado = "pronto";
    navegar();
  } catch (erro) {
    document.body.dataset.estado = "erro";
    console.error("Falha ao carregar o dashboard", erro);
  }
}

// Monta uma vez, e só quando a página é aberta: o catálogo de cartas da grade e as listas pesam no celular.
const montadas = new Set();
function montarUma(chave, montar) {
  if (!montadas.has(chave)) {
    montadas.add(chave);
    montar();
  }
}

function garantirPagina(pagina) {
  if (pagina === "inicio" || pagina === "meta") {
    montarUma("brasoes", () => montarBrasoes(efeitos));
  } else if (pagina === "patches") {
    montarUma("indice", montarIndice);
  } else if (pagina === "cartas") {
    montarUma("cartas", montarCartas);
  } else if (pagina === "noticias") {
    montarUma("noticias", montarNoticias);
  }
}

function montarInicio() {
  const ultimo = dados.patches.find((patch) => patch.cartas.length) ?? dados.patches[0];
  if (dados.patches.length) {
    $("#sobre-hero").textContent = "Patch " + dados.patches[0].versao + " · " + dados.noticias.length + " notícias · Meta";
  }
  const faixa = [
    ...(ultimo ? ["Patch " + ultimo.versao, ultimo.buffs + " buffs", ultimo.nerfs + " nerfs"] : []),
    dados.noticias.length + " notícias", "Decks do meta", "Padrão e Wild",
    "Cartas em 3D", "Resumo por IA", "Aviso no Telegram", "A cada 60 minutos"
  ];
  for (const [id, itens] of [["faixa1", faixa], ["faixa2", Object.keys(CLASSES).map(nomeClasse)]]) {
    const alvo = $("#" + id);
    alvo.replaceChildren();
    for (const texto of [...itens, ...itens]) {
      const no = elemento("span", "", texto);
      no.append(icone("estrela"));
      alvo.append(no);
    }
  }
  const nCartas = new Set(dados.patches.flatMap((patch) => patch.cartas.map((carta) => carta.nome))).size;
  const portas = [
    ["patches", "i.", "Patches", dados.patches.length ? dados.patches.length + " versões, do " + dados.patches.at(-1).versao + " ao " + dados.patches[0].versao + ", com resumo em tópicos." : "", "Abrir o livro"],
    ["cartas", "ii.", "Cartas", nCartas + " cartas alteradas, em 3D, com antes e depois.", "Ver as cartas"],
    ["noticias", "iii.", "Notícias", dados.noticias.length + " notícias: expansões, eventos, loja e esports.", "Ler as notícias"],
    ["meta", "iv.", "Meta", "", "Ver os decks"]
  ];
  $("#portas").replaceChildren(...portas.map(([rota, numero, titulo, descricao, acao]) => {
    const item = elemento("li");
    const ancora = link("", "#/" + rota, "porta revela");
    const pequena = elemento("small", "", acao);
    pequena.append(icone("seta-d"));
    ancora.append(elemento("i", "", numero), elemento("b", "", titulo), elemento("p", "", descricao), pequena);
    item.append(ancora);
    return item;
  }));
  dados.falas = {
    inicio: [
      ...(ultimo ? [ultimo.buffs + " buffs e " + ultimo.nerfs + " nerfs no Patch " + ultimo.versao + "."] : []),
      ...(dados.noticias.length ? ["Nova notícia na Taverna!"] : []),
      ...(dados.patches.length ? ["Novo patch na Taverna: " + dados.patches[0].versao + "."] : []),
      "Padrão ou Wild? Escolha um brasão.", "Volto a vigiar em 60 minutos."
    ],
    patches: [
      ...(ultimo ? [ultimo.buffs + " buffs e " + ultimo.nerfs + " nerfs no Patch " + ultimo.versao + "."] : []),
      dados.patches.length + " patches no livro.", "Escolha uma versão ao lado."
    ],
    cartas: [nCartas + " cartas mudaram desde abril.", "Toque numa carta para ver em 3D.", "Buffs em verde, nerfs em vermelho."],
    noticias: [...(dados.noticias.length ? ["Nova notícia na Taverna!"] : []), dados.noticias.length + " notícias guardadas.", "Resumo nosso, link para a original."],
    meta: ["Escolha um brasão.", "Padrão ou Wild?"]
  };
}

function montarIndice() {
  $("#indice-patches").replaceChildren(...dados.patches.map((patch) => {
    const item = elemento("li");
    const ancora = link("", rotaVersao(patch.versao));
    ancora.dataset.versao = patch.versao;
    const conta = elemento("span", "conta");
    conta.setAttribute("aria-label", patch.buffs + " buffs, " + patch.nerfs + " nerfs");
    if (patch.cartas.length) {
      for (const [grupo, classe, simbolo] of [["buffs", "cb", "buff"], ["nerfs", "cn", "nerf"]]) {
        const numero = elemento("span", classe + (patch[grupo] ? "" : " zero"));
        numero.append(icone(simbolo), String(patch[grupo]));
        conta.append(numero);
      }
    } else {
      conta.append(elemento("span", "zero", "sem cartas"));
    }
    ancora.append(elemento("b", "", patch.versao), dataElemento(patch.data), conta);
    item.append(ancora);
    return item;
  }));
}

let geracaoPatch = 0;

function abrirPatch(versao) {
  geracaoPatch += 1;
  const minha = geracaoPatch;
  const patch = dados.patches.find((item) => item.versao === versao)
    ?? dados.patches.find((item) => item.cartas.length) ?? dados.patches[0];
  const detalhe = $("#detalhe");
  detalhe.replaceChildren();
  if (!patch) {
    return;
  }
  $$("#indice-patches a").forEach((ancora) => ancora.setAttribute("aria-current", String(ancora.dataset.versao === patch.versao)));
  const topo = elemento("div", "detalhe-topo");
  const titulo = elemento("h2", "", "Patch ");
  titulo.append(elemento("em", "", patch.versao));
  topo.append(titulo, link("Notícia oficial ↗", patch.link, "oficial"));
  detalhe.append(topo);
  if (patch.topicos.length) {
    const resumo = elemento("article", "pergaminho");
    const cabeca = elemento("header");
    const rotulo = elemento("span");
    rotulo.append(elemento("b", "", "Resumo próprio"), " · gerado por IA");
    cabeca.append(rotulo, elemento("span", "", patch.versao));
    const lista = elemento("ol", "marcavel");
    for (const topico of patch.topicos) {
      const item = elemento("li");
      const texto = elemento("span");
      marcar(texto, topico);
      item.append(icone("estrela"), texto);
      lista.append(item);
    }
    resumo.append(cabeca, lista, elemento("footer", "", "Texto nosso, sem reproduzir a notícia da Blizzard."));
    detalhe.append(resumo);
  } else {
    detalhe.append(elemento("p", "vazio", "O resumo desta versão ainda está na fila do monitor."));
  }
  if (!patch.cartas.length) {
    detalhe.append(elemento("p", "vazio", "Nenhuma carta mudou de custo, ataque, vida ou texto nesta versão."));
  } else {
    // D46: Padrão e Livre em partes separadas; os ids da primeira mesa seguem únicos na página.
    // A primeira seção entra na hora; as outras ficam para a tarefa seguinte, fora da primeira tela (D50).
    const [primeira, ...demais] = secoesDoPatch(patch);
    montarSecao(detalhe, patch, primeira, true);
    demais.forEach((secao) => setTimeout(() => {
      if (minha === geracaoPatch) {
        efeitos.contar(montarSecao(detalhe, patch, secao, false));
      }
    }, 0));
  }
  efeitos.observarMarcas(detalhe);
  efeitos.contar(detalhe);
}

function montarSecao(raiz, patch, secao, primeira) {
  const bloco = elemento("section", "secao-formato");
  bloco.dataset.formato = secao.chave;
  const cabeca = elemento("div", "secao-topo");
  cabeca.append(elemento("h3", "", secao.rotulo));
  const medalhas = elemento("div", "medalhas");
  GRUPOS_COMPLETOS.forEach(([grupo, rotulo], indice) => {
    const medalha = elemento("div", "medalha " + ["b", "n", "a", "t"][indice]);
    const numero = elemento("b", "", secao[grupo]);
    numero.dataset.contar = "";
    medalha.append(icone(["buff", "nerf", "alterada", "alterada"][indice]), numero, elemento("small", "", rotulo));
    medalhas.append(medalha);
  });
  bloco.append(cabeca, medalhas);
  if (secao.cartas.length) {
    montarMesa(bloco, secao.cartas, primeira);
  } else {
    bloco.append(elemento("p", "vazio", "Nenhuma alteração relevante para o " + secao.rotulo + " neste patch."));
  }
  raiz.append(bloco);
  return bloco;
}

function montarMesa(raiz, cartas, comIds = true) {
  const mesa = elemento("div", "mesa");
  const palco = elemento("div", "palco");
  const mao = elemento("div", "mao");
  if (comIds) {
    mao.id = "mao";
  }
  mao.classList.toggle("muitas", cartas.length > 7);
  mao.setAttribute("role", "group");
  mao.setAttribute("aria-label", "Cartas alteradas");
  const coluna = elemento("div", "foco");
  const foco = elemento("div", "carta");
  if (comIds) {
    foco.id = "foco";
  }
  foco.tabIndex = 0;
  foco.setAttribute("role", "button");
  let atual = cartas[0];
  let versao = "depois";
  const mudancas = elemento("div");
  if (comIds) {
    mudancas.id = "mudancas";
  }
  const desenhar = (animar = true) => {
    atualizarCarta(foco, atual, versao, efeitos, animar);
    mudancas.replaceChildren(linhasMudanca(atual));
  };
  const segmento = montarSegmento((nova) => {
    versao = nova;
    desenhar();
  });
  coluna.append(foco, segmento, mudancas);
  palco.append(mao, coluna);
  mesa.append(palco);
  raiz.append(mesa);
  const n = cartas.length;
  const passo = Math.min(62, 340 / n);
  cartas.forEach((carta, indice) => {
    const mini = botao("", "mini");
    mini.style.setProperty("--i", indice);
    mini.style.setProperty("--r", (indice - (n - 1) / 2) * Math.min(8, 48 / n) + "deg");
    mini.style.left = "calc(50% - 68px + " + ((indice - (n - 1) / 2) * passo) + "px)";
    mini.setAttribute("aria-label", carta.nome);
    mini.setAttribute("aria-pressed", String(indice === 0));
    const desenho = elemento("div", "carta");
    desenharCarta(desenho, carta);
    mini.append(desenho);
    mini.addEventListener("click", () => {
      atual = carta;
      $$(".mini", mao).forEach((no) => no.setAttribute("aria-pressed", String(no === mini)));
      desenhar();
    });
    mao.append(mini);
  });
  iniciarCarta(foco, efeitos);
  desenhar(false);
  if (!efeitos.reduzir) {
    requestAnimationFrame(() => mao.classList.add("viva"));
  }
}

function montarSegmento(aoTrocar) {
  const segmento = elemento("div", "segmento");
  segmento.setAttribute("role", "group");
  segmento.setAttribute("aria-label", "Versão da carta");
  for (const [valor, rotulo] of [["antes", "Antes"], ["depois", "Depois"]]) {
    const no = botao(rotulo);
    no.dataset.v = valor;
    no.setAttribute("aria-pressed", String(valor === "depois"));
    no.addEventListener("click", () => {
      $$("button", segmento).forEach((outro) => outro.setAttribute("aria-pressed", String(outro === no)));
      aoTrocar(valor);
    });
    segmento.append(no);
  }
  return segmento;
}

const LOTE_CARTAS = 6;
const filaCartas = [];
let rodandoFila = 0;

function itemDaCarta(carta) {
  const item = elemento("li");
  item.dataset.nome = carta.nome;
  item.dataset.grupo = carta.grupo;
  const abrir = botao();
  abrir.setAttribute("aria-label", carta.nome);
  const desenho = elemento("div", "carta");
  // Na grade a carta tem uns 170 px: a imagem de 256 basta, mesmo em tela de alta densidade.
  desenharCarta(desenho, carta, "depois", 1);
  const rotulo = elemento("span", "rotulo");
  const formato = FORMATOS.find(([chave]) => chave === carta.formato);
  rotulo.append(
    elemento("b", "t-" + carta.grupo, rotuloDoGrupo(carta.grupo)),
    elemento("span", "", nomeClasse(carta.classe) + (formato ? " · " + formato[1] : ""))
  );
  abrir.append(desenho, rotulo);
  abrir.addEventListener("click", () => abrirCarta(carta));
  item.carta = carta;
  item.append(abrir);
  return item;
}

// Um lote por tarefa deixa o navegador responder entre eles; o filtro e a busca esvaziam a fila de uma vez.
function esvaziarFilaCartas() {
  clearTimeout(rodandoFila);
  rodandoFila = 0;
  while (filaCartas.length) {
    filaCartas.shift()();
  }
}

function rodarFilaCartas() {
  rodandoFila = 0;
  const proximo = filaCartas.shift();
  if (proximo) {
    proximo();
    rodandoFila = setTimeout(rodarFilaCartas, 0);
  }
}

function montarCartas() {
  const antigas = $("#grade-cartas");
  const grade = elemento("div");
  grade.id = "grade-cartas";
  antigas.replaceWith(grade);
  const instancias = dados.patches.flatMap((patch) => patch.cartas);
  const formatos = instancias.some((carta) => carta.formato) ? FORMATOS : [];
  $("#filtro-cartas").replaceChildren(...[["todas", "Todas"], ...formatos, ...GRUPOS_COMPLETOS].map(([grupo, rotulo]) => {
    const filtro = botao(rotulo + " ");
    filtro.dataset.grupo = grupo;
    filtro.setAttribute("aria-pressed", String(grupo === "todas"));
    filtro.append(elemento("span", "", grupo === "todas" ? instancias.length : instancias.filter((carta) => carta.grupo === grupo || carta.formato === grupo).length));
    filtro.addEventListener("click", () => {
      grupoAtivo = grupo;
      $$("#filtro-cartas button").forEach((no) => no.setAttribute("aria-pressed", String(no === filtro)));
      filtrarCartas();
    });
    return filtro;
  }));
  for (const patch of dados.patches.filter((item) => item.cartas.length)) {
    const grupo = elemento("details", "grupo-patch");
    grupo.open = true;
    grupo.dataset.versao = patch.versao;
    const resumo = elemento("summary");
    const titulo = elemento("h3", "", "Patch ");
    titulo.append(elemento("em", "", patch.versao));
    const data = dataElemento(patch.data);
    data.append(" · " + patch.cartas.length + (patch.cartas.length === 1 ? " carta" : " cartas"));
    const ancora = link("Ver o patch →", rotaVersao(patch.versao));
    ancora.addEventListener("click", (evento) => evento.stopPropagation());
    const seta = elemento("span", "seta-grupo");
    seta.setAttribute("aria-hidden", "true");
    resumo.append(titulo, data, ancora, seta);
    const lista = elemento("ul", "grade-cartas");
    // As cartas entram em lotes pequenos (D50): 140 desenhos de uma vez travavam o celular por segundos.
    for (let inicio = 0; inicio < patch.cartas.length; inicio += LOTE_CARTAS) {
      const lote = patch.cartas.slice(inicio, inicio + LOTE_CARTAS);
      filaCartas.push(() => lista.append(...lote.map(itemDaCarta)));
    }
    grupo.append(resumo, lista);
    grupo.addEventListener("toggle", sincronizarRecolher);
    resumo.addEventListener("click", (evento) => {
      evento.preventDefault();
      efeitos.alternarGrupo(grupo, !grupo.open || grupo.classList.contains("fechando"), sincronizarRecolher);
    });
    grade.append(grupo);
  }
  $("#recolher-todos").addEventListener("click", () => {
    const grupos = $$(".grupo-patch").filter((grupo) => !grupo.hidden);
    const abrir = !grupos.some((grupo) => grupo.open && !grupo.classList.contains("fechando"));
    grupos.forEach((grupo) => efeitos.alternarGrupo(grupo, abrir, sincronizarRecolher));
  });
  $("#busca-cartas").addEventListener("input", filtrarCartas);
  rodarFilaCartas();
}

function sincronizarRecolher() {
  $("#recolher-todos").textContent = $$(".grupo-patch").some((grupo) => !grupo.hidden && grupo.open) ? "Recolher todos" : "Expandir todos";
}

function filtrarCartas() {
  garantirPagina("cartas");
  esvaziarFilaCartas();
  $$("#grade-cartas .grade-cartas > li").forEach((item) => {
    item.hidden = !filtrarCarta(item.carta, $("#busca-cartas").value, grupoAtivo);
  });
  $$(".grupo-patch").forEach((grupo) => {
    grupo.hidden = !$$(".grade-cartas > li", grupo).some((item) => !item.hidden);
  });
  $("#sem-resultados").hidden = $$(".grupo-patch").some((grupo) => !grupo.hidden);
  sincronizarRecolher();
  efeitos.atualizar();
}

function abrirCarta(carta) {
  cartaAberta = carta;
  versaoCarta = "depois";
  $("#carta-titulo").textContent = carta.nome;
  const historico = dados.patches.flatMap((patch) => patch.cartas.filter((item) =>
    String(item.dbfId) === String(carta.dbfId) || item.nome === carta.nome
  ));
  $("#historico-carta").replaceChildren(...historico.map((mudanca) => {
    const item = elemento("li");
    item.append(link("Patch " + mudanca.versao, rotaVersao(mudanca.versao)), elemento("span", "", dataBR(mudanca.data)), elemento("b", "t-" + mudanca.grupo, nomeDoGrupo(mudanca.grupo)), linhasMudanca(mudanca));
    return item;
  }));
  atualizarCarta($("#carta-grande"), cartaAberta, versaoCarta, efeitos, false);
  janelaCarta.showModal();
}

function configurarDialogos() {
  $$(".janela").forEach((janela) => {
    janela.addEventListener("click", (evento) => {
      const retangulo = janela.getBoundingClientRect();
      const fora = evento.clientX < retangulo.left || evento.clientX > retangulo.right || evento.clientY < retangulo.top || evento.clientY > retangulo.bottom;
      if (evento.target.closest("[data-fechar]") || (evento.target === janela && fora)) {
        janela.close();
      }
    });
  });
  $("#historico-carta").addEventListener("click", (evento) => {
    if (evento.target.closest("a")) {
      janelaCarta.close();
    }
  });
}

function configurarBusca() {
  $("#busca").addEventListener("keydown", async (evento) => {
    if (evento.key !== "Enter") {
      return;
    }
    evento.preventDefault();
    const consulta = evento.target.value.trim();
    try {
      await garantirCatalogo();
    } catch (erro) {
      document.body.dataset.estado = "erro";
      console.error("Falha ao carregar o catálogo de cartas", erro);
      return;
    }
    // A busca global mantém a D32: catálogo atual, deduplicado, Padrão/Wild.
    const resultados = buscar(dados.cartas, consulta, 1);
    if (resultados.length) {
      const carta = resultados[0];
      const depois = { ...carta };
      abrirCarta({ ...carta, antes: depois, depois, mudancas: [] });
      return;
    }
    $("#busca-cartas").value = consulta;
    grupoAtivo = "todas";
    $$("#filtro-cartas button").forEach((no) => no.setAttribute("aria-pressed", String(no.dataset.grupo === "todas")));
    window.location.hash = "#/cartas";
    filtrarCartas();
  });
}

const ASSUNTOS = [["todas", "Todas"], ["expansao", "Expansões"], ["evento", "Eventos"], ["loja", "Loja"], ["campos", "Campos de Batalha"], ["esports", "Esports"]];
const CAPAS = {
  expansao: ["#a78bfa", "#4c1d95", "lis"],
  evento: ["#f3d27a", "#1a1430", "estrela"],
  loja: ["#6ff0b8", "#0b2027", "mana"],
  campos: ["#d36bff", "#1d0f2e", "ataque"],
  esports: ["#ff7a72", "#1f0d14", "vida"]
};

function capaNoticia(assunto, indice, mini = false) {
  const [cor, fundo, simbolo] = CAPAS[assunto];
  const capa = elemento("figure", "capa-noticia" + (mini ? " mini-capa" : ""));
  capa.style.setProperty("--cor-capa", cor);
  capa.style.setProperty("--fundo-capa", fundo);
  capa.style.setProperty("--cx", 30 + indice * 37 % 50 + "%");
  capa.style.setProperty("--cy", 30 + indice * 23 % 50 + "%");
  capa.style.margin = "0";
  capa.setAttribute("aria-hidden", "true");
  capa.append(icone(simbolo));
  return capa;
}

function resumoNoticia(noticia, alvo) {
  marcar(alvo, noticia.topicos.length ? noticia.topicos.join(" ") : "O resumo desta notícia ainda está na fila do monitor (lotes diários).");
}

function montarNoticias() {
  const noticias = dados.noticias.map((noticia) => ({ ...noticia, assunto: assuntoNoticia(noticia.titulo) }));
  const manchete = $("#manchete");
  manchete.replaceChildren();
  manchete.hidden = !noticias.length;
  if (noticias.length) {
    const primeira = noticias[0];
    const titulo = elemento("h3");
    marcar(titulo, primeira.titulo);
    const resumo = elemento("p");
    resumoNoticia(primeira, resumo);
    const ancora = link("Notícia oficial", primeira.link, "botao real");
    ancora.append(icone("estrela"));
    manchete.append(capaNoticia(primeira.assunto[0], 0), elemento("small", "", "Mais recente · " + primeira.assunto[1] + " · " + dataBR(primeira.data)), titulo, resumo, ancora);
  }
  $("#notas").replaceChildren(...noticias.slice(1).map((noticia, indice) => {
    const item = elemento("li", "nota");
    item.dataset.tipo = noticia.assunto[0];
    const detalhes = elemento("details");
    detalhes.dataset.arquivo = noticia.arquivo;
    const cabeca = elemento("summary");
    const texto = elemento("div");
    const titulo = elemento("b");
    marcar(titulo, noticia.titulo);
    texto.append(elemento("small", "", noticia.assunto[1]), titulo);
    cabeca.append(capaNoticia(noticia.assunto[0], indice + 1, true), dataElemento(noticia.data), texto, icone("estrela"));
    const resumo = elemento("p", "resumo");
    resumoNoticia(noticia, resumo);
    const fonte = elemento("em");
    fonte.append(link("Notícia original na Battle.net ↗", noticia.link));
    resumo.append(fonte);
    detalhes.append(cabeca, resumo);
    item.append(detalhes);
    return item;
  }));
  $("#filtros").replaceChildren(...ASSUNTOS.map(([id, rotulo]) => {
    const no = botao(rotulo + " ");
    no.dataset.assunto = id;
    no.setAttribute("aria-pressed", String(id === "todas"));
    no.append(elemento("span", "", noticias.slice(1).filter((noticia) => id === "todas" || noticia.assunto[0] === id).length));
    no.addEventListener("click", () => {
      $$("#filtros button").forEach((outro) => outro.setAttribute("aria-pressed", String(outro === no)));
      let ordem = 0;
      $$("#notas .nota").forEach((item) => {
        item.hidden = id !== "todas" && item.dataset.tipo !== id;
        item.classList.remove("entra");
        if (!item.hidden && !efeitos.reduzir) {
          item.style.animationDelay = ordem * 50 + "ms";
          ordem += 1;
          void item.offsetWidth;
          item.classList.add("entra");
        }
      });
      efeitos.atualizar();
    });
    return no;
  }));
  efeitos.observarMarcas($('[data-pagina="noticias"]'));
}

function navegar() {
  const rota = lerRota(window.location.hash);
  // Preserva links antigos já publicados pelo bot.
  let pagina = rota.tipo;
  let versao = rota.versao;
  if (pagina === "patch") {
    pagina = "patches";
    versao = dados?.patches.find((patch) => patch.arquivo === rota.arquivo)?.versao;
  } else if (pagina === "noticia") {
    pagina = "noticias";
  } else if (pagina === "carta") {
    pagina = "cartas";
  }
  const mudou = pagina !== rotaAtual;
  rotaAtual = pagina;
  // Patches, cartas e a janela de uma carta esperam o catálogo; a página abre na hora e o conteúdo entra quando ele chega.
  const semCatalogo = Boolean(dados) && rotaPrecisaCatalogo(rota) && !catalogo;
  if (semCatalogo) {
    document.body.dataset.estado = "carregando";
    garantirCatalogo().then(() => {
      document.body.dataset.estado = "pronto";
      navegar();
    }, (erro) => {
      document.body.dataset.estado = "erro";
      console.error("Falha ao carregar o catálogo de cartas", erro);
    });
  }
  $$(".pagina").forEach((no) => {
    const ativa = no.dataset.pagina === pagina;
    no.hidden = !ativa;
    if (ativa && mudou) {
      no.classList.remove("chegou");
      void no.offsetWidth;
      no.classList.add("chegou");
    }
  });
  // As páginas já estão marcadas com hidden; a marca de js/rota.js (que escondia o início antes do JS) não faz mais falta.
  delete document.documentElement.dataset.rota;
  $$(".links a, .menu-movel a").forEach((no) => {
    const alvo = lerRota(no.getAttribute("href")).tipo;
    if (alvo === pagina) {
      no.setAttribute("aria-current", "page");
    } else {
      no.removeAttribute("aria-current");
    }
  });
  if (dados && !semCatalogo) {
    garantirPagina(pagina);
  }
  if (dados && !semCatalogo && pagina === "patches") {
    abrirPatch(versao);
  }
  if (mudou) {
    $$(".janela[open]").forEach((janela) => janela.close());
    window.scrollTo({ top: 0, behavior: "instant" });
    if (!efeitos.reduzir) {
      $("#cortina").classList.remove("corre");
      void $("#cortina").offsetWidth;
      $("#cortina").classList.add("corre");
    }
    $("#conteudo-principal").focus({ preventScroll: true });
  }
  if (dados) {
    efeitos.rodarFalas(pagina, dados.falas[pagina] ?? []);
    if (rota.tipo === "carta" && !semCatalogo && dados.cartas[rota.dbfId]) {
      const carta = { ...dados.cartas[rota.dbfId], dbfId: rota.dbfId };
      abrirCarta({ ...carta, antes: carta, depois: carta, mudancas: [] });
    }
    if (rota.tipo === "noticia") {
      const detalhes = $$("#notas details").find((no) => no.dataset.arquivo === rota.arquivo);
      if (detalhes) {
        detalhes.open = true;
        detalhes.scrollIntoView({ block: "center" });
      }
    }
  }
  efeitos.mudarPagina(pagina);
}
