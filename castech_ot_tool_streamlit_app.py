import streamlit as st
import pandas as pd
import json, uuid, io
from datetime import date, datetime, time, timedelta
try:
    from supabase import create_client
except ImportError:
    create_client = None

st.set_page_config(page_title='Castech OT Tool', page_icon='🧮', layout='wide')

DEFAULT_STATE = {
    'settings': {'dayStart':'06:00','nightStart':'18:00','currency':'EGP','monthHours':240},
    'workers': [
        {'id':'w_1','code':'EMP-001','name':'Ahmed Mahmoud','role':'Operations Lead','monthlyNetSalary':9500.0,'transportRate':35.0},
        {'id':'w_2','code':'EMP-002','name':'Sara Ibrahim','role':'Logistics Coordinator','monthlyNetSalary':8400.0,'transportRate':30.0},
        {'id':'w_3','code':'EMP-003','name':'Omar Khaled','role':'Technician','monthlyNetSalary':6720.0,'transportRate':25.0},
    ],
    'holidays': [
        {'id':'h_1','date':'2026-01-07','name':'Coptic Christmas'},
        {'id':'h_2','date':'2026-04-25','name':'Sinai Liberation Day'},
        {'id':'h_3','date':'2026-05-01','name':'Labor Day'},
        {'id':'h_4','date':'2026-07-23','name':'Revolution Day'},
        {'id':'h_5','date':'2026-10-06','name':'Armed Forces Day'},
    ], 'entries': []
}

@st.cache_resource
def db_client():
    if create_client is None:
        raise RuntimeError('The supabase package is missing. Add supabase>=2.10,<3 to requirements.txt and reboot the app.')
    sec = st.secrets
    return create_client(sec['SUPABASE_URL'], sec['SUPABASE_SERVICE_ROLE_KEY'])

def cloud_ready():
    return create_client is not None and 'SUPABASE_URL' in st.secrets and 'SUPABASE_SERVICE_ROLE_KEY' in st.secrets

def load_state():
    if not cloud_ready():
        st.error('Cloud database is not configured yet. Follow README_DEPLOYMENT.md to connect Supabase.')
        return json.loads(json.dumps(DEFAULT_STATE))
    try:
        row = db_client().table('ot_workspace').select('state').eq('id','castech-main').maybe_single().execute()
        if row.data and row.data.get('state'):
            state = row.data['state']
            state.setdefault('settings', DEFAULT_STATE['settings'])
            state.setdefault('workers', []); state.setdefault('holidays', []); state.setdefault('entries', [])
            return state
        db_client().table('ot_workspace').upsert({'id':'castech-main','state':DEFAULT_STATE}).execute()
        return json.loads(json.dumps(DEFAULT_STATE))
    except Exception as e:
        st.error(f'Could not load cloud data: {e}')
        return json.loads(json.dumps(DEFAULT_STATE))

def save_state(state):
    if not cloud_ready():
        st.error('Cloud is not configured. No changes were saved.'); return False
    try:
        db_client().table('ot_workspace').upsert({'id':'castech-main','state':state,'updated_at':datetime.utcnow().isoformat()}).execute()
        st.cache_data.clear()
        st.success('Saved to the shared cloud workspace.')
        return True
    except Exception as e:
        st.error(f'Cloud save failed: {e}'); return False

def money(v, cur): return f'{cur} {float(v):,.2f}'
def mins(t):
    h,m=map(int,t.split(':')); return h*60+m

def split_hours(start, end, day_start, night_start):
    a,b=mins(start),mins(end)
    if b<=a: b+=1440
    ds,ns=mins(day_start),mins(night_start)
    morning=night=0
    for x in range(a,b):
        mod=x%1440
        if ds<ns: is_morning=ds<=mod<ns
        else: is_morning=not (ns<=mod<ds)
        if is_morning: morning+=1
        else: night+=1
    return morning/60,night/60,(b-a)/60

def day_type(d, holidays):
    holiday=next((h for h in holidays if h['date']==str(d)),None)
    if holiday: return 'holiday', holiday['name']
    if d.weekday() in (4,5): return 'weekend', None # Python Friday=4, Saturday=5
    return 'weekday',None

def calculate(state, worker, work_date, mode, start=None, end=None, override='Auto split', hours=0, shift='Morning', transport='Automatic'):
    typ, hol=day_type(work_date,state['holidays'])
    prior=any(e['workerId']==worker['id'] and e['date']==str(work_date) for e in state['entries'])
    if transport=='Automatic': trips=0 if prior else (2 if typ in ('holiday','weekend') else 1)
    else: trips=int(transport)
    h135=h175=h200=h300=0.0; summary=''
    if mode=='Start & End Time':
        if not start or not end: raise ValueError('Enter both start and end times.')
