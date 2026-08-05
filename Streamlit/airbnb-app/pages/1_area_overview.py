import streamlit as st
import pydeck as pdk
import json
from snowflake.snowpark.functions import st_x, st_y
from db import get_session
from styles import apply_theme
from nav import render_breadcrumb
import persist

st.set_page_config(page_title="Area Overview", page_icon="🏡", layout='wide')
#st.write("Checking 1 2 3")

apply_theme(bottom_panel=True)

render_breadcrumb("area_overview")

if 'starred_neighbourhoods' not in st.session_state:
    st.session_state['starred_neighbourhoods'] = persist.get_starred()

if 'selected_neighbourhood' not in st.session_state:
    st.session_state['selected_neighbourhood'] = None

session = get_session()



#TITLE ---
st.title('Area Overview')
st.subheader('Find the best neighbourhoods based on your chosen persona and cities. Star your personal favourite 3 neighbourhoods.')

#SQL QUERY ---
@st.cache_data(ttl=300)
def load_neighbourhoods(_session, persona):
    safe_persona = persona.replace("'", "''")

    return _session.sql(
    f"""
        SELECT n.CITY,
            n.NEIGHBOURHOOD,
            n.LISTING_COUNT AS listings_count,
            n.AVG_ADR AS average_adr,
            n.MEDIAN_ADR AS median_adr,
            n.AVG_OCCUPANCY_RATE as average_occupancy_rate,
            n.AVG_ANNUAL_REVENUE AS average_annual_revenue,
            n.MEDIAN_ANNUAL_REVENUE AS median_annual_revenue,
            n.MEDIAN_SALE_PRICE as median_sale_price,
            n.AVG_BEDROOMS AS average_no_bedrooms,
            n.AVG_RATING AS average_rating,
            n.POI_COUNT AS poi_count,
            n.POI_DENSITY_SQKM AS poi_density,
            n.TRANSPORT_COUNT AS transport_count,
            n.DINING_COUNT AS dining_count,
            n.AREA_SQKM AS area,
            ST_ASGEOJSON(ST_SIMPLIFY(n.BOUNDARY, 50)) as boundary,
            ST_Y(ST_CENTROID(ST_SIMPLIFY(n.BOUNDARY, 50))) as lat,
            ST_X(ST_CENTROID(ST_SIMPLIFY(n.BOUNDARY, 50))) as lon,
            l."investment_score" AS INVESTMENT_SCORE,
            ROW_NUMBER() OVER (ORDER BY l."investment_score" DESC) AS INVESTMENT_RANK
        
        FROM AIRBNB_INVESTMENT_DB.GOLD.MART_AREA_OVERVIEW n
        
        JOIN  AIRBNB_INVESTMENT_DB.GOLD.AI_OUTPUTS l
        
        ON lower(n.neighbourhood) = lower(l."neighbourhood_cleansed")

        WHERE LOWER(l."persona") = LOWER('{safe_persona}') AND lower(l."output_type") = 'area_overview'
        
        ORDER BY l."investment_score" DESC
    """
    ).to_pandas()

@st.cache_data(ttl=300)
def load_summary(_session):
    return _session.sql(
    """
        SELECT *
        FROM AIRBNB_INVESTMENT_DB.GOLD.AI_OUTPUTS
    """
    ).to_pandas()

persona = st.session_state.get('persona', None) or persist.get_persona()
st.session_state['persona'] = persona

if persona is None:
    st.warning('No persona selected. Please go back to the homepage and select a persona.')
    st.stop()

with st.spinner('Loading neighbourhoods...'):
    neighbourhoods = load_neighbourhoods(session, persona)
    ai_summary = load_summary(session)

# City selection now lives on the Get Started page; read what was chosen there.
CITIES = ["London", "Manchester", "Bristol"]
CITY_VALUES = {"London": "London", "Manchester": "Greater Manchester", "Bristol": "Bristol"}

selected_display_cities = st.session_state.get('selected_cities') or persist.get_cities(CITIES)
st.session_state['selected_cities'] = selected_display_cities

cities = [CITY_VALUES[name] for name in selected_display_cities]

if "London" in cities:
    st.warning(
        "LONDON 90-DAY RULE: Short-term lets in London are generally limited to 90 nights per calendar year unless planning permission is granted."
    )

filtered_neighbourhoods = neighbourhoods[neighbourhoods['CITY'].isin(cities)]

# Budget is set on the Get Started page; read it here.
max_budget = st.session_state.get('max_budget') or persist.get_budget(1_000_000)
st.session_state['max_budget'] = max_budget

