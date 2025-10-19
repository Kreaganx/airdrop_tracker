import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread
from google.auth.transport.requests import Request
import json

# ==============================
# CONFIGURATION
# ==============================
st.set_page_config(page_title="Airdrop Tracker", page_icon="🪂", layout="wide")

# ==============================
# GOOGLE AUTH SETUP
# ==============================
def get_gsheet_client():
    try:
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return None


def get_calendar_service():
    try:
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        st.error(f"Error connecting to Google Calendar: {e}")
        return None


def add_to_calendar(protocol_name, expected_date, ref_link, user_email):
    try:
        service = get_calendar_service()
        if not service:
            return False, "Could not connect to Google Calendar"
        if isinstance(expected_date, str):
            event_date = datetime.strptime(expected_date, "%Y/%m/%d")
        else:
            event_date = expected_date

        event = {
            "summary": f"🪂 {protocol_name} Airdrop",
            "description": f"Airdrop claim day for {protocol_name}\n\nReferral Link: {ref_link}\n\nAdded via Airdrop Tracker",
            "start": {"date": event_date.strftime("%Y-%m-%d"), "timeZone": "UTC"},
            "end": {"date": event_date.strftime("%Y-%m-%d"), "timeZone": "UTC"},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 60}],
            },
        }

        calendar_id = st.secrets.get("calendar_id", "primary")
        service.events().insert(calendarId=calendar_id, body=event).execute()
        return True, "✅ Event successfully added to Google Calendar!"
    except Exception as e:
        return False, f"⚠️ Error adding to calendar: {str(e)}"


# ==============================
# GOOGLE SHEET HELPERS
# ==============================
SPREADSHEET_NAME = "AirdropTrackerDB"

def get_user_worksheet(email):
    client = get_gsheet_client()
    if not client:
        return None
    try:
        sheet = client.open(SPREADSHEET_NAME)
        worksheet = None
        for ws in sheet.worksheets():
            if ws.title == email:
                worksheet = ws
                break
        if not worksheet:
            worksheet = sheet.add_worksheet(title=email, rows="100", cols="15")
            worksheet.append_row(["Protocol", "Status", "Expected Date", "Referral", "Notes",
                                  "Amount", "Tasks", "Wallet", "TX Count", "Activity"])
        return worksheet
    except Exception as e:
        st.error(f"Google Sheet error: {e}")
        return None


def load_user_data(email):
    ws = get_user_worksheet(email)
    if not ws:
        return []
    data = ws.get_all_records()
    return data


def save_user_data(email, data):
    ws = get_user_worksheet(email)
    if not ws:
        return False
    df = pd.DataFrame(data)
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())
    return True


# ==============================
# CUSTOM CSS STYLING (DARK / FIXED)
# ==============================
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #1f1f2e, #24243e, #302b63);
    color: #f5f5f5;
    font-family: 'Inter', sans-serif;
}
.stApp {
    background-color: transparent;
}

/* Input & Select fields */
.stTextInput > div > div > input,
.stDateInput input,
.stTextArea textarea,
.stSelectbox > div > div > div {
    background-color: #2c2c3c !important;
    color: #ffffff !important;
    border: 1px solid #3a3a4a !important;
    border-radius: 8px;
}
.stTextInput > div > div > input::placeholder {
    color: #aaa;
}

