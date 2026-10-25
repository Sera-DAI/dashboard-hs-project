import {
  buscar,
  carregarJson,
  formatarCampo,
  higienizarTexto,
  historicoDaCarta,
  lerRota,
  nomeClasse,
  rotaPatch
} from "./logica.js";
import { iniciarEfeitos } from "./efeitos.js";

const porId = (id) => document.getElementById(id);
const lista = porId("lista-patches");
const conteudo = porId("conteudo");
const campoBusca = porId("busca");
const resultadosBusca = porId("busca-resultados");
const estadoCarregando = porId("estado-carregando");
const estadoVazio = porId("estado-vazio");
const estadoErro = porId("estado-erro");
const efeitos = iniciarEfeitos();

let indice;
let cartasCache;
let rotaAnterior = "";
let resultadoAtivo = -1;
let numeroRenderizacao = 0;

iniciar();

async function iniciar() {
  try {
    let resposta;
    try {
      resposta = await fetchJson("dados/indice.json");
    } catch (erro) {
      if (erro.status !== 404) {
        throw erro;
      }
      resposta = { patches: [] };
    }
    if (!Array.isArray(resposta.patches)) {
      throw new Error("Índice inválido");
    }

    indice = resposta.patches.map(validarEntrada).sort((a, b) =>
      String(b.data).localeCompare(String(a.data))
    );
    renderizarLista();
    ocultarEstados();
    window.addEventListener("hashchange", renderizarRota);
    configurarBusca();
    await renderizarRota();
  } catch {
    mostrarErro();
  }
}

function validarEntrada(entrada) {
  if (!entrada || typeof entrada.arquivo !== "string" || typeof entrada.data !== "string") {
    throw new Error("Entrada de índice inválida");
  }

  return {
    arquivo: entrada.arquivo,
    versao: String(entrada.versao ?? ""),
    data: entrada.data,
    buffs: contar(entrada.buffs),
    nerfs: contar(entrada.nerfs),
    alteradas: contar(entrada.alteradas)
  };
}

function contar(valor) {
  const numero = Number(valor ?? 0);
  if (!Number.isInteger(numero) || numero < 0) {
    throw new Error("Contagem inválida");
  }
  return numero;
}

async function fetchJson(url) {
  return carregarJson(url);
}

function renderizarLista() {
  lista.replaceChildren();

  indice.forEach((patch, ordem) => {
    const item = clonar("tpl-patch");
    const botao = item.querySelector(".patch");
    preencher(item, "versao", patch.versao ? `Patch ${patch.versao}` : "Patch");
    preencherData(item.querySelector('[data-campo="data"]'), patch.data);
    preencher(item, "buffs", rotuloContagem(patch.buffs, "buff"));
    preencher(item, "nerfs", rotuloContagem(patch.nerfs, "nerf"));
    preencher(item, "alteradas", rotuloContagem(patch.alteradas, "alterada"));
    botao.style.setProperty("--i", ordem);
    botao.addEventListener("click", () => {
      window.location.hash = rotaPatch(patch.arquivo);
    });
    lista.append(item);
  });
}

async function renderizarRota() {
  if (!indice) {
    return;
  }

  const renderizacao = ++numeroRenderizacao;
  ocultarEstados();
  estadoCarregando.hidden = false;
  conteudo.replaceChildren();
  const rota = lerRota(window.location.hash);

  try {
    if (rota.tipo === "carta") {
      await renderizarCarta(rota.dbfId, renderizacao);
    } else {
      const arquivo = rota.tipo === "patch" ? rota.arquivo : indice[0]?.arquivo;
      const entrada = indice.find((patch) => patch.arquivo === arquivo);
      if (!entrada) {
        if (!indice.length && rota.tipo === "inicio") {
          mostrarVazio();
          return;
        }
        throw new Error("Patch não encontrado");
      }
      const patch = await carregarPatch(entrada.arquivo);
      if (renderizacao !== numeroRenderizacao) {
        return;
      }
      renderizarDetalhe(patch, entrada);
      rotaAnterior = window.location.hash || rotaPatch(entrada.arquivo);
      marcarPatchAtivo(entrada.arquivo);
    }
  } catch {
    if (renderizacao === numeroRenderizacao) {
      mostrarErro();
    }
  } finally {
    if (renderizacao === numeroRenderizacao) {
      estadoCarregando.hidden = true;
    }
  }
}

