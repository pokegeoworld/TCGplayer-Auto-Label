import streamlit as st
from supabase import create_client
import io
import re
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="TCGplayer Auto Label", page_icon="🎴", layout="centered")

# --- 2. DATABASE CONNECTION ---
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 3. STYLING (48PX TITLE & UI FIXES) ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .hero-title {
        color: #1E3A8A;
        font-size: 48px;
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
    /* Hides the "Press Enter to submit form" text */
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
    # Explicit 4x6 Page Size for Thermal Printers
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
    st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-subtitle">Fast and automated thermal printer label creator for TCGplayer packing slips</p>', unsafe_allow_html=True)
    
    with st.sidebar.form("auth_form"):
        st.subheader("Account Login")
        e = st.text_input("Email")
        p = st.text_input("Password", type="password")
        c1, c2 = st.columns(2)
        login_btn = c1.form_submit_button("Log In")
        signup_btn = c2.form_submit_button("Sign Up")

    if login_btn:
        try:
            res = supabase.auth.sign_in_with_password({"email": e, "password": p})
            st.session_state.user = res.user
            st.rerun()
        except: st.sidebar.error("Invalid email or password.")
            
    if signup_btn:
        try:
            # Note: Signup relies on the Database Trigger you set up in Supabase
            supabase.auth.sign_up({"email": e, "password": p})
            st.sidebar.success("Account created! You can now Log In.")
        except Exception as err: st.sidebar.error(f"Error: {str(err)}")
    
    st.info("👈 Please log in via the sidebar to start.")
    st.stop()

# --- 6. MAIN INTERFACE (Logged In) ---
user = st.session_state.user
profile = get_user_profile(user.id)

# If profile is missing, notify user to check the Database Trigger
if not profile:
    st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    st.error("Profile not found. Please ensure the Database Trigger and Function are set up in Supabase.")
    if st.sidebar.button("Log Out"):
        st.session_state.clear()
        st.rerun()
    st.stop()

# Sidebar Stats
st.sidebar.title("Your Account")
st.sidebar.write(f"**Email:** {user.email}")
st.sidebar.write(f"**Credits:** {profile.get('credits', 0)}")
if st.sidebar.button("Log Out"):
    st.session_state.clear()
    st.rerun()

# Prominent Main Title
st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-subtitle">Fast and automated thermal printer label creator for TCGplayer packing slips</p>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload TCGplayer Packing Slip PDF", type="pdf")

if uploaded_file:
    if st.button("Generate 4x6 Labels"):
        if profile.get('credits', 0) > 0 or profile.get('tier') == "unlimited":
            items = extract_tcg_data(uploaded_file)
            if items:
                pdf_bytes = create_label_pdf(items)
                try:
                    # Update credits in DB
                    is_unlimited = profile.get('tier') == "unlimited"
                    new_count = profile.get('credits', 0) if is_unlimited else profile.get('credits', 0) - 1
                    supabase.table("profiles").update({"credits": new_count}).eq("id", user.id).execute()
                    
                    st.success(f"Success! Found {len(items)} items. Download your labels below.")
                    st.download_button("📥 Download 4x6 PDF", pdf_bytes, "TCGplayer_Labels.pdf", "application/pdf")
                except Exception as e:
                    st.error(f"Credit Update Failed: {e}")
            else:
                st.error("Could not find any order items in this PDF.")
        else:
            st.error("Zero credits remaining.")
