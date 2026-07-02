import streamlit as st

#TITLE ---

st.title('Recommendations')

#INTERACTIVE ELEMENTS ---

property_type_selection = st.session_state['property_type_selection']

property_type_selection = st.sidebar.multiselect('property type',property_type_selection,default=property_type_selection)

#VISUALISATIONS ---