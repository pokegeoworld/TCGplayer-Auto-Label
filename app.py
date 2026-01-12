import streamlit as st
from supabase import create_client
import io
import re
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# --- 1. PAGE CONFIGURATION & STYLING ---
st.set_page_config(page_title="TCGplayer Auto Label", page_icon="🎴", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .title-text { color: #1E3A8A; font-size: 32px; font-weight: bold; text-align: center; padding-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE CONNECTION ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 3. HELPER FUNCTIONS ---
def get_user_profile(user_id):
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return response.data
    except Exception:
        return None

def extract_tcg_data(uploaded_file):
    reader = PdfReader(uploaded_file)
    all_text = ""
    for page in reader.pages:
        all_text += page.extract_text() + "\n"
    pattern = r"(\d+)\s+(.*?)\s+\[(.*?)\]"
    return re.findall(pattern, all_text)

def create_label_pdf(items):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(4*inch, 6*inch))
    x_offset, y_offset, line_height = 0.25*inch, 5.75*inch, 0.25*inch
    can.setFont("Helvetica-Bold", 12)
    can.drawString(x_offset, y_offset, "TCGplayer Label")
    y_offset -= 0.4*inch
    can.setFont("Helvetica", 10)
    for qty, name, set_name in items:
        if y_offset < 0.5*inch:
            can.showPage()
            y_offset = 5.75*inch
            can.setFont("Helvetica", 10)
        can.drawString(x_offset, y_offset, f"[{qty}x] {name} - {set_name}")
        y_offset -= line_height
    can.save()
    packet.seek(0)
    return packet

# --- 4. AUTHENTICATION LOGIC ---
if "user" not in st.session_state:
    st.sidebar.title("Login / Signup")
    
    with st.sidebar.form("auth_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        # Create two columns for buttons inside the form
        col1, col2 = st.columns(2)
        login_submitted = col1.form_submit_button("Log In")
        signup_submitted = col2.form_submit_button("Sign Up")

    if login_submitted:
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception:
            st.sidebar.error("Invalid email or password.")
            
    if signup_submitted:
        try:
            res = supabase.auth.
