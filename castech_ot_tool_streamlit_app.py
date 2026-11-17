from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="CASTECH OT Tool",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "Castech OT Tool.html"

# Keep Streamlit's own chrome out of the way so the original HTML is the interface.
st.markdown(
    """
    <style>
      #MainMenu, footer, header, [data-testid="stToolbar"],
      [data-testid="stDecoration"], [data-testid="stStatusWidget"] {display:none !important;}
      .block-container {padding:0 !important; max-width:100% !important;}
      iframe {border:0 !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

if not HTML_FILE.exists():
    st.error("The original interface file is missing. Keep 'Castech OT Tool.html' beside streamlit_app.py.")
    st.stop()

html = HTML_FILE.read_text(encoding="utf-8")

# Firebase web configuration is stored in Streamlit Cloud Secrets.
# It is a browser/client config, not a service-account private key.
firebase_config = None
try:
    raw = st.secrets.get("firebase", {})
    if raw:
        firebase_config = {
            "apiKey": raw.get("apiKey", ""),
            "authDomain": raw.get("authDomain", ""),
            "projectId": raw.get("projectId", ""),
            "storageBucket": raw.get("storageBucket", ""),
            "messagingSenderId": raw.get("messagingSenderId", ""),
            "appId": raw.get("appId", ""),
        }
        required = ("apiKey", "authDomain", "projectId", "appId")
        if not all(firebase_config.get(k) for k in required):
            firebase_config = None
except Exception:
    firebase_config = None

if firebase_config:
    # The original HTML already has Firestore + anonymous-auth sync code.
    # Supply the config it was originally expecting from its former host.
    config_js = "window.__firebase_config = " + json.dumps(firebase_config, ensure_ascii=False) + ";"
    html = html.replace("<!-- Firebase SDK Imports -->", "<script>" + config_js + "</script>\n    <!-- Firebase SDK Imports -->", 1)
    # Stable shared document ID for every visitor to this deployed website.
    html = html.replace(
        "const appId = typeof __app_id !== 'undefined' ? __app_id : 'castech-ot-tool-default';",
        "const appId = 'castech-ot-tool-shared';",
    )
    # Make the config lookup explicit in the browser global scope.
    html = html.replace(
        "if (typeof __firebase_config === 'undefined') {",
        "if (!window.__firebase_config) {",
    )
    html = html.replace(
        "const firebaseConfig = JSON.parse(__firebase_config);",
        "const firebaseConfig = window.__firebase_config;",
    )
    st.caption("CASTECH OT Tool · Shared cloud mode configured")
else:
    st.warning(
        "Cloud is not configured yet. The original interface will open, but changes will stay in this browser. "
        "Add the Firebase web configuration in Streamlit Cloud → Settings → Secrets to enable shared live data."
    )

# Render the actual uploaded HTML rather than recreating it with Streamlit widgets.
# This preserves its existing layout, tabs, dialogs, calculations, exports and interactions.
components.html(html, height=5200, scrolling=True)
