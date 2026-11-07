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
            for j in range(i + 1, len(vals)):
                pairs[(vals[i], vals[j])] += 1
    return pd.DataFrame([
        {"Par": f"{a:02d}–{b:02d}", "Ocorrências": count}
        for (a, b), count in pairs.most_common(top)
    ])

def pair_matrix(df):
    # Cada célula mostra em quantos concursos as duas dezenas apareceram juntas.
    matrix = [[0 for _ in range(25)] for _ in range(25)]
    for nums in df["dezenas"]:
        values = sorted(nums)
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                a, b = values[i] - 1, values[j] - 1
                matrix[a][b] += 1
                matrix[b][a] += 1

    labels = [f"{n:02d}" for n in range(1, 26)]
    result = pd.DataFrame(matrix, index=labels, columns=labels)
    for i in range(25):
        result.iat[i, i] = None
    return result


def weighted_pick(rng, candidates, quantity):
    """Seleciona sem reposição, favorecendo a ordem do ranking recebido."""
    pool = list(candidates)
    weights = [float(len(pool) - index) for index in range(len(pool))]
    selected = []
    for _ in range(min(quantity, len(pool))):
        total = sum(weights)
        point = rng.random() * total
        running = 0.0
        chosen_index = len(pool) - 1
        for index, weight in enumerate(weights):
            running += weight
            if point <= running:
                chosen_index = index
                break
        selected.append(pool.pop(chosen_index))
        weights.pop(chosen_index)
    return selected

def is_balanced_game(game):
    odd_count = sum(number % 2 for number in game)
    low_count = sum(number <= 13 for number in game)
    band_counts = [
        sum(start <= number <= start + 4 for number in game)
        for start in [1, 6, 11, 16, 21]
    ]
    total = sum(game)
    return (
        6 <= odd_count <= 9
        and 6 <= low_count <= 9
        and all(1 <= count <= 5 for count in band_counts)
        and 165 <= total <= 225
    )

def build_games(
    strategy,
    quantity,
    candidate_size,
    overall_rank,
    cold_rank,
    final0_rank,
    recent_rank,
    overdue_rank,
    seed=None,
):
    rng = random.Random(seed)
    games = []
    seen = set()
    usage = {number: 0 for number in range(1, 26)}
    attempts = 0
    max_attempts = max(3000, quantity * 500)

    while len(games) < quantity and attempts < max_attempts:
        attempts += 1

        if strategy == "Quentes — mais sorteadas":
            candidates = overall_rank[:candidate_size]
            game = weighted_pick(rng, candidates, 15)

        elif strategy == "Frias — menos sorteadas":
            candidates = cold_rank[:candidate_size]
            game = weighted_pick(rng, candidates, 15)

        elif strategy == "Mista — quentes + frias":
            hot = rng.sample(overall_rank[:10], 6)
            cold_pool = [n for n in cold_rank[:10] if n not in hot]
            if len(cold_pool) < 6:
                cold_pool = [n for n in cold_rank if n not in hot]
            cold = rng.sample(cold_pool, 6)
            used = set(hot) | set(cold)
            middle = [n for n in range(1, 26) if n not in used]
            middle_pick = rng.sample(middle, 3)
            game = hot + cold + middle_pick

        elif strategy == "Especial — concursos final 0":
            candidates = final0_rank[:candidate_size]
            game = weighted_pick(rng, candidates, 15)

        elif strategy == "Tendência recente":
            candidates = recent_rank[:candidate_size]
            game = weighted_pick(rng, candidates, 15)

        elif strategy == "Mais atrasadas":
            candidates = overdue_rank[:candidate_size]
            game = weighted_pick(rng, candidates, 15)

        elif strategy == "Equilibrada":
            game = rng.sample(range(1, 26), 15)
            if not is_balanced_game(game):
                continue

        elif strategy == "Aleatória — referência":
            game = rng.sample(range(1, 26), 15)

        elif strategy == "Carteira diversificada":
            candidates = list(range(1, 26))
            weights = [1.0 / (1.0 + usage[n] * 0.7) for n in candidates]
            pool = candidates.copy()
            game = []
            for _ in range(15):
                total_weight = sum(weights)
                point = rng.random() * total_weight
                running = 0.0
                chosen_index = len(pool) - 1
                for index, weight in enumerate(weights):
                    running += weight
                    if point <= running:
                        chosen_index = index
                        break
                game.append(pool.pop(chosen_index))
                weights.pop(chosen_index)

        else:
            game = rng.sample(range(1, 26), 15)

        game = tuple(sorted(game))
        if len(game) != 15 or len(set(game)) != 15 or game in seen:
            continue

        seen.add(game)
        games.append(game)
        for number in game:
            usage[number] += 1

    return games



