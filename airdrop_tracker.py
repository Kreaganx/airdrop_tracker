import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import random
import string

# Page configuration
st.set_page_config(
    page_title="Airdrop Hunting Tracker",
    page_icon="🪂",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    div[data-testid="stDataFrame"] {
        background-color: white;
        border-radius: 10px;
        padding: 10px;
        overflow-x: auto !important;
    }
    div[data-testid="stDataFrame"] > div {
        overflow-x: auto !important;
    }
    section[data-testid="stDataFrameResizable"] {
        overflow-x: scroll !important;
    }
    h1 {
        color: white !important;
    }
    .info-box {
        background-color: rgba(255, 255, 255, 0.9);
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        border-left: 5px solid #667eea;
    }
    .login-box {
        background-color: white;
        padding: 30px;
        border-radius: 15px;
        max-width: 500px;
        margin: 50px auto;
        box-shadow: 0 10px 40px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

# Google Sheets connection
def get_sheets_service():
    try:
        # Convert secrets to proper format for credentials
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Ensure private_key has proper newlines
        if 'private_key' in creds_dict:
            creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None

def generate_user_id(email):
    """Generate a unique user ID from email"""
    return hashlib.md5(email.lower().encode()).hexdigest()[:12]

def generate_verification_code():
    """Generate a 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(to_email, code):
    """Send verification code via email"""
    try:
        from_email = st.secrets.get("alert_email", "")
        password = st.secrets.get("alert_email_password", "")
        
        if not from_email or not password:
            return False, "Email credentials not configured"
        
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = "Your Airdrop Tracker Verification Code"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white;">🪂 Airdrop Tracker</h1>
            </div>
            <div style="padding: 30px;">
                <h2>Your Verification Code</h2>
                <p>Enter this code to access your personal airdrop tracker:</p>
                <div style="background-color: #f0f0f0; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; margin: 20px 0;">
                    {code}
                </div>
                <p>This code is valid for 10 minutes.</p>
                <p style="color: #666; font-size: 12px; margin-top: 30px;">If you didn't request this code, please ignore this email.</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()
        
        return True, "Verification code sent!"
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

def load_user_data(user_id):
    """Load data for specific user from Google Sheets"""
    try:
        service = get_sheets_service()
        if not service:
            return []
        
        sheet_id = st.secrets["sheet_id"]
        
        # First check if UserData sheet exists, if not create it
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="UserData!A1:K1"
            ).execute()
        except:
            # Sheet doesn't exist or is empty, create header
            header = [['User ID', 'Protocol Name', 'Status', 'Expected Date', 'Ref Link', 
                      'Tasks Completed', 'Wallet Used', 'TX Count', 'Amount Invested', 'Last Activity', 'Notes']]
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="UserData!A1",
                valueInputOption="RAW",
                body={'values': header}
            ).execute()
            return []
        
        # Load all data
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="UserData!A:K"
        ).execute()
        
        values = result.get('values', [])
        
        if not values or len(values) < 2:
            return []
        
        # Filter data for this user
        user_data = []
        for row in values[1:]:
            if len(row) >= 11 and row[0] == user_id:
                user_data.append({
                    'Protocol Name': row[1],
                    'Status': row[2],
                    'Expected Date': row[3],
                    'Ref Link': row[4],
                    'Tasks Completed': row[5],
                    'Wallet Used': row[6],
                    'TX Count': int(row[7]) if row[7] and row[7].isdigit() else 0,
                    'Amount Invested': row[8],
                    'Last Activity': row[9],
                    'Notes': row[10]
                })
        return user_data
    except Exception as e:
        st.error(f"Error loading user data: {e}")
        return []

def save_user_data(user_id, data):
    """Save user-specific data to Google Sheets"""
    try:
        service = get_sheets_service()
        if not service:
            st.error("Could not connect to Google Sheets service")
            return False
        
        sheet_id = st.secrets["sheet_id"]
        
        # Get existing data
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="UserData!A:K"
            ).execute()
            existing_values = result.get('values', [])
        except:
            existing_values = []
        
        # Keep header and other users' data
        if not existing_values:
            filtered_values = [['User ID', 'Protocol Name', 'Status', 'Expected Date', 'Ref Link', 
                              'Tasks Completed', 'Wallet Used', 'TX Count', 'Amount Invested', 'Last Activity', 'Notes']]
        else:
            filtered_values = [existing_values[0]]
            for row in existing_values[1:]:
                if len(row) > 0 and row[0] != user_id:
                    filtered_values.append(row)
        
        # Add current user's data
        for item in data:
            filtered_values.append([
                user_id,
                item.get('Protocol Name', ''),
                item.get('Status', ''),
                item.get('Expected Date', ''),
                item.get('Ref Link', ''),
                item.get('Tasks Completed', ''),
                item.get('Wallet Used', ''),
                str(item.get('TX Count', 0)),
                item.get('Amount Invested', ''),
                item.get('Last Activity', ''),
                item.get('Notes', '')
            ])
        
        body = {'values': filtered_values}
        
        # Clear and update
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range="UserData!A:K"
        ).execute()
        
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="UserData!A1",
            valueInputOption="RAW",
            body=body
        ).execute()
        
        return True
    except Exception as e:
        st.error(f"Error saving user data: {str(e)}")
        return False

def send_email_alert(to_email, subject, body):
    """Send email notification"""
    try:
        from_email = st.secrets.get("alert_email", "")
        password = st.secrets.get("alert_email_password", "")
        
        if not from_email or not password:
            return False, "Email credentials not configured"
        
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()
        
        return True, "Email sent successfully!"
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

def check_upcoming_airdrops(airdrops, days_ahead=7):
    """Check for airdrops coming up within the specified days"""
    upcoming = []
    today = date.today()
    
    for airdrop in airdrops:
        if airdrop.get('Expected Date') and airdrop.get('Status') == 'Active':
            try:
                expected = datetime.strptime(airdrop['Expected Date'], '%Y-%m-%d').date()
                days_until = (expected - today).days
                
                if 0 <= days_until <= days_ahead:
                    airdrop['days_until'] = days_until
                    upcoming.append(airdrop)
            except:
                continue
    
    return upcoming

def generate_alert_email(upcoming_airdrops):
    """Generate HTML email for upcoming airdrops"""
    html = """
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #667eea;">🪂 Airdrop Alert!</h2>
        <p>You have upcoming airdrops ready to claim:</p>
        <table style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #667eea; color: white;">
                <th style="padding: 10px; text-align: left;">Protocol</th>
                <th style="padding: 10px; text-align: left;">Expected Date</th>
                <th style="padding: 10px; text-align: left;">Days Until</th>
                <th style="padding: 10px; text-align: left;">Ref Link</th>
            </tr>
    """
    
    for airdrop in upcoming_airdrops:
        status_color = "#4CAF50" if airdrop['days_until'] == 0 else "#FF9800"
        days_text = "TODAY!" if airdrop['days_until'] == 0 else f"{airdrop['days_until']} days"
        
        html += f"""
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 10px;">{airdrop.get('Protocol Name', 'N/A')}</td>
                <td style="padding: 10px;">{airdrop.get('Expected Date', 'N/A')}</td>
                <td style="padding: 10px; color: {status_color}; font-weight: bold;">{days_text}</td>
                <td style="padding: 10px;"><a href="{airdrop.get('Ref Link', '#')}">Claim Now</a></td>
            </tr>
        """
    
    html += """
        </table>
    </body>
    </html>
    """
    
    return html

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'verification_code' not in st.session_state:
    st.session_state.verification_code = None
if 'code_timestamp' not in st.session_state:
    st.session_state.code_timestamp = None
if 'airdrops' not in st.session_state:
    st.session_state.airdrops = []

# Login/Authentication Screen
if not st.session_state.authenticated:
    st.title("🪂 Airdrop Hunting Tracker")
    
    st.markdown("""
    <div class="login-box">
        <h2 style="color: #667eea; text-align: center;">Welcome!</h2>
        <p style="text-align: center; color: #666;">Sign in with your email to access your personal airdrop tracker</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        email = st.text_input("📧 Email Address", placeholder="your.email@example.com")
        
        if st.session_state.verification_code is None:
            if st.button("Send Verification Code", type="primary", use_container_width=True):
                if email and "@" in email:
                    code = generate_verification_code()
                    success, message = send_verification_email(email, code)
                    
                    if success:
                        st.session_state.verification_code = code
                        st.session_state.code_timestamp = datetime.now()
                        st.session_state.user_email = email
                        st.success("✅ Verification code sent! Check your email.")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                else:
                    st.error("Please enter a valid email address")
        else:
            # Check if code expired (10 minutes)
            if (datetime.now() - st.session_state.code_timestamp).seconds > 600:
                st.session_state.verification_code = None
                st.session_state.code_timestamp = None
                st.error("⏰ Verification code expired. Please request a new one.")
                st.rerun()
            
            st.info(f"📨 Code sent to {st.session_state.user_email}")
            verification_input = st.text_input("Enter 6-digit code", max_chars=6)
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Verify", type="primary", use_container_width=True):
                    if verification_input == st.session_state.verification_code:
                        st.session_state.authenticated = True
                        st.session_state.user_id = generate_user_id(st.session_state.user_email)
                        st.session_state.airdrops = load_user_data(st.session_state.user_id)
                        st.success("✅ Successfully logged in!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid code. Please try again.")
            
            with col_b:
                if st.button("Resend Code", use_container_width=True):
                    code = generate_verification_code()
                    success, message = send_verification_email(st.session_state.user_email, code)
                    if success:
                        st.session_state.verification_code = code
                        st.session_state.code_timestamp = datetime.now()
                        st.success("✅ New code sent!")
                        st.rerun()

else:
    # Main App (After Authentication)
    st.title("🪂 Airdrop Hunting Tracker")
    st.markdown(f"Logged in as: **{st.session_state.user_email}**")
    
    # Instructions box
    st.markdown("""
    <div class="info-box">
        <h3 style="color: #667eea; margin-bottom: 10px;">📋 Your Personal Tracker</h3>
        <p style="color: #666;">• Your data is private and saved to your account<br>
        • Add protocols, track progress, and set up alerts<br>
        • Download/upload CSV backups anytime<br>
        • Data automatically syncs when you make changes</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("👤 Account")
        st.write(f"**Email:** {st.session_state.user_email}")
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_email = None
            st.session_state.user_id = None
            st.session_state.airdrops = []
            st.rerun()
        
        st.markdown("---")
        st.header("📊 Statistics")
        df = pd.DataFrame(st.session_state.airdrops)
        
        if len(df) > 0:
            active_count = len(df[df['Status'] == 'Active'])
            completed_count = len(df[df['Status'] == 'Completed'])
            upcoming_count = len(df[df['Status'] == 'Upcoming'])
            
            st.metric("Total Protocols", len(df))
            st.metric("Active", active_count)
            st.metric("Completed", completed_count)
            st.metric("Upcoming", upcoming_count)
            
            total_tx = df['TX Count'].sum() if 'TX Count' in df else 0
            st.metric("Total Transactions", int(total_tx))
        
        st.markdown("---")
        st.header("💾 Data Management")
        
        # Refresh data button
        if st.button("🔄 Refresh Data"):
            st.session_state.airdrops = load_user_data(st.session_state.user_id)
            st.rerun()
        
        # Download data
        if st.session_state.airdrops:
            csv = pd.DataFrame(st.session_state.airdrops).to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"airdrop_tracker_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        # Upload data
        uploaded_file = st.file_uploader("📤 Upload CSV", type=['csv'])
        if uploaded_file is not None:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                st.session_state.airdrops = uploaded_df.to_dict('records')
                if save_user_data(st.session_state.user_id, st.session_state.airdrops):
                    st.success("✅ Data uploaded successfully!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error uploading file: {e}")
        
        st.markdown("---")
        st.header("🔔 Alert Settings")
        
        days_ahead = st.slider("Alert me X days before", 1, 30, 7)
        
        if st.button("🔍 Check Alerts Now"):
            upcoming = check_upcoming_airdrops(st.session_state.airdrops, days_ahead)
            
            if upcoming:
                st.info(f"Found {len(upcoming)} upcoming airdrop(s)!")
                
                for airdrop in upcoming:
                    days_text = "TODAY!" if airdrop['days_until'] == 0 else f"in {airdrop['days_until']} days"
                    st.write(f"🪂 **{airdrop['Protocol Name']}** - {days_text}")
                
                email_body = generate_alert_email(upcoming)
                success, message = send_email_alert(
                    st.session_state.user_email,
                    f"🪂 {len(upcoming)} Airdrop Alert(s)!",
                    email_body
                )
                
                if success:
                    st.success("✅ Alert email sent!")
                else:
                    st.error(f"❌ {message}")
            else:
                st.success(f"No airdrops in next {days_ahead} days")
    
    # Display the data table
    st.subheader("📋 Your Airdrop Portfolio")
    
    if st.session_state.airdrops:
        df = pd.DataFrame(st.session_state.airdrops)
        
        for col in ['Expected Date', 'Last Activity']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        edited_df = st.data_editor(
            df,
            use_container_width=False,
            width=1800,
            height=400,
            num_rows="dynamic",
            column_config={
                "Protocol Name": st.column_config.TextColumn("Protocol Name", width=180),
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Active", "Completed", "Upcoming"],
                    width=120
                ),
                "Expected Date": st.column_config.DateColumn("Expected Date", width=140),
                "Ref Link": st.column_config.LinkColumn("Ref Link", width=220),
                "Tasks Completed": st.column_config.TextColumn("Tasks Completed", width=280),
                "Wallet Used": st.column_config.TextColumn("Wallet Used", width=180),
                "TX Count": st.column_config.NumberColumn("TX Count", format="%d", width=100),
                "Amount Invested": st.column_config.TextColumn("Amount Invested", width=140),
                "Last Activity": st.column_config.DateColumn("Last Activity", width=140),
                "Notes": st.column_config.TextColumn("Notes", width=280)
            },
            hide_index=True,
            key="data_editor"
        )
        
        edited_df_copy = edited_df.copy()
        for col in ['Expected Date', 'Last Activity']:
            if col in edited_df_copy.columns:
                edited_df_copy[col] = edited_df_copy[col].dt.strftime('%Y-%m-%d').where(edited_df_copy[col].notna(), '')
        
        if not edited_df_copy.equals(pd.DataFrame(st.session_state.airdrops)):
            st.session_state.airdrops = edited_df_copy.to_dict('records')
            with st.spinner("Saving changes..."):
                if save_user_data(st.session_state.user_id, st.session_state.airdrops):
                    st.success("✅ Changes saved!")
                    st.rerun()
    else:
        st.info("No airdrops tracked yet. Add your first protocol below!")
    
    # Add new airdrop form
    st.markdown("---")
    st.subheader("➕ Add New Protocol")
    
    with st.form("add_airdrop_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            protocol_name = st.text_input("Protocol Name*")
            status = st.selectbox("Status", ["Active", "Upcoming", "Completed"])
            expected_date = st.date_input("Expected Date", value=None)
            ref_link = st.text_input("Referral Link")
        
        with col2:
            tasks = st.text_area("Tasks Completed", height=100)
            wallet = st.text_input("Wallet Used")
            tx_count = st.number_input("TX Count", min_value=0, value=0, step=1)
        
        with col3:
            amount_invested = st.text_input("Amount Invested (e.g., $500)")
            last_activity = st.date_input("Last Activity", value=date.today())
            notes = st.text_area("Notes", height=100)
        
        submitted = st.form_submit_button("Add Protocol", use_container_width=True)
        
        if submitted:
            if protocol_name:
                new_airdrop = {
                    'Protocol Name': protocol_name,
                    'Status': status,
                    'Expected Date': expected_date.strftime('%Y-%m-%d') if expected_date else '',
                    'Ref Link': ref_link,
                    'Tasks Completed': tasks,
                    'Wallet Used': wallet,
                    'TX Count': int(tx_count),
                    'Amount Invested': amount_invested,
                    'Last Activity': last_activity.strftime('%Y-%m-%d'),
                    'Notes': notes
                }
                st.session_state.airdrops.append(new_airdrop)
                with st.spinner("Saving..."):
                    if save_user_data(st.session_state.user_id, st.session_state.airdrops):
                        st.success(f"✅ Added {protocol_name}!")
                        st.rerun()
            else:
                st.error("Please enter a protocol name")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: white; padding: 20px;">
        <p>Built with Streamlit • Your Personal Airdrop Tracker 🚀</p>
    </div>
    """, unsafe_allow_html=True)
