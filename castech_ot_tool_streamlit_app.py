
import streamlit as st
import pandas as pd
import json
import uuid
from datetime import date, datetime, time

try:
    from supabase import create_client
except ImportError:
    create_client = None


st.set_page_config(
    page_title="Castech OT Tool",
    page_icon="🧮",
    layout="wide"
)


# =========================================================
# DEFAULT DATA
# =========================================================

DEFAULT_STATE = {
    "settings": {
        "dayStart": "06:00",
        "nightStart": "18:00",
        "currency": "EGP",
        "monthHours": 240
    },

    "workers": [
        {
            "id": "w_1",
            "code": "EMP-001",
            "name": "Ahmed Mahmoud",
            "role": "Operations Lead",
            "monthlyNetSalary": 9500.0,
            "transportRate": 35.0
        },
        {
            "id": "w_2",
            "code": "EMP-002",
            "name": "Sara Ibrahim",
            "role": "Logistics Coordinator",
            "monthlyNetSalary": 8400.0,
            "transportRate": 30.0
        },
        {
            "id": "w_3",
            "code": "EMP-003",
            "name": "Omar Khaled",
            "role": "Technician",
            "monthlyNetSalary": 6720.0,
            "transportRate": 25.0
        }
    ],

    "holidays": [
        {
            "id": "h_1",
            "date": "2026-01-07",
            "name": "Coptic Christmas"
        },
        {
            "id": "h_2",
            "date": "2026-04-25",
            "name": "Sinai Liberation Day"
        },
        {
            "id": "h_3",
            "date": "2026-05-01",
            "name": "Labor Day"
        },
        {
            "id": "h_4",
            "date": "2026-07-23",
            "name": "Revolution Day"
        },
        {
            "id": "h_5",
            "date": "2026-10-06",
            "name": "Armed Forces Day"
        }
    ],

    "entries": []
}


# =========================================================
# SUPABASE CLOUD CONNECTION
# =========================================================

@st.cache_resource
def db_client():

    if create_client is None:
        raise RuntimeError(
            "Supabase package is missing. "
            "Add supabase to requirements.txt."
        )

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    )


def cloud_ready():

    return (
        create_client is not None
        and "SUPABASE_URL" in st.secrets
        and "SUPABASE_SERVICE_ROLE_KEY" in st.secrets
    )


def load_state():

    if not cloud_ready():

        st.error(
            "Cloud database is not configured. "
            "Check your Streamlit secrets."
        )

        return json.loads(json.dumps(DEFAULT_STATE))

    try:

        response = (
            db_client()
            .table("ot_workspace")
            .select("state")
            .eq("id", "castech-main")
            .maybe_single()
            .execute()
        )

        if response.data and response.data.get("state"):

            state = response.data["state"]

            state.setdefault(
                "settings",
                DEFAULT_STATE["settings"]
            )

            state.setdefault("workers", [])
            state.setdefault("holidays", [])
            state.setdefault("entries", [])

            return state

        db_client().table("ot_workspace").upsert({
            "id": "castech-main",
            "state": DEFAULT_STATE
        }).execute()

        return json.loads(json.dumps(DEFAULT_STATE))

    except Exception as e:

        st.error(f"Could not load cloud data: {e}")

        return json.loads(json.dumps(DEFAULT_STATE))


