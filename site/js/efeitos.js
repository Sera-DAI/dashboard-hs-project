export function dividir(el, documento = document) {
  if (el.dataset.dividido) {
    return;
  }
  let indice = 0;
  const andar = (no) => [...no.childNodes].forEach((filho) => {
    if (filho.nodeType === 3) {
      const fragmento = documento.createDocumentFragment();
      for (const palavra of filho.textContent.split(/(\s+)/)) {
        if (!palavra) {
          continue;
        }
        if (/^\s+$/.test(palavra)) {
          fragmento.append(palavra);
          continue;
        }
        const span = documento.createElement("span");
        span.className = "sobe";
        for (const letra of palavra) {
          const caractere = documento.createElement("span");
          caractere.textContent = letra;
          caractere.style.setProperty("--l", indice);
          indice += 1;
          span.append(caractere);
        }
        fragmento.append(span);
      }
      filho.replaceWith(fragmento);
    } else if (filho.nodeType === 1 && filho.namespaceURI !== "http://www.w3.org/2000/svg" && !filho.classList.contains("ds")) {
      andar(filho);
    }
  });
  andar(el);
  el.dataset.dividido = "true";
}

export function iniciarEfeitos(documento = document, janela = window) {
  const $ = (seletor, raiz = documento) => raiz.querySelector(seletor);
  const $$ = (seletor, raiz = documento) => [...raiz.querySelectorAll(seletor)];
  const movimento = janela.matchMedia("(prefers-reduced-motion: reduce)");
  const fino = janela.matchMedia("(pointer: fine)");
  const decorativo = () => !movimento.matches && fino.matches;
  const animacoes = new Set();
  const grupos = new WeakMap();
  let pagina = "inicio";
  let quadro = 0;
  let parar;
  let digitando;
  let giro;
  let listaFalas = [];
  let fraseAtual = "";
  const nomes = { inicio: "Início", patches: "Patches", cartas: "Cartas", noticias: "Notícias", meta: "Meta" };
  const claras = [];

  const ioMarca = janela.IntersectionObserver ? new janela.IntersectionObserver((entradas) => {
    for (const entrada of entradas) {
      if (entrada.isIntersecting) {
        entrada.target.classList.add("marcado");
        ioMarca.unobserve(entrada.target);
      }
    }
  }, { threshold: 0.4 }) : null;

  if (!movimento.matches) {
    $$(".cabeca-pagina h1, .titulo-hero").forEach((el) => dividir(el, documento));
  }

  function falar(frase) {
    clearInterval(digitando);
    fraseAtual = frase;
    const alvo = $('[data-pagina="' + pagina + '"] [data-fala]');
    if (!alvo) {
      return;
    }
    alvo.textContent = frase;
    if (movimento.matches || !frase) {
      return;
    }
    let indice = 0;
    alvo.textContent = "";
    digitando = janela.setInterval(() => {
      indice += 1;
      alvo.textContent = frase.slice(0, indice);
      if (indice >= frase.length) {
        clearInterval(digitando);
      }
    }, 24);
  }

  function rodarFalas(nova, lista) {
    clearInterval(giro);
    clearInterval(digitando);
    pagina = nova;
    listaFalas = lista;
    let indice = 0;
    falar(lista[0] ?? "");
    if (!movimento.matches && lista.length > 1) {
      giro = janela.setInterval(() => {
        if (!documento.hidden) {
          indice += 1;
          falar(lista[indice % lista.length]);
        }
      }, 6500);
    }
  }

  function medir() {
    const maximo = documento.documentElement.scrollHeight - janela.innerHeight;
    const progresso = maximo > 0 ? Math.max(0, Math.min(1, janela.scrollY / maximo)) : 0;
    for (const seletor of ["#progresso", "#fio"]) {
      $(seletor)?.style.setProperty("--p", progresso.toFixed(4));
    }
    $$("#fio .nos b").forEach((no) => no.classList.toggle("acesa", progresso + 0.004 >= Number(no.dataset.f)));
    const rotulo = $("#progresso b");
    if (rotulo) {
      rotulo.textContent = nomes[pagina] + " · " + (progresso < 0.2 ? "início" : progresso > 0.8 ? "fim" : "meio") + " · " + Math.round(progresso * 100) + "%";
    }
    for (const clara of claras) {
      if (!clara.host.getClientRects().length) {
        continue;
      }
      const caixa = clara.host.getBoundingClientRect();
      const fracao = decorativo() ? Math.max(0, Math.min(1, (janela.innerHeight - caixa.top) / (caixa.height + janela.innerHeight * 0.55))) : 1;
      clara.svg.style.setProperty("--d", fracao.toFixed(3));
      if (decorativo() && caixa.bottom >= 0 && caixa.top <= janela.innerHeight) {
        const ponto = clara.linha.getPointAtLength(clara.linha.getTotalLength() * fracao);
        clara.agulha.style.left = ponto.x / 10 + "%";
        clara.agulha.style.top = ponto.y / 4 + "%";
        clara.agulha.style.opacity = fracao > 0.02 && fracao < 0.99 ? "1" : "0";
      } else {
        clara.agulha.style.opacity = "0";
      }
    }
  }

  function montarNos() {
    const nos = $("#fio .nos");
    if (!nos) {
      return;
    }
    nos.replaceChildren();
    const maximo = documento.documentElement.scrollHeight - janela.innerHeight;
    if (maximo > 0) {
      const vistos = new Set();
      $$('[data-pagina="' + pagina + '"] > section').slice(1).forEach((secao) => {
        const fracao = Math.max(0, Math.min(1, (secao.getBoundingClientRect().top + janela.scrollY - 70) / maximo));
        const chave = Math.round(fracao * 40);
        if (fracao <= 0.01 || fracao >= 0.99 || vistos.has(chave)) {
          return;
        }
        vistos.add(chave);
        const no = documento.createElement("b");
        no.dataset.f = fracao.toFixed(4);
        no.style.top = fracao * 100 + "%";
        nos.append(no);
      });
    }
    medir();
  }

  function atualizar() {
    if (!quadro) {
      quadro = janela.requestAnimationFrame(() => {
        quadro = 0;
        montarNos();
      });
    }
  }

  janela.addEventListener("scroll", () => {
    atualizar();
    $("#progresso")?.classList.add("mexendo");
    clearTimeout(parar);
    parar = janela.setTimeout(() => $("#progresso")?.classList.remove("mexendo"), 1200);
  }, { passive: true });
  janela.addEventListener("resize", atualizar);
  if (janela.ResizeObserver) {
    new janela.ResizeObserver(atualizar).observe(documento.body);
  }
  documento.addEventListener("toggle", atualizar, true);

  function ceu(host, claro) {
    const canvas = documento.createElement("canvas");
    canvas.className = "ceu";
    canvas.setAttribute("aria-hidden", "true");
    host.classList.add("secao-ceu");
    host.prepend(canvas);
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      canvas.remove();
      return;
    }
    let largura = 0;
    let altura = 0;
    let estrelas = [];
    let visivel = false;
    let raf = 0;
    let mx = -999;
    let my = -999;
    const cor = claro ? "194,138,10" : "255,255,255";
    const ouro = claro ? "184,135,26" : "243,210,122";

    function desenhar(tempo = 0) {
      ctx.clearRect(0, 0, largura, altura);
      for (const estrela of estrelas) {
        if (decorativo() && visivel && !documento.hidden) {
          estrela.x = (estrela.x + estrela.dx + largura) % largura;
          estrela.y = (estrela.y + estrela.dy + altura) % altura;
        }
        const brilho = decorativo() ? Math.max(0.1, 0.5 + 0.4 * Math.sin(tempo / 900 + estrela.fase)) : 0.5;
        ctx.fillStyle = "rgba(" + cor + "," + brilho * (claro ? 0.55 : 0.75) + ")";
        ctx.beginPath();
        ctx.arc(estrela.x, estrela.y, estrela.raio, 0, Math.PI * 2);
        ctx.fill();
      }
      if (decorativo() && mx > -900) {
        const perto = estrelas.filter((estrela) => Math.hypot(estrela.x - mx, estrela.y - my) < 180).slice(0, 8);
        ctx.lineWidth = 1;
        perto.forEach((a, indice) => {
          for (const b of perto.slice(indice + 1)) {
            const distancia = Math.hypot(a.x - b.x, a.y - b.y);
            if (distancia < 150) {
              ctx.strokeStyle = "rgba(" + ouro + "," + (1 - distancia / 150) * 0.6 + ")";
              ctx.beginPath();
              ctx.moveTo(a.x, a.y);
              ctx.lineTo(b.x, b.y);
              ctx.stroke();
            }
          }
        });
      }
      raf = decorativo() && visivel && !documento.hidden ? janela.requestAnimationFrame(desenhar) : 0;
    }

    function retomar() {
      janela.cancelAnimationFrame(raf);
      raf = 0;
      mx = -999;
      my = -999;
      if (largura) {
        desenhar();
      }
    }

    function montar() {
      const caixa = host.getBoundingClientRect();
      if (!caixa.width || !caixa.height) {
        return;
      }
      largura = caixa.width;
      altura = caixa.height;
      // Sem movimento as estrelas ficam paradas: pontos de 1 px não pedem densidade dupla, e o canvas fica até 4 vezes menor.
      const dpr = decorativo() ? Math.min(janela.devicePixelRatio || 1, 2) : 1;
      canvas.width = Math.round(largura * dpr);
      canvas.height = Math.round(altura * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      estrelas = Array.from({ length: Math.min(90, Math.round(largura * altura / (claro ? 26000 : 15000))) }, () => ({
        x: Math.random() * largura,
        y: Math.random() * altura,
        raio: 0.4 + Math.random() * 1.3,
        fase: Math.random() * 6.28,
        dx: (Math.random() - 0.5) * 0.07,
        dy: (Math.random() - 0.5) * 0.04
      }));
      retomar();
    }
    host.addEventListener("pointermove", (evento) => {
      if (!decorativo() || evento.pointerType !== "mouse") {
        return;
      }
      const caixa = host.getBoundingClientRect();
      mx = evento.clientX - caixa.left;
      my = evento.clientY - caixa.top;
    }, { passive: true });
    host.addEventListener("pointerleave", () => {
      mx = -999;
      my = -999;
    });
    // O céu só é montado quando a seção chega perto da tela (D50): as de baixo não gastam canvas na abertura.
    const montarSePerto = () => {
      if (visivel || largura) {
        montar();
      }
    };
    if (janela.ResizeObserver) {
      new janela.ResizeObserver(montarSePerto).observe(host);
    } else {
      janela.addEventListener("resize", montarSePerto);
    }
    if (janela.IntersectionObserver) {
      new janela.IntersectionObserver(([entrada]) => {
        visivel = entrada.isIntersecting;
        if (visivel && !largura) {
          montar();
        } else {
          retomar();
        }
      }, { rootMargin: "300px 0px" }).observe(host);
    } else {
      visivel = true;
      montar();
    }
    animacoes.add(retomar);
  }

  $$(".secao.s-noite, .secao.s-profundo, .secao.s-marfim").forEach((host) => ceu(host, host.classList.contains("s-marfim")));

  const ns = "http://www.w3.org/2000/svg";
  $$(".secao.s-marfim").forEach((host, indice) => {
    const svg = documento.createElementNS(ns, "svg");
    svg.setAttribute("class", "fio-claro");
    svg.setAttribute("viewBox", "0 0 1000 400");
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("aria-hidden", "true");
    const caminho = indice % 2 ? "M1020 60 C800 -20 700 220 480 150 S180 40 -20 300" : "M-20 60 C200 -20 300 220 520 150 S820 40 1020 300";
    const linha = documento.createElementNS(ns, "path");
    linha.setAttribute("d", caminho);
    linha.setAttribute("pathLength", "1");
    const outra = linha.cloneNode();
    outra.setAttribute("class", "b");
    outra.setAttribute("transform", "translate(0 26)");
    svg.append(linha, outra);
    const agulha = documento.createElement("span");
    agulha.className = "agulha-clara";
    agulha.setAttribute("aria-hidden", "true");
    agulha.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 20 L19 5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><ellipse cx="18.4" cy="5.6" rx="1.1" ry="2.4" transform="rotate(45 18.4 5.6)" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>';
    host.prepend(svg, agulha);
    claras.push({ host, svg, linha, agulha });
  });

  if (decorativo()) {
    $$(".pagina").forEach((pg) => {
      [...pg.children].filter((no) => no.tagName === "SECTION").forEach((secao, indice) => {
        const anterior = secao.previousElementSibling;
        if (anterior?.tagName !== "SECTION" || anterior.classList.contains("s-marfim") === secao.classList.contains("s-marfim")) {
          return;
        }
        const emenda = documento.createElement("div");
        emenda.className = "emenda";
        emenda.setAttribute("aria-hidden", "true");
        emenda.innerHTML = '<i><b></b></i>';
        emenda.firstChild.style.setProperty("--x", indice % 2 ? "88%" : "12%");
        secao.before(emenda);
      });
    });
  }

  documento.addEventListener("pointermove", (evento) => {
    if (!decorativo() || evento.pointerType !== "mouse") {
      return;
    }
    const cena = $("#cena");
    cena?.style.setProperty("--px", (evento.clientX / janela.innerWidth - 0.5) * 2);
    cena?.style.setProperty("--py", (evento.clientY / janela.innerHeight - 0.5) * 2);
    const botao = evento.target.closest?.(".grade-cartas button");
    const carta = botao?.querySelector(".carta");
    if (carta) {
      const caixa = botao.getBoundingClientRect();
      carta.style.setProperty("--mx", (evento.clientX - caixa.left) / caixa.width * 100 + "%");
      carta.style.setProperty("--my", (evento.clientY - caixa.top) / caixa.height * 100 + "%");
    }
  }, { passive: true });

  const poeira = $("#poeira");
  const ctx = poeira?.getContext("2d");
  let particulas = [];
  let rafPoeira = 0;
  function limparPoeira() {
    janela.cancelAnimationFrame(rafPoeira);
    rafPoeira = 0;
    particulas = [];
    if (ctx) {
      ctx.clearRect(0, 0, poeira.width, poeira.height);
    }
  }
  function redimensionarPoeira() {
    if (poeira) {
      poeira.width = janela.innerWidth;
      poeira.height = janela.innerHeight;
    }
    limparPoeira();
  }
  function desenharPoeira() {
    ctx.clearRect(0, 0, poeira.width, poeira.height);
    particulas = particulas.filter((particula) => particula.vida > 0);
    for (const particula of particulas) {
      particula.x += particula.vx;
      particula.y += particula.vy;
      particula.vy += 0.02;
      particula.vida -= 0.028;
      ctx.globalAlpha = Math.max(0, particula.vida);
      ctx.fillStyle = particula.clara ? "#c28a0a" : particula.ouro ? "#f3d27a" : "#a78bfa";
      const r = particula.raio * (0.6 + particula.vida);
      const { x, y } = particula;
      ctx.beginPath();
      ctx.moveTo(x, y - r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.quadraticCurveTo(x, y, x, y + r);
      ctx.quadraticCurveTo(x, y, x - r, y);
      ctx.quadraticCurveTo(x, y, x, y - r);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    rafPoeira = particulas.length && decorativo() && !documento.hidden ? janela.requestAnimationFrame(desenharPoeira) : 0;
  }
  documento.addEventListener("pointermove", (evento) => {
    if (!ctx || !decorativo() || evento.pointerType !== "mouse" || documento.hidden) {
      return;
    }
    for (let indice = 0; indice < 2; indice += 1) {
      particulas.push({
        x: evento.clientX + (Math.random() - 0.5) * 8,
        y: evento.clientY + (Math.random() - 0.5) * 8,
        vx: (Math.random() - 0.5) * 0.9,
        vy: Math.random() * 0.5 + 0.1,
        raio: Math.random() * 3 + 2,
        vida: 1,
        ouro: Math.random() < 0.6,
        clara: Boolean(evento.target.closest?.(".s-marfim, .hero-deck"))
      });
    }
    particulas = particulas.slice(-60);
    if (!rafPoeira) {
      rafPoeira = janela.requestAnimationFrame(desenharPoeira);
    }
  }, { passive: true });
  janela.addEventListener("resize", redimensionarPoeira);
  redimensionarPoeira();

  function preferencias() {
    limparPoeira();
    animacoes.forEach((retomar) => retomar());
    if (movimento.matches) {
      clearInterval(giro);
      clearInterval(digitando);
      falar(fraseAtual);
      $$(".carta").forEach((carta) => {
        carta.style.setProperty("--rx", "0deg");
        carta.style.setProperty("--ry", "0deg");
      });
      $$(".grupo-patch").forEach((grupo) => grupos.get(grupo)?.finish());
    } else {
      rodarFalas(pagina, listaFalas);
    }
    $$(".emenda").forEach((emenda) => {
      emenda.hidden = !decorativo();
    });
    atualizar();
  }
  movimento.addEventListener("change", preferencias);
  fino.addEventListener("change", preferencias);
  documento.addEventListener("visibilitychange", () => {
    limparPoeira();
    animacoes.forEach((retomar) => retomar());
  });

  return {
    get reduzir() {
      return movimento.matches;
    },
    rodarFalas,
    atualizar,
    mudarPagina(nova) {
      pagina = nova;
      atualizar();
    },
    observarMarcas(raiz) {
      $$(".marcavel", raiz).forEach((el) => {
        if (ioMarca && !movimento.matches) {
          el.classList.remove("marcado");
          ioMarca.observe(el);
        } else {
          el.classList.add("marcado");
        }
      });
    },
    contar(raiz) {
      $$("[data-contar]", raiz).forEach((el) => {
        const valor = Number(el.textContent);
        if (movimento.matches || !valor) {
          return;
        }
        const inicio = janela.performance.now();
        const passo = (agora) => {
          if (!el.isConnected) {
            return;
          }
          const fracao = movimento.matches ? 1 : Math.min(1, (agora - inicio) / 700);
          el.textContent = String(Math.round(valor * fracao));
          if (fracao < 1) {
            janela.requestAnimationFrame(passo);
          }
        };
        janela.requestAnimationFrame(passo);
      });
    },
    alternarGrupo(grupo, abrir, sincronizar) {
      const anterior = grupos.get(grupo);
      const inicio = grupo.offsetHeight;
      anterior?.cancel();
      if (movimento.matches || !grupo.animate) {
        grupo.open = abrir;
        sincronizar();
        atualizar();
        return;
      }
      $$(".grade-cartas li", grupo).forEach((item, indice) => item.style.setProperty("--d", abrir ? Math.min(indice, 8) : Math.max(0, 8 - indice)));
      grupo.classList.toggle("fechando", !abrir);
      if (abrir) {
        grupo.classList.add("abrindo-ini");
        grupo.open = true;
      }
      const fim = abrir ? grupo.scrollHeight : $("summary", grupo).offsetHeight + parseFloat(janela.getComputedStyle(grupo).paddingTop || 0);
      janela.requestAnimationFrame(() => grupo.classList.remove("abrindo-ini"));
      const animacao = grupo.animate({ height: [inicio + "px", fim + "px"] }, { duration: abrir ? 650 : 560, easing: "cubic-bezier(.16, 1, .3, 1)", fill: "both" });
      grupos.set(grupo, animacao);
      animacao.onfinish = () => {
        grupo.open = abrir;
        grupo.classList.remove("fechando", "abrindo-ini");
        grupos.delete(grupo);
        animacao.cancel();
        sincronizar();
        atualizar();
      };
      animacao.oncancel = () => grupo.classList.remove("fechando", "abrindo-ini");
    }
  };
}
