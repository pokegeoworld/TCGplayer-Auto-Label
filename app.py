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

# --- 3. STYLING (PIXEL-PERFECT BUTTONS & MASSIVE TEXT) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 450px !important; max-width: 450px !important; }
    .hero-title { color: #1E3A8A; font-size: 68px !important; font-weight: 800; text-align: center; margin-top: -40px; line-height: 1.1; }
    
    /* Pricing Card Redesign */
    .pricing-card { 
        border: 2px solid #e1e4e8; padding: 40px 20px; border-radius: 15px; 
        text-align: center; background: white; box-shadow: 0 6px 15px rgba(0,0,0,0.1); 
        min-height: 350px; display: flex; flex-direction: column; justify-content: center;
    }
    .sub-header { 
        background: linear-gradient(90deg, #1E3A8A, #3B82F6); color: white; 
        padding: 20px; border-radius: 12px; text-align: center; font-weight: 900; 
        margin: 45px auto 25px auto; font-size: 35px !important; 
    }
    
    /* FONT SCALING */
    .big-stat { font-size: 85px !important; font-weight: 900; color: #1E3A8A; margin: 0; line-height: 1; }
    .label-text { font-size: 32px !important; font-weight: 700; color: #1E3A8A; margin-bottom: 10px; }
    .small-price { font-size: 30px !important; color: #374151; font-weight: 800; margin-top: 10px; }
    .tier-name { font-size: 24px !important; font-weight: 700; color: #9CA3AF; text-transform: uppercase; }
    
    /* GLOBAL BUTTON LOCK - FORCES IDENTICAL SIZE ACROSS ALL COLS */
    div.stButton > button, div.stLinkButton > a {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        border-radius: 12px !important;
        font-weight: 800 !important;
        height: 75px !important;
        font-size: 22px !important;
        background-color: #1E3A8A !important;
        color: white !important;
        text-decoration: none !important;
        border: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. CORE LOGIC ---
def get_user_profile(user_id):
    try:
        res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return res.data
    except: return None

def extract_tcg_data(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "".join([p.extract_text() + "\n" for p in reader.pages])
    order_match = re.search(r"Order\s*Number:\s*([A-Z0-9\-]+)", text, re.IGNORECASE)
    order_no = order_match.group(1) if order_match else "Unknown"
    items = []
    for line in text.split('\n'):
        match = re.match(r"^(\d+)\s+([\w\s\'\-\,\!\.\?\(\)\#\/]+).*?$", line.strip(), re.IGNORECASE)
        if match:
            qty, desc = match.groups()
            clean_desc = re.split(r"\s+\\\$", desc)[0].strip()
            items.append((qty, clean_desc))
    return items, order_no

def create_label_pdf(items):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(4*inch, 6*inch))
    x, y = 0.25*inch, 5.7*inch
    can.setFont("Helvetica-Bold", 14); can.drawString(x, y, "TCGplayer Auto Labels")
    y -= 0.4*inch; can.setFont("Helvetica", 10)
    for qty, desc in items:
        if y < 0.5*inch: can.showPage(); y = 5.7*inch; can.setFont("Helvetica", 10)
        full_text, limit = f"[{qty}x] {desc}", 3.5 * inch
        words, line = full_text.split(), ""
        for word in words:
            if can.stringWidth(line + word + " ", "Helvetica", 10) < limit: line += word + " "
            else:
                can.drawString(x, y, line.strip()); y -= 0.15*inch; line = word + " "
        can.drawString(x, y, line.strip()); y -= 0.25*inch
    can.save(); packet.seek(0)
    return packet

def trigger_auto_download(pdf_bytes, filename):
    b64 = base64.b64encode(pdf_bytes.getvalue()).decode()
    dl_link = f"""<a id="autodl" href="data:application/pdf;base64,{b64}" download="{filename}"></a>
    <script>document.getElementById('autodl').click();</script>"""
    st.components.v1.html(dl_link, height=0)

# --- 5. AUTHENTICATION (REINFORCED 1-CLICK SUCCESS) ---
if "user" not in st.session_state:
    st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    st.sidebar.title("Login / Register")
    u_email = st.sidebar.text_input("Email")
    u_pass = st.sidebar.text_input("Password", type="password")
    l_col, r_col = st.sidebar.columns(2)
    
    if l_col.button("Log In"):
        try:
            res = supabase.auth.sign_in_with_password({"email": u_email, "password": u_pass})
            if res.user:
                st.session_state.user = res.user
                st.rerun() 
        except: st.sidebar.error("Login failed.")
    if r_col.button("Sign Up"):
        try:
            supabase.auth.sign_up({"email": u_email, "password": u_pass})
            st.sidebar.success("Success! Click Log In.")
        except: st.sidebar.error("Signup failed.")
    st.stop()

# --- 6. MAIN APP DASHBOARD ---
user = st.session_state.user
profile = get_user_profile(user.id)
if not profile:
    try:
        supabase.table("profiles").insert({"id": user.id, "credits": 5, "tier": "New"}).execute()
        profile = get_user_profile(user.id)
    except: st.error("Database sync failed."); st.stop()

if st.sidebar.button("Log Out"):
    st.session_state.clear(); supabase.auth.sign_out(); st.rerun()

# --- 7. PRICING WALL (IDENTICAL BUTTONS & NO 'ONE-TIME') ---
if profile.get('tier') == 'New':
    st.markdown('<p class="hero-title">Choose Your Plan</p>', unsafe_allow_html=True)
    
    # One-Time Section (2nd Row Buttons Lock Height)
    colA, colB = st.columns(2)
    with colA:
        st.markdown('<div class="pricing-card"><p class="tier-name">Free Trial</p><p class="big-stat">5</p><p class="label-text">Labels</p><p class="small-price">$0</p></div>', unsafe_allow_html=True)
        if st.button("Activate Free Trial"):
            supabase.table("profiles").update({"tier": "Free", "credits": 5}).eq("id", user.id).execute()
            st.rerun()
    with colB:
        st.markdown('<div class="pricing-card"><p class="tier-name">Starter Pack</p><p class="big-stat">10</p><p class="label-text">Labels</p><p class="small-price">$0.50</p></div>', unsafe_allow_html=True)
        st.link_button("Buy Starter Pack", "https://buy.stripe.com/test_5kQfZjgJ67x66ot5kW5J601")

    st.markdown('<div class="sub-header">MONTHLY SUBSCRIPTIONS</div>', unsafe_allow_html=True)
    
    # Monthly Section
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="pricing-card"><p class="tier-name">Basic</p><p class="big-stat">50</p><p class="label-text">Labels</p><p class="small-price">$1.49/mo</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Basic", "https://buy.stripe.com/test_4gM28t0K8dVueUZdRs5J602")
    with c2:
        st.markdown('<div class="pricing-card"><p class="tier-name">Pro</p><p class="big-stat">150</p><p class="label-text">Labels</p><p class="small-price">$1.99/mo</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Pro", "https://buy.stripe.com/test_bJe9AV9gE3gQeUZeVw5J603")
    with c3:
        st.markdown('<div class="pricing-card"><p class="tier-name">Unlimited</p><p class="big-stat">∞</p><p class="label-text">Labels</p><p class="small-price">$2.99/mo</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Unlimited", "https://buy.stripe.com/test_9B600ldwU5oY5kp8x85J604")
    st.stop()

# --- 8. CREATOR VIEW ---
st.sidebar.write(f"Plan: **{profile['tier']}** | Credits: **{'∞' if profile['tier'] == 'Unlimited' else profile['credits']}**")
st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    if profile['tier'] == 'Unlimited' or profile['credits'] > 0:
        items, order_no = extract_tcg_data(uploaded_file)
        if items:
            pdf_result = create_label_pdf(items)
            filename = f"TCGplayer_{order_no}.pdf"
            if f"dl_{order_no}" not in st.session_state:
                if profile['tier'] != 'Unlimited':
                    supabase.table("profiles").update({"credits": profile['credits'] - 1}).eq("id", user.id).execute()
                st.session_state[f"dl_{order_no}"] = True
                trigger_auto_download(pdf_result, filename)
            st.download_button("📥 Download Label", data=pdf_result, file_name=filename, mime="application/pdf", use_container_width=True)
