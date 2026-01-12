import streamlit as st
from supabase import create_client
import io, re
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# ────────────────────────────────────────────────
#  PAGE CONFIG
# ────────────────────────────────────────────────
st.set_page_config(page_title="TCGplayer Auto Label", page_icon="🎴", layout="centered")

# ────────────────────────────────────────────────
#  DB CONNECTION
# ────────────────────────────────────────────────
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# ────────────────────────────────────────────────
#  STYLING
# ────────────────────────────────────────────────
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 450px !important; max-width: 450px !important; }
    .hero-title { color: #1E3A8A; font-size: 52px !important; font-weight: 800; text-align: center; margin: 10px 0 30px 0; }
    .stDownloadButton > button {
        background-color: #15803d !important;
        color: white !important;
        font-size: 20px !important;
        height: 65px !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        width: 100% !important;
        margin: 20px 0;
    }
    div.stButton > button, div.stLinkButton > a {
        width: 100% !important; border-radius: 10px !important;
        font-weight: 700 !important; height: 58px !important;
        font-size: 18px !important;
    }
    </style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────
#  PDF LABEL GENERATOR (4×6 inch)
# ────────────────────────────────────────────────
def create_label_pdf(data, items):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(4*inch, 6*inch))
    
    # Address block – 14 pt
    can.setFont("Helvetica-Bold", 14)
    y = 5.65 * inch
    can.drawString(0.25*inch, y, data['buyer_name']); y -= 0.24*inch
    can.drawString(0.25*inch, y, data['address']);     y -= 0.24*inch
    can.drawString(0.25*inch, y, data['city_state_zip']); y -= 0.32*inch

    can.setDash(3, 3); can.line(0.25*inch, y, 3.75*inch, y); y -= 0.22*inch; can.setDash()

    # Metadata – 10 pt
    can.setFont("Helvetica", 10)
    for line in [
        f"Order Date: {data['date']}",
        f"Shipping Method: {data['method']}",
        f"Buyer: {data['buyer_name']}",
        f"Seller: {data['seller']}",
        f"Order #: {data['order_no']}"
    ]:
        can.drawString(0.25*inch, y, line)
        y -= 0.16*inch

    can.setDash(3, 3); can.line(0.25*inch, y, 3.75*inch, y); y -= 0.22*inch; can.setDash()

    # Items table
    styles = getSampleStyleSheet()
    styleN = styles["BodyText"]
    styleN.fontSize = 8
    styleN.leading = 9.5

    table_data = [["QTY", "Description", "Price", "Total"]]
    for item in items:
        table_data.append([
            item['qty'],
            Paragraph(item['desc'], styleN),
            item['price'],
            item['total']
        ])

    table = Table(table_data, colWidths=[0.4*inch, 2.15*inch, 0.5*inch, 0.55*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, "#CCCCCC"),
    ]))

    w, h = table.wrapOn(can, 3.6*inch, 9999)
    table.drawOn(can, 0.25*inch, y - h - 0.1*inch)
    
    can.save()
    packet.seek(0)
    return packet.getvalue()

