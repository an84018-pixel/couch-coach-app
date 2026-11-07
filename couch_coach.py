import os
import re
import time

import streamlit as st
from google import genai
from google.genai import errors, types


MODEL_NAME = "gemini-3.8-flash"
NFL_TEAM_COLORS = {
    "Arizona Cardinals": ("#97233F", "#000000"),
    "Atlanta Falcons": ("#A71930", "#000000"),
    "Baltimore Ravens": ("#241773", "#9E7C0C"),
    "Buffalo Bills": ("#00338D", "#C60C30"),
    "Carolina Panthers": ("#0085CA", "#101820"),
    "Chicago Bears": ("#0B162A", "#C83803"),
    "Cincinnati Bengals": ("#FB4F14", "#000000"),
    "Cleveland Browns": ("#311D00", "#FF3C00"),
    "Dallas Cowboys": ("#003594", "#869397"),
    "Denver Broncos": ("#FB4F14", "#002244"),
    "Detroit Lions": ("#0076B6", "#B0B7BC"),
    "Green Bay Packers": ("#203731", "#FFB612"),
    "Houston Texans": ("#03202F", "#A71930"),
    "Indianapolis Colts": ("#002C5F", "#A2AAAD"),
    "Jacksonville Jaguars": ("#101820", "#D7A22A"),
    "Kansas City Chiefs": ("#E31837", "#FFB81C"),
    "Las Vegas Raiders": ("#000000", "#A5ACAF"),
    "Los Angeles Chargers": ("#0080C6", "#FFC20E"),
    "Los Angeles Rams": ("#003594", "#FFA300"),
    "Miami Dolphins": ("#008E97", "#FC4C02"),
    "Minnesota Vikings": ("#4F2683", "#FFC62F"),
    "New England Patriots": ("#002244", "#C60C30"),
    "New Orleans Saints": ("#D3BC8D", "#101820"),
    "New York Giants": ("#0B2265", "#A71930"),
    "New York Jets": ("#125740", "#FFFFFF"),
    "Philadelphia Eagles": ("#004C54", "#A5ACAF"),
    "Pittsburgh Steelers": ("#FFB612", "#101820"),
    "San Francisco 49ers": ("#AA0000", "#B3995D"),
    "Seattle Seahawks": ("#002244", "#69BE28"),
    "Tampa Bay Buccaneers": ("#D50A0A", "#34302B"),
    "Tennessee Titans": ("#0C2340", "#4B92DB"),
    "Washington Commanders": ("#5A1414", "#FFB612"),
}
SYSTEM_INSTRUCTION = """
You are The Couch Coach, a knowledgeable, practical American football head coach.
Use the game situation provided to recommend one clear, realistic next play.
Be decisive, concise, and explain the reasoning in plain language for a beginner.
Account for the quarter, time remaining, down and distance, field position, and
score. If a detail is missing or ambiguous, state a brief assumption rather than
inventing facts. Do not claim certainty about the opponent's defense.

Format your response as:
THE PLAY CALL
State the recommended play, then add a small ASCII formation diagram directly
under it. Use O for the offense, X for the defense, and arrows to show the
intended ball-carrier or route movement. Keep the diagram compact and align its
characters with spaces. Treat it as a simple schematic, not a claim about the
opponent's actual defensive alignment.
FORMATION / PERSONNEL
WHY IT FITS
COACHING NOTE
"""