async function carregarPatch(arquivo) {
  if (!/^patches\/[\w.-]+\.json$/.test(arquivo)) {
    throw new Error("Caminho de patch inválido");
  }

  const patch = await fetchJson(`dados/${arquivo}`);
  if (!patch || typeof patch !== "object") {
    throw new Error("Patch inválido");
  }
  return patch;
}

function renderizarDetalhe(patch, entrada) {
  if (!patch.cartas) {
    conteudo.textContent = "As cartas deste patch ainda não chegaram.";
    return;
  }

  const detalhe = clonar("tpl-detalhe");
  const noticia = patch.noticia ?? patch.noticia_en;
  preencher(detalhe, "titulo", noticia?.titulo ?? `Patch ${patch.versao ?? entrada.versao}`);
  preencherData(detalhe.querySelector('[data-campo="data"]'), patch.data ?? entrada.data);
  preencher(detalhe, "buffs", entrada.buffs);
  preencher(detalhe, "nerfs", entrada.nerfs);
  preencher(detalhe, "alteradas", entrada.alteradas);

  const link = detalhe.querySelector('[data-campo="link"]');
  if (noticia?.link) {
    link.href = noticia.link;
    if (!patch.noticia && patch.noticia_en) {
      preencher(detalhe, "link-texto", "Notícia oficial (inglês)");
    }
  } else {
    link.hidden = true;
  }

  const grupos = detalhe.querySelector('[data-campo="grupos"]');
  const definicoes = [
    ["buffs", "Buffs"],
    ["nerfs", "Nerfs"],
    ["alteradas", "Alteradas"]
  ];

  definicoes.forEach(([chave, rotulo]) => {
    const cartas = Array.isArray(patch.cartas[chave]) ? patch.cartas[chave] : [];
    const grupo = clonar("tpl-grupo");
    const secao = grupo.querySelector(".grupo");
    secao.classList.add(chave);
    preencher(grupo, "rotulo", rotulo);
    preencher(grupo, "quantidade", `${cartas.length} ${cartas.length === 1 ? "carta" : "cartas"}`);

    if (!cartas.length) {
      grupo.querySelector('[data-campo="cartas"]').hidden = true;
      grupo.querySelector('[data-campo="vazio"]').hidden = false;
    } else {
      const listaCartas = grupo.querySelector('[data-campo="cartas"]');
      cartas.forEach((carta, ordem) => listaCartas.append(renderizarCartaAlterada(carta, ordem)));
    }

    grupos.append(grupo);
  });

  conteudo.append(detalhe);
  efeitos.revelarTitulos(conteudo);
  efeitos.contar(conteudo);
}

function renderizarCartaAlterada(carta, ordem) {
  const item = clonar("tpl-carta");
  const elemento = item.querySelector(".carta");
  const custo = carta.custo ?? (carta.mudancas ?? []).find((mudanca) => mudanca.campo === "custo")?.depois;
  if (custo === null || custo === undefined) {
    item.querySelector(".mana").hidden = true;
  } else {
    preencher(item, "custo", custo);
  }
  preencher(item, "nome", carta.nome ?? "Carta sem nome");
  preencher(item, "classe", nomeClasse(carta.classe));
  elemento.style.setProperty("--i", ordem);

  const mudancas = item.querySelector('[data-campo="mudancas"]');
  (carta.mudancas ?? []).forEach((mudanca, indice) => {
    mudancas.append(renderizarMudanca(mudanca, indice));
  });

  return item;
}

function renderizarMudanca(mudanca, indice) {
  if (mudanca.campo === "texto") {
    const item = clonar("tpl-mudanca-texto");
    inserirTextoSeguro(item.querySelector('[data-texto-carta="antes"]'), mudanca.antes);
    inserirTextoSeguro(item.querySelector('[data-texto-carta="depois"]'), mudanca.depois);
    item.querySelector(".depois").style.setProperty("--i", indice);
    return item;
  }

  const item = clonar("tpl-mudanca");
  preencher(item, "campo", rotuloCampo(mudanca.campo));
  preencher(item, "antes", formatarCampo(mudanca.campo, mudanca.antes));
  preencher(item, "depois", formatarCampo(mudanca.campo, mudanca.depois));
  item.querySelector(".depois").style.setProperty("--i", indice);
  return item;
}

