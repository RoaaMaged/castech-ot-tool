import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Castech OT & Payroll Tool",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .stButton>button { border-radius: 10px; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# DATABASE INITIALIZATION (SQLite Cloud Storage / Shared File Backend)
# -----------------------------------------------------------------------------
DB_FILE = "castech_ot_shared.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Workers table
    c.execute('''CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                code TEXT,
                name TEXT,
                role TEXT,
                monthly_net_salary REAL,
                transport_rate REAL
            )''')
    
    # Holidays table
    c.execute('''CREATE TABLE IF NOT EXISTS holidays (
                id TEXT PRIMARY KEY,
                date TEXT,
                name TEXT
            )''')
    
    # Overtime entries table
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
    
    # Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')
    
    # Insert defaults if empty
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
# DATA LOADERS & HELPERS
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
# NAVIGATION HEADER
# -----------------------------------------------------------------------------
st.title("⚙️ Castech OT & Payroll Tool")
st.caption("Shared Management Dashboard — Any manager opening this app URL sees real-time synced data.")

tabs = st.tabs(["📊 Calculator & Summary", "👥 Workers Directory", "🗓️ Public Holidays", "⚙️ Rules & Settings"])

# -----------------------------------------------------------------------------
# TAB 1: CALCULATOR & SUMMARY
# -----------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Log Overtime Shift")
    
    if workers_df.empty:
        st.warning("Please add workers in the 'Workers Directory' tab first.")
    else:
        with st.form("ot_form"):
            col1, col2 = st.columns(2)
            with col1:
                worker_options = {row['name'] + f" ({row['code']})": row['id'] for _, row in workers_df.iterrows()}
                selected_worker_name = st.selectbox("Select Worker *", list(worker_options.keys()))
                worker_id = worker_options[selected_worker_name]
                worker_row = workers_df[workers_df['id'] == worker_id].iloc[0]
            with col2:
                work_date = st.date_input("Work Date *", value=datetime.today())
                
            col3, col4, col5 = st.columns(3)
            with col3:
                start_time = st.time_input("Start Time", value=datetime.strptime("17:00", "%H:%M").time())
            with col4:
                end_time = st.time_input("End Time", value=datetime.strptime("21:00", "%H:%M").time())
            with col5:
                transport_mode = st.selectbox("Transportation", ["Auto (1x Wkday / 2x Wkend-Hol)", "Force 1 Trip", "Force 2 Trips", "None (0 Trips)"])
                
            notes = st.text_input("Task / Notes (Optional)", placeholder="e.g., Urgent machine repair")
            
            submitted = st.form_submit_button("✅ Save Overtime Record", use_container_width=True)
            if submitted:
                date_str = work_date.strftime("%Y-%m-%d")
                day_name = work_date.strftime("%A")
                
                # Classify day
                day_type = "weekday"
                holiday_name = ""
                matched_hol = holidays_df[holidays_df['date'] == date_str]
                if not matched_hol.empty:
                    day_type = "holiday"
                    holiday_name = matched_hol.iloc[0]['name']
                elif work_date.weekday() >= 5: # Sat=5, Sun=6 in python or 5=Fri, 6=Sat depending on config. Let's check Python weekday: 0=Mon...5=Sat, 6=Sun. Actually in Egypt Weekend is Fri/Sat (4 and 5).
                    day_type = "weekend"
                
                # Calculate hours
                start_mins = start_time.hour * 60 + start_time.minute
                end_mins = end_time.hour * 60 + end_time.minute
                if end_mins <= start_mins:
                    end_mins += 24 * 60
                total_hrs = (end_mins - start_mins) / 60.0
                
                h135, h175, h200, h300 = 0.0, 0.0, 0.0, 0.0
                if day_type == "holiday":
                    h300 = total_hrs
                elif day_type == "weekend" or work_date.weekday() in [4, 5]: # Fri / Sat
                    day_type = "weekend"
                    h200 = total_hrs
                else:
                    # Split morning / night based on 18:00 cutoff
                    night_cutoff = 18 * 60
                    morn_mins, night_mins = 0, 0
                    for t in range(start_mins, end_mins):
                        mod = t % 1440
                        if mod >= 360 and mod < night_cutoff: # 06:00 to 18:00
                            morn_mins += 1
                        else:
                            night_mins += 1
                    h135 = morn_mins / 60.0
                    h175 = night_mins / 60.0
                
                hourly_rate = float(worker_row['monthly_net_salary']) / month_hours
                
                # Determine trips
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
                total_pay = ot_panel_total = ot_pay + transport_pay
                
                entry_id = f"ot_{datetime.now().strftime('%Y%m%d%H%M%S_%f')}"
                shift_sum = f"{start_time.strftime('%H:%M')} – {end_time.strftime('%H:%M')}"
                
                add_entry_db((
                    entry_id, worker_id, worker_row['name'], worker_row['code'], date_str,
                    day_name, day_type, holiday_name, shift_sum, h135, h175, h200, h300,
                    total_hours := h135+h175+h200+h300, hourly_rate, trips, ot_pay, transport_pay, total_pay, notes
                ))
                st.success(f"Successfully logged {total_hours:.2f}h overtime for {worker_row['name']}!")
                st.rerun()

    st.divider()
    
    # KPIs & Filters
    st.subheader("Payroll & Attendance Summary")
    
    if not entries_df.empty:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filter_worker = st.selectbox("Filter by Worker", ["All Workers"] + list(workers_df['name'].unique()))
        with col_f2:
            filter_month = st.text_input("Filter by Month (YYYY-MM)", placeholder="e.g. 2026-04")
            
        filtered_entries = entries_df.copy()
        if filter_worker != "All Workers":
            filtered_entries = filtered_entries[filtered_entries['worker_name'] == filter_worker]
        if filter_month:
            filtered_entries = filtered_entries[filtered_entries['date'].str.startswith(filter_month)]
            
        if not filtered_entries.empty:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total OT Hours", f"{filtered_entries['total_hours'].sum():.2f} hrs")
            k2.metric("Total OT Pay", f"{currency} {filtered_entries['ot_pay'].sum():.2f}")
            k3.metric("Transport Allowance", f"{currency} {filtered_entries['transport_pay'].sum():.2f}")
            k4.metric("Grand Total Payout", f"{currency} {filtered_entries['total_pay'].sum():.2f}")
            
            st.markdown("### Worker Summary Sheet")
            summary = filtered_entries.groupby(['worker_code', 'worker_name']).agg(
                {'hours_135': 'sum', 'hours_175': 'sum', 'hours_200': 'sum', 'hours_300': 'sum',
                 'total_hours': 'sum', 'ot_pay': 'sum', 'trips': 'sum', 'transport_pay': 'sum', 'total_pay': 'sum'}
            ).reset_index()
            st.dataframe(summary, use_container_width=True)
            
            st.markdown("### Detailed Log Records")
            st.dataframe(filtered_entries[['date', 'worker_name', 'day_type', 'shift_summary', 'total_hours', 'ot_pay', 'transport_pay', 'total_pay', 'notes']], use_container_width=True)
            
            if st.button("🗑️ Clear All Logged Entries"):
                conn = sqlite3.connect(DB_FILE)
                conn.cursor().execute("DELETE FROM entries")
                conn.commit()
                conn.close()
                st.rerun()
        else:
            st.info("No records found matching the filter.")
    else:
        st.info("No overtime entries logged yet.")

