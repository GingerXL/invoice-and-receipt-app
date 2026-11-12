import streamlit as st
import sqlite3
from datetime import date
from io import BytesIO
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# --- PAGE CONFIG ---
st.set_page_config(page_title="Invoice & Receipt App", layout="wide")

# --- CUSTOM CSS FOR CLEAN MINIMALIST DESIGN ---
st.markdown("""
<style>
    .card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 30px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .badge {
        background-color: #fef3c7;
        color: #92400e;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        float: right;
    }
    .section-tag {
        color: #b45309;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .preview-header {
        font-size: 26px;
        font-weight: 700;
        color: #111827;
        margin-bottom: 20px;
    }
    .meta-box {
        background-color: #f9fafb;
        border-radius: 8px;
        padding: 12px;
        margin-top: 15px;
        margin-bottom: 20px;
    }
    .item-table th {
        text-align: left;
        font-size: 12px;
        color: #6b7280;
        text-transform: uppercase;
        border-bottom: 1px solid #e5e7eb;
        padding-bottom: 8px;
    }
    .item-table td {
        padding: 10px 0;
        font-size: 14px;
        color: #374151;
        border-bottom: 1px solid #f3f4f6;
    }
    .total-line {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        font-size: 14px;
    }
    .grand-total {
        font-size: 18px;
        font-weight: 700;
        border-top: 2px solid #111827;
        padding-top: 8px;
        margin-top: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- DATABASE SETUP ---
conn = sqlite3.connect("invoices.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        address TEXT
    )
""")
conn.commit()

# --- DATABASE HELPERS ---
def get_customers():
    c.execute("SELECT id, name, email, address FROM customers")
    return c.fetchall()

def add_customer(name, email, address):
    c.execute("INSERT INTO customers (name, email, address) VALUES (?, ?, ?)", (name, email, address))
    conn.commit()

# --- STATE INITIALIZATION FOR DYNAMIC ITEMS ---
if "line_items" not in st.session_state:
    st.session_state["line_items"] = [
        {"desc": "Brand identity consultation", "qty": 1, "rate": 85000.0},
        {"desc": "Design system delivery", "qty": 1, "rate": 145000.0}
    ]

# --- PDF GENERATOR (WITH LOGO SUPPORT) ---
def generate_pdf(doc_type, meta, business, client, items_list, totals, symbol, logo_file=None):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Draw Logo if provided
    if logo_file is not None:
        try:
            logo_img = ImageReader(logo_file)
            p.drawImage(logo_img, 50, height - 90, width=100, height=45, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # Header / Title
    p.setFont("Helvetica-Bold", 20)
    p.drawString(380, height - 60, doc_type.upper())
    p.setFont("Helvetica", 10)
    p.drawString(380, height - 75, f"Status: {meta.get('status', 'Paid')}")

    # Meta Info
    y = height - 120
    p.setFont("Helvetica", 9)
    p.drawString(50, y, f"NUMBER: {meta['number']}")
    p.drawString(220, y, f"DATE: {meta['date']}")
    if "due_date" in meta:
        p.drawString(400, y, f"DUE DATE: {meta['due_date']}")
    elif "payment_method" in meta:
        p.drawString(400, y, f"PAID VIA: {meta['payment_method']}")

    # Business & Client Box
    y -= 40
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, "FROM:")
    p.drawString(300, y, "BILL TO / CUSTOMER:")
    
    p.setFont("Helvetica", 9)
    y -= 15
    p.drawString(50, y, business['name'])
    p.drawString(300, y, client['name'])
    y -= 12
    p.drawString(50, y, business['address'].replace('\n', ', '))
    p.drawString(300, y, client['address'].replace('\n', ', '))
    y -= 12
    p.drawString(50, y, business['email'])
    p.drawString(300, y, client['email'])

    # Items Table Header
    y -= 40
    p.line(50, y + 10, 550, y + 10)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(50, y, "DESCRIPTION")
    p.drawString(300, y, "QTY")
    p.drawString(380, y, "RATE")
    p.drawString(470, y, "AMOUNT")
    p.line(50, y - 5, 550, y - 5)

    # Line Items
    p.setFont("Helvetica", 9)
    y -= 20
    for itm in items_list:
        amt = itm['qty'] * itm['rate']
        p.drawString(50, y, str(itm['desc']))
        p.drawString(300, y, str(itm['qty']))
        p.drawString(380, y, f"{symbol}{itm['rate']:,.2f}")
        p.drawString(470, y, f"{symbol}{amt:,.2f}")
        y -= 18

    # Totals
    y -= 20
    p.line(350, y + 10, 550, y + 10)
    p.drawString(350, y, "Subtotal:")
    p.drawString(470, y, f"{symbol}{totals['subtotal']:,.2f}")
    y -= 15
    p.drawString(350, y, f"Tax ({totals['tax_rate']}%):")
    p.drawString(470, y, f"{symbol}{totals['tax']:,.2f}")
    y -= 15
    p.drawString(350, y, f"Discount ({totals['discount_rate']}%):")
    p.drawString(470, y, f"-{symbol}{totals['discount']:,.2f}")
    y -= 15
    p.setFont("Helvetica-Bold", 11)
    p.drawString(350, y, "Total Due / Paid:")
    p.drawString(470, y, f"{symbol}{totals['grand_total']:,.2f}")

    if meta.get("notes"):
        y -= 40
        p.setFont("Helvetica-Bold", 9)
        p.drawString(50, y, "Notes:")
        p.setFont("Helvetica", 8)
        p.drawString(50, y - 12, meta["notes"])

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# --- SIDEBAR SETTINGS ---
st.sidebar.title("⚙️ Workspace")
nav_choice = st.sidebar.radio("View", ["Invoice Generator", "Receipt Generator", "Customer Database"])

