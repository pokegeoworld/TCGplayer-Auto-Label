import streamlit as st
from supabase import create_client
import io, re, base64, time
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="TCGplayer Auto Label", page_icon="🎴", layout="centered")

# --- 2. DATABASE CONNECTION (MOVED TO SESSION STATE FOR PER-USER ISOLATION) ---
if "supabase" not in st.session_state:
    url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    st.session_state.supabase = create_client(url, key)
supabase = st.session_state.supabase

# --- 3. STYLING (PERFECTED SIDE-BY-SIDE & 14PT ADAPTATION) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 450px !important; max-width: 450px !important; }
    .hero-title { color: #1E3A8A; font-size: 68px !important; font-weight: 800; text-align: center; margin-top: -40px; line-height: 1.1; }
    .pricing-card { border: 2px solid #e1e4e8; padding: 30px 15px; border-radius: 15px; text-align: center; background: white; box-shadow: 0 4px 10px rgba(0,0,0,0.05); min-height: 350px; display: flex; flex-direction: column; justify-content: center; }
    .sub-header { background: #3B82F6; color: white; padding: 20px; border-radius: 12px; text-align: center; font-weight: 900; margin: 30px auto 20px auto; font-size: 32px !important; text-transform: uppercase; }
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
        height: 70px !important; font-size: 22px !important; background-color: #1E3A8A !important; 
        color: white !important; display: flex !important; align-items: center !important; 
        justify-content: center !important; text-decoration: none !important; border: none !important; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. THE PDF CREATOR (14PT FONT & CORRECTED TABLES) ---
def create_label_pdf(data, items):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(4*inch, 6*inch))
    can.setFont("Helvetica-Bold", 14) 
    y = 5.7 * inch
    can.drawString(0.25*inch, y, data['buyer_name']); y -= 0.22*inch
    can.drawString(0.25*inch, y, data['address']); y -= 0.22*inch
    can.drawString(0.25*inch, y, data['city_state_zip']); y -= 0.3*inch
    can.setDash(3, 3); can.line(0.25*inch, y, 3.75*inch, y); y -= 0.2*inch; can.setDash()
    can.setFont("Helvetica", 10)
    can.drawString(0.25*inch, y, f"Order Date: {data['date']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Shipping Method: {data['method']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Buyer Name: {data['buyer_name']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Seller Name: {data['seller']}"); y -= 0.15*inch
    can.drawString(0.25*inch, y, f"Order Number: {data['order_no']}"); y -= 0.2*inch
    can.setDash(3, 3); can.line(0.25*inch, y, 3.75*inch, y); y -= 0.2*inch; can.setDash()
    styles = getSampleStyleSheet(); styleN = styles["BodyText"]; styleN.fontSize = 8; styleN.leading = 9
    table_data = [["QTY", "Description", "Price", "Total"]]
    for item in items:
        p_desc = Paragraph(item['desc'], styleN)
        table_data.append([item['qty'], p_desc, item['price'], item['total']])
    table = Table(table_data, colWidths=[0.35*inch, 2.2*inch, 0.45*inch, 0.5*inch])
    table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),('VALIGN', (0,0), (-1,-1), 'TOP'),('BOTTOMPADDING', (0,0), (-1,-1), 4),('FONTSIZE', (0,0), (-1,-1), 8)]))
    w, h = table.wrapOn(can, 3.5*inch, y); table.drawOn(can, 0.25*inch, y - h); can.save(); packet.seek(0)
    return packet.getvalue()

