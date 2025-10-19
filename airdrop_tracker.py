import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, date, timedelta
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
        creds_dict = dict(st.secrets["gcp_service_account"])
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

def get_calendar_service():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if 'private_key' in creds_dict:
            creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        service = build('calendar', 'v3', credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Error connecting to Google Calendar: {e}")
        return None

def generate_user_id(email):
    return hashlib.md5(email.lower().encode()).hexdigest()[:12]

def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(to_email, code):
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
    try:
        service = get_sheets_service()
        if not service:
            return []
        sheet_id = st.secrets["sheet_id"]
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="UserData!A1:K1"
            ).execute()
        except:
            header = [['User ID', 'Protocol Name', 'Status', 'Expected Date', 'Ref Link', 
                      'Tasks Completed', 'Wallet Used', 'TX Count', 'Amount Invested', 'Last Activity', 'Notes']]
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="UserData!A1",
                valueInputOption="RAW",
                body={'values': header}
            ).execute()
            return []
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="UserData!A:K"
        ).execute()
        values = result.get('values', [])
        if not values or len(values) < 2:
            return []
        user_data = []
        for row in values[1:]:
            if len(row) > 0:
                row_user_id = row[0] if len(row) > 0 else ""
                if row_user_id == user_id and len(row) >= 2:
                    user_data.append({
                        'Protocol Name': row[1] if len(row) > 1 else '',
                        'Status': row[2] if len(row) > 2 else 'Active',
                        'Expected Date': row[3] if len(row) > 3 else '',
                        'Ref Link': row[4] if len(row) > 4 else '',
                        'Tasks Completed': row[5] if len(row) > 5 else '',
                        'Wallet Used': row[6] if len(row) > 6 else '',
                        'TX Count': int(row[7]) if len(row) > 7 and row[7] and str(row[7]).replace('-','').isdigit() else 0,
                        'Amount Invested': row[8] if len(row) > 8 else '',
                        'Last Activity': row[9] if len(row) > 9 else '',
                        'Notes': row[10] if len(row) > 10 else ''
                    })
        return user_data
    except Exception as e:
        st.error(f"Error loading user data: {e}")
        return []

def save_user_data(user_id, data):
    try:
        service = get_sheets_service()
        if not service:
            return False
        sheet_id = st.secrets["sheet_id"]
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="UserData!A:K"
            ).execute()
            existing_values = result.get('values', [])
        except:
            existing_values = []
        if not existing_values:
            filtered_values = [['User ID', 'Protocol Name', 'Status', 'Expected Date', 'Ref Link', 
                              'Tasks Completed', 'Wallet Used', 'TX Count', 'Amount Invested', 'Last Activity', 'Notes']]
        else:
            filtered_values = [existing_values[0]]
            for row in existing_values[1:]:
                if len(row) > 0 and row[0] != user_id:
                    filtered_values.append(row)
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

def add_to_calendar(protocol_name, expected_date, ref_link, user_email):
    try:
        service = get_calendar_service()
        if not service:
            return False, "Could not connect to Google Calendar"
        if isinstance(expected_date, str):
            event_date = datetime.strptime(expected_date, '%Y-%m-%d')
        else:
            event_date = expected_date
        event = {
            'summary': f'🪂 {protocol_name} Airdrop',
            'description': f'Airdrop claim day for {protocol_name}\n\nReferral Link: {ref_link}\n\nAdded via Airdrop Tracker',
            'start': {
                'date': event_date.strftime('%Y-%m-%d'),
                'timeZone': 'America/New_York',
            },
            'end': {
                'date': event_date.strftime('%Y-%m-%d'),
                'timeZone': 'America/New_York',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 60},
                ],
            },
            'attendees': [
                {'email': user_email}
            ]
        }
        calendar_id = st.secrets.get("calendar_id", "primary")
        event = service.events().insert(calendarId=calendar_id, body=event, sendNotifications=True).execute()
        return True, f"Added to calendar!"
    except Exception as e:
        return False, f"Error adding to calendar: {str(e)}"

