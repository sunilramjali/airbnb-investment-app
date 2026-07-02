import streamlit as st
import os

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

#TITLE ---

st.title('Property Type Overview')

#SQL QUERY ---

bristol_property_type_ranked = session.sql(
    """
        SELECT "property_type",
            avg("estimated_revenue_l365d"::numeric) as avg_revenue,
            avg("price"::numeric) as avg_price,
            avg("review_scores_rating"::numeric) as avg_rating,
            row_number() over (order by avg_revenue desc,avg_price asc,avg_rating desc) as investment_rank
        FROM PRACTICE_AIRBNB.PUBLIC."bristol_listings_clean"
        GROUP BY "property_type"
    """
).to_pandas()

#VISUALISATIONS ---
