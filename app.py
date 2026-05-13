"""
Gasket Quote Processor — Dashboard landing page.

The original processing workspace now lives at pages/2_Quote_Workspace.py.
"""
import streamlit as st

from ui.bootstrap import init_session_state  # also runs env / secrets loading

st.set_page_config(
    page_title='Quote Pipeline — GGPL',
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='collapsed',
)

from ui.chat import render_chat_widget
from ui.dashboard import render_dashboard
from ui.history import load_history
from ui.styles import apply_global_styles

apply_global_styles()
init_session_state()
load_history()
render_dashboard()
render_chat_widget()
