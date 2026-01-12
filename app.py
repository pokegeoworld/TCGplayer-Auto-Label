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

# --- 3. STYLING ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 450px; max-width: 450px; }
    .hero-title { color: #1E3A8A; font-size: 68px; font-weight: 800; text-align: center; margin-top: -40px; line-height: 1.1; }
    .hero-subtitle { color: #4B5563; font-size: 20px; text-align: center; margin-bottom: 30px; }
    .pricing-card { border: 1px solid #ddd; padding: 20px; border-radius: 10px; text-align: center; background: #f9f9f9; height: 100%; }
    .stButton>button { width: 100%; }
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
    text = "".join([p.extract_text() + "\n" for p in reader.pages])
    order_match = re.search(r"Order\s*Number:\s*([A-Z0-9\-]+)", text, re.IGNORECASE)
    order_no = order_match.group(1) if order_match else "Unknown"
    items = []
    lines = text.split('\n')
    for line in lines:
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
    y -= 0.4*inch
    can.setFont("Helvetica", 10)
    for qty, desc in items:
        if y < 0.5*inch:
            can.showPage(); y = 5.7*inch; can.setFont("Helvetica", 10)
        full_text = f"[{qty}x] {desc}"
        limit = 3.5 * inch
        words = full_text.split()
        line = ""
        for word in words:
            if can.stringWidth(line + word + " ", "Helvetica", 10) < limit:
                line += word + " "
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

# --- 5. AUTHENTICATION ---
if "user" not in st.session_state:
    st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-subtitle">Fast and automated thermal label printer creator for TCGplayer packing slips</p>', unsafe_allow_html=True)
    with st.sidebar.form("auth"):
        e, p = st.text_input("Email"), st.text_input("Password", type="password")
        c1, c2 = st.columns(2)
        if c1.form_submit_button("Log In"):
            try:
                res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                if res.user: st.session_state.user = res.user; st.rerun()
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
        # Adjusted default to 5 credits and 'New' status
        supabase.table("profiles").insert({"id": user.id, "credits": 5, "tier": "New"}).execute()
        profile = get_user_profile(user.id)
    except: st.error("Sync error."); st.stop()

# LOGOUT BUTTON ALWAYS VISIBLE
if st.sidebar.button("Log Out"):
    st.session_state.clear(); supabase.auth.sign_out(); st.rerun()

# --- 7. PRICING WALL (If Tier is 'New') ---
if profile.get('tier') == 'New':
    st.markdown('<p class="hero-title">Choose Your Plan</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-subtitle">Select a plan to start generating labels</p>', unsafe_allow_html=True)
    
    colA, colB = st.columns(2)
    with colA:
        st.markdown('<div class="pricing-card"><h3>Free Trial</h3><h1>$0</h1><p>5 Auto Labels</p></div>', unsafe_allow_html=True)
        if st.button("Activate Free Trial"):
            supabase.table("profiles").update({"tier": "Free", "credits": 5}).eq("id", user.id).execute()
            st.rerun()
            
    with colB:
        st.markdown('<div class="pricing-card"><h3>Starter Pack</h3><h1>$0.50</h1><p>10 Auto Labels</p></div>', unsafe_allow_html=True)
        if st.button("Buy Starter Pack"):
            st.info("Redirecting to Stripe...")

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="pricing-card"><h3>Basic</h3><h1>$1.49/mo</h1><p>50 Labels/mo</p></div>', unsafe_allow_html=True)
        if st.button("Choose Basic"): st.info("Stripe Link...")
    with c2:
        st.markdown('<div class="pricing-card"><h3>Pro</h3><h1>$1.99/mo</h1><p>150 Labels/mo</p></div>', unsafe_allow_html=True)
        if st.button("Choose Pro"): st.info("Stripe Link...")
    with c3:
        st.markdown('<div class="pricing-card"><h3>Unlimited</h3><h1>$2.99/mo</h1><p>No Limits</p></div>', unsafe_allow_html=True)
        if st.button("Choose Unlimited"): st.info("Stripe Link...")
    st.stop()

# --- 8. LABEL CREATOR (If Plan Active) ---
st.sidebar.title("💳 Account")
st.sidebar.write(f"Plan: **{profile['tier']}**")
st.sidebar.write(f"Credits: **{'∞' if profile['tier'] == 'Unlimited' else profile['credits']}**")

st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    # Logic for Unlimited or remaining credits
    if profile['tier'] == 'Unlimited' or profile['credits'] > 0:
        items, order_no = extract_tcg_data(uploaded_file)
        if items:
            pdf_result = create_label_pdf(items)
            filename = f"TCGplayer_{order_no}.pdf"
            if f"last_dl_{order_no}" not in st.session_state:
                if profile['tier'] != 'Unlimited':
                    new_c = profile['credits'] - 1
                    supabase.table("profiles").update({"credits": new_c}).eq("id", user.id).execute()
                st.session_state[f"last_dl_{order_no}"] = True
                trigger_auto_download(pdf_result, filename)
            st.download_button("📥 Download Label", data=pdf_result, file_name=filename, mime="application/pdf", use_container_width=True)
        else: st.error("No item data found.")
    else: st.error("Out of credits. Please upgrade your plan.")
