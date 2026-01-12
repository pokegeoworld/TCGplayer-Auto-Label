import streamlit as st

# Set page title and layout
st.set_page_config(page_title="TCGplayer Auto Label", layout="centered")

# Custom Title and Basic Color Formatting
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .title-text {
        color: #1E3A8A;
        font-size: 40px;
        font-weight: bold;
        text-align: center;
        padding-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="title-text">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)

# --- YOUR EXISTING APP CODE CONTINUES HERE ---
# Below is the fix for your specific Line 70 error
st.sidebar.success("Unlimited Access") 
import streamlit as st
from supabase import create_client
import io
import re
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit

# --- 1. DATABASE CONNECTION ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 2. CONFIGURATION ---
st.set_page_config(
    page_title="TCGplayer Auto Label", 
    page_icon="🎴",
    initial_sidebar_state="expanded"
)

# --- 3. AUTHENTICATION & BALANCES ---
st.sidebar.title("Settings & Account")

def get_user_profile(user_id):
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return response.data
    except Exception:
        return None

if "user" not in st.session_state:
    st.sidebar.subheader("Login / Signup")
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    
    col1, col2 = st.sidebar.columns(2)
    
    if col1.button("Log In"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception:
            st.sidebar.error("Invalid email or password.")
            
    if col2.button("Sign Up"):
        try:
            res = supabase.auth.sign_up({"email": email, "password": password})
            st.sidebar.success("Account created! You can now Log In.")
        except Exception:
            st.sidebar.error("Signup failed. Check Supabase Auth settings.")
    st.stop()

# --- 4. LOGGED-IN VIEW ---
user = st.session_state.user
profile = get_user_profile(user.id)

if profile:
    tier = profile.get("tier", "free")
    credits = profile.get("credits", 0)
    used = profile.get("used_this_month", 0)
    
    st.sidebar.write(f"Logged in as: **{user.email}**")
    
    can_print = False
    if tier == "unlimited":
        st.sidebar.markdown("**Plan:** UNLIMITED")
        st.sidebar.success("Unlimited Access")
