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

# Helper function to get user data from your 'profiles' table
def get_user_profile(user_id):
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return response.data
    except Exception:
        return None

# Sidebar Authentication Logic
if "user" not in st.session_state:
    st.sidebar.subheader("Login / Signup")
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    
    col1, col2 = st.sidebar.columns(2)
    
    # LOG IN BUTTON
    if col1.button("Log In"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception:
            st.sidebar.error("Invalid email or password.")
            
    # SIGN UP BUTTON
    if col2.button("Sign Up"):
        try:
            # This creates the user in Auth and triggers the 'handle_new_user' 
            # function we wrote in SQL to give them 5 free credits.
            res = supabase.auth.sign_up({"email": email, "password": password})
            st.sidebar.success("Account created! You can now Log In.")
        except Exception:
            st.sidebar.error("Signup failed. Email may already exist.")
    st.stop()

# --- 4. LOGGED-IN VIEW ---
user = st.session_state.user
profile = get_user_profile(user.id)

if profile:
    tier = profile.get("tier", "free")
    credits = profile.get("credits", 0)
    used = profile.get("used_this_month", 0)
    
    st.sidebar.write(f"Logged in as: **{user.email}**")
    st.sidebar.markdown(f"**Plan:** {tier.upper()}")
    
    # Determine remaining labels and if user is allowed to print
    can_print = False
    if tier == "unlimited":
        st.sidebar.success("Unlimited Access Active")
        can_print = True
    elif tier == "standard":
        left = 150 - used
        st.sidebar.info(f"Labels: {max(0, left)} / 150")
        can_print = left > 0
    elif tier == "basic":
        left = 50 - used
        st.sidebar.info(f"Labels: {max(0, left)} / 50")
        can_print = left > 0
    else:
        # One-time credits (Starter Pack or Free Trial)
        st.sidebar.info(f"Starter Credits: {credits}")
        can_print = credits > 0

    if not can_print:
        st.error("⚠️ Label limit reached.")
        st.info("Upgrade your plan or buy a $0.50 Starter Pack (10 Labels).")
        st.stop()
        
    if st.sidebar.button("Log Out"):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()

# --- 5. MAIN APP LOGIC ---
st.title("🎴 TCGplayer Auto Labeler")
st.write("Upload your packing slip to generate organized pull labels.")

uploaded_file = st.file_uploader("Upload TCGplayer Packing Slip (PDF)", type="pdf")

if uploaded_file is not None:
    # This button only appears/works if 'can_print' is True
    if st.button("Generate & Print Labels"):
        
        # 1. Update Database (Charge the user for usage)
        if profile['tier'] == 'free':
            # Subtract 1 from their one-time credit balance
            supabase.table("profiles").update({"credits": credits - 1}).eq("id", user.id).execute()
        else:
            # Add 1 to their monthly usage count
            supabase.table("profiles").update({"used_this_month": used + 1}).eq("id", user.id).execute()
        
        # 2. SUCCESS FEEDBACK
        st.success("Label processed! Your balance has been updated.")
        
        # Trigger a rerun so the sidebar balance updates immediately
        st.rerun()   
