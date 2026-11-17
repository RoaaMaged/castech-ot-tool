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
    
    try:
        return create_client is not None and bool(st.secrets.get('SUPABASE_URL')) and bool(st.secrets.get('SUPABASE_SERVICE_ROLE_KEY'))
    except Exception:
        return False

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
        hm,hn,ht=split_hours(start,end,state['settings']['dayStart'],state['settings']['nightStart'])
        summary=f'{start} – {end}'
        if typ=='holiday': h300=ht
        elif typ=='weekend': h200=ht
        elif override=='Morning': h135=ht; summary+=' (Morning)'
        elif override=='Night': h175=ht; summary+=' (Night)'
        else: h135,h175=hm,hn
    else:
        ht=float(hours)
        if ht<=0: raise ValueError('Overtime hours must be greater than zero.')
        if typ=='holiday': h300=ht; summary=f'{ht:g}h (Holiday)'
        elif typ=='weekend': h200=ht; summary=f'{ht:g}h (Weekend)'
        elif shift=='Night': h175=ht; summary=f'{ht:g}h (Night Shift)'
        else: h135=ht; summary=f'{ht:g}h (Morning Shift)'
    divisor=float(state['settings']['monthHours'])
    rate=float(worker['monthlyNetSalary'])/divisor
    ot=h135*rate*1.35+h175*rate*1.70+h200*rate*2+h300*rate*3
    transport_pay=trips*float(worker['transportRate'])
    return {'dayType':typ,'holidayName':hol,'shiftSummary':summary,'hours135':round(h135,4),'hours175':round(h175,4),'hours200':round(h200,4),'hours300':round(h300,4),'totalHours':round(h135+h175+h200+h300,4),'hourlyRateSnapshot':round(rate,4),'transportRateSnapshot':float(worker['transportRate']),'trips':trips,'otPay':round(ot,2),'transportPay':round(transport_pay,2),'totalPay':round(ot+transport_pay,2),'duplicateDay':prior}

if 'state' not in st.session_state: st.session_state.state=load_state()
# Password-free mode: editing is enabled for all visitors.
state=st.session_state.state
cur=state['settings']['currency']

with st.sidebar:
    st.title('CASTECH')
    st.caption('Overtime & Transportation Allowance')
    st.write('🟢 Cloud-connected' if cloud_ready() else '🟠 Local preview — cloud database not configured')
    if st.button('Refresh cloud data',use_container_width=True):
        st.session_state.state=load_state(); st.rerun()
    st.caption('Anyone with this link can view and edit the shared workspace.')

st.title('Castech OT Tool')
st.caption('Shared overtime and transportation allowance workspace')
tabs=st.tabs(['Log & Summary','Workers','Holidays','Settings & Backup'])