filtered_neighbourhoods = filtered_neighbourhoods[filtered_neighbourhoods['MEDIAN_SALE_PRICE'] <= max_budget]

if filtered_neighbourhoods.empty:
    st.warning(
        f"No neighbourhoods match your budget of £{max_budget:,.0f} in the selected cities. "
        "Go back to Get Started and raise your maximum budget."
    )
    st.stop()

st.session_state['neighbourhoods'] = filtered_neighbourhoods['NEIGHBOURHOOD'].tolist()

#VISUALISATIONS ---
RANK_COLORS = {1: "#D4AF37", 2: "#A8A9AD", 3: "#CD7F32"}  # gold / silver / bronze


def rank_badge(rank):
    color = RANK_COLORS.get(rank, "#000000")
    st.markdown(
        f"""<div style='
            display: flex; align-items: center; justify-content: center;
            width: 36px; height: 36px; border-radius: 50%;
            background-color: {color}; color: white;
            font-size: 18px; font-weight: 700;
        '>{rank}</div>""",
        unsafe_allow_html=True,
    )


acol1, acol2, acol3 = st.columns([1, 1, 1], border=True)

def find_best_neighbourhoods(index):
    if index >= len(filtered_neighbourhoods):
        st.write('No data')
        return

    row = filtered_neighbourhoods.iloc[index]

    st.header(row['NEIGHBOURHOOD'])
    st.caption(row['CITY'])

    st.metric('Investment rank', f"{row['INVESTMENT_RANK']}")
    st.metric('Investment score', f"{row['INVESTMENT_SCORE']:,.1f}")
    st.metric('Median house price', f"£{row['MEDIAN_SALE_PRICE']:,.0f}")
    st.metric('Median annual revenue', f"£{row['MEDIAN_ANNUAL_REVENUE']:,.0f}")
    st.metric('Average rating', f"{row['AVERAGE_RATING']:,.2f}")
    st.metric('POI density', f"{row['POI_DENSITY']:,.2f} per sqkm")
    st.metric('Area', f"{row['AREA']:,.2f} sqkm")

with acol1:
    num_col, city_col = st.columns([1,7], border=False)

    with num_col:
        rank_badge(1)

    with city_col:
        find_best_neighbourhoods(0)

with acol2:
    num_col, city_col = st.columns([1,7], border=False)

    with num_col:
        rank_badge(2)

    with city_col:
        find_best_neighbourhoods(1)

with acol3:
    num_col, city_col = st.columns([1,7], border=False)

    with num_col:
        rank_badge(3)

    with city_col:
        find_best_neighbourhoods(2)

#Pydeck map ---
#CALCULATE CENTROIDS FOR THE BOUNDARIES
neighbourhoods_center_lat = filtered_neighbourhoods['LAT'].mean()
neighbourhoods_center_lon = filtered_neighbourhoods['LON'].mean()

#CREATES THE JSON EACH BOUNDARY HOLDS
@st.cache_data(ttl=300)
def build_map_data(cities, _filtered_df):
    features = []

    top_neighbourhoods = _filtered_df.head(3)['NEIGHBOURHOOD'].tolist()

    for _, row in _filtered_df.iterrows():
        geom = row["BOUNDARY"] if isinstance(row["BOUNDARY"], dict) else json.loads(row["BOUNDARY"])

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "name": row["NEIGHBOURHOOD"],
                "city": row["CITY"],
                "listings_count": row["LISTINGS_COUNT"],
                "average_adr": round(row["AVERAGE_ADR"]),
                "median_adr": round(row["MEDIAN_ADR"]),
                "average_occupancy_rate": round(row["AVERAGE_OCCUPANCY_RATE"], 2),
                "average_annual_revenue": round(row["AVERAGE_ANNUAL_REVENUE"]),
                "median_annual_revenue": round(row["MEDIAN_ANNUAL_REVENUE"]),
                "median_sale_price": round(row["MEDIAN_SALE_PRICE"]),
                "average_no_bedrooms": round(row["AVERAGE_NO_BEDROOMS"], 2),
                "average_rating": round(row["AVERAGE_RATING"], 2),
                "poi_count": row["POI_COUNT"],
                "poi_density": round(row["POI_DENSITY"], 2),
                "transport_count": row["TRANSPORT_COUNT"],
                "dining_count": row["DINING_COUNT"],
                "area": round(row["AREA"], 2),
                "investment_score": round(row["INVESTMENT_SCORE"], 1),
                "investment_rank": row["INVESTMENT_RANK"],
                "is_top_three": row["NEIGHBOURHOOD"] in top_neighbourhoods
            }
        })

    geojson_data = {"type": "FeatureCollection", "features": features}

    all_coords = []
    for feature in features:
        geom = feature["geometry"]

        if geom["type"] == "Polygon":
            for ring in geom["coordinates"]:
                all_coords.extend(ring)

        elif geom["type"] == "MultiPolygon":
            for polygon in geom["coordinates"]:
                for ring in polygon:
                    all_coords.extend(ring)

    if all_coords:
        view_state = pdk.data_utils.compute_view(all_coords)
        view_state.zoom = max(view_state.zoom - 0.2, 0)
    else:
        view_state = pdk.ViewState(latitude=51.5, longitude=-0.1, zoom=5)

    return geojson_data, view_state

