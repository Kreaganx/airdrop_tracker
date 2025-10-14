import streamlit as st
import pandas as pd
from datetime import datetime, date
import json

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
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if 'airdrops' not in st.session_state:
    st.session_state.airdrops = [
        {
            'Protocol Name': 'LayerZero',
            'Status': 'Active',
            'Expected Date': '2025-12-31',
            'Ref Link': 'https://ref.layerzero.com/example',
            'Tasks Completed': 'Bridge transactions, Provide liquidity, Daily check-in',
            'Wallet Used': '0x742d...5678',
            'TX Count': 25,
            'Amount Invested': '$500',
            'Last Activity': '2025-10-14',
            'Notes': 'Meeting criteria for power user tier'
        }
    ]

# Title and description
st.title("🪂 Airdrop Hunting Tracker")
st.markdown("Track your airdrop farming activities across multiple protocols")

# Instructions box
st.markdown("""
<div class="info-box">
    <h3 style="color: #667eea; margin-bottom: 10px;">📋 How to Use This App</h3>
    <p style="color: #666;">• Add new protocols using the form below<br>
    • Edit existing entries by clicking on cells in the table<br>
    • Download your data as CSV for backup<br>
    • Upload previous CSV files to restore your data</p>
</div>
""", unsafe_allow_html=True)

# Sidebar for statistics
with st.sidebar:
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
            st.success("Data uploaded successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Error uploading file: {e}")

# Display the data table
st.subheader("📋 Your Airdrop Portfolio")

if st.session_state.airdrops:
    df = pd.DataFrame(st.session_state.airdrops)
    
    # Convert date strings to datetime for proper display
    for col in ['Expected Date', 'Last Activity']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Make the dataframe editable
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Protocol Name": st.column_config.TextColumn("Protocol Name", width="medium"),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["Active", "Completed", "Upcoming"],
                width="small"
            ),
            "Expected Date": st.column_config.DateColumn("Expected Date"),
            "Ref Link": st.column_config.LinkColumn("Ref Link", width="medium"),
            "Tasks Completed": st.column_config.TextColumn("Tasks Completed", width="large"),
            "Wallet Used": st.column_config.TextColumn("Wallet Used", width="medium"),
            "TX Count": st.column_config.NumberColumn("TX Count", format="%d"),
            "Amount Invested": st.column_config.TextColumn("Amount Invested", width="small"),
            "Last Activity": st.column_config.DateColumn("Last Activity"),
            "Notes": st.column_config.TextColumn("Notes", width="large")
        },
        hide_index=True,
        key="data_editor"
    )
    
    # Convert dates back to strings for storage and update session state
    edited_df_copy = edited_df.copy()
    for col in ['Expected Date', 'Last Activity']:
        if col in edited_df_copy.columns:
            edited_df_copy[col] = edited_df_copy[col].dt.strftime('%Y-%m-%d').where(edited_df_copy[col].notna(), '')
    
    # Update session state with edited data
    if not edited_df_copy.equals(pd.DataFrame(st.session_state.airdrops)):
        st.session_state.airdrops = edited_df_copy.to_dict('records')
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
            st.success(f"✅ Added {protocol_name} to your tracker!")
            st.rerun()
        else:
            st.error("Please enter a protocol name")

# Delete all data option
st.markdown("---")
if st.button("🗑️ Clear All Data", type="secondary"):
    if st.session_state.airdrops:
        st.session_state.airdrops = []
        st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: white; padding: 20px;">
    <p>Built with Streamlit • Track your airdrops like a pro 🚀</p>
</div>
""", unsafe_allow_html=True)