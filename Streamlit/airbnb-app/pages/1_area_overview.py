import streamlit as st
import os
import pydeck as pdk
import json
from snowflake.snowpark.functions import st_x, st_y

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

st.set_page_config(layout = 'wide')

#TITLE ---

st.title('Area Overview')
st.subheader('Use the filters in the sidebar and find the best area for your investment')

#SQL QUERY ---
@st.cache_data(ttl=300)
def load_neighbourhoods(_session):
    return _session.sql(
    """
        SELECT CASE
                WHEN l._filename ILIKE '%london%' THEN 'London'
                WHEN l._filename ILIKE '%bristol%' THEN 'Bristol'
                WHEN l._filename ILIKE '%manchester%' THEN 'Manchester'
                ELSE 'No city'
            END as city,
            l.neighbourhood,
            avg(l.price) as average_price,
            avg(l.estimated_revenue_l365d) as average_annual_revenue,
            count(l.listing_id) as listings_count,
            ANY_VALUE(ST_ASGEOJSON(n.boundary)) as BOUNDARY,
            ANY_VALUE(ST_Y(ST_CENTROID(n.boundary))) as lat,
            ANY_VALUE(ST_X(ST_CENTROID(n.boundary))) as lon,
            row_number() over (order by average_annual_revenue desc, average_price asc) as investment_rank
        FROM AIRBNB_INVESTMENT_DB.SILVER."LISTINGS_CLEANED" l
        JOIN AIRBNB_INVESTMENT_DB.SILVER."NEIGHBOURHOODS_GEO_CLEANED" n ON n.neighbourhood = l.neighbourhood
        GROUP BY l.neighbourhood, city
        ORDER BY investment_rank
    """
    ).to_pandas()

#@st.cache_data(ttl=300)
#def load_summary(_session):
 #   return _session.sql(
  #  """
   #     SELECT *
    #    FROM MBRXEHU_YPB38047_AIRBNB_GOLD_SHARE.GOLD.AI_OUTPUTS
    #"""
    #).to_pandas()

neighbourhoods = load_neighbourhoods(session)

#ai_summary = load_summary(session)
#INTERACTIVE ELEMENTS ---

city = st.sidebar.selectbox('City',('All','London','Bristol','Manchester'))

if city == 'All':
    filtered_neighbourhoods = neighbourhoods
else:
    filtered_neighbourhoods = neighbourhoods[neighbourhoods['CITY'] == city]

st.session_state['neighbourhoods'] = filtered_neighbourhoods['NEIGHBOURHOOD'].tolist()

area = st.sidebar.selectbox('Area', st.session_state['neighbourhoods'])

#VISUALISATIONS ---
col1,col2,col3,col4,col5 = st.columns(5,border=True)

with col1:
    st.metric('Average Yearly Revenue',f"£{neighbourhoods['AVERAGE_ANNUAL_REVENUE'][neighbourhoods['NEIGHBOURHOOD']==area].iloc[0]:,.0f}")
with col2:
    st.metric('Average nightly price',f"£{neighbourhoods['AVERAGE_PRICE'][neighbourhoods['NEIGHBOURHOOD']==area].iloc[0]:,.2f}")
with col3:
    st.metric('Number of listings',f"{neighbourhoods['LISTINGS_COUNT'][neighbourhoods['NEIGHBOURHOOD']==area].iloc[0]}")
with col4:
    st.write('Nighlife Venues: TBC')
with col5:
    st.write('Tourist Attractions: TBC')


acol1,acol2,acol3 = st.columns([1,1,1],border=True)

def find_best_neighbourhoods(index):
    if index >= len(filtered_neighbourhoods):
        st.write('No data')
        return
    row = filtered_neighbourhoods.iloc[index]
    st.header(str(index+1)+'. '+row['NEIGHBOURHOOD'])
    #st.subheader(row['CITY'])
    st.metric('Average annual revenue', f"£{row['AVERAGE_ANNUAL_REVENUE']:,.0f}")
    st.metric('Average price charged per night', f"£{row['AVERAGE_PRICE']:,.0f}")
    st.metric('Number of listings: ', f"{row['LISTINGS_COUNT']}")

with acol1:
    find_best_neighbourhoods(0)
with acol2:
    find_best_neighbourhoods(1)
with acol3:
    find_best_neighbourhoods(2)

#Experimenting with pydeck map ---
#CALCULATE CENTROIDS FOR THE BOUNDARIES
neighbourhoods_center_lat = filtered_neighbourhoods['LAT'].mean()
neighbourhoods_center_lon = filtered_neighbourhoods['LON'].mean()

#CREATES THE JSON EACH BOUNDARY HOLDS
@st.cache_data(ttl=300)
def build_map_data(city, _filtered_df):
    features = []
    for _, row in _filtered_df.iterrows():
        geom = row["BOUNDARY"] if isinstance(row["BOUNDARY"], dict) else json.loads(row["BOUNDARY"])
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "name": row["NEIGHBOURHOOD"],
                "metric": round(row["AVERAGE_ANNUAL_REVENUE"])
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

#BUILDS MAP WITH BOUNDARIES, CORRECT ZOOM, AND PROPERTIES AS TOOLTIPS
geojson_data, view_state = build_map_data(city, filtered_neighbourhoods)

layer = pdk.Layer(
    "GeoJsonLayer",
    geojson_data,
    opacity=0.6,
    stroked=True,
    filled=True,
    extruded=False,
    get_fill_color="[255, 140, properties.metric * 2, 140]",
    get_line_color=[0, 0, 0],
    get_line_width=100,
    pickable=True,
)

st.pydeck_chart(pdk.Deck(
    map_style="dark_no_labels",
    layers=[layer],
    initial_view_state=view_state,
    tooltip={"text": "{name}\nAverage Annual Revenue: £{metric}"}
))

#---
with st.bottom:
    with st.expander('AI Summary'):
        st.write('This is your AI summary using persona:', st.session_state['persona'])

        #mask = (
         #   (ai_summary['persona'].str.lower() == st.session_state['persona'].lower())
          #  & (ai_summary['neighbourhood_cleansed'] == area)
        #)
        #matches = ai_summary.loc[mask, 'ai_narrative']

        #if not matches.empty:
         #   narrative_dict = json.loads(matches.iloc[0])
          #  investment_summary = narrative_dict.get('investment_summary', 'No investment summary available.')
           # st.write(investment_summary)
        #else:
         #   st.warning("No AI summary found for this persona/area combination.")

