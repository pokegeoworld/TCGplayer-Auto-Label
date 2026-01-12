import streamlit as st
from supabase import create_client
import io
import re
from pypdf import PdfReader
from reportlab.pdfgen import canvas
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
        font-size: 32px;
        font-weight: bold;
        text-align: center;
        padding-bottom: 20px;
    }
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
    items = re.findall(pattern, all_text)
    return items

def create_label_pdf(items):
    packet = io.BytesIO()
    label_size = (4 * inch, 6 * inch)
    can = canvas.Canvas(packet, pagesize=label_size)
    
    x_offset = 0.25 * inch
    y_offset = 5.75 * inch
    line_height = 0.25 * inch
    
    can.setFont("Helvetica-Bold", 12)
    can.drawString(x_offset, y_offset, "TCGplayer Label")
    y_offset -= 0.4 * inch
    
    can.setFont("Helvetica", 10)
    for qty, name, set_name in items:
        if y_offset < 0.5 * inch:
            can.showPage()
            y_offset = 5.75 * inch
            can.setFont("Helvetica", 10)
            
        text = f"[{qty}x] {name} - {set_name}"
        can.drawString(x_offset, y_offset, text)
        y_offset -= line_height
        
    can.save()
    packet.seek(0)
    return packet

# --- 4. AUTHENTICATION LOGIC ---
if "user" not in st.session_state:
    st.sidebar.title("Login / Signup")
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
            st.sidebar.success("Check email or Log In.")
        except Exception:
            st.sidebar.error("Signup failed.")
    
    # Show welcome message if not logged in
    st.markdown('<p class="title-text">Welcome to TCGplayer Labeler</p>', unsafe_allow_html=True)
    st.info("Please log in via the sidebar to access the label generator.")
    st.stop()

# --- 5. MAIN INTERFACE (ONLY SHOWN IF LOGGED IN) ---
user = st.session_state.user
profile = get_user_profile(user.id)

if profile:
    tier = profile.get("tier", "free")
    credits = profile.get("credits", 0)
    used = profile.get("used_this_month", 0)
    
    # Sidebar Profile Info
    st.sidebar.title("Your Account")
    st.sidebar.write(f"Logged in: **{user.email}**")
    st.sidebar.write(f"Plan: **{tier.upper()}**")
    st.sidebar.write(f"Credits Remaining: **{credits}**")
    
    if st.sidebar.button("Log Out"):
        st.session_state.clear()
        st.rerun()

    # App Main Body
    st.markdown('<p class="title-text">TCGplayer 4x6 Label Creator</p>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Upload TCGplayer Packing Slip PDF", type="pdf")
    
    if uploaded_file:
        if st.button("Generate 4x6 Labels"):
            if tier == "unlimited" or credits > 0:
                with st.spinner("Formatting for 4x6..."):
                    data = extract_tcg_data(uploaded_file)
                    
                    if data:
                        pdf_output = create_label_pdf(data)
                        
                        # Update Usage
                        supabase.table("profiles").update({
                            "used_this_month": used + 1,
                            "credits": credits if tier == "unlimited" else credits - 1
                        }).eq("id", user.id).execute()
                        
                        st.success(f"Successfully parsed {len(data)} items for 4x6 print.")
                        st.download_button(
                            label="📥 Download 4x6 PDF",
                            data=pdf_output,
                            file_name="TCG_4x6_Labels.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("No items found in PDF. Please ensure this is a standard TCGplayer Packing Slip.")
            else:
                st.error("No credits remaining. Please upgrade your account.")
else:
    st.error("Could not load user profile. Please contact support.")
