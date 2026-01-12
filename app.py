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

# --- 3. STYLING (RESTORED STABLE LAYOUT) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 450px !important; max-width: 450px !important; }
    .hero-title { color: #1E3A8A; font-size: 68px !important; font-weight: 800; text-align: center; margin-top: -40px; line-height: 1.1; }
    .pricing-card { border: 2px solid #e1e4e8; padding: 30px 15px; border-radius: 15px; text-align: center; background: white; box-shadow: 0 4px 10px rgba(0,0,0,0.05); min-height: 350px; display: flex; flex-direction: column; justify-content: center; }
    .sub-header { background: #3B82F6; color: white; padding: 20px; border-radius: 12px; text-align: center; font-weight: 900; margin: 30px auto 20px auto; font-size: 32px !important; text-transform: uppercase; }
    
    .stDownloadButton > button {
        background-color: #1E3A8A !important;
        color: white !important;
        font-size: 24px !important;
        height: 80px !important;
        font-weight: 800 !important;
        border-radius: 12px !important;
        margin-top: 20px !important;
    }
    
    div.stButton > button, div.stLinkButton > a { 
        width: 100% !important; border-radius: 12px !important; font-weight: 800 !important; 
        height: 75px !important; font-size: 24px !important; background-color: #1E3A8A !important; 
        color: white !important; display: flex !important; align-items: center !important; 
        justify-content: center !important; text-decoration: none !important; border: none !important; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. THE PDF CREATOR (14PT FONT & ITEM LISTING) ---
def create_label_pdf(data, items):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(4*inch, 6*inch))
    
    # 1. Address Section (14pt Bold)
    can.setFont("Helvetica-Bold", 14)
    y = 5.7 * inch
    can.drawString(0.25*inch, y, data['buyer_name']); y -= 0.22*inch
    can.drawString(0.25*inch, y, data['address']); y -= 0.22*inch
    can.drawString(0.25*inch, y, data['city_state_zip']); y -= 0.3*inch
    
    can.setDash(3, 3); can.line(0.25*inch, y, 3.75*inch, y); y -= 0.2*inch; can.setDash()
    
    # 2. Metadata Section (10pt)
    can.setFont("Helvetica", 10)
    can.drawString(0.25*inch, y, f"Order Date: {data['date']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Shipping Method: {data['method']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Buyer Name: {data['buyer_name_meta']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Seller Name: {data['seller']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Order Number: {data['order_no']}"); y -= 0.2*inch
    
    can.setDash(3, 3); can.line(0.25*inch, y, 3.75*inch, y); y -= 0.2*inch; can.setDash()
    
    # 3. Packing Table
    styles = getSampleStyleSheet(); styleN = styles["BodyText"]
    styleN.fontSize = 8; styleN.leading = 9

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
    return packet.getvalue()

# --- 5. FAILSAFE DATA EXTRACTION ---
def extract_tcg_data(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "".join([p.extract_text() + "\n" for p in reader.pages])
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    try:
        # Address Extraction Logic [cite: 1, 2, 7, 8, 9]
        # Look for "Ship To:" then take next 3 lines
        ship_to_match = next((i for i, line in enumerate(lines) if "Ship To:" in line), None)
        if ship_to_match is not None:
            buyer_name = lines[ship_to_match + 1]
            address = lines[ship_to_match + 2]
            city_state_zip = lines[ship_to_match + 3]
        else:
            # Fallback for different headers
            buyer_name, address, city_state_zip = lines[0], lines[1], lines[2]

        # Metadata Logic [cite: 3, 10, 16]
        order_no = re.search(r"Order Number:\s*([A-Z0-9\-]+)", text).group(1)
        # Handle complex CSV order date
        date_match = re.search(r"Order Date:.*?\"([\d/]+)\"", text, re.DOTALL)
        order_date = date_match.group(1) if date_match else "01/12/2026"
        
        method_match = re.search(r"Shipping Method:.*?\"([\s\S]*?)\"", text, re.DOTALL)
        method = method_match.group(1).replace('\n', '').strip() if method_match else "Standard"

        # Item Extraction Logic [cite: 17]
        items = []
        # Pattern for "Qty","Desc","Price","Total"
        item_pattern = r'\"(\d+)\"\s*,\s*\"([\s\S]*?)\"\s*,\s*\"\\?\$([\d\.]+)\"\s*,\s*\"\\?\$([\d\.]+)\"'
        item_matches = re.findall(item_pattern, text)
        for m in item_matches:
            if "Total" in m[1]: continue 
            items.append({'qty': m[0], 'desc': m[1].replace('\n', ' ').strip(), 'price': f"${m[2]}", 'total': f"${m[3]}"})
        
        data = {
            'buyer_name': buyer_name,
            'address': address,
            'city_state_zip': city_state_zip,
            'buyer_name_meta': buyer_name,
            'date': order_date,
            'method': method,
            'seller': "ThePokeGeo",
            'order_no': order_no
        }
        return data, items
    except Exception as e:
        return None, None

# --- 6. AUTHENTICATION ---
if "user" not in st.session_state:
    st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    st.sidebar.title("Login / Register")
    u_email = st.sidebar.text_input("Email")
    u_pass = st.sidebar.text_input("Password", type="password")
    l_col, r_col = st.sidebar.columns(2)
    if l_col.button("Log In"):
        try:
            res = supabase.auth.sign_in_with_password({"email": u_email, "password": u_pass})
            if res.user: st.session_state.user = res.user; st.rerun() 
        except: st.sidebar.error("Login Failed.")
    if r_col.button("Sign Up"):
        try:
            supabase.auth.sign_up({"email": u_email, "password": u_pass})
            st.sidebar.success("Created! Click Log In.")
        except: st.sidebar.error("Signup failed.")
    st.stop()

# --- 7. MAIN APP DASHBOARD ---
user = st.session_state.user
profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data
if not profile:
    supabase.table("profiles").insert({"id": user.id, "credits": 5, "tier": "New"}).execute()
    profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data

st.sidebar.write(f"Credits: **{'∞' if profile['tier'] == 'Unlimited' else profile['credits']}**")
st.sidebar.link_button("⚙️ Account Settings", "https://billing.stripe.com/p/login/28E9AV1P2anlaIO8GMbsc00")
if st.sidebar.button("Log Out"): st.session_state.clear(); supabase.auth.sign_out(); st.rerun()

# --- 8. PRICING VIEW ---
if profile.get('tier') == 'New':
    st.markdown('<p class="hero-title">Choose Your Plan</p>', unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        st.markdown('<div class="pricing-card"><h3>Free Trial</h3><p>5 Labels</p></div>', unsafe_allow_html=True)
        if st.button("Activate"): supabase.table("profiles").update({"tier": "Free", "credits": 5}).eq("id", user.id).execute(); st.rerun()
    with colB:
        st.markdown('<div class="pricing-card"><h3>Starter</h3><p>10 Labels</p></div>', unsafe_allow_html=True)
        st.link_button("Buy $0.50", "https://buy.stripe.com/28EeVf0KY7b97wC3msbsc03")
    st.stop()

# --- 9. CREATOR VIEW ---
st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    h_data, i_list = extract_tcg_data(uploaded_file)
    if h_data:
        pdf_bytes = create_label_pdf(h_data, i_list)
        st.download_button(
            label=f"📥 DOWNLOAD LABEL: {h_data['order_no']}",
            data=pdf_bytes,
            file_name=f"TCGplayer_{h_data['order_no']}.pdf",
            mime="application/pdf",
            use_container_width=True,
            on_click=lambda: (supabase.table("profiles").update({"credits": profile['credits'] - 1}).eq("id", user.id).execute() if profile['tier'] != 'Unlimited' else None)
        )
    else:
        st.error("Error reading data. Please ensure this is a valid TCGplayer packing slip.")
