export class ErroDados extends Error {
  constructor() {
    super("Falha ao ler dados publicados.");
    this.name = "ErroDados";
  }
}

export function criarLeitor(fetcher, base) {
  const raiz = String(base ?? "").replace(/\/+$/, "");

  return async function lerJson(caminho) {
    const arquivo = String(caminho ?? "").replace(/^\/+/, "");

    try {
      const resposta = await fetcher(`${raiz}/${arquivo}`, {
        cf: { cacheTtl: 300, cacheEverything: true }
      });

      if (resposta.status !== 200) {
        throw new ErroDados();
      }

      return await resposta.json();
    } catch {
      throw new ErroDados();
    }
  };
}
