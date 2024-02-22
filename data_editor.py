import streamlit as st

from import_pdf import load_data

rider = st.radio('Choose your rider',
                 ['B', 'K'],
                 horizontal=True,
                 label_visibility='hidden')
df = load_data(rider)
st.data_editor(df, hide_index=True, height=500)