#BUILDS MAP WITH BOUNDARIES, CORRECT ZOOM, PROPERTIES AS TOOLTIPS AND SELECTS NEIGBURHOODS INTO STARRED SECTION
geojson_data, view_state = build_map_data(tuple(cities), filtered_neighbourhoods)

st.caption('Tip: move your cursor outside the map before scrolling the page.')

map_col1, map_col2 = st.columns([3, 1], border=True)

with map_col1:
    layer = pdk.Layer(
        "GeoJsonLayer",
        geojson_data,
        id = "neighbourhood-boundaries",
        opacity=0.6,
        stroked=True,
        filled=True,
        extruded=False,
        get_fill_color="[properties.is_top_three ? 242 : 248, properties.is_top_three ? 99 : 217, properties.is_top_three ? 89 : 211, 240]",
        get_line_color=[0, 0, 0],
        get_line_width=100,
        pickable=True,
        auto_highlight = True
    )
    
    map_event = st.pydeck_chart(
        pdk.Deck(
            map_style="dark_no_labels",
            layers=[layer],
            initial_view_state=view_state,
            views=[
                pdk.View(
                    type="MapView",
                    controller={'scrollZoom': False}
                )
            ],
            tooltip={
                "text": "{name}\n"
                        "City: {city}\n"
                        "Investment Rank: {investment_rank}\n"
                        "Investment Score: {investment_score}\n"
                        "Median Annual Revenue: £{median_annual_revenue}\n"
                        "Median House Price: £{median_sale_price}\n"
                        "Average Rating: {average_rating}\n"
                        "POI Density: {poi_density}\n"
                        "Area: {area} sqkm"
            }
        ),
        height = 650,
        on_select="rerun",
        selection_mode="single-object",
        key="neighbourhood_map"
    )
    
    selected_objects = map_event.selection.objects.get("neighbourhood-boundaries", [])

    if selected_objects:
        selected_neighbourhood = selected_objects[0]["properties"]["name"]
        selected_city = selected_objects[0]["properties"]["city"]

        st.session_state['selected_neighbourhood'] = {"neighbourhood": selected_neighbourhood, "city": selected_city}
        
        selected_star = {
            "neighbourhood": selected_neighbourhood,
            "city": selected_city
        }
        
        if selected_star not in st.session_state['starred_neighbourhoods']:
            if len(st.session_state['starred_neighbourhoods']) < 3:
                st.session_state['starred_neighbourhoods'].append(selected_star)
                persist.set_starred(st.session_state['starred_neighbourhoods'])
                st.rerun()

        selected_properties = selected_objects[0]["properties"]

        with st.expander("Full analytics", expanded=True):
            dcol1, dcol2, dcol3, dcol4 = st.columns(4)

            with dcol1:
                st.metric("Investment rank", selected_properties["investment_rank"])
                st.metric("Investment score", selected_properties["investment_score"])
                st.metric("Listings", f"{selected_properties['listings_count']:,}")
                st.metric("Average nightly rate", f"£{selected_properties['average_adr']:,.0f}")

            with dcol2:
                st.metric("Median nightly rate", f"£{selected_properties['median_adr']:,.0f}")
                st.metric("Occupancy rate", selected_properties["average_occupancy_rate"])
                st.metric("Average yearly revenue", f"£{selected_properties['average_annual_revenue']:,.0f}")
                st.metric("Median yearly revenue", f"£{selected_properties['median_annual_revenue']:,.0f}")
                st.metric("Median house price", f"£{selected_properties['median_sale_price']:,.0f}")

            with dcol3:
                st.metric("Average bedrooms", selected_properties["average_no_bedrooms"])
                st.metric("Average rating", selected_properties["average_rating"])
                st.metric("POI count", f"{selected_properties['poi_count']:,}")
                st.metric("POI density", selected_properties["poi_density"])
            
            with dcol4:
                st.metric("Transport count", f"{selected_properties['transport_count']:,}")
                st.metric("Dining count", f"{selected_properties['dining_count']:,}")
                st.metric("Area", f"{selected_properties['area']} sqkm")

    else:
        st.session_state['selected_neighbourhood'] = None
                
