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
# These pull from your Streamlit "Secrets" menu
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 2. CONFIGURATION ---
st.set_page_config(page_title="TCGplayer Auto Label", page_icon="🎴")

# --- 3. AUTHENTICATION & BALANCES ---
st.sidebar.title("Settings & Account")

# Helper function to get user data
def get_user_profile(user_id):
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return response.data
    except Exception:
        return None

# Simple Sidebar Login (Using Supabase Auth)
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
        except Exception as e:
            st.sidebar.error("Login failed. Check credentials.")
            
    if col2.button("Sign Up"):
        try:
            res = supabase.auth.sign_up({"email": email, "password": password})
            st.sidebar.success("Check email for confirmation link!")
        except Exception as e:
            st.sidebar.error("Signup failed.")
    st.stop()

# If logged in, show balance and plan
user = st.session_state.user
profile = get_user_profile(user.id)

if profile:
    tier = profile.get("tier", "free")
    credits = profile.get("credits", 0)
    used = profile.get("used_this_month", 0)
    
    st.sidebar.write(f"Logged in as: **{user.email}**")
    st.sidebar.markdown(f"**Current Plan:** {tier.upper()}")
    
    # Display remaining labels based on Tier
    if tier == "unlimited":
        st.sidebar.success("Unlimited Printing Active")
        can_print = True
    elif tier == "standard":
        left = 150 - used
        st.sidebar.info(f"Monthly Labels: {max(0, left)} / 150")
        can_print = left > 0
    elif tier == "basic":
        left = 50 - used
        st.sidebar.info(f"Monthly Labels: {max(0, left)} / 50")
        can_print = left > 0
    else:
        st.sidebar.info(f"Starter Credits: {credits}")
        can_print = credits > 0

    if not can_print:
        st.error("⚠️ You have reached your label limit.")
        st.info("Please upgrade your plan or purchase a $0.50 Starter Pack.")
        st.stop()
        
    if st.sidebar.button("Log Out"):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()

# --- 4. THE APP LOGIC (Label Processing) ---
st.title("🎴 TCGplayer Auto Labeler")
st.write("Upload your packing slip to generate organized pull labels.")

uploaded_file = st.file_uploader("Upload TCGplayer Packing Slip (PDF)", type="pdf")

if uploaded_file is not None:
    if st.button("Generate & Print Labels"):
        # 1. Update the Database FIRST (Charge the user)
        if profile['tier'] == 'free':
            supabase.table("profiles").update({"credits": credits - 1}).eq("id", user.id).execute()
        else:
            supabase.table("profiles").update({"used_this_month": used + 1}).eq("id", user.id).execute()
        
        # 2. Process the PDF (Your existing logic)
        # [Insert your specific PDF extraction and ReportLab logic here]
        st.success("Label processed successfully! Check your downloads.")
        
        # Trigger a rerun to update the sidebar balance
        st.rerun()    
