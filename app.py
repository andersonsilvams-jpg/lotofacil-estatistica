import io
import random
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Lotofácil Estatística", page_icon="🍀", layout="wide")

HISTORICO_URL = "https://raw.githubusercontent.com/andersonsilvams-jpg/lotofacil-estatistica/main/dados/historico.csv"

CAIXA_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Origin": "https://loterias.caixa.gov.br",
    "Referer": "https://loterias.caixa.gov.br/",
}

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
div[data-testid="stMetric"] {background: rgba(120,120,120,.08); padding: 14px; border-radius: 12px;}
.ball {display:inline-flex; width:39px; height:39px; margin:3px; border-radius:50%; background:#6b36a8;
color:white; align-items:center; justify-content:center; font-weight:700;}
.small-note {color:#888; font-size:.85rem;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600, show_spinner=False)
def get_json(url):
    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.json()

def montar_historico(csv_df):
    required = {"concurso", "data", "dezenas"}
    if not required.issubset(set(csv_df.columns)):
        raise ValueError("O CSV não contém as colunas esperadas.")
    rows = []
    for _, row in csv_df.iterrows():
        nums = [int(x) for x in str(row["dezenas"]).replace(",", " ").split()]
        if len(nums) != 15 or len(set(nums)) != 15 or any(n < 1 or n > 25 for n in nums):
            continue
        rows.append({
            "concurso": int(row["concurso"]),
            "data": pd.to_datetime(row["data"], errors="coerce"),
            "dezenas": sorted(nums),
            "dezenas_txt": " ".join(f"{n:02d}" for n in sorted(nums)),
        })
    if not rows:
        raise ValueError("O histórico CSV não contém concursos válidos.")
    return pd.DataFrame(rows).drop_duplicates("concurso").sort_values("concurso").reset_index(drop=True)

@st.cache_data(ttl=1800, show_spinner=False)
def load_history():
    # Prioriza o CSV versionado no próprio GitHub, atualizado diariamente pelo Actions.
    try:
        response = requests.get(HISTORICO_URL, timeout=30)
        response.raise_for_status()
        csv_df = pd.read_csv(io.StringIO(response.content.decode("utf-8-sig")), sep=";")
        return montar_historico(csv_df), "CSV do GitHub (atualização automática diária)"
    except Exception:
        pass

    # Contingência: CSV público compilado a partir dos resultados da CAIXA.
    try:
        from dados_utils import baixar_historico_publicado
        return baixar_historico_publicado(), "CSV do ValorFinal, compilado a partir dos resultados da CAIXA"
    except Exception:
        pass

    # Última contingência: planilha histórica oficial da CAIXA.
    from dados_utils import baixar_historico_caixa
    return baixar_historico_caixa(), "Planilha histórica oficial da CAIXA"


def frequency_table(df):
    counts = {n: 0 for n in range(1, 26)}
    for nums in df["dezenas"]:
        for n in nums:
            counts[n] += 1
    total = len(df)
    return pd.DataFrame([
        {"Dezena": f"{n:02d}", "Número": n, "Ocorrências": counts[n],
         "Frequência (%)": round(counts[n] / total * 100, 2) if total else 0}
        for n in range(1, 26)
    ]).sort_values(["Ocorrências", "Número"], ascending=[False, True])

def pair_table(df, top=20):
    from collections import Counter
    pairs = Counter()
    for nums in df["dezenas"]:
        vals = sorted(nums)
        for i in range(len(vals)):
            for j in range(i+1, len(vals)):
                pairs[(vals[i], vals[j])] += 1
    return pd.DataFrame([
        {"Par": f"{a:02d}–{b:02d}", "Ocorrências": c}
        for (a,b), c in pairs.most_common(top)
    ])

def build_games(strategy, qty, base_count, seed=None):
    rng = random.Random(seed)
    games = []
    for _ in range(qty):
        if strategy == "Final 0":
            pool = final0_rank
        elif strategy == "Histórico geral":
            pool = overall_rank
        else:
            pool = combined_rank
        fixed = pool[:base_count]
        remaining = [n for n in range(1, 26) if n not in fixed]
        choose = 15 - len(fixed)
        game = sorted(fixed + rng.sample(remaining, choose))
        # Evita duplicação na lista gerada.
        attempts = 0
        while tuple(game) in games and attempts < 100:
            game = sorted(fixed + rng.sample(remaining, choose))
            attempts += 1
        games.append(tuple(game))
    return games

st.title("🍀 Painel Estatístico da Lotofácil")
st.caption("Histórico de resultados, análise especial dos concursos de final 0 e gerador de combinações.")
st.info("Os resultados são consultados na API pública das Loterias CAIXA. Frequências históricas descrevem sorteios passados e não aumentam a chance de uma dezena no próximo concurso.")

with st.sidebar:
    st.header("Controles")
    if st.button("🔄 Atualizar dados agora", use_container_width=True):
        load_history.clear()
        st.rerun()
    st.caption("O histórico é atualizado diariamente pelo GitHub Actions; o botão limpa o cache e consulta novamente as fontes.")

try:
    with st.spinner("Verificando o último concurso..."):
        history, data_source = load_history()
except Exception as exc:
    st.error(f"Falha ao carregar os resultados: {exc}")
    st.markdown(f"[Consultar resultados oficiais na CAIXA](https://loterias.caixa.gov.br/Paginas/Lotofacil.aspx)")
    st.stop()

last_row = history.iloc[-1]
final0 = history[history["concurso"] % 10 == 0].copy()
overall_freq = frequency_table(history)
final0_freq = frequency_table(final0)
recent_n = min(100, len(history))
recent_freq = frequency_table(history.tail(recent_n))

overall_rank = overall_freq["Número"].tolist()
final0_rank = final0_freq["Número"].tolist()
combined_scores = {}
for n in range(1, 26):
    a = overall_freq.loc[overall_freq["Número"] == n, "Frequência (%)"].iloc[0]
    b = final0_freq.loc[final0_freq["Número"] == n, "Frequência (%)"].iloc[0] if len(final0) else 0
    combined_scores[n] = 0.5 * a + 0.5 * b
combined_rank = sorted(range(1,26), key=lambda n: (-combined_scores[n], n))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Concursos carregados", f"{len(history):,}".replace(",", "."))
c2.metric("Último concurso", f"#{int(last_row['concurso'])}")
c3.metric("Concursos final 0", f"{len(final0):,}".replace(",", "."))
c4.metric("Data do último resultado", last_row["data"].strftime("%d/%m/%Y") if pd.notna(last_row["data"]) else "—")

st.caption(f"Fonte dos dados: {data_source} · Último concurso disponível: {int(last_row['concurso'])}")
st.subheader(f"Último resultado · Concurso {int(last_row['concurso'])}")
st.markdown("".join([f'<span class="ball">{n:02d}</span>' for n in last_row["dezenas"]]), unsafe_allow_html=True)
st.caption(f"Data: {last_row['data'].strftime('%d/%m/%Y') if pd.notna(last_row['data']) else 'não informada'} · Fonte: Loterias CAIXA")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Visão geral", "🔟 Concursos final 0", "📈 Frequência e atrasos", "🎲 Gerador de jogos", "📚 Histórico"
])