async function carregarCartas() {
  if (!cartasCache) {
    cartasCache = fetchJson("dados/cartas.json").then((dados) => {
      if (!dados || !dados.cartas || typeof dados.cartas !== "object") {
        throw new Error("Arquivo de cartas inválido");
      }
      return dados.cartas;
    });
  }
  return cartasCache;
}

async function renderizarCarta(dbfId, renderizacao) {
  const cartas = await carregarCartas();
  if (renderizacao !== numeroRenderizacao) {
    return;
  }
  const carta = cartas[dbfId];
  if (!carta) {
    throw new Error("Carta não encontrada");
  }

  const ficha = clonar("tpl-ficha");
  preencher(ficha, "nome", carta.nome);
  preencher(ficha, "classe", nomeClasse(carta.classe));
  inserirTextoSeguro(ficha.querySelector('[data-texto-carta="texto"]'), carta.texto);
  ficha.querySelector('[data-campo="voltar"]').addEventListener("click", () => {
    window.location.hash = rotaAnterior || "";
  });

  const atributos = ficha.querySelector('[data-campo="atributos"]');
  const definicoes = [
    ["custo", "Custo"],
    ["ataque", "Ataque"],
    ["vida", "Vida"],
    ["durabilidade", "Durabilidade"],
    ["armadura", "Armadura"]
  ];

  definicoes.forEach(([campo, rotulo], ordem) => {
    if (carta[campo] === null || carta[campo] === undefined) {
      return;
    }
    const atributo = clonar("tpl-atributo");
    preencher(atributo, "rotulo", rotulo);
    preencher(atributo, "valor", carta[campo]);
    atributo.querySelector(".total").style.setProperty("--i", ordem);
    atributos.append(atributo);
  });

  const historico = await carregarHistorico(dbfId);
  if (renderizacao !== numeroRenderizacao) {
    return;
  }
  const listaHistorico = ficha.querySelector('[data-campo="historico"]');
  historico.forEach(({ patch, entrada }) => {
    const linha = clonar("tpl-historico");
    const link = linha.querySelector('[data-campo="patch"]');
    link.href = rotaPatch(entrada.arquivo);
    link.textContent = `Patch ${patch.versao ?? entrada.versao}`;
    preencherData(linha.querySelector('[data-campo="data"]'), patch.data ?? entrada.data);
    const grupos = patch.cartas ?? {};
    const mudancas = [...(grupos.buffs ?? []), ...(grupos.nerfs ?? []), ...(grupos.alteradas ?? [])]
      .find((item) => String(item.dbfId) === String(dbfId))?.mudancas ?? [];
    const listaMudancas = linha.querySelector('[data-campo="mudancas"]');
    mudancas.forEach((mudanca, indice) => listaMudancas.append(renderizarMudanca(mudanca, indice)));
    listaHistorico.append(linha);
  });

  ficha.querySelector('[data-campo="sem-historico"]').hidden = historico.length > 0;
  conteudo.append(ficha);
  marcarPatchAtivo("");
  efeitos.revelarTitulos(conteudo);
  efeitos.contar(conteudo);
}

async function carregarHistorico(dbfId) {
  const encontrados = await Promise.all(indice.map(async (entrada) => {
    const patch = await carregarPatch(entrada.arquivo);
    return { patch, entrada };
  }));
  const somentePatches = encontrados.map(({ patch }) => patch);
  const historico = historicoDaCarta(dbfId, somentePatches);
  return historico.map((patch) => encontrados.find((item) => item.patch === patch));
}

function inserirTextoSeguro(elemento, texto) {
  const pilha = [elemento];

  for (const token of higienizarTexto(texto)) {
    if (token.tipo === "texto") {
      pilha[pilha.length - 1].append(document.createTextNode(token.texto));
      continue;
    }

    if (token.fechar) {
      if (pilha.length > 1 && pilha[pilha.length - 1].tagName.toLowerCase() === token.nome) {
        pilha.pop();
      }
      continue;
    }

    const no = document.createElement(token.nome);
    pilha[pilha.length - 1].append(no);
    pilha.push(no);
  }
}

