import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION & CASTECH BRAND STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Castech OT tool",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    /* Global Theme & Slate Background */
    .main { background-color: #f8fafc; color: #0f172a; font-family: 'Inter', sans-serif; }
    
    /* Top Header Bar */
    .castech-header {
        background-color: #0f172a;
        color: white;
        padding: 16px 24px;
        border-radius: 16px;
        margin-bottom: 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* Card Containers */
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 16px;
    }
    
    /* Buttons & Inputs */
    .stButton>button { border-radius: 12px; font-weight: 600; padding: 8px 16px; transition: all 0.2s; }
    div[data-baseweb="select"] > div { border-radius: 12px !important; }
    input { border-radius: 12px !important; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# DATABASE INITIALIZATION (SQLite Shared Cloud Backend)
# -----------------------------------------------------------------------------
DB_FILE = "castech_ot_shared.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                code TEXT,
                name TEXT,
                role TEXT,
                monthly_net_salary REAL,
                transport_rate REAL
            )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS holidays (
                id TEXT PRIMARY KEY,
                date TEXT,
                name TEXT
            )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY,
                worker_id TEXT,
                worker_name TEXT,
                worker_code TEXT,
                date TEXT,
                day_name TEXT,
                day_type TEXT,
                holiday_name TEXT,
                shift_summary TEXT,
                hours_135 REAL,
                hours_175 REAL,
                hours_200 REAL,
                hours_300 REAL,
                total_hours REAL,
                hourly_rate REAL,
                trips INTEGER,
                ot_pay REAL,
                transport_pay REAL,
                total_pay REAL,
                notes TEXT
            )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')
    
    c.execute("SELECT COUNT(*) FROM workers")
    if c.fetchone()[0] == 0:
        default_workers = [
            ('w_1', 'EMP-001', 'Ahmed Mahmoud', 'Operations Lead', 9500.0, 35.0),
            ('w_2', 'EMP-002', 'Sara Ibrahim', 'Logistics Coordinator', 8400.0, 30.0),
            ('w_3', 'EMP-003', 'Omar Khaled', 'Technician', 6720.0, 25.0)
        ]
        c.executemany("INSERT INTO workers VALUES (?, ?, ?, ?, ?, ?)", default_workers)
        
        default_holidays = [
            ('h_1', '2026-01-07', 'Coptic Christmas'),
            ('h_2', '2026-04-25', 'Sinai Liberation Day'),
            ('h_3', '2026-05-01', 'Labor Day'),
            ('h_4', '2026-07-23', 'Revolution Day'),
            ('h_5', '2026-10-06', 'Armed Forces Day')
        ]
        c.executemany("INSERT INTO holidays VALUES (?, ?, ?)", default_holidays)
        
        default_settings = [
            ('currency', 'EGP'),
            ('month_hours', '240'),
            ('day_start', '06:00'),
            ('night_start', '18:00')
        ]
        c.executemany("INSERT INTO settings VALUES (?, ?)", default_settings)
        
    conn.commit()
    conn.close()

init_db()

# -----------------------------------------------------------------------------
# DATA LOADERS & CRUD HELPERS
# -----------------------------------------------------------------------------
def load_data():
    conn = sqlite3.connect(DB_FILE)
    workers = pd.read_sql("SELECT * FROM workers", conn)
    holidays = pd.read_sql("SELECT * FROM holidays", conn)
    entries = pd.read_sql("SELECT * FROM entries", conn)
    settings_df = pd.read_sql("SELECT * FROM settings", conn)
    conn.close()
    
    settings = dict(zip(settings_df['key'], settings_df['value']))
    settings['month_hours'] = int(settings.get('month_hours', 240))
    return workers, holidays, entries, settings

def save_worker_db(w_id, code, name, role, monthly, transport):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO workers VALUES (?, ?, ?, ?, ?, ?)", (w_id, code, name, role, monthly, transport))
    conn.commit()
    conn.close()

