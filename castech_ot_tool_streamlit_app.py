import streamlit as st
import pandas as pd
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
        if st.session_state.admin:
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
    if st.session_state.admin:
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
    if st.session_state.admin:
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
    if st.session_state.admin:
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