with map_col2:
    st.subheader('Starred neighbourhoods')

    starred_count = len(st.session_state['starred_neighbourhoods'])

    st.write(f'{starred_count}/3 selected')

    if starred_count < 3:
        st.info('Select 3 neighbourhoods to continue.')
        if st.button('✨ Auto-select top 3', use_container_width=True):
            top_three = filtered_neighbourhoods.head(3)
            st.session_state['starred_neighbourhoods'] = [
                {'neighbourhood': row['NEIGHBOURHOOD'], 'city': row['CITY']}
                for _, row in top_three.iterrows()
            ]
            persist.set_starred(st.session_state['starred_neighbourhoods'])
            st.rerun()
    elif starred_count == 3:
        st.success('Ready to continue.')

    if starred_count == 0:
        st.write('No starred neighbourhoods yet.')
    else:
        for starred_area in st.session_state['starred_neighbourhoods']:
            neighbourhood = starred_area['neighbourhood']
            city_name = starred_area['city']
        
            star_col1, star_col2 = st.columns([3, 1])
        
            with star_col1:
                st.markdown(
                    f'''<div style="display:flex;align-items:center;gap:6px;">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="#F26359" stroke="#F26359">
                            <polygon points="12 2 15.09 8.63 22 9.24 17 14.14 18.18 21 12 17.77 5.82 21 7 14.14 2 9.24 8.91 8.63"/>
                        </svg>
                        {neighbourhood}
                    </div>''',
                    unsafe_allow_html=True,
                )
                st.caption(city_name)
        
            with star_col2:
                if st.button('🗑️', key='remove_' + city_name + '_' + neighbourhood):
                    st.session_state['starred_neighbourhoods'].remove(starred_area)
                    persist.set_starred(st.session_state['starred_neighbourhoods'])
                    st.rerun()
    
    if len(st.session_state['starred_neighbourhoods']) == 3:
        if st.button('Generate Analysis', use_container_width=True):
            st.switch_page('pages/1.1_area_comparison.py')
        if st.button('Continue to Property Types', use_container_width=True):
            st.switch_page('pages/2_property_types.py')
    else:
        st.button('Generate Analysis', disabled = True)
        st.button('Continue to Property Types', disabled = True)
        st.caption('Select exactly 3 neighbourhoods before continuing.')

#AI SUMMARY
with st.bottom:
        
    persona = st.session_state.get('persona', None)
    selected_area = st.session_state.get('selected_neighbourhood', None)

    if persona is None:
        st.warning('No persona has been selected yet.')

    elif selected_area is None:
        st.warning('Click a neighbourhood on the map to view its AI summary.')

    else:
        neighbourhood = selected_area['neighbourhood']
        
        st.write('This is your AI summary using persona:', persona.replace('_', ' '))
        st.header(neighbourhood)
    
        mask = (
            (ai_summary['persona'].str.lower() == persona.lower())
            & (ai_summary['neighbourhood_cleansed'].str.lower() == neighbourhood.lower())
            & (ai_summary['output_type'].str.lower() == 'area_overview')
        )
    
        matches = ai_summary.loc[mask, 'ai_narrative']
    
        if not matches.empty:
            narrative_dict = json.loads(matches.iloc[0])
            investment_summary = narrative_dict.get('investment_summary', 'No investment summary available.')
            key_strengths = narrative_dict.get('key_strengths')
            key_risks = narrative_dict.get('key_risks')
            confidence = narrative_dict.get('confidence')
            recommended_action = narrative_dict.get('recommended_action')
            st.write(investment_summary)

            with st.expander('Click for more'):
                st.caption(f"**Key Strengths**")
                st.write(f"- {key_strengths[0]}")
                st.write(f"- {key_strengths[1]}")
                st.write(f"- {key_strengths[2]}")
                
                st.caption(f"**Key Risks**")
                st.write(f"- {key_risks[0]}")
                st.write(f"- {key_risks[1]}")

                st.caption(f"**Recommended Action**")
                st.write(recommended_action)
        else:
            st.warning('No AI summary found for this persona/neighbourhood combination.')