def delete_worker_db(w_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM workers WHERE id = ?", (w_id,))
    conn.commit()
    conn.close()

def save_holiday_db(h_id, date, name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO holidays VALUES (?, ?, ?)", (h_id, date, name))
    conn.commit()
    conn.close()

def delete_holiday_db(h_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM holidays WHERE id = ?", (h_id,))
    conn.commit()
    conn.close()

def add_entry_db(entry_data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", entry_data)
    conn.commit()
    conn.close()

def delete_entry_db(e_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM entries WHERE id = ?", (e_id,))
    conn.commit()
    conn.close()

def update_setting_db(key, val):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO settings VALUES (?, ?)", (key, str(val)))
    conn.commit()
    conn.close()

workers_df, holidays_df, entries_df, settings = load_data()
currency = settings.get('currency', 'EGP')
month_hours = int(settings.get('month_hours', 240))

# -----------------------------------------------------------------------------
# TOP NAVIGATION & BRANDING HEADER
# -----------------------------------------------------------------------------
st.markdown("""
    <div class="castech-header">
        <div>
            <h2 style="margin:0; font-size:22px; font-weight:700;">CASTECH® Castech OT tool</h2>
            <p style="margin:2px 0 0 0; font-size:12px; color:#94a3b8;">Overtime & Transportation Allowance Calculator (Streamlit Edition)</p>
        </div>
        <div style="background:#10b981; color:white; padding:6px 14px; border-radius:20px; font-size:11px; font-weight:600;">
            🟢 Cloud Live Sync Active
        </div>
    </div>
""", unsafe_allow_html=True)

# Navigation Tabs matching HTML version
tab_calc, tab_workers, tab_holidays, tab_settings = st.tabs([
    "📊 Log & Summary", 
    f"👥 Workers ({len(workers_df)})", 
    f"🗓️ Holidays ({len(holidays_df)})", 
    "⚙️ Rules & Backup"
])

# -----------------------------------------------------------------------------
# TAB 1: CALCULATOR, LOGS & FINANCE SUMMARY
# -----------------------------------------------------------------------------
with tab_calc:
    if workers_df.empty:
        st.warning("⚠️ No workers found. Please add workers in the 'Workers' tab first.")
    else:
        with st.form("ot_entry_form"):
            st.markdown("### ➕ Log Overtime Entry")
            st.caption("Select worker, date, and hours. Rates & transport trips auto-adjust for Fri/Sat & Holidays.")
            
            c1, c2 = st.columns(2)
            with c1:
                worker_options = {f"{row['name']} ({row['code']})": row['id'] for _, row in workers_df.iterrows()}
                selected_w_name = st.selectbox("Worker *", list(worker_options.keys()))
                worker_id = worker_options[selected_w_name]
                worker_row = workers_df[workers_df['id'] == worker_id].iloc[0]
            with c2:
                work_date = st.date_input("Work Date *", value=datetime.today())
                
            st.markdown("##### Shift & Time Method")
            time_mode = st.radio("Time Entry Method", ["Start & End Time (Auto 6 PM Night Split)", "Direct Manual Hours"], horizontal=True, label_visibility="collapsed")
            
            if "Start & End" in time_mode:
                sc1, sc2, sc3 = st.columns(3)
                start_time = sc1.time_input("Start Time *", value=datetime.strptime("17:00", "%H:%M").time())
                end_time = sc2.time_input("End Time *", value=datetime.strptime("21:00", "%H:%M").time())
                time_override = sc3.selectbox("Shift Classification", ["Auto-Split (6 PM Night Cutoff)", "Force Morning OT (1.35x)", "Force Night OT (1.7x)"])
            else:
                mc1, mc2 = st.columns(2)
                manual_hours = mc1.number_input("Total Overtime Hours *", min_value=0.25, max_value=24.0, value=2.0, step=0.25)
                manual_shift = mc2.selectbox("Shift Period", ["Morning / Day OT (1.35x)", "Night OT (1.7x)"])
                
            tc1, tc2 = st.columns(2)
            with tc1:
                transport_mode = st.selectbox("Transportation Allowance", [
                    "Auto (1 Trip Wkday / Roundtrip Wkend & Holiday)", 
                    "Force 1 Trip (Single)", 
                    "Force 2 Trips (Roundtrip)", 
                    "None (0 Trips - Already Claimed Today)"
                ])
            with tc2:
                notes = st.text_input("Task / Notes (Optional)", placeholder="e.g., Inventory audit, urgent shipment...")
                
            submitted = st.form_submit_button("✅ Add Overtime Record", use_container_width=True)
            if submitted:
                date_str = work_date.strftime("%Y-%m-%d")
                day_name = work_date.strftime("%A")
                
                # Classify date
                day_type = "weekday"
                holiday_name = ""
                matched_hol = holidays_df[holidays_df['date'] == date_str]
                if not matched_hol.empty:
                    day_type = "holiday"
                    holiday_name = matched_hol.iloc[0]['name']
                elif work_date.weekday() in [4, 5]: # Friday & Saturday in Egypt
                    day_type = "weekend"
                    
                # Compute hours
                h135, h175, h200, h300 = 0.0, 0.0, 0.0, 0.0
                shift_summary = ""
                
                if "Start & End" in time_mode:
                    start_mins = start_time.hour * 60 + start_time.minute
                    end_mins = end_time.hour * 60 + end_time.minute
                    if end_mins <= start_mins:
                        end_mins += 24 * 60
                    total_hours = (end_mins - start_mins) / 60.0
                    shift_summary = f"{start_time.strftime('%H:%M')} – {end_time.strftime('%H:%M')}"
                    
                    if day_type == "holiday":
                        h300 = total_hours
                    elif day_type == "weekend":
                        h200 = total_hours
                    else:
                        if "Morning" in time_override:
                            h135 = total_hours
                            shift_summary += " (Morning)"
                        elif "Night" in time_override:
                            h175 = total_hours
                            shift_summary += " (Night)"
                        else:
                            night_cutoff = 18 * 60
                            morn_m, night_m = 0, 0
                            for t in range(start_mins, end_mins):
                                mod = t % 1440
                                if mod >= 360 and mod < night_cutoff:
                                    morn_m += 1
                                else:
                                    night_m += 1
                            h135 = morn_m / 60.0
                            h175 = night_m / 60.0
                else:
                    total_hours = manual_hours
                    shift_summary = f"{manual_hours}h"
                    if day_type == "holiday":
                        h300 = total_hours
                    elif day_type == "weekend":
                        h200 = total_hours
                    else:
                        if "Night" in manual_shift:
                            h175 = total_hours
                            shift_summary += " (Night)"
                        else:
                            h135 = total_hours
                            shift_summary += " (Morning)"

                hourly_rate = float(worker_row['monthly_net_salary']) / month_hours
                existing_today = not entries_df[(entries_df['worker_id'] == worker_id) & (entries_df['date'] == date_str)].empty
                
                if "Auto" in transport_mode:
                    trips = 0 if existing_today else (2 if day_type in ["holiday", "weekend"] else 1)
                elif "1 Trip" in transport_mode:
                    trips = 1
                elif "2 Trips" in transport_mode:
                    trips = 2
                else:
                    trips = 0
                    
                ot_pay = (h135 * hourly_rate * 1.35) + (h175 * hourly_rate * 1.70) + (h200 * hourly_rate * 2.00) + (h300 * hourly_rate * 3.00)
                transport_pay = trips * float(worker_row['transport_rate'])
                total_pay = ot_pay + transport_pay
                
                entry_id = f"ot_{datetime.now().strftime('%Y%m%d%H%M%S_%f')}"
                add_entry_db((
                    entry_id, worker_id, worker_row['name'], worker_row['code'], date_str,
                    day_name, day_type, holiday_name, shift_summary, h135, h175, h200, h300,
                    total_hours, hourly_rate, trips, ot_pay, transport_pay, total_pay, notes
                ))
                st.success(f"Added {total_hours:.2f}h overtime for {worker_row['name']}!")
                st.rerun()

    st.divider()

    # Filters & KPI Header matching HTML version
    st.markdown("### 📊 Summary Period & Filters")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        filter_worker = st.selectbox("Worker Filter", ["All Workers"] + list(workers_df['name'].unique() if not workers_df.empty else []))
    with fc2:
        filter_month = st.text_input("Month Filter (YYYY-MM)", placeholder="e.g. 2026-04")
    with fc3:
        filter_from = st.date_input("Date From", value=None)
    with fc4:
        filter_to = st.date_input("Date To", value=None)
        
    filtered_entries = entries_df.copy()
    if not filtered_entries.empty:
        if filter_worker != "All Workers":
            filtered_entries = filtered_entries[filtered_entries['worker_name'] == filter_worker]
        if filter_month:
            filtered_entries = filtered_entries[filtered_entries['date'].str.startswith(filter_month)]
        if filter_from:
            filtered_entries = filtered_entries[filtered_entries['date'] >= filter_from.strftime("%Y-%m-%d")]
        if filter_to:
            filtered_entries = filtered_entries[filtered_entries['date'] <= filter_to.strftime("%Y-%m-%d")]

    # KPI Metric Cards
    if not filtered_entries.empty:
        tot_hrs = filtered_entries['total_hours'].sum()
        tot_ot = filtered_entries['ot_pay'].sum()
        tot_trans = filtered_entries['transport_pay'].sum()
        tot_grand = filtered_entries['total_pay'].sum()
        
        kc1, kc2, kc3, kc4 = st.columns(4)
        kc1.metric("Total OT Hours", f"{tot_hrs:.2f} hrs", f"1.35x: {filtered_entries['hours_135'].sum():.1f}h | 1.7x: {filtered_entries['hours_175'].sum():.1f}h")
        kc2.metric("Total Overtime Pay", f"{currency} {tot_ot:.2f}", f"Across {len(filtered_entries)} entries")
        kc3.metric("Transport Allowance", f"{currency} {tot_trans:.2f}", f"{filtered_entries['trips'].sum()} total trips")
        kc4.metric("Grand Total Payout", f"{currency} {tot_grand:.2f}", "Ready for Finance")
    else:
        kc1, kc2, kc3, kc4 = st.columns(4)
        kc1.metric("Total OT Hours", "0.00 hrs")
        kc2.metric("Total Overtime Pay", f"{currency} 0.00")
        kc3.metric("Transport Allowance", f"{currency} 0.00")
        kc4.metric("Grand Total Payout", f"{currency} 0.00")

    st.divider()

    # Worker Payroll Summary Table
    st.markdown("### 📋 Worker Payroll Summary (Finance Sheet)")
    if not filtered_entries.empty:
        summary = filtered_entries.groupby(['worker_code', 'worker_name']).agg(
            {'hourly_rate': 'first', 'hours_135': 'sum', 'hours_175': 'sum', 'hours_200': 'sum', 'hours_300': 'sum',
             'ot_pay': 'sum', 'trips': 'sum', 'transport_pay': 'sum', 'total_pay': 'sum'}
        ).reset_index()
        
        summary.columns = ['ID', 'Worker Name', 'Hourly Rate', 'Morn (1.35x)', 'Night (1.7x)', 'Wkend (2x)', 'Hol (3x)', 'OT Pay', 'Trips', 'Transport Pay', 'Total Payout']
        st.dataframe(summary, use_container_width=True)
        
        # CSV Export
        csv_data = summary.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Worker Summary (CSV)", data=csv_data, file_name="Castech_Worker_Summary.csv", mime="text/csv")
    else:
        st.info("No records match the current filter for payroll summary.")

    st.divider()

    # Detailed Overtime Logs Table with Advanced Search & Filters
    st.markdown("### 📑 Detailed Overtime Log Entries")
    if not entries_df.empty:
        dc1, dc2, dc3 = st.columns(3)
        log_daytype = dc1.selectbox("Day Type Filter", ["All Day Types", "weekday", "weekend", "holiday"])
        log_search = dc2.text_input("Search Notes / Date", placeholder="Search keyword...")
        log_sort = dc3.selectbox("Sort Order", ["Date: Oldest First", "Date: Newest First"])
        
        log_filtered = filtered_entries.copy()
        if log_daytype != "All Day Types":
            log_filtered = log_filtered[log_filtered['day_type'] == log_daytype]
        if log_search:
            log_filtered = log_filtered[log_filtered['notes'].str.contains(log_search, case=False, na=False) | log_filtered['date'].str.contains(log_search)]
            
        if log_sort == "Date: Newest First":
            log_filtered = log_filtered.sort_values(by="date", ascending=False)
        else:
            log_filtered = log_filtered.sort_values(by="date", ascending=True)
            
        st.dataframe(log_filtered[['date', 'day_name', 'worker_name', 'day_type', 'shift_summary', 'total_hours', 'ot_pay', 'trips', 'transport_pay', 'total_pay', 'notes']], use_container_width=True)
        
        if st.button("🗑️ Clear Filtered Log Entries"):
            if not log_filtered.empty:
                ids_to_del = log_filtered['id'].tolist()
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                for eid in ids_to_del:
                    c.execute("DELETE FROM entries WHERE id = ?", (eid,))
                conn.commit()
                conn.close()
                st.success("Deleted selected log entries.")
                st.rerun()
    else:
        st.info("No detailed log entries found.")

# -----------------------------------------------------------------------------
# TAB 2: WORKERS & MONTHLY NET SALARY MANAGEMENT
# -----------------------------------------------------------------------------
with tab_workers:
    st.markdown("### 👥 Manage Workers & Monthly Net Salary Rates")
    
    with st.form("worker_add_form"):
        rc1, rc2, rc3 = st.columns(3)
        w_name = rc1.text_input("Full Name *")
        w_code = rc2.text_input("Employee ID", value=f"EMP-00{len(workers_df)+1}")
        w_role = rc3.text_input("Department / Role", value="Technician")
        
        rc4, rc5 = st.columns(2)
        w_monthly = rc4.number_input("Monthly Net Salary (EGP) *", min_value=1.0, value=8500.0, step=100.0)
        w_transport = rc5.number_input("1-Trip Transport Allowance (EGP) *", min_value=0.0, value=35.0, step=5.0)
        
        st.caption(f"Derived Hourly Rate: **{currency} {(w_monthly / month_hours):.4f} / hr** (Divided by {month_hours}h monthly divisor)")
        
        if st.form_submit_button("💾 Save Worker Profile"):
            if w_name:
                w_id = f"w_{datetime.now().strftime('%H%M%S_%f')}"
                save_worker_db(w_id, w_code, w_name, w_role, w_monthly, w_transport)
                st.success(f"Successfully added worker {w_name}!")
                st.rerun()
            else:
                st.error("Please enter a worker name.")
                
    st.markdown("### Saved Workers Directory")
    if not workers_df.empty:
        for _, row in workers_df.iterrows():
            hourly = row['monthly_net_salary'] / month_hours
            col1, col2 = st.columns([5, 1])
            col1.write(f"**{row['name']}** ({row['code']}) — {row['role']} | Monthly: {currency} {row['monthly_net_salary']} | Hourly: **{currency} {hourly:.2f}/hr** | Transport: {currency} {row['transport_rate']}")
            if col2.button("Delete", key=f"del_w_{row['id']}"):
                delete_worker_db(row['id'])
                st.rerun()

# -----------------------------------------------------------------------------
# TAB 3: PUBLIC HOLIDAYS (3.0x RATE + ROUNDTRIP TRANSPORT)
# -----------------------------------------------------------------------------
with tab_holidays:
    st.markdown("### 🗓️ Register Public Holidays (3.0x Rate)")
    st.caption("Overtime logged on registered public holidays automatically applies 3.0x hourly rate and 2 transport trips.")
    
    with st.form("holiday_add_form"):
        h_name = st.text_input("Holiday Name *", placeholder="e.g., Eid Al-Fitr Day 1")
        h_date = st.date_input("Holiday Date *")
        if st.form_submit_button("➕ Register Holiday (3x Rate)"):
            if h_name:
                h_id = f"h_{datetime.now().strftime('%H%M%S_%f')}"
                save_holiday_db(h_id, h_date.strftime("%Y-%m-%d"), h_name)
                st.success(f"Registered holiday: {h_name}!")
                st.rerun()
                
    st.markdown("### Registered Public Holidays")
    if not holidays_df.empty:
        for _, row in holidays_df.iterrows():
            c1, c2 = st.columns([5, 1])
            c1.write(f"📅 **{row['date']}** — {row['name']} *(3.0x OT Rate)*")
            if c2.button("Remove", key=f"del_h_{row['id']}"):
                delete_holiday_db(row['id'])
                st.rerun()

# -----------------------------------------------------------------------------
# TAB 4: RULES, SHIFT CUTOFFS & CLOUD SHARING INSTRUCTIONS
# -----------------------------------------------------------------------------
with tab_settings:
    st.markdown("### ⚙️ Shift Cutoffs & Calculation Rules")
    
    with st.form("settings_save_form"):
        sc1, sc2 = st.columns(2)
        set_curr = sc1.text_input("Currency Symbol / Code", value=currency)
        set_m_hrs = sc2.number_input("Monthly Working Hours Divisor", value=month_hours, min_value=1, max_value=744)
        
        if st.form_submit_button("Save Settings"):
            update_setting_db("currency", set_curr)
            update_setting_db("month_hours", set_m_hrs)
            st.success("Settings updated successfully!")
            st.rerun()
            
    st.divider()
    st.markdown("### 🌐 How Managers See All Data Instantly")
    st.success("""
    **Collaboration & Real-Time Syncing:**
    - Because this app is powered by a shared SQLite database (`castech_ot_shared.db`), **anyone who opens the app URL will see the exact same data instantly**!
    - To share this online with your managers, you can deploy this `app.py` file for free on **Streamlit Community Cloud** (`share.streamlit.io`) by connecting a free GitHub repository. Once hosted, send the link to your managers—whenever you log an overtime shift, they will see it update in real time when refreshing their browser!
    """)
