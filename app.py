import streamlit as st
from supabase import create_client
import io
import re
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="TCGplayer Auto Label", page_icon="🎴", layout="centered")

url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .title-text { color: #1E3A8A; font-size: 32px; font-weight: bold; text-align: center; padding-bottom: 20px; }
    /* Hides the "Press Enter to submit form" text */
    div[data-testid="stForm"] small { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIC FUNCTIONS ---
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
    can.setFont("Helvetica-Bold", 12)
    can.drawString(x, y, "TCGplayer Label")
    y -= 0.4*inch
    can.setFont("Helvetica", 10)
    for qty, name, set_name in items:
        if y < 0.5*inch:
            can.showPage()
            y = 5.75*inch
            can.setFont("Helvetica", 10)
        can.drawString(x, y, f"[{qty}x] {name} - {set_name}")
        y -= lh
    can.save()
    packet.seek(0)
    return packet

# --- 3. AUTH SIDEBAR ---
if "user" not in st.session_state:
    with st.sidebar.form("auth_form"):
        st.title("Login / Signup")
        e, p = st.text_input("Email"), st.text_input("Password", type="password")
        c1, c2 = st.columns(2)
        login = c1.form_submit_button("Log In")
        signup = c2.form_submit_button("Sign Up")

    if login:
        try:
            res = supabase.auth.sign_in_with_password({"email": e, "password": p})
            st.session_state.user = res.user
            st.rerun()
        except: st.sidebar.error("Invalid credentials.")
    if signup:
        try:
            supabase.auth.sign_up({"email": e, "password": p})
            st.sidebar.success("Account created! Log In now.")
        except Exception as err: st.sidebar.error(f"Error: {str(err)}")
    
    st.markdown('<p class="title-text">TCGplayer 4x6 Labeler</p>', unsafe_allow_html=True)
    st.info("Log in via the sidebar to start.")
    st.stop()

# --- 4. MAIN APP ---
user = st.session_state.user
profile = get_user_profile(user.id)

# Only if the trigger failed for some reason (older accounts)
if not profile:
    try:
        supabase.table("profiles").insert({"id": user.id, "credits": 5}).execute()
        profile = get_user_profile(user.id)
    except:
        st.error("Database connection issue. Ensure RLS SQL has been run.")
        st.stop()

st.sidebar.title("Your Account")
st.sidebar.write(f"User: **{user.email}**")
st.sidebar.write(f"Credits: **{profile.get('credits', 0)}**")
if st.sidebar.button("Log Out"):
    st.session_state.clear()
    st.rerun()

st.markdown('<p class="title-text">TCGplayer 4x6 Label Creator</p>', unsafe_allow_html=True)
file = st.file_uploader("Upload Packing Slip (PDF)", type="pdf")

if file and st.button("Generate 4x6 Labels"):
    if profile.get('credits', 0) > 0 or profile.get('tier') == "unlimited":
        items = extract_tcg_data(file)
        if items:
            pdf = create_label_pdf(items)
            try:
                new_c = profile.get('credits', 0) if profile.get('tier') == "unlimited" else profile.get('credits', 0) - 1
                supabase.table("profiles").update({"credits": new_c}).eq("id", user.id).execute()
                st.success(f"Generated {len(items)} labels.")
                st.download_button("📥 Download PDF", pdf, "labels.pdf", "application/pdf")
            except Exception as e: st.error(f"Credit Update Failed: {e}")
        else: st.error("No items found.")
    else: st.error("No credits remaining.")
