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
    [data-testid="stSidebar"] { min-width: 450px !important; max-width: 450px !important; }
    .hero-title { color: #1E3A8A; font-size: 68px !important; font-weight: 800; text-align: center; margin-top: -40px; line-height: 1.1; }
    .pricing-card { border: 2px solid #e1e4e8; padding: 40px 20px; border-radius: 15px; text-align: center; background: white; box-shadow: 0 6px 15px rgba(0,0,0,0.1); min-height: 350px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px; }
    .sub-header { background: linear-gradient(90deg, #1E3A8A, #3B82F6); color: white; padding: 20px; border-radius: 12px; text-align: center; font-weight: 900; margin: 40px auto 25px auto; font-size: 35px !important; }
    .free-trial-title { font-size: 55px !important; font-weight: 900; color: #1E3A8A; line-height: 1.1; margin-bottom: 15px; }
    .big-stat { font-size: 85px !important; font-weight: 900; color: #1E3A8A; margin: 0; line-height: 1; }
    .label-text { font-size: 32px !important; font-weight: 700; color: #1E3A8A; margin-bottom: 10px; }
    .small-price { font-size: 30px !important; color: #374151; font-weight: 800; margin-top: 10px; }
    .tier-name { font-size: 24px !important; font-weight: 700; color: #9CA3AF; text-transform: uppercase; }
    .top-row-btn div.stButton > button, .top-row-btn div.stLinkButton > a { width: 100% !important; border-radius: 12px !important; font-weight: 800 !important; height: 70px !important; font-size: 22px !important; background-color: #1E3A8A !important; color: white !important; display: flex !important; align-items: center !important; justify-content: center !important; text-decoration: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. PERFECTED PDF FUNCTION ---
def create_label_pdf(data, items):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(4*inch, 6*inch))
    can.setFont("Helvetica-Bold", 18)
    y = 5.7*inch
    can.drawString(0.25*inch, y, data['name']); y -= 0.3*inch
    can.drawString(0.25*inch, y, data['address']); y -= 0.3*inch
    can.drawString(0.25*inch, y, data['city_state_zip']); y -= 0.4*inch
    can.setFont("Helvetica", 10)
    meta = [f"Order Date: {data['date']}", f"Shipping Method: {data['method']}", f"Buyer Name: {data['name']}", f"Seller Name: {data['seller']}", f"Order Number: {data['order_no']}"]
    for line in meta:
        can.drawString(0.25*inch, y, line); y -= 0.15*inch
    y -= 0.1*inch
    can.setLineWidth(1.5); can.line(0.25*inch, y, 3.75*inch, y); y -= 0.25*inch
    can.setFont("Helvetica-Bold", 11)
    can.drawString(0.25*inch, y, "QTY"); can.drawString(0.75*inch, y, "Description"); can.drawString(3.0*inch, y, "Price"); can.drawString(3.5*inch, y, "Total"); y -= 0.2*inch
    can.setFont("Helvetica", 9)
    for item in items:
        if y < 0.5*inch: can.showPage(); y = 5.7*inch; can.setFont("Helvetica", 9)
        can.drawString(0.25*inch, y, f"{item['qty']}x")
        desc, limit = item['desc'], 2.1*inch
        words, line = desc.split(), ""
        for word in words:
            if can.stringWidth(line + word + " ", "Helvetica", 9) < limit: line += word + " "
            else:
                can.drawString(0.75*inch, y, line.strip()); y -= 0.12*inch; line = word + " "
        can.drawString(0.75*inch, y, line.strip())
        can.drawString(3.0*inch, y, item['price']); can.drawString(3.5*inch, y, item['total']); y -= 0.25*inch
    can.save(); packet.seek(0); return packet

# --- 5. DATA EXTRACTION ---
def extract_tcg_data(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "".join([p.extract_text() + "\n" for p in reader.pages])
    lines = text.split('\n')
    try:
        data = {
            'name': lines[0].replace("", "").strip(),
            'address': lines[1].replace("", "").strip(),
            'city_state_zip': lines[2].replace("", "").strip(),
            'date': re.search(r"Order Date:\s*(.*)", text).group(1).strip(),
            'method': re.search(r"Shipping Method:\s*(.*)", text).group(1).strip(),
            'seller': re.search(r"Seller Name:\s*(.*)", text).group(1).strip(),
            'order_no': re.search(r"Order Number:\s*(.*)", text).group(1).strip()
        }
        items = []
        item_matches = re.findall(r'"(\d+)"\s*,\s*"([\s\S]*?)"\s*,\s*"\s*\\\$([\d\.]+)"\s*,\s*"\s*\\\$([\d\.]+)"', text)
        for m in item_matches:
            items.append({'qty': m[0], 'desc': m[1].replace('\n', ' ').strip(), 'price': f"${m[2]}", 'total': f"${m[3]}"})
        return data, items
    except: return None, None

# --- 6. AUTHENTICATION (GLITCH-FREE LOCK) ---
if "user" not in st.session_state:
    st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    st.sidebar.title("Login / Register")
    u_email = st.sidebar.text_input("Email", key="u_email")
    u_pass = st.sidebar.text_input("Password", type="password", key="u_pass")
    l_col, r_col = st.sidebar.columns(2)
    
    if l_col.button("Log In"):
        try:
            res = supabase.auth.sign_in_with_password({"email": u_email, "password": u_pass})
            if res.user:
                st.session_state.user = res.user
                st.rerun() # Fixed: Single-click login
        except: st.sidebar.error("Login failed.")
    if r_col.button("Sign Up"):
        try:
            supabase.auth.sign_up({"email": u_email, "password": u_pass})
            st.sidebar.success("Success! Click Log In.")
        except: st.sidebar.error("Signup failed.")
    st.stop()

# --- 7. MAIN APP LOGIC ---
profile = supabase.table("profiles").select("*").eq("id", st.session_state.user.id).single().execute().data
if not profile:
    supabase.table("profiles").insert({"id": st.session_state.user.id, "credits": 5, "tier": "New"}).execute()
    profile = supabase.table("profiles").select("*").eq("id", st.session_state.user.id).single().execute().data

if st.sidebar.button("Log Out"):
    st.session_state.clear(); supabase.auth.sign_out(); st.rerun()

# --- 8. PRICING VIEW ---
if profile.get('tier') == 'New':
    st.markdown('<p class="hero-title">Choose Your Plan</p>', unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        st.markdown('<div class="pricing-card"><p class="free-trial-title">Free Trial</p><p class="label-text">5 Labels</p></div>', unsafe_allow_html=True)
        st.markdown('<div class="top-row-btn">', unsafe_allow_html=True)
        if st.button("Activate Free Trial"):
            supabase.table("profiles").update({"tier": "Free", "credits": 5}).eq("id", st.session_state.user.id).execute()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with colB:
        st.markdown('<div class="pricing-card"><p class="tier-name">Starter Pack</p><p class="big-stat">10</p><p class="label-text">Labels</p><p class="small-price">$0.50</p></div>', unsafe_allow_html=True)
        st.markdown('<div class="top-row-btn">', unsafe_allow_html=True)
        st.link_button("Buy Starter Pack", "https://buy.stripe.com/28EeVf0KY7b97wC3msbsc03")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sub-header">MONTHLY SUBSCRIPTIONS</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="pricing-card"><p class="tier-name">Basic</p><p class="big-stat">50</p><p class="label-text">Labels</p><p class="small-price">$1.49/mo</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Basic", "https://buy.stripe.com/aFafZj9hu7b9dV0f5absc02")
    with c2:
        st.markdown('<div class="pricing-card"><p class="tier-name">Pro</p><p class="big-stat">150</p><p class="label-text">Labels</p><p class="small-price">$1.99/mo</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Pro", "https://buy.stripe.com/4gM3cx9hu1QP04a5uAbsc01")
    with c3:
        st.markdown('<div class="pricing-card"><p class="tier-name">Unlimited</p><p class="big-stat">∞</p><p class="label-text">Labels</p><p class="small-price">$2.99/mo</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Unlimited", "https://buy.stripe.com/28E9AV1P2anlaIO8GMbsc00")
    st.stop()

# --- 9. CREATOR VIEW ---
st.sidebar.write(f"Plan: **{profile['tier']}** | Credits: **{'∞' if profile['tier'] == 'Unlimited' else profile['credits']}**")
st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    if profile['tier'] == 'Unlimited' or profile['credits'] > 0:
        h_data, i_list = extract_tcg_data(uploaded_file)
        if h_data:
            pdf_result = create_label_pdf(h_data, i_list)
            if f"dl_{h_data['order_no']}" not in st.session_state:
                if profile['tier'] != 'Unlimited':
                    supabase.table("profiles").update({"credits": profile['credits'] - 1}).eq("id", st.session_state.user.id).execute()
                st.session_state[f"dl_{h_data['order_no']}"] = True
                b64 = base64.b64encode(pdf_result.getvalue()).decode()
                st.components.v1.html(f'<a id="autodl" href="data:application/pdf;base64,{b64}" download="TCGplayer_{h_data["order_no"]}.pdf"></a><script>document.getElementById("autodl").click();</script>', height=0)
            st.download_button("📥 Download Label", data=pdf_result, file_name=f"TCGplayer_{h_data['order_no']}.pdf", mime="application/pdf", use_container_width=True)