def send_email_alert(to_email, subject, body):
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
                        with st.spinner("Loading your data..."):
                            st.session_state.airdrops = load_user_data(st.session_state.user_id)
                        st.success(f"✅ Successfully logged in! Loaded {len(st.session_state.airdrops)} entries.")
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
    st.markdown(f"Logged in as: **{st.session_state.user_email}** (ID: `{st.session_state.user_id}`)")
    
    # Debug info
    with st.expander("🔍 Debug Info"):
        st.write(f"User ID: {st.session_state.user_id}")
        st.write(f"Number of airdrops in memory: {len(st.session_state.airdrops)}")
        if st.button("Force Reload from Sheets"):
            st.session_state.airdrops = load_user_data(st.session_state.user_id)
            st.success(f"Loaded {len(st.session_state.airdrops)} entries from Google Sheets")
            st.rerun()
    
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
        if st.button("🔄 Refresh Data"):
            st.session_state.airdrops = load_user_data(st.session_state.user_id)
            st.rerun()
        if st.session_state.airdrops:
            csv = pd.DataFrame(st.session_state.airdrops).to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"airdrop_tracker_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
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
    
    # Display airdrops as cards
    st.subheader("📋 Your Airdrop Portfolio")
    
    if st.session_state.airdrops:
        col_filter1, col_filter2 = st.columns([1, 3])
        with col_filter1:
            filter_status = st.selectbox("Filter by Status", ["All", "Active", "Upcoming", "Completed"])
        filtered_airdrops = st.session_state.airdrops if filter_status == "All" else [
            a for a in st.session_state.airdrops if a.get('Status') == filter_status
        ]
        if not filtered_airdrops:
            st.info(f"No {filter_status.lower()} airdrops found.")
        else:
            for idx, airdrop in enumerate(filtered_airdrops):
                status = airdrop.get('Status', 'Active')
                if status == 'Active':
                    status_color = "#4CAF50"
                    status_icon = "🟢"
                elif status == 'Upcoming':
                    status_icon = "🟡"
                    status_color = "#FF9800"
                else:
                    status_icon = "⚪"
                    status_color = "#9E9E9E"
                days_until_text = ""
                if airdrop.get('Expected Date'):
                    try:
                        expected = datetime.strptime(airdrop['Expected Date'], '%Y-%m-%d').date()
                        days_until = (expected - date.today()).days
                        if days_until == 0:
                            days_until_text = "📅 TODAY!"
                        elif days_until > 0:
                            days_until_text = f"📅 {days_until} days"
                        else:
                            days_until_text = f"📅 {abs(days_until)} days ago"
                    except:
                        pass
                with st.expander(f"{status_icon} **{airdrop.get('Protocol Name', 'Unknown')}** - {status} {days_until_text}", expanded=False):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"""
                        <div style="background: white; padding: 20px; border-radius: 10px; border-left: 5px solid {status_color};">
                            <h3 style="color: #667eea; margin-top: 0;">{airdrop.get('Protocol Name', 'Unknown')}</h3>
                            <p style="margin: 5px 0;"><strong>Status:</strong> <span style="color: {status_color};">{status}</span></p>
                            <p style="margin: 5px 0;"><strong>Expected Date:</strong> {airdrop.get('Expected Date', 'Not set')} {days_until_text}</p>
                            <p style="margin: 5px 0;"><strong>Wallet:</strong> <code>{airdrop.get('Wallet Used', 'N/A')}</code></p>
                            <p style="margin: 5px 0;"><strong>TX Count:</strong> {airdrop.get('TX Count', 0)}</p>
                            <p style="margin: 5px 0;"><strong>Amount Invested:</strong> {airdrop.get('Amount Invested', 'N/A')}</p>
                            <p style="margin: 5px 0;"><strong>Last Activity:</strong> {airdrop.get('Last Activity', 'N/A')}</p>
                            <p style="margin: 10px 0 5px 0;"><strong>Tasks Completed:</strong></p>
                            <p style="margin: 0; padding: 10px; background: #f5f5f5; border-radius: 5px;">{airdrop.get('Tasks Completed', 'None')}</p>
                            <p style="margin: 10px 0 5px 0;"><strong>Notes:</strong></p>
                            <p style="margin: 0; padding: 10px; background: #f5f5f5; border-radius: 5px;">{airdrop.get('Notes', 'None')}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        if airdrop.get('Ref Link'):
                            st.link_button("🔗 Open Referral Link", airdrop.get('Ref Link'), use_container_width=True)
                    with col2:
                        if st.button("✏️ Edit", key=f"edit_{idx}", use_container_width=True):
                            st.session_state[f'editing_{idx}'] = True
                            st.rerun()
                        if st.button("🗑️ Delete", key=f"delete_{idx}", type="secondary", use_container_width=True):
                            actual_idx = st.session_state.airdrops.index(airdrop)
                            st.session_state.airdrops.pop(actual_idx)
                            with st.spinner("Deleting..."):
                                if save_user_data(st.session_state.user_id, st.session_state.airdrops):
                                    st.success("✅ Deleted!")
                                    st.rerun()
                        if airdrop.get('Expected Date') and status != 'Completed':
                            if st.button("📅 Add to Cal", key=f"cal_{idx}", use_container_width=True):
                                with st.spinner("Adding to calendar..."):
                                    success, message = add_to_calendar(
                                        airdrop.get('Protocol Name'),
                                        airdrop.get('Expected Date'),
                                        airdrop.get('Ref Link', ''),
                                        st.session_state.user_email
                                    )
                                    if success:
                                        st.success(f"📅 {message}")
                                    else:
                                        st.warning(f"⚠️ {message}")
                    if st.session_state.get(f'editing_{idx}', False):
                        st.markdown("---")
                        st.subheader("Edit Entry")
                        with st.form(key=f"edit_form_{idx}"):
                            edit_col1, edit_col2, edit_col3 = st.columns(3)
                            with edit_col1:
                                new_protocol = st.text_input("Protocol Name", value=airdrop.get('Protocol Name', ''))
                                new_status = st.selectbox("Status", ["Active", "Upcoming", "Completed"], 
                                                         index=["Active", "Upcoming", "Completed"].index(airdrop.get('Status', 'Active')))
                                new_expected = st.date_input("Expected Date", 
                                                            value=datetime.strptime(airdrop.get('Expected Date'), '%Y-%m-%d').date() if airdrop.get('Expected Date') else None)
                                new_ref = st.text_input("Ref Link", value=airdrop.get('Ref Link', ''))
                            with edit_col2:
                                new_tasks = st.text_area("Tasks Completed", value=airdrop.get('Tasks Completed', ''))
                                new_wallet = st.text_input("Wallet Used", value=airdrop.get('Wallet Used', ''))
                                new_tx = st.number_input("TX Count", min_value=0, value=int(airdrop.get('TX
