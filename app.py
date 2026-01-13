import streamlit as st
from supabase import create_client
import io, re, time
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

# --- 3. STYLING (HIGH-IMPACT UI + MOBILE SIDEBAR FIX) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 450px !important; max-width: 450px !important; }
    .hero-title { color: #1E3A8A; font-size: 68px !important; font-weight: 800; text-align: center; margin-top: -40px; line-height: 1.1; }
    .pricing-card { border: 2px solid #e1e4e8; padding: 40px 20px; border-radius: 15px; text-align: center; background: white; box-shadow: 0 6px 15px rgba(0,0,0,0.1); min-height: 380px; display: flex; flex-direction: column; justify-content: center; }
    .free-trial-large { font-size: 65px !important; font-weight: 900; color: #1E3A8A; line-height: 1.1; margin-bottom: 20px; }
    .big-stat { font-size: 90px !important; font-weight: 900; color: #1E3A8A; margin: 0; line-height: 1; }
    .label-text { font-size: 35px !important; font-weight: 700; color: #1E3A8A; margin-bottom: 15px; }
    .small-price { font-size: 32px !important; color: #374151; font-weight: 800; margin-top: 15px; }
    .tier-name { font-size: 26px !important; font-weight: 700; color: #9CA3AF; text-transform: uppercase; margin-bottom: 10px; }
    .sub-header { background: #3B82F6; color: white; padding: 25px; border-radius: 12px; text-align: center; font-weight: 900; margin: 40px auto 25px auto; font-size: 40px !important; text-transform: uppercase; }
    
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
    
    /* REDUCED SIZE TO PREVENT WRAPPING */
    .glitch-note-red { 
        color: #FF0000; 
        font-size: 11px; 
        font-weight: 900; 
        text-align: center; 
        margin-top: 15px; 
        border: 2px dashed #FF0000; 
        padding: 8px; 
        border-radius: 8px; 
        white-space: nowrap;
    }

    /* --- MOBILE SPECIFIC OVERRIDES --- */
    @media only screen and (max-width: 600px) {
        .hero-title { font-size: 38px !important; margin-top: 0px !important; }
        .free-trial-large { font-size: 35px !important; }
        .big-stat { font-size: 50px !important; }
        .sub-header { font-size: 24px !important; padding: 15px !important; }
        
        [data-testid="stSidebar"] { 
            min-width: 0px !important; 
            max-width: 100vw !important; 
            width: auto !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. THE DYNAMIC PDF CREATOR (STRICT 22PT BOLD NAME/ADDRESS) ---
def create_label_pdf(data, items):
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 22) 
    c.drawString(0.5 * inch, height - 1.0 * inch, data['buyer_name'])
    c.drawString(0.5 * inch, height - 1.35 * inch, data['address'])
    c.drawString(0.5 * inch, height - 1.70 * inch, data['city_state_zip'])
    
    c.setLineWidth(2); c.line(0.5 * inch, height - 2.0 * inch, 7.5 * inch, height - 2.0 * inch)
    
    c.setFont("Helvetica", 11); y_pos = height - 2.3 * inch
    c.drawString(0.5 * inch, y_pos, f"Order Date: {data['date']}")
    c.drawString(0.5 * inch, y_pos - 0.22*inch, "Shipping Method: Standard (7-10 days)")
    c.drawString(0.5 * inch, y_pos - 0.44*inch, f"Buyer Name: {data['buyer_name']}")
    c.drawString(0.5 * inch, y_pos - 0.66*inch, "Seller Name: ThePokeGeo")
    c.drawString(0.5 * inch, y_pos - 0.88*inch, f"Order Number: {data['order_no']}")
    
    y_pos -= 1.3 * inch; c.setFont("Helvetica-Bold", 12)
    c.drawString(0.5 * inch, y_pos, "Qty"); c.drawString(1.0 * inch, y_pos, "Description")
    c.drawString(6.6 * inch, y_pos, "Price"); c.drawString(7.2 * inch, y_pos, "Total")
    y_pos -= 0.1 * inch; c.setLineWidth(1); c.line(0.5 * inch, y_pos, 7.8 * inch, y_pos); y_pos -= 0.25 * inch
    
    font_name, font_size = "Helvetica", 9.5; c.setFont(font_name, font_size)
    total_qty, grand_total = 0, 0.0
    for item in items:
        wrapped_lines = simpleSplit(item['desc'], font_name, font_size, 5.3 * inch)
        needed_space = len(wrapped_lines) * 0.18 * inch
        if y_pos - needed_space < 1.0 * inch:
            c.showPage(); y_pos = height - 0.5 * inch; c.setFont(font_name, font_size)
        c.drawString(0.5 * inch, y_pos, item['qty'])
        c.drawString(6.6 * inch, y_pos, item['price']); c.drawString(7.2 * inch, y_pos, item['total'])
        for line in wrapped_lines:
            c.drawString(1.0 * inch, y_pos, line); y_pos -= 0.18 * inch
        total_qty += int(item['qty']); grand_total += float(item['total'].replace('$', '').replace(',', '')); y_pos -= 0.07 * inch
        
    y_pos -= 0.3 * inch; c.line(0.5 * inch, y_pos + 0.15 * inch, 7.8 * inch, y_pos + 0.15 * inch)
    c.setFont("Helvetica-Bold", 11); c.drawString(0.5 * inch, y_pos, f"{total_qty} Total Items") 
    c.drawString(5.8 * inch, y_pos, "Grand Total:"); c.drawString(7.2 * inch, y_pos, f"${grand_total:.2f}")
    
    # --- PROMOTIONAL TEXT ---
    y_pos -= 0.35 * inch 
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2.0, y_pos, "Try TCGplayer Auto Label for FREE at tcgplayerautolabel.streamlit.app")
    
    c.save(); packet.seek(0)
    return packet.getvalue()

# --- 5. AUTHENTICATION ---
if "user" not in st.session_state:
    try:
        session = supabase.auth.get_session()
        if session and session.user:
            st.session_state.user = session.user
            st.rerun()
    except: pass

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
        except: st.sidebar.error("Login Failed.")
    if r_col.button("Sign Up"):
        try:
            supabase.auth.sign_up({"email": u_email, "password": u_pass})
            st.sidebar.success("Account Created! Click Log In.")
        except: st.sidebar.error("Signup failed.")
    
    # "NOTE:" REMOVED HERE
    st.sidebar.markdown('<p class="glitch-note-red">⚠️ MAY NEED TO CLICK LOG IN TWICE TO SYNC PROFILE</p>', unsafe_allow_html=True)
    st.stop()

# --- 6. DATABASE HANDSHAKE ---
user = st.session_state.user

if st.query_params.get("payment") == "success":
    st.balloons()
    st.success("🎉 Payment Successful! Your credits have been updated.")
    time.sleep(1.5)
    st.query_params.clear()

profile_res = supabase.table("profiles").select("*").eq("id", user.id).execute()
profile = profile_res.data[0] if profile_res.data else None

if not profile:
    try:
        supabase.table("profiles").upsert({"id": user.id, "credits": 0, "tier": "None"}).execute()
        profile = {"id": user.id, "credits": 0, "tier": "None"}
    except:
        st.error("Profile sync in progress... please refresh page.")
        st.stop()

# --- 7. SIDEBAR USERNAME & PROFILE ---
st.sidebar.title(f"👤 {user.email}")
st.sidebar.write(f"Credits: **{profile['credits']}**")

display_tier = profile['tier'] if profile['tier'] == "VIP" else ('Active' if profile['credits'] > 0 else profile['tier'])
st.sidebar.write(f"Tier: **{display_tier}**")

st.sidebar.markdown("---")
st.sidebar.link_button("⚙️ Account Settings", "https://billing.stripe.com/p/login/28E9AV1P2anlaIO8GMbsc00")
if st.sidebar.button("🚪 Log Out"):
    st.session_state.clear()
    supabase.auth.sign_out()
    st.rerun()

# --- 8. PRICING GATE ---
if profile['credits'] == 0 and profile['tier'] == "None":
    st.markdown('<p class="hero-title">Choose Your Plan</p>', unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        st.markdown('<div class="pricing-card"><p class="free-trial-large">Free Trial</p><p class="label-text">5 Labels</p></div>', unsafe_allow_html=True)
        if st.button("Activate Free Trial"):
            supabase.table("profiles").update({"tier": "Free", "credits": 5}).eq("id", user.id).execute(); st.rerun()
    with colB:
        st.markdown('<div class="pricing-card"><p class="tier-name">Starter Pack</p><p class="big-stat">10</p><p class="label-text">Labels</p><p class="small-price">$0.50</p></div>', unsafe_allow_html=True)
        st.link_button("Buy Starter", "https://buy.stripe.com/28EeVf0KY7b97wC3msbsc03")
    
    st.markdown('<div class="sub-header">MONTHLY SUBSCRIPTIONS</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="pricing-card"><p class="tier-name">BASIC</p><p class="big-stat">50</p><p class="label-text">Labels</p><p class="small-price">$1.49/mo</p></div>', unsafe_allow_html=True); st.link_button("Choose Basic", "https://buy.stripe.com/aFafZj9hu7b9dV0f5absc02")
    with c2:
        st.markdown('<div class="pricing-card"><p class="tier-name">PRO</p><p class="big-stat">150</p><p class="label-text">Labels</p><p class="small-price">$1.99/mo</p></div>', unsafe_allow_html=True); st.link_button("Choose Pro", "https://buy.stripe.com/4gM3cx9hu1QP04a5uAbsc01")
    with c3:
        st.markdown('<div class="pricing-card"><p class="tier-name">UNLIMITED</p><p class="big-stat">∞</p><p class="label-text">Labels</p><p class="small-price">$2.99/mo</p></div>', unsafe_allow_html=True); st.link_button("Choose Unlimited", "https://buy.stripe.com/28E9AV1P2anlaIO8GMbsc00")
    st.stop()

# --- 9. DYNAMIC CREATOR VIEW ---
st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    reader = PdfReader(uploaded_file)
    text = "".join([p.extract_text() + "\n" for p in reader.pages])
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    try:
        order_no = re.search(r"Order Number:\s*([A-Z0-9\-]+)", text).group(1)
        order_date = re.search(r"(\d{2}/\d{2}/\d{4})", text).group(1)
        ship_idx = next(i for i, line in enumerate(lines) if "Ship To:" in line or "Shipping Address:" in line)
        
        data = {
            'buyer_name': lines[ship_idx + 1],
            'address': lines[ship_idx + 2],
            'city_state_zip': lines[ship_idx + 3],
            'date': order_date, 'order_no': order_no,
            'method': "Standard (7-10 days)", 'seller': "ThePokeGeo"
        }

        items = []
        item_rows = re.findall(r"(\d+)\s+(Pokemon.*?)\s+\$(\d+\.\d{2})\s+\$(\d+\.\d{2})", text, use_container_width=True)
        for qty, desc, price, total in item_rows:
            items.append({'qty': qty, 'desc': desc.replace('\n', ' ').strip(), 'price': f"${price}", 'total': f"${total}"})

        pdf_bytes = create_label_pdf(data, items)
        st.download_button(
            label=f"📥 DOWNLOAD LABEL: {order_no}",
            data=pdf_bytes, file_name=f"TCGplayer_{order_no}.pdf", mime="application/pdf", use_container_width=True,
            on_click=lambda: (supabase.table("profiles").update({"credits": profile['credits'] - 1}).eq("id", user.id).execute())
        )
    except:
        st.error("Error reading file. Ensure it is a valid TCGplayer packing slip.")
