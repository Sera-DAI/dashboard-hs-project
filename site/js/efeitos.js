export function iniciarEfeitos(documento = document, janela = window) {
  const reduzirMovimento = janela.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canvas = documento.querySelector("#brasas");

  if (!reduzirMovimento && canvas) {
    iniciarBrasas(canvas, janela);
  }

  if (!reduzirMovimento) {
    documento.addEventListener("pointermove", (evento) => {
      const carta = evento.target.closest?.(".carta");
      if (!carta) {
        return;
      }

      const caixa = carta.getBoundingClientRect();
      carta.style.setProperty("--cx", `${evento.clientX - caixa.left}px`);
      carta.style.setProperty("--cy", `${evento.clientY - caixa.top}px`);
    });
  }

  return {
    contar(raiz = documento) {
      if (!reduzirMovimento) {
        raiz.querySelectorAll("[data-contar]").forEach(animarContador);
      }
    },
    revelarTitulos(raiz = documento) {
      raiz.querySelectorAll(".titulo").forEach((titulo) => {
        if (titulo.dataset.revelado === "true") {
          return;
        }

        const palavras = titulo.textContent.trim().split(/\s+/).filter(Boolean);
        titulo.replaceChildren(...palavras.map((palavra, indice) => {
          const span = documento.createElement("span");
          span.className = "palavra";
          span.style.setProperty("--i", indice);
          span.textContent = `${palavra} `;
          return span;
        }));
        titulo.dataset.revelado = "true";
      });
    }
  };
}

function iniciarBrasas(canvas, janela) {
  const contexto = canvas.getContext("2d");
  if (!contexto) {
    return;
  }

  const particulas = Array.from({ length: 55 }, () => criarParticula(canvas));
  let quadro;

  function redimensionar() {
    const escala = Math.min(janela.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(canvas.clientWidth * escala);
    canvas.height = Math.floor(canvas.clientHeight * escala);
    contexto.setTransform(escala, 0, 0, escala, 0, 0);
  }

  function desenhar() {
    const largura = canvas.clientWidth;
    const altura = canvas.clientHeight;
    contexto.clearRect(0, 0, largura, altura);

    for (const particula of particulas) {
      particula.y -= particula.velocidade;
      particula.x += Math.sin(particula.y * 0.02) * 0.25;
      particula.vida -= 0.002;

      if (particula.y < 0 || particula.vida <= 0) {
        Object.assign(particula, criarParticula(canvas, true));
      }

      const vermelho = Math.round(130 + particula.vida * 60);
      contexto.fillStyle = `rgba(255, ${vermelho}, 40, ${particula.vida * 0.55})`;
      contexto.beginPath();
      contexto.arc(particula.x, particula.y, particula.raio, 0, Math.PI * 2);
      contexto.fill();
    }

    quadro = janela.requestAnimationFrame(desenhar);
  }

  redimensionar();
  janela.addEventListener("resize", redimensionar);
  desenhar();
  canvas.dataset.quadro = String(quadro);
}

function criarParticula(canvas, noFundo = false) {
  return {
    x: Math.random() * canvas.clientWidth,
    y: noFundo ? canvas.clientHeight : Math.random() * canvas.clientHeight,
    raio: Math.random() * 2 + 0.5,
    velocidade: Math.random() * 0.7 + 0.25,
    vida: Math.random() * 0.65 + 0.35
  };
}

function animarContador(elemento) {
  const valor = Number(elemento.textContent);
  if (!Number.isFinite(valor) || valor <= 0) {
    elemento.textContent = "0";
    return;
  }

  const inicio = performance.now();
  const duracao = 700;

  function quadro(agora) {
    const progresso = Math.min((agora - inicio) / duracao, 1);
    elemento.textContent = String(Math.round(valor * progresso));
    if (progresso < 1) {
      requestAnimationFrame(quadro);
    }
  }

  elemento.textContent = "0";
  requestAnimationFrame(quadro);
}
