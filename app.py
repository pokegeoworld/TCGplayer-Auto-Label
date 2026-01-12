import streamlit as st
from supabase import create_client
import io, re, base64
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="TCGplayer Auto Label", page_icon="🎴", layout="centered")

# --- 2. DATABASE CONNECTION ---
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 3. STYLING (68PX TITLE & 450PX SIDEBAR) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 450px; max-width: 450px; }
    .hero-title {
        color: #1E3A8A;
        font-size: 68px;
        font-weight: 800;
        text-align: center;
        margin-top: -40px;
        line-height: 1.1;
    }
    .hero-subtitle {
        color: #4B5563;
        font-size: 20px;
        text-align: center;
        margin-bottom: 30px;
    }
    div[data-testid="stForm"] small { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNCTIONS ---
def get_user_profile(user_id):
    try:
        res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return res.data
    except: return None

def extract_tcg_data(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    
    order_match = re.search(r"Order\s*Number:\s*([A-Z0-9\-]+)", text, re.IGNORECASE)
    order_no = order_match.group(1) if order_match else "Unknown"

    items = []
    lines = text.split('\n')
    for line in lines:
        match = re.match(r"^(\d+)\s+(Pokemon|Magic|Yu-Gi-Oh|Lorcana|Disney).*?$", line.strip(), re.IGNORECASE)
        if match:
            qty = match.group(1)
            desc = line.strip()[len(qty):].strip().strip('"').strip("'")
            items.append((qty, desc))
    return items, order_no

def create_label_pdf(items):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(4*inch, 6*inch))
    x, y, lh = 0.25*inch, 5.75*inch, 0.25*inch
    can.setFont("Helvetica-Bold", 14); can.drawString(x, y, "TCGplayer Auto Labels")
    y -= 0.5*inch
    can.setFont("Helvetica", 11)
    for qty, desc in items:
        if y < 0.8*inch:
            can.showPage(); y = 5.75*inch; can.setFont("Helvetica", 11)
        clean_desc = " ".join(desc.split())
        can.drawString(x, y, f"[{qty}x] {clean_desc}"); y -= lh
    
    can.setFont("Helvetica-Oblique", 8); can.setStrokeColorRGB(0.8, 0.8, 0.8)
    can.line(0.25*inch, 0.5*inch, 3.75*inch, 0.5*inch)
    can.drawString(0.25*inch, 0.35*inch, "Return: 36 Michael Anthony ln, Depew NY 14043")
    can.save(); packet.seek(0)
    return packet

# --- 5. AUTHENTICATION ---
if "user" not in st.session_state:
    st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-subtitle">Fast and automated thermal label printer creator for TCGplayer packing slips</p>', unsafe_allow_html=True)
    with st.sidebar.form("auth"):
        st.subheader("Account Access")
        e, p = st.text_input("Email"), st.text_input("Password", type="password")
        c1, c2 = st.columns(2)
        if c1.form_submit_button("Log In"):
            st.session_state.clear()
            try:
                res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                if res.user:
                    st.session_state.user = res.user; st.rerun()
            except: st.error("Login failed.")
        if c2.form_submit_button("Sign Up"):
            try:
                supabase.auth.sign_up({"email": e, "password": p})
                st.success("Success! Please Log In.")
            except: st.error("Signup failed.")
    st.stop()

# --- 6. MAIN DASHBOARD ---
user = st.session_state.user
profile = get_user_profile(user.id)

if not profile:
    try:
        supabase.table("profiles").insert({"id": user.id, "credits": 10}).execute()
        profile = get_user_profile(user.id)
    except: st.error("Sync error."); st.stop()

st.sidebar.write(f"Logged in: **{user.email}**")
st.sidebar.write(f"Credits: **{profile['credits']}**")
if st.sidebar.button("Log Out"):
    st.session_state.clear(); supabase.auth.sign_out(); st.rerun()

st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-subtitle">Fast and automated thermal label printer creator for TCGplayer packing slips</p>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    if profile['credits'] > 0:
        items, order_no = extract_tcg_data(uploaded_file)
        if items:
            pdf_result = create_label_pdf(items)
            filename = f"TCGplayer_{order_no}.pdf"
            
            # Deduct Credit and refresh profile to prevent over-deduction on retry
            new_c = profile['credits'] - 1
            supabase.table("profiles").update({"credits": new_c}).eq("id", user.id).execute()
            
            # Show a clear Download Button as the primary action (more reliable than script injection)
            st.success(f"Label Generated for Order {order_no}!")
            st.download_button(
                label="📥 Download Label PDF",
                data=pdf_result,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True
            )
            st.info("Click the button above if the download didn't start automatically.")
        else:
            st.error("No item data found. Check PDF format.")
    else:
        st.error("Out of credits.")