def create_demo_play_call(
    quarter, time_left, down_distance, field_position, score_situation
):
    down_match = re.search(
        r"\b(1st|2nd|3rd|4th|1|2|3|4)(?:\s*(?:st|nd|rd|th))?\s*"
        r"(?:&|and)\s*(\d+|goal)\b",
        down_distance.lower(),
    )
    down = int(down_match.group(1)[0]) if down_match else None
    yards_to_go = (
        int(down_match.group(2))
        if down_match and down_match.group(2).isdigit()
        else None
    )

    position_match = re.search(
        r"\b(own|opponent(?:'s)?|opp)\s*(\d{1,2})\b",
        field_position.lower(),
    )
    yards_to_goal = None
    own_yard_line = None
    if position_match:
        yard_line = int(position_match.group(2))
        if position_match.group(1) == "own":
            own_yard_line = yard_line
            yards_to_goal = 100 - yard_line
        else:
            yards_to_goal = yard_line
    elif "midfield" in field_position.lower() or "50" in field_position:
        own_yard_line = 50
        yards_to_goal = 50

    time_match = re.search(r"\b(\d{1,2}):([0-5]\d)\b", time_left)
    remaining_seconds = (
        int(time_match.group(1)) * 60 + int(time_match.group(2))
        if time_match
        else None
    )
    late_game = (
        quarter in ("4th Quarter", "Overtime")
        and remaining_seconds is not None
        and remaining_seconds <= 300
    )
    score_lower = score_situation.lower()
    trailing_late = late_game and any(
        word in score_lower for word in ("trail", "behind", "losing")
    )

    if trailing_late:
        play = "Hurry-up pass: use a quick sideline concept to preserve clock."
        diagram = "X   X   X   X   X\n  O   O   O   O\n      O  --->"
        why = "The team is trailing late, so a pass can gain yards while stopping the clock."
    elif down == 4:
        if (
            yards_to_go is not None
            and yards_to_go <= 2
            and yards_to_goal is not None
            and yards_to_goal <= 5
        ):
            play = "Go for it: quick quarterback sneak or low-risk dive."
            diagram = "X   X   X   X   X\n    O O O O O\n        O --->"
            why = (
                "It is fourth-and-short near the goal line, making a direct "
                "conversion attempt reasonable."
            )
        elif yards_to_goal is not None and yards_to_goal <= 35:
            play = "Attempt a field goal."
            diagram = "X   X   X   X   X\n  O   O   O   O\n      O   ^"
            why = "Field position appears close enough to consider a field goal on fourth down."
        elif own_yard_line is not None and own_yard_line < 60:
            play = "Punt to improve field position."
            diagram = "X   X   X   X   X\n  O   O   O   O\n      O   ^"
            why = (
                "On fourth down in your own territory, a punt avoids giving the "
                "opponent a short field."
            )
        else:
            play = "Go for it with a quick pass or an inside run."
            diagram = "X   X   X   X   X\n  O   O   O   O\n      O  --->"
            why = "The field position makes an aggressive fourth-down conversion more reasonable."
    elif down == 3 and yards_to_go is not None and yards_to_go <= 2:
        play = "Run a quick inside handoff or quarterback sneak."
        diagram = "X   X   X   X   X\n    O O O O O\n        O --->"
        why = "A short third-down distance favors a direct, low-risk conversion attempt."
    elif down == 3:
        play = "Pass a quick slant or crossing route."
        diagram = "X   X   X   X   X\n  O   O   O   O\n  O --->  O  --->"
        why = "A pass gives the offense a chance to cover the needed yards on third down."
    elif down == 2 and yards_to_go is not None and yards_to_go >= 7:
        play = "Use play-action with a short crossing route."
        diagram = "X   X   X   X   X\n  O   O   O   O\n      O  --->"
        why = "Play-action can make a manageable second-and-long situation more favorable."
    else:
        play = "Run an inside zone or other balanced handoff."
        diagram = "X   X   X   X   X\n    O O O O O\n        O --->"
        why = (
            "A balanced run is a sensible early-down call and can keep the "
            "next down manageable."
        )

    situation = (
        f"Situation: {quarter}, {time_left}, {down_distance}, "
        f"{field_position}, {score_situation}."
    )
    return (
        "DEMO MODE — RULE-BASED SUGGESTION (NOT AI-GENERATED)\n\n"
        "THE PLAY CALL\n"
        f"{play}\n"
        f"{diagram}\n\n"
        "WHY IT FITS\n"
        f"{why}\n"
        f"{situation}\n\n"
        "COACHING NOTE\n"
        "This offline demo uses simple rules, not live game data or a full playbook."
    )


