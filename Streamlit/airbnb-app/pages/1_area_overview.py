# Area overview page for Airbnb investment app
import streamlit as st
import os
import pydeck as pdk
import json
from snowflake.snowpark.functions import st_x, st_y

#st.write("Checking 1 2 3")

st.set_page_config(layout = 'wide')

if 'starred_neighbourhoods' not in st.session_state:
    st.session_state['starred_neighbourhoods'] = []

if len(st.session_state['starred_neighbourhoods']) == 3:
    if st.button('Continue to Property Types'):
        st.switch_page('pages/2_property_types.py')
else:
    st.button('Continue to Property Types', disabled = True)
    st.caption('Select exactly 3 neighbourhoods before continuing.')

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()



#TITLE ---
st.title('Area Overview')
st.subheader('Select your desired city and find the best neighbourhoods based on your selected persona. Star your personal favourite 3 neighbourhoods.')

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

persona = st.session_state.get('persona', None)

if persona is None:
    st.warning('No persona selected. Please go back to the homepage and select a persona.')
    st.stop()

neighbourhoods = load_neighbourhoods(session, persona)

ai_summary = load_summary(session)

#INTERACTIVE ELEMENTS ---

city = st.sidebar.selectbox('City',('All','London','Bristol','Greater Manchester'))

if city == 'All':
    filtered_neighbourhoods = neighbourhoods
else:
    filtered_neighbourhoods = neighbourhoods[neighbourhoods['CITY'] == city]

st.session_state['neighbourhoods'] = filtered_neighbourhoods['NEIGHBOURHOOD'].tolist()

#area = st.sidebar.selectbox('Area', st.session_state['neighbourhoods'])

#VISUALISATIONS ---
#col1,col2,col3,col4,col5 = st.columns(5,border=True)

#with col1:
 #   st.metric('Average Yearly Revenue',f"£{neighbourhoods['AVERAGE_ANNUAL_REVENUE'][neighbourhoods['NEIGHBOURHOOD']==area].iloc[0]:,.0f}")
#with col2:
 #   st.metric('Average nightly price',f"£{neighbourhoods['AVERAGE_PRICE'][neighbourhoods['NEIGHBOURHOOD']==area].iloc[0]:,.2f}")
#with col3:
 #   st.metric('Number of listings',f"{neighbourhoods['LISTINGS_COUNT'][neighbourhoods['NEIGHBOURHOOD']==area].iloc[0]}")
#with col4:
 #   st.write('Nighlife Venues: TBC')
#with col5:
 #   st.write('Tourist Attractions: TBC')


acol1, acol2, acol3 = st.columns([1, 1, 1], border=True)

def find_best_neighbourhoods(index):
    if index >= len(filtered_neighbourhoods):
        st.write('No data')
        return

    row = filtered_neighbourhoods.iloc[index]

    st.header(str(index + 1) + '. ' + row['NEIGHBOURHOOD'])
    st.caption(row['CITY'])

    st.metric('Investment rank', f"{row['INVESTMENT_RANK']}")
    st.metric('Investment score', f"{row['INVESTMENT_SCORE']:,.1f}")
    st.metric('Average annual revenue', f"£{row['AVERAGE_ANNUAL_REVENUE']:,.0f}")
    st.metric('Average rating', f"{row['AVERAGE_RATING']:,.2f}")
    st.metric('POI density', f"{row['POI_DENSITY']:,.2f} per sqkm")
    st.metric('Area', f"{row['AREA']:,.2f} sqkm")

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
geojson_data, view_state = build_map_data(city, filtered_neighbourhoods)



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
        get_fill_color="[properties.is_top_three ? 0 : 255, properties.is_top_three ? 200 : 140, properties.is_top_three ? 80 : 120, 160]",
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
            tooltip={
                "text": "{name}\n"
                        "City: {city}\n"
                        "Investment Rank: {investment_rank}\n"
                        "Investment Score: {investment_score}\n"
                        "Average Annual Revenue: £{average_annual_revenue}\n"
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
        
        selected_star = {
            "neighbourhood": selected_neighbourhood,
            "city": selected_city
        }
        
        if selected_star in st.session_state['starred_neighbourhoods']:
            st.info(selected_neighbourhood + ' is already starred.')

        elif len(st.session_state['starred_neighbourhoods']) < 3:
            st.session_state['starred_neighbourhoods'].append(selected_star)
            st.rerun()
    
        else:
            st.warning('You can only star 3 neighbourhoods. Unstar one before adding another.')

        selected_properties = selected_objects[0]["properties"]

        with st.expander("Selected neighbourhood details", expanded=True):
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

            with dcol3:
                st.metric("Average bedrooms", selected_properties["average_no_bedrooms"])
                st.metric("Average rating", selected_properties["average_rating"])
                st.metric("POI count", f"{selected_properties['poi_count']:,}")
                st.metric("POI density", selected_properties["poi_density"])
            
            with dcol4:
                st.metric("Transport count", f"{selected_properties['transport_count']:,}")
                st.metric("Dining count", f"{selected_properties['dining_count']:,}")
                st.metric("Area", f"{selected_properties['area']} sqkm")

with map_col2:
    st.subheader('Starred neighbourhoods')

    starred_count = len(st.session_state['starred_neighbourhoods'])

    st.write(f'{starred_count}/3 selected')

    if starred_count < 3:
        st.info('Select 3 neighbourhoods to continue.')
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
                st.write('⭐ ' + neighbourhood)
                st.caption(city_name)
        
            with star_col2:
                if st.button('Remove', key='remove_' + city_name + '_' + neighbourhood):
                    st.session_state['starred_neighbourhoods'].remove(starred_area)
                    st.rerun()


#---
with st.bottom:
    with st.expander('AI Summary'):

        persona = st.session_state.get('persona', None)
        starred_neighbourhoods = st.session_state.get('starred_neighbourhoods', [])

        if persona is None:
            st.warning('No persona has been selected yet.')

        elif len(starred_neighbourhoods) == 0:
            st.warning('No starred neighbourhoods selected yet.')

        else:
            st.write('This is your AI summary using persona:', persona)

            for starred_area in starred_neighbourhoods:
                neighbourhood = starred_area['neighbourhood']
                city_name = starred_area['city']
            
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

