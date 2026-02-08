import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client
import bcrypt
import qrcode
from io import BytesIO
from fpdf import FPDF

# --- CONFIGURATION ---
SUPABASE_URL = "https://ytfpiyfapvybihlngxks.supabase.co"
SUPABASE_KEY = "sb_secret_YOUR_KEY" # Secure this in Streamlit Secrets
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Page Branding
st.set_page_config(page_title="DAR TO Portal", page_icon="✏️", layout="wide")

# Custom CSS for DAR Branding (Green & Gold)
st.markdown("""
    <style>
    .main { background-color: #F3F4F6; }
    .stButton>button { background-color: #003811; color: #D4AF37; border-radius: 5px; }
    .sidebar .sidebar-content { background-color: #003811; color: white; }
    h1 { color: #003811; }
    </style>
    """, unsafe_allow_html=True)

# --- AUTHENTICATION LOGIC ---
if 'auth_status' not in st.session_state:
    st.session_state.auth_status = False

def login():
    st.sidebar.image("https://raw.githubusercontent.com/cabellojaysonnew-max/e-sign/main/logo.png", width=100)
    st.sidebar.title("DAR Login")
    emp_id = st.sidebar.text_input("Employee ID")
    password = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Secure Login"):
        res = supabase.table("employees").select("*").eq("emp_id", emp_id).execute()
        if res.data:
            user = res.data[0]
            if bcrypt.checkpw(password.encode('utf-8'), user['pass'].encode('utf-8')):
                st.session_state.auth_status = True
                st.session_state.user = user
                st.rerun()
        st.sidebar.error("Invalid Credentials")

# --- MAIN APP INTERFACE ---
if not st.session_state.auth_status:
    login()
    st.info("Please login via the sidebar to access the Travel Order System.")
else:
    user = st.session_state.user
    st.title(f"Welcome, {user['full_name']}")
    
    menu = ["New Travel Order", "My Applications", "Travel Log (DTR)"]
    choice = st.sidebar.selectbox("System Menu", menu)

    # --- MODULE 1: NEW TRAVEL ORDER ---
    if choice == "New Travel Order":
        st.subheader("✏️ Apply for Travel Order")
        
        with st.form("to_form"):
            col1, col2 = st.columns(2)
            with col1:
                transport = st.selectbox("Transportation", ["LAND", "AIR", "GOV'T VEHICLE"])
                report_to = st.text_input("Report To (Position/Official)")
            with col2:
                start_date = st.date_input("Start Date", min_value=datetime.now())
                end_date = st.date_input("End Date", min_value=start_date)
            
            destination = st.text_input("Destination")
            purpose = st.text_area("Purpose of Travel")
            
            if st.form_submit_button("Submit Application"):
                # Logic to generate TO_NO and Insert to Supabase
                to_no = f"TO-{datetime.now().strftime('%Y%m%d-%H%M')}"
                data = {
                    "to_no": to_no, "emp_id": user['emp_id'], "emp_name": user['full_name'],
                    "status": "PENDING_UNIT_HEAD", "transport": transport, 
                    "destination": destination, "purpose": purpose
                }
                supabase.table("travel_orders").insert(data).execute()
                st.success(f"Application {to_no} submitted successfully!")

    # --- MODULE 2: MONITORING ---
    elif choice == "My Applications":
        st.subheader("📋 Track My Travel Orders")
        res = supabase.table("travel_orders").select("*").eq("emp_id", user['emp_id']).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            st.dataframe(df[['to_no', 'status', 'destination', 'transport']])
        else:
            st.write("No travel orders found.")

    # --- MODULE 3: LOG VIEW ---
    elif choice == "Travel Log (DTR)":
        st.subheader("📅 Monthly Travel Log")
        # Logic to display calendar-style records
        st.info("This view displays all approved TOs for the current month.")

    if st.sidebar.button("Logout"):
        st.session_state.auth_status = False
        st.rerun()