BACKTEST_STRATEGIES = [
    "Quentes — mais sorteadas",
    "Frias — menos sorteadas",
    "Mista — quentes + frias",
    "Especial — concursos final 0",
    "Tendência recente",
    "Mais atrasadas",
    "Equilibrada",
    "Carteira diversificada",
    "Aleatória — referência",
]

def rankings_for_training(training, recent_window, candidate_size):
    """Calcula todos os rankings usando somente concursos anteriores ao alvo."""
    general_frequency = frequency_table(training)
    general_rank = general_frequency["Número"].tolist()
    cold_rank_local = general_frequency.sort_values(
        ["Ocorrências", "Número"], ascending=[True, True]
    )["Número"].tolist()

    zero_draws = training[training["concurso"] % 10 == 0]
    if len(zero_draws):
        zero_rank = frequency_table(zero_draws)["Número"].tolist()
    else:
        zero_rank = general_rank[:]

    recent_draws = training.tail(min(recent_window, len(training)))
    recent_rank = frequency_table(recent_draws)["Número"].tolist()

    last_seen_local = {n: 0 for n in range(1, 26)}
    for _, row in training.iloc[::-1].iterrows():
        for number in row["dezenas"]:
            if last_seen_local[number] == 0:
                last_seen_local[number] = int(row["concurso"])
        if all(last_seen_local.values()):
            break

    last_training_contest = int(training["concurso"].max())
    overdue_rank_local = sorted(
        range(1, 26),
        key=lambda n: (last_training_contest - last_seen_local[n], -n),
        reverse=True,
    )

    zero_frequency = frequency_table(zero_draws) if len(zero_draws) else None
    if zero_frequency is not None:
        zero_scores = {
            n: float(zero_frequency.loc[zero_frequency["Número"] == n, "Frequência (%)"].iloc[0])
            for n in range(1, 26)
        }
    else:
        zero_scores = {n: 0.0 for n in range(1, 26)}

    general_scores = {
        n: float(general_frequency.loc[general_frequency["Número"] == n, "Frequência (%)"].iloc[0])
        for n in range(1, 26)
    }
    combined_rank_local = sorted(
        range(1, 26),
        key=lambda n: (-(general_scores[n] + zero_scores[n]) / 2, n),
    )

    return {
        "overall_rank": general_rank,
        "cold_rank": cold_rank_local,
        "final0_rank": zero_rank,
        "recent_rank": recent_rank,
        "overdue_rank": overdue_rank_local,
        "combined_rank": combined_rank_local,
        "candidate_size": candidate_size,
    }