with tab1:
    st.subheader("Frequência histórica — todos os concursos")
    fig = px.bar(overall_freq.sort_values("Número"), x="Dezena", y="Ocorrências",
                 hover_data=["Frequência (%)"], title="Ocorrências de cada dezena (01 a 25)")
    fig.update_layout(xaxis_title="Dezena", yaxis_title="Quantidade de concursos")
    st.plotly_chart(fig, use_container_width=True)
    left, right = st.columns(2)
    with left:
        st.markdown("**15 dezenas mais frequentes**")
        st.dataframe(overall_freq.head(15)[["Dezena","Ocorrências","Frequência (%)"]], hide_index=True, use_container_width=True)
    with right:
        st.markdown("**Pares mais recorrentes**")
        st.dataframe(pair_table(history, 15), hide_index=True, use_container_width=True)

with tab2:
    st.subheader("Análise exclusiva dos concursos terminados em zero")
    st.write(f"Foram identificados {len(final0)} concursos: 10, 20, 30, 40... até {int(final0['concurso'].max()) if len(final0) else 0}.")
    if len(final0):
        f0 = px.bar(final0_freq.sort_values("Número"), x="Dezena", y="Ocorrências",
                    hover_data=["Frequência (%)"], title="Frequência das dezenas somente nos concursos final 0")
        st.plotly_chart(f0, use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Ranking dos concursos final 0**")
            st.dataframe(final0_freq, hide_index=True, use_container_width=True)
        with col2:
            st.markdown("**Pares mais recorrentes — final 0**")
            st.dataframe(pair_table(final0, 20), hide_index=True, use_container_width=True)
        st.markdown("**Comparação: histórico geral × final 0**")
        compare = overall_freq[["Dezena","Frequência (%)"]].merge(
            final0_freq[["Dezena","Frequência (%)"]], on="Dezena", suffixes=(" geral", " final 0"))
        compare = compare.rename(columns={"Frequência (%) geral":"Geral (%)", "Frequência (%) final 0":"Final 0 (%)"})
        compare_long = compare.melt(id_vars="Dezena", var_name="Recorte", value_name="Frequência (%)")
        st.plotly_chart(px.bar(compare_long, x="Dezena", y="Frequência (%)", color="Recorte", barmode="group"), use_container_width=True)
    else:
        st.warning("Ainda não há concurso final 0 na base.")

with tab3:
    st.subheader("Frequência e dezenas há mais tempo sem sair")
    period = st.selectbox("Janela de concursos para frequência recente", [20, 50, 100, 200, 500], index=2)
    recent = frequency_table(history.tail(min(period, len(history))))
    gap_rows = []
    last_draw = int(history["concurso"].max())
    for n in range(1,26):
        last_seen = max((int(row["concurso"]) for _, row in history.iterrows() if n in row["dezenas"]), default=0)
        gap_rows.append({"Dezena": f"{n:02d}", "Último concurso": last_seen, "Atraso atual": last_draw-last_seen})
    gaps = pd.DataFrame(gap_rows).sort_values("Atraso atual", ascending=False)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Frequência nos últimos {min(period,len(history))} concursos**")
        st.dataframe(recent, hide_index=True, use_container_width=True)
    with col2:
        st.markdown("**Atraso atual por dezena**")
        st.dataframe(gaps, hide_index=True, use_container_width=True)
    st.bar_chart(gaps.set_index("Dezena")["Atraso atual"])

with tab4:
    st.subheader("Gerador de combinações")
    col1, col2, col3 = st.columns(3)
    with col1:
        strategy = st.selectbox("Critério de seleção", ["Histórico geral", "Final 0", "Combinado"])
    with col2:
        qty = st.selectbox("Quantidade de jogos", [5, 10, 15, 20, 30], index=2)
    with col3:
        base_count = st.slider("Dezenas fixas do ranking", min_value=0, max_value=12, value=8)
    st.caption("O gerador fixa até 12 dezenas do ranking escolhido e completa cada aposta com dezenas sorteadas entre as restantes. As apostas geradas são distintas.")
    if st.button("🎯 Gerar jogos", type="primary"):
        games = build_games(strategy, qty, base_count, seed=datetime.now().microsecond)
        st.session_state["games"] = games
        st.session_state["games_strategy"] = strategy
    if "games" in st.session_state:
        st.write(f"**{len(st.session_state['games'])} jogos · estratégia {st.session_state.get('games_strategy','')}**")
        for idx, game in enumerate(st.session_state["games"], 1):
            balls = "".join([f'<span class="ball">{n:02d}</span>' for n in game])
            st.markdown(f"**Jogo {idx:02d}**<br>{balls}", unsafe_allow_html=True)
        csv = pd.DataFrame([
            {"Jogo": i+1, **{f"D{j+1:02d}": f"{n:02d}" for j,n in enumerate(game)}}
            for i, game in enumerate(st.session_state["games"])
        ]).to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button("⬇️ Baixar jogos em CSV", csv, "jogos_lotofacil.csv", "text/csv")
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            pd.DataFrame([
                {"Jogo": i+1, **{f"D{j+1:02d}": f"{n:02d}" for j,n in enumerate(game)}}
                for i, game in enumerate(st.session_state["games"])
            ]).to_excel(writer, sheet_name="Jogos", index=False)
            overall_freq.to_excel(writer, sheet_name="Ranking geral", index=False)
            final0_freq.to_excel(writer, sheet_name="Ranking final 0", index=False)
        st.download_button("📊 Baixar relatório Excel", excel_buffer.getvalue(),
                           "relatorio_lotofacil.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab5:
    st.subheader("Histórico de resultados")
    min_conc = int(history["concurso"].min())
    max_conc = int(history["concurso"].max())
    selected = st.slider("Filtrar concursos", min_value=min_conc, max_value=max_conc,
                         value=(max(min_conc, max_conc-49), max_conc))
    view = history[(history["concurso"] >= selected[0]) & (history["concurso"] <= selected[1])].copy()
    view["Data"] = view["data"].dt.strftime("%d/%m/%Y")
    view = view.rename(columns={"concurso":"Concurso", "dezenas_txt":"Dezenas"})
    st.dataframe(view[["Concurso","Data","Dezenas"]], hide_index=True, use_container_width=True)
    st.download_button("⬇️ Exportar histórico filtrado CSV",
                       view[["Concurso","Data","Dezenas"]].to_csv(index=False, sep=";", encoding="utf-8-sig"),
                       "historico_lotofacil.csv", "text/csv")

st.divider()
st.caption("Painel independente para fins estatísticos e recreativos. Fonte dos resultados: Loterias CAIXA. Confira sempre os resultados e regras no site oficial.")
