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

# --- 3. STYLING (HIGH-IMPACT UI) ---
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

# --- 4. THE MASTER PDF CREATOR (YOUR EXACT COLAB LOGIC) ---
def create_label_pdf(all_text, order_num, order_date):
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    width, height = letter

    # Standardized Address (18PT BOLD) - Fixed for Xoua Vang as per your request
    c.setFont("Helvetica-Bold", 18)
    c.drawString(0.5 * inch, height - 1.0 * inch, "Xoua Vang")
    c.drawString(0.5 * inch, height - 1.30 * inch, "4071 E DWIGHT WAY APT 201")
    c.drawString(0.5 * inch, height - 1.60 * inch, "FRESNO, CA 93702-4469")
    
    c.setLineWidth(2)
    c.line(0.5 * inch, height - 1.9 * inch, 7.5 * inch, height - 1.9 * inch)

    # Order Summary
    c.setFont("Helvetica", 11)
    y_pos = height - 2.2 * inch
    c.drawString(0.5 * inch, y_pos, f"Order Date: {order_date}")
    c.drawString(0.5 * inch, y_pos - 0.22*inch, "Shipping Method: Standard (7-10 days)")
    c.drawString(0.5 * inch, y_pos - 0.44*inch, "Buyer Name: Xoua Vang")
    c.drawString(0.5 * inch, y_pos - 0.66*inch, "Seller Name: ThePokeGeo")
    c.drawString(0.5 * inch, y_pos - 0.88*inch, f"Order Number: {order_num}")
    
    # Items Table Header
    y_pos -= 1.3 * inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.5 * inch, y_pos, "Qty")
    c.drawString(1.0 * inch, y_pos, "Description")
    c.drawString(6.6 * inch, y_pos, "Price") 
    c.drawString(7.2 * inch, y_pos, "Total")
    
    y_pos -= 0.1 * inch
    c.setLineWidth(1)
    c.line(0.5 * inch, y_pos, 7.8 * inch, y_pos)
    y_pos -= 0.25 * inch
    
    # Item Extraction Logic
    item_rows = re.findall(r"(\d+)\s+(Pokemon.*?)\s+\$(\d+\.\d{2})\s+\$(\d+\.\d{2})", all_text, re.DOTALL)
    
    total_qty = 0
    grand_total = 0.0
    font_name, font_size = "Helvetica", 9.5
    c.setFont(font_name, font_size)
    max_desc_width = 5.3 * inch 

    for qty, desc, price, total in item_rows:
        clean_desc = desc.replace('\n', ' ').strip()
        wrapped_lines = simpleSplit(clean_desc, font_name, font_size, max_desc_width)
        
        needed_space = len(wrapped_lines) * 0.18 * inch
        if y_pos - needed_space < 1.0 * inch:
            c.showPage(); y_pos = height - 0.5 * inch; c.setFont(font_name, font_size)

        c.drawString(0.5 * inch, y_pos, qty)
        c.drawString(6.6 * inch, y_pos, f"${price}")
        c.drawString(7.2 * inch, y_pos, f"${total}")
        
        for line in wrapped_lines:
            c.drawString(1.0 * inch, y_pos, line)
            y_pos -= 0.18 * inch
        
        total_qty += int(qty)
        grand_total += float(total)
        y_pos -= 0.07 * inch

    # Totals Section
    y_pos -= 0.3 * inch
    c.line(0.5 * inch, y_pos + 0.15 * inch, 7.8 * inch, y_pos + 0.15 * inch)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.5 * inch, y_pos, f"{total_qty} Total Items") 
    c.drawString(5.8 * inch, y_pos, "Grand Total:") 
    c.drawString(7.2 * inch, y_pos, f"${grand_total:.2f}")

    c.save(); packet.seek(0)
    return packet.getvalue()

# --- 5. AUTHENTICATION ---
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

# --- 6. DATABASE HANDSHAKE ---
user = st.session_state.user
profile_res = supabase.table("profiles").select("*").eq("id", user.id).execute()
profile = profile_res.data[0] if profile_res.data else None
if not profile:
    supabase.table("profiles").insert({"id": user.id, "credits": 0, "tier": "None"}).execute()
    profile = {"id": user.id, "credits": 0, "tier": "None"}

st.sidebar.title("🎴 Account Controls")
st.sidebar.write(f"Credits: **{'∞' if profile['tier'] == 'Unlimited' else profile['credits']}**")
st.sidebar.write(f"Current Tier: **{'Active' if profile['credits'] > 0 else profile['tier']}**")
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Log Out"): st.session_state.clear(); supabase.auth.sign_out(); st.rerun()

# --- 7. PRICING GATE ---
if profile.get('credits') == 0 and profile.get('tier') in ["None", "New"]:
    st.markdown('<p class="hero-title">Choose Your Plan</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="pricing-card"><p class="big-stat">5</p><p class="label-text">Free Labels</p></div>', unsafe_allow_html=True)
        if st.button("Activate"):
            supabase.table("profiles").update({"tier": "Free", "credits": 5}).eq("id", user.id).execute(); st.rerun()
    with c2:
        st.markdown('<div class="pricing-card"><p class="tier-name">Starter</p><p class="big-stat">10</p><p class="small-price">$0.50</p></div>', unsafe_allow_html=True)
        st.link_button("Buy Pack", "https://buy.stripe.com/28EeVf0KY7b97wC3msbsc03")
    st.stop()

# --- 8. CREATOR VIEW ---
st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    reader = PdfReader(uploaded_file)
    all_text = "".join([page.extract_text() + "\n" for page in reader.pages])
    
    # Extract order metadata from text
    order_match = re.search(r"Order Number:\s*([A-Z0-9-]+)", all_text)
    order_num = order_match.group(1) if order_match else "Unknown"
    date_match = re.search(r"(\d{2}/\d{2}/\d{4})", all_text)
    order_date = date_match.group(1) if date_match else "01/12/2026"

    # Process and Download
    pdf_bytes = create_label_pdf(all_text, order_num, order_date)
    st.download_button(
        label=f"📥 DOWNLOAD LABEL PDF: {order_num}",
        data=pdf_bytes, file_name=f"TCGplayer_{order_num}.pdf", mime="application/pdf", use_container_width=True,
        on_click=lambda: (supabase.table("profiles").update({"credits": profile['credits'] - 1}).eq("id", user.id).execute() if profile['tier'] != 'Unlimited' else None)
    )
