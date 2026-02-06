import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
import bcrypt
from supabase import create_client
from fpdf import FPDF
import io
import qrcode
import os
import tempfile

# --- CONFIGURATION & SECRETS ---
# In Streamlit Cloud, you set these in the dashboard. 
# Locally, create a .streamlit/secrets.toml file.
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except:
    # Fallback for local testing (DO NOT COMMIT THIS TO GITHUB)
    SUPABASE_URL = "https://ytfpiyfapvybihlngxks.supabase.co"
    SUPABASE_KEY = "YOUR_SUPABASE_KEY_HERE"

# --- THEME COLORS ---
COLOR_DAR_GREEN = "#003811"
COLOR_DAR_GOLD = "#D4AF37"

# --- SETUP PAGE ---
st.set_page_config(
    page_title="DAR Travel Order System",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS STYLING (To match your Tkinter look) ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: #F3F4F6; }}
    .stButton>button {{
        background-color: {COLOR_DAR_GREEN};
        color: white;
        font-weight: bold;
    }}
    h1, h2, h3 {{ color: {COLOR_DAR_GREEN}; font-family: 'Times New Roman'; }}
    .success-status {{ color: #15803d; font-weight: bold; }}
    .pending-status {{ color: #b45309; font-weight: bold; }}
    </style>
""", unsafe_allow_html=True)

# --- SUPABASE CONNECTION ---
@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

client = init_connection()

# --- HELPER FUNCTIONS ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except ValueError:
        return password == hashed # Fallback for legacy passwords

# --- LOGIN SYSTEM ---
def login_page():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown(f"<h1 style='text-align: center; color:{COLOR_DAR_GOLD};'>DAR TRAVEL ORDER SYSTEM</h1>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='text-align: center; color:{COLOR_DAR_GREEN};'>Camarines Sur 1</h3>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            uid = st.text_input("Employee ID")
            pwd = st.text_input("Password", type="password")
            submitted = st.form_submit_button("SECURE LOGIN")
            
            if submitted:
                try:
                    response = client.table("employees").select("*").eq("emp_id", uid).execute()
                    if response.data:
                        user = response.data[0]
                        if check_password(pwd, user.get('pass')):
                            st.session_state['logged_in'] = True
                            st.session_state['user'] = user
                            st.success("Login Successful!")
                            st.rerun()
                        else:
                            st.error("Invalid Password")
                    else:
                        st.error("User ID not found")
                except Exception as e:
                    st.error(f"Connection Error: {e}")

# --- MAIN APPLICATION ---
def main_app():
    user = st.session_state['user']
    
    # Sidebar
    with st.sidebar:
        st.header(f"👤 {user['full_name']}")
        st.caption(f"Division: {user.get('division', 'DAR')}")
        
        menu = st.radio("Navigation", ["New Travel Order", "My Applications", "DTR View", "Change Password"])
        
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- TAB 1: NEW TRAVEL ORDER ---
    if menu == "New Travel Order":
        st.title("✏️ New Travel Order")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("1. Logistics")
            transport = st.selectbox("Means of Transportation", ["LAND", "AIR", "GOV'T VEHICLE", "OTHERS"])
            report_to = st.text_input("Report To (Official/Position)")
            
            st.subheader("2. Personnel (Max 3)")
            # In web, we can just select from a list
            all_emps = client.table("employees").select("emp_id, full_name").execute().data
            emp_options = {e['full_name']: e['emp_id'] for e in all_emps}
            
            # Default to current user
            default_emp = [user['full_name']] if user['full_name'] in emp_options else []
            selected_personnel = st.multiselect("Search Personnel", options=emp_options.keys(), default=default_emp, max_selections=3)

        with col2:
            st.subheader("3. Itinerary")
            with st.form("itin_form"):
                d_date = st.date_input("Travel Date")
                d_dest = st.text_input("Destination")
                d_purp = st.text_input("Purpose")
                add_itin = st.form_submit_button("Add to Itinerary List")
                
                if add_itin:
                    if 'itin_list' not in st.session_state: st.session_state['itin_list'] = []
                    st.session_state['itin_list'].append({
                        "date": str(d_date),
                        "destination": d_dest,
                        "purpose": d_purp
                    })
                    st.success("Added to list")

            if 'itin_list' in st.session_state and st.session_state['itin_list']:
                st.table(st.session_state['itin_list'])
                if st.button("Clear Itinerary"):
                    st.session_state['itin_list'] = []
                    st.rerun()

        st.divider()
        if st.button("🚀 SUBMIT OFFICIAL REQUEST", type="primary"):
            if not selected_personnel or 'itin_list' not in st.session_state or not st.session_state['itin_list']:
                st.error("Please add personnel and itinerary details.")
            else:
                # GENERATE TO NUMBER LOGIC
                # (Simplified for web - ideally this happens via database function/trigger to avoid race conditions)
                current_year = str(datetime.now().year)
                div_code = str(user.get('division', 'DAR'))[:4].upper()
                
                # Fetch last TO to increment
                # This is a basic implementation; in production use a DB sequence
                existing = client.table("travel_orders").select("to_no").order("created_at", desc=True).limit(1).execute()
                next_num = 1
                if existing.data:
                    try:
                        last_no = existing.data[0]['to_no']
                        next_num = int(last_no.split('-')[-1]) + 1
                    except: pass
                
                to_no = f"{current_year}-{div_code}-{next_num:04d}"
                
                try:
                    # Submit Orders
                    for p_name in selected_personnel:
                        pid = emp_options[p_name]
                        status = "PENDING_VEHICLE_RESERVATION" if transport == "GOV'T VEHICLE" else "PENDING_UNIT_HEAD"
                        
                        client.table("travel_orders").insert({
                            "to_no": to_no,
                            "emp_id": pid,
                            "emp_name": p_name,
                            "status": status,
                            "division": user.get('division'),
                            "transport": transport,
                            "report_to": report_to
                        }).execute()
                    
                    # Submit Itinerary
                    itin_rows = []
                    for item in st.session_state['itin_list']:
                        itin_rows.append({
                            "to_no": to_no,
                            "travel_date": item['date'],
                            "destination": item['destination'],
                            "purpose": item['purpose']
                        })
                    client.table("itinerary").insert(itin_rows).execute()
                    
                    st.success(f"Travel Order {to_no} Submitted Successfully!")
                    st.session_state['itin_list'] = [] # Reset
                except Exception as e:
                    st.error(f"Submission failed: {e}")

    # --- TAB 2: MY APPLICATIONS ---
    elif menu == "My Applications":
        st.title("📋 My Applications")
        
        # Fetch Data
        my_orders = client.table("travel_orders").select("*").eq("emp_id", user['emp_id']).order("created_at", desc=True).execute().data
        
        if my_orders:
            df = pd.DataFrame(my_orders)
            # Display as a dataframe
            st.dataframe(df[["to_no", "status", "transport", "report_to"]], use_container_width=True)
            
            # Select TO for Actions
            selected_to = st.selectbox("Select TO Number to Print/Action", options=df['to_no'].unique())
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Cancel Application"):
                    client.table("travel_orders").delete().eq("to_no", selected_to).execute()
                    client.table("itinerary").delete().eq("to_no", selected_to).execute()
                    st.success("Cancelled.")
                    st.rerun()
            
            with col_b:
                # PDF GENERATION LOGIC
                # We generate PDF in memory and offer download button
                status = df[df['to_no'] == selected_to].iloc[0]['status']
                if status == "APPROVED":
                    pdf_bytes = generate_pdf_in_memory(selected_to)
                    st.download_button(
                        label="📄 Download Official TO PDF",
                        data=pdf_bytes,
                        file_name=f"TO_{selected_to}.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.warning("Only APPROVED orders can be downloaded.")

    # --- TAB 3: DTR VIEW (Simplified) ---
    elif menu == "DTR View":
        st.title("📅 Monthly Travel Log")
        st.info("Calendar visualization is simplified for the web version.")
        
        my_itin = client.table("itinerary").select("*").execute().data
        # Filter logic here...
        if my_itin:
            df_itin = pd.DataFrame(my_itin)
            st.dataframe(df_itin)

# --- PDF GENERATOR (Adapted for Web) ---
def generate_pdf_in_memory(to_no):
    # Retrieve data
    orders = client.table("travel_orders").select("*").eq("to_no", to_no).execute().data
    itinerary = client.table("itinerary").select("*").eq("to_no", to_no).execute().data
    
    if not orders: return None
    
    # Simple FPDF layout
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"TRAVEL ORDER NO. {to_no}", 0, 1, 'C')
    
    pdf.set_font("Arial", '', 12)
    names = ", ".join([o['emp_name'] for o in orders])
    pdf.cell(0, 10, f"Personnel: {names}", 0, 1)
    pdf.cell(0, 10, f"Transport: {orders[0]['transport']}", 0, 1)
    
    # Add Itinerary table
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(40, 10, "Date", 1)
    pdf.cell(60, 10, "Destination", 1)
    pdf.cell(90, 10, "Purpose", 1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 10)
    for item in itinerary:
        pdf.cell(40, 10, str(item['travel_date']), 1)
        pdf.cell(60, 10, str(item['destination']), 1)
        pdf.cell(90, 10, str(item['purpose']), 1)
        pdf.ln()
        
    # Return bytes
    return pdf.output(dest='S').encode('latin-1')

# --- ENTRY POINT ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    login_page()
else:
    main_app()