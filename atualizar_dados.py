from pathlib import Path

from dados_utils import baixar_historico_caixa, baixar_historico_publicado

DESTINO = Path("dados/historico.csv")

def main():
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    try:
        df = baixar_historico_caixa()
        fonte = "planilha histórica da CAIXA"
    except Exception as erro_caixa:
        print(f"Download direto da CAIXA indisponível: {erro_caixa}")
        df = baixar_historico_publicado()
        fonte = "CSV público do ValorFinal (dados compilados da CAIXA; CC BY 4.0)"

    export = df.copy()
    export["data"] = export["data"].dt.strftime("%Y-%m-%d")
    export["dezenas"] = export["dezenas_txt"]
    export = export[["concurso", "data", "dezenas"]]
    export.to_csv(DESTINO, index=False, sep=";", encoding="utf-8-sig")
    print(f"Fonte utilizada: {fonte}")
    print(f"Histórico atualizado: {len(export)} concursos.")
    print(f"Primeiro concurso: {int(export['concurso'].min())}")
    print(f"Último concurso: {int(export['concurso'].max())}")
    print(f"Arquivo: {DESTINO}")

if __name__ == "__main__":
    main()
