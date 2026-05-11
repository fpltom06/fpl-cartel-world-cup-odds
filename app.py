import os
import math
from datetime import datetime, timezone
from html import escape
from io import BytesIO

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

st.set_page_config(
    page_title="FPL Cartel World Cup Odds Dashboard",
    page_icon="WC",
    layout="wide",
    initial_sidebar_state="collapsed",
)

query_params = st.query_params
view = query_params.get("view", "desktop")


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


def render_mobile_app():
    st.markdown(
        """
        <style>
            .stApp {
                background: #eef1f4;
                color: #17202a;
            }

            .block-container {
                max-width: 460px;
                padding: 0.75rem 0.65rem 2rem;
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
        </style>
        <section class="mobile-title">
            <h1>FPL Cartel World Cup Odds Dashboard</h1>
            <p>Projected goals and model-estimated clean sheet percentages.</p>
        </section>
        """,
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


if view == "mobile":
    render_mobile_app()
    st.stop()


st.markdown(
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
    """,
    unsafe_allow_html=True,
)


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
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
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
        flag = flag.resize((28, 28))
        _FLAG_CACHE[code] = flag
        return flag
    except Exception:
        return None


def draw_flag_badge(img, draw, team, x, y, font):
    flag = load_flag_image(team)
    if flag is not None:
        img.paste(flag, (int(x), int(y)), flag)
        return

    draw.ellipse((x, y, x + 28, y + 28), fill=hex_to_rgb("#e5e7eb"))
    draw_text_center(
        draw,
        (x, y, x + 28, y + 28),
        "?",
        font,
        hex_to_rgb("#64748b"),
    )


def build_export_image(fixtures_to_show, selected_round):
    EXPORT_W = 1920
    BASE_H = 1080
    MARGIN_X = 60
    START_Y = 145
    CARD_W = 850
    CARD_H = 110
    GAP_X = 70
    GAP_Y = 14
    FOOTER_GAP = 55
    FOOTER_H = 70
    CARD_RADIUS = 12
    BORDER = 2
    INNER_PAD = 2
    DATE_W = 115
    TEAM_W = 435
    PROJ_W = 145
    CS_W = 155
    HEADER_H = 28
    ROW_H = 41

    bg = "#f3f6f9"
    fixture_count = len(fixtures_to_show)
    rows_needed = math.ceil(fixture_count / 2) if fixture_count else 0
    content_h = START_Y + rows_needed * (CARD_H + GAP_Y)
    EXPORT_H = max(BASE_H, content_h + FOOTER_GAP + FOOTER_H)

    img = Image.new("RGB", (EXPORT_W, EXPORT_H), hex_to_rgb(bg))
    draw = ImageDraw.Draw(img)

    title_font = load_font(44, bold=True)
    subtitle_font = load_font(24)
    team_font = load_font(22, bold=True)
    small_font = load_font(17)
    metric_head_font = load_font(15, bold=True)
    metric_font = load_font(26, bold=True)
    footer_font = load_font(18)
    footer_bold = load_font(18, bold=True)
    badge_font = load_font(15, bold=True)

    draw.text(
        (MARGIN_X, 36),
        "FPL Cartel World Cup Odds Dashboard",
        font=title_font,
        fill=hex_to_rgb("#111827"),
    )
    draw.text(
        (MARGIN_X, 94),
        f"{selected_round} - Projected goals and clean sheet odds",
        font=subtitle_font,
        fill=hex_to_rgb("#4b5563"),
    )
    draw.text(
        (MARGIN_X, 122),
        f"Showing {fixture_count} fixtures",
        font=small_font,
        fill=hex_to_rgb("#4b5563"),
    )

    left_x = MARGIN_X
    right_x = MARGIN_X + CARD_W + GAP_X
    max_card_bottom = START_Y

    for index, row in enumerate(fixtures_to_show.itertuples(index=False)):
        col = index % 2
        row_position = index // 2

        x = left_x if col == 0 else right_x
        y = START_Y + row_position * (CARD_H + GAP_Y)

        max_card_bottom = max(max_card_bottom, y + CARD_H)

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
            (date_x + 8, y + 16, team_x - 8, y + 58),
            str(row.date),
            small_font,
            hex_to_rgb("#111827"),
        )
        draw_text_center(
            draw,
            (date_x + 8, y + 58, team_x - 8, y + 98),
            str(row.kickoff),
            small_font,
            hex_to_rgb("#4b5563"),
        )

        home_row_y = y + HEADER_H
        away_row_y = y + HEADER_H + ROW_H
        draw_flag_badge(img, draw, row.home_team, team_x + 18, home_row_y + 7, badge_font)
        draw_flag_badge(img, draw, row.away_team, team_x + 18, away_row_y + 7, badge_font)
        draw.text((team_x + 58, home_row_y + 10), str(row.home_team), font=team_font, fill=hex_to_rgb("#111827"))
        draw.text((team_x + 58, away_row_y + 10), str(row.away_team), font=team_font, fill=hex_to_rgb("#111827"))

        draw_text_center(draw, (proj_x, y, cs_x, y + HEADER_H), "PROJ", metric_head_font, hex_to_rgb("#4b5563"))
        draw_text_center(draw, (cs_x, y, card_right_x, y + HEADER_H), "CS %", metric_head_font, hex_to_rgb("#4b5563"))

        draw.rounded_rectangle(
            (x, y, card_right_x, y + CARD_H),
            radius=CARD_RADIUS,
            outline=hex_to_rgb("#d8dee8"),
            width=2,
        )

    max_card_bottom = START_Y + rows_needed * (CARD_H + GAP_Y)
    footer_y = max_card_bottom + 35
    divider_y = footer_y - 22
    footer_text_y = footer_y + 10

    draw.line((MARGIN_X, divider_y, EXPORT_W - MARGIN_X, divider_y), fill=hex_to_rgb("#d1d5db"), width=2)
    draw.text((MARGIN_X, footer_text_y), "Graphics by ", font=footer_font, fill=hex_to_rgb("#111827"))
    graphics_prefix_width = draw.textlength("Graphics by ", font=footer_font)
    draw.text(
        (MARGIN_X + graphics_prefix_width, footer_text_y),
        "FPL Cartel",
        font=footer_bold,
        fill=hex_to_rgb("#111827"),
    )
    source_text = "Source: live odds via The Odds API"
    source_width = draw.textlength(source_text, font=footer_font)
    draw.text(
        (EXPORT_W - MARGIN_X - source_width, footer_text_y),
        source_text,
        font=footer_font,
        fill=hex_to_rgb("#111827"),
    )

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


@st.cache_data(show_spinner=False)
def build_export_image_bytes(fixtures_to_show, selected_round):
    return build_export_image(fixtures_to_show, selected_round).getvalue()


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


raw_api_response, api_error, _api_status_code = fetch_world_cup_odds()
live_fixtures = parse_odds_response(raw_api_response)
using_live_data = not live_fixtures.empty

status_text = "Live odds via The Odds API" if using_live_data else "Sample fallback data"
display_fixtures = live_fixtures if using_live_data else SAMPLE_FIXTURES
st.markdown(
    f"""
    <section class="title-section">
        <div>
            <h1>FPL Cartel World Cup Odds Dashboard</h1>
            <p>Projected goals and model-estimated clean sheet percentages by round.</p>
        </div>
        <div class="status-chip">{status_text}</div>
    </section>
    """,
    unsafe_allow_html=True,
)

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
    export_state_key = "export_image_state"
    export_request_key = f"{fixture_set}|{selected_round}|{len(filtered)}"
    cached_export = st.session_state.get(export_state_key, {})

    if cached_export.get("request_key") != export_request_key:
        st.session_state.pop(export_state_key, None)
        cached_export = {}

    if st.button("Download image", key="prepare_export_image"):
        st.session_state[export_state_key] = {
            "request_key": export_request_key,
            "data": build_export_image_bytes(filtered, selected_round),
        }
        cached_export = st.session_state[export_state_key]

    if cached_export.get("data"):
        st.download_button(
            "Save PNG",
            data=cached_export["data"],
            file_name=(
                "fpl-cartel-world-cup-odds-"
                f"{selected_round.lower().replace(' ', '-')}-full.png"
            ),
            mime="image/png",
        )

if filtered.empty:
    st.markdown(
        '<div class="empty-note">No fixtures available for this selection.</div>',
        unsafe_allow_html=True,
    )
else:
    total_fixtures = len(filtered)
    page_size = 12
    total_pages = max(1, math.ceil(total_fixtures / page_size))
    page_key = f"fixture_page_{fixture_set}_{selected_round}_{page_size}"
    page_key = page_key.replace(" ", "_").replace("/", "_")

    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    st.session_state[page_key] = min(st.session_state[page_key], total_pages - 1)
    current_page = st.session_state[page_key]

    page_start = current_page * page_size
    page_end = min(page_start + page_size, total_fixtures)
    paged_fixtures = filtered.iloc[page_start:page_end]

    page_cols = st.columns([1, 1.4, 1])
    with page_cols[0]:
        if st.button("Previous", disabled=current_page == 0):
            st.session_state[page_key] = max(0, current_page - 1)
            st.rerun()
    with page_cols[1]:
        st.markdown(
            (
                f'<div class="empty-note">Showing fixtures {page_start + 1}-'
                f'{page_end} of {total_fixtures}</div>'
            ),
            unsafe_allow_html=True,
        )
    with page_cols[2]:
        if st.button("Next", disabled=current_page >= total_pages - 1):
            st.session_state[page_key] = min(total_pages - 1, current_page + 1)
            st.rerun()

    st.markdown(render_export_area(paged_fixtures), unsafe_allow_html=True)

with st.expander("Debug API response", expanded=False):
    if api_error:
        st.error(api_error)
    st.json(raw_api_response)
