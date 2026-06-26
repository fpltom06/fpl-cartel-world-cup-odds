import os
import math
import base64
import mimetypes
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
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
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4/sports"
FPL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"
FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
MARKETS = "h2h,totals,spreads"
COMPETITIONS = {
    "World Cup": {
        "sport_key": "soccer_fifa_world_cup",
        "neutral": True,
    },
    "Premier League": {
        "sport_key": "soccer_epl",
        "neutral": False,
    },
}
NO_LIVE_ODDS_MESSAGE = (
    "No live betting odds available yet. This usually happens when fixtures "
    "are too far away or markets are not open."
)
PINNACLE_UNAVAILABLE_MESSAGE = "Pinnacle odds unavailable"
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


def make_fixture_id(commence_time, home_team, away_team):
    return f"{commence_time or 'tbd'}::{home_team}::{away_team}"

st.set_page_config(
    page_title="FPL Cartel Odds Dashboard",
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


def format_last_updated(timestamp):
    if not timestamp:
        return ""

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    return f"Last updated: {timestamp.strftime('%d %b %Y %H:%M UTC')}"


def competition_title(competition_name):
    return f"FPL Cartel {competition_name} Odds Dashboard"


def render_brand_header(competition_name="World Cup"):
    logo_src = get_logo_src()
    return f"""
    <div class="brand-header">
      <img src="{logo_src}" class="brand-logo" alt="FPL Cartel logo">
      <div>
        <h1>{escape(competition_title(competition_name))}</h1>
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
        ("Algeria", "Austria"): "Round 3",
        ("Austria", "Algeria"): "Round 3",
        ("Jordan", "Argentina"): "Round 3",
        ("Argentina", "Jordan"): "Round 3",
        ("South Africa", "Canada"): "Round of 32",
        ("Canada", "South Africa"): "Round of 32",
        ("Brazil", "Japan"): "Round of 32",
        ("Japan", "Brazil"): "Round of 32",
        ("Netherlands", "Morocco"): "Round of 32",
        ("Morocco", "Netherlands"): "Round of 32",
    }
    override = overrides.get((home_team, away_team))
    if override:
        return override

    if dt.month == 6 and dt.day <= 18:
        return "Round 1"
    if dt.month == 6 and 19 <= dt.day <= 24:
        return "Round 2"
    if dt.month == 6 and 25 <= dt.day <= 27:
        return "Round 3"
    if dt.month == 6 and dt.day >= 28:
        return "Round of 32"
    return "Knockouts"


def mobile_round_sort_key(round_name):
    return round_sort_key(round_name)


def mobile_extract_market(bookmaker, market_key):
    for market in bookmaker.get("markets", []):
        if market.get("key") == market_key:
            return market
    return {}


def implied_prob(decimal_odds):
    try:
        odds = float(decimal_odds)
    except (TypeError, ValueError):
        return None
    if odds <= 1:
        return None
    return 1 / odds


def normalize_probs(probs):
    clean_probs = [prob for prob in probs if prob is not None and prob > 0]
    total = sum(clean_probs)
    if total <= 0:
        return []
    return [prob / total for prob in clean_probs]


def is_pinnacle_bookmaker(bookmaker):
    key = str(bookmaker.get("key", "")).lower()
    title = str(bookmaker.get("title", "")).lower()
    return key == "pinnacle" or title == "pinnacle"


def find_pinnacle_bookmaker(event):
    for bookmaker in event.get("bookmakers", []):
        if is_pinnacle_bookmaker(bookmaker):
            return bookmaker
    return None


def extract_h2h_probabilities(bookmaker, home_team, away_team):
    market = extract_market(bookmaker, "h2h")
    outcomes = market.get("outcomes", [])
    probs = []
    names = []
    for outcome in outcomes:
        name = outcome.get("name")
        prob = implied_prob(outcome.get("price"))
        if name and prob is not None:
            names.append(name)
            probs.append(prob)

    fair_probs = normalize_probs(probs)
    if not fair_probs:
        return None

    return {
        names[index]: fair_probs[index]
        for index in range(min(len(names), len(fair_probs)))
    }


def apply_h2h_calibration(home_goals, away_goals, bookmaker, home_team, away_team):
    h2h_probs = extract_h2h_probabilities(bookmaker, home_team, away_team)
    if not h2h_probs:
        return home_goals, away_goals, False

    home_prob = h2h_probs.get(home_team)
    away_prob = h2h_probs.get(away_team)
    if home_prob is None or away_prob is None:
        return home_goals, away_goals, False

    market_edge = home_prob - away_prob
    model_edge = math.tanh((home_goals - away_goals) / 1.5) * 0.45
    adjustment = max(-0.08, min(0.08, (market_edge - model_edge) * 0.08))
    return (
        max(0.05, home_goals + adjustment),
        max(0.05, away_goals - adjustment),
        True,
    )


def project_goals_from_event(event):
    home_team = event.get("home_team")
    away_team = event.get("away_team")
    debug = {
        "bookmaker_used": "Pinnacle",
        "total_line": None,
        "spread_line": None,
        "h2h_used": False,
        "btts_used": False,
        "correct_score_used": False,
    }
    if not home_team:
        return None, None, debug

    bookmaker = find_pinnacle_bookmaker(event)
    if not bookmaker:
        debug["bookmaker_used"] = "Unavailable"
        return None, None, debug

    total_line = extract_total(bookmaker)
    home_spread = extract_spread(bookmaker, home_team)
    debug["total_line"] = total_line
    debug["spread_line"] = home_spread
    debug["h2h_used"] = False

    home_goals, away_goals = calculate_team_goal_projections(total_line, home_spread)
    if home_goals is None or away_goals is None:
        return None, None, debug

    home_goals, away_goals, h2h_used = apply_h2h_calibration(
        home_goals,
        away_goals,
        bookmaker,
        home_team,
        away_team,
    )
    debug["h2h_used"] = h2h_used
    return home_goals, away_goals, debug


def mobile_extract_total_and_spread(event):
    home_team = event.get("home_team")
    if not home_team:
        return None, None

    bookmaker = find_pinnacle_bookmaker(event)
    if not bookmaker:
        return None, None

    return extract_total(bookmaker), extract_spread(bookmaker, home_team)


def mobile_goal_projection(total_line, home_spread):
    if total_line is None or home_spread is None:
        return None, None

    # World Cup fixtures are neutral: home/away only means API fixture order.
    ordered_home_goals = (total_line - home_spread) / 2
    ordered_away_goals = total_line - ordered_home_goals
    return ordered_home_goals, ordered_away_goals


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


@st.cache_data(ttl=300, show_spinner=False)
def fetch_odds(sport_key):
    api_key = ODDS_API_KEY
    if not api_key or api_key == "your_api_key_here":
        return [], "Missing Odds API key.", None, None

    params = {
        "apiKey": api_key,
        "regions": "uk,eu",
        "markets": MARKETS,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }

    try:
        response = requests.get(
            f"{ODDS_API_BASE_URL}/{sport_key}/odds",
            params=params,
            timeout=12,
        )
        status_code = response.status_code
        if status_code != 200:
            return [], f"The Odds API returned status code {status_code}.", status_code, None
        return response.json(), None, status_code, datetime.now(timezone.utc)
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return [], str(exc), status_code, None
    except ValueError:
        return [], "The Odds API returned a response that was not valid JSON.", None, None


def fetch_world_cup_odds_mobile():
    payload, error, _status, updated = fetch_odds(COMPETITIONS["World Cup"]["sport_key"])
    return payload, updated, error


def mobile_parse_odds_response(payload, competition_name="World Cup"):
    rows = []
    for event in payload or []:
        commence_time = event.get("commence_time")
        dt = mobile_parse_datetime(commence_time)
        home_team = event.get("home_team", "Home team")
        away_team = event.get("away_team", "Away team")
        home_goals, away_goals, debug = project_goals_from_event(event)
        total_line = debug["total_line"]
        home_spread = debug["spread_line"]
        home_cs = round(math.exp(-away_goals) * 100) if away_goals is not None else None
        away_cs = round(math.exp(-home_goals) * 100) if home_goals is not None else None
        odds_note = (
            PINNACLE_UNAVAILABLE_MESSAGE
            if total_line is None or home_spread is None
            else ""
        )

        rows.append(
            {
                "fixture_id": event.get("id")
                or make_fixture_id(commence_time, home_team, away_team),
                "Date": dt.strftime("%a %d %b") if dt.year < 9999 else "TBD",
                "Time": dt.strftime("%H:%M") if dt.year < 9999 else "TBD",
                "commence_time": commence_time,
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
                "odds_note": odds_note,
                "round": (
                    mobile_round_for_fixture(home_team, away_team, dt)
                    if competition_name == "World Cup"
                    else "Premier League"
                ),
                "fixture_set": competition_name,
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
    rows["odds_note"] = ""
    return rows


def render_mobile_card(row):
    home = str(row["Home"])
    away = str(row["Away"])
    note = str(row.get("odds_note", "") or "")
    note_html = (
        f'<div class="mobile-odds-note">{escape(note)}</div>'
        if note
        else ""
    )
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
        f"{note_html}"
        "</article>"
    )


def render_mobile_cards(fixtures):
    cards = "\n".join(render_mobile_card(row) for row in fixtures.to_dict("records"))
    return f'<section class="mobile-card-list">{cards}</section>'


def render_mobile_top_team_card(row, metric_key, selected_rounds):
    round_cells = []
    for round_name in selected_rounds:
        cell = row["rounds"].get(round_name)
        if not cell:
            round_cells.append(
                '<div class="mobile-top-team-round">'
                f'<span>{escape(ROUND_TO_MD.get(round_name, round_name))}</span>'
                "<strong>-</strong>"
                "</div>"
            )
            continue

        value = cell[metric_key]
        value_text = format_leaderboard_value(value, metric_key)
        round_cells.append(
            '<div class="mobile-top-team-round">'
            f'<span>{escape(ROUND_TO_MD.get(round_name, round_name))}</span>'
            f'<em>{escape(str(cell["opponent"]))}</em>'
            f'<strong>{escape(value_text)}</strong>'
            "</div>"
        )

    return (
        '<article class="mobile-top-team-card">'
        '<div class="mobile-top-team-name">'
        f'<span class="flag-emoji">{get_team_emoji(row["team"])}</span>'
        f'<strong>{escape(str(row["team"]))}</strong>'
        + (
            f'<b>{escape(format_leaderboard_value(row["total"], metric_key))}</b>'
            if show_leaderboard_total(metric_key)
            else ""
        )
        + "</div>"
        '<div class="mobile-top-team-rounds">'
        f'{"".join(round_cells)}'
        "</div>"
        "</article>"
    )


def render_mobile_top_teams(fixtures, metric_key, selected_rounds):
    rows = build_leaderboard_rows(fixtures, metric_key, selected_rounds)
    if not rows:
        return '<div class="mobile-top-empty">No model data available yet.</div>'

    cards = "\n".join(
        render_mobile_top_team_card(row, metric_key, selected_rounds) for row in rows
    )
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

            .source-note {
                display: block;
                max-width: 430px;
                margin: -0.35rem auto 0.8rem;
                color: #64748b;
                font-size: 0.82rem;
                font-weight: 800;
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

            .mobile-odds-note {
                grid-column: 1 / -1;
                padding: 0.42rem 0.55rem;
                border-top: 1px solid #d8dee8;
                background: #fff7ed;
                color: #9a3412;
                font-size: 0.72rem;
                font-weight: 850;
                text-align: center;
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
                min-width: 0;
                flex: 1;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .mobile-top-team-name b {
                color: #0f7a45;
                font-size: 1rem;
                font-weight: 950;
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
    selected_competition = st.selectbox(
        "Competition",
        list(COMPETITIONS.keys()),
        key="mobile_competition",
    )
    competition_config = COMPETITIONS[selected_competition]
    mobile_neutral_label = "On" if competition_config["neutral"] else "Off"
    st.segmented_control(
        "Neutral venue",
        [mobile_neutral_label],
        default=mobile_neutral_label,
        key=f"{selected_competition}_mobile_neutral_venue",
    )
    st.markdown(
        render_brand_header(selected_competition),
        unsafe_allow_html=True,
    )
    mobile_api_response, mobile_api_error, _mobile_status, mobile_last_updated = fetch_odds(
        competition_config["sport_key"]
    )
    mobile_updated_text = format_last_updated(mobile_last_updated)
    mobile_source_note = (
        "Live odds via The Odds API &middot; Pinnacle only"
        + (f"<br>{escape(mobile_updated_text)}" if mobile_updated_text else "")
    )
    st.markdown(
        f'<div class="source-note">{mobile_source_note}</div>',
        unsafe_allow_html=True,
    )

    live_fixtures = mobile_parse_odds_response(mobile_api_response, selected_competition)
    if mobile_api_error:
        st.error("Live odds unavailable: API request failed. Check markets/API plan.")
        st.caption(f"Details: {mobile_api_error}")
        return
    if live_fixtures.empty:
        st.markdown(f'<div class="mobile-top-empty">{NO_LIVE_ODDS_MESSAGE}</div>', unsafe_allow_html=True)
        return
    if selected_competition == "Premier League":
        live_fixtures = add_premier_league_gameweeks(live_fixtures)
    fixtures = live_fixtures

    if selected_competition == "World Cup":
        round_options = sorted(
            fixtures["round"].drop_duplicates().tolist(),
            key=mobile_round_sort_key,
        )
        selected_round = st.selectbox("Round", round_options)
        fixtures_to_show = fixtures[fixtures["round"] == selected_round]
    else:
        gw_options = gameweek_options()
        default_gw = default_gameweek(fixtures)
        selected_gameweek = st.selectbox(
            "Gameweek",
            gw_options,
            index=gw_options.index(default_gw) if default_gw in gw_options else 0,
        )
        fixtures_to_show = filter_by_gameweek(fixtures, selected_gameweek)
        if fixtures_to_show.empty and selected_gameweek.startswith("GW"):
            st.warning(
                f"No {selected_gameweek} matches could be linked to FPL fixtures. "
                "Use All priced fixtures to inspect returned odds."
            )
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
          <p>Live odds via The Odds API &middot; Pinnacle only</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if selected_competition == "World Cup":
        mobile_leaderboard_range = st.selectbox(
            "Leaderboard range",
            list(LEADERBOARD_RANGES.keys()),
            key=f"{selected_competition}_mobile_leaderboard_range",
        )
        mobile_selected_rounds = LEADERBOARD_RANGES[mobile_leaderboard_range]
        mobile_leaderboard_fixtures = fixtures
    else:
        mobile_selected_rounds = [selected_gameweek]
        mobile_leaderboard_fixtures = fixtures_to_show.copy()
        mobile_leaderboard_fixtures["round"] = selected_gameweek
    mobile_goal_tab, mobile_cs_tab = st.tabs(["Projected Goals", "Clean Sheet %"])
    with mobile_goal_tab:
        st.markdown(
            render_mobile_top_teams(
                mobile_leaderboard_fixtures,
                "projected_goals",
                mobile_selected_rounds,
            ),
            unsafe_allow_html=True,
        )
    with mobile_cs_tab:
        st.markdown(
            render_mobile_top_teams(
                mobile_leaderboard_fixtures,
                "clean_sheet_pct",
                mobile_selected_rounds,
            ),
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

        .source-note {
            display: inline-flex;
            align-items: center;
            margin: -0.35rem 0 1rem;
            color: #64748b;
            font-size: 0.9rem;
            font-weight: 800;
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

        .fixture-card-wrap {
            display: grid;
            gap: 0.35rem;
        }

        .fixture-note {
            padding: 0.48rem 0.7rem;
            border: 1px solid #fed7aa;
            border-radius: 9px;
            background: #fff7ed;
            color: #9a3412;
            font-size: 0.78rem;
            font-weight: 850;
            text-align: center;
            box-shadow: 0 6px 14px rgba(23, 32, 42, 0.04);
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
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.2rem;
            padding: 0.65rem 0.45rem;
            font-weight: 800;
            font-size: 22px;
        }

        .metric-value {
            line-height: 1;
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
            width: 72px;
            text-align: center;
        }

        .top-teams-table th:nth-child(2) {
            width: 28%;
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

        .top-rank-cell {
            text-align: center;
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
            margin: 0 auto;
        }

        .top-round-cell {
            min-height: 54px;
            text-align: center;
        }

        .top-round-cell .top-opponent {
            display: block;
            color: #111827;
            font-size: 0.88rem;
            font-weight: 800;
            line-height: 1.15;
            overflow-wrap: anywhere;
            word-break: break-word;
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

        .top-total-cell strong {
            color: #0f7a45;
            font-size: 1.3rem;
            font-weight: 950;
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


def fetch_world_cup_odds():
    return fetch_odds(COMPETITIONS["World Cup"]["sport_key"])


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


ROUND_ORDER = [
    "Round 1",
    "Round 2",
    "Round 3",
    "Round of 32",
    "Round of 16",
    "Quarter-finals",
    "Semi-finals",
    "Final",
]
ROUND_ORDER_INDEX = {
    round_name: index for index, round_name in enumerate(ROUND_ORDER)
}

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
    ("Algeria", "Austria"): "Round 3",
    ("Austria", "Algeria"): "Round 3",
    ("Jordan", "Argentina"): "Round 3",
    ("Argentina", "Jordan"): "Round 3",
    ("South Africa", "Canada"): "Round of 32",
    ("Canada", "South Africa"): "Round of 32",
    ("Brazil", "Japan"): "Round of 32",
    ("Japan", "Brazil"): "Round of 32",
    ("Netherlands", "Morocco"): "Round of 32",
    ("Morocco", "Netherlands"): "Round of 32",
}


def get_round_for_fixture(home_team, away_team, dt):
    override = ROUND_OVERRIDES.get((home_team, away_team))
    if override:
        return override

    if dt.month == 6 and dt.day <= 18:
        return "Round 1"

    if dt.month == 6 and 19 <= dt.day <= 24:
        return "Round 2"

    if dt.month == 6 and 25 <= dt.day <= 27:
        return "Round 3"

    if dt.month == 6 and dt.day >= 28:
        return "Round of 32"

    return "Knockouts"


def round_sort_key(round_name):
    return ROUND_ORDER_INDEX.get(str(round_name), 99)


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


PL_TEAM_ALIASES = {
    "afc bournemouth": "bournemouth",
    "bournemouth": "bournemouth",
    "brighton": "brighton",
    "brighton and hove albion": "brighton",
    "brighton hove albion": "brighton",
    "man city": "manchester city",
    "manchester city": "manchester city",
    "man utd": "manchester united",
    "man united": "manchester united",
    "manchester united": "manchester united",
    "newcastle": "newcastle united",
    "newcastle united": "newcastle united",
    "nottingham forest": "nottingham forest",
    "nottm forest": "nottingham forest",
    "nott m forest": "nottingham forest",
    "spurs": "tottenham hotspur",
    "tottenham": "tottenham hotspur",
    "tottenham hotspur": "tottenham hotspur",
    "west ham": "west ham united",
    "west ham united": "west ham united",
    "wolves": "wolverhampton wanderers",
    "wolverhampton": "wolverhampton wanderers",
    "wolverhampton wanderers": "wolverhampton wanderers",
}


TEAM_NAME_ALIASES = {
    "Man United": "Manchester United",
    "Manchester Utd": "Manchester United",
    "Man Utd": "Manchester United",
    "Spurs": "Tottenham Hotspur",
    "Tottenham": "Tottenham Hotspur",
    "Nott'm Forest": "Nottingham Forest",
    "Nottingham Forest": "Nottingham Forest",
    "Brighton": "Brighton & Hove Albion",
    "Wolves": "Wolverhampton Wanderers",
    "West Ham": "West Ham United",
    "Newcastle": "Newcastle United",
    "Leeds": "Leeds United",
    "Man City": "Manchester City",
    "Bournemouth": "AFC Bournemouth",
}


def normalize_pl_team_name(team_name):
    canonical = TEAM_NAME_ALIASES.get(str(team_name or "").strip(), team_name)
    clean = str(canonical or "").lower()
    clean = clean.replace("&", " and ")
    clean = re.sub(r"[^a-z0-9]+", " ", clean).strip()
    clean = re.sub(r"\s+", " ", clean)
    return PL_TEAM_ALIASES.get(clean, clean)


def pl_team_similarity(left, right):
    return SequenceMatcher(
        None,
        normalize_pl_team_name(left),
        normalize_pl_team_name(right),
    ).ratio()


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_fpl_fixture_schedule():
    try:
        bootstrap = requests.get(FPL_BOOTSTRAP_URL, timeout=12)
        bootstrap.raise_for_status()
        fixtures_response = requests.get(FPL_FIXTURES_URL, timeout=12)
        fixtures_response.raise_for_status()
        teams = {
            team["id"]: team["name"]
            for team in bootstrap.json().get("teams", [])
        }
        rows = []
        for fixture in fixtures_response.json():
            kickoff = fixture.get("kickoff_time")
            gameweek = fixture.get("event")
            if not kickoff or not gameweek:
                continue
            kickoff_dt = parse_commence_datetime(kickoff)
            home_team = teams.get(fixture.get("team_h"), "")
            away_team = teams.get(fixture.get("team_a"), "")
            rows.append(
                {
                    "gameweek": int(gameweek),
                    "kickoff_dt": kickoff_dt,
                    "fixture_date": kickoff_dt.date().isoformat(),
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_norm": normalize_pl_team_name(home_team),
                    "away_norm": normalize_pl_team_name(away_team),
                }
            )
        return pd.DataFrame(rows)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return pd.DataFrame(
            columns=[
                "gameweek",
                "kickoff_dt",
                "fixture_date",
                "home_team",
                "away_team",
                "home_norm",
                "away_norm",
            ]
        )


def match_premier_league_fixture(fixture, schedule):
    home_team = fixture.get("home_team") or fixture.get("Home")
    away_team = fixture.get("away_team") or fixture.get("Away")
    kickoff_dt = fixture.get("commence_time_dt")
    if kickoff_dt is None or schedule.empty:
        return None

    best_match = None
    best_score = 0
    for candidate in schedule.to_dict("records"):
        day_gap = abs((kickoff_dt.date() - candidate["kickoff_dt"].date()).days)
        if day_gap > 2:
            continue

        home_score = pl_team_similarity(home_team, candidate["home_team"])
        away_score = pl_team_similarity(away_team, candidate["away_team"])
        team_score = (home_score + away_score) / 2
        date_score = max(0, 1 - (day_gap / 2))
        score = (team_score * 0.85) + (date_score * 0.15)
        if score > best_score:
            best_score = score
            best_match = candidate

    if not best_match or best_score < 0.78:
        return None

    return {
        "gameweek": int(best_match["gameweek"]),
        "fpl_event": (
            f'GW{int(best_match["gameweek"])}: '
            f'{best_match["home_team"]} vs {best_match["away_team"]}'
        ),
        "confidence": round(best_score * 100),
    }


def add_premier_league_gameweeks(fixtures):
    if fixtures.empty:
        fixtures["gameweek"] = pd.Series(dtype="float")
        fixtures["gameweek_label"] = pd.Series(dtype="object")
        fixtures["matched_fpl_event"] = pd.Series(dtype="object")
        fixtures["match_confidence"] = pd.Series(dtype="float")
        return fixtures

    schedule = fetch_fpl_fixture_schedule()
    fixtures = fixtures.copy()
    fixtures["gameweek"] = None
    fixtures["gameweek_label"] = "Unmatched / Upcoming"
    fixtures["matched_fpl_event"] = "Unmatched / Upcoming"
    fixtures["match_confidence"] = 0
    if schedule.empty:
        return fixtures

    gameweeks = []
    labels = []
    events = []
    confidences = []
    for fixture in fixtures.to_dict("records"):
        match = match_premier_league_fixture(fixture, schedule)
        if match:
            label = f"GW{match['gameweek']}"
            gameweeks.append(match["gameweek"])
            labels.append(label)
            events.append(match["fpl_event"])
            confidences.append(match["confidence"])
        else:
            gameweeks.append(None)
            labels.append("Unmatched / Upcoming")
            events.append("Unmatched / Upcoming")
            confidences.append(0)

    fixtures["gameweek"] = gameweeks
    fixtures["gameweek_label"] = labels
    fixtures["matched_fpl_event"] = events
    fixtures["match_confidence"] = confidences
    return fixtures


def gameweek_options():
    return ["All priced fixtures"] + [
        f"GW{gameweek}" for gameweek in range(1, 39)
    ] + ["Unmatched / Upcoming"]


def default_gameweek(fixtures):
    now = datetime.now(timezone.utc)
    for gameweek in range(1, 39):
        gw_fixtures = fixtures[fixtures["gameweek"] == gameweek]
        if not gw_fixtures.empty and any(gw_fixtures["commence_time_dt"] > now):
            return f"GW{gameweek}"
    available = fixtures["gameweek"].dropna().astype(int).sort_values().tolist()
    return f"GW{available[0]}" if available else "GW1"


def filter_by_gameweek(fixtures, selected_gameweek):
    if selected_gameweek == "All priced fixtures":
        return fixtures
    if selected_gameweek == "Unmatched / Upcoming":
        return fixtures[fixtures["gameweek"].isna()]
    try:
        gameweek = int(str(selected_gameweek).replace("GW", ""))
    except ValueError:
        return fixtures.iloc[0:0]
    return fixtures[fixtures["gameweek"] == gameweek]


SAMPLE_FIXTURES["round"] = SAMPLE_FIXTURES.apply(
    lambda row: get_round_for_fixture(
        row["home_team"],
        row["away_team"],
        row["commence_time_dt"],
    ),
    axis=1,
)
SAMPLE_FIXTURES["fixture_id"] = SAMPLE_FIXTURES.apply(
    lambda row: make_fixture_id(
        row["commence_time_dt"].isoformat(),
        row["home_team"],
        row["away_team"],
    ),
    axis=1,
)
SAMPLE_FIXTURES["odds_note"] = ""


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


def extract_over_under_probabilities(bookmaker):
    market = extract_market(bookmaker, "totals")
    names = []
    probs = []
    for outcome in market.get("outcomes", []):
        prob = implied_prob(outcome.get("price"))
        name = outcome.get("name")
        if prob is not None and name:
            names.append(name)
            probs.append(prob)

    fair_probs = normalize_probs(probs)
    return {
        names[index]: fair_probs[index]
        for index in range(min(len(names), len(fair_probs)))
    }


def extract_total(bookmaker):
    market = extract_market(bookmaker, "totals")
    _fair_over_under_probs = extract_over_under_probabilities(bookmaker)
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


def extract_total_and_home_spread(event):
    home_team = event.get("home_team")
    if not home_team:
        return None, None

    bookmaker = find_pinnacle_bookmaker(event)
    if not bookmaker:
        return None, None

    return extract_total(bookmaker), extract_spread(bookmaker, home_team)


def extract_total_line(event):
    total_line, _home_spread = extract_total_and_home_spread(event)
    return total_line


def extract_home_spread(event):
    _total_line, home_spread = extract_total_and_home_spread(event)
    return home_spread


def calculate_team_goal_projections(total_line, home_spread):
    if total_line is None or home_spread is None:
        return None, None

    # World Cup fixtures are neutral: home/away only means fixture ordering.
    ordered_home_projected_goals = (total_line - home_spread) / 2
    ordered_away_projected_goals = total_line - ordered_home_projected_goals
    return ordered_home_projected_goals, ordered_away_projected_goals


def calculate_clean_sheet_percent(opponent_projected_goals):
    if opponent_projected_goals is None:
        return None
    return round(math.exp(-opponent_projected_goals) * 100)


def parse_odds_response(payload, competition_name="World Cup"):
    rows = []
    for event in payload or []:
        commence_time = event.get("commence_time")
        date_label, kickoff, _unused_label = parse_commence_time(commence_time)
        commence_time_dt = parse_commence_datetime(commence_time)
        home_team = event.get("home_team", "Home team")
        away_team = event.get("away_team", "Away team")
        home_xg, away_xg, debug = project_goals_from_event(event)
        total_line = debug["total_line"]
        home_spread = debug["spread_line"]
        odds_note = (
            PINNACLE_UNAVAILABLE_MESSAGE
            if total_line is None or home_spread is None
            else ""
        )

        rows.append(
            {
                "fixture_id": event.get("id")
                or make_fixture_id(commence_time, home_team, away_team),
                "date": date_label,
                "kickoff": kickoff,
                "round": (
                    get_round_for_fixture(home_team, away_team, commence_time_dt)
                    if competition_name == "World Cup"
                    else "Premier League"
                ),
                "commence_time": commence_time,
                "commence_time_dt": commence_time_dt,
                "fixture_set": competition_name,
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
                "bookmaker_used": debug["bookmaker_used"],
                "h2h_used": debug["h2h_used"],
                "btts_used": debug["btts_used"],
                "correct_score_used": debug["correct_score_used"],
                "odds_note": odds_note,
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


ROUND_TABLE_COLUMNS = ["Round of 32"]
ROUND_TO_MD = {
    "Round 1": "MD1",
    "Round 2": "MD2",
    "Round 3": "MD3",
    "Round of 32": "Round of 32",
    "Premier League": "Fixture",
}
MD_TO_ROUND = {label: round_name for round_name, label in ROUND_TO_MD.items()}
LEADERBOARD_RANGES = {
    "Round of 32": ["Round of 32"],
}


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


def metric_title(metric_key):
    return "Projected Goals" if metric_key == "projected_goals" else "Clean Sheet %"


def metric_total_label(metric_key):
    return "Total" if metric_key == "projected_goals" else "Total CS%"


def show_leaderboard_total(metric_key):
    return metric_key == "projected_goals"


def format_leaderboard_value(value, metric_key):
    if metric_key == "projected_goals":
        return format_projected_goals(value)
    return format_clean_sheet(value)


def leaderboard_export_metric_header(metric_key):
    return "Projected Goals" if metric_key == "projected_goals" else "Clean Sheet %"


def build_leaderboard_rows(fixtures, metric_key, selected_rounds, top_n=10):
    team_rows = build_team_round_rows(fixtures)
    if team_rows.empty or metric_key not in team_rows.columns:
        return []

    team_rows = team_rows[
        team_rows["round"].isin(selected_rounds)
        & team_rows["team"].notna()
        & team_rows[metric_key].notna()
    ].copy()
    if team_rows.empty:
        return []

    team_rows = team_rows.sort_values(metric_key, ascending=False)
    best_by_team_round = team_rows.drop_duplicates(["team", "round"], keep="first")
    ranking = (
        best_by_team_round.groupby("team", as_index=False)[metric_key]
        .sum()
        .rename(columns={metric_key: "total"})
        .sort_values("total", ascending=False)
        .head(top_n)
    )

    output_rows = []
    for team, total in ranking[["team", "total"]].itertuples(index=False):
        team_rounds = {}
        for round_name in selected_rounds:
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
        output_rows.append({"team": team, "rounds": team_rounds, "total": total})

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


def draw_text_fit(draw, xy, text, font, fill, max_width):
    clean_text = str(text)
    if draw.textlength(clean_text, font=font) <= max_width:
        draw.text(xy, clean_text, font=font, fill=fill)
        return

    ellipsis = "..."
    while clean_text and draw.textlength(clean_text + ellipsis, font=font) > max_width:
        clean_text = clean_text[:-1]
    draw.text(xy, clean_text + ellipsis, font=font, fill=fill)


def wrap_text(draw, text, font, max_width, max_lines=2):
    words = str(text).split()
    if not words:
        return [""]

    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = word
        else:
            chunk = ""
            for char in word:
                candidate_chunk = f"{chunk}{char}"
                if draw.textlength(candidate_chunk, font=font) <= max_width:
                    chunk = candidate_chunk
                else:
                    lines.append(chunk)
                    chunk = char
            current = chunk

        if len(lines) == max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    return lines


def draw_wrapped_text_center(draw, box, text, font, fill, max_lines=2, line_height=1.15):
    left, top, right, bottom = box
    max_width = max(1, right - left - 10)
    lines = wrap_text(draw, text, font, max_width, max_lines=max_lines)
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    base_height = bbox[3] - bbox[1]
    line_px = base_height * line_height
    total_height = line_px * len(lines)
    y = top + ((bottom - top) - total_height) / 2

    for line in lines:
        line_width = draw.textlength(line, font=font)
        draw.text(
            (left + ((right - left) - line_width) / 2, y),
            line,
            font=font,
            fill=fill,
        )
        y += line_px


def build_leaderboard_image(
    fixtures,
    metric_key,
    leaderboard_range,
    selected_rounds,
    competition_name="World Cup",
):
    EXPORT_W = 1080
    EXPORT_H = 1350
    BG = "#f3f6f9"
    MARGIN_X = 55
    TABLE_TOP = 178
    HEADER_H = 50
    ROW_H = 94

    img = Image.new("RGB", (EXPORT_W, EXPORT_H), hex_to_rgb(BG))
    draw = ImageDraw.Draw(img)

    title_font = load_font(38, bold=True)
    subtitle_font = load_font(22)
    link_font = load_font(16)
    header_font = load_font(15, bold=True)
    rank_font = load_font(22, bold=True)
    team_font = load_font(25, bold=True)
    opponent_font = load_font(18, bold=True)
    value_font = load_font(28, bold=True)
    total_font = load_font(34, bold=True)
    footer_font = load_font(18)

    logo = load_export_logo(66)
    img.paste(logo, (MARGIN_X, 30), logo)
    draw.text((MARGIN_X + 84, 29), metric_title(metric_key), font=title_font, fill=hex_to_rgb("#111827"))
    draw.text((MARGIN_X + 86, 77), competition_title(competition_name), font=link_font, fill=hex_to_rgb("#64748b"))
    draw.text((MARGIN_X, 120), leaderboard_range, font=subtitle_font, fill=hex_to_rgb("#4b5563"))

    rows = build_leaderboard_rows(fixtures, metric_key, selected_rounds)
    table_left = MARGIN_X
    table_right = EXPORT_W - MARGIN_X
    table_w = table_right - table_left
    rank_w = 72
    team_w = 330
    total_w = 150
    metric_w = table_w - rank_w - team_w - total_w
    col_widths = [rank_w, team_w, metric_w, total_w]
    table_h = HEADER_H + min(10, len(rows)) * ROW_H

    draw.rounded_rectangle(
        (table_left, TABLE_TOP, table_right, TABLE_TOP + table_h),
        radius=18,
        fill=hex_to_rgb("#ffffff"),
        outline=hex_to_rgb("#d8dee8"),
        width=2,
    )
    draw.rounded_rectangle(
        (table_left, TABLE_TOP, table_right, TABLE_TOP + HEADER_H),
        radius=18,
        fill=hex_to_rgb("#f5f7fa"),
    )
    draw.rectangle(
        (table_left, TABLE_TOP + HEADER_H - 20, table_right, TABLE_TOP + HEADER_H),
        fill=hex_to_rgb("#f5f7fa"),
    )

    headers = [
        "Rank",
        "Team",
        leaderboard_export_metric_header(metric_key),
        "Total",
    ]
    x = table_left
    for header, width in zip(headers, col_widths):
        draw_text_center(
            draw,
            (x, TABLE_TOP, x + width, TABLE_TOP + HEADER_H),
            header.upper(),
            header_font,
            hex_to_rgb("#64748b"),
        )
        x += width

    line_color = hex_to_rgb("#d8dee8")
    y = TABLE_TOP + HEADER_H
    draw.line((table_left, y, table_right, y), fill=line_color, width=1)

    for index, row in enumerate(rows[:10], start=1):
        row_top = TABLE_TOP + HEADER_H + (index - 1) * ROW_H
        row_bottom = row_top + ROW_H
        draw.line((table_left, row_bottom, table_right, row_bottom), fill=hex_to_rgb("#edf1f5"), width=1)

        x = table_left
        draw_text_center(
            draw,
            (x, row_top, x + rank_w, row_bottom),
            str(index),
            rank_font,
            hex_to_rgb("#64748b"),
        )
        x += rank_w

        draw_flag_badge(img, draw, row["team"], x + 20, row_top + 35, header_font)
        draw_text_fit(
            draw,
            (x + 66, row_top + 32),
            row["team"],
            team_font,
            hex_to_rgb("#111827"),
            team_w - 82,
        )
        x += team_w

        metric_cells = [
            row["rounds"].get(round_name)
            for round_name in selected_rounds
            if row["rounds"].get(round_name)
        ]
        if metric_cells:
            visible_cells = metric_cells[:3]
            sub_w = metric_w / len(visible_cells)
            for cell_index, cell in enumerate(visible_cells):
                cell_left = x + (cell_index * sub_w)
                cell_right = cell_left + sub_w
                draw_wrapped_text_center(
                    draw,
                    (cell_left + 10, row_top + 9, cell_right - 10, row_top + 50),
                    cell["opponent"],
                    opponent_font,
                    hex_to_rgb("#111827"),
                    max_lines=2,
                    line_height=1.15,
                )
                draw_text_center(
                    draw,
                    (cell_left, row_top + 50, cell_right, row_bottom - 6),
                    format_leaderboard_value(cell[metric_key], metric_key),
                    value_font,
                    hex_to_rgb("#0f7a45"),
                )
        else:
            draw_text_center(
                draw,
                (x, row_top, x + metric_w, row_bottom),
                "-",
                value_font,
                hex_to_rgb("#94a3b8"),
            )
        x += metric_w

        draw_text_center(
            draw,
            (x, row_top, x + total_w, row_bottom),
            format_leaderboard_value(row["total"], metric_key),
            total_font,
            hex_to_rgb("#0f7a45"),
        )

    x = table_left
    for width in col_widths[:-1]:
        x += width
        draw.line((x, TABLE_TOP, x, TABLE_TOP + table_h), fill=hex_to_rgb("#edf1f5"), width=1)

    if not rows:
        draw_text_center(
            draw,
            (table_left, TABLE_TOP + HEADER_H, table_right, TABLE_TOP + 260),
            "No leaderboard data available yet.",
            subtitle_font,
            hex_to_rgb("#64748b"),
        )

    footer_divider_y = min(TABLE_TOP + table_h + 40, EXPORT_H - 88)
    footer_text_y = footer_divider_y + 24
    draw.line((MARGIN_X, footer_divider_y, EXPORT_W - MARGIN_X, footer_divider_y), fill=hex_to_rgb("#d1d5db"), width=2)
    draw.text((MARGIN_X, footer_text_y), "Graphics by FPL Cartel", font=footer_font, fill=hex_to_rgb("#111827"))
    draw.text((EXPORT_W - 430, footer_text_y), "Source: Pinnacle odds via The Odds API", font=footer_font, fill=hex_to_rgb("#111827"))

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


def build_export_image(fixtures_to_show, selected_round, competition_name="World Cup"):
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
        competition_title(competition_name),
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
    source_text = "Source: Pinnacle odds via The Odds API"
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


def build_export_image_bytes(
    fixtures_to_show,
    selected_round,
    export_page,
    total_export_pages,
    competition_name="World Cup",
):
    if USE_BROWSER_EXPORT:
        return build_export_with_playwright(
            fixtures_to_show,
            selected_round,
            export_page,
            total_export_pages,
            competition_name,
        ).getvalue()

    return build_export_with_pil(
        fixtures_to_show,
        selected_round,
        export_page,
        total_export_pages,
        competition_name,
    ).getvalue()


def build_export_with_playwright(fixtures_to_show, selected_round, export_page, total_export_pages, competition_name="World Cup"):
    from playwright.sync_api import sync_playwright

    html = build_export_html(fixtures_to_show, selected_round, export_page, total_export_pages, competition_name)

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


def build_export_with_pil(fixtures_to_show, selected_round, export_page, total_export_pages, competition_name="World Cup"):
    export_title = selected_round
    if total_export_pages > 1:
        export_title = f"{selected_round} - Page {export_page} of {total_export_pages}"
    return build_export_image(fixtures_to_show, export_title, competition_name)


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


def build_export_html(fixtures_to_show, selected_round, export_page, total_export_pages, competition_name="World Cup"):
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
    <h1 class="export-title">{escape(competition_title(competition_name))}</h1>
    <p class="export-subtitle">{escape(subtitle)}</p>
    <main class="export-grid">
      {cards}
    </main>
    <footer class="export-footer">
      <div>Graphics by <strong>FPL Cartel</strong></div>
      <div>Source: Pinnacle odds via <strong>The Odds API</strong></div>
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


def render_metric_cell(value, metric, class_name):
    value_text = (
        format_clean_sheet(value)
        if metric == "clean_sheet_pct"
        else format_projected_goals(value)
    )
    return (
        f'<div class="metric-cell {class_name}">'
        f'<span class="metric-value">{escape(value_text)}</span>'
        "</div>"
    )


def render_fixture_card(row):
    note = getattr(row, "odds_note", "") or ""
    note_html = (
        f'<div class="fixture-note">{escape(str(note))}</div>'
        if note
        else ""
    )
    return (
        '<div class="fixture-card-wrap">'
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
        f'{render_metric_cell(row.home_xg, "projected_goals", goal_cell_class(row.home_xg))}'
        f'{render_metric_cell(row.away_xg, "projected_goals", goal_cell_class(row.away_xg))}'
        "</div>"
        '<div class="clean-col">'
        '<div class="metric-head">Clean sheet</div>'
        f'{render_metric_cell(row.home_cs, "clean_sheet_pct", cs_cell_class(row.home_cs))}'
        f'{render_metric_cell(row.away_cs, "clean_sheet_pct", cs_cell_class(row.away_cs))}'
        "</div>"
        "</article>"
        f"{note_html}"
        "</div>"
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


def render_fixture_group(fixtures, heading):
    cards = "\n".join(
        render_fixture_card(row) for row in fixtures.itertuples(index=False)
    )
    return (
        '<section class="date-group">'
        f'<h2 class="date-heading">{escape(str(heading))}</h2>'
        f'<main class="fixture-grid">{cards}</main>'
        "</section>"
    )


def render_top_team_value_cell(cell, metric_key):
    if not cell:
        return '<td class="top-round-cell top-round-empty">-</td>'

    value = cell[metric_key]
    value_text = format_leaderboard_value(value, metric_key)
    return (
        '<td class="top-round-cell">'
        f'<span class="top-opponent">{escape(str(cell["opponent"]))}</span>'
        f'<strong>{escape(value_text)}</strong>'
        "</td>"
    )


def render_leaderboard_table(fixtures, metric_key, selected_rounds):
    rows = build_leaderboard_rows(fixtures, metric_key, selected_rounds)
    if not rows:
        return '<div class="empty-note">No team ranking data available yet.</div>'

    round_headers = "".join(
        f"<th>{escape(ROUND_TO_MD.get(round_name, round_name))}</th>"
        for round_name in selected_rounds
    )
    body_rows = []
    for index, row in enumerate(rows, start=1):
        round_cells = "".join(
            render_top_team_value_cell(row["rounds"].get(round_name), metric_key)
            for round_name in selected_rounds
        )
        total_cell = (
            '<td class="top-total-cell">'
            f'<strong>{escape(format_leaderboard_value(row["total"], metric_key))}</strong>'
            "</td>"
            if show_leaderboard_total(metric_key)
            else ""
        )
        body_rows.append(
            "<tr>"
            f'<td class="top-rank-cell"><span class="top-rank">{index}</span></td>'
            '<td class="top-team-cell">'
            f"{render_team_flag(row['team'])}"
            f'<span>{escape(str(row["team"]))}</span>'
            "</td>"
            f"{round_cells}"
            f"{total_cell}"
            "</tr>"
        )
    total_header = (
        f"<th>{escape(metric_total_label(metric_key))}</th>"
        if show_leaderboard_total(metric_key)
        else ""
    )

    return (
        '<div class="top-teams-table-wrap">'
        '<table class="top-teams-table">'
        "<thead><tr>"
        "<th>Rank</th>"
        "<th>Team</th>"
        f"{round_headers}"
        f"{total_header}"
        "</tr></thead>"
        f'<tbody>{"".join(body_rows)}</tbody>'
        "</table>"
        "</div>"
    )


def render_top_teams_section(fixtures, competition_name="World Cup", leaderboard_label=None):
    section_title = (
        "Top Teams by Round"
        if competition_name == "World Cup"
        else "Top Teams by Gameweek"
    )
    st.markdown(
        f"""
        <section class="top-teams-section">
          <div class="section-kicker">FPL Cartel model</div>
          <h2>{escape(section_title)}</h2>
          <p>Opponent and model-estimated value for each team's selected round/gameweek.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if competition_name == "World Cup":
        leaderboard_range = st.selectbox(
            "Leaderboard range",
            list(LEADERBOARD_RANGES.keys()),
            key=f"{competition_name}_leaderboard_range",
        )
        selected_rounds = LEADERBOARD_RANGES[leaderboard_range]
    else:
        leaderboard_range = leaderboard_label or "Premier League"
        selected_rounds = [leaderboard_range]
        fixtures = fixtures.copy()
        fixtures["round"] = leaderboard_range
    goals_tab, cs_tab = st.tabs(["Projected Goals", "Clean Sheet %"])
    with goals_tab:
        st.markdown(
            render_leaderboard_table(fixtures, "projected_goals", selected_rounds),
            unsafe_allow_html=True,
        )
        st.download_button(
            "Download leaderboard image",
            data=build_leaderboard_image(
                fixtures,
                "projected_goals",
                leaderboard_range,
                selected_rounds,
                competition_name,
            ),
            file_name=(
                "fpl-cartel-leaderboard-projected-goals-"
                f"{leaderboard_range.lower().replace(' ', '-').replace('+', 'plus')}.png"
            ),
            mime="image/png",
            key=f"{competition_name}_download_projected_goals_leaderboard",
        )
    with cs_tab:
        st.markdown(
            render_leaderboard_table(fixtures, "clean_sheet_pct", selected_rounds),
            unsafe_allow_html=True,
        )
        st.download_button(
            "Download leaderboard image",
            data=build_leaderboard_image(
                fixtures,
                "clean_sheet_pct",
                leaderboard_range,
                selected_rounds,
                competition_name,
            ),
            file_name=(
                "fpl-cartel-leaderboard-clean-sheets-"
                f"{leaderboard_range.lower().replace(' ', '-').replace('+', 'plus')}.png"
            ),
            mime="image/png",
            key=f"{competition_name}_download_clean_sheet_leaderboard",
        )


def render_export_area(fixtures, group_heading=None):
    fixture_html = (
        render_fixture_group(fixtures, group_heading)
        if group_heading
        else render_fixture_groups(fixtures)
    )
    return (
        '<section class="export-area">'
        f"{fixture_html}"
        '<div class="export-footer">'
        "<div>Graphics by <strong>FPL Cartel</strong></div>"
        "<div>Source: Pinnacle odds via <strong>The Odds API</strong></div>"
        "</div>"
        "</section>"
    )


def build_fixture_debug_table(fixtures):
    rows = []
    if fixtures is None or fixtures.empty:
        return pd.DataFrame(rows)

    for fixture in fixtures.to_dict("records"):
        rows.append(
            {
                "Date": fixture.get("date", ""),
                "Kickoff": fixture.get("kickoff", ""),
                "Odds API home_team": fixture.get("home_team", ""),
                "Odds API away_team": fixture.get("away_team", ""),
                "commence_time": fixture.get("commence_time", ""),
                "Fixture": (
                    f'{fixture.get("home_team", "")} vs '
                    f'{fixture.get("away_team", "")}'
                ),
                "Round": fixture.get("round", ""),
                "Gameweek": (
                    f"GW{int(fixture['gameweek'])}"
                    if pd.notna(fixture.get("gameweek"))
                    else ""
                ),
                "matched FPL event": fixture.get("matched_fpl_event", ""),
                "matched GW": (
                    f"GW{int(fixture['gameweek'])}"
                    if pd.notna(fixture.get("gameweek"))
                    else "Unmatched / Upcoming"
                ),
                "match confidence": (
                    f'{int(fixture.get("match_confidence", 0))}%'
                    if fixture.get("match_confidence") is not None
                    else ""
                ),
                "Bookmaker": fixture.get("bookmaker_used", "Sample"),
                "Total line": format_price(fixture.get("total_line")),
                "Spread line": format_price(fixture.get("home_spread")),
                "H2H used": bool(fixture.get("h2h_used", False)),
                "BTTS used": bool(fixture.get("btts_used", False)),
                "Correct score used": bool(
                    fixture.get("correct_score_used", False)
                ),
            }
        )

    return pd.DataFrame(rows)


def render_competition_dashboard(selected_competition):
    desktop_styles()
    competition_config = COMPETITIONS[selected_competition]

    raw_api_response, api_error, _api_status_code, last_updated = fetch_odds(
        competition_config["sport_key"]
    )
    live_fixtures = parse_odds_response(raw_api_response, selected_competition)
    if selected_competition == "Premier League":
        live_fixtures = add_premier_league_gameweeks(live_fixtures)
    using_live_data = not live_fixtures.empty

    status_text = "Live odds via The Odds API &middot; Pinnacle only"
    display_fixtures = live_fixtures
    last_updated_text = format_last_updated(last_updated)
    source_note = status_text + (
        f"<br>{escape(last_updated_text)}" if last_updated_text else ""
    )
    st.markdown(render_brand_header(selected_competition), unsafe_allow_html=True)
    st.markdown(
        f'<div class="source-note">{source_note}</div>',
        unsafe_allow_html=True,
    )

    if api_error:
        st.error("Live odds unavailable: API request failed. Check markets/API plan.")
        st.caption(f"Details: {api_error}")
        return

    if not using_live_data:
        st.markdown(f'<div class="empty-note">{NO_LIVE_ODDS_MESSAGE}</div>', unsafe_allow_html=True)
        return

    fixture_options = display_fixtures["fixture_set"].drop_duplicates().tolist()
    control_cols = st.columns([1.1, 1.05, 0.9, 1.2])

    with control_cols[0]:
        fixture_set = st.segmented_control(
            "Fixture set",
            fixture_options,
            default=fixture_options[0],
            key=f"{selected_competition}_fixture_set",
        )

    filtered = display_fixtures[display_fixtures["fixture_set"] == fixture_set]
    debug_fixtures = filtered
    if selected_competition == "World Cup":
        available_rounds = filtered["round"].drop_duplicates().tolist()
        round_options = sorted(available_rounds, key=round_sort_key)
        fixture_records = filtered.to_dict("records")
        default_round = get_current_round(fixture_records)
        default_round_index = (
            round_options.index(default_round)
            if default_round in round_options
            else 0
        )

        with control_cols[1]:
            selected_filter = st.selectbox(
                "Round",
                round_options,
                index=default_round_index,
                key=f"{selected_competition}_round",
            )
        filtered = filtered[filtered["round"] == selected_filter]
    else:
        with control_cols[1]:
            gw_options = gameweek_options()
            default_gw = default_gameweek(filtered)
            selected_filter = st.selectbox(
                "Gameweek",
                gw_options,
                index=gw_options.index(default_gw) if default_gw in gw_options else 0,
                key=f"{selected_competition}_gameweek",
            )
        filtered = filter_by_gameweek(filtered, selected_filter)
        if filtered.empty and selected_filter.startswith("GW"):
            st.warning(
                f"No {selected_filter} matches could be linked to FPL fixtures. "
                "Use All priced fixtures to inspect returned odds."
            )

    with control_cols[2]:
        neutral_label = "On" if competition_config["neutral"] else "Off"
        st.segmented_control(
            "Neutral venue",
            [neutral_label],
            default=neutral_label,
            key=f"{selected_competition}_neutral_venue",
        )

    with control_cols[3]:
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
                key=f"{selected_competition}_export_page",
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
                selected_filter,
                selected_export_page,
                total_export_pages,
                selected_competition,
            ),
            file_name=(
                f"fpl-cartel-{selected_competition.lower().replace(' ', '-')}-odds-"
                f"{selected_filter.lower().replace(' ', '-')}-"
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
        group_heading = selected_filter if selected_competition == "Premier League" else None
        st.markdown(render_export_area(filtered, group_heading), unsafe_allow_html=True)

    top_team_fixtures = (
        filtered
        if selected_competition == "Premier League"
        else display_fixtures[display_fixtures["fixture_set"] == fixture_set]
    )
    render_top_teams_section(
        top_team_fixtures,
        selected_competition,
        selected_filter if selected_competition == "Premier League" else None,
    )

    with st.expander("Fixture model debug", expanded=False):
        if selected_competition == "Premier League":
            st.caption(
                "Premier League GW matching debug: Odds API teams, commence_time, "
                "matched FPL event, matched GW, and match confidence."
            )
        st.dataframe(
            build_fixture_debug_table(
                debug_fixtures if selected_competition == "Premier League" else filtered
            ),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Debug API response", expanded=False):
        if api_error:
            st.error(api_error)
        st.json(raw_api_response)


def render_desktop_dashboard():
    desktop_styles()
    world_cup_tab, premier_league_tab = st.tabs(["World Cup", "Premier League"])
    with world_cup_tab:
        render_competition_dashboard("World Cup")
    with premier_league_tab:
        render_competition_dashboard("Premier League")


is_mobile = view == "mobile"

if is_mobile:
    render_mobile_dashboard()
else:
    render_desktop_dashboard()