def save_state(state):

    if not cloud_ready():

        st.error("Cloud is not configured. Changes were not saved.")

        return False

    try:

        db_client().table("ot_workspace").upsert({
            "id": "castech-main",
            "state": state,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

        st.success("Saved successfully to the shared cloud database.")

        return True

    except Exception as e:

        st.error(f"Cloud save failed: {e}")

        return False


# =========================================================
# CALCULATION FUNCTIONS
# =========================================================

def money(value, currency):

    return f"{currency} {float(value):,.2f}"


def time_to_minutes(value):

    hours, minutes = map(int, value.split(":"))

    return hours * 60 + minutes


def split_hours(start, end, day_start, night_start):

    start_minutes = time_to_minutes(start)
    end_minutes = time_to_minutes(end)

    if end_minutes <= start_minutes:
        end_minutes += 1440

    day_minutes = time_to_minutes(day_start)
    night_minutes = time_to_minutes(night_start)

    morning = 0
    night = 0

    for current in range(start_minutes, end_minutes):

        current_time = current % 1440

        if day_minutes < night_minutes:

            is_morning = (
                day_minutes <= current_time < night_minutes
            )

        else:

            is_morning = not (
                night_minutes <= current_time < day_minutes
            )

        if is_morning:
            morning += 1
        else:
            night += 1

    return (
        morning / 60,
        night / 60,
        (end_minutes - start_minutes) / 60
    )


def day_type(work_date, holidays):

    holiday = next(
        (
            h for h in holidays
            if h["date"] == str(work_date)
        ),
        None
    )

    if holiday:
        return "holiday", holiday["name"]

    # Friday = 4, Saturday = 5
    if work_date.weekday() in (4, 5):
        return "weekend", None

    return "weekday", None


def calculate(
    state,
    worker,
    work_date,
    mode,
    start=None,
    end=None,
    override="Auto split",
    hours=0,
    shift="Morning",
    transport="Automatic"
):

    day, holiday_name = day_type(
        work_date,
        state["holidays"]
    )

    duplicate = any(
        entry["workerId"] == worker["id"]
        and entry["date"] == str(work_date)
        for entry in state["entries"]
    )

    if transport == "Automatic":

        trips = (
            0 if duplicate
            else 2 if day in ("holiday", "weekend")
            else 1
        )

    else:

        trips = int(transport)

    h135 = 0.0
    h170 = 0.0
    h200 = 0.0
    h300 = 0.0

    summary = ""

    if mode == "Start & End Time":

        if not start or not end:
            raise ValueError("Enter both start and end times.")

        morning, night, total = split_hours(
            start,
            end,
            state["settings"]["dayStart"],
            state["settings"]["nightStart"]
        )

        summary = f"{start} – {end}"

        if day == "holiday":

            h300 = total

        elif day == "weekend":

            h200 = total

        elif override == "Morning":

            h135 = total
            summary += " (Morning)"

        elif override == "Night":

            h170 = total
            summary += " (Night)"

        else:

            h135 = morning
            h170 = night

    else:

        total = float(hours)

        if total <= 0:
            raise ValueError("Overtime hours must be greater than zero.")

        if day == "holiday":

            h300 = total
            summary = f"{total:g}h (Holiday)"

        elif day == "weekend":

            h200 = total
            summary = f"{total:g}h (Weekend)"

        elif shift == "Night":

            h170 = total
            summary = f"{total:g}h (Night Shift)"

        else:

            h135 = total
            summary = f"{total:g}h (Morning Shift)"

    monthly_hours = float(
        state["settings"]["monthHours"]
    )

    hourly_rate = (
        float(worker["monthlyNetSalary"])
        / monthly_hours
    )

    overtime_pay = (
        h135 * hourly_rate * 1.35
        + h170 * hourly_rate * 1.70
        + h200 * hourly_rate * 2.00
        + h300 * hourly_rate * 3.00
    )

    transport_pay = (
        trips * float(worker["transportRate"])
    )

    total_hours = h135 + h170 + h200 + h300

    return {
        "dayType": day,
        "holidayName": holiday_name,
        "shiftSummary": summary,

        "hours135": round(h135, 4),
        "hours175": round(h170, 4),
        "hours200": round(h200, 4),
        "hours300": round(h300, 4),

        "totalHours": round(total_hours, 4),

        "hourlyRateSnapshot": round(hourly_rate, 4),
        "transportRateSnapshot": float(worker["transportRate"]),

        "trips": trips,

        "otPay": round(overtime_pay, 2),
        "transportPay": round(transport_pay, 2),
        "totalPay": round(overtime_pay + transport_pay, 2),

        "duplicateDay": duplicate
    }


# =========================================================
# SESSION STATE
# =========================================================

if "state" not in st.session_state:
    st.session_state.state = load_state()

if "admin" not in st.session_state:
    st.session_state.admin = False

state = st.session_state.state

currency = state["settings"]["currency"]


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("CASTECH")

    st.caption(
        "Overtime & Transportation Allowance"
    )

    st.markdown("### Workspace Access")

    if cloud_ready():
        st.success("Cloud connected")
    else:
        st.error("Cloud not configured")

    if not st.session_state.admin:

        password = st.text_input(
            "Admin password",
            type="password"
        )

        if st.button(
            "Unlock editing",
            use_container_width=True
        ):

            correct_password = st.secrets.get(
                "ADMIN_PASSWORD",
                ""
            )

            if correct_password and password == correct_password:

                st.session_state.admin = True
                st.rerun()

            else:

                st.error("Incorrect admin password.")

    else:

        st.success("Admin editing enabled")

        if st.button(
            "Lock editing",
            use_container_width=True
        ):

            st.session_state.admin = False
            st.rerun()

    if st.button(
        "Refresh cloud data",
        use_container_width=True
    ):

        st.session_state.state = load_state()
        st.rerun()

    st.caption(
        "Public viewers can view payroll data. "
        "Only admins can edit records."
    )


# =========================================================
# MAIN APPLICATION
# =========================================================

st.title("Castech OT Tool")

st.caption(
    "Shared overtime and transportation allowance workspace"
)

tabs = st.tabs([
    "Log & Summary",
    "Workers",
    "Holidays",
    "Settings & Backup"
])


# =========================================================
# TAB 1: LOG AND SUMMARY
# =========================================================

with tabs[0]:

    st.subheader("Payroll Overview")

    col1, col2, col3, col4 = st.columns(4)

    total_hours = sum(
        float(e.get("totalHours", 0))
        for e in state["entries"]
    )

    total_ot = sum(
        float(e.get("otPay", 0))
        for e in state["entries"]
    )

    total_transport = sum(
        float(e.get("transportPay", 0))
        for e in state["entries"]
    )

    col1.metric("OT Hours", f"{total_hours:,.2f}")

    col2.metric("OT Pay", money(total_ot, currency))

    col3.metric("Transport", money(total_transport, currency))

    col4.metric(
        "Grand Total",
        money(total_ot + total_transport, currency)
    )

    st.divider()

    with st.expander(
        "Add Overtime Record",
        expanded=st.session_state.admin
    ):

        if not st.session_state.admin:

            st.info("Admin access is required to add records.")

        elif not state["workers"]:

            st.warning("Add a worker first.")

        else:

            worker_map = {
                f"{w['name']} ({w.get('code', '')})": w
                for w in state["workers"]
            }

            with st.form("add_entry"):

                selected_worker = st.selectbox(
                    "Worker",
                    list(worker_map.keys())
                )

                work_date = st.date_input(
                    "Work date",
                    value=date.today()
                )

                mode = st.radio(
                    "Entry method",
                    [
                        "Start & End Time",
                        "Manual Hours"
                    ],
                    horizontal=True
                )

                start = None
                end = None
                override = "Auto split"
                hours = 0.0
                shift = "Morning"

                if mode == "Start & End Time":

                    col_a, col_b = st.columns(2)

                    start = col_a.time_input(
                        "Start time",
                        time(17, 0)
                    ).strftime("%H:%M")

                    end = col_b.time_input(
                        "End time",
                        time(21, 0)
                    ).strftime("%H:%M")

                    override = st.selectbox(
                        "Weekday shift rate",
                        [
                            "Auto split",
                            "Morning",
                            "Night"
                        ]
                    )

                else:

                    hours = st.number_input(
                        "Overtime hours",
                        min_value=0.25,
                        max_value=24.0,
                        value=2.0,
                        step=0.25
                    )

                    shift = st.selectbox(
                        "Weekday shift",
                        ["Morning", "Night"]
                    )

                transport = st.selectbox(
                    "Transport trips",
                    ["Automatic", "0", "1", "2"]
                )

                notes = st.text_input("Notes")

                submitted = st.form_submit_button(
                    "Calculate & Save Record",
                    type="primary"
                )

            if submitted:

                worker = worker_map[selected_worker]

                try:

                    result = calculate(
                        state,
                        worker,
                        work_date,
                        mode,
                        start,
                        end,
                        override,
                        hours,
                        shift,
                        transport
                    )

                    entry = {
                        "id": "ot_" + uuid.uuid4().hex,
                        "workerId": worker["id"],
                        "workerName": worker["name"],
                        "workerCode": worker.get("code", ""),
                        "date": str(work_date),
                        "dayName": work_date.strftime("%A"),
                        "notes": notes,
                        **result
                    }

                    state["entries"].insert(0, entry)

                    if save_state(state):

                        st.session_state.state = state
                        st.rerun()

                except Exception as e:

                    st.error(str(e))

    # FILTERS

    st.subheader("Filters")

    f1, f2, f3 = st.columns(3)

    worker_filter = f1.selectbox(
        "Worker filter",
        ["All"] + [
            w["name"]
            for w in state["workers"]
        ]
    )

    month_filter = f2.text_input(
        "Month (YYYY-MM)",
        placeholder="2026-11"
    )

    day_filter = f3.selectbox(
        "Day type",
        ["All", "weekday", "weekend", "holiday"]
    )

    entries = state["entries"][:]

    if worker_filter != "All":

        entries = [
            e for e in entries
            if e.get("workerName") == worker_filter
        ]

    if month_filter:

        entries = [
            e for e in entries
            if e.get("date", "").startswith(month_filter)
        ]

    if day_filter != "All":

        entries = [
            e for e in entries
            if e.get("dayType") == day_filter
        ]

    # FINANCE SUMMARY

    st.subheader("Worker Finance Summary")

    summary = []

    for worker in state["workers"]:

        worker_entries = [
            e for e in entries
            if e.get("workerId") == worker["id"]
        ]

        if worker_entries:

            summary.append({
                "Worker": worker["name"],
                "Entries": len(worker_entries),

                "OT Hours": sum(
                    e.get("totalHours", 0)
                    for e in worker_entries
                ),

                "OT Pay": sum(
                    e.get("otPay", 0)
                    for e in worker_entries
                ),

                "Transport": sum(
                    e.get("transportPay", 0)
                    for e in worker_entries
                ),

                "Total": sum(
                    e.get("totalPay", 0)
                    for e in worker_entries
                )
            })

    if summary:

        st.dataframe(
            pd.DataFrame(summary),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("No matching overtime records yet.")

    # DETAILED LOGS

    st.subheader(f"Detailed Logs ({len(entries)})")

    if entries:

        columns = [
            "date",
            "workerName",
            "workerCode",
            "dayType",
            "shiftSummary",
            "totalHours",
            "hours135",
            "hours175",
            "hours200",
            "hours300",
            "hourlyRateSnapshot",
            "otPay",
            "trips",
            "transportPay",
            "totalPay",
            "notes"
        ]

        df = pd.DataFrame(entries)

        visible_columns = [
            c for c in columns
            if c in df.columns
        ]

        st.dataframe(
            df[visible_columns],
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "Export Detailed Logs CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            "castech_ot_detailed_logs.csv",
            "text/csv"
        )

        summary_df = pd.DataFrame(summary)

        st.download_button(
            "Export Finance Summary CSV",
            summary_df.to_csv(index=False).encode("utf-8-sig"),
            "castech_ot_finance_summary.csv",
            "text/csv"
        )

        if st.session_state.admin:

            ids = st.multiselect(
                "Select records to delete",
                [e["id"] for e in entries],
                format_func=lambda x: next(
                    (
                        f"{e.get('date')} – "
                        f"{e.get('workerName')} – "
                        f"{e.get('totalPay', 0):.2f}"
                        for e in entries
                        if e["id"] == x
                    ),
                    x
                )
            )

            if st.button(
                "Delete selected records",
                disabled=not ids
            ):

                state["entries"] = [
                    e for e in state["entries"]
                    if e["id"] not in ids
                ]

                if save_state(state):

                    st.session_state.state = state
                    st.rerun()

    else:

        st.info("No records to display.")


# =========================================================
# TAB 2: WORKERS
# =========================================================

with tabs[1]:

    st.subheader("Workers & Salary Rates")

    if state["workers"]:

        worker_df = pd.DataFrame([
            {
                **worker,
                "hourlyRate": round(
                    float(worker["monthlyNetSalary"])
                    / float(state["settings"]["monthHours"]),
                    4
                )
            }
            for worker in state["workers"]
        ])

        st.dataframe(
            worker_df,
            use_container_width=True,
            hide_index=True
        )

    if st.session_state.admin:

        with st.expander("Add / Update Worker"):

            existing = {
                f"{w['name']} ({w.get('code', '')})": w
                for w in state["workers"]
            }

            choice = st.selectbox(
                "Edit existing worker or add new",
                ["Add new"] + list(existing.keys())
            )

            old = existing.get(choice, {})

            with st.form("worker_form"):

                name = st.text_input(
                    "Full name",
                    old.get("name", "")
                )

                code = st.text_input(
                    "Employee ID",
                    old.get("code", "")
                )

                role = st.text_input(
                    "Department / role",
                    old.get("role", "")
                )

                salary = st.number_input(
                    "Monthly net salary",
                    min_value=1.0,
                    value=float(old.get("monthlyNetSalary", 8000)),
                    step=100.0
                )

                transport_rate = st.number_input(
                    "One-trip transport allowance",
                    min_value=0.0,
                    value=float(old.get("transportRate", 30)),
                    step=1.0
                )

                save_worker = st.form_submit_button("Save Worker")

            if save_worker:

                if not name.strip():

                    st.error("Worker name is required.")

                else:

                    worker = {
                        "id": old.get(
                            "id",
                            "w_" + uuid.uuid4().hex
                        ),
                        "name": name.strip(),
                        "code": code.strip(),
                        "role": role.strip(),
                        "monthlyNetSalary": salary,
                        "transportRate": transport_rate
                    }

                    if old:

                        state["workers"] = [
                            worker if w["id"] == old["id"] else w
                            for w in state["workers"]
                        ]

                    else:

                        state["workers"].append(worker)

                    if save_state(state):

                        st.session_state.state = state
                        st.rerun()

        if state["workers"]:

            delete_worker = st.selectbox(
                "Remove worker",
                [w["id"] for w in state["workers"]],
                format_func=lambda x: next(
                    w["name"]
                    for w in state["workers"]
                    if w["id"] == x
                )
            )

            if st.button("Delete Worker"):

                state["workers"] = [
                    w for w in state["workers"]
                    if w["id"] != delete_worker
                ]

                if save_state(state):

                    st.session_state.state = state
                    st.rerun()

    else:

        st.info(
            "Unlock admin editing to add, update, or remove workers."
        )


# =========================================================
# TAB 3: PUBLIC HOLIDAYS
# =========================================================

with tabs[2]:

    st.subheader("Registered Public Holidays")

    if state["holidays"]:

        holiday_df = pd.DataFrame(state["holidays"])

        holiday_df["OT multiplier"] = "3.0x"
        holiday_df["Transport trips"] = 2

        st.dataframe(
            holiday_df,
            use_container_width=True,
            hide_index=True
        )

    if st.session_state.admin:

        with st.form("holiday_form"):

            holiday_name = st.text_input("Holiday name")

            holiday_date = st.date_input(
                "Holiday date",
                value=date.today()
            )

            add_holiday = st.form_submit_button(
                "Register Holiday"
            )

        if add_holiday:

            if not holiday_name.strip():

                st.error("Enter a holiday name.")

            else:

                state["holidays"] = [
                    h for h in state["holidays"]
                    if h["date"] != str(holiday_date)
                ]

                state["holidays"].append({
                    "id": "h_" + uuid.uuid4().hex,
                    "date": str(holiday_date),
                    "name": holiday_name.strip()
                })

                if save_state(state):

                    st.session_state.state = state
                    st.rerun()

        if state["holidays"]:

            remove_holiday = st.selectbox(
                "Remove holiday",
                [h["id"] for h in state["holidays"]],
                format_func=lambda x: next(
                    f"{h['date']} – {h['name']}"
                    for h in state["holidays"]
                    if h["id"] == x
                )
            )

            if st.button("Remove Selected Holiday"):

                state["holidays"] = [
                    h for h in state["holidays"]
                    if h["id"] != remove_holiday
                ]

                if save_state(state):

                    st.session_state.state = state
                    st.rerun()

    else:

        st.info(
            "Unlock admin editing to manage public holidays."
        )


# =========================================================
# TAB 4: SETTINGS & BACKUP
# =========================================================

with tabs[3]:

    st.subheader("Calculation Settings")

    settings = state["settings"]

    st.markdown("### Overtime rules")

    st.markdown("""
    - Sunday–Thursday: 1.35x morning / 1.70x night
    - Friday–Saturday: 2.00x
    - Public holidays: 3.00x
    - Automatic transport: one trip on working days
    - Automatic transport: two trips on weekends and holidays
    - Duplicate worker entries on the same date: automatic transport becomes zero
    """)

    if st.session_state.admin:

        with st.form("settings_form"):

            day_start = st.time_input(
                "Day / Morning starts",
                time.fromisoformat(settings["dayStart"])
            ).strftime("%H:%M")

            night_start = st.time_input(
                "Night starts",
                time.fromisoformat(settings["nightStart"])
            ).strftime("%H:%M")

            currency = st.text_input(
                "Currency",
                settings["currency"]
            )

            month_hours = st.number_input(
                "Monthly working hours divisor",
                min_value=1,
                max_value=744,
                value=int(settings["monthHours"])
            )

            save_settings = st.form_submit_button(
                "Save Settings"
            )

        if save_settings:

            state["settings"] = {
                "dayStart": day_start,
                "nightStart": night_start,
                "currency": currency.strip() or "EGP",
                "monthHours": int(month_hours)
            }

            if save_state(state):

                st.session_state.state = state
                st.rerun()

        st.divider()

        st.subheader("Backup & Restore")

        st.download_button(
            "Download Full JSON Backup",
            json.dumps(
                state,
                ensure_ascii=False,
                indent=2
            ).encode("utf-8"),
            "castech_ot_backup.json",
            "application/json"
        )

        uploaded_file = st.file_uploader(
            "Restore JSON backup",
            type=["json"]
        )

        if uploaded_file and st.button("Restore Uploaded Backup"):

            try:

                restored = json.load(uploaded_file)

                required_keys = [
                    "settings",
                    "workers",
                    "holidays",
                    "entries"
                ]

                if all(key in restored for key in required_keys):

                    if save_state(restored):

                        st.session_state.state = restored
                        st.rerun()

                else:

                    st.error("Backup file structure is invalid.")

            except Exception as e:

                st.error(f"Could not restore backup: {e}")

        if st.button("Factory Reset to Sample Data"):

            fresh_state = json.loads(
                json.dumps(DEFAULT_STATE)
            )

            if save_state(fresh_state):

                st.session_state.state = fresh_state
                st.rerun()

    else:

        st.info(
            "Unlock admin editing to change settings or manage backups."
        )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Castech OT Tool | Shared Cloud Workspace | "
    "Public viewers can see employee payroll information."
)
