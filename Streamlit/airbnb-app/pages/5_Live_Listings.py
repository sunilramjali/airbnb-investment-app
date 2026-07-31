# Live Listings page: bridges a recommended area to real properties for sale.
# Frontend-only preview for now — the property cards below use placeholder data.
# A future backend integration (e.g. Rightmove/Zoopla) will replace the mock
# generator with real, current listings for each recommended area.
import random

import streamlit as st
from styles import apply_theme, CORAL, CORAL_LIGHT
from nav import render_breadcrumb
import persist

st.set_page_config(page_title="Live Listings", page_icon="🏡", layout='wide')

apply_theme()

render_breadcrumb("live_listings")

st.title('Live Listings')
st.subheader('See real properties for sale in your recommended areas.')

st.info(
    "This page is a preview of the Live Listings feature. The property cards below "
    "use placeholder data — a future update will connect to a live provider (such as "
    "Rightmove or Zoopla) to show real, current listings for each recommended area.",
    icon="🚧",
)

persona = st.session_state.get('persona', None) or persist.get_persona()
starred_neighbourhoods = st.session_state.get('starred_neighbourhoods', persist.get_starred())

if not starred_neighbourhoods:
    st.warning(
        'No starred neighbourhoods yet. Go back to Area Overview and star up to '
        '3 neighbourhoods to see example listings here.'
    )
    st.stop()

area_labels = [f"{a['neighbourhood']}, {a['city']}" for a in starred_neighbourhoods]
selected_label = st.selectbox('Choose a recommended area', area_labels)
selected_area = starred_neighbourhoods[area_labels.index(selected_label)]

st.markdown(f"### Example properties for sale in {selected_area['neighbourhood']}, {selected_area['city']}")
if persona:
    st.caption(f"Match scores below are illustrative, weighted toward your {persona.replace('_', ' ')} persona.")

# ---- Mock listing generator ------------------------------------------------
# Seeded by area so the same area always shows the same example cards instead
# of reshuffling on every rerun.
PROPERTY_TYPES = ['Flat', 'Terraced House', 'Semi-Detached House', 'Maisonette']
STREET_NAMES = ['High Street', 'Church Road', 'Victoria Road', 'Mill Lane', 'Park Avenue', 'Station Road']


def generate_mock_listings(area, count=6):
    rng = random.Random(f"{area['neighbourhood']}_{area['city']}")
    listings = []
    for _ in range(count):
        bedrooms = rng.choice([1, 2, 2, 3, 3, 4])
        listings.append({
            'address': f"{rng.randint(1, 200)} {rng.choice(STREET_NAMES)}, {area['neighbourhood']}",
            'price': rng.randint(180, 650) * 1000,
            'bedrooms': bedrooms,
            'bathrooms': max(1, bedrooms - rng.choice([0, 1])),
            'property_type': rng.choice(PROPERTY_TYPES),
            'match_score': rng.randint(72, 98),
        })
    return listings


st.markdown(
    f"""
    <style>
    .listing-thumb {{
        height: 140px;
        border-radius: 8px;
        background: linear-gradient(135deg, {CORAL_LIGHT}, {CORAL});
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.04em;
        margin-bottom: 8px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

listings = generate_mock_listings(selected_area)

cols_per_row = 3
for row_start in range(0, len(listings), cols_per_row):
    row_listings = listings[row_start:row_start + cols_per_row]
    cols = st.columns(cols_per_row)
    for col, listing in zip(cols, row_listings):
        with col:
            with st.container(border=True):
                st.markdown('<div class="listing-thumb">EXAMPLE LISTING</div>', unsafe_allow_html=True)
                st.markdown(f"**£{listing['price']:,}**")
                st.write(listing['address'])
                st.caption(f"{listing['bedrooms']} bed · {listing['bathrooms']} bath · {listing['property_type']}")
                st.progress(listing['match_score'] / 100, text=f"{listing['match_score']}% match")
                st.button(
                    'View listing (coming soon)',
                    key=f"live_listing_{row_start}_{listing['address']}",
                    disabled=True,
                    use_container_width=True,
                )

st.divider()
st.caption(
    "Once connected to a live provider, these cards will show real photos, prices, "
    "and a direct link to the listing."
)