function configurarBusca() {
  campoBusca.addEventListener("focus", () => {
    carregarCartas().catch(mostrarErro);
  });
  campoBusca.addEventListener("input", async () => {
    const consulta = campoBusca.value;
    if (consulta.trim().length < 2) {
      fecharBusca();
      return;
    }

    try {
      const cartas = await carregarCartas();
      renderizarResultados(buscar(cartas, consulta));
    } catch {
      mostrarErro();
    }
  });
  campoBusca.addEventListener("keydown", navegarBusca);
  document.addEventListener("click", (evento) => {
    if (!evento.target.closest(".busca")) {
      fecharBusca();
    }
  });
}

function renderizarResultados(cartas) {
  resultadosBusca.replaceChildren();
  resultadoAtivo = -1;

  if (!cartas.length) {
    const nenhum = document.createElement("button");
    nenhum.type = "button";
    nenhum.disabled = true;
    nenhum.className = "resultado";
    nenhum.textContent = "Nenhuma carta com esse nome";
    resultadosBusca.append(nenhum);
  } else {
    cartas.forEach((carta, ordem) => {
      const resultado = clonar("tpl-resultado");
      const botao = resultado.querySelector(".resultado");
      preencher(resultado, "nome", carta.nome);
      preencher(resultado, "info", carta.custo === null || carta.custo === undefined
        ? nomeClasse(carta.classe)
        : `${nomeClasse(carta.classe)} · ${carta.custo} de mana`);
      botao.setAttribute("aria-selected", "false");
      botao.style.setProperty("--i", ordem);
      botao.addEventListener("click", () => {
        fecharBusca();
        window.location.hash = `#carta/${carta.dbfId}`;
      });
      resultadosBusca.append(resultado);
    });
  }

  resultadosBusca.hidden = false;
}

function navegarBusca(evento) {
  const opcoes = [...resultadosBusca.querySelectorAll('[role="option"]:not([disabled])')];
  if (evento.key === "Escape") {
    fecharBusca();
    return;
  }
  if (!opcoes.length || !["ArrowDown", "ArrowUp", "Enter"].includes(evento.key)) {
    return;
  }

  evento.preventDefault();
  if (evento.key === "Enter" && resultadoAtivo >= 0) {
    opcoes[resultadoAtivo].click();
    return;
  }

  const passo = evento.key === "ArrowUp" ? -1 : 1;
  resultadoAtivo = resultadoAtivo < 0
    ? (passo < 0 ? opcoes.length - 1 : 0)
    : (resultadoAtivo + passo + opcoes.length) % opcoes.length;
  opcoes.forEach((opcao, indice) => {
    opcao.setAttribute("aria-selected", String(indice === resultadoAtivo));
  });
}

function fecharBusca() {
  resultadosBusca.hidden = true;
  resultadoAtivo = -1;
}

function marcarPatchAtivo(arquivo) {
  lista.querySelectorAll(".patch").forEach((botao, ordem) => {
    const ativo = indice[ordem]?.arquivo === arquivo;
    botao.setAttribute("aria-current", String(ativo));
  });
}

function clonar(id) {
  const modelo = porId(id);
  if (!modelo?.content) {
    throw new Error(`Modelo ausente: ${id}`);
  }
  return modelo.content.cloneNode(true);
}

function preencher(raiz, nome, valor) {
  const alvo = raiz.querySelector(`[data-campo="${nome}"]`);
  if (alvo) {
    alvo.textContent = String(valor ?? "");
  }
}

function preencherData(elemento, data) {
  const valor = String(data ?? "");
  elemento.dateTime = valor;
  const dataLocal = new Date(`${valor}T00:00:00Z`);
  elemento.textContent = Number.isNaN(dataLocal.getTime())
    ? valor
    : new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeZone: "UTC" }).format(dataLocal);
}

function rotuloContagem(quantidade, singular) {
  return `${quantidade} ${singular}${quantidade === 1 ? "" : "s"}`;
}

function rotuloCampo(campo) {
  const rotulos = {
    custo: "custo",
    ataque: "ataque",
    vida: "vida",
    durabilidade: "durabilidade",
    armadura: "armadura"
  };
  return rotulos[campo] ?? campo;
}

function ocultarEstados() {
  estadoCarregando.hidden = true;
  estadoVazio.hidden = true;
  estadoErro.hidden = true;
}

function mostrarVazio() {
  ocultarEstados();
  estadoVazio.hidden = false;
}

function mostrarErro() {
  ocultarEstados();
  estadoErro.hidden = false;
}
