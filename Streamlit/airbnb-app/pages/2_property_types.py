import streamlit as st
import os
import pandas as pd
import json
import time

st.cache_data.clear()

st.set_page_config(layout="wide")

st.markdown(
    """
    <style>
    div.stButton > button {
        white-space: pre-line;
        min-height: 80px;
    }

    div.stButton > button p {
        white-space: pre-line;
        text-align: center;
        font-size: 13px;
        line-height: 1.3;
    }

    div.stButton > button p::first-line {
        font-size: 18px;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True
)

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

#AI_COOLDOWN_SECONDS = 60

#if "property_ai_summaries" not in st.session_state:
 #   st.session_state["property_ai_summaries"] = {}

#if "last_property_ai_call_time" not in st.session_state:
 #   st.session_state["last_property_ai_call_time"] = 0
    
if "starred_neighbourhoods" not in st.session_state:
    st.session_state["starred_neighbourhoods"] = []

if "selected_property_neighbourhood" not in st.session_state:
    st.session_state["selected_property_neighbourhood"] = None

if "starred_property_types" not in st.session_state:
    st.session_state["starred_property_types"] = []

if len(st.session_state['starred_property_types']) == 3:
    if st.button('Continue to Listing Candidates'):
        st.switch_page('pages/3_listing_candidates.py')
else:
    st.button('Continue to Listing Candidates', disabled = True)
    st.caption('Select exactly 3 Property Types before continuing.')
#TITLE ---

st.title('Property Type')
st.subheader('Out of your favourite neighbourhoods, find the best property types based on your selected persona. Choose 3 property types from any of the nieghbourhoods that spark the most interest.')
#SQL QUERY ---

@st.cache_data(ttl=300)
def load_property_types(_session):
    return _session.sql(
        """
       SELECT
            c.CITY,
            p.NEIGHBOURHOOD,
            p.PROPERTY_GROUP,
            p.LISTING_COUNT
            
        FROM AIRBNB_INVESTMENT_DB.GOLD.MART_PROPERTY_GROUP p

        LEFT JOIN (
        SELECT DISTINCT CITY, NEIGHBOURHOOD
        FROM AIRBNB_INVESTMENT_DB.GOLD.MART_AREA_POI
        ) c
        
        ON p.NEIGHBOURHOOD = c.NEIGHBOURHOOD

        WHERE p.NEIGHBOURHOOD IS NOT NULL AND p.PROPERTY_GROUP IS NOT NULL AND c.CITY IS NOT NULL

        ORDER BY c.CITY, p.NEIGHBOURHOOD, p.LISTING_COUNT DESC
        """
    ).to_pandas()

property_types = load_property_types(session)

@st.cache_data(ttl=300)
def load_summary(_session):
    return _session.sql(
    """
        SELECT *
        FROM TESTER123GOLD.GOLD.AI_OUTPUTS
    """
    ).to_pandas()

ai_summary = load_summary(session)
#VISUALISATIONS ---
starred_neighbourhoods = st.session_state["starred_neighbourhoods"]

st.markdown("### Your starred neighbourhoods")

if len(starred_neighbourhoods) == 0:
    st.info(
        "You have not starred any neighbourhoods yet. "
        "Go back to the Area Overview page and star up to 3 neighbourhoods."
    )

else:
    cols = st.columns(3)

    for i, neighbourhood in enumerate(starred_neighbourhoods[:3]):

        neighbourhood_name = neighbourhood["neighbourhood"]
        city_name = neighbourhood["city"]

        button_label = f"{neighbourhood_name}\n{city_name}"

        with cols[i]:
            if st.button(
                label=button_label,
                key=f"property_neighbourhood_{i}_{city_name}_{neighbourhood_name}",
                use_container_width=True
            ):
                st.session_state["selected_property_neighbourhood"] = neighbourhood_name


selected_neighbourhood = st.session_state["selected_property_neighbourhood"]

if selected_neighbourhood is not None:

    neighbourhood_data = property_types[
        property_types["NEIGHBOURHOOD"] == selected_neighbourhood
    ].copy()

    if neighbourhood_data.empty:
        st.warning("No property group data found for this neighbourhood.")

    else:
        selected_city = neighbourhood_data["CITY"].iloc[0]

        st.markdown(f"## {selected_neighbourhood}")
        st.caption(f"City: {selected_city}")

        st.markdown("### Top 3 property Types")

        top_3 = neighbourhood_data.sort_values(
            by = "LISTING_COUNT",
            ascending=False
        ).head(3)

        top_cols = st.columns(3)

        for i, row in enumerate(top_3.itertuples()):
            with top_cols[i]:

                with st.container(border=True):
                    st.markdown(
                        f"""
                        ## **{row.PROPERTY_GROUP}**
                        """
                    )

                    st.metric(
                        label = "Listings",
                        value = f"{row.LISTING_COUNT:,.0f}"
                    )

        st.divider()

        all_property_types = neighbourhood_data.sort_values(
            by="LISTING_COUNT",
            ascending=False
        )

        list_col, starred_col = st.columns([2, 1], gap="medium")

        with list_col:
            st.markdown("### All Property Types in this neighbourhood")

            for row in all_property_types.itertuples():
                property_group = row.PROPERTY_GROUP
                neighbourhood = row.NEIGHBOURHOOD
                city = row.CITY
                listing_count = row.LISTING_COUNT

                property_item = {
                    "property_group": property_group,
                    "neighbourhood": neighbourhood,
                    "city": city,
                    "listing_count": listing_count
                }

                property_key = f"{city}_{neighbourhood}_{property_group}"

                already_starred = any(
                    f"{item['city']}_{item['neighbourhood']}_{item['property_group']}" == property_key
                    for item in st.session_state["starred_property_types"]
                )

                with st.container(border=True):
                    row_cols = st.columns([4, 1, 1])

                    with row_cols[0]:
                        st.markdown(f"## {property_group}")

                    with row_cols[1]:
                        st.markdown("**Listings**")
                        st.write(f"{listing_count:,.0f}")

                    with row_cols[2]:
                        if already_starred:
                            st.success("Selected")
                        else:
                            if st.button(
                                "Star",
                                key=f"star_property_{property_key}",
                                use_container_width=True
                            ):
                                if len(st.session_state["starred_property_types"]) < 3:
                                    st.session_state["starred_property_types"].append(property_item)
                                    st.rerun()
                                else:
                                    st.warning("You can only star 3 property types.")

        with starred_col:
            with st.container(border=True):
                st.markdown("### Starred Property Types")
        
                starred_property_types = st.session_state["starred_property_types"]
        
                if len(starred_property_types) == 0:
                    st.info("No property types starred yet.")
                else:
                    for i, item in enumerate(starred_property_types):
                        with st.container(border=True):
                            st.markdown(f"### ⭐ {item['property_group']}")
                            st.markdown(f"**{item['neighbourhood']}**")
                            st.caption(item["city"])
        
                            if st.button(
                                "Remove",
                                key=f"remove_starred_property_{i}_{item['city']}_{item['neighbourhood']}_{item['property_group']}",
                                use_container_width=True
                            ):
                                st.session_state["starred_property_types"].pop(i)
                                st.rerun()
        
                st.caption(f"{len(starred_property_types)} / 3 selected")

#---
with st.bottom:
    with st.expander("AI Summary"):

        persona = st.session_state.get("persona", None)
        starred_property_types = st.session_state.get("starred_property_types", [])

        if persona is None:
            st.warning("No persona has been selected yet.")

        elif len(starred_property_types) == 0:
            st.warning("No starred property types selected yet.")

        elif len(starred_property_types) != 3:
            st.warning("Please select exactly 3 property types before viewing the AI summary.")

        else:
            st.write("This is your AI summary using persona:", persona)

            for starred_property in starred_property_types:

                property_group = starred_property["property_group"]
                neighbourhood = starred_property["neighbourhood"]
                city_name = starred_property["city"]

                st.subheader(property_group)
                st.caption(f"{neighbourhood}, {city_name}")

                mask = (
                    (ai_summary["persona"].str.lower() == persona.lower())
                    & (ai_summary["neighbourhood_cleansed"].str.lower() == neighbourhood.lower())
                    & (ai_summary["output_type"].str.lower() == "recommendation")
                )

                matches = ai_summary.loc[mask, "ai_narrative"]

                if not matches.empty:
                    narrative_dict = json.loads(matches.iloc[0])

                    recommendation_summary = narrative_dict.get(
                        "recommendation_summary",
                        narrative_dict.get(
                            "investment_summary",
                            narrative_dict.get(
                                "summary",
                                "No recommendation summary available."
                            )
                        )
                    )

                    st.write(recommendation_summary)

                else:
                    st.warning(
                        "No AI recommendation found for this persona/neighbourhood combination."
                    )