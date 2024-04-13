import time
import streamlit as st

from import_pdf import load_data, categorize, save_to_gcs

# Initialize session state for df_edited and last_rider if they don't exist
if 'df_edited' not in st.session_state:
    st.session_state.df_edited = None
if 'last_rider' not in st.session_state:
    st.session_state.last_rider = ''

rider = st.radio('Choose your rider',
                 ['B', 'K'],
                 horizontal=True,
                 label_visibility='hidden')

# Check if the rider has changed since the last selection
if rider != st.session_state.last_rider:
    df = load_data(rider)
    # Update df_edited in session state with the new data
    st.session_state.df_edited = df
    # Update last_rider in session state
    st.session_state.last_rider = rider
    # Optionally, you can force a rerun here to immediately reflect changes
    # st.rerun()
else:
    # Load data only if df_edited is None (e.g., on first run)
    if st.session_state.df_edited is None:
        df = load_data(rider)
        st.session_state.df_edited = df

# Display the data editor with the current state of df_edited
df_edited_display = st.data_editor(
    st.session_state.df_edited, hide_index=True, height=500)

if st.button('Re-categorize'):
    # Update df_edited in session state with the categorized data
    st.session_state.df_edited = categorize(st.session_state.df_edited)
    # Rerun the app to reflect the changes in the UI
    st.rerun()

if st.button('Save changes', type='primary'):
    save_to_gcs(rider, st.session_state.df_edited)
    st.success('Saved!', icon='🚍')
    time.sleep(3)
    st.rerun()