# Logo Uploader
uploaded_logo = st.sidebar.file_uploader("Upload Business Logo", type=["png", "jpg", "jpeg"])

# Quick Customer Database
if nav_choice == "Customer Database":
    st.title("👥 Customer Database")
    with st.form("add_customer_form"):
        c_name = st.text_input("Client / Company Name")
        c_email = st.text_input("Email Address")
        c_address = st.text_area("Client Address")
        if st.form_submit_button("Save Customer"):
            if c_name.strip():
                add_customer(c_name, c_email, c_address)
                st.success("Customer saved!")
            else:
                st.error("Name is required.")

    st.subheader("Existing Clients")
    customers = get_customers()
    if customers:
        st.dataframe([{"ID": c[0], "Name": c[1], "Email": c[2], "Address": c[3]} for c in customers], use_container_width=True)
    st.stop()

# --- MAIN INVOICE & RECEIPT INTERFACE ---
is_invoice = (nav_choice == "Invoice Generator")
doc_type = "Invoice" if is_invoice else "Receipt"
tag_text = "01 / COMPOSE" if is_invoice else "02 / RECORD PAYMENT"
desc_text = "Make it yours. Your preview updates as you type." if is_invoice else "Record the purchase and payment. The receipt updates as you type."

left_col, right_col = st.columns([1.1, 1], gap="large")

