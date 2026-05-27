import os
import math
import base64
import mimetypes
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from PIL import Image, ImageDraw, ImageFont

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(override=False):
        env_path = ".env"
        if not os.path.exists(env_path):
            return False
        with open(env_path, encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if override or key not in os.environ:
                    os.environ[key] = value.strip().strip('"').strip("'")
        return False


load_dotenv(override=True)


def get_odds_api_key():
    try:
        return st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY", ""))
    except (FileNotFoundError, StreamlitSecretNotFoundError):
        return os.getenv("ODDS_API_KEY", "")


ODDS_API_KEY = get_odds_api_key()
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds"
NO_LIVE_ODDS_MESSAGE = (
    "No World Cup betting odds available yet. This usually happens when fixtures "
    "are too far away or markets are not open."
)
USE_BROWSER_EXPORT = False
SUBLAUNCH_URL = "https://sublaunch.com/fplcartel"
LOGO_PATH = Path("assets/fpl-cartel-logo.png")
LOGO_CANDIDATES = [
    "assets/fpl-cartel-logo.png",
    "fpl-cartel-logo.png",
    "fpl_cartel_logo.png",
    "fpl-cartel.png",
    "fplcartel.png",
    "logo.png",
    "cartel-logo.png",
    "FPL Cartel Logo.png",
]

st.set_page_config(
    page_title="FPL Cartel World Cup Odds Dashboard",
    page_icon="WC",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    #MainMenu {
        visibility: hidden;
    }

    header {
        visibility: hidden;
    }

    [data-testid="stToolbar"] {
        display: none !important;
    }

    [data-testid="stDecoration"] {
        display: none !important;
    }

    [data-testid="stStatusWidget"] {
        display: none !important;
    }

    [data-testid="stHeader"] {
        display: none !important;
    }

    [data-testid="stFeedback"] {
        display: none !important;
    }

    [data-testid="stBaseButton-secondary"] {
        display: none !important;
    }

    .st-emotion-cache-1wbqy5l,
    .st-emotion-cache-1dp5vir,
    .st-emotion-cache-1avcm0n {
        display: none !important;
    }

    iframe[title="streamlit_feedback"] {
        display: none !important;
    }

    [data-testid="stDownloadButton"] [data-testid="stBaseButton-secondary"],
    [data-testid="stDownloadButton"] button,
    [data-testid="stSelectbox"] [data-testid="stBaseButton-secondary"],
    [data-testid="stSelectbox"] button,
    [data-testid="stNumberInput"] [data-testid="stBaseButton-secondary"],
    [data-testid="stNumberInput"] button {
        display: inline-flex !important;
    }

    [data-testid="stAppViewContainer"] > div[style*="position: fixed"][style*="right"][style*="bottom"],
    body > div[style*="position: fixed"][style*="right"][style*="bottom"] iframe,
    body > div[style*="position: fixed"][style*="right"][style*="bottom"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }

    .block-container {
        padding-top: 1rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

query_params = st.query_params
view = query_params.get("view", "desktop")


def find_logo_path():
    if LOGO_PATH.exists():
        return LOGO_PATH

    for name in LOGO_CANDIDATES:
        path = Path(name)
        if path.exists():
            return path
    return None


def fallback_logo_svg():
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" width="144" height="144" viewBox="0 0 144 144">
      <rect width="144" height="144" rx="30" fill="#111827"/>
      <circle cx="72" cy="72" r="50" fill="#00e676"/>
      <text x="72" y="66" text-anchor="middle" font-family="Arial, sans-serif" font-size="34" font-weight="900" fill="#111827">FPL</text>
      <text x="72" y="96" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" font-weight="900" fill="#111827">CARTEL</text>
    </svg>
    """
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def get_logo_src():
    logo_path = find_logo_path()
    if not logo_path:
        return fallback_logo_svg()

    mime_type, _encoding = mimetypes.guess_type(str(logo_path))
    if not mime_type:
        mime_type = "image/png"
    data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}"


def render_brand_header():
    logo_src = get_logo_src()
    return f"""
    <div class="brand-header">
      <img src="{logo_src}" class="brand-logo" alt="FPL Cartel logo">
      <div>
        <h1>FPL Cartel World Cup Odds Dashboard</h1>
        <a href="{SUBLAUNCH_URL}" target="_blank" rel="noopener noreferrer">
          Join FPL Cartel on Sublaunch
        </a>
      </div>
    </div>
    """


SAMPLE_FIXTURES = pd.DataFrame(
    [
        {
            "date": "Sat 13 Jun",
            "kickoff": "17:00",
            "fixture_set": "World Cup",
            "home_team": "Argentina",
            "away_team": "Morocco",
            "home_badge": "ARG",
            "away_badge": "MAR",
            "home_xg": 1.84,
            "away_xg": 0.91,
            "home_cs": 41,
            "away_cs": 18,
            "delta": "+3.2%",
            "source": "sample",
        },
        {
            "date": "Sat 13 Jun",
            "kickoff": "20:00",
            "fixture_set": "World Cup",
            "home_team": "England",
            "away_team": "Japan",
            "home_badge": "ENG",
            "away_badge": "JPN",
            "home_xg": 1.61,
            "away_xg": 1.02,
            "home_cs": 34,
            "away_cs": 21,
            "delta": "-1.4%",
            "source": "sample",
        },
        {
            "date": "Sun 14 Jun",
            "kickoff": "18:00",
            "fixture_set": "World Cup",
            "home_team": "Spain",
            "away_team": "Ghana",
            "home_badge": "ESP",
            "away_badge": "GHA",
            "home_xg": 2.03,
            "away_xg": 0.74,
            "home_cs": 47,
            "away_cs": 13,
            "delta": "+5.6%",
            "source": "sample",
        },
        {
            "date": "Sun 14 Jun",
            "kickoff": "21:00",
            "fixture_set": "World Cup",
            "home_team": "Brazil",
            "away_team": "Croatia",
            "home_badge": "BRA",
            "away_badge": "CRO",
            "home_xg": 1.71,
            "away_xg": 1.18,
            "home_cs": 29,
            "away_cs": 22,
            "delta": "+0.8%",
            "source": "sample",
        },
        {
            "date": "Mon 15 Jun",
            "kickoff": "17:00",
            "fixture_set": "World Cup",
            "home_team": "France",
            "away_team": "Mexico",
            "home_badge": "FRA",
            "away_badge": "MEX",
            "home_xg": 1.78,
            "away_xg": 0.98,
            "home_cs": 38,
            "away_cs": 19,
            "delta": "+2.1%",
            "source": "sample",
        },
        {
            "date": "Mon 15 Jun",
            "kickoff": "20:00",
            "fixture_set": "World Cup",
            "home_team": "Germany",
            "away_team": "USA",
            "home_badge": "GER",
            "away_badge": "USA",
            "home_xg": 1.52,
            "away_xg": 1.20,
            "home_cs": 27,
            "away_cs": 24,
            "delta": "-0.7%",
            "source": "sample",
        },
        {
            "date": "Sat 04 Jul",
            "kickoff": "19:00",
            "fixture_set": "Knockouts",
            "home_team": "Netherlands",
            "away_team": "Portugal",
            "home_badge": "NED",
            "away_badge": "POR",
            "home_xg": 1.28,
            "away_xg": 1.31,
            "home_cs": 25,
            "away_cs": 26,
            "delta": "+0.4%",
            "source": "sample",
        },
        {
            "date": "Sun 05 Jul",
            "kickoff": "21:00",
            "fixture_set": "Knockouts",
            "home_team": "Uruguay",
            "away_team": "Belgium",
            "home_badge": "URU",
            "away_badge": "BEL",
            "home_xg": 1.12,
            "away_xg": 1.47,
            "home_cs": 22,
            "away_cs": 31,
            "delta": "-2.9%",
            "source": "sample",
        },
    ]
)
SAMPLE_FIXTURES["commence_time_dt"] = pd.to_datetime(
    "2026 " + SAMPLE_FIXTURES["date"] + " " + SAMPLE_FIXTURES["kickoff"],
    format="%Y %a %d %b %H:%M",
    utc=True,
).dt.to_pydatetime()

TEAM_FLAGS = {
    "Mexico": "mx",
    "South Africa": "za",
    "Argentina": "ar",
    "England": "gb-eng",
    "Japan": "jp",
    "Brazil": "br",
    "France": "fr",
    "Germany": "de",
    "Spain": "es",
    "Portugal": "pt",
    "Netherlands": "nl",
    "Italy": "it",
    "USA": "us",
    "United States": "us",
    "Canada": "ca",
    "Morocco": "ma",
    "Croatia": "hr",
    "Belgium": "be",
    "Uruguay": "uy",
    "Colombia": "co",
    "Australia": "au",
    "Denmark": "dk",
    "Switzerland": "ch",
    "Poland": "pl",
    "Senegal": "sn",
    "Ghana": "gh",
    "Nigeria": "ng",
    "Cameroon": "cm",
    "Serbia": "rs",
    "Saudi Arabia": "sa",
    "South Korea": "kr",
    "Korea Republic": "kr",
    "Iran": "ir",
    "IR Iran": "ir",
    "Qatar": "qa",
    "Algeria": "dz",
    "Austria": "at",
    "Bosnia & Herzegovina": "ba",
    "Cape Verde": "cv",
    "Cabo Verde": "cv",
    "Chile": "cl",
    "China PR": "cn",
    "Costa Rica": "cr",
    "Curacao": "cw",
    "Cura\u00e7ao": "cw",
    "Czech Republic": "cz",
    "DR Congo": "cd",
    "Congo DR": "cd",
    "Ecuador": "ec",
    "Egypt": "eg",
    "Haiti": "ht",
    "Hong Kong": "hk",
    "Chinese Taipei": "tw",
    "Iraq": "iq",
    "Ivory Coast": "ci",
    "Jamaica": "jm",
    "Jordan": "jo",
    "Korea DPR": "kp",
    "Kuwait": "kw",
    "Lebanon": "lb",
    "New Zealand": "nz",
    "North Macedonia": "mk",
    "Norway": "no",
    "Oman": "om",
    "Palestine": "ps",
    "Panama": "pa",
    "Paraguay": "py",
    "Peru": "pe",
    "Scotland": "gb-sct",
    "Sweden": "se",
    "Syria": "sy",
    "Thailand": "th",
    "Tunisia": "tn",
    "Turkey": "tr",
    "UAE": "ae",
    "Uzbekistan": "uz",
    "Vietnam": "vn",
    "Wales": "gb-wls",
    "Bahrain": "bh",
}


def mobile_parse_datetime(value):
    if not value:
        return datetime.max.replace(tzinfo=timezone.utc)

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.max.replace(tzinfo=timezone.utc)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def mobile_round_for_fixture(home_team, away_team, dt):
    overrides = {
        ("Uzbekistan", "Colombia"): "Round 1",
        ("Colombia", "Uzbekistan"): "Round 1",
        ("Czech Republic", "South Africa"): "Round 2",
        ("South Africa", "Czech Republic"): "Round 2",
        ("Switzerland", "Bosnia & Herzegovina"): "Round 2",
        ("Bosnia & Herzegovina", "Switzerland"): "Round 2",
        ("Canada", "Qatar"): "Round 2",
        ("Qatar", "Canada"): "Round 2",
        ("Colombia", "DR Congo"): "Round 2",
        ("DR Congo", "Colombia"): "Round 2",
    }
    override = overrides.get((home_team, away_team))
    if override:
        return override

    if dt.month == 6 and dt.day <= 17:
        return "Round 1"
    if dt.month == 6 and 18 <= dt.day <= 23:
        return "Round 2"
    if dt.month == 6 and dt.day >= 24:
        return "Round 3"
    return "Knockouts"


def mobile_round_sort_key(round_name):
    return {
        "Round 1": 0,
        "Round 2": 1,
        "Round 3": 2,
        "Knockouts": 3,
    }.get(str(round_name), 99)


def mobile_extract_market(bookmaker, market_key):
    for market in bookmaker.get("markets", []):
        if market.get("key") == market_key:
            return market
    return {}


def mobile_extract_total_and_spread(event):
    home_team = event.get("home_team")
    if not home_team:
        return None, None

    for bookmaker in event.get("bookmakers", []):
        total = None
        total_market = mobile_extract_market(bookmaker, "totals")
        for outcome in total_market.get("outcomes", []):
            point = outcome.get("point")
            if isinstance(point, (int, float)):
                total = float(point)
                break

        spread = None
        spread_market = mobile_extract_market(bookmaker, "spreads")
        for outcome in spread_market.get("outcomes", []):
            point = outcome.get("point")
            if outcome.get("name") == home_team and isinstance(point, (int, float)):
                spread = float(point)
                break

        if total is not None and spread is not None:
            return total, spread

    return None, None


def mobile_goal_projection(total_line, home_spread):
    if total_line is None or home_spread is None:
        return None, None

    home_goals = (total_line - home_spread) / 2
    return home_goals, total_line - home_goals


def mobile_format_goals(value):
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.2f}"


def mobile_format_cs(value):
    if value is None or pd.isna(value):
        return "-"
    return f"{int(value)}%"


TEAM_EMOJIS = {
    "Mexico": "🇲🇽",
    "South Africa": "🇿🇦",
    "Uzbekistan": "🇺🇿",
    "Colombia": "🇨🇴",
    "Czech Republic": "🇨🇿",
    "Switzerland": "🇨🇭",
    "Bosnia & Herzegovina": "🇧🇦",
    "Canada": "🇨🇦",
    "Qatar": "🇶🇦",
    "Jordan": "🇯🇴",
    "Iraq": "🇮🇶",
    "Cape Verde": "🇨🇻",
    "Cabo Verde": "🇨🇻",
    "Argentina": "🇦🇷",
    "England": "🏴",
    "Brazil": "🇧🇷",
    "France": "🇫🇷",
    "Germany": "🇩🇪",
    "Spain": "🇪🇸",
    "Portugal": "🇵🇹",
    "Netherlands": "🇳🇱",
    "USA": "🇺🇸",
    "United States": "🇺🇸",
    "Croatia": "🇭🇷",
    "Belgium": "🇧🇪",
    "Uruguay": "🇺🇾",
    "Morocco": "🇲🇦",
    "Japan": "🇯🇵",
    "South Korea": "🇰🇷",
    "Korea Republic": "🇰🇷",
    "Saudi Arabia": "🇸🇦",
    "Iran": "🇮🇷",
    "IR Iran": "🇮🇷",
    "Australia": "🇦🇺",
    "Denmark": "🇩🇰",
    "Poland": "🇵🇱",
    "Senegal": "🇸🇳",
    "Ghana": "🇬🇭",
    "Nigeria": "🇳🇬",
    "Cameroon": "🇨🇲",
    "Serbia": "🇷🇸",
    "Tunisia": "🇹🇳",
    "Egypt": "🇪🇬",
    "Algeria": "🇩🇿",
    "Scotland": "🏴",
    "Wales": "🏴",
}


def get_team_emoji(team_name):
    if not team_name:
        return "⚽"

    clean = str(team_name).strip()
    return TEAM_EMOJIS.get(clean, "⚽")


def mobile_goal_cell_class(value):
    if value is None or pd.isna(value):
        return "empty"
    if value >= 2.20:
        return "dark-green"
    if value >= 1.70:
        return "green"
    if value >= 1.30:
        return "grey"
    if value >= 1.00:
        return "pink"
    return "red"


def mobile_cs_cell_class(value):
    if value is None or pd.isna(value):
        return "empty"
    if value >= 45:
        return "dark-green"
    if value >= 32:
        return "green"
    if value >= 22:
        return "grey"
    if value >= 15:
        return "red"
    return "dark-red"


@st.cache_data(ttl=600, show_spinner=False)
def fetch_world_cup_odds_mobile():
    api_key = ODDS_API_KEY
    if not api_key or api_key == "your_api_key_here":
        return []

    params = {
        "apiKey": api_key,
        "regions": "uk,eu",
        "markets": "h2h,totals,spreads",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }

    try:
        response = requests.get(ODDS_API_URL, params=params, timeout=12)
        if response.status_code != 200:
            return []
        return response.json()
    except (requests.RequestException, ValueError):
        return []


def mobile_parse_odds_response(payload):
    rows = []
    for event in payload or []:
        commence_time = event.get("commence_time")
        dt = mobile_parse_datetime(commence_time)
        home_team = event.get("home_team", "Home team")
        away_team = event.get("away_team", "Away team")
        total_line, home_spread = mobile_extract_total_and_spread(event)
        home_goals, away_goals = mobile_goal_projection(total_line, home_spread)
        home_cs = round(math.exp(-away_goals) * 100) if away_goals is not None else None
        away_cs = round(math.exp(-home_goals) * 100) if home_goals is not None else None

        rows.append(
            {
                "Date": dt.strftime("%a %d %b") if dt.year < 9999 else "TBD",
                "Time": dt.strftime("%H:%M") if dt.year < 9999 else "TBD",
                "Home": home_team,
                "Home Goals": mobile_format_goals(home_goals),
                "Home CS%": mobile_format_cs(home_cs),
                "Away": away_team,
                "Away Goals": mobile_format_goals(away_goals),
                "Away CS%": mobile_format_cs(away_cs),
                "home_goals_value": home_goals,
                "home_cs_value": home_cs,
                "away_goals_value": away_goals,
                "away_cs_value": away_cs,
                "round": mobile_round_for_fixture(home_team, away_team, dt),
                "commence_time_dt": dt,
            }
        )

    return pd.DataFrame(rows).sort_values("commence_time_dt") if rows else pd.DataFrame(rows)


def mobile_sample_fixtures():
    rows = SAMPLE_FIXTURES.copy()
    rows["round"] = rows.apply(
        lambda row: mobile_round_for_fixture(
            row["home_team"],
            row["away_team"],
            row["commence_time_dt"],
        ),
        axis=1,
    )
    rows = rows.rename(
        columns={
            "date": "Date",
            "kickoff": "Time",
            "home_team": "Home",
            "home_xg": "Home Goals",
            "home_cs": "Home CS%",
            "away_team": "Away",
            "away_xg": "Away Goals",
            "away_cs": "Away CS%",
        }
    )
    rows["home_goals_value"] = rows["Home Goals"]
    rows["home_cs_value"] = rows["Home CS%"]
    rows["away_goals_value"] = rows["Away Goals"]
    rows["away_cs_value"] = rows["Away CS%"]
    rows["Home Goals"] = rows["Home Goals"].apply(mobile_format_goals)
    rows["Away Goals"] = rows["Away Goals"].apply(mobile_format_goals)
    rows["Home CS%"] = rows["Home CS%"].apply(mobile_format_cs)
    rows["Away CS%"] = rows["Away CS%"].apply(mobile_format_cs)
    return rows


def render_mobile_card(row):
    home = str(row["Home"])
    away = str(row["Away"])
    return (
        '<article class="mobile-fixture-card">'
        '<div class="mobile-date">'
        f'<strong>{escape(str(row["Date"]))}</strong>'
        f'<span>{escape(str(row["Time"]))}</span>'
        "</div>"
        '<div class="mobile-teams">'
        '<div class="mobile-team-row">'
        f'<span class="flag-emoji">{get_team_emoji(home)}</span>'
        f'<span class="team-name">{escape(home)}</span>'
        "</div>"
        '<div class="mobile-team-row">'
        f'<span class="flag-emoji">{get_team_emoji(away)}</span>'
        f'<span class="team-name">{escape(away)}</span>'
        "</div>"
        "</div>"
        '<div class="mobile-metric-col">'
        '<div class="mobile-metric-head">PROJ</div>'
        f'<div class="mobile-metric {mobile_goal_cell_class(row["home_goals_value"])}">{escape(str(row["Home Goals"]))}</div>'
        f'<div class="mobile-metric {mobile_goal_cell_class(row["away_goals_value"])}">{escape(str(row["Away Goals"]))}</div>'
        "</div>"
        '<div class="mobile-metric-col">'
        '<div class="mobile-metric-head">CS %</div>'
        f'<div class="mobile-metric {mobile_cs_cell_class(row["home_cs_value"])}">{escape(str(row["Home CS%"]))}</div>'
        f'<div class="mobile-metric {mobile_cs_cell_class(row["away_cs_value"])}">{escape(str(row["Away CS%"]))}</div>'
        "</div>"
        "</article>"
    )


def render_mobile_cards(fixtures):
    cards = "\n".join(render_mobile_card(row) for row in fixtures.to_dict("records"))
    return f'<section class="mobile-card-list">{cards}</section>'


def render_mobile_top_team_card(row, metric_key):
    round_cells = []
    for round_name in ROUND_TABLE_COLUMNS:
        cell = row["rounds"].get(round_name)
        if not cell:
            round_cells.append(
                '<div class="mobile-top-team-round">'
                f'<span>{escape(round_name)}</span>'
                "<strong>-</strong>"
                "</div>"
            )
            continue

        value = cell[metric_key]
        value_text = (
            format_projected_goals(value)
            if metric_key == "projected_goals"
            else format_clean_sheet(value)
        )
        round_cells.append(
            '<div class="mobile-top-team-round">'
            f'<span>{escape(round_name)}</span>'
            f'<em>{escape(str(cell["opponent"]))}</em>'
            f'<strong>{escape(value_text)}</strong>'
            "</div>"
        )

    return (
        '<article class="mobile-top-team-card">'
        '<div class="mobile-top-team-name">'
        f'<span class="flag-emoji">{get_team_emoji(row["team"])}</span>'
        f'<strong>{escape(str(row["team"]))}</strong>'
        "</div>"
        '<div class="mobile-top-team-rounds">'
        f'{"".join(round_cells)}'
        "</div>"
        "</article>"
    )


def render_mobile_top_teams(fixtures, metric_key):
    rows = build_top_team_round_table(fixtures, metric_key)
    if not rows:
        return '<div class="mobile-top-empty">No model data available yet.</div>'

    cards = "\n".join(render_mobile_top_team_card(row, metric_key) for row in rows)
    return f'<section class="mobile-top-team-list">{cards}</section>'


def mobile_styles():
    st.markdown(
        """
        <style>
            .stApp {
                background: #eef1f4;
                color: #17202a;
            }

            .block-container {
                max-width: 460px;
                padding: 0.5rem 0.65rem 2rem;
            }

            .mobile-title {
                max-width: 430px;
                margin: 0 auto 0.85rem;
            }

            .mobile-title h1 {
                margin: 0;
                font-size: 1.7rem;
                line-height: 1.05;
                color: #17202a;
                letter-spacing: 0;
            }

            .mobile-title p {
                margin: 0.4rem 0 0;
                color: #687380;
                font-size: 0.9rem;
            }

            .brand-header {
                display: flex;
                align-items: center;
                gap: 12px;
                max-width: 430px;
                margin: 0 auto 18px;
            }

            .brand-logo {
                width: 64px;
                height: 64px;
                border-radius: 16px;
                object-fit: cover;
                flex: 0 0 64px;
            }

            .brand-header h1 {
                margin: 0;
                font-size: 25px;
                line-height: 1.05;
                color: #111827;
                letter-spacing: 0;
                font-weight: 900;
            }

            .brand-header a {
                display: inline-block;
                margin-top: 8px;
                color: #64748b;
                font-size: 13px;
                text-decoration: none;
            }

            .brand-header a:hover {
                text-decoration: underline;
            }

            .mobile-card-list {
                display: grid;
                grid-template-columns: 1fr;
                gap: 0.72rem;
                max-width: 430px;
                margin: 0.8rem auto 0;
            }

            .mobile-fixture-card {
                display: grid;
                grid-template-columns: 70px minmax(0, 1fr) 58px 58px;
                background: #ffffff;
                border: 1px solid #d8dee8;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 2px 6px rgba(23, 32, 42, 0.06);
            }

            .mobile-date {
                background: #f5f7fa;
                border-right: 1px solid #d8dee8;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                text-align: center;
                padding: 0.45rem 0.28rem;
                gap: 0.14rem;
            }

            .mobile-date strong,
            .mobile-date span {
                font-size: 0.7rem;
                line-height: 1.1;
            }

            .mobile-date span {
                color: #687380;
                font-weight: 750;
            }

            .mobile-teams {
                display: grid;
                grid-template-rows: 1fr 1fr;
                padding-top: 28px;
                min-width: 0;
            }

            .mobile-team-row {
                min-height: 41px;
                display: flex;
                align-items: center;
                gap: 0.45rem;
                padding: 0.45rem 0.55rem;
                border-bottom: 1px solid #d8dee8;
                min-width: 0;
            }

            .mobile-team-row:last-child {
                border-bottom: 0;
            }

            .flag-emoji {
                width: 24px;
                text-align: center;
                margin-right: 6px;
                display: inline-block;
                font-size: 17px;
                line-height: 1;
            }

            .team-name {
                font-size: 0.88rem;
                font-weight: 850;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .mobile-metric-col {
                display: grid;
                grid-template-rows: 28px 1fr 1fr;
                border-left: 1px solid #d8dee8;
            }

            .mobile-metric-head {
                min-height: 28px;
                background: #f5f7fa;
                border-bottom: 1px solid #d8dee8;
                display: grid;
                place-items: center;
                color: #687380;
                font-size: 0.6rem;
                font-weight: 850;
            }

            .mobile-metric {
                min-height: 41px;
                display: grid;
                place-items: center;
                border-bottom: 1px solid #d8dee8;
                font-size: 0.84rem;
                font-weight: 850;
            }

            .mobile-metric:last-child {
                border-bottom: 0;
            }

            .dark-green {
                background: #28531d;
                color: #ffffff;
            }

            .green {
                background: #00e676;
                color: #064e3b;
            }

            .grey {
                background: #dedede;
                color: #263238;
            }

            .pink {
                background: #ffe6e6;
                color: #b91c1c;
            }

            .red {
                background: #ff0f4f;
                color: #ffffff;
            }

            .dark-red {
                background: #8b002f;
                color: #ffffff;
            }

            .empty {
                background: #f1f5f9;
                color: #64748b;
            }

            .mobile-top-section {
                max-width: 430px;
                margin: 1.5rem auto 0;
            }

            .mobile-top-section h2 {
                margin: 0 0 0.25rem;
                color: #111827;
                font-size: 1.35rem;
                line-height: 1.1;
            }

            .mobile-top-section p {
                margin: 0 0 0.75rem;
                color: #687380;
                font-size: 0.84rem;
            }

            .mobile-top-team-list {
                display: grid;
                gap: 0.7rem;
                margin-top: 0.8rem;
            }

            .mobile-top-team-card {
                background: #ffffff;
                border: 1px solid #d8dee8;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 2px 6px rgba(23, 32, 42, 0.05);
            }

            .mobile-top-team-name {
                display: flex;
                align-items: center;
                gap: 0.35rem;
                padding: 0.7rem 0.75rem;
                border-bottom: 1px solid #d8dee8;
                color: #111827;
            }

            .mobile-top-team-name strong {
                font-size: 0.95rem;
            }

            .mobile-top-team-rounds {
                display: grid;
                grid-template-columns: 1fr;
            }

            .mobile-top-team-round {
                display: grid;
                grid-template-columns: 78px minmax(0, 1fr) 62px;
                align-items: center;
                gap: 0.4rem;
                min-height: 44px;
                padding: 0.45rem 0.75rem;
                border-bottom: 1px solid #edf1f5;
            }

            .mobile-top-team-round:last-child {
                border-bottom: 0;
            }

            .mobile-top-team-round span {
                color: #687380;
                font-size: 0.72rem;
                font-weight: 850;
                text-transform: uppercase;
            }

            .mobile-top-team-round em {
                color: #111827;
                font-size: 0.84rem;
                font-style: normal;
                font-weight: 800;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .mobile-top-team-round strong {
                color: #0f7a45;
                font-size: 0.92rem;
                text-align: right;
            }

            .mobile-top-empty {
                margin-top: 0.8rem;
                padding: 0.9rem;
                background: #ffffff;
                border: 1px dashed #bdc8d3;
                border-radius: 10px;
                color: #687380;
                font-weight: 800;
                text-align: center;
            }

            @media (max-width: 768px) {
                header[data-testid="stHeader"] {
                    display: none !important;
                }

                .stAppToolbar {
                    display: none !important;
                }

                .stDeployButton {
                    display: none !important;
                }

                div[data-testid="stToolbar"] {
                    display: none !important;
                }

                #MainMenu {
                    display: none !important;
                }

                footer {
                    display: none !important;
                }

                .block-container {
                    padding-top: 0.5rem !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_mobile_dashboard():
    mobile_styles()
    st.markdown(
        render_brand_header(),
        unsafe_allow_html=True,
    )

    live_fixtures = mobile_parse_odds_response(fetch_world_cup_odds_mobile())
    fixtures = live_fixtures if not live_fixtures.empty else mobile_sample_fixtures()

    round_options = sorted(
        fixtures["round"].drop_duplicates().tolist(),
        key=mobile_round_sort_key,
    )
    selected_round = st.selectbox("Round", round_options)

    fixtures_to_show = fixtures[fixtures["round"] == selected_round]
    page_size = 8
    max_pages = max(1, math.ceil(len(fixtures_to_show) / page_size))
    page_options = [f"Page {page_number}" for page_number in range(1, max_pages + 1)]
    selected_page = st.selectbox("Page", page_options)
    page_number = page_options.index(selected_page) + 1
    start = (page_number - 1) * page_size
    end = start + page_size
    fixtures_page = fixtures_to_show.iloc[start:end]
    st.markdown(render_mobile_cards(fixtures_page), unsafe_allow_html=True)
    st.markdown(
        """
        <section class="mobile-top-section">
          <h2>Top Teams by Round</h2>
          <p>Live odds via The Odds API</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    mobile_goal_tab, mobile_cs_tab = st.tabs(["Projected Goals", "Clean Sheet %"])
    with mobile_goal_tab:
        st.markdown(
            render_mobile_top_teams(fixtures, "projected_goals"),
            unsafe_allow_html=True,
        )
    with mobile_cs_tab:
        st.markdown(
            render_mobile_top_teams(fixtures, "clean_sheet_pct"),
            unsafe_allow_html=True,
        )


DESKTOP_STYLE = (
    """
    <style>
        :root {
            --app-bg: #eef1f4;
            --ink: #17202a;
            --muted: #687380;
            --line: #d8dee6;
            --card: #ffffff;
            --green: #12a66a;
            --blue: #1f77d0;
            --amber: #f0a51f;
            --pill: #edf3f8;
        }

        .stApp {
            background: var(--app-bg);
            color: var(--ink);
            max-width: 100%;
            overflow-x: hidden;
        }

        .block-container {
            max-width: 1560px;
            padding-top: 0.75rem;
            padding-left: 1.25rem;
            padding-right: 1.25rem;
            padding-bottom: 3rem;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        .title-section {
            display: flex;
            align-items: end;
            justify-content: space-between;
            gap: 1rem;
            margin: 0 0 1rem;
        }

        .title-section h1 {
            margin: 0;
            font-size: clamp(2rem, 3vw, 3.1rem);
            line-height: 1.05;
            letter-spacing: 0;
            color: var(--ink);
        }

        .title-section p {
            margin: 0.45rem 0 0;
            color: var(--muted);
            font-size: 1rem;
        }

        .status-chip {
            background: #fff;
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 0.5rem 0.8rem;
            color: var(--muted);
            font-size: 0.9rem;
            white-space: nowrap;
            box-shadow: 0 8px 18px rgba(23, 32, 42, 0.06);
        }

        .brand-header {
            display: flex;
            align-items: center;
            gap: 18px;
            margin-bottom: 22px;
        }

        .brand-logo {
            width: 90px;
            height: 90px;
            border-radius: 22px;
            object-fit: cover;
            flex: 0 0 90px;
        }

        .brand-header h1 {
            margin: 0;
            font-size: 44px;
            line-height: 1.05;
            color: #111827;
            letter-spacing: 0;
            font-weight: 900;
        }

        .brand-header a {
            display: inline-block;
            margin-top: 8px;
            color: #64748b;
            font-size: 15px;
            text-decoration: none;
        }

        .brand-header a:hover {
            text-decoration: underline;
        }

        div[data-testid="stHorizontalBlock"] {
            gap: 1rem;
        }

        .stSelectbox label,
        .stSegmentedControl label,
        .stRadio label {
            font-weight: 700;
            color: var(--ink);
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius: 10px;
            border: 1px solid #c8d2dc;
            background: #ffffff;
            color: var(--ink);
            font-weight: 750;
            min-height: 2.75rem;
            box-shadow: 0 8px 18px rgba(23, 32, 42, 0.08);
        }

        .fixture-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1.1rem;
            margin-top: 0.75rem;
        }

        .date-group {
            margin-top: 1.25rem;
        }

        .export-area {
            padding-bottom: 32px;
        }

        .export-footer {
            margin-top: 28px;
            padding: 14px 4px 4px 4px;
            border-top: 1px solid #d8dee8;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 13px;
            color: #1f2937;
        }

        .date-heading {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 900;
            margin: 0 0 0.65rem;
        }

        .date-heading span {
            color: var(--muted);
            font-weight: 750;
        }

        .fixture-card {
            background: var(--card);
            border: 1px solid #dce3ea;
            border-radius: 12px;
            display: grid;
            grid-template-columns: 92px minmax(0, 1fr) 92px 92px;
            overflow: hidden;
            box-shadow: 0 10px 20px rgba(23, 32, 42, 0.08);
        }

        .date-block {
            background: #f5f7fa;
            border-right: 1px solid var(--line);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.18rem;
            padding: 0.85rem 0.65rem;
            text-align: center;
        }

        .date-block strong {
            color: var(--ink);
            font-size: 0.88rem;
            line-height: 1.1;
        }

        .date-block span {
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 750;
            text-transform: uppercase;
        }

        .fixture-teams,
        .projection-col,
        .clean-col {
            display: grid;
            grid-template-rows: 34px 1fr 1fr;
        }

        .fixture-teams {
            grid-template-rows: 1fr 1fr;
            padding-top: 34px;
        }

        .team-row,
        .metric-cell {
            min-height: 58px;
            border-bottom: 1px solid var(--line);
        }

        .team-row:last-child,
        .metric-cell:last-child {
            border-bottom: 0;
        }

        .team-row {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            padding: 0.72rem 0.9rem;
            min-width: 0;
        }

        .team-flag {
            width: 28px;
            height: 28px;
            flex: 0 0 28px;
            object-fit: cover;
            border-radius: 50%;
            box-shadow: 0 0 0 1px #d8dee8;
            background: #f4f6f8;
        }

        .team-flag-fallback {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #e5e7eb;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
        }

        .team-name {
            color: var(--ink);
            font-size: 0.98rem;
            font-weight: 850;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .metric-head {
            min-height: 34px;
            display: grid;
            place-items: center;
            padding: 0.4rem;
            background: #f5f7fa;
            border-left: 1px solid var(--line);
            border-bottom: 1px solid var(--line);
            color: var(--muted);
            font-size: 0.68rem;
            font-weight: 800;
            text-transform: uppercase;
            text-align: center;
        }

        .metric-cell {
            border-left: 1px solid var(--line);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0.65rem 0.45rem;
            font-weight: 800;
            font-size: 22px;
        }

        .cell-dark-green {
            background: #28531d;
            color: #ffffff;
        }

        .cell-green {
            background: #00e676;
            color: #064e3b;
        }

        .cell-grey {
            background: #dedede;
            color: #263238;
        }

        .cell-light-red {
            background: #ffe6e6;
            color: #b91c1c;
        }

        .cell-red {
            background: #ff0f4f;
            color: #ffffff;
        }

        .cell-dark-red {
            background: #8b002f;
            color: #ffffff;
        }

        .cell-empty {
            background: #f1f5f9;
            color: #64748b;
        }

        .empty-note {
            margin-top: 1.2rem;
            padding: 1.2rem;
            background: #fff;
            border: 1px dashed #bdc8d3;
            border-radius: 16px;
            color: var(--muted);
            text-align: center;
            font-weight: 700;
        }

        .top-teams-section {
            margin: 2rem 0 1rem;
        }

        .section-kicker {
            color: #0f7a45;
            font-size: 0.78rem;
            font-weight: 900;
            letter-spacing: 0;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .top-teams-section h2 {
            margin: 0;
            color: #111827;
            font-size: 2rem;
            line-height: 1.1;
            font-weight: 900;
        }

        .top-teams-section p {
            margin: 0.35rem 0 0;
            color: var(--muted);
            font-size: 0.98rem;
        }

        .top-teams-table-wrap {
            margin-top: 0.9rem;
            background: #ffffff;
            border: 1px solid #d8dee8;
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 12px 24px rgba(23, 32, 42, 0.08);
        }

        .top-teams-table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }

        .top-teams-table th {
            background: #f5f7fa;
            border-bottom: 1px solid #d8dee8;
            color: #64748b;
            font-size: 0.72rem;
            font-weight: 900;
            padding: 0.85rem 1rem;
            text-align: left;
            text-transform: uppercase;
        }

        .top-teams-table th:first-child {
            width: 30%;
        }

        .top-teams-table td {
            border-bottom: 1px solid #edf1f5;
            padding: 0.78rem 1rem;
            vertical-align: middle;
        }

        .top-teams-table tbody tr:last-child td {
            border-bottom: 0;
        }

        .top-team-cell {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            color: #111827;
            font-size: 0.98rem;
            font-weight: 900;
            min-width: 0;
        }

        .top-rank {
            width: 26px;
            height: 26px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            background: #eef3f7;
            color: #64748b;
            font-size: 0.76rem;
            font-weight: 900;
            flex: 0 0 26px;
        }

        .top-round-cell {
            min-height: 54px;
        }

        .top-round-cell .top-opponent {
            display: block;
            color: #111827;
            font-size: 0.88rem;
            font-weight: 800;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .top-round-cell strong {
            display: block;
            margin-top: 0.16rem;
            color: #0f7a45;
            font-size: 1.22rem;
            font-weight: 950;
            line-height: 1;
        }

        .top-round-empty {
            color: #94a3b8;
            font-weight: 800;
        }

        @media (max-width: 880px) {
            html,
            body,
            [data-testid="stAppViewContainer"],
            .stApp {
                max-width: 100%;
                overflow-x: hidden;
            }

            .block-container {
                max-width: 100%;
                padding-left: 0.75rem;
                padding-right: 0.75rem;
            }

            .title-section {
                align-items: flex-start;
                flex-direction: column;
                gap: 0.85rem;
                padding-top: 0.4rem;
            }

            .title-section h1 {
                font-size: 1.75rem;
            }

            .title-section p {
                font-size: 0.95rem;
            }

            .fixture-grid {
                grid-template-columns: 1fr;
                gap: 0.7rem;
            }

            .date-group {
                margin-top: 1.1rem;
            }

            .date-heading {
                font-size: 0.95rem;
            }

            .fixture-card {
                box-shadow: 0 4px 10px rgba(22, 34, 51, 0.08);
            }

            .export-area {
                padding-bottom: 18px;
            }

            .brand-header {
                gap: 12px;
                margin-bottom: 18px;
            }

            .brand-logo {
                width: 64px;
                height: 64px;
                border-radius: 16px;
                flex-basis: 64px;
            }

            .brand-header h1 {
                font-size: 25px;
            }

            .brand-header a {
                font-size: 13px;
            }
        }

        @media (max-width: 700px) {
            .export-footer {
                flex-direction: column;
                gap: 6px;
                align-items: flex-start;
            }
        }

        @media (max-width: 520px) {
            .fixture-card {
                grid-template-columns: 68px minmax(0, 1fr) 64px 64px;
                border-radius: 8px;
            }

            .team-row {
                padding: 0.55rem;
            }

            .team-name {
                font-size: 0.82rem;
            }

            .metric-head {
                font-size: 0.54rem;
                padding: 0.38rem 0.15rem;
            }

            .metric-cell {
                font-size: 0.8rem;
                padding: 0.55rem 0.2rem;
            }

            .date-block {
                padding: 0.5rem 0.3rem;
            }

            .date-block strong,
            .date-block span {
                font-size: 0.68rem;
            }

            .team-flag,
            .team-flag-fallback {
                width: 24px;
                height: 24px;
                flex-basis: 24px;
                font-size: 12px;
            }
        }
    </style>
    """
)


def desktop_styles():
    st.markdown(DESKTOP_STYLE, unsafe_allow_html=True)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_world_cup_odds():
    api_key = ODDS_API_KEY
    if not api_key or api_key == "your_api_key_here":
        return [], None, None

    params = {
        "apiKey": api_key,
        "regions": "uk,eu",
        "markets": "h2h,totals,spreads",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }

    try:
        response = requests.get(ODDS_API_URL, params=params, timeout=12)
        status_code = response.status_code
        if status_code != 200:
            return [], f"The Odds API returned status code {status_code}.", status_code
        return response.json(), None, status_code
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return [], str(exc), status_code
    except ValueError:
        return [], "The Odds API returned a response that was not valid JSON.", None


def team_badge(team_name):
    words = team_name.replace("-", " ").split()
    if not words:
        return "TBD"
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(word[0] for word in words[:3]).upper()


def get_flag_url(team_name):
    if not team_name:
        return ""

    clean_name = str(team_name).strip()
    code = TEAM_FLAGS.get(clean_name)

    if not code:
        return ""

    return f"https://flagcdn.com/w40/{code}.png"


def parse_commence_time(value):
    if not value:
        return "TBD", "TBD", "TBD"

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value, "TBD", "Live"

    return parsed.strftime("%a %d %b"), parsed.strftime("%H:%M"), parsed.strftime("%d %b")


def parse_commence_datetime(value):
    if not value:
        return datetime.max.replace(tzinfo=timezone.utc)

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.max.replace(tzinfo=timezone.utc)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


ROUND_ORDER = {
    "Round 1": 0,
    "Round 2": 1,
    "Round 3": 2,
    "Knockouts": 3,
}

SHARP_BOOKS = [
    "Pinnacle",
    "Betfair Exchange",
    "SBOBET",
    "Matchbook",
    "Marathon Bet",
    "188Bet",
]

ROUND_OVERRIDES = {
    ("Uzbekistan", "Colombia"): "Round 1",
    ("Colombia", "Uzbekistan"): "Round 1",
    ("Czech Republic", "South Africa"): "Round 2",
    ("South Africa", "Czech Republic"): "Round 2",
    ("Switzerland", "Bosnia & Herzegovina"): "Round 2",
    ("Bosnia & Herzegovina", "Switzerland"): "Round 2",
    ("Canada", "Qatar"): "Round 2",
    ("Qatar", "Canada"): "Round 2",
    ("Colombia", "DR Congo"): "Round 2",
    ("DR Congo", "Colombia"): "Round 2",
}


def get_round_for_fixture(home_team, away_team, dt):
    override = ROUND_OVERRIDES.get((home_team, away_team))
    if override:
        return override

    if dt.month == 6 and dt.day <= 17:
        return "Round 1"

    if dt.month == 6 and 18 <= dt.day <= 23:
        return "Round 2"

    if dt.month == 6 and dt.day >= 24:
        return "Round 3"

    return "Knockouts"


def round_sort_key(round_name):
    return ROUND_ORDER.get(str(round_name), 99)


def get_current_round(fixtures):
    rounds = sorted(
        {fixture["round"] for fixture in fixtures},
        key=round_sort_key,
    )

    now = datetime.now(timezone.utc)

    for round_name in rounds:
        round_fixtures = [
            fixture for fixture in fixtures if fixture["round"] == round_name
        ]
        if any(fixture["commence_time_dt"] > now for fixture in round_fixtures):
            return round_name

    return rounds[-1] if rounds else "Round 1"


SAMPLE_FIXTURES["round"] = SAMPLE_FIXTURES.apply(
    lambda row: get_round_for_fixture(
        row["home_team"],
        row["away_team"],
        row["commence_time_dt"],
    ),
    axis=1,
)


def format_price(price):
    if price is None:
        return "-"
    try:
        return f"{float(price):.2f}"
    except (TypeError, ValueError):
        return str(price)


def extract_market(bookmaker, market_key):
    for market in bookmaker.get("markets", []):
        if market.get("key") == market_key:
            return market
    return {}


def bookmaker_rank(bookmaker):
    try:
        return SHARP_BOOKS.index(bookmaker["title"])
    except (KeyError, ValueError):
        return 999


def extract_total(bookmaker):
    market = extract_market(bookmaker, "totals")
    for outcome in market.get("outcomes", []):
        point = outcome.get("point")
        if isinstance(point, (int, float)):
            return float(point)
    return None


def extract_spread(bookmaker, home_team):
    market = extract_market(bookmaker, "spreads")
    for outcome in market.get("outcomes", []):
        point = outcome.get("point")
        if outcome.get("name") == home_team and isinstance(point, (int, float)):
            return float(point)
    return None


def has_h2h_market(bookmaker):
    return bool(extract_market(bookmaker, "h2h").get("outcomes"))


def average(values):
    return sum(values) / len(values) if values else None


def extract_total_and_home_spread(event):
    home_team = event.get("home_team")
    if not home_team:
        return None, None

    sorted_books = sorted(event.get("bookmakers", []), key=bookmaker_rank)
    sharp_candidates = []

    for bookmaker in sorted_books:
        if bookmaker.get("title") not in SHARP_BOOKS:
            continue

        total = extract_total(bookmaker)
        spread = extract_spread(bookmaker, home_team)

        if total is not None and spread is not None:
            sharp_candidates.append(
                {
                    "total": total,
                    "spread": spread,
                    "has_h2h": has_h2h_market(bookmaker),
                }
            )

    if sharp_candidates:
        preferred = [
            candidate for candidate in sharp_candidates if candidate["has_h2h"]
        ] or sharp_candidates
        return (
            average([candidate["total"] for candidate in preferred]),
            average([candidate["spread"] for candidate in preferred]),
        )

    fallback_candidates = []
    for bookmaker in sorted_books:
        total = extract_total(bookmaker)
        spread = extract_spread(bookmaker, home_team)

        if total is not None and spread is not None:
            fallback_candidates.append(
                {
                    "total": total,
                    "spread": spread,
                    "has_h2h": has_h2h_market(bookmaker),
                    "rank": bookmaker_rank(bookmaker),
                }
            )

    if fallback_candidates:
        fallback_candidates = sorted(
            fallback_candidates,
            key=lambda candidate: (not candidate["has_h2h"], candidate["rank"]),
        )
        best = fallback_candidates[0]
        return best["total"], best["spread"]

    return None, None


def extract_total_line(event):
    total_line, _home_spread = extract_total_and_home_spread(event)
    return total_line


def extract_home_spread(event):
    _total_line, home_spread = extract_total_and_home_spread(event)
    return home_spread


def calculate_team_goal_projections(total_line, home_spread):
    if total_line is None or home_spread is None:
        return None, None

    home_projected_goals = (total_line - home_spread) / 2
    away_projected_goals = total_line - home_projected_goals
    return home_projected_goals, away_projected_goals


def calculate_clean_sheet_percent(opponent_projected_goals):
    if opponent_projected_goals is None:
        return None
    return round(math.exp(-opponent_projected_goals) * 100)


def parse_odds_response(payload):
    rows = []
    for event in payload or []:
        commence_time = event.get("commence_time")
        date_label, kickoff, _unused_label = parse_commence_time(commence_time)
        commence_time_dt = parse_commence_datetime(commence_time)
        home_team = event.get("home_team", "Home team")
        away_team = event.get("away_team", "Away team")
        total_line, home_spread = extract_total_and_home_spread(event)
        home_xg, away_xg = calculate_team_goal_projections(total_line, home_spread)

        rows.append(
            {
                "date": date_label,
                "kickoff": kickoff,
                "round": get_round_for_fixture(
                    home_team,
                    away_team,
                    commence_time_dt,
                ),
                "commence_time": commence_time,
                "commence_time_dt": commence_time_dt,
                "fixture_set": "World Cup",
                "home_team": home_team,
                "away_team": away_team,
                "home_badge": team_badge(home_team),
                "away_badge": team_badge(away_team),
                "home_xg": home_xg,
                "away_xg": away_xg,
                "home_cs": calculate_clean_sheet_percent(away_xg),
                "away_cs": calculate_clean_sheet_percent(home_xg),
                "total_line": total_line,
                "home_spread": home_spread,
                "delta": "Live odds",
                "source": "api",
            }
        )

    if not rows:
        return pd.DataFrame(rows)

    return pd.DataFrame(rows).sort_values("commence_time_dt")


def format_projected_goals(value):
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.2f}"


def format_clean_sheet(value):
    if value is None or pd.isna(value):
        return "-"
    return f"{int(value)}%"


ROUND_TABLE_COLUMNS = ["Round 1", "Round 2", "Round 3"]


def optional_float(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value):
    number = optional_float(value)
    if number is None:
        return None
    return int(round(number))


def build_team_round_rows(fixtures):
    columns = [
        "team",
        "opponent",
        "round",
        "projected_goals",
        "clean_sheet_pct",
    ]
    if fixtures is None or fixtures.empty:
        return pd.DataFrame(columns=columns)

    team_round_rows = []
    for fixture in fixtures.to_dict("records"):
        home_team = fixture.get("home_team") or fixture.get("Home")
        away_team = fixture.get("away_team") or fixture.get("Away")
        round_name = fixture.get("round")

        team_round_rows.append(
            {
                "team": home_team,
                "opponent": away_team,
                "round": round_name,
                "projected_goals": optional_float(
                    fixture.get("home_xg", fixture.get("home_goals_value"))
                ),
                "clean_sheet_pct": optional_int(
                    fixture.get("home_cs", fixture.get("home_cs_value"))
                ),
            }
        )
        team_round_rows.append(
            {
                "team": away_team,
                "opponent": home_team,
                "round": round_name,
                "projected_goals": optional_float(
                    fixture.get("away_xg", fixture.get("away_goals_value"))
                ),
                "clean_sheet_pct": optional_int(
                    fixture.get("away_cs", fixture.get("away_cs_value"))
                ),
            }
        )

    return pd.DataFrame(team_round_rows, columns=columns)


def build_top_team_round_table(fixtures, metric_key, top_n=10):
    team_rows = build_team_round_rows(fixtures)
    if team_rows.empty or metric_key not in team_rows.columns:
        return []

    team_rows = team_rows[
        team_rows["round"].isin(ROUND_TABLE_COLUMNS)
        & team_rows["team"].notna()
        & team_rows[metric_key].notna()
    ].copy()
    if team_rows.empty:
        return []

    team_rows = team_rows.sort_values(metric_key, ascending=False)
    best_by_team_round = team_rows.drop_duplicates(["team", "round"], keep="first")
    ranking = (
        best_by_team_round.groupby("team", as_index=False)[metric_key]
        .max()
        .sort_values(metric_key, ascending=False)
        .head(top_n)
    )

    output_rows = []
    for team in ranking["team"].tolist():
        team_rounds = {}
        for round_name in ROUND_TABLE_COLUMNS:
            match_rows = best_by_team_round[
                (best_by_team_round["team"] == team)
                & (best_by_team_round["round"] == round_name)
            ]
            if match_rows.empty:
                continue
            match = match_rows.iloc[0]
            team_rounds[round_name] = {
                "opponent": match["opponent"],
                "projected_goals": match["projected_goals"],
                "clean_sheet_pct": match["clean_sheet_pct"],
            }
        output_rows.append({"team": team, "rounds": team_rounds})

    return output_rows


def goal_cell_class(value):
    if value is None or pd.isna(value):
        return "cell-empty"
    if value >= 2.20:
        return "cell-dark-green"
    if value >= 1.70:
        return "cell-green"
    if value >= 1.30:
        return "cell-grey"
    if value >= 1.00:
        return "cell-light-red"
    return "cell-red"


def cs_cell_class(value):
    if value is None or pd.isna(value):
        return "cell-empty"
    if value >= 45:
        return "cell-dark-green"
    if value >= 32:
        return "cell-green"
    if value >= 22:
        return "cell-grey"
    if value >= 15:
        return "cell-red"
    return "cell-dark-red"


CELL_COLORS = {
    "cell-dark-green": ("#28531d", "#ffffff"),
    "cell-green": ("#00e676", "#064e3b"),
    "cell-grey": ("#dedede", "#263238"),
    "cell-light-red": ("#ffe6e6", "#b91c1c"),
    "cell-red": ("#ff0f4f", "#ffffff"),
    "cell-dark-red": ("#8b002f", "#ffffff"),
    "cell-empty": ("#f1f5f9", "#64748b"),
}

_FLAG_CACHE = {}


def hex_to_rgb(hex_color):
    value = hex_color.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def load_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for font_path in paths:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_text_center(draw, box, text, font, fill):
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = left + ((right - left) - text_width) / 2
    y = top + ((bottom - top) - text_height) / 2 - 2
    draw.text((x, y), text, font=font, fill=fill)


def draw_metric_cell(draw, box, text, class_name, font):
    bg_color, text_color = CELL_COLORS[class_name]
    draw.rectangle(box, fill=hex_to_rgb(bg_color))
    draw_text_center(draw, box, text, font, hex_to_rgb(text_color))


@st.cache_data(ttl=86400, show_spinner=False)
def get_flag_bytes(code):
    if not code:
        return None

    try:
        url = f"https://flagcdn.com/w40/{code}.png"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.content
    except requests.RequestException:
        return None


def load_flag_image(team):
    code = TEAM_FLAGS.get(team)
    if not code:
        return None

    if code in _FLAG_CACHE:
        return _FLAG_CACHE[code]

    try:
        flag_bytes = get_flag_bytes(code)
        if not flag_bytes:
            return None
        flag = Image.open(BytesIO(flag_bytes)).convert("RGBA")
        flag = flag.resize((34, 24))
        _FLAG_CACHE[code] = flag
        return flag
    except Exception:
        return None


def draw_flag_badge(img, draw, team, x, y, font):
    flag = load_flag_image(team)
    if flag is not None:
        img.paste(flag, (int(x), int(y)), flag)
        return

    draw.rounded_rectangle((x, y, x + 34, y + 24), radius=5, fill=hex_to_rgb("#e5e7eb"))
    draw_text_center(
        draw,
        (x, y, x + 34, y + 24),
        "?",
        font,
        hex_to_rgb("#64748b"),
    )


def load_export_logo(size):
    logo_path = find_logo_path()
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
        except Exception:
            logo = None
    else:
        logo = None

    if logo is None:
        logo = Image.new("RGBA", (size, size), (17, 24, 39, 255))
        logo_draw = ImageDraw.Draw(logo)
        logo_draw.ellipse((11, 11, size - 11, size - 11), fill=hex_to_rgb("#00e676"))
        logo_draw.text(
            (size / 2, size / 2 - 8),
            "FC",
            anchor="mm",
            font=load_font(max(18, size // 3), bold=True),
            fill=hex_to_rgb("#111827"),
        )
    else:
        logo = logo.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, size, size), radius=max(12, size // 4), fill=255)
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(logo, (0, 0), mask)
    return output


def build_export_image(fixtures_to_show, selected_round):
    EXPORT_W = 1920
    EXPORT_H = 1080
    BG = "#f3f6f9"
    LEFT_X = 55
    RIGHT_X = 985
    START_Y = 145
    CARD_W = 875
    CARD_H = 140
    GAP_Y = 18
    CARD_RADIUS = 10
    BORDER = 2
    INNER_PAD = 2
    DATE_W = 120
    TEAM_W = 515
    PROJ_W = 120
    CS_W = 120
    HEADER_H = 32
    ROW_H = 54
    FOOTER_DIVIDER_Y = 990
    FOOTER_TEXT_Y = 1022

    bg = BG
    fixture_count = len(fixtures_to_show)

    img = Image.new("RGB", (EXPORT_W, EXPORT_H), hex_to_rgb(bg))
    draw = ImageDraw.Draw(img)

    title_font = load_font(48, bold=True)
    subtitle_font = load_font(24)
    link_font = load_font(17)
    date_font = load_font(18, bold=True)
    time_font = load_font(17)
    team_font = load_font(25, bold=True)
    header_font = load_font(14, bold=True)
    metric_font = load_font(30, bold=True)
    footer_font = load_font(18)
    footer_bold = load_font(18, bold=True)
    badge_font = load_font(15, bold=True)

    logo = load_export_logo(90)
    img.paste(logo, (LEFT_X, 28), logo)

    header_text_x = LEFT_X + 112
    draw.text(
        (header_text_x, 38),
        "FPL Cartel World Cup Odds Dashboard",
        font=title_font,
        fill=hex_to_rgb("#111827"),
    )
    draw.text(
        (header_text_x, 92),
        "Join FPL Cartel on Sublaunch",
        font=link_font,
        fill=hex_to_rgb("#64748b"),
    )
    draw.text(
        (LEFT_X, 116),
        f"{selected_round} - Projected goals and clean sheet odds",
        font=subtitle_font,
        fill=hex_to_rgb("#4b5563"),
    )

    for index, row in enumerate(fixtures_to_show.itertuples(index=False)):
        if index >= 10:
            break

        col = 0 if index < 5 else 1
        row_position = index if index < 5 else index - 5

        x = LEFT_X if col == 0 else RIGHT_X
        y = START_Y + row_position * (CARD_H + GAP_Y)

        date_x = x
        team_x = x + DATE_W
        proj_x = x + DATE_W + TEAM_W
        cs_x = proj_x + PROJ_W
        card_right_x = x + CARD_W
        metric_right = x + CARD_W - BORDER - INNER_PAD
        metric_bottom = y + CARD_H - BORDER - INNER_PAD

        # Draw full card first, then square metric cells, then redraw the border last.
        draw.rounded_rectangle(
            (x, y, card_right_x, y + CARD_H),
            radius=CARD_RADIUS,
            fill=hex_to_rgb("#ffffff"),
        )
        draw.rectangle((date_x, y, team_x, y + CARD_H), fill=hex_to_rgb("#f5f7fa"))
        draw.rectangle((proj_x, y, card_right_x, y + HEADER_H), fill=hex_to_rgb("#f5f7fa"))

        draw_metric_cell(
            draw,
            (proj_x, y + HEADER_H, proj_x + PROJ_W, y + HEADER_H + ROW_H),
            format_projected_goals(row.home_xg),
            goal_cell_class(row.home_xg),
            metric_font,
        )
        draw_metric_cell(
            draw,
            (cs_x, y + HEADER_H, metric_right, y + HEADER_H + ROW_H),
            format_clean_sheet(row.home_cs),
            cs_cell_class(row.home_cs),
            metric_font,
        )
        draw_metric_cell(
            draw,
            (proj_x, y + HEADER_H + ROW_H, proj_x + PROJ_W, metric_bottom),
            format_projected_goals(row.away_xg),
            goal_cell_class(row.away_xg),
            metric_font,
        )
        draw_metric_cell(
            draw,
            (cs_x, y + HEADER_H + ROW_H, metric_right, metric_bottom),
            format_clean_sheet(row.away_cs),
            cs_cell_class(row.away_cs),
            metric_font,
        )

        for line_x in (team_x, proj_x, cs_x):
            draw.line(
                (line_x, y, line_x, y + CARD_H),
                fill=hex_to_rgb("#d8dee8"),
                width=2,
            )
        draw.line((team_x, y + HEADER_H + ROW_H, card_right_x, y + HEADER_H + ROW_H), fill=hex_to_rgb("#d8dee8"), width=2)
        draw.line((proj_x, y + HEADER_H, card_right_x, y + HEADER_H), fill=hex_to_rgb("#d8dee8"), width=2)

        draw_text_center(
            draw,
            (date_x + 8, y + 22, team_x - 8, y + 68),
            str(row.date),
            date_font,
            hex_to_rgb("#111827"),
        )
        draw_text_center(
            draw,
            (date_x + 8, y + 68, team_x - 8, y + 112),
            str(row.kickoff),
            time_font,
            hex_to_rgb("#4b5563"),
        )

        home_row_y = y + HEADER_H
        away_row_y = y + HEADER_H + ROW_H
        draw_flag_badge(img, draw, row.home_team, team_x + 24, home_row_y + 15, badge_font)
        draw_flag_badge(img, draw, row.away_team, team_x + 24, away_row_y + 15, badge_font)
        draw.text((team_x + 72, home_row_y + 13), str(row.home_team), font=team_font, fill=hex_to_rgb("#111827"))
        draw.text((team_x + 72, away_row_y + 13), str(row.away_team), font=team_font, fill=hex_to_rgb("#111827"))

        draw_text_center(draw, (proj_x, y, cs_x, y + HEADER_H), "PROJ", header_font, hex_to_rgb("#4b5563"))
        draw_text_center(draw, (cs_x, y, card_right_x, y + HEADER_H), "CS %", header_font, hex_to_rgb("#4b5563"))

        draw.rounded_rectangle(
            (x, y, card_right_x, y + CARD_H),
            radius=CARD_RADIUS,
            outline=hex_to_rgb("#d7dee8"),
            width=2,
        )

    draw.line((LEFT_X, FOOTER_DIVIDER_Y, EXPORT_W - LEFT_X, FOOTER_DIVIDER_Y), fill=hex_to_rgb("#d1d5db"), width=2)
    draw.text((LEFT_X, FOOTER_TEXT_Y), "Graphics by ", font=footer_font, fill=hex_to_rgb("#111827"))
    graphics_prefix_width = draw.textlength("Graphics by ", font=footer_font)
    draw.text(
        (LEFT_X + graphics_prefix_width, FOOTER_TEXT_Y),
        "FPL Cartel",
        font=footer_bold,
        fill=hex_to_rgb("#111827"),
    )
    source_text = "Source: live odds via The Odds API"
    source_width = draw.textlength(source_text, font=footer_font)
    draw.text(
        (EXPORT_W - LEFT_X - source_width, FOOTER_TEXT_Y),
        source_text,
        font=footer_font,
        fill=hex_to_rgb("#111827"),
    )

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


def build_export_image_bytes(fixtures_to_show, selected_round, export_page, total_export_pages):
    if USE_BROWSER_EXPORT:
        return build_export_with_playwright(
            fixtures_to_show,
            selected_round,
            export_page,
            total_export_pages,
        ).getvalue()

    return build_export_with_pil(
        fixtures_to_show,
        selected_round,
        export_page,
        total_export_pages,
    ).getvalue()


def build_export_with_playwright(fixtures_to_show, selected_round, export_page, total_export_pages):
    from playwright.sync_api import sync_playwright

    html = build_export_html(fixtures_to_show, selected_round, export_page, total_export_pages)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.set_content(html, wait_until="networkidle")
            png_bytes = page.screenshot(type="png", full_page=False)
            return BytesIO(png_bytes)
        finally:
            browser.close()


def build_export_with_pil(fixtures_to_show, selected_round, export_page, total_export_pages):
    export_title = selected_round
    if total_export_pages > 1:
        export_title = f"{selected_round} - Page {export_page} of {total_export_pages}"
    return build_export_image(fixtures_to_show, export_title)


def render_export_team_flag(team_name):
    flag_url = get_flag_url(team_name)
    if not flag_url:
        return '<span class="export-flag-fallback" aria-hidden="true">&#9917;</span>'
    return (
        f'<img class="export-flag" src="{escape(flag_url)}" '
        f'alt="{escape(str(team_name))} flag">'
    )


def render_export_fixture_card(row):
    return (
        '<article class="export-card">'
        '<div class="export-date">'
        f'<strong>{escape(str(row.date))}</strong>'
        f'<span>{escape(str(row.kickoff))}</span>'
        '</div>'
        '<div class="export-teams">'
        '<div class="export-team-row">'
        f'{render_export_team_flag(row.home_team)}'
        f'<span class="export-team-name">{escape(str(row.home_team))}</span>'
        '</div>'
        '<div class="export-team-row">'
        f'{render_export_team_flag(row.away_team)}'
        f'<span class="export-team-name">{escape(str(row.away_team))}</span>'
        '</div>'
        '</div>'
        '<div class="export-metric-col">'
        '<div class="export-metric-head">GOALS</div>'
        f'<div class="export-metric {goal_cell_class(row.home_xg)}">{format_projected_goals(row.home_xg)}</div>'
        f'<div class="export-metric {goal_cell_class(row.away_xg)}">{format_projected_goals(row.away_xg)}</div>'
        '</div>'
        '<div class="export-metric-col">'
        '<div class="export-metric-head">CS%</div>'
        f'<div class="export-metric {cs_cell_class(row.home_cs)}">{format_clean_sheet(row.home_cs)}</div>'
        f'<div class="export-metric {cs_cell_class(row.away_cs)}">{format_clean_sheet(row.away_cs)}</div>'
        '</div>'
        '</article>'
    )


def build_export_html(fixtures_to_show, selected_round, export_page, total_export_pages):
    cards = "\n".join(
        render_export_fixture_card(row)
        for row in fixtures_to_show.head(10).itertuples(index=False)
    )
    subtitle = (
        f"{selected_round} · Page {export_page} of {total_export_pages} · "
        "Projected goals and clean sheet odds"
    )

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=1920, initial-scale=1">
  <style>
    * {{
      box-sizing: border-box;
    }}

    html,
    body {{
      width: 1920px;
      height: 1080px;
      margin: 0;
      overflow: hidden;
      background: #f3f6f9;
      color: #111827;
      font-family: Arial, "Segoe UI", sans-serif;
    }}

    .export-canvas {{
      width: 1920px;
      height: 1080px;
      padding: 38px 60px 0;
      background: #f3f6f9;
      position: relative;
    }}

    .export-title {{
      margin: 0;
      font-size: 46px;
      line-height: 1.05;
      font-weight: 900;
      letter-spacing: 0;
    }}

    .export-subtitle {{
      margin: 12px 0 0;
      color: #4b5563;
      font-size: 24px;
      font-weight: 600;
    }}

    .export-grid {{
      position: absolute;
      left: 60px;
      top: 145px;
      width: 1800px;
      display: grid;
      grid-template-columns: 850px 850px;
      grid-template-rows: repeat(5, 135px);
      grid-auto-flow: column;
      gap: 18px 70px;
    }}

    .export-card {{
      width: 850px;
      height: 135px;
      display: grid;
      grid-template-columns: 115px 435px 145px 155px;
      overflow: hidden;
      background: #ffffff;
      border: 1px solid #d8dee8;
      border-radius: 12px;
      box-shadow: 0 10px 20px rgba(23, 32, 42, 0.08);
    }}

    .export-date {{
      background: #f5f7fa;
      border-right: 1px solid #d8dee8;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 5px;
      text-align: center;
      padding: 12px 8px;
    }}

    .export-date strong {{
      font-size: 18px;
      line-height: 1.12;
      font-weight: 900;
    }}

    .export-date span {{
      color: #4b5563;
      font-size: 17px;
      line-height: 1;
      font-weight: 800;
    }}

    .export-teams {{
      display: grid;
      grid-template-rows: 1fr 1fr;
      padding-top: 35px;
      min-width: 0;
    }}

    .export-team-row {{
      min-height: 50px;
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 0 18px;
      border-bottom: 1px solid #d8dee8;
      min-width: 0;
    }}

    .export-team-row:last-child {{
      border-bottom: 0;
    }}

    .export-flag {{
      width: 30px;
      height: 30px;
      object-fit: cover;
      border-radius: 50%;
      box-shadow: 0 0 0 1px #d8dee8;
      background: #f4f6f8;
      flex: 0 0 30px;
    }}

    .export-flag-fallback {{
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: #e5e7eb;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 15px;
      flex: 0 0 30px;
    }}

    .export-team-name {{
      font-size: 24px;
      font-weight: 900;
      line-height: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      min-width: 0;
    }}

    .export-metric-col {{
      display: grid;
      grid-template-rows: 35px 50px 50px;
      border-left: 1px solid #d8dee8;
    }}

    .export-metric-head {{
      min-height: 35px;
      display: grid;
      place-items: center;
      background: #f5f7fa;
      border-bottom: 1px solid #d8dee8;
      color: #4b5563;
      font-size: 16px;
      font-weight: 900;
      letter-spacing: 0;
    }}

    .export-metric {{
      display: grid;
      place-items: center;
      min-height: 50px;
      border-bottom: 1px solid #d8dee8;
      font-size: 30px;
      line-height: 1;
      font-weight: 900;
    }}

    .export-metric:last-child {{
      border-bottom: 0;
    }}

    .cell-dark-green {{
      background: #28531d;
      color: #ffffff;
    }}

    .cell-green {{
      background: #00e676;
      color: #064e3b;
    }}

    .cell-grey {{
      background: #dedede;
      color: #263238;
    }}

    .cell-light-red {{
      background: #ffe6e6;
      color: #b91c1c;
    }}

    .cell-red {{
      background: #ff0f4f;
      color: #ffffff;
    }}

    .cell-dark-red {{
      background: #8b002f;
      color: #ffffff;
    }}

    .cell-empty {{
      background: #f1f5f9;
      color: #64748b;
    }}

    .export-footer {{
      position: absolute;
      left: 60px;
      right: 60px;
      top: 990px;
      padding-top: 26px;
      border-top: 2px solid #d1d5db;
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: #111827;
      font-size: 18px;
    }}
  </style>
</head>
<body>
  <section class="export-canvas">
    <h1 class="export-title">FPL Cartel World Cup Odds Dashboard</h1>
    <p class="export-subtitle">{escape(subtitle)}</p>
    <main class="export-grid">
      {cards}
    </main>
    <footer class="export-footer">
      <div>Graphics by <strong>FPL Cartel</strong></div>
      <div>Source: live odds via <strong>The Odds API</strong></div>
    </footer>
  </section>
</body>
</html>"""


def render_team_flag(team_name):
    flag_url = get_flag_url(team_name)
    if not flag_url:
        return '<div class="team-flag-fallback" aria-hidden="true">&#9917;</div>'
    return (
        f'<img class="team-flag" src="{escape(flag_url)}" '
        f'alt="{escape(team_name)} flag" '
        'loading="lazy" decoding="async" '
        'onerror="this.style.display=\'none\'; '
        'this.nextElementSibling.style.display=\'flex\';">'
        '<div class="team-flag-fallback" style="display:none;" '
        'aria-hidden="true">&#9917;</div>'
    )


def render_fixture_card(row):
    return (
        '<article class="fixture-card">'
        '<div class="date-block">'
        f"<strong>{escape(row.date)}</strong><span>{escape(row.kickoff)}</span>"
        "</div>"
        '<div class="fixture-teams">'
        '<div class="team-row">'
        f"{render_team_flag(row.home_team)}"
        f'<div class="team-name">{escape(row.home_team)}</div>'
        "</div>"
        '<div class="team-row">'
        f"{render_team_flag(row.away_team)}"
        f'<div class="team-name">{escape(row.away_team)}</div>'
        "</div></div>"
        '<div class="projection-col">'
        '<div class="metric-head">Proj goals</div>'
        f'<div class="metric-cell {goal_cell_class(row.home_xg)}">{format_projected_goals(row.home_xg)}</div>'
        f'<div class="metric-cell {goal_cell_class(row.away_xg)}">{format_projected_goals(row.away_xg)}</div>'
        "</div>"
        '<div class="clean-col">'
        '<div class="metric-head">Clean sheet</div>'
        f'<div class="metric-cell {cs_cell_class(row.home_cs)}">{format_clean_sheet(row.home_cs)}</div>'
        f'<div class="metric-cell {cs_cell_class(row.away_cs)}">{format_clean_sheet(row.away_cs)}</div>'
        "</div>"
        "</article>"
    )


def render_fixture_groups(fixtures):
    groups_html = []
    for date, date_fixtures in fixtures.groupby("date", sort=False):
        cards = "\n".join(
            render_fixture_card(row) for row in date_fixtures.itertuples(index=False)
        )
        groups_html.append(
            '<section class="date-group">'
            f'<h2 class="date-heading">{escape(str(date))}</h2>'
            f'<main class="fixture-grid">{cards}</main>'
            "</section>"
        )
    return "\n".join(groups_html)


def render_top_team_value_cell(cell, metric_key):
    if not cell:
        return '<td class="top-round-cell top-round-empty">-</td>'

    value = cell[metric_key]
    value_text = (
        format_projected_goals(value)
        if metric_key == "projected_goals"
        else format_clean_sheet(value)
    )
    return (
        '<td class="top-round-cell">'
        f'<span class="top-opponent">{escape(str(cell["opponent"]))}</span>'
        f'<strong>{escape(value_text)}</strong>'
        "</td>"
    )


def render_top_teams_table(fixtures, metric_key):
    rows = build_top_team_round_table(fixtures, metric_key)
    if not rows:
        return '<div class="empty-note">No team ranking data available yet.</div>'

    body_rows = []
    for index, row in enumerate(rows, start=1):
        round_cells = "".join(
            render_top_team_value_cell(row["rounds"].get(round_name), metric_key)
            for round_name in ROUND_TABLE_COLUMNS
        )
        body_rows.append(
            "<tr>"
            '<td class="top-team-cell">'
            f'<span class="top-rank">{index}</span>'
            f"{render_team_flag(row['team'])}"
            f'<span>{escape(str(row["team"]))}</span>'
            "</td>"
            f"{round_cells}"
            "</tr>"
        )

    return (
        '<div class="top-teams-table-wrap">'
        '<table class="top-teams-table">'
        "<thead><tr>"
        "<th>Team</th>"
        "<th>Round 1</th>"
        "<th>Round 2</th>"
        "<th>Round 3</th>"
        "</tr></thead>"
        f'<tbody>{"".join(body_rows)}</tbody>'
        "</table>"
        "</div>"
    )


def render_top_teams_section(fixtures):
    st.markdown(
        """
        <section class="top-teams-section">
          <div class="section-kicker">FPL Cartel model</div>
          <h2>Top Teams by Round</h2>
          <p>Opponent and model-estimated value for each team's group-stage round.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    goals_tab, cs_tab = st.tabs(["Projected Goals", "Clean Sheet %"])
    with goals_tab:
        st.markdown(
            render_top_teams_table(fixtures, "projected_goals"),
            unsafe_allow_html=True,
        )
    with cs_tab:
        st.markdown(
            render_top_teams_table(fixtures, "clean_sheet_pct"),
            unsafe_allow_html=True,
        )


def render_export_area(fixtures):
    return (
        '<section class="export-area">'
        f"{render_fixture_groups(fixtures)}"
        '<div class="export-footer">'
        "<div>Graphics by <strong>FPL Cartel</strong></div>"
        "<div>Source: live odds via <strong>The Odds API</strong></div>"
        "</div>"
        "</section>"
    )


def render_desktop_dashboard():
    desktop_styles()

    raw_api_response, api_error, _api_status_code = fetch_world_cup_odds()
    live_fixtures = parse_odds_response(raw_api_response)
    using_live_data = not live_fixtures.empty

    status_text = "Live odds via The Odds API" if using_live_data else "Sample fallback data"
    display_fixtures = live_fixtures if using_live_data else SAMPLE_FIXTURES
    st.markdown(render_brand_header(), unsafe_allow_html=True)

    if api_error:
        st.warning(f"Could not fetch live odds from The Odds API: {api_error}")

    if not using_live_data:
        st.markdown(f'<div class="empty-note">{NO_LIVE_ODDS_MESSAGE}</div>', unsafe_allow_html=True)

    fixture_options = display_fixtures["fixture_set"].drop_duplicates().tolist()
    control_cols = st.columns([1.2, 1.1, 1.2])

    with control_cols[0]:
        fixture_set = st.segmented_control(
            "Fixture set",
            fixture_options,
            default=fixture_options[0],
        )

    available_rounds = (
        display_fixtures.loc[display_fixtures["fixture_set"] == fixture_set, "round"]
        .drop_duplicates()
        .tolist()
    )
    round_options = sorted(available_rounds, key=round_sort_key)
    fixture_records = (
        display_fixtures.loc[display_fixtures["fixture_set"] == fixture_set]
        .to_dict("records")
    )
    default_round = get_current_round(fixture_records)
    default_round_index = (
        round_options.index(default_round)
        if default_round in round_options
        else 0
    )

    with control_cols[1]:
        selected_round = st.selectbox(
            "Round",
            round_options,
            index=default_round_index,
        )

    filtered = display_fixtures[display_fixtures["fixture_set"] == fixture_set]
    filtered = filtered[filtered["round"] == selected_round]

    with control_cols[2]:
        export_page_size = 10
        total_export_pages = max(1, math.ceil(len(filtered) / export_page_size))
        export_page_options = [
            f"Export page {page_number}"
            for page_number in range(1, total_export_pages + 1)
        ]
        if total_export_pages > 1:
            selected_export_page_label = st.selectbox(
                "Export page",
                export_page_options,
            )
            selected_export_page = export_page_options.index(selected_export_page_label) + 1
        else:
            selected_export_page = 1
        export_start = (selected_export_page - 1) * export_page_size
        export_end = export_start + export_page_size
        export_fixtures = filtered.iloc[export_start:export_end]
        st.download_button(
            "Download image",
            data=build_export_image_bytes(
                export_fixtures,
                selected_round,
                selected_export_page,
                total_export_pages,
            ),
            file_name=(
                "fpl-cartel-world-cup-odds-"
                f"{selected_round.lower().replace(' ', '-')}-"
                f"page-{selected_export_page}.png"
            ),
            mime="image/png",
        )

    if filtered.empty:
        st.markdown(
            '<div class="empty-note">No fixtures available for this selection.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(render_export_area(filtered), unsafe_allow_html=True)

    top_team_fixtures = display_fixtures[
        display_fixtures["fixture_set"] == fixture_set
    ]
    render_top_teams_section(top_team_fixtures)

    with st.expander("Debug API response", expanded=False):
        if api_error:
            st.error(api_error)
        st.json(raw_api_response)


is_mobile = view == "mobile"

if is_mobile:
    render_mobile_dashboard()
else:
    render_desktop_dashboard()
