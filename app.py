import streamlit as st
from supabase import create_client
import io
import re
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="TCGplay Auto Label Creator", page_icon="🎴", layout="centered")

# --- 2. DATABASE CONNECTION ---
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 3. STYLING (68PX TITLE & UI) ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .hero-title {
        color: #1E3A8A;
        font-size: 68px;
        font-weight: 800;
        text-align: center;
        margin-top: -40px;
        padding-bottom: 5px;
        line-height: 1.1;
    }
    .hero-subtitle {
        color: #4B5563;
        font-size: 20px;
        text-align: center;
        padding-bottom: 30px;
    }
    div[data-testid="stForm"] small { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. LOGIC FUNCTIONS ---
def get_user_profile(user_id):
    try:
        res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return res.data
    except: return None

def extract_tcg_data(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "".join([p.extract_text() + "\n" for p in reader.pages])
    return re.findall(r"(\d+)\s+(.*?)\s+\[(.*?)\]", text)

def create_label_pdf(items):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(4*inch, 6*inch))
    x, y, lh = 0.25*inch, 5.75*inch, 0.25*inch
    can.setFont("Helvetica-Bold", 14)
    can.drawString(x, y, "TCGplayer Auto Labels")
    y -= 0.5*inch
    can.setFont("Helvetica", 11)
    for qty, name, set_name in items:
        if y < 0.5*inch:
            can.showPage()
            y = 5.75*inch
            can.setFont("Helvetica", 11)
        can.drawString(x, y, f"[{qty}x] {name} - {set_name}")
        y -= lh
    can.save()
    packet.seek(0)
    return packet

# --- 5. AUTHENTICATION ---
if "user" not in st.session_state:
    st.markdown('<p class="hero-title">TCGplay Auto Label Creator</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-subtitle">Fast and automated thermal label printer creator for TCGplayer packing slips</p>', unsafe_allow_html=True)
    with st.sidebar.form("auth_form"):
        st.subheader("Account Access")
        e, p = st.text_input("Email"), st.text_input("Password", type="password")
        c1, c2 = st.columns(2)
        login_btn, signup_btn = c1.form_submit_button("Log In"), c2.form_submit_button("Sign Up")

    if login_btn:
        try:
            res = supabase.auth.sign_in_with_password({"email": e, "password": p})
            st.session_state.user = res.user
            st.rerun()
        except Exception as err: st.sidebar.error(f"Login Error: {str(err)}")
    if signup_btn:
        try:
            res = supabase.auth.sign_up({"email": e, "password": p})
            if res.user:
                st.sidebar.success("Signup successful! Please log in.")
        except Exception as err: st.sidebar.error(f"Signup Error: {str(err)}")
    st.stop()

# --- 6. MAIN INTERFACE ---
user = st.session_state.user
profile = get_user_profile(user.id)

# Silent Sync for profiles
if not profile:
    try:
        supabase.table("profiles").upsert({"id": user.id, "credits": 5, "tier": "free"}).execute()
        profile = get_user_profile(user.id)
    except:
        st.markdown('<p class="hero-title">TCGplay Auto Label Creator</p>', unsafe_allow_html=True)
        st.error("Profile sync pending. Refresh in a moment.")
        if st.sidebar.button("Log Out"):
            st.session_state.clear()
            st.rerun()
        st.stop()

st.sidebar.title("Dashboard")
st.sidebar.write(f"**Credits:** {profile.get('credits', 0)}")
if st.sidebar.button("Log Out"):
    st.session_state.clear()
    st.rerun()

st.markdown('<p class="hero-title">TCGplay Auto Label Creator</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-subtitle">Fast and automated thermal label printer creator for TCGplayer packing slips</p>', unsafe_allow_html=True)

file = st.file_uploader("Upload Packing Slip PDF", type="pdf")

if file and st.button("Generate 4x6 Labels"):
    if profile.get('credits', 0) > 0:
        items = extract_tcg_data(file)
        if items:
            pdf = create_label_pdf(items)
            try:
                new_c = profile.get('credits', 0) - 1
                supabase.table("profiles").update({"credits": new_c}).eq("id", user.id).execute()
                st.success(f"Processed {len(items)} items.")
                st.download_button("📥 Download PDF", pdf, "TCG_Labels.pdf", "application/pdf")
            except: st.error("Credit update failed.")
        else: st.error("No items found.")
    else: st.error("No credits remaining.")