with tabs[0]:
    st.subheader('Payroll overview')
    c1,c2,c3,c4=st.columns(4)
    total_hours=sum(float(e.get('totalHours',0)) for e in state['entries'])
    total_ot=sum(float(e.get('otPay',0)) for e in state['entries'])
    total_transport=sum(float(e.get('transportPay',0)) for e in state['entries'])
    c1.metric('OT hours',f'{total_hours:,.2f}')
    c2.metric('OT pay',money(total_ot,cur))
    c3.metric('Transport',money(total_transport,cur))
    c4.metric('Grand total',money(total_ot+total_transport,cur))
    st.divider()
    with st.expander('Add overtime record',expanded=True):
        if not True: st.info('Admin access is required to add records.')
        elif not state['workers']: st.warning('Add a worker first.')
        else:
            worker_map={f"{w['name']} ({w.get('code','')})":w for w in state['workers']}
            with st.form('add_entry'):
                selected=st.selectbox('Worker',list(worker_map))
                d=st.date_input('Work date',value=date.today())
                mode=st.radio('Entry method',['Start & End Time','Manual Hours'],horizontal=True)
                a=b=None; override='Auto split'; hours=0.0; shift='Morning'
                if mode=='Start & End Time':
                    ca,cb=st.columns(2)
                    a=ca.time_input('Start time',time(17,0)).strftime('%H:%M')
                    b=cb.time_input('End time',time(21,0)).strftime('%H:%M')
                    override=st.selectbox('Weekday shift rate',['Auto split','Morning','Night'])
                else:
                    hours=st.number_input('Overtime hours',min_value=0.25,max_value=24.0,value=2.0,step=0.25)
                    shift=st.selectbox('Weekday shift',['Morning','Night'])
                transport=st.selectbox('Transport trips',['Automatic','0','1','2'])
                note=st.text_input('Notes')
                submitted=st.form_submit_button('Calculate & save record',type='primary')
            if submitted:
                w=worker_map[selected]
                try:
                    calc=calculate(state,w,d,mode,a,b,override,hours,shift,transport)
                    entry={'id':'ot_'+uuid.uuid4().hex,'workerId':w['id'],'workerName':w['name'],'workerCode':w.get('code',''),'date':str(d),'dayName':d.strftime('%A'),'notes':note,**calc}
                    state['entries'].insert(0,entry)
                    if save_state(state): st.session_state.state=state; st.rerun()
                except Exception as e: st.error(str(e))
    st.subheader('Filters')
    f1,f2,f3=st.columns(3)
    worker_filter=f1.selectbox('Worker filter',['All']+[w['name'] for w in state['workers']])
    month_filter=f2.text_input('Month (YYYY-MM)',placeholder='2026-11')
    day_filter=f3.selectbox('Day type',['All','weekday','weekend','holiday'])
    entries=state['entries'][:]
    if worker_filter!='All': entries=[e for e in entries if e.get('workerName')==worker_filter]
    if month_filter: entries=[e for e in entries if e.get('date','').startswith(month_filter)]
    if day_filter!='All': entries=[e for e in entries if e.get('dayType')==day_filter]
    st.subheader('Worker finance summary')
    summary=[]
    for w in state['workers']:
        es=[e for e in entries if e.get('workerId')==w['id']]
        if es: summary.append({'Worker':w['name'],'Entries':len(es),'OT Hours':sum(e.get('totalHours',0) for e in es),'OT Pay':sum(e.get('otPay',0) for e in es),'Transport':sum(e.get('transportPay',0) for e in es),'Total':sum(e.get('totalPay',0) for e in es)})
    if summary: st.dataframe(pd.DataFrame(summary),use_container_width=True,hide_index=True)
    else: st.info('No matching overtime records yet.')
    st.subheader(f'Detailed logs ({len(entries)})')
    if entries:
        cols=['date','workerName','workerCode','dayType','shiftSummary','totalHours','hours135','hours175','hours200','hours300','hourlyRateSnapshot','otPay','trips','transportPay','totalPay','notes']
        df=pd.DataFrame(entries)
        st.dataframe(df[[c for c in cols if c in df.columns]],use_container_width=True,hide_index=True)
        csv=df.to_csv(index=False).encode('utf-8-sig')
        st.download_button('Export detailed logs (CSV)',csv,'castech_ot_detailed_logs.csv','text/csv')
        summary_df=pd.DataFrame(summary)
        st.download_button('Export finance summary (CSV)',summary_df.to_csv(index=False).encode('utf-8-sig'),'castech_ot_finance_summary.csv','text/csv')
        if True:
            ids=st.multiselect('Select records to delete',[e['id'] for e in entries],format_func=lambda x: next((f"{e.get('date')} – {e.get('workerName')} – {e.get('totalPay',0):.2f}" for e in entries if e['id']==x),x))
            if st.button('Delete selected records',disabled=not ids):
                state['entries']=[e for e in state['entries'] if e['id'] not in ids]
                if save_state(state): st.session_state.state=state; st.rerun()
    else: st.info('No records to display.')

with tabs[1]:
    st.subheader('Workers & salary rates')
    if state['workers']:
        wdf=pd.DataFrame([{**w,'hourlyRate':round(float(w['monthlyNetSalary'])/float(state['settings']['monthHours']),4)} for w in state['workers']])
        st.dataframe(wdf,use_container_width=True,hide_index=True)
    if True:
        with st.expander('Add / update worker'):
            existing={f"{w['name']} ({w.get('code','')})":w for w in state['workers']}
            choice=st.selectbox('Edit existing worker or add new',['Add new']+list(existing))
            old=existing.get(choice,{})
            with st.form('worker_form'):
                name=st.text_input('Full name',old.get('name',''))
                code=st.text_input('Employee ID',old.get('code',''))
                role=st.text_input('Department / role',old.get('role',''))
                salary=st.number_input('Monthly net salary',min_value=1.0,value=float(old.get('monthlyNetSalary',8000)),step=100.0)
                tr=st.number_input('One-trip transport allowance',min_value=0.0,value=float(old.get('transportRate',30)),step=1.0)
                ok=st.form_submit_button('Save worker')
            if ok:
                if not name.strip(): st.error('Worker name is required.')
                else:
                    item={'id':old.get('id','w_'+uuid.uuid4().hex),'name':name.strip(),'code':code.strip(),'role':role.strip(),'monthlyNetSalary':salary,'transportRate':tr}
                    if old: state['workers']=[item if x['id']==old['id'] else x for x in state['workers']]
                    else: state['workers'].append(item)
                    if save_state(state): st.session_state.state=state; st.rerun()
        del_worker=st.selectbox('Remove worker',[w['id'] for w in state['workers']],format_func=lambda x:next(w['name'] for w in state['workers'] if w['id']==x)) if state['workers'] else None
        if del_worker and st.button('Delete worker'):
            state['workers']=[w for w in state['workers'] if w['id']!=del_worker]
            if save_state(state): st.session_state.state=state; st.rerun()
    else: st.info('Unlock admin editing to add, update, or remove workers.')

