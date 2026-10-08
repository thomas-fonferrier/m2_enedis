"""Climat départemental via Open-Meteo Historical Weather API.

Calcule pour chaque département français :
- ``dju`` : degrés-jours unifiés annuels moyens (base 18 °C, méthode chauffagiste)
- ``t_moy_hiver`` : température moyenne déc–fév (°C)
- ``t_moy_ete`` : température moyenne juin–août (°C)

API : https://open-meteo.com/en/docs/historical-weather-api
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent / "raw"
METEO_CSV = DATA_DIR / "meteo_departements.csv"

URL_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
DJU_BASE = 18.0
# Normale climatique récente (5 ans — compromis précision / quota API)
START_DATE = "2019-01-01"
END_DATE = "2023-12-31"
BATCH_SIZE = 1  # 1 lieu / requête (évite le 429 Open-Meteo free)
REQUEST_PAUSE_S = 3.0
MAX_RETRIES = 8

# Chef-lieu (lat, lon) — métropole + Corse + DOM
DEPARTEMENTS: dict[str, tuple[float, float]] = {
    "01": (46.2052, 5.2258),
    "02": (49.5656, 3.6204),
    "03": (46.3402, 2.6064),
    "04": (44.0925, 6.2316),
    "05": (44.5588, 6.0773),
    "06": (43.7102, 7.2620),
    "07": (44.5580, 4.5980),
    "08": (49.7719, 4.7202),
    "09": (42.9630, 1.6050),
    "10": (48.2973, 4.0744),
    "11": (43.2128, 2.3537),
    "12": (44.3494, 2.5750),
    "13": (43.2965, 5.3698),
    "14": (49.1829, -0.3707),
    "15": (44.9297, 2.4440),
    "16": (45.6500, 0.1600),
    "17": (46.1591, -1.1522),
    "18": (47.0810, 2.3988),
    "19": (45.2670, 1.7710),
    "2A": (41.9264, 8.7364),
    "2B": (42.7028, 9.4475),
    "21": (47.3220, 5.0415),
    "22": (48.5140, -2.7600),
    "23": (46.1700, 1.8700),
    "24": (45.1840, 0.7180),
    "25": (47.2378, 6.0241),
    "26": (44.9333, 4.8917),
    "27": (49.0270, 1.1510),
    "28": (48.4439, 1.4892),
    "29": (48.3904, -4.4861),
    "30": (43.8367, 4.3601),
    "31": (43.6047, 1.4442),
    "32": (43.6450, 0.5860),
    "33": (44.8378, -0.5792),
    "34": (43.6108, 3.8767),
    "35": (48.1173, -1.6778),
    "36": (46.8090, 1.6910),
    "37": (47.3941, 0.6848),
    "38": (45.1885, 5.7245),
    "39": (46.6750, 5.5540),
    "40": (43.8900, -0.5000),
    "41": (47.5860, 1.3360),
    "42": (45.4397, 4.3872),
    "43": (45.0430, 3.8850),
    "44": (47.2184, -1.5536),
    "45": (47.9029, 1.9093),
    "46": (44.4470, 1.4410),
    "47": (44.2030, 0.6210),
    "48": (44.5180, 3.5000),
    "49": (47.4712, -0.5518),
    "50": (49.1140, -1.0920),
    "51": (49.2583, 4.0317),
    "52": (48.1120, 5.1390),
    "53": (48.0720, -0.7700),
    "54": (48.6921, 6.1844),
    "55": (49.1580, 5.3830),
    "56": (47.7480, -2.7350),
    "57": (49.1193, 6.1757),
    "58": (46.9900, 3.1620),
    "59": (50.6292, 3.0573),
    "60": (49.4170, 2.8260),
    "61": (48.4300, 0.0930),
    "62": (50.4280, 2.8320),
    "63": (45.7772, 3.0870),
    "64": (43.2951, -0.3708),
    "65": (43.2330, 0.0780),
    "66": (42.6987, 2.8956),
    "67": (48.5734, 7.7521),
    "68": (48.0790, 7.3580),
    "69": (45.7640, 4.8357),
    "70": (47.6230, 6.1550),
    "71": (46.3070, 4.8300),
    "72": (48.0061, 0.1996),
    "73": (45.5660, 5.9210),
    "74": (45.8992, 6.1294),
    "75": (48.8566, 2.3522),
    "76": (49.4431, 1.0993),
    "77": (48.5400, 2.6600),
    "78": (48.8014, 2.1301),
    "79": (46.3240, -0.4640),
    "80": (49.8940, 2.2960),
    "81": (43.9298, 2.1480),
    "82": (44.0170, 1.3550),
    "83": (43.1242, 5.9280),
    "84": (43.9493, 4.8055),
    "85": (46.6700, -1.4260),
    "86": (46.5802, 0.3404),
    "87": (45.8336, 1.2611),
    "88": (48.1740, 6.4510),
    "89": (47.7980, 3.5670),
    "90": (47.6390, 6.8630),
    "91": (48.6280, 2.4400),
    "92": (48.8920, 2.2070),
    "93": (48.9100, 2.4400),
    "94": (48.7900, 2.4600),
    "95": (49.0360, 2.0760),
    "971": (16.2410, -61.5330),
    "972": (14.6160, -61.0590),
    "973": (4.9220, -52.3130),
    "974": (-20.8789, 55.4481),
    "976": (-12.7806, 45.2278),
}


def _aggregate_climate(daily: pd.DataFrame) -> dict[str, float]:
    """DJU annuel moyen + T° moyennes hiver / été à partir de températures quotidiennes."""
    daily = daily.copy()
    daily["time"] = pd.to_datetime(daily["time"])
    daily["t"] = pd.to_numeric(daily["temperature_2m_mean"], errors="coerce")
    daily = daily.dropna(subset=["t"])

    daily["dju_day"] = (DJU_BASE - daily["t"]).clip(lower=0)
    n_years = max(1, daily["time"].dt.year.nunique())
    dju = float(daily["dju_day"].sum() / n_years)

    month = daily["time"].dt.month
    winter = daily.loc[month.isin([12, 1, 2]), "t"]
    summer = daily.loc[month.isin([6, 7, 8]), "t"]

    return {
        "dju": round(dju, 1),
        "t_moy_hiver": round(float(winter.mean()), 2) if len(winter) else float("nan"),
        "t_moy_ete": round(float(summer.mean()), 2) if len(summer) else float("nan"),
    }


def _get_with_retry(params: dict) -> dict:
    """GET Open-Meteo avec backoff sur 429."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        response = requests.get(URL_ARCHIVE, params=params, timeout=120)
        if response.status_code == 429:
            wait = REQUEST_PAUSE_S * (2**attempt)
            print(f"    rate-limit 429 → pause {wait:.1f}s")
            time.sleep(wait)
            last_error = requests.HTTPError("429 Too Many Requests", response=response)
            continue
        response.raise_for_status()
        return response.json()
    assert last_error is not None
    raise last_error


