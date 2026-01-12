import streamlit as st
from supabase import create_client
import io, re, base64
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="TCGplayer Auto Label", page_icon="🎴", layout="centered")

# --- 2. DATABASE CONNECTION ---
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 3. STYLING (RESTORED HIGH-IMPACT LAYOUT) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 450px !important; max-width: 450px !important; }
    .hero-title { color: #1E3A8A; font-size: 68px !important; font-weight: 800; text-align: center; margin-top: -40px; line-height: 1.1; }
    .pricing-card { border: 2px solid #e1e4e8; padding: 40px 20px; border-radius: 15px; text-align: center; background: white; box-shadow: 0 6px 15px rgba(0,0,0,0.1); min-height: 380px; display: flex; flex-direction: column; justify-content: center; }
    .big-stat { font-size: 90px !important; font-weight: 900; color: #1E3A8A; margin: 0; line-height: 1; }
    .label-text { font-size: 35px !important; font-weight: 700; color: #1E3A8A; margin-bottom: 15px; }
    .tier-name { font-size: 26px !important; font-weight: 700; color: #9CA3AF; text-transform: uppercase; margin-bottom: 10px; }
    
    .stDownloadButton > button {
        background-color: #15803d !important;
        color: white !important;
        font-size: 24px !important;
        height: 80px !important;
        font-weight: 800 !important;
        border-radius: 12px !important;
        border: 2px solid #14532d !important;
    }
    
    div.stButton > button, div.stLinkButton > a { 
        width: 100% !important; border-radius: 12px !important; font-weight: 800 !important; 
        height: 75px !important; font-size: 24px !important; background-color: #1E3A8A !important; 
        color: white !important; display: flex !important; align-items: center !important; 
        justify-content: center !important; text-decoration: none !important; border: none !important; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. THE PDF CREATOR (STRICT 18PT BOLD LAYOUT) ---
def create_label_pdf(data, items):
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    width, height = letter
    
    # Standardized Address (18PT BOLD)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(0.5 * inch, height - 1.0 * inch, data['buyer_name'])
    c.drawString(0.5 * inch, height - 1.30 * inch, data['address'])
    c.drawString(0.5 * inch, height - 1.60 * inch, data['city_state_zip'])
    
    c.setLineWidth(2)
    c.line(0.5 * inch, height - 1.9 * inch, 7.5 * inch, height - 1.9 * inch)

    # Order Summary (11PT)
    c.setFont("Helvetica", 11)
    y_pos = height - 2.2 * inch
    c.drawString(0.5 * inch, y_pos, f"Order Date: {data['date']}")
    c.drawString(0.5 * inch, y_pos - 0.22*inch, f"Shipping Method: {data['method']}")
    c.drawString(0.5 * inch, y_pos - 0.44*inch, f"Buyer Name: {data['buyer_name']}")
    c.drawString(0.5 * inch, y_pos - 0.66*inch, f"Seller Name: {data['seller']}")
    c.drawString(0.5 * inch, y_pos - 0.88*inch, f"Order Number: {data['order_no']}")
    
    # Items Table
    y_pos -= 1.3 * inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.5 * inch, y_pos, "Qty")
    c.drawString(1.0 * inch, y_pos, "Description")
    c.drawString(6.6 * inch, y_pos, "Price") 
    c.drawString(7.2 * inch, y_pos, "Total")
    
    y_pos -= 0.1 * inch; c.setLineWidth(1); c.line(0.5 * inch, y_pos, 7.8 * inch, y_pos); y_pos -= 0.25 * inch
    
    font_name, font_size = "Helvetica", 9.5
    c.setFont(font_name, font_size)
    total_qty, grand_total = 0, 0.0

    for item in items:
        wrapped_lines = simpleSplit(item['desc'], font_name, font_size, 5.3 * inch)
        needed_space = len(wrapped_lines) * 0.18 * inch
        if y_pos - (needed_space + 0.2*inch) < 1.0 * inch:
            c.showPage(); y_pos = height - 0.5 * inch; c.setFont(font_name, font_size)

        c.drawString(0.5 * inch, y_pos, item['qty'])
        c.drawString(6.6 * inch, y_pos, item['price'])
        c.drawString(7.2 * inch, y_pos, item['total'])
        
        for line in wrapped_lines:
            c.drawString(1.0 * inch, y_pos, line)
            y_pos -= 0.18 * inch
        
        total_qty += int(item['qty'])
        grand_total += float(item['total'].replace('$', '').replace(',', ''))
        y_pos -= 0.07 * inch

    # Totals
    y_pos -= 0.3 * inch
    c.line(0.5 * inch, y_pos + 0.15 * inch, 7.8 * inch, y_pos + 0.15 * inch)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.5 * inch, y_pos, f"{total_qty} Total Items") 
    c.drawString(5.8 * inch, y_pos, "Grand Total:") 
    c.drawString(7.2 * inch, y_pos, f"${grand_total:.2f}")

    c.save(); packet.seek(0)
    return packet.getvalue()

# --- 5. ROBUST DATA EXTRACTION (Jesus/Xoua Optimized) ---
def extract_tcg_data(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "".join([p.extract_text() + "\n" for p in reader.pages])
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    try:
        # Scan for Ship To anchor
        ship_idx = next(i for i, line in enumerate(lines) if "Ship To:" in line or "Shipping Address:" in line)
        data = {
            'buyer_name': lines[ship_idx + 1],
            'address': lines[ship_idx + 2],
            'city_state_zip': lines[ship_idx + 3],
            'date': re.search(r"Order Date:.*?\"([\d/]+)\"", text, re.DOTALL).group(1),
            'order_no': re.search(r"Order Number:\s*([A-Z0-9\-]+)", text).group(1),
            'method': "Standard (7-10 days)",
            'seller': "ThePokeGeo"
        }
        # Brute Force Item Search
        items = []
        matches = re.findall(r'\"(\d+)\"\s*,\s*\"([\s\S]*?)\"\s*,\s*\"\\?\$([\d\.]+)\"\s*,\s*\"\\?\$([\d\.]+)\"', text)
        for m in matches:
            if "Total" in m[1]: continue 
            items.append({'qty': m[0], 'desc': m[1].replace('\n', ' ').strip(), 'price': f"${m[2]}", 'total': f"${m[3]}"})
        return data, items
    except: return None, None

# --- 6. AUTHENTICATION ---
if "user" not in st.session_state:
    st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    st.sidebar.title("Login / Register")
    u_email, u_pass = st.sidebar.text_input("Email"), st.sidebar.text_input("Password", type="password")
    l_col, r_col = st.sidebar.columns(2)
    if l_col.button("Log In"):
        try:
            res = supabase.auth.sign_in_with_password({"email": u_email, "password": u_pass})
            if res.user: st.session_state.user = res.user; st.rerun() 
        except: st.sidebar.error("Login Failed.")
    if r_col.button("Sign Up"):
        try: supabase.auth.sign_up({"email": u_email, "password": u_pass}); st.sidebar.success("Created! Click Log In.")
        except: st.sidebar.error("Signup failed.")
    st.stop()

# --- 7. DATABASE HANDSHAKE ---
user = st.session_state.user
profile_res = supabase.table("profiles").select("*").eq("id", user.id).execute()
profile = profile_res.data[0] if profile_res.data else None

if not profile:
    supabase.table("profiles").insert({"id": user.id, "credits": 0, "tier": "None"}).execute()
    profile = {"id": user.id, "credits": 0, "tier": "None"}

st.sidebar.title("🎴 Account Controls")
st.sidebar.write(f"Credits: **{'∞' if profile['tier'] == 'Unlimited' else profile['credits']}**")
st.sidebar.write(f"Current Tier: **{profile['tier'] if profile['credits'] == 0 else 'Active'}**")
st.sidebar.markdown("---")
st.sidebar.link_button("⚙️ Billing Settings", "https://billing.stripe.com/p/login/28E9AV1P2anlaIO8GMbsc00")
if st.sidebar.button("Log Out"): st.session_state.clear(); supabase.auth.sign_out(); st.rerun()

# --- 8. PRICING GATE (ONLY IF 0 CREDITS & NO PLAN) ---
if profile.get('credits') == 0 and profile.get('tier') in ["None", "New"]:
    st.markdown('<p class="hero-title">Choose Your Plan</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="pricing-card"><p class="label-text">Free Trial</p><p class="big-stat">5</p></div>', unsafe_allow_html=True)
        if st.button("Activate Free Trial"):
            supabase.table("profiles").update({"tier": "Free", "credits": 5}).eq("id", user.id).execute(); st.rerun()
    with c2:
        st.markdown('<div class="pricing-card"><p class="tier-name">Starter</p><p class="big-stat">10</p><p class="small-price">$0.50</p></div>', unsafe_allow_html=True)
        st.link_button("Buy Starter", "https://buy.stripe.com/28EeVf0KY7b97wC3msbsc03")
    st.stop()

# --- 9. CREATOR VIEW ---
st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    h_data, i_list = extract_tcg_data(uploaded_file)
    if h_data:
        # Fixed: Generate bytes only once and pass directly
        label_bytes = create_label_pdf(h_data, i_list)
        st.download_button(
            label=f"📥 DOWNLOAD LABEL PDF: {h_data['order_no']}",
            data=label_bytes, 
            file_name=f"TCGplayer_{h_data['order_no']}.pdf", 
            mime="application/pdf", 
            use_container_width=True,
            on_click=lambda: (supabase.table("profiles").update({"credits": profile['credits'] - 1}).eq("id", user.id).execute() if profile['tier'] != 'Unlimited' else None)
        )
    else:
        st.error("Could not extract data from PDF. Please ensure it is a valid TCGplayer packing slip.")