def run_strategy_backtest(history, test_window, bets_per_draw, candidate_size, recent_window, progress=None):
    """Walk-forward backtest: each target contest is scored using only earlier contests."""
    start_position = max(1, len(history) - test_window)
    target_positions = list(range(start_position, len(history)))
    total_steps = max(1, len(target_positions) * len(BACKTEST_STRATEGIES))
    step = 0
    records = []

    for position in target_positions:
        training = history.iloc[:position].copy()
        target = history.iloc[position]
        actual_numbers = set(target["dezenas"])
        rankings = rankings_for_training(training, recent_window, candidate_size)

        for strategy_index, strategy_name in enumerate(BACKTEST_STRATEGIES):
            step += 1
            generated = build_games(
                strategy=strategy_name,
                quantity=bets_per_draw,
                candidate_size=candidate_size,
                overall_rank=rankings["overall_rank"],
                cold_rank=rankings["cold_rank"],
                final0_rank=rankings["final0_rank"],
                recent_rank=rankings["recent_rank"],
                overdue_rank=rankings["overdue_rank"],
                seed=(int(target["concurso"]) * 1000 + strategy_index * 97 + recent_window),
            )

            for ticket_index, game in enumerate(generated, start=1):
                hits = len(set(game) & actual_numbers)
                records.append({
                    "Estratégia": strategy_name,
                    "Concurso testado": int(target["concurso"]),
                    "Data": target["data"].strftime("%d/%m/%Y") if pd.notna(target["data"]) else "",
                    "Aposta": ticket_index,
                    "Dezenas apostadas": " ".join(f"{n:02d}" for n in game),
                    "Acertos": hits,
                    "Dezenas acertadas": " ".join(f"{n:02d}" for n in sorted(set(game) & actual_numbers)),
                })

            if progress is not None and (step % 10 == 0 or step == total_steps):
                progress.progress(step / total_steps, text=f"Simulando estratégia {strategy_index + 1}/9 · concurso {int(target['concurso'])}")

    return pd.DataFrame(records), len(target_positions)

def summarize_backtest(backtest_df):
    rows = []
    for strategy_name in BACKTEST_STRATEGIES:
        subset = backtest_df[backtest_df["Estratégia"] == strategy_name]
        total = len(subset)
        if total == 0:
            continue
        hit_counts = {
            hits: int((subset["Acertos"] == hits).sum())
            for hits in range(11, 16)
        }
        rows.append({
            "Estratégia": strategy_name,
            "Apostas": total,
            "Até 10 acertos": int((subset["Acertos"] <= 10).sum()),
            "11 acertos": hit_counts[11],
            "12 acertos": hit_counts[12],
            "13 acertos": hit_counts[13],
            "14 acertos": hit_counts[14],
            "15 acertos": hit_counts[15],
            "Apostas com 11+": int((subset["Acertos"] >= 11).sum()),
            "Taxa 11+ (%)": round((subset["Acertos"] >= 11).mean() * 100, 2),
            "Taxa 12+ (%)": round((subset["Acertos"] >= 12).mean() * 100, 2),
            "Média de acertos": round(float(subset["Acertos"].mean()), 3),
            "Máximo de acertos": int(subset["Acertos"].max()),
        })
    return pd.DataFrame(rows).sort_values(
        ["Taxa 11+ (%)", "Média de acertos"],
        ascending=[False, False],
    ).reset_index(drop=True)

st.title("🍀 Painel Estatístico da Lotofácil")
st.caption("Histórico de resultados, análise especial dos concursos de final 0 e gerador de combinações.")
st.info("O painel utiliza o histórico de resultados das Loterias CAIXA, com cópia versionada no GitHub e fontes de contingência. Frequências históricas descrevem sorteios passados e não aumentam a chance de uma dezena no próximo concurso.")

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

cold_freq = overall_freq.sort_values(["Ocorrências", "Número"], ascending=[True, True]).reset_index(drop=True)
cold_rank = cold_freq["Número"].tolist()

last_seen = {n: 0 for n in range(1, 26)}
for _, history_row in history.iterrows():
    for n in history_row["dezenas"]:
        last_seen[n] = int(history_row["concurso"])
latest_contest = int(history["concurso"].max())
overdue_rank = sorted(
    range(1, 26),
    key=lambda n: (latest_contest - last_seen[n], -n),
    reverse=True,
)


c1, c2, c3, c4 = st.columns(4)
c1.metric("Concursos carregados", f"{len(history):,}".replace(",", "."))
c2.metric("Último concurso", f"#{int(last_row['concurso'])}")
c3.metric("Concursos final 0", f"{len(final0):,}".replace(",", "."))
c4.metric("Data do último resultado", last_row["data"].strftime("%d/%m/%Y") if pd.notna(last_row["data"]) else "—")

