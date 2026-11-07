# Painel Estatístico da Lotofácil

Painel Streamlit para análise do histórico da Lotofácil, com uma área dedicada aos concursos terminados em zero (10, 20, 30...).

## Funcionalidades

- Frequência histórica de cada dezena (01 a 25).
- Análise exclusiva dos concursos de final 0.
- Comparação entre frequência geral e frequência dos concursos final 0.
- Pares de dezenas mais recorrentes.
- Frequência nos últimos 20, 50, 100, 200 ou 500 concursos.
- Dezenas mais atrasadas.
- Gerador de apostas por histórico geral, final 0 ou critério combinado.
- Exportação de jogos e rankings em CSV e Excel.

## Atualização dos dados

O GitHub Actions executa diariamente às 07h15 (horário de Campo Grande, UTC-4). Ele tenta baixar a planilha histórica diretamente do serviço de Loterias da CAIXA. Se esse download estiver indisponível, usa como contingência um CSV público compilado a partir dos resultados da CAIXA, publicado pelo ValorFinal sob licença CC BY 4.0, com atribuição.

O histórico validado é salvo no arquivo dados/historico.csv. O painel lê esse arquivo versionado; se ainda não existir, utiliza as fontes de contingência.

## Publicar no Streamlit Community Cloud

1. Acesse https://share.streamlit.io/
2. Entre com sua conta GitHub.
3. Clique em Create app.
4. Repositório: andersonsilvams-jpg/lotofacil-estatistica.
5. Branch: main.
6. Main file path: app.py.
7. Clique em Deploy.

## Executar localmente

    pip install -r requirements.txt
    streamlit run app.py

## Fontes e observação

Fonte primária dos resultados: serviço de Loterias da CAIXA. Fonte de contingência: ValorFinal, histórico aberto da Lotofácil (https://valorfinal.com.br/dados/loteria-lotofacil), licença CC BY 4.0. Confira os resultados no site oficial https://loterias.caixa.gov.br/Paginas/Lotofacil.aspx.

Frequências passadas descrevem apenas resultados históricos. Cada sorteio é independente e o painel não prevê resultados nem garante premiações.
