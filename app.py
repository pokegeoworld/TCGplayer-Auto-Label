Python

import streamlit as st
from supabase import create_client
import io
import re
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

# --- 1. PAGE CONFIGURATION & STYLING ---
st.set_page_config(
    page_title="TCGplayer Auto Label", 
    page_icon="🎴",
    layout="centered",
    initial_sidebar_state="expanded"
)

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

# --- 2. DATABASE CONNECTION ---
# Ensure these keys are set in your .streamlit/secrets.toml
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
    """Parses TCGplayer Packing Slip for Qty, Name, and Set."""
    reader = PdfReader(uploaded_file)
    all_text = ""
    for page in reader.pages:
        all_text += page.extract_text() + "\n"
    
    # Common TCGplayer pattern: Quantity Name [Set Name]
    pattern = r"(\d+)\s+(.*?)\s+\[(.*?)\]"
    items = re.findall(pattern, all_text)
    return items

def create_label_pdf(items):
    """Generates a PDF layout suitable for labels."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    width, height = letter
    
    x_offset = 0.5 * inch
    y_offset = height - 0.75 * inch
    line_height = 0.3 * inch
    
    can.setFont("Helvetica-Bold", 14)
    can.drawString(x_offset, y_offset, "TCGplayer Auto Labels")
    y_offset -= 0.5 * inch
    
    can.setFont("Helvetica", 10)
    for qty, name, set_name in items:
        if y_offset < 1 * inch:
            can.showPage()
            y_offset = height - 0.75 * inch
            can.setFont("Helvetica", 10)
            
        text = f"[{qty}x] {name} - {set_name}"
        can.drawString(x_offset, y_offset, text)
        y_offset -= line_height
        
    can.save()
    packet.seek(0)
    return packet

# --- 4. AUTHENTICATION SIDEBAR ---
st.sidebar.title("Settings & Account")

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
            st.sidebar.success("Account created! Check email or Log In.")
        except Exception:
            st.sidebar.error("Signup failed.")
    st.stop()

# --- 5. LOGGED-IN VIEW ---
user = st.session_state.user
profile = get_user_profile(user.id)

if profile:
    tier = profile.get("tier", "free")
    credits = profile.get("credits", 0)
    used = profile.get("used_this_month", 0)
    
    st.sidebar.write(f"Logged in: **{user.email}**")
    st.sidebar.write(f"Plan: **{tier.upper()}**")
    st.sidebar.write(f"Credits: **{credits}**")
    
    if st.sidebar.button("Log Out"):
        st.session_state.clear()
        st.rerun()

    # --- MAIN APP INTERFACE ---
    st.markdown('<p class="title-text">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Upload TCGplayer Packing Slip (PDF)", type="pdf")
    
    if uploaded_file:
        if st.button("Generate Labels"):
            if tier == "unlimited" or credits > 0:
                with st.spinner("Processing labels..."):
                    data = extract_tcg_data(uploaded_file)
                    
                    if data:
                        pdf_output = create_label_pdf(data)
                        
                        # Update Usage in Supabase
                        new_used = used + 1
                        new_credits = credits if tier == "unlimited" else credits - 1
                        
                        supabase.table("profiles").update({
                            "used_this_month": new_used,
                            "credits": new_credits
                        }).eq("id", user.id).execute()
                        
                        st.success(f"Successfully parsed {len(data)} items!")
                        st.download_button(
                            label="📥 Download Labels PDF",
                            data=pdf_output,
                            file_name=f"TCG_Labels_{user.id[:5]}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("No items found. Please ensure this is a standard TCGplayer Packing Slip.")
            else:
                st.error("Insufficient credits. Please upgrade your plan.")