# ────────────────────────────────────────────────
#  PDF → DATA EXTRACTION (fixed version - no ?. operator)
# ────────────────────────────────────────────────
def extract_tcg_data(uploaded_file):
    try:
        reader = PdfReader(uploaded_file)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        ship_idx = next((i for i, line in enumerate(lines) if "Ship To:" in line), None)
        if ship_idx is None:
            return None, None, "Could not find 'Ship To:' section in the PDF"

        # Helper to safely get regex group or fallback
        def get_match(pattern, default="??"):
            m = re.search(pattern, text, re.I | re.DOTALL)
            return m.group(1).strip() if m else default

        data = {
            'buyer_name': lines[ship_idx + 1].strip() if ship_idx + 1 < len(lines) else "??",
            'address': lines[ship_idx + 2].strip() if ship_idx + 2 < len(lines) else "??",
            'city_state_zip': lines[ship_idx + 3].strip() if ship_idx + 3 < len(lines) else "??",
            'date': get_match(r"Order Date.*?(\d{1,2}/\d{1,2}/\d{2,4})"),
            'method': get_match(r"Shipping Method.*?,\s*\"([^\"]+)\""),
            'seller': "ThePokeGeo",
            'order_no': get_match(r"Order Number.*?([A-Z0-9\-]{8,})")
        }

        # Item rows (CSV-like quoted fields)
        item_pattern = r'"(\d+)"\s*,\s*"([^"]*?)"\s*,\s*"\\\$?([\d\.]+)"\s*,\s*"\\\$?([\d\.]+)"'
        matches = re.findall(item_pattern, text, re.DOTALL)
        
        items = []
        for qty, desc, price, total in matches:
            desc_clean = desc.replace('\n', ' ').strip()
            if "Total" in desc_clean or not qty.isdigit():
                continue
            try:
                price_clean = f"${float(price):.2f}"
                total_clean = f"${float(total):.2f}"
            except ValueError:
                price_clean = f"${price}"
                total_clean = f"${total}"
            items.append({
                'qty': qty,
                'desc': desc_clean,
                'price': price_clean,
                'total': total_clean
            })

        return data, items, None

    except Exception as e:
        return None, None, f"Extraction failed: {str(e)}"

# ────────────────────────────────────────────────
#  AUTH + PROFILE
# ────────────────────────────────────────────────
if "user" not in st.session_state:
    st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)
    with st.sidebar:
        st.title("Login / Register")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        c1, c2 = st.columns(2)
        if c1.button("Log In", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.user:
                    st.session_state.user = res.user
                    st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")
        if c2.button("Sign Up", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.success("Account created. Now click Log In.")
            except Exception as e:
                st.error(f"Sign-up failed: {e}")
    st.stop()

# ────────────────────────────────────────────────
#  MAIN APP
# ────────────────────────────────────────────────
user = st.session_state.user
profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data

if not profile:
    supabase.table("profiles").insert({"id": user.id, "credits": 5, "tier": "New"}).execute()
    profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute().data

with st.sidebar:
    st.write(f"**Credits:** {'∞' if profile['tier'] == 'Unlimited' else profile['credits']}")
    st.link_button("⚙️ Account Settings", "https://billing.stripe.com/p/login/28E9AV1P2anlaIO8GMbsc00")
    if st.button("🚪 Log Out"):
        st.session_state.clear()
        supabase.auth.sign_out()
        st.rerun()

st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)

# Credit check
if profile['tier'] != 'Unlimited' and profile['credits'] <= 0:
    st.error("No credits remaining. Please upgrade your plan →")
    st.link_button("Upgrade Plan", "https://buy.stripe.com/28E9AV1P2anlaIO8GMbsc00")
    st.stop()

uploaded_file = st.file_uploader("Upload your TCGplayer order PDF", type=["pdf"])

if uploaded_file:
    with st.spinner("Processing PDF..."):
        data, items, error = extract_tcg_data(uploaded_file)

    if error:
        st.error(error)
        st.info("Tip: Make sure you're uploading a recent TCGplayer **order confirmation PDF** (not an invoice or packing slip).")
        if st.button("Show raw extracted text (debug)"):
            reader = PdfReader(uploaded_file)
            raw = "\n".join(p.extract_text() or "" for p in reader.pages)
            st.code(raw[:4000] + "..." if len(raw) > 4000 else raw, language="text")
    elif data and items:
        pdf_bytes = create_label_pdf(data, items)

        # Show preview info
        st.success(f"Ready! Order **{data['order_no']}** – {len(items)} item(s)")

        # Download button
        st.download_button(
            label=f"📥 Download 4×6 Label – {data['order_no']}",
            data=pdf_bytes,
            file_name=f"TCG_Label_{data['order_no']}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"dl_{data['order_no']}"
        )

        # Deduct credit AFTER successful generation
        if profile['tier'] != 'Unlimited':
            new_credits = profile['credits'] - 1
            supabase.table("profiles").update({"credits": new_credits}).eq("id", user.id).execute()
            st.rerun()  # refresh sidebar credits display
    else:
        st.warning("Could not extract order data. The PDF layout may have changed.")