def show_demo_play_call(
    quarter, time_left, down_distance, field_position, score_situation, reason
):
    st.info(reason)
    st.subheader("Demo-mode play call")
    st.code(
        create_demo_play_call(
            quarter, time_left, down_distance, field_position, score_situation
        )
    )


st.set_page_config(
    page_title="The Couch Coach",
    page_icon="🏈",
    layout="centered",
)

st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">Your sideline starts here</div>
        <h1>🏈 The Couch Coach</h1>
        <p>Set the game situation. Get a clear, coach-style play call.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

selected_team = st.selectbox(
    "Favorite NFL Team",
    ("Select a team", *NFL_TEAM_COLORS),
)
team_primary, team_secondary = NFL_TEAM_COLORS.get(
    selected_team,
    ("#33564a", "#c9e36a"),
)
primary_rgb = tuple(
    int(team_primary[index:index + 2], 16) for index in (1, 3, 5)
)
primary_luminance = sum(
    channel * weight
    for channel, weight in zip(primary_rgb, (0.299, 0.587, 0.114))
)
button_text_color = "#101916" if primary_luminance > 150 else "#FFFFFF"
team_highlight = "#{:02X}{:02X}{:02X}".format(
    *(round(channel + (255 - channel) * 0.55) for channel in primary_rgb)
)

