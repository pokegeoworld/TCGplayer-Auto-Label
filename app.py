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
    
    # Use st.form to capture the Enter key press
    with st.sidebar.form("auth_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        login_submitted = st.form_submit_button("Log In")
        signup_submitted = st.form_submit_button("Sign Up")

    if login_submitted:
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception:
            st.sidebar.error("Invalid email or password.")
            
    if signup_submitted:
        try:
            res = supabase.auth.sign_up({"email": email, "password": password})
            if res.user:
                try:
                    supabase.table("profiles").upsert({"id": res.user.id, "tier": "free", "credits": 5, "used_this_month": 0}).execute()
                    st.sidebar.success("Account created! Please Log In.")
                except Exception:
                    st.sidebar.error("Database error during signup.")
        except Exception as e:
            st.sidebar.error(f"Signup failed: {str(e)}")
    
    st.markdown('<p class="title-text">TCGplayer 4x6 Labeler</p>', unsafe_allow_html=True)
    st.info("Please log in via the sidebar to access the label generator.")
    st.stop()

# --- 5. MAIN INTERFACE ---
user = st.session_state.user
profile = get_user_profile(user.id)

# If profile is missing, try to create it once
if user and not profile:
    try:
        supabase.table("profiles").upsert({"id": user.id, "tier": "free", "credits": 5, "used_this_month": 0}).execute()
        profile = get_user_profile(user.id)
    except Exception:
        st.error("Permissions Error: Check your Supabase RLS policies.")
        st.stop()

if profile:
    tier, credits, used = profile.get("tier", "free"), profile.get("credits", 0), profile.get("used_this_month", 0)
    st.sidebar.title("Your Account")
    st.sidebar.write(f"Logged in: **{user.email}**")
    st.sidebar.write(f"Credits: **{credits}**")
    
    if st.sidebar.button("Log Out"):
        st.session_state.clear()
        st.rerun()

    st.markdown('<p class="title-text">TCGplayer 4x6 Label Creator</p>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")
    
    if uploaded_file and st.button("Generate 4x6 Labels"):
        if tier == "unlimited" or credits > 0:
            data = extract_tcg_data(uploaded_file)
            if data:
                pdf_output = create_label_pdf(data)
                try:
                    supabase.table("profiles").update({
                        "used_this_month": used + 1,
                        "credits": credits if tier == "unlimited" else credits - 1
                    }).eq("id", user.id).execute()
                    st.success(f"Parsed {len(data)} items.")
                    st.download_button("📥 Download 4x6 PDF", pdf_output, "TCG_4x6.pdf", "application/pdf")
                except Exception:
                    st.error("Failed to update credits in database.")
            else:
                st.error("No items found in PDF.")
        else:
            st.error("No credits remaining.")
