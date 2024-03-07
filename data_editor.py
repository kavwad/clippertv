import time
import streamlit as st

from import_pdf import load_data, save_to_gcs

rider = st.radio('Choose your rider',
                 ['B', 'K'],
                 horizontal=True,
                 label_visibility='hidden')
df = load_data(rider)
df_edited = st.data_editor(df, hide_index=True, height=500)

if st.button('Save changes', type='primary'):
    save_to_gcs(rider, df_edited)
    st.success(f'Saved!', icon='🚍')
    time.sleep(3)
    st.rerun()