/* Buttons */
.stButton button {
    background: linear-gradient(90deg, #007bff, #00b3b3);
    color: white !important;
    border-radius: 8px;
    border: none;
    font-weight: 600;
    padding: 0.4rem 1rem;
    transition: 0.3s ease;
}
.stButton button:hover {
    background: linear-gradient(90deg, #0099ff, #00d4d4);
    transform: scale(1.03);
}

/* Cards & Boxes */
.stContainer, .stExpander {
    background-color: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px !important;
    padding: 1rem !important;
    box-shadow: 0 4px 10px rgba(0,0,0,0.4);
}
h1, h2, h3, h4 {
    color: #ffffff !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #1b1b2b !important;
    color: #fff !important;
    border-right: 1px solid #333;
}
[data-testid="stSidebar"] a {
    color: #00b3ff !important;
}
</style>
""", unsafe_allow_html=True)

# ==============================
# LOGIN / AUTH SECTION
# ==============================
if "user_email" not in st.session_state:
    with st.container():
        st.title("🪂 Airdrop Tracker Login")
        email_input = st.text_input("Enter your email to continue:")
        if st.button("Login"):
            if email_input:
                st.session_state.user_email = email_input.strip().lower()
                st.session_state.airdrops = load_user_data(st.session_state.user_email)
                st.success(f"Welcome {st.session_state.user_email}!")
                st.rerun()
            else:
                st.error("Please enter a valid email.")
    st.stop()

# ==============================
# MAIN APP BODY
# ==============================
st.sidebar.title("📊 Statistics")
airdrops = st.session_state.get("airdrops", [])
df = pd.DataFrame(airdrops)
st.sidebar.metric("Total Protocols", len(df))
st.sidebar.metric("Active", len(df[df["Status"] == "Active"]) if not df.empty else 0)
st.sidebar.metric("Completed", len(df[df["Status"] == "Completed"]) if not df.empty else 0)

st.sidebar.divider()
if st.sidebar.button("🔁 Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.title(f"🪂 Airdrop Tracker — {st.session_state.user_email}")

# ==============================
# DISPLAY EXISTING PROTOCOLS
# ==============================
if len(airdrops) > 0:
    for p in airdrops:
        with st.expander(f"🧩 {p['Protocol']} — {p['Status']}"):
            st.write(f"📅 **Expected Date:** {p.get('Expected Date', '')}")
            st.write(f"💰 **Amount:** {p.get('Amount', '')}")
            st.write(f"📝 **Notes:** {p.get('Notes', '')}")
            st.write(f"🔗 **Referral:** {p.get('Referral', '')}")
            st.write(f"🧮 **Tasks:** {p.get('Tasks', '')}")
else:
    st.info("No airdrops added yet. Use the form below to start tracking!")

# ==============================
# ADD NEW AIRDROP FORM
# ==============================
st.markdown("### ➕ Add New Protocol")
with st.form("new_airdrop_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        protocol_name = st.text_input("Protocol Name*")
        status = st.selectbox("Status", ["Active", "Completed", "Upcoming"])
        expected_date = st.text_input("Expected Date", placeholder="YYYY/MM/DD")
        ref_link = st.text_input("Referral Link")
    with c2:
        tasks = st.text_area("Tasks Completed")
        wallet = st.text_input("Wallet Used")
        tx_count = st.number_input("TX Count", min_value=0, step=1)
    with c3:
        amount = st.text_input("Amount Invested (e.g., $500)")
        notes = st.text_area("Notes")
        last_activity = st.text_input("Last Activity", value=datetime.today().strftime("%Y/%m/%d"))
        add_to_cal = st.checkbox("📅 Add to Google Calendar")

    submitted = st.form_submit_button("Add Protocol")

    if submitted:
        if protocol_name.strip():
            new_airdrop = {
                "Protocol": protocol_name,
                "Status": status,
                "Expected Date": expected_date,
                "Referral": ref_link,
                "Notes": notes,
                "Amount": amount,
                "Tasks": tasks,
                "Wallet": wallet,
                "TX Count": tx_count,
                "Activity": last_activity,
            }

            st.session_state.airdrops.append(new_airdrop)
            with st.spinner("Saving..."):
                if save_user_data(st.session_state.user_email, st.session_state.airdrops):
                    st.success("✅ Added new protocol!")
                    if add_to_cal and expected_date:
                        success, message = add_to_calendar(
                            protocol_name,
                            expected_date,
                            ref_link,
                            st.session_state.user_email,
                        )
                        if success:
                            st.success(f"📅 {message}")
                        else:
                            st.warning(f"⚠️ {message}")
                    st.rerun()
                else:
                    st.error("❌ Failed to save to Google Sheets.")
        else:
            st.error("Please provide a Protocol Name before saving.")