st.markdown(
    f"""
    <style>
    .stApp {{
        --team-primary: {team_primary};
        --team-secondary: {team_secondary};
        --team-highlight: {team_highlight};
        --team-button-text: {button_text_color};
        background:
            radial-gradient(
                ellipse at 50% 0%,
                color-mix(in srgb, var(--team-primary) 35%, transparent) 0%,
                transparent 48%
            ),
            #101916;
        color: #f4f3e8;
    }}
    [data-testid="stHeader"] {{ background: transparent; }}
    .main .block-container {{ max-width: 860px; padding-top: 3rem; }}
    .hero {{
        padding: 1.8rem 2rem;
        margin-bottom: 1.5rem;
        border: 1px solid var(--team-secondary);
        border-radius: 18px;
        background: linear-gradient(
            135deg,
            color-mix(in srgb, var(--team-primary) 35%, #1d3c32),
            #172820
        );
    }}
    .eyebrow {{
        color: var(--team-highlight);
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .16em;
        text-transform: uppercase;
    }}
    .hero h1 {{ margin: .35rem 0; color: #f4f3e8; }}
    .hero p {{ margin: 0; color: #c3d0c6; }}
    [data-testid="stForm"] {{
        padding: 1.4rem;
        border: 1px solid color-mix(in srgb, var(--team-secondary) 70%, #33564a);
        border-radius: 16px;
        background: #18251f;
    }}
    [data-testid="stWidgetLabel"] p {{ color: #e6eadf; font-weight: 600; }}
    div.stButton > button, [data-testid="stFormSubmitButton"] button {{
        min-height: 3rem;
        border: 0;
        border-radius: 10px;
        background: var(--team-primary);
        color: var(--team-button-text);
        font-weight: 800;
    }}
    div.stButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {{
        background: var(--team-highlight);
        color: #101916;
        border: 0;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

if selected_team != "Select a team":
    st.caption(f"Showing team colors for the {selected_team}.")

with st.form("play_call_form"):
    st.subheader("Game situation")

    left_column, right_column = st.columns(2)
    with left_column:
        quarter = st.selectbox(
            "Quarter",
            ("1st Quarter", "2nd Quarter", "3rd Quarter", "4th Quarter", "Overtime"),
        )
        down_distance = st.text_input(
            "Down & Distance",
            placeholder="e.g. 3rd & 6",
        )
        score_situation = st.text_input(
            "Score Situation",
            placeholder="e.g. Leading 21–17",
        )
    with right_column:
        time_left = st.text_input(
            "Time Left",
            placeholder="e.g. 2:14",
        )
        field_position = st.text_input(
            "Field Position",
            placeholder="e.g. Own 42-yard line",
        )

    submitted = st.form_submit_button("Get Play Call", use_container_width=True)

if submitted:
    required_values = {
        "Time Left": time_left,
        "Down & Distance": down_distance,
        "Field Position": field_position,
        "Score Situation": score_situation,
    }
    missing_fields = [label for label, value in required_values.items() if not value.strip()]

    if missing_fields:
        st.warning("Please fill in: " + ", ".join(missing_fields) + ".")
    else:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            try:
                api_key = st.secrets["GEMINI_API_KEY"]
            except (KeyError, FileNotFoundError):
                api_key = None

        if not api_key:
            show_demo_play_call(
                quarter,
                time_left,
                down_distance,
                field_position,
                score_situation,
                "Gemini is not configured, so this recommendation is generated "
                "in offline demo mode.",
            )
        else:
            prompt = (
                "Recommend the next play for this game situation:\n"
                f"Quarter: {quarter}\n"
                f"Time Left: {time_left.strip()}\n"
                f"Down & Distance: {down_distance.strip()}\n"
                f"Field Position: {field_position.strip()}\n"
                f"Score Situation: {score_situation.strip()}"
            )
            st.subheader("Coach's call")
            response_placeholder = st.empty()
            try:
                with st.spinner("The coach is reviewing the situation..."):
                    client = genai.Client(api_key=api_key)
                    for attempt in range(3):
                        try:
                            response_stream = client.models.generate_content_stream(
                                model=MODEL_NAME,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    system_instruction=SYSTEM_INSTRUCTION,
                                    temperature=0.7,
                                ),
                            )
                            response_text = ""
                            for chunk in response_stream:
                                if chunk.text:
                                    response_text += chunk.text
                                    response_placeholder.code(response_text)
                            break
                        except errors.APIError as error:
                            if error.code == 503:
                                response_placeholder.empty()
                                if attempt < 2:
                                    time.sleep(2 ** (attempt + 1))
                                    continue
                                show_demo_play_call(
                                    quarter,
                                    time_left,
                                    down_distance,
                                    field_position,
                                    score_situation,
                                    "Gemini is temporarily unavailable after "
                                    "multiple attempts. Showing an offline demo "
                                    "recommendation instead.",
                                )
                            elif error.code == 429:
                                response_placeholder.empty()
                                show_demo_play_call(
                                    quarter,
                                    time_left,
                                    down_distance,
                                    field_position,
                                    score_situation,
                                    "Gemini's quota is exhausted. Showing an "
                                    "offline demo recommendation instead.",
                                )
                            elif error.code == 402:
                                response_placeholder.empty()
                                st.error(
                                    "Gemini could not process this request because "
                                    "of a billing or quota issue. Check your API "
                                    "account and try again."
                                )
                            elif error.code == 404:
                                response_placeholder.empty()
                                st.error(
                                    f"Gemini could not find the model {MODEL_NAME}. "
                                    "Check the configured model name."
                                )
                            elif error.code in (400, 401, 403):
                                response_placeholder.empty()
                                st.error(
                                    "Gemini rejected the request. Check that your "
                                    f"API key is valid and has access to {MODEL_NAME}. "
                                    f"Details: {error}"
                                )
                            else:
                                response_placeholder.empty()
                                st.error(
                                    f"Gemini could not generate a play call: {error}"
                                )
                            break
            except errors.APIError as error:
                response_placeholder.empty()
                if error.code in (429, 503):
                    show_demo_play_call(
                        quarter,
                        time_left,
                        down_distance,
                        field_position,
                        score_situation,
                        "Gemini is unavailable or its quota is exhausted. "
                        "Showing an offline demo recommendation instead.",
                    )
                else:
                    st.error(f"Gemini could not generate a play call: {error}")