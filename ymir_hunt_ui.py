"""Read-only live hunt window for the desktop Timer."""
import queue
import threading
import time
import tkinter as tk
from ymir_hunt_sync import HuntClient, fresh
from ymir_theme import BG,PANEL,TEXT,MUTED,ACCENT,GamerButton


def open_hunt(app):
    if getattr(app,'hunt_window',None) is not None and app.hunt_window.winfo_exists():
        app.hunt_window.lift();return
    win=tk.Toplevel(app);app.hunt_window=win;win.title('Ymir · Caça ao vivo');win.geometry('700x640');win.configure(bg=BG)
    status=tk.Label(win,text='Conecte o mesmo login em Nuvem no Timer e no Boss Auto.',bg=BG,fg=MUTED,wraplength=650,justify='left');status.pack(fill='x',padx=18,pady=10)
    frame=tk.Frame(win,bg=BG);frame.pack(fill='both',expand=True,padx=18,pady=8)
    results=queue.SimpleQueue();state={'busy':False,'next':0,'uid':None,'rows':[],'signature':None,'client':None,'session_key':None}
    def poll():
        if not win.winfo_exists():return
        session=getattr(app,'cloud_session',None)
        owner=(session['project'],session['uid']) if session else None
        if owner!=state['uid']:
            state['rows']=[];state['signature']=None;state['uid']=owner
        session_key=(session['project'],session['uid'],session['refresh']) if session else None
        if session_key!=state['session_key']:
            state['session_key']=session_key;state['client']=HuntClient(session) if session else None;state['next']=0
        try:
            while True:
                uid,value,error=results.get_nowait();state['busy']=False
                if not session or uid!=(session['project'],session['uid']):continue
                if error:status.config(text=error)
                else:state['rows']=value;status.config(text='Atualizações a cada 15s com esta janela aberta. Sem atualização recente não confirma que o PC parou.')
        except queue.Empty:pass
        if not session:
            state['rows']=[];status.config(text='Nuvem desconectada. Entre no mesmo login do Boss Auto em Ajustes → Nuvem.')
        elif not state['busy'] and time.monotonic()>=state['next']:
            state['busy']=True;state['next']=time.monotonic()+15
            def work(saved=dict(session),client=state['client']):
                try:results.put(((saved['project'],saved['uid']),client.live(),None))
                except Exception as exc:results.put(((saved['project'],saved['uid']),None,str(exc)))
            threading.Thread(target=work,daemon=True).start()
        pid=app.active_profile_id();rows=[r for r in state['rows'] if r['profile_id']==pid]
        signature=repr([(r,int(time.time()-r['received_at'])) for r in rows])
        if signature!=state['signature']:
            state['signature']=signature
            for child in frame.winfo_children():child.destroy()
            if not rows:tk.Label(frame,text='Nenhuma atividade recebida nesta conta/servidor.',bg=BG,fg=MUTED).pack(pady=25)
            for value in rows:
                card=tk.Frame(frame,bg=PANEL);card.pack(fill='x',pady=6)
                age=max(0,int(time.time()-value['received_at']))
                badge='SEM ATUALIZAÇÃO RECENTE' if not fresh(value['received_at']) else 'SIMULAÇÃO' if value['simulate'] else 'PAUSADO' if value['paused'] else 'EM EXECUÇÃO' if value['running'] else 'PARADO'
                texts=[value.get('device_label','PC')+' · '+badge,f"{value.get('boss') or 'Sem alvo'} · Canal {value.get('channel') or '—'}",value.get('map',''),value.get('stage',''),
                       'Próximo: '+value.get('next_visit','—'),value.get('reason',''),f'Última atualização há {age}s']
                stats=value.get('stats',{});texts.insert(-1,f"Visitados: {stats.get('bosses_visited',0)} · Mortes estimadas: {stats.get('combat_ended',0)} · Inconclusivos: {stats.get('combat_inconclusive',0)}")
                for i,text in enumerate(texts):tk.Label(card,text=text,bg=PANEL,fg=ACCENT if i==0 else TEXT,wraplength=620,justify='left',anchor='w').pack(fill='x',padx=12,pady=3)
        win.after(1000,poll)
    poll()
