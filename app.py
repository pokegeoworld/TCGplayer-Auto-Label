import streamlit as st
from supabase import create_client
import io, re, base64
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="TCGplayer Auto Label", page_icon="🎴", layout="centered")

# --- 2. DATABASE CONNECTION ---
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 3. STYLING (REFINED BUTTONS & STABLE LAYOUT) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 450px !important; max-width: 450px !important; }
    .hero-title { color: #1E3A8A; font-size: 68px !important; font-weight: 800; text-align: center; margin-top: -40px; line-height: 1.1; }
    .pricing-card { border: 2px solid #e1e4e8; padding: 40px 20px; border-radius: 15px; text-align: center; background: white; box-shadow: 0 6px 15px rgba(0,0,0,0.1); min-height: 380px; display: flex; flex-direction: column; justify-content: center; }
    
    /* REFINED DOWNLOAD BUTTON (Darker Green, Standard Height) */
    .stDownloadButton > button {
        background-color: #15803d !important;
        color: white !important;
        font-size: 22px !important;
        height: 70px !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        border: none !important;
        margin-top: 20px !important;
    }
    
    div.stButton > button, div.stLinkButton > a { width: 100% !important; border-radius: 12px !important; font-weight: 800 !important; height: 75px !important; font-size: 24px !important; background-color: #1E3A8A !important; color: white !important; display: flex !important; align-items: center !important; justify-content: center !important; text-decoration: none !important; border: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. THE CORRECTED PDF CREATOR ---
def create_label_pdf(data, items):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(4*inch, 6*inch))
    
    # 1. Address Section (Reduced Font Size to 14pt)
    can.setFont("Helvetica-Bold", 14)
    y = 5.7 * inch
    can.drawString(0.25*inch, y, data['buyer_name']); y -= 0.22*inch
    can.drawString(0.25*inch, y, data['address']); y -= 0.22*inch
    can.drawString(0.25*inch, y, data['city_state_zip']); y -= 0.3*inch
    
    # Dash Line 1
    can.setDash(3, 3)
    can.line(0.25*inch, y, 3.75*inch, y); y -= 0.2*inch
    can.setDash()
    
    # 2. Metadata Section (10pt)
    can.setFont("Helvetica", 10)
    can.drawString(0.25*inch, y, f"Order Date: {data['date']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Shipping Method: {data['method']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Buyer Name: {data['buyer_name']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Seller Name: {data['seller']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Order Number: {data['order_no']}"); y -= 0.2*inch
    
    # Dash Line 2
    can.setDash(3, 3)
    can.line(0.25*inch, y, 3.75*inch, y); y -= 0.2*inch
    can.setDash()
    
    # 3. Packing Table (FIXED ITEM LISTING)
    styles = getSampleStyleSheet()
    styleN = styles["BodyText"]
    styleN.fontSize = 8
    styleN.leading = 9

    table_data = [["QTY", "Description", "Price", "Total"]]
    for item in items:
        p_desc = Paragraph(item['desc'], styleN)
        table_data.append([item['qty'], p_desc, item['price'], item['total']])
    
    table = Table(table_data, colWidths=[0.35*inch, 2.2*inch, 0.45*inch, 0.5*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('FONTSIZE', (0,0), (-1,-1), 8),
    ]))
    
    w, h = table.wrapOn(can, 3.5*inch, y)
    table.drawOn(can, 0.25*inch, y - h)
    
    can.save(); packet.seek(0)
    return packet

# --- 5. DATA EXTRACTION (FIXED FOR ITEM TABLES) ---
def extract_tcg_data(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "".join([p.extract_text() + "\n" for p in reader.pages])
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    try:
        ship_idx = next(i for i, line in enumerate(lines) if "Ship To:" in line)
        data = {
            'buyer_name': lines[ship_idx + 1],
            'address': lines[ship_idx + 2],
            'city_state_zip': lines[ship_idx + 3],
            'date': re.search(r"Order Date:\s*,\s*\"([\d/]+)\"", text).group(1),
            'method': re.search(r"Shipping Method:\s*,\s*\"([\s\S]*?)\"", text).group(1).strip(),
            'seller': "ThePokeGeo",
            'order_no': re.search(r"Order Number:\s*([A-Z0-9\-]+)", text).group(1)
        }
        
        # [cite_start]IMPROVED TABLE EXTRACTION [cite: 25]
        items = []
        # [cite_start]Specifically targeting the CSV-style table lines in your sample [cite: 25]
        item_matches = re.findall(r'\"(\d+)\"\s*,\s*\"([\s\S]*?)\"\s*,\s*\"\\\$([\d\.]+)\"\s*,\s*\"\\\$([\d\.]+)\"', text)
        for m in item_matches:
            # [cite_start]Skip the 'Total' summary row [cite: 25]
            if "Total" in m[1]: continue 
            items.append({'qty': m[0], 'desc': m[1].replace('\n', ' ').strip(), 'price': f"${m[2]}", 'total': f"${m[3]}"})
        
        return data, items
    except: return None, None

# --- 6. AUTHENTICATION ---
if "user" not in st.session_state:
    st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    st.sidebar.title("Login / Register")
    u_email = st.sidebar.text_input("Email")
    u_pass = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Log In"):
        res = supabase.auth.sign_in_with_password({"email": u_email, "password": u_pass})
        if res.user: st.session_state.user = res.user; st.rerun() 
    if st.sidebar.button("Sign Up"):
        supabase.auth.sign_up({"email": u_email, "password": u_pass})
        st.sidebar.success("Account Created! Click Log In.")
    st.stop()

# --- 7. MAIN APP DASHBOARD ---
user = st.session_state.user
profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
st.sidebar.link_button("⚙️ Account Settings", "https://billing.stripe.com/p/login/28E9AV1P2anlaIO8GMbsc00")
if st.sidebar.button("Log Out"): st.session_state.clear(); supabase.auth.sign_out(); st.rerun()

# --- 8. PRICING VIEW ---
if profile.get('tier') == 'New':
    st.markdown('<p class="hero-title">Choose Your Plan</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="pricing-card"><p class="free-trial-large">Free Trial</p><p class="label-text">5 Labels</p></div>', unsafe_allow_html=True)
        if st.button("Activate"): supabase.table("profiles").update({"tier": "Free", "credits": 5}).eq("id", user.id).execute(); st.rerun()
    with c2:
        st.markdown('<div class="pricing-card"><p class="tier-name">Starter</p><p class="big-stat">10</p><p class="label-text">Labels</p></div>', unsafe_allow_html=True)
        st.link_button("Buy $0.50", "https://buy.stripe.com/28EeVf0KY7b97wC3msbsc03")
    st.stop()

# --- 9. CREATOR VIEW ---
st.sidebar.write(f"Credits: **{'∞' if profile['tier'] == 'Unlimited' else profile['credits']}**")
st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    h_data, i_list = extract_tcg_data(uploaded_file)
    if h_data:
        if profile['tier'] == 'Unlimited' or profile['credits'] > 0:
            pdf_bytes = create_label_pdf(h_data, i_list)
            
            st.download_button(
                label=f"📥 DOWNLOAD LABEL PDF: {h_data['order_no']}",
                data=pdf_bytes,
                file_name=f"TCGplayer_{h_data['order_no']}.pdf",
                mime="application/pdf",
                use_container_width=True,
                on_click=lambda: (supabase.table("profiles").update({"credits": profile['credits'] - 1}).eq("id", user.id).execute() if profile['tier'] != 'Unlimited' else None)
            )
        else: st.error("Out of credits.")