with tabs[2]:
    st.subheader('Registered public holidays')
    if state['holidays']:
        hdf=pd.DataFrame(state['holidays']); hdf['OT multiplier']='3.0x'; hdf['Transport trips']=2
        st.dataframe(hdf,use_container_width=True,hide_index=True)
    if True:
        with st.form('holiday_form'):
            hn=st.text_input('Holiday name'); hd=st.date_input('Holiday date',value=date.today())
            addh=st.form_submit_button('Register holiday')
        if addh:
            state['holidays']=[h for h in state['holidays'] if h['date']!=str(hd)]
            state['holidays'].append({'id':'h_'+uuid.uuid4().hex,'date':str(hd),'name':hn.strip()})
            if save_state(state): st.session_state.state=state; st.rerun()
        if state['holidays']:
            rem=st.selectbox('Remove holiday',[h['id'] for h in state['holidays']],format_func=lambda x:next(f"{h['date']} – {h['name']}" for h in state['holidays'] if h['id']==x))
            if st.button('Remove selected holiday'):
                state['holidays']=[h for h in state['holidays'] if h['id']!=rem]
                if save_state(state): st.session_state.state=state; st.rerun()
    else: st.info('Unlock admin editing to manage public holidays.')

with tabs[3]:
    st.subheader('Calculation settings')
    s=state['settings']
    st.markdown('**Current rules from the supplied HTML**')
    st.markdown('- Sunday–Thursday: 1.35× morning / 1.70× night, one automatic trip\n- Friday–Saturday: 2.00×, two automatic trips\n- Registered public holiday: 3.00×, two automatic trips\n- Automatic transport is reduced to zero for another entry by the same worker on the same date.')
    if True:
        with st.form('settings_form'):
            ds=st.time_input('Day / morning starts',time.fromisoformat(s['dayStart'])).strftime('%H:%M')
            ns=st.time_input('Night starts',time.fromisoformat(s['nightStart'])).strftime('%H:%M')
            currency=st.text_input('Currency',s['currency'])
            mh=st.number_input('Monthly working hours divisor',min_value=1,max_value=744,value=int(s['monthHours']))
            save_settings=st.form_submit_button('Save settings')
        if save_settings:
            state['settings']={'dayStart':ds,'nightStart':ns,'currency':currency.strip() or 'EGP','monthHours':int(mh)}
            if save_state(state): st.session_state.state=state; st.rerun()
        st.divider(); st.subheader('Backup & restore')
        st.download_button('Download full JSON backup',json.dumps(state,ensure_ascii=False,indent=2).encode('utf-8'),'castech_ot_backup.json','application/json')
        upload=st.file_uploader('Restore JSON backup',type=['json'])
        if upload and st.button('Restore uploaded backup'):
            try:
                restored=json.load(upload)
                if all(k in restored for k in ('settings','workers','holidays','entries')):
                    if save_state(restored): st.session_state.state=restored; st.rerun()
                else: st.error('Backup file structure is not valid.')
            except Exception as e: st.error(f'Could not restore backup: {e}')
        if st.button('Factory reset to sample data'):
            if save_state(json.loads(json.dumps(DEFAULT_STATE))): st.session_state.state=json.loads(json.dumps(DEFAULT_STATE)); st.rerun()
    else: st.info('Unlock admin editing to change rules or manage backups.')

st.divider()
st.caption('Castech OT Tool • Anyone with this link can view and edit employee salary, overtime and transport records.')
