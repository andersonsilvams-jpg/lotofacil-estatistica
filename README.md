# Painel Estatístico da Lotofácil

Aplicação Streamlit para explorar os resultados da Lotofácil, com análise dedicada aos concursos cujo número termina em zero (10, 20, 30, ...).

## Recursos

- Consulta do histórico pela API pública de resultados das Loterias CAIXA.
- Frequência histórica das 25 dezenas.
- Recorte exclusivo dos concursos final 0.
- Ranking e pares mais recorrentes em cada recorte.
- Frequência recente e atraso atual.
- Gerador de apostas com critérios histórico geral, final 0 ou combinado.
- Exportação de jogos e relatórios em CSV e Excel.
- Cache de uma hora e botão para atualização manual.

## Publicar no Streamlit Community Cloud

1. Acesse https://share.streamlit.io/
2. Entre com sua conta GitHub.
3. Selecione o repositório `andersonsilvams-jpg/lotofacil-estatistica`.
4. Branch: `main`.
5. Main file path: `app.py`.
6. Clique em Deploy.

## Executar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Fonte e observações

Os resultados são solicitados à API pública do Portal de Loterias da CAIXA. A disponibilidade do endpoint depende da própria CAIXA e de acesso de rede do ambiente que hospeda a aplicação.

As frequências representam apenas ocorrências passadas. Sorteios são independentes: resultados anteriores não tornam uma dezena mais provável no próximo concurso. Este painel não prevê resultados nem garante premiações.
