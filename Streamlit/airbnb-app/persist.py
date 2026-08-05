# Persists small bits of user selection (persona, city filter, starred
# neighbourhoods) in the URL's query params, so they survive a full browser
# refresh — plain st.session_state resets on refresh since that starts a new
# Streamlit session.
import streamlit as st


def get_persona() -> str | None:
    return st.query_params.get("persona")


def set_persona(persona: str) -> None:
    st.query_params["persona"] = persona


def get_cities(default: list[str]) -> list[str]:
    raw = st.query_params.get("cities")
    if not raw:
        return list(default)
    return raw.split(",")


def set_cities(cities: list[str]) -> None:
    st.query_params["cities"] = ",".join(cities)


def get_budget(default: int) -> int:
    raw = st.query_params.get("budget")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def set_budget(budget: int) -> None:
    st.query_params["budget"] = str(budget)


def get_starred() -> list[dict]:
    raw = st.query_params.get("starred")
    if not raw:
        return []
    starred = []
    for pair in raw.split(","):
        if "|" in pair:
            neighbourhood, city = pair.split("|", 1)
            starred.append({"neighbourhood": neighbourhood, "city": city})
    return starred


def set_starred(starred: list[dict]) -> None:
    st.query_params["starred"] = ",".join(f"{s['neighbourhood']}|{s['city']}" for s in starred)