# ==========================================
# LEFT COLUMN: FORM / COMPOSE
# ==========================================
with left_col:
    st.markdown(f"<div class='section-tag'>{tag_text}</div>", unsafe_allow_html=True)
    st.markdown(f"### {doc_type} details")
    st.caption(desc_text)

    # 1. From / Bill To
    c1, c2 = st.columns(2)
    with c1:
        st.caption("**From · Your business**")
        biz_name = st.text_input("BUSINESS NAME", value="Ginger Visual Studios", key="biz_name")
        biz_email = st.text_input("EMAIL ADDRESS", value="hello@studiomeridian.example", key="biz_email")
        biz_address = st.text_area("BUSINESS ADDRESS", value="12 Marina Road\nLagos, Nigeria", height=80, key="biz_addr")

    with c2:
        st.caption("**Bill to · Your client**" if is_invoice else "**Received from · Customer**")
        
        # Load from DB or type directly
        cust_list = get_customers()
        options = ["-- Type Manually --"] + [c[1] for c in cust_list]
        selected_cust = st.selectbox("CHOOSE SAVED CLIENT", options)
        
        if selected_cust != "-- Type Manually --":
            cust_data = next(c for c in cust_list if c[1] == selected_cust)
            client_name = st.text_input("CLIENT NAME", value=cust_data[1], key="c_name")
            client_email = st.text_input("EMAIL ADDRESS", value=cust_data[2], key="c_email")
            client_address = st.text_area("CLIENT ADDRESS", value=cust_data[3], height=80, key="c_addr")
        else:
            client_name = st.text_input("CLIENT NAME", value="Acacia Projects", key="c_name")
            client_email = st.text_input("EMAIL ADDRESS", value="accounts@acacia.example", key="c_email")
            client_address = st.text_area("CLIENT ADDRESS", value="Victoria Island\nLagos, Nigeria", height=80, key="c_addr")

    st.markdown("---")

    # 2. Meta Details
    if is_invoice:
        m1, m2, m3 = st.columns(3)
        doc_num = m1.text_input("INVOICE NUMBER", value="INV-2026-001")
        issue_date = m2.date_input("ISSUE DATE", date.today())
        due_date = m3.date_input("DUE DATE", date.today())
        
        col_cur, col_status = st.columns(2)
        currency = col_cur.selectbox("CURRENCY", ["NGN — Nigerian naira (₦)", "USD — US Dollar ($)", "EUR — Euro (€)", "GBP — British Pound (£)"])
        payment_status = col_status.selectbox("PAYMENT STATUS", ["Unpaid", "Paid", "Pending", "Overdue"])
        pay_method = ""
    else:
        m1, m2, m3 = st.columns(3)
        doc_num = m1.text_input("RECEIPT NUMBER", value="RCT-2026-001")
        issue_date = m2.date_input("RECEIPT DATE", date.today())
        pay_method = m3.selectbox("PAYMENT METHOD", ["Bank transfer", "Cash", "Card / POS", "Online"])
        
        col_cur, _ = st.columns(2)
        currency = col_cur.selectbox("CURRENCY", ["NGN — Nigerian naira (₦)", "USD — US Dollar ($)", "EUR — Euro (€)", "GBP — British Pound (£)"])
        payment_status = "Paid"

    # Currency Symbol extractor
    symbol = "₦" if "NGN" in currency else ("$" if "USD" in currency else ("€" if "EUR" in currency else "£"))

    st.markdown("---")

    # 3. Dynamic Items Table
    header_col, btn_col = st.columns([3, 1])
    header_col.markdown("#### Services & fees" if is_invoice else "#### Purchased items")
    if btn_col.button("+ Add item", use_container_width=True):
        st.session_state["line_items"].append({"desc": "", "qty": 1, "rate": 0.0})
        st.rerun()

    subtotal = 0.0
    for idx, item in enumerate(st.session_state["line_items"]):
        row = st.columns([3, 1, 1.5, 1.5, 1])
        item["desc"] = row[0].text_input(f"DESC #{idx+1}", item["desc"], key=f"desc_{idx}")
        item["qty"] = row[1].number_input(f"QTY", min_value=1, value=int(item["qty"]), key=f"qty_{idx}")
        item["rate"] = row[2].number_input(f"RATE", min_value=0.0, value=float(item["rate"]), step=1000.0, key=f"rate_{idx}")
        
        line_total = item["qty"] * item["rate"]
        subtotal += line_total
        
        row[3].markdown(f"<p style='margin-top:30px; font-weight:600;'>{symbol}{line_total:,.2f}</p>", unsafe_allow_html=True)
        if row[4].button("Remove", key=f"del_{idx}"):
            st.session_state["line_items"].pop(idx)
            st.rerun()

    st.markdown("---")

    # 4. Tax, Discount, Notes
    t1, t2 = st.columns(2)
    tax_rate = t1.number_input("TAX RATE (%)", min_value=0.0, max_value=100.0, value=7.5, step=0.5)
    discount_rate = t2.number_input("DISCOUNT (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
    
    notes = ""
    amount_paid = 0.0
    if not is_invoice:
        amount_paid = st.number_input("AMOUNT PAID", value=float(subtotal + (subtotal * tax_rate/100)), step=1000.0)
        notes = st.text_area("NOTES", "Payment received with thanks.")
    else:
        notes = st.text_area("NOTES / PAYMENT TERMS", "Thank you for your business.")

# ==========================================
# CALCULATIONS
# ==========================================
tax_amount = subtotal * (tax_rate / 100)
discount_amount = subtotal * (discount_rate / 100)
grand_total = subtotal + tax_amount - discount_amount
change = (amount_paid - grand_total) if not is_invoice else 0.0

# ==========================================
# RIGHT COLUMN: LIVE PREVIEW CARD
# ==========================================
with right_col:
    st.markdown("<div class='section-tag'>READY TO SEND</div>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        
        # Logo + Status Badge
        top_l, top_r = st.columns([2, 1])
        with top_l:
            if uploaded_logo:
                st.image(uploaded_logo, width=130)
            st.markdown(f"<div class='preview-header'>{doc_type}</div>", unsafe_allow_html=True)
        with top_r:
            st.markdown(f"<span class='badge'>{payment_status}</span>", unsafe_allow_html=True)

        # From / Bill To
        c_from, c_to = st.columns(2)
        with c_from:
            st.caption("FROM")
            st.markdown(f"**{biz_name}**<br><span style='color:#6b7280; font-size:13px;'>{biz_address.replace(chr(10), '<br>')}<br>{biz_email}</span>", unsafe_allow_html=True)
        with c_to:
            st.caption("BILL TO" if is_invoice else "CUSTOMER")
            st.markdown(f"**{client_name}**<br><span style='color:#6b7280; font-size:13px;'>{client_address.replace(chr(10), '<br>')}<br>{client_email}</span>", unsafe_allow_html=True)

        # Meta Grey Box
        st.markdown(f"""
        <div class='meta-box'>
            <table width='100%' style='font-size:12px;'>
                <tr>
                    <td style='color:#6b7280;'>NUMBER</td>
                    <td style='color:#6b7280;'>{'ISSUED' if is_invoice else 'DATE'}</td>
                    <td style='color:#6b7280;'>{'DUE' if is_invoice else 'PAID VIA'}</td>
                </tr>
                <tr style='font-weight:600;'>
                    <td>{doc_num}</td>
                    <td>{issue_date.strftime('%d %b %Y')}</td>
                    <td>{due_date.strftime('%d %b %Y') if is_invoice else pay_method}</td>
                </tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

        # Items Table
        items_html = "<table class='item-table' width='100%'><tr><th>SERVICE / ITEM</th><th style='text-align:center;'>QTY</th><th style='text-align:right;'>RATE</th><th style='text-align:right;'>AMOUNT</th></tr>"
        for itm in st.session_state["line_items"]:
            amt = itm['qty'] * itm['rate']
            items_html += f"<tr><td>{itm['desc']}</td><td style='text-align:center;'>{itm['qty']}</td><td style='text-align:right;'>{symbol}{itm['rate']:,.2f}</td><td style='text-align:right;'>{symbol}{amt:,.2f}</td></tr>"
        items_html += "</table>"
        st.markdown(items_html, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Summary / Totals
        _, tot_col = st.columns([1, 1.2])
        with tot_col:
            st.markdown(f"<div class='total-line'><span>Subtotal</span><span>{symbol}{subtotal:,.2f}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-line'><span>Tax</span><span>{symbol}{tax_amount:,.2f} ({tax_rate}%)</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-line'><span>Discount</span><span>-{symbol}{discount_amount:,.2f} ({discount_rate}%)</span></div>", unsafe_allow_html=True)
            
            if is_invoice:
                st.markdown(f"<div class='total-line grand-total'><span>Total due</span><span>{symbol}{grand_total:,.2f}</span></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='total-line grand-total'><span>Purchase total</span><span>{symbol}{grand_total:,.2f}</span></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='total-line' style='font-weight:600;'><span>Total paid</span><span>{symbol}{amount_paid:,.2f}</span></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='total-line' style='border-top:1px solid #e5e7eb; padding-top:6px; margin-top:6px;'><span>Change</span><span>{symbol}{max(0.0, change):,.2f}</span></div>", unsafe_allow_html=True)

        if notes:
            st.markdown(f"<div style='margin-top:25px;'><b style='font-size:12px;'>Notes</b><br><span style='color:#6b7280; font-size:12px;'>{notes}</span></div>", unsafe_allow_html=True)

        st.markdown("<p style='text-align:center; color:#9ca3af; font-size:12px; margin-top:35px;'>Thank you for your business.</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Export Button
    st.markdown("<br>", unsafe_allow_html=True)
    meta_dict = {
        "number": doc_num,
        "date": issue_date.strftime("%d %b %Y"),
        "status": payment_status,
        "notes": notes
    }
    if is_invoice:
        meta_dict["due_date"] = due_date.strftime("%d %b %Y")
    else:
        meta_dict["payment_method"] = pay_method

    pdf_bytes = generate_pdf(
        doc_type=doc_type,
        meta=meta_dict,
        business={"name": biz_name, "email": biz_email, "address": biz_address},
        client={"name": client_name, "email": client_email, "address": client_address},
        items_list=st.session_state["line_items"],
        totals={"subtotal": subtotal, "tax_rate": tax_rate, "tax": tax_amount, "discount_rate": discount_rate, "discount": discount_amount, "grand_total": grand_total},
        symbol=symbol,
        logo_file=uploaded_logo
    )

    st.download_button(
        label=f"📥 Download {doc_type} as PDF",
        data=pdf_bytes,
        file_name=f"{doc_type.lower()}_{doc_num}.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary"
    )