st.caption(f"Fonte dos dados: {data_source} · Último concurso disponível: {int(last_row['concurso'])}")
st.subheader(f"Último resultado · Concurso {int(last_row['concurso'])}")
st.markdown("".join([f'<span class="ball">{n:02d}</span>' for n in last_row["dezenas"]]), unsafe_allow_html=True)
st.caption(f"Data: {last_row['data'].strftime('%d/%m/%Y') if pd.notna(last_row['data']) else 'não informada'} · Fonte: Loterias CAIXA")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Visão geral",
    "🔟 Concursos final 0",
    "📈 Frequência e atrasos",
    "🎲 Gerador de jogos",
    "🧪 Comparador de estratégias",
    "📚 Histórico",
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
    st.write(
        f"Foram identificados {len(final0)} concursos: 10, 20, 30, 40... "
        f"até {int(final0['concurso'].max()) if len(final0) else 0}."
    )

    if len(final0):
        total_final0 = len(final0)
        expected_pct = 60.0  # Em cada sorteio, 15 das 25 dezenas são selecionadas.
        above = int((final0_freq["Frequência (%)"] > expected_pct).sum())
        below = int((final0_freq["Frequência (%)"] < expected_pct).sum())
        equal = int((final0_freq["Frequência (%)"] == expected_pct).sum())

        metric1, metric2, metric3, metric4 = st.columns(4)
        metric1.metric("Concursos analisados", f"{total_final0:,}".replace(",", "."))
        metric2.metric("Dezenas acima de 60%", str(above))
        metric3.metric("Dezenas abaixo de 60%", str(below))
        metric4.metric("Referência teórica", "60,00%")

        st.divider()
        st.markdown("### 🏆 Top 15 dezenas dos concursos final 0")
        top15 = final0_freq.head(15).copy().reset_index(drop=True)
        top15.insert(0, "Posição", range(1, len(top15) + 1))
        top15 = top15.rename(columns={
            "Dezena": "Dezena",
            "Ocorrências": "Aparições",
        })
        st.dataframe(
            top15[["Posição", "Dezena", "Aparições", "Frequência (%)"]],
            hide_index=True,
            use_container_width=True,
        )

        st.markdown("### 🤝 Pares que mais saem juntos")
        st.caption(
            "A tabela apresenta as duplas mais recorrentes. O mapa de calor permite "
            "comparar qualquer combinação entre as 25 dezenas."
        )
        pair_col, heat_col = st.columns([0.85, 1.5])
        with pair_col:
            st.markdown("**20 pares mais recorrentes**")
            st.dataframe(
                pair_table(final0, 20),
                hide_index=True,
                use_container_width=True,
            )
        with heat_col:
            st.markdown("**Mapa de calor — coocorrência das dezenas**")
            heatmap = px.imshow(
                pair_matrix(final0),
                aspect="auto",
                color_continuous_scale="Viridis",
                labels={
                    "x": "Dezena",
                    "y": "Dezena",
                    "color": "Concursos juntos",
                },
                title="Quantidade de concursos em que cada par apareceu",
            )
            heatmap.update_layout(
                xaxis_title="Dezena",
                yaxis_title="Dezena",
                coloraxis_colorbar_title="Concursos",
            )
            heatmap.update_traces(
                hovertemplate=(
                    "Dezena da coluna: %{x}<br>"
                    "Dezena da linha: %{y}<br>"
                    "Concursos juntos: %{z}<extra></extra>"
                )
            )
            st.plotly_chart(heatmap, use_container_width=True)

        st.divider()
        st.markdown("### 🎯 Frequência observada versus expectativa teórica de 60%")
        st.caption(
            "Como são sorteadas 15 dezenas entre 25, cada dezena tem probabilidade "
            "teórica de 15/25 = 60% em qualquer concurso. A diferença abaixo é "
            "expressa em pontos percentuais (p.p.), não em aumento de probabilidade futura."
        )

        comparison = final0_freq[[
            "Dezena", "Número", "Ocorrências", "Frequência (%)"
        ]].copy()
        comparison["Esperado (%)"] = expected_pct
        comparison["Diferença (p.p.)"] = (
            comparison["Frequência (%)"] - expected_pct
        ).round(2)
        comparison["Situação"] = comparison["Diferença (p.p.)"].apply(
            lambda value: (
                "Acima de 60%" if value > 0 else
                "Abaixo de 60%" if value < 0 else
                "Igual a 60%"
            )
        )

        deviation_fig = px.bar(
            comparison.sort_values("Número"),
            x="Dezena",
            y="Frequência (%)",
            color="Situação",
            hover_data=["Ocorrências", "Esperado (%)", "Diferença (p.p.)"],
            color_discrete_map={
                "Acima de 60%": "#16A36A",
                "Abaixo de 60%": "#E09B35",
                "Igual a 60%": "#8A8A8A",
            },
            title="Frequência observada de cada dezena nos concursos final 0",
        )
        deviation_fig.add_hline(
            y=expected_pct,
            line_dash="dash",
            line_color="#E05252",
            annotation_text="Referência teórica: 60%",
            annotation_position="top left",
        )
        deviation_fig.update_layout(
            xaxis_title="Dezena",
            yaxis_title="Frequência nos concursos final 0 (%)",
            legend_title="Comparação com 60%",
        )
        st.plotly_chart(deviation_fig, use_container_width=True)

        st.markdown("**Tabela completa — diferença em relação aos 60%**")
        st.dataframe(
            comparison[[
                "Dezena", "Ocorrências", "Frequência (%)",
                "Esperado (%)", "Diferença (p.p.)", "Situação"
            ]].sort_values("Frequência (%)", ascending=False),
            hide_index=True,
            use_container_width=True,
        )

        st.divider()
        st.markdown("### Comparação entre o histórico geral e os concursos final 0")
        compare = overall_freq[["Dezena", "Frequência (%)"]].merge(
            final0_freq[["Dezena", "Frequência (%)"]],
            on="Dezena",
            suffixes=(" geral", " final 0"),
        )
        compare = compare.rename(columns={
            "Frequência (%) geral": "Histórico geral (%)",
            "Frequência (%) final 0": "Concursos final 0 (%)",
        })
        compare_long = compare.melt(
            id_vars="Dezena",
            var_name="Recorte",
            value_name="Frequência (%)",
        )
        st.plotly_chart(
            px.bar(
                compare_long,
                x="Dezena",
                y="Frequência (%)",
                color="Recorte",
                barmode="group",
                title="Frequência por dezena: todos os concursos versus final 0",
            ),
            use_container_width=True,
        )
    else:
        st.warning("Ainda não há concursos final 0 na base.")

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
    st.subheader("Gerador inteligente de combinações")
    st.caption(
        "Escolha um perfil estatístico, incluindo uma referência totalmente aleatória. Cada estratégia organiza os números de maneira diferente, "
        "mas não altera a probabilidade matemática de uma combinação."
    )

    strategy_options = [
        "Quentes — mais sorteadas",
        "Frias — menos sorteadas",
        "Mista — quentes + frias",
        "Especial — concursos final 0",
        "Tendência recente",
        "Mais atrasadas",
        "Equilibrada",
        "Carteira diversificada",
        "Aleatória — referência",
    ]

    gen_col1, gen_col2, gen_col3 = st.columns(3)
    with gen_col1:
        strategy = st.selectbox("Perfil de geração", strategy_options)
    with gen_col2:
        qty = st.selectbox("Quantidade de jogos", [5, 10, 15, 20, 30], index=2)
    with gen_col3:
        candidate_size = st.slider(
            "Tamanho do grupo candidato",
            min_value=18,
            max_value=25,
            value=20,
            help="Nas estratégias baseadas em ranking, o gerador seleciona 15 dezenas dentro deste grupo, favorecendo as primeiras posições.",
        )

    recent_window = st.selectbox(
        "Janela para tendência recente",
        [50, 100, 200],
        index=1,
        help="Usada quando o perfil Tendência recente está selecionado.",
    )

    strategy_descriptions = {
        "Quentes — mais sorteadas": "Dá maior peso às dezenas que mais apareceram em todo o histórico.",
        "Frias — menos sorteadas": "Dá maior peso às dezenas com menor frequência histórica. 'Frias' descreve o passado, não uma menor chance no próximo sorteio.",
        "Mista — quentes + frias": "Combina 6 dezenas do grupo mais frequente, 6 do menos frequente e 3 do grupo intermediário.",
        "Especial — concursos final 0": "Usa o ranking calculado somente com concursos 10, 20, 30, 40 e assim por diante.",
        "Tendência recente": f"Prioriza as dezenas mais frequentes nos últimos {recent_window} concursos.",
        "Mais atrasadas": "Prioriza as dezenas há mais concursos sem aparecer.",
        "Equilibrada": "Filtra combinações com distribuição de pares/ímpares, metade inferior/superior, faixas numéricas e soma dentro de intervalos amplos.",
        "Carteira diversificada": "Ao gerar vários jogos, reduz gradualmente o peso das dezenas já usadas para espalhar melhor a cobertura entre as apostas.",
        "Aleatória — referência": "Gera combinações sem usar ranking histórico. Serve como grupo de comparação para as outras estratégias.",
    }
    st.info(strategy_descriptions[strategy])

    if st.button("🎯 Gerar jogos", type="primary"):
        recent_rank = frequency_table(history.tail(min(recent_window, len(history))))["Número"].tolist()
        generated_games = build_games(
            strategy=strategy,
            quantity=qty,
            candidate_size=candidate_size,
            overall_rank=overall_rank,
            cold_rank=cold_rank,
            final0_rank=final0_rank,
            recent_rank=recent_rank,
            overdue_rank=overdue_rank,
            seed=datetime.now().microsecond,
        )
        st.session_state["games"] = generated_games
        st.session_state["games_strategy"] = strategy
        st.session_state["games_recent_window"] = recent_window
        st.session_state["games_candidate_size"] = candidate_size

    if "games" in st.session_state:
        current_games = st.session_state["games"]
        st.write(
            f"**{len(current_games)} jogos gerados · "
            f"Perfil: {st.session_state.get('games_strategy', '')}**"
        )

        used_numbers = sorted({n for game in current_games for n in game})
        avg_odd = sum(sum(n % 2 for n in game) for game in current_games) / len(current_games)
        avg_sum = sum(sum(game) for game in current_games) / len(current_games)
        summary1, summary2, summary3 = st.columns(3)
        summary1.metric("Dezenas diferentes utilizadas", f"{len(used_numbers)} de 25")
        summary2.metric("Média de ímpares por jogo", f"{avg_odd:.1f}".replace(".", ","))
        summary3.metric("Soma média das dezenas", f"{avg_sum:.1f}".replace(".", ","))

        for idx, game in enumerate(current_games, 1):
            balls = "".join([f'<span class="ball">{n:02d}</span>' for n in game])
            odd_count = sum(n % 2 for n in game)
            even_count = 15 - odd_count
            low_count = sum(n <= 13 for n in game)
            high_count = 15 - low_count
            number_sum = sum(game)
            st.markdown(f"**Jogo {idx:02d}**<br>{balls}", unsafe_allow_html=True)
            st.caption(
                f"Pares: {even_count} · Ímpares: {odd_count} · "
                f"01–13: {low_count} · 14–25: {high_count} · Soma: {number_sum}"
            )

        games_df = pd.DataFrame([
            {
                "Jogo": i + 1,
                **{f"D{j + 1:02d}": f"{n:02d}" for j, n in enumerate(game)},
                "Pares": 15 - sum(n % 2 for n in game),
                "Ímpares": sum(n % 2 for n in game),
                "Soma": sum(game),
            }
            for i, game in enumerate(current_games)
        ])

        csv_data = games_df.to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button(
            "⬇️ Baixar jogos em CSV",
            csv_data,
            "jogos_lotofacil.csv",
            "text/csv",
        )

        excel_buffer = io.BytesIO()
        recent_export = frequency_table(
            history.tail(min(st.session_state.get("games_recent_window", 100), len(history)))
        )
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            games_df.to_excel(writer, sheet_name="Jogos", index=False)
            overall_freq.to_excel(writer, sheet_name="Ranking geral", index=False)
            cold_freq.to_excel(writer, sheet_name="Ranking frias", index=False)
            final0_freq.to_excel(writer, sheet_name="Ranking final 0", index=False)
            recent_export.to_excel(writer, sheet_name="Tendência recente", index=False)
        st.download_button(
            "📊 Baixar relatório Excel",
            excel_buffer.getvalue(),
            "relatorio_lotofacil.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


with tab5:
    st.subheader("🧪 Comparador de estratégias — backtest histórico")
    st.caption(
        "O teste percorre concursos passados em sequência. Para cada concurso avaliado, "
        "os rankings são recalculados usando somente resultados anteriores àquele sorteio."
    )
    st.info(
        "Este é um teste retrospectivo, não uma previsão. O desempenho passado pode variar "
        "por acaso e não altera as probabilidades matemáticas dos próximos concursos."
    )

    bt_col1, bt_col2, bt_col3 = st.columns(3)
    with bt_col1:
        bt_window = st.selectbox("Concursos a testar", [100, 200], index=0, key="bt_window")
    with bt_col2:
        bt_bets = st.selectbox("Apostas por estratégia em cada concurso", [1, 3, 5], index=0, key="bt_bets")
    with bt_col3:
        bt_candidate_size = st.slider(
            "Grupo candidato das estratégias por ranking",
            min_value=18,
            max_value=25,
            value=20,
            key="bt_candidate_size",
        )

    bt_recent_window = st.selectbox(
        "Janela da estratégia de tendência recente",
        [50, 100, 200],
        index=1,
        key="bt_recent_window",
    )

    st.caption(
        f"Serão comparadas {len(BACKTEST_STRATEGIES)} estratégias, incluindo uma referência aleatória. "
        f"Com a configuração atual, serão geradas aproximadamente "
        f"{bt_window * bt_bets * len(BACKTEST_STRATEGIES):,} apostas simuladas."
    )

    if st.button("▶️ Executar backtest", type="primary", key="run_backtest"):
        progress_bar = st.progress(0, text="Preparando simulação...")
        with st.spinner("Executando a simulação histórica sem vazamento de informação..."):
            bt_results, bt_draws_tested = run_strategy_backtest(
                history=history,
                test_window=bt_window,
                bets_per_draw=bt_bets,
                candidate_size=bt_candidate_size,
                recent_window=bt_recent_window,
                progress=progress_bar,
            )
        progress_bar.empty()
        st.session_state["backtest_results"] = bt_results
        st.session_state["backtest_draws_tested"] = bt_draws_tested
        st.session_state["backtest_config"] = {
            "window": bt_window,
            "bets": bt_bets,
            "candidate_size": bt_candidate_size,
            "recent_window": bt_recent_window,
        }

    if "backtest_results" in st.session_state:
        results = st.session_state["backtest_results"]
        config = st.session_state.get("backtest_config", {})
        summary = summarize_backtest(results)

        if results.empty:
            st.warning("Nenhuma aposta foi gerada. Tente executar novamente.")
        else:
            contest_count = int(st.session_state.get("backtest_draws_tested", 0))
            total_bets = len(results)
            first_contest = int(results["Concurso testado"].min())
            last_contest = int(results["Concurso testado"].max())
            best_strategy = summary.iloc[0]["Estratégia"]
            top_rate = float(summary.iloc[0]["Taxa 11+ (%)"])

            metric1, metric2, metric3, metric4 = st.columns(4)
            metric1.metric("Concursos avaliados", f"{contest_count:,}".replace(",", "."))
            metric2.metric("Apostas simuladas", f"{total_bets:,}".replace(",", "."))
            metric3.metric("Faixa testada", f"{first_contest}–{last_contest}")
            metric4.metric("Maior taxa 11+", f"{top_rate:.2f}%".replace(".", ","))

            st.markdown(
                f"**Melhor resultado observado nesta simulação:** {best_strategy}. "
                "A liderança é descritiva e pode mudar com outra janela, quantidade de apostas ou nova simulação."
            )

            st.caption(
                f"Configuração utilizada: {config.get('window', '—')} concursos · "
                f"{config.get('bets', '—')} apostas por estratégia/concurso · "
                f"grupo candidato de {config.get('candidate_size', '—')} dezenas · "
                f"tendência recente de {config.get('recent_window', '—')} concursos."
            )

            st.markdown("### Resultado por estratégia")
            st.caption(
                "As colunas de 11, 12, 13, 14 e 15 mostram a quantidade de apostas com aquele número "
                "exato de acertos. 'Apostas com 11+' é uma soma cumulativa."
            )
            st.dataframe(summary, hide_index=True, use_container_width=True)

            distribution = []
            for strategy_name in BACKTEST_STRATEGIES:
                subset = results[results["Estratégia"] == strategy_name]
                total = len(subset)
                if not total:
                    continue
                distribution.append({
                    "Estratégia": strategy_name,
                    "Faixa de acertos": "0 a 10",
                    "Apostas": int((subset["Acertos"] <= 10).sum()),
                })
                for hits in range(11, 16):
                    distribution.append({
                        "Estratégia": strategy_name,
                        "Faixa de acertos": str(hits),
                        "Apostas": int((subset["Acertos"] == hits).sum()),
                    })

            st.markdown("### Distribuição de acertos")
            dist_fig = px.bar(
                pd.DataFrame(distribution),
                x="Estratégia",
                y="Apostas",
                color="Faixa de acertos",
                barmode="stack",
                category_orders={"Faixa de acertos": ["0 a 10", "11", "12", "13", "14", "15"]},
                title="Quantidade de apostas por faixa de acertos",
            )
            dist_fig.update_layout(xaxis_title="Estratégia", yaxis_title="Quantidade de apostas")
            st.plotly_chart(dist_fig, use_container_width=True)

            st.markdown("### Taxa de apostas com 11 ou mais acertos")
            rate_fig = px.bar(
                summary.sort_values("Taxa 11+ (%)", ascending=False),
                x="Estratégia",
                y="Taxa 11+ (%)",
                hover_data=["Apostas", "Apostas com 11+", "Média de acertos", "Máximo de acertos"],
                title="Comparação da taxa observada de 11+ acertos",
            )
            st.plotly_chart(rate_fig, use_container_width=True)

            st.markdown("### Detalhamento das apostas simuladas")
            filter_strategy = st.selectbox(
                "Filtrar estratégia",
                ["Todas"] + BACKTEST_STRATEGIES,
                key="bt_filter_strategy",
            )
            filtered = results if filter_strategy == "Todas" else results[results["Estratégia"] == filter_strategy]
            st.dataframe(
                filtered.sort_values(["Concurso testado", "Estratégia", "Aposta"]),
                hide_index=True,
                use_container_width=True,
            )

            csv_bt = results.to_csv(index=False, sep=";", encoding="utf-8-sig")
            st.download_button(
                "⬇️ Baixar resultados do backtest (CSV)",
                csv_bt,
                "backtest_lotofacil.csv",
                "text/csv",
            )
            excel_bt = io.BytesIO()
            with pd.ExcelWriter(excel_bt, engine="openpyxl") as writer:
                summary.to_excel(writer, sheet_name="Resumo", index=False)
                results.to_excel(writer, sheet_name="Apostas simuladas", index=False)
            st.download_button(
                "📊 Baixar relatório do backtest (Excel)",
                excel_bt.getvalue(),
                "backtest_lotofacil.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


with tab6:
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