def _fetch_batch(
    codes: list[str],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> list[dict]:
    """Appelle Open-Meteo pour un lot de départements."""
    lats = [DEPARTEMENTS[c][0] for c in codes]
    lons = [DEPARTEMENTS[c][1] for c in codes]
    params = {
        "latitude": ",".join(str(x) for x in lats),
        "longitude": ",".join(str(x) for x in lons),
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_mean",
        "timezone": "Europe/Paris",
    }
    payload = _get_with_retry(params)

    # Une seule localisation → objet ; plusieurs → liste
    items = payload if isinstance(payload, list) else [payload]
    rows: list[dict] = []
    for code, item in zip(codes, items):
        daily = pd.DataFrame(item["daily"])
        metrics = _aggregate_climate(daily)
        lat, lon = DEPARTEMENTS[code]
        rows.append(
            {
                "code_departement": code,
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                **metrics,
            }
        )
    return rows


def fetch_meteo_departements(
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    out_path: Path | str = METEO_CSV,
    resume: bool = True,
) -> pd.DataFrame:
    """Récupère le climat pour tous les départements et sauvegarde en CSV.

    Si ``resume`` et qu'un CSV partiel existe, reprend uniquement les départements manquants.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done: dict[str, dict] = {}
    if resume and out_path.exists():
        prev = pd.read_csv(out_path, dtype={"code_departement": str})
        done = {str(r["code_departement"]): r.to_dict() for _, r in prev.iterrows()}
        print(f"Reprise : {len(done)} départements déjà présents dans {out_path.name}")

    codes = [c for c in DEPARTEMENTS if c not in done]
    print(
        f"Open-Meteo Historical : {len(codes)} à télécharger "
        f"({start_date} → {end_date})…"
    )

    rows = list(done.values())
    for i, code in enumerate(codes):
        if i % 10 == 0:
            print(f"  {i + 1}/{len(codes)} : dép. {code}")
        batch_rows = _fetch_batch([code], start_date=start_date, end_date=end_date)
        rows.extend(batch_rows)
        # Checkpoint après chaque succès
        pd.DataFrame(rows).to_csv(out_path, index=False)
        time.sleep(REQUEST_PAUSE_S)

    df = pd.DataFrame(rows).drop_duplicates(subset=["code_departement"], keep="last")
    df = df.sort_values("code_departement").reset_index(drop=True)
    df.to_csv(out_path, index=False)
    print(f"CSV météo sauvegardé : {out_path} ({len(df)} départements)")
    return df


def load_meteo_departements(path: Path | str = METEO_CSV) -> pd.DataFrame:
    """Charge le CSV climat ; le génère s'il est absent."""
    path = Path(path)
    if not path.exists():
        print(f"{path.name} introuvable → fetch Open-Meteo…")
        return fetch_meteo_departements(out_path=path)
    return pd.read_csv(path, dtype={"code_departement": str})


def enrich_dpe_with_meteo(
    df: pd.DataFrame,
    meteo_path: Path | str = METEO_CSV,
) -> pd.DataFrame:
    """Joint ``dju``, ``t_moy_hiver``, ``t_moy_ete`` sur ``code_departement_ban``."""
    if "code_departement_ban" not in df.columns:
        print("Attention : colonne code_departement_ban absente → pas de jointure météo")
        return df

    meteo = load_meteo_departements(meteo_path)
    keep = ["code_departement", "dju", "t_moy_hiver", "t_moy_ete"]
    meteo = meteo[keep].drop_duplicates(subset=["code_departement"])

    out = df.copy()
    out["code_departement_ban"] = out["code_departement_ban"].astype(str).str.strip()
    # Homogénéise "6" → "06" (sauf Corse / DOM déjà corrects)
    mask_digit = out["code_departement_ban"].str.fullmatch(r"\d{1,2}")
    out.loc[mask_digit, "code_departement_ban"] = out.loc[mask_digit, "code_departement_ban"].str.zfill(2)

    before_cols = set(out.columns)
    out = out.merge(
        meteo,
        how="left",
        left_on="code_departement_ban",
        right_on="code_departement",
    )
    if "code_departement" in out.columns and "code_departement" not in before_cols:
        out = out.drop(columns=["code_departement"])

    matched = int(out["dju"].notna().sum())
    print(f"Jointure météo : {matched}/{len(out)} lignes renseignées")
    return out


if __name__ == "__main__":
    fetch_meteo_departements()
