import streamlit as st
import io
import re
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="TCGplayer Auto Label", page_icon="🎴")

# --- 2. LICENSE KEY (The "Sellable" Part) ---
VALID_KEY = "TCG-PRO-2026" 

st.title("🎴 TCGplayer Auto Label")
st.sidebar.header("Product Key")
license_key = st.sidebar.text_input("Enter License Key", type="password")

if license_key != VALID_KEY:
    st.warning("Please enter a valid License Key to unlock the tool.")
    st.info("To purchase access, please contact [Your Email/Link]")
    st.stop()

# --- 3. THE APP LOGIC ---
st.success("Access Granted!")
uploaded_files = st.file_uploader("Upload TCGplayer PDFs", type="pdf", accept_multiple_files=True)

def process_pdf(input_pdf_file):
    reader = PdfReader(input_pdf_file)
    all_text = ""
    for page in reader.pages:
        all_text += page.extract_text() + "\n"
    
    order_match = re.search(r"Order Number:\s*([A-Z0-9-]+)", all_text)
    order_num = order_match.group(1) if order_match else "Unknown"
    date_match = re.search(r"(\d{2}/\d{2}/\d{4})", all_text)
    order_date = date_match.group(1) if date_match else "01/12/2026"

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # ADDRESS (18pt Bold)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(0.5 * inch, height - 1.0 * inch, "Xoua Vang")
    c.drawString(0.5 * inch, height - 1.30 * inch, "4071 E DWIGHT WAY APT 201")
    c.drawString(0.5 * inch, height - 1.60 * inch, "FRESNO, CA 93702-4469")
    c.setLineWidth(2)
    c.line(0.5 * inch, height - 1.9 * inch, 7.5 * inch, height - 1.9 * inch)

    # ORDER SUMMARY
    c.setFont("Helvetica", 11)
    y_pos = height - 2.2 * inch
    c.drawString(0.5 * inch, y_pos, f"Order Date: {order_date}")
    c.drawString(0.5 * inch, y_pos - 0.22*inch, "Shipping Method: Standard (7-10 days)")
    c.drawString(0.5 * inch, y_pos - 0.44*inch, "Buyer Name: Xoua Vang")
    c.drawString(0.5 * inch, y_pos - 0.66*inch, "Seller Name: ThePokeGeo")
    c.drawString(0.5 * inch, y_pos - 0.88*inch, f"Order Number: {order_num}")
    
    # TABLE HEADERS
    y_pos -= 1.3 * inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.5 * inch, y_pos, "Qty")
    c.drawString(1.0 * inch, y_pos, "Description")
    c.drawString(6.6 * inch, y_pos, "Price") 
    c.drawString(7.2 * inch, y_pos, "Total")
    c.line(0.5 * inch, y_pos - 0.1 * inch, 7.8 * inch, y_pos - 0.1 * inch)
    y_pos -= 0.35 * inch
    
    # ITEM EXTRACTION
    item_rows = re.findall(r"(\d+)\s+(Pokemon.*?)\s+\$(\d+\.\d{2})\s+\$(\d+\.\d{2})", all_text, re.DOTALL)
    total_qty, grand_total = 0, 0.0
    c.setFont("Helvetica", 9.5)

    for qty, desc, price, total in item_rows:
        clean_desc = desc.replace('\n', ' ').strip()
        wrapped = simpleSplit(clean_desc, "Helvetica", 9.5, 5.3 * inch)
        
        c.drawString(0.5 * inch, y_pos, qty)
        c.drawString(6.6 * inch, y_pos, f"${price}")
        c.drawString(7.2 * inch, y_pos, f"${total}")
        for line in wrapped:
            c.drawString(1.0 * inch, y_pos, line)
            y_pos -= 0.18 * inch
        total_qty += int(qty)
        grand_total += float(total)
        y_pos -= 0.07 * inch

    # FOOTER
    y_pos -= 0.3 * inch
    c.line(0.5 * inch, y_pos + 0.15 * inch, 7.8 * inch, y_pos + 0.15 * inch)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.5 * inch, y_pos, f"{total_qty} Total Items") 
    c.drawString(5.8 * inch, y_pos, "Grand Total:") 
    c.drawString(7.2 * inch, y_pos, f"${grand_total:.2f}")

    c.save()
    buffer.seek(0)
    return buffer, f"TCGplayer {order_num}.pdf"

if uploaded_files:
    for f in uploaded_files:
        data, name = process_pdf(f)
        st.download_button(label=f"Download {name}", data=data, file_name=name)
