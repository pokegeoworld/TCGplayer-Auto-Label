import streamlit as st
from supabase import create_client
import io, re
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
    </style>
    """, unsafe_allow_html=True)

# --- 4. THE DYNAMIC PDF CREATOR (STRICT 18PT BOLD) ---
def create_label_pdf(data, items):
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 18)
    c.drawString(0.5 * inch, height - 1.0 * inch, data['buyer_name'])
    c.drawString(0.5 * inch, height - 1.30 * inch, data['address'])
    c.drawString(0.5 * inch, height - 1.60 * inch, data['city_state_zip'])
    c.setLineWidth(2); c.line(0.5 * inch, height - 1.9 * inch, 7.5 * inch, height - 1.9 * inch)
    c.setFont("Helvetica", 11); y_pos = height - 2.2 * inch
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
    c.save(); packet.seek(0)
    return packet.getvalue()

# --- 5. AUTHENTICATION ---
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
        except Exception:
            st.sidebar.error("Login Failed. Check credentials or try again.")
    if r_col.button("Sign Up"):
        try:
            supabase.auth.sign_up({"email": u_email, "password": u_pass})
            st.sidebar.success("Account Created! Check your email (if confirmation required), then click Log In.")
        except Exception:
            st.sidebar.error("Signup failed. Email may already exist or password too weak.")
    st.stop()

# --- 6. DATABASE HANDSHAKE (Trigger should auto-create profile; fallback only if needed) ---
user = st.session_state.user

with st.spinner("Loading your profile..."):
    profile_res = supabase.table("profiles").select("*").eq("id", user.id).execute()

    if profile_res.data:
        profile = profile_res.data[0]
    else:
        st.warning("Profile not found — automatic creation may be delayed. Attempting fallback...")
        try:
            supabase.table("profiles").insert({
                "id": user.id,
                "credits": 0,
                "tier": "None"
            }).execute()
            # Fetch again after insert
            profile_res = supabase.table("profiles").select("*").eq("id", user.id).execute()
            if profile_res.data:
                profile = profile_res.data[0]
            else:
                raise Exception("Insert succeeded but profile still not found.")
        except Exception as e:
            st.error(
                f"Failed to create fallback profile: {str(e)}\n\n"
                "This is usually due to Row Level Security (RLS) settings.\n"
                "Please run the following SQL in Supabase SQL Editor:\n\n"
                "CREATE POLICY \"Users can create their own profile\"\n"
                "ON public.profiles FOR INSERT\n"
                "TO authenticated WITH CHECK (auth.uid() = id);\n\n"
                "Then log out and back in. If issue persists, contact support."
            )
            st.stop()

# --- 7. SIDEBAR USERNAME & PROFILE ---
st.sidebar.title(f"👤 {user.email}")
st.sidebar.write(f"Credits: **{profile['credits']}**")
st.sidebar.write(f"Tier: **{'Active' if profile['credits'] > 0 else profile['tier']}**")
st.sidebar.markdown("---")
st.sidebar.link_button("⚙️ Account Settings", "https://billing.stripe.com/p/login/28E9AV1P2anlaIO8GMbsc00")
if st.sidebar.button("🚪 Log Out"):
    st.session_state.clear()
    supabase.auth.sign_out()
    st.rerun()

# --- 8. RESTORED PRICING GATE (ALL TIERS) ---
if profile['credits'] == 0 and profile['tier'] == "None":
    st.markdown('<p class="hero-title">Choose Your Plan</p>', unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        st.markdown('<div class="pricing-card"><p class="free-trial-large">Free Trial</p><p class="label-text">5 Labels</p></div>', unsafe_allow_html=True)
        if st.button("Activate Free Trial"):
            supabase.table("profiles").update({"tier": "Free", "credits": 5}).eq("id", user.id).execute()
            st.rerun()
    with colB:
        st.markdown('<div class="pricing-card"><p class="tier-name">Starter Pack</p><p class="big-stat">10</p><p class="label-text">Labels</p><p class="small-price">$0.50</p></div>', unsafe_allow_html=True)
        st.link_button("Buy Starter", "https://buy.stripe.com/28EeVf0KY7b97wC3msbsc03")
   
    st.markdown('<div class="sub-header">MONTHLY SUBSCRIPTIONS</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="pricing-card"><p class="tier-name">BASIC</p><p class="big-stat">50</p><p class="label-text">Labels</p><p class="small-price">$1.49/mo</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Basic", "https://buy.stripe.com/aFafZj9hu7b9dV0f5absc02")
    with c2:
        st.markdown('<div class="pricing-card"><p class="tier-name">PRO</p><p class="big-stat">150</p><p class="label-text">Labels</p><p class="small-price">$1.99/mo</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Pro", "https://buy.stripe.com/4gM3cx9hu1QP04a5uAbsc01")
    with c3:
        st.markdown('<div class="pricing-card"><p class="tier-name">UNLIMITED</p><p class="big-stat">∞</p><p class="label-text">Labels</p><p class="small-price">$2.99/mo</p></div>', unsafe_allow_html=True)
        st.link_button("Choose Unlimited", "https://buy.stripe.com/28E9AV1P2anlaIO8GMbsc00")
    st.stop()

# --- 9. DYNAMIC CREATOR VIEW ---
st.markdown('<p class="hero-title">TCGplayer Auto Label Creator</p>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload TCGplayer PDF", type="pdf")

if uploaded_file:
    try:
        reader = PdfReader(uploaded_file)
        text = "".join([page.extract_text() + "\n" for page in reader.pages])
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        order_no = re.search(r"Order Number:\s*([A-Z0-9\-]+)", text).group(1)
        order_date = re.search(r"(\d{2}/\d{2}/\d{4})", text).group(1)
        ship_idx = next(i for i, line in enumerate(lines) if "Ship To:" in line or "Shipping Address:" in line)

        data = {
            'buyer_name': lines[ship_idx + 1],
            'address': lines[ship_idx + 2],
            'city_state_zip': lines[ship_idx + 3],
            'date': order_date,
            'order_no': order_no,
            'method': "Standard (7-10 days)",
            'seller': "ThePokeGeo"
        }

        items = []
        item_rows = re.findall(r"(\d+)\s+(Pokemon.*?)\s+\$(\d+\.\d{2})\s+\$(\d+\.\d{2})", text, re.DOTALL)
        for qty, desc, price, total in item_rows:
            items.append({
                'qty': qty,
                'desc': desc.replace('\n', ' ').strip(),
                'price': f"${price}",
                'total': f"${total}"
            })

        pdf_bytes = create_label_pdf(data, items)

        def decrement_credits():
            supabase.table("profiles").update({"credits": profile['credits'] - 1}).eq("id", user.id).execute()

        st.download_button(
            label=f"📥 DOWNLOAD LABEL: {order_no}",
            data=pdf_bytes,
            file_name=f"TCGplayer_{order_no}.pdf",
            mime="application/pdf",
            use_container_width=True,
            on_click=decrement_credits
        )
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}\nMake sure this is a valid TCGplayer packing slip PDF.")