# --- 5. EXTRACTION LOGIC ---
def extract_tcg_data(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "".join([p.extract_text() + "\n" for p in reader.pages])
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    try:
        ship_to_idx = next(i for i, line in enumerate(lines) if "Ship To:" in line)
        data = {
            'buyer_name': lines[ship_to_idx + 1],
            'address': lines[ship_to_idx + 2],
            'city_state_zip': lines[ship_to_idx + 3],
            'date': re.search(r"Order Date:\s*,\s*\"([\d/]+)\"", text).group(1),
            'method': "Standard (7-10 days)",
            'seller': "ThePokeGeo",
            'order_no': re.search(r"Order Number:\s*([A-Z0-9\-]+)", text).group(1)
        }
        items = []
        item_matches = re.findall(r'\"(\d+)\"\s*,\s*\"([\s\S]*?)\"\s*,\s*\"\\\$([\d\.]+)\"\s*,\s*\"\\\$([\d\.]+)\"', text)
        for m in item_matches:
            if "Total" in m[1]: continue
            items.append({'qty': m[0], 'desc': m[1].replace('\n', ' ').strip(), 'price': f"${m[2]}", 'total': f"${m[3]}"})
        return data, items
    except: return None, None

# --- 6. PHASE 1: AUTHENTICATION GATE ---
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
        except Exception as e:  # Narrowed for better debugging; was too broad before
            st.sidebar.error(f"Login Failed: {str(e)}")
    if r_col.button("Sign Up"):
        try:
            supabase.auth.sign_up({"email": u_email, "password": u_pass})
            st.sidebar.success("Account Created! Click Log In.")
        except Exception as e:
            st.sidebar.error(f"Signup failed: {str(e)}")
    st.stop()

# --- 7. PHASE 2: PROFILE SYNC ---
user = st.session_state.user
try:
    profile_req = supabase.table("profiles").select("*").eq("id", user.id).execute()
    if not profile_req.data:
        supabase.table("profiles").insert({"id": user.id, "credits": 5, "tier": "New"}).execute()
        profile = {"id": user.id, "credits": 5, "tier": "New"}
    else:
        profile = profile_req.data[0]
except Exception as e:
    st.error(f"Database connection lost: {str(e)}. Please log out and back in.")
    if st.button("Log Out"):
        st.session_state.clear(); supabase.auth.sign_out(); st.rerun()
    st.stop()

# --- 8. PHASE 3: PRICING GATE ---
if profile.get('tier') == 'New':
    st.markdown('<p class="hero-title">Choose Your Plan</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="pricing-card"><h3>Free Trial</h3><p>5 Labels</p></div>', unsafe_allow_html=True)
        if st.button("Activate Free Trial"):
            supabase.table("profiles").update({"tier": "Free", "credits": 5}).eq("id", user.id).execute(); st.rerun()
    with c2:
        st.markdown('<div class="pricing-card"><h3>Starter</h3><p>10 Labels</p></div>', unsafe_allow_html=True)
        st.link_button("Buy $0.50", "https://buy.stripe.com/28EeVf0KY7b97wC3msbsc03")
    
    st.markdown('<div class="sub-header">Monthly Plans</div>', unsafe_allow_html=True)
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown('<div class="pricing-card"><h4>BASIC</h4><p>50 Labels</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Basic", "https://buy.stripe.com/aFafZj9hu7b9dV0f5absc02")
    with p2:
        st.markdown('<div class="pricing-card"><h4>PRO</h4><p>150 Labels</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Pro", "https://buy.stripe.com/4gM3cx9hu1QP04a5uAbsc01")
    with p3:
        st.markdown('<div class="pricing-card"><h4>UNLIMITED</h4><p>∞</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Unlimited", "https://buy.stripe.com/28E9AV1P2anlaIO8GMbsc00")
    st.stop()

# --- 9. PHASE 4: THE CREATOR ---
st.sidebar.write(f"Credits: **{'∞' if profile['tier'] == 'Unlimited' else profile['credits']}**")
st.sidebar.link_button("⚙️ Account Settings", "https://billing.stripe.com/p/login/28E9AV1P2anlaIO8GMbsc00")
if st.sidebar.button("🚪 Log Out"): st.session_state.clear(); supabase.auth.sign_out(); st.rerun()

st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    h_data, i_list = extract_tcg_data(uploaded_file)
    if h_data:
        if profile['credits'] > 0 or profile['tier'] == 'Unlimited':
            current_order_no = h_data['order_no']
            if "label_generated" not in st.session_state or st.session_state.label_generated != current_order_no:
                final_bytes = create_label_pdf(h_data, i_list)
                st.session_state.final_bytes = final_bytes
                st.session_state.order_no = current_order_no
                st.session_state.label_generated = current_order_no
                st.session_state.auto_download_triggered = False  # Reset for new generation
                # Deduct credits on generation (aligns with auto-download)
                if profile['tier'] != 'Unlimited':
                    supabase.table("profiles").update({"credits": profile['credits'] - 1}).eq("id", user.id).execute()
                    # Refresh profile to reflect updated credits
                    profile_req = supabase.table("profiles").select("*").eq("id", user.id).execute()
                    profile = profile_req.data[0]

            # Manual download button (backup)
            st.download_button(
                label=f"📥 MANUAL DOWNLOAD LABEL: {st.session_state.order_no}",
                data=st.session_state.final_bytes,
                file_name=f"TCGplayer_{st.session_state.order_no}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

            # Auto-download trigger (runs once per generation)
            if not st.session_state.auto_download_triggered:
                b64 = base64.b64encode(st.session_state.final_bytes).decode()
                filename = f"TCGplayer_{st.session_state.order_no}"
                st.markdown(f"""<a href="data:application/pdf;base64,{b64}" download="{filename}.pdf" id="hidden-download-link" style="display:none;">Auto Download</a>""", unsafe_allow_html=True)
                st.markdown("""<script>document.getElementById('hidden-download-link').click();</script>""", unsafe_allow_html=True)
                st.session_state.auto_download_triggered = True
        else:
            st.error("Out of credits! Please upgrade your plan.")
