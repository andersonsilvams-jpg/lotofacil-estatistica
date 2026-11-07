import io
import re
import unicodedata

import pandas as pd
import requests

CAIXA_DOWNLOAD_URL = (
    "https://servicebus2.caixa.gov.br/portaldeloterias/api/resultados/download"
    "?modalidade=Lotof%C3%A1cil"
)
VALORFINAL_CSV_URL = "https://valorfinal.com.br/dados/loterias/lotofacil.csv"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Origin": "https://loterias.caixa.gov.br",
    "Referer": "https://loterias.caixa.gov.br/",
}

def _norm(value):
    value = str(value).strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

def _finalizar_historico(result):
    result = result.drop_duplicates("concurso").sort_values("concurso").reset_index(drop=True)
    result["dezenas_txt"] = result["dezenas"].apply(
        lambda nums: " ".join(f"{n:02d}" for n in nums)
    )
    return result[["concurso", "data", "dezenas", "dezenas_txt"]]

def normalizar_planilha_caixa(raw):
    if raw is None or raw.empty:
        raise ValueError("A planilha histórica da CAIXA veio vazia.")

    columns = list(raw.columns)
    norm = {col: _norm(col) for col in columns}
    concurso_col = next((c for c in columns if norm[c] == "concurso"), None)
    if concurso_col is None:
        concurso_col = next((c for c in columns if "concurso" in norm[c]), None)
    data_col = next((c for c in columns if norm[c] in {"data sorteio", "data"}), None)
    if data_col is None:
        data_col = next((c for c in columns if "data" in norm[c]), None)

    ball_map = {}
    for col in columns:
        match = re.search(r"(?:bola|dezena)\s*0*(\d+)", norm[col])
        if match:
            index = int(match.group(1))
            if 1 <= index <= 15:
                ball_map[index] = col

    if concurso_col is None or data_col is None or len(ball_map) != 15:
        raise ValueError(
            "Formato da planilha da CAIXA não reconhecido. "
            f"Colunas: {', '.join(map(str, columns))}"
        )

    dates = raw[data_col]
    if pd.api.types.is_numeric_dtype(dates):
        parsed_dates = pd.to_datetime(dates, unit="D", origin="1899-12-30", errors="coerce")
    else:
        parsed_dates = pd.to_datetime(dates, dayfirst=True, errors="coerce")

    contests = pd.to_numeric(raw[concurso_col], errors="coerce")
    valid_rows = []
    for row_index in range(len(raw)):
        contest = contests.iloc[row_index]
        nums = [pd.to_numeric(raw[ball_map[i]].iloc[row_index], errors="coerce") for i in range(1, 16)]
        if pd.isna(contest) or any(pd.isna(x) for x in nums):
            continue
        nums = [int(x) for x in nums]
        if len(set(nums)) != 15 or any(x < 1 or x > 25 for x in nums):
            continue
        valid_rows.append({
            "concurso": int(contest),
            "data": parsed_dates.iloc[row_index],
            "dezenas": sorted(nums),
        })

    result = pd.DataFrame(valid_rows)
    if result.empty:
        raise ValueError("Nenhum concurso passou na validação da planilha.")
    return _finalizar_historico(result)

def baixar_historico_caixa():
    response = requests.get(CAIXA_DOWNLOAD_URL, headers=HEADERS, timeout=90)
    response.raise_for_status()
    if len(response.content) < 1000:
        raise ValueError("O arquivo retornado pela CAIXA parece incompleto.")
    raw = pd.read_excel(io.BytesIO(response.content))
    return normalizar_planilha_caixa(raw)

def baixar_historico_publicado():
    response = requests.get(VALORFINAL_CSV_URL, timeout=60)
    response.raise_for_status()
    raw = pd.read_csv(io.StringIO(response.content.decode("utf-8-sig")), sep=";", comment="#")
    cols = {_norm(c): c for c in raw.columns}
    contest_col = cols.get("concurso")
    date_col = cols.get("data")
    numbers_col = cols.get("dezenas")
    if not contest_col or not date_col or not numbers_col:
        raise ValueError(f"Formato CSV inesperado: {list(raw.columns)}")

    rows = []
    for _, row in raw.iterrows():
        try:
            nums = [int(x) for x in str(row[numbers_col]).replace(",", " ").split()]
            if len(nums) != 15 or len(set(nums)) != 15 or any(n < 1 or n > 25 for n in nums):
                continue
            rows.append({
                "concurso": int(row[contest_col]),
                "data": pd.to_datetime(row[date_col], errors="coerce"),
                "dezenas": sorted(nums),
            })
        except (TypeError, ValueError):
            continue
    if not rows:
        raise ValueError("O CSV público não contém concursos válidos.")
    return _finalizar_historico(pd.DataFrame(rows))