# -----------------------------------------------------------------------------
# TAB 2: WORKERS DIRECTORY
# -----------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Manage Workers & Monthly Salaries")
    
    with st.form("worker_form"):
        c1, c2, c3 = st.columns(3)
        w_name = c1.text_input("Full Name *")
        w_code = c2.text_input("Employee ID", value=f"EMP-00{len(workers_df)+1}")
        w_role = c3.text_input("Role / Department", value="Technician")
        
        c4, c5 = st.columns(2)
        w_monthly = c4.number_input("Monthly Net Salary (EGP) *", min_value=100.0, value=8500.0, step=100.0)
        w_transport = c5.number_input("1-Trip Transport Allowance (EGP) *", min_value=0.0, value=35.0, step=5.0)
        
        st.caption(f"Derived Hourly Rate: **{currency} {(w_monthly / month_hours):.2f} / hr** (Based on {month_hours}h monthly divisor)")
        
        if st.form_submit_button("💾 Save Worker"):
            if w_name:
                w_id = f"w_{datetime.now().strftime('%H%M%S')}"
                save_worker_db(w_id, w_code, w_name, w_role, w_monthly, w_transport)
                st.success(f"Added worker {w_name} successfully!")
                st.rerun()
            else:
                st.error("Worker name is required.")
                
    st.markdown("### Registered Workers")
    if not workers_df.empty:
        for _, row in workers_df.iterrows():
            col_a, col_b = st.columns([4, 1])
            hourly = row['monthly_net_salary'] / month_hours
            col_a.write(f"**{row['name']}** ({row['code']}) — {row['role']} | Salary: {currency} {row['monthly_net_salary']} | Hourly: {currency} {hourly:.2f}/hr | Transport: {currency} {row['transport_rate']}")
            if col_b.button("Delete", key=f"del_w_{row['id']}"):
                delete_worker_db(row['id'])
                st.rerun()

# -----------------------------------------------------------------------------
# TAB 3: PUBLIC HOLIDAYS
# -----------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Public Holidays (3.0x Rate + Roundtrip Transport)")
    
    with st.form("holiday_form"):
        h_name = st.text_input("Holiday Name *", placeholder="e.g., Eid Al-Adha Day 1")
        h_date = st.date_input("Holiday Date *")
        if st.form_submit_button("➕ Register Holiday"):
            if h_name:
                h_id = f"h_{datetime.now().strftime('%H%M%S')}"
                save_holiday_db(h_id, h_date.strftime("%Y-%m-%d"), h_name)
                st.success(f"Registered holiday: {h_name}!")
                st.rerun()
                
    st.markdown("### Upcoming / Registered Holidays")
    if not holidays_df.empty:
        for _, row in holidays_df.iterrows():
            c1, c2 = st.columns([4, 1])
            c1.write(f"📅 **{row['date']}** — {row['name']} *(3.0x OT Rate)*")
            if c2.button("Remove", key=f"del_h_{row['id']}"):
                delete_holiday_db(row['id'])
                st.rerun()

# -----------------------------------------------------------------------------
# TAB 4: RULES & SETTINGS
# -----------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Calculation Rules & Currency")
    
    with st.form("settings_form"):
        set_curr = st.text_input("Currency Symbol / Code", value=currency)
        set_m_hrs = st.number_input("Monthly Working Hours Divisor", value=month_hours, min_value=100, max_value=744)
        
        if st.form_submit_button("Save Settings"):
            update_setting_db("currency", set_curr)
            update_setting_db("month_hours", set_m_hrs)
            st.success("Settings saved successfully!")
            st.rerun()
            
    st.divider()
    st.markdown("### 🌐 How to Share with Managers")
    st.info("""
    To give your managers access where everyone sees the exact same data instantly:
    1. Host this Streamlit app for free on **Streamlit Community Cloud** (`share.streamlit.io`) by connecting your GitHub repository.
    2. Share the generated app URL with your managers. 
    3. Because all data is stored in the shared SQLite database (`castech_ot_shared.db`), any entry you add on your phone or PC will be instantly visible to all managers when they refresh their browser!
    """)