// Roda antes da página (script clássico, sem módulo) e só adianta pedidos; não monta nada (D50).
// Esconde o início quando o link abre outra página e pede cedo a arte dessa página e, nas rotas de carta, o catálogo.
// O app.js tira o atributo data-rota de <html> quando assume as páginas.
(function () {
  var hash = String(location.hash).replace(/^#\/?/, "");
  var achada = /^(patches|cartas|noticias|meta)(\/|$)/.exec(hash);
  var pagina = achada ? achada[1]
    : /^patch\//.test(hash) ? "patches"
    : /^noticia\//.test(hash) ? "noticias"
    : /^carta\//.test(hash) ? "cartas"
    : "inicio";
  document.documentElement.setAttribute("data-rota", pagina);

  // Os mesmos srcset e sizes das <img> de cada página em index.html (tests/js/desempenho.test.mjs confere).
  var faixa = "(max-width: 760px) 640px, 100vw";
  var artes = {
    inicio: ["img/inicio-darc-640.webp 640w, img/inicio-darc-1000.webp 1000w, img/inicio-darc.webp 1600w", "(max-width: 960px) 80vw, 650px"],
    patches: ["img/patches-darc-1200.webp 1200w, img/patches-darc-1800.webp 1800w, img/patches-darc.webp 2880w", faixa],
    cartas: ["img/cartas-darc-1200.webp 1200w, img/cartas-darc-1800.webp 1800w, img/cartas-darc.webp 2400w", faixa],
    noticias: ["img/noticias-darc-1200.webp 1200w, img/noticias-darc-1800.webp 1800w, img/noticias-darc.webp 2400w", faixa],
    meta: ["img/meta-darc-1200.webp 1200w, img/meta-darc-1800.webp 1800w, img/meta-darc.webp 2400w", faixa]
  };

  function pedir(atributos) {
    var no = document.createElement("link");
    no.rel = "preload";
    for (var chave in atributos) {
      no.setAttribute(chave, atributos[chave]);
    }
    document.head.appendChild(no);
  }

  pedir({ as: "image", imagesrcset: artes[pagina][0], imagesizes: artes[pagina][1], fetchpriority: "high" });
  if (pagina === "patches" || pagina === "cartas") {
    pedir({ as: "fetch", href: "dados/cartas.json", crossorigin: "" });
    pedir({ as: "fetch", href: "dados/imagens.json", crossorigin: "" });
  }
})();
