"""Centro de Salud avanzado: batería, throttling, benchmarks, Windows, historial y rollback."""
from __future__ import annotations

import copy
import threading
import time
import datetime as dt
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image, ImageTk

from core.theme_manager import color as theme_color
from core.battery_health import collect_battery_health
from core.benchmark_engine import run_quick_suite
from core.before_after import capture_metrics, save_snapshot, load_snapshots, compare
from core.device_identity import collect_hardware_inventory
from core.windows_health import (
    analyze_startup, analyze_services, analyze_crashes, analyze_drivers,
    compare_hardware_inventory, save_hardware_baseline, restore_point_status, create_restore_point,
)
from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost

BG = theme_color('#06111f')
CARD = theme_color('#0d1828')
CARD2 = theme_color('#0a1524')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT2 = theme_color('#b8c4d4')
MUTED = theme_color('#7f91a8')
CYAN = '#14b8ff'; GREEN = '#10b981'; AMBER = '#f59e0b'; RED = '#ef4444'; PURPLE = '#a855f7'
FONT = 'Segoe UI'


def _num(v):
    try: return float(v) if v is not None else None
    except Exception: return None


def _fmt(v, unit='', digits=1):
    n = _num(v)
    return f'{n:.{digits}f}{unit}' if n is not None else 'N/A'


def _short(text, n=120):
    s = str(text or '').replace('\r',' ').replace('\n',' ').strip()
    return s if len(s) <= n else s[:n-1] + '…'


class HealthCenterPanel:
    TABS = (
        ('summary', 'Resumen'), ('battery', 'Batería'), ('performance', 'Rendimiento'),
        ('windows', 'Windows'), ('history', 'Historial y cambios'), ('recovery', 'Recuperación'),
    )

    def __init__(self, app, host):
        self.app = app; self.host = host; self._alive = True; self._tab='summary'; self._jobs=set()
        self._battery=None; self._startup=None; self._services=None; self._crashes=None; self._drivers=None; self._hw=None; self._restore=None; self._bench=None
        self._health_chart_photo = None
        self._bench_compare = None
        self._build(); self.refresh()

    def widget(self): return self.frame

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)
        header = ctk.CTkFrame(self.frame, fg_color='transparent'); header.pack(fill='x', padx=18, pady=(14,7))
        ctk.CTkButton(header,text='Volver al resumen',width=145,height=31,fg_color='transparent',hover_color=theme_color('#102840'),border_width=1,border_color=theme_color('#214765'),text_color=TEXT2,font=(FONT,9,'bold'),corner_radius=8,command=lambda:show_dashboard(self.app)).pack(side='left')
        titles=ctk.CTkFrame(header,fg_color='transparent'); titles.pack(side='left',fill='x',expand=True,padx=14)
        ctk.CTkLabel(titles,text='Centro de Salud',font=(FONT,20,'bold'),text_color=TEXT,anchor='w').pack(anchor='w')
        ctk.CTkLabel(titles,text='Batería, throttling, benchmarks, Windows, historial, cambios y recuperación',font=(FONT,10),text_color=TEXT2,anchor='w').pack(anchor='w',pady=(1,0))
        self.lbl_status=ctk.CTkLabel(header,text='Datos reales · REAL_OR_NA',font=(FONT,9,'bold'),text_color=GREEN); self.lbl_status.pack(side='right')
        tabs=ctk.CTkFrame(self.frame,fg_color='transparent'); tabs.pack(fill='x',padx=18,pady=(2,8))
        self.tab_buttons={}
        for key,label in self.TABS:
            b=ctk.CTkButton(tabs,text=label,height=31,corner_radius=8,fg_color='transparent',hover_color=theme_color('#102840'),border_width=1,border_color=BORDER,text_color=TEXT2,font=(FONT,9,'bold'),command=lambda k=key:self._select_tab(k))
            b.pack(side='left',padx=(0,6)); self.tab_buttons[key]=b
        self.scroll=StableScrollHost(self.frame,fg_color=BG); self.scroll.pack(fill='both',expand=True,padx=13,pady=(0,10))
        self.body=self.scroll.content
        self._apply_tab_style()

    def _apply_tab_style(self):
        for key,b in self.tab_buttons.items():
            try: b.configure(fg_color=theme_color('#164f7d') if key==self._tab else 'transparent', text_color='#ffffff' if key==self._tab and not str(theme_color('#164f7d')).startswith('#c') else TEXT)
            except Exception: pass

    def _select_tab(self,key):
        self._tab=key; self._apply_tab_style(); self._render(); self._lazy_load(key)

    def _clear(self):
        for child in list(self.body.winfo_children()):
            try: child.destroy()
            except Exception: pass

    def _title(self,text,sub=None):
        ctk.CTkLabel(self.body,text=text,font=(FONT,14,'bold'),text_color=TEXT,anchor='w').pack(fill='x',padx=8,pady=(7,1))
        if sub: ctk.CTkLabel(self.body,text=sub,font=(FONT,9),text_color=MUTED,anchor='w',justify='left',wraplength=1100).pack(fill='x',padx=8,pady=(0,7))

    def _card(self,parent=None):
        f=ctk.CTkFrame(parent or self.body,fg_color=CARD,border_width=1,border_color=BORDER,corner_radius=9)
        return f

    def _kv(self,parent,label,value,color=TEXT):
        row=ctk.CTkFrame(parent,fg_color='transparent'); row.pack(fill='x',padx=13,pady=4)
        ctk.CTkLabel(row,text=label,font=(FONT,9),text_color=MUTED,anchor='w').pack(side='left')
        ctk.CTkLabel(row,text=str(value),font=(FONT,9,'bold'),text_color=color,anchor='e',justify='right',wraplength=700).pack(side='right')

    def _summary_box(self,parent,title,value,detail,color):
        f=self._card(parent); f.pack(side='left',fill='both',expand=True,padx=4)
        ctk.CTkLabel(f,text=title,font=(FONT,8,'bold'),text_color=TEXT2,anchor='w').pack(fill='x',padx=12,pady=(11,2))
        ctk.CTkLabel(f,text=value,font=(FONT,20,'bold'),text_color=color,anchor='w').pack(fill='x',padx=12)
        ctk.CTkLabel(f,text=detail,font=(FONT,8),text_color=MUTED,anchor='w',wraplength=270,justify='left').pack(fill='x',padx=12,pady=(2,11))

    def _render(self):
        self._clear()
        {'summary':self._render_summary,'battery':self._render_battery,'performance':self._render_performance,'windows':self._render_windows,'history':self._render_history,'recovery':self._render_recovery}.get(self._tab,self._render_summary)()
        try: self.scroll._schedule_geometry(20)
        except Exception: pass

    def _render_summary(self):
        self._title('Resumen de salud','Una vista única de los componentes prioritarios. Los módulos largos se cargan sólo cuando los abres.')
        row=ctk.CTkFrame(self.body,fg_color='transparent'); row.pack(fill='x',padx=4,pady=(0,8))
        batt=self._battery or {}; present=batt.get('present')
        self._summary_box(row,'BATERÍA',_fmt(batt.get('health_percent'),'%') if present else 'No detectada','Capacidad actual vs diseño · ciclos si Windows los expone',GREEN if present else MUTED)
        throttle=getattr(self.app,'thermal_throttling_state',{}) or {}; cpu=throttle.get('cpu') or {}; st=cpu.get('state','N/A'); color=RED if st=='CONFIRMED' else AMBER if st in ('SUSPECTED','WATCHING') else GREEN
        self._summary_box(row,'THROTTLING',st,str(cpu.get('reason') or 'Sin evidencia actual'),color)
        hist=getattr(self.app,'health_history_store',None); summ=hist.summary(7) if hist else {'samples':0}
        self._summary_box(row,'HISTORIAL 7 DÍAS',str(summ.get('samples',0))+' muestras','Persistencia local de salud, sin interpolación',CYAN)
        changes=(self._hw or {}).get('changes') if isinstance(self._hw,dict) else None
        self._summary_box(row,'CAMBIOS DE HARDWARE',str(len(changes)) if changes is not None else 'Pendiente','RAM, GPU, almacenamiento, BIOS/placa e identidad',PURPLE)
        actions=self._card(); actions.pack(fill='x',padx=8,pady=6)
        ctk.CTkLabel(actions,text='Accesos rápidos',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=13,pady=(11,5))
        br=ctk.CTkFrame(actions,fg_color='transparent'); br.pack(fill='x',padx=9,pady=(0,11))
        for txt,cmd in (('Benchmark rápido',lambda:self._select_tab('performance')),('Analizar Windows',lambda:self._select_tab('windows')),('Historial / Antes vs Después',lambda:self._select_tab('history')),('Red avanzada',getattr(self.app,'open_network_details',lambda:None)),('Crear punto de restauración',lambda:self._select_tab('recovery'))):
            ctk.CTkButton(br,text=txt,height=30,corner_radius=7,fg_color=theme_color('#0d2942'),hover_color=theme_color('#164f7d'),border_width=1,border_color=theme_color('#1d5278'),text_color=TEXT2,font=(FONT,8,'bold'),command=cmd).pack(side='left',padx=4)

    def _render_battery(self):
        self._title('Battery Health','Salud real de batería. Se combinan únicamente fuentes disponibles: LHM, powercfg y psutil.')
        b=self._battery
        if b is None:
            self._loading('Analizando batería…'); return
        if not b.get('present'):
            self._notice('Este equipo no reporta una batería. En un PC de escritorio esto es normal.',MUTED); return
        row=ctk.CTkFrame(self.body,fg_color='transparent'); row.pack(fill='x',padx=4,pady=(0,8))
        self._summary_box(row,'SALUD',_fmt(b.get('health_percent'),'%'),'100% = capacidad máxima actual igual a diseño',GREEN if (_num(b.get('health_percent')) or 0)>=80 else AMBER)
        self._summary_box(row,'CARGA',_fmt(b.get('charge_percent'),'%'),'Conectada' if b.get('power_plugged') else 'En batería',CYAN)
        self._summary_box(row,'CICLOS',str(b.get('cycle_count')) if b.get('cycle_count') is not None else 'N/A','Reportado por Windows si está disponible',PURPLE)
        secs=b.get('estimated_seconds_left'); runtime=f'{int(secs)//3600} h {(int(secs)%3600)//60} min' if secs else 'N/A'
        self._summary_box(row,'AUTONOMÍA',runtime,'Estimación expuesta por el sistema, no inventada',CYAN)
        card=self._card(); card.pack(fill='x',padx=8,pady=6)
        for label,val in (
            ('Capacidad de diseño',_fmt(b.get('designed_capacity_mwh'),' mWh',0)),('Capacidad carga completa',_fmt(b.get('full_charge_capacity_mwh'),' mWh',0)),('Capacidad restante',_fmt(b.get('remaining_capacity_mwh'),' mWh',0)),('Desgaste',_fmt(b.get('degradation_percent'),'%')),('Voltaje',_fmt(b.get('voltage_v'),' V',3)),('Corriente',_fmt(b.get('current_ma'),' mA',0)),('Carga/descarga',_fmt(b.get('charge_discharge_rate_w'),' W',2)),('Fuentes',' + '.join(b.get('sources') or []) or 'N/A')): self._kv(card,label,val)

    def _render_performance(self):
        self._title('Thermal Throttling + Benchmark integrado','El throttling se confirma sólo con sensor explícito; si no, CorePulse muestra sospecha basada en evidencia observable.')
        th=getattr(self.app,'thermal_throttling_state',{}) or {}; cpu=th.get('cpu') or {}
        card=self._card(); card.pack(fill='x',padx=8,pady=6)
        self._kv(card,'Estado CPU',cpu.get('state','N/A'),RED if cpu.get('state')=='CONFIRMED' else AMBER if cpu.get('state') in ('SUSPECTED','WATCHING') else GREEN)
        self._kv(card,'Motivo',cpu.get('reason') or 'Sin evidencia')
        self._kv(card,'Confianza',cpu.get('confidence','N/A'))
        self._kv(card,'Evidencia',' · '.join(cpu.get('evidence') or []) or 'N/A')
        gpu_state=th.get('gpu') or {}
        self._kv(card,'Estado GPU',gpu_state.get('state','N/A'),RED if gpu_state.get('state')=='CONFIRMED' else AMBER if gpu_state.get('state')=='SUSPECTED' else GREEN)
        gpu_devices=gpu_state.get('devices') or []
        if gpu_devices:
            self._kv(card,'GPU evidencia',' · '.join(f"{d.get('name')}: {d.get('state')} {d.get('reason') or ''}" for d in gpu_devices[:3]))
        controls=ctk.CTkFrame(self.body,fg_color='transparent'); controls.pack(fill='x',padx=8,pady=6)
        self.btn_bench=ctk.CTkButton(controls,text='Ejecutar benchmark rápido',height=32,corner_radius=8,fg_color=theme_color('#164f7d'),hover_color=theme_color('#1b5c8f'),font=(FONT,9,'bold'),command=self._run_benchmark); self.btn_bench.pack(side='left')
        ctk.CTkLabel(controls,text='CPU ~2 s · RAM 512 MB aprox. transferidos · SSD ~96 MB escritura/lectura · GPU WinSAT si está disponible',font=(FONT,8),text_color=MUTED).pack(side='left',padx=10)
        if self._bench:
            for key in ('cpu','ram','ssd','gpu'):
                r=self._bench.get(key) or {}; f=self._card(); f.pack(fill='x',padx=8,pady=4)
                title=f"{key.upper()} · {r.get('provider','N/A')}"; ctk.CTkLabel(f,text=title,font=(FONT,10,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(9,3))
                if key=='ssd': value=f"Escritura {_fmt(r.get('write_mbps'),' MB/s')} · Lectura {_fmt(r.get('read_mbps'),' MB/s')}"
                else: value=f"{_fmt(r.get('value'),' '+str(r.get('unit') or ''),1)}"
                ctk.CTkLabel(f,text=value,font=(FONT,15,'bold'),text_color=CYAN if key!='gpu' else PURPLE).pack(anchor='w',padx=12,pady=(0,9))
            if isinstance(self._bench_compare,dict) and self._bench_compare.get('available'):
                c=self._card(); c.pack(fill='x',padx=8,pady=5)
                ctk.CTkLabel(c,text='Telemetría antes vs después del benchmark',font=(FONT,10,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(9,3))
                for key in ('cpu_temp','cpu_ghz','ram_usage','gpu_temp'):
                    d=(self._bench_compare.get('deltas') or {}).get(key) or {}
                    self._kv(c,key,f"{_fmt(d.get('before'))} → {_fmt(d.get('after'))} · Δ {_fmt(d.get('delta'))}")
                ctk.CTkLabel(c,text='Diferencia observada durante la prueba; no es una puntuación de salud por sí sola.',font=(FONT,8),text_color=MUTED).pack(anchor='w',padx=12,pady=(3,9))

    def _render_windows(self):
        self._title('Analyzers de Windows','Inicio, servicios, Crash/WHEA y drivers. Esta sección analiza; no deshabilita automáticamente servicios críticos.')
        controls=ctk.CTkFrame(self.body,fg_color='transparent'); controls.pack(fill='x',padx=8,pady=(0,7))
        for txt,name,fn in (('Startup Analyzer','startup',analyze_startup),('Servicios Analyzer','services',analyze_services),('Crash / BSOD / WHEA','crashes',lambda:analyze_crashes(7)),('Driver Health','drivers',analyze_drivers)):
            ctk.CTkButton(controls,text=txt,height=31,corner_radius=7,fg_color=theme_color('#0d2942'),hover_color=theme_color('#164f7d'),border_width=1,border_color=theme_color('#1d5278'),text_color=TEXT2,font=(FONT,8,'bold'),command=lambda n=name,f=fn:self._run_windows(n,f)).pack(side='left',padx=4)
        self._render_analyzer('Inicio',self._startup,'startup')
        self._render_analyzer('Servicios',self._services,'services')
        self._render_analyzer('Crashes / WHEA',self._crashes,'crashes')
        self._render_analyzer('Drivers',self._drivers,'drivers')

    def _render_analyzer(self,title,data,kind):
        card=self._card(); card.pack(fill='x',padx=8,pady=5)
        ctk.CTkLabel(card,text=title,font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,4))
        if data is None:
            ctk.CTkLabel(card,text='No analizado todavía.',font=(FONT,9),text_color=MUTED).pack(anchor='w',padx=12,pady=(0,10)); return
        if data.get('error'):
            ctk.CTkLabel(card,text='Error: '+_short(data.get('error'),220),font=(FONT,8),text_color=AMBER,wraplength=1050,justify='left').pack(anchor='w',padx=12,pady=(0,8))
        if kind=='startup':
            self._kv(card,'Elementos detectados',data.get('count',0)); items=data.get('items',[])[:12]
            for x in items: self._line(card,f"{x.get('name') or 'N/A'} · {x.get('impact')} · RAM actual {_fmt(x.get('running_memory_mb'),' MB')} · {_short(x.get('location'),70)}")
        elif kind=='services':
            self._kv(card,'Servicios analizados',data.get('count',0)); items=data.get('items',[])[:12]
            for x in items: self._line(card,f"{x.get('DisplayName') or x.get('Name')} · {x.get('State')} / {x.get('StartMode')} · {_fmt(x.get('memory_mb'),' MB')} · {x.get('load_flag')}")
        elif kind=='crashes':
            self._kv(card,'Severidad',data.get('severity','N/A'),RED if data.get('severity')=='CRITICAL' else AMBER if data.get('severity')=='WARNING' else GREEN)
            counts=data.get('counts') or {}; self._kv(card,'BSOD / WHEA / Kernel-Power',f"{counts.get('bsod_bugcheck',0)} / {counts.get('whea',0)} / {counts.get('kernel_power',0)}")
            for x in (data.get('items') or [])[:10]: self._line(card,f"ID {x.get('Id')} · {x.get('ProviderName')} · {_short(x.get('Message'),130)}")
        elif kind=='drivers':
            self._kv(card,'Drivers',data.get('count',0)); self._kv(card,'Problemas de dispositivo',data.get('device_problems',0),RED if data.get('device_problems') else GREEN); self._kv(card,'No firmados',data.get('unsigned',0),RED if data.get('unsigned') else GREEN); self._kv(card,'Más de 5 años',data.get('older_than_5y',0),AMBER if data.get('older_than_5y') else TEXT)
            for x in (data.get('items') or [])[:12]: self._line(card,f"{x.get('DeviceName') or 'N/A'} · {x.get('DriverProviderName') or 'N/A'} · {x.get('DriverVersion') or 'N/A'} · {x.get('status')}")

    def _render_history(self):
        self._title('Historial de salud · Antes vs Después · Hardware Changes','CorePulse registra una muestra espaciada de salud y permite cuantificar diferencias observadas sin atribuir causalidad automáticamente.')
        store=getattr(self.app,'health_history_store',None)
        row=ctk.CTkFrame(self.body,fg_color='transparent'); row.pack(fill='x',padx=4,pady=(0,8))
        for days in (1,7,30):
            s=store.summary(days) if store else {'samples':0,'metrics':{}}; m=s.get('metrics',{})
            detail=f"CPU temp máx {_fmt((m.get('cpu_temp') or {}).get('max'),' °C')} · SSD salud mín {_fmt((m.get('storage_health') or {}).get('min'),'%')}"
            self._summary_box(row,f'{days} DÍAS',str(s.get('samples',0))+' muestras',detail,CYAN)
        if store:
            self._render_health_chart(store.query(30, limit=3000))
            benches=store.latest_benchmarks(12)
            if benches:
                bench_card=self._card(); bench_card.pack(fill='x',padx=8,pady=5)
                ctk.CTkLabel(bench_card,text='Historial de rendimiento',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,4))
                for b in benches:
                    payload=b.get('payload') or {}; value=payload.get('value')
                    if str(payload.get('kind')).upper()=='SSD':
                        txt=f"SSD · write {_fmt(payload.get('write_mbps'),' MB/s')} · read {_fmt(payload.get('read_mbps'),' MB/s')}"
                    else:
                        txt=f"{payload.get('kind') or b.get('kind')} · {_fmt(value,' '+str(payload.get('unit') or b.get('unit') or ''))} · {payload.get('provider') or b.get('provider')}"
                    self._line(bench_card,txt)
        ba=self._card(); ba.pack(fill='x',padx=8,pady=5)
        ctk.CTkLabel(ba,text='Antes vs Después',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,4))
        buttons=ctk.CTkFrame(ba,fg_color='transparent'); buttons.pack(fill='x',padx=8,pady=4)
        ctk.CTkButton(buttons,text='Capturar ANTES',command=lambda:self._capture_slot('before'),height=30).pack(side='left',padx=4)
        ctk.CTkButton(buttons,text='Capturar DESPUÉS',command=lambda:self._capture_slot('after'),height=30).pack(side='left',padx=4)
        comp=compare(); snaps=load_snapshots(); self._kv(ba,'Snapshot ANTES','Disponible' if snaps.get('before') else 'No'); self._kv(ba,'Snapshot DESPUÉS','Disponible' if snaps.get('after') else 'No')
        if comp.get('available'):
            for key in ('cpu_temp','cpu_ghz','ram_usage','gpu_temp','battery_health'):
                d=(comp.get('deltas') or {}).get(key) or {}; self._kv(ba,key,f"{_fmt(d.get('before'))} → {_fmt(d.get('after'))} · Δ {_fmt(d.get('delta'))}")
            ctk.CTkLabel(ba,text=comp.get('note'),font=(FONT,8),text_color=AMBER).pack(anchor='w',padx=12,pady=(4,10))
        hw=self._card(); hw.pack(fill='x',padx=8,pady=5)
        ctk.CTkLabel(hw,text='Hardware Changes',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,4))
        data=self._hw
        if data is None: ctk.CTkLabel(hw,text='Comparación pendiente.',font=(FONT,9),text_color=MUTED).pack(anchor='w',padx=12,pady=(0,8))
        else:
            changes=data.get('changes') or []; self._kv(hw,'Baseline previo','Sí' if data.get('baseline_exists') else 'No'); self._kv(hw,'Cambios detectados',len(changes),AMBER if changes else GREEN)
            for c in changes: self._line(hw,f"{c.get('component')}: cambió desde el baseline guardado")
        ctk.CTkButton(hw,text='Guardar hardware actual como nuevo baseline',height=30,command=self._save_hw_baseline).pack(anchor='w',padx=12,pady=(5,11))

    def _render_health_chart(self, rows):
        card=self._card(); card.pack(fill='x',padx=8,pady=5)
        ctk.CTkLabel(card,text='Evolución de salud · últimos 30 días',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,3))
        if not rows:
            ctk.CTkLabel(card,text='Aún no hay suficientes muestras. CorePulse registra una muestra aproximadamente cada 60 s mientras está abierto.',font=(FONT,9),text_color=MUTED).pack(anchor='w',padx=12,pady=(0,12)); return
        width_px=1040; height_px=360; dpi=100
        fig=Figure(figsize=(width_px/dpi,height_px/dpi),dpi=dpi,facecolor=CARD)
        ax1=fig.add_subplot(211,facecolor=CARD); ax2=fig.add_subplot(212,facecolor=CARD)
        xs=[dt.datetime.fromtimestamp(float(r['ts'])) for r in rows]
        def series(key): return [r.get(key) if isinstance(r.get(key),(int,float)) else float('nan') for r in rows]
        ax1.plot(xs,series('cpu_temp'),color=CYAN,linewidth=1.7,label='CPU °C')
        ax1.plot(xs,series('gpu_temp'),color=PURPLE,linewidth=1.7,label='GPU °C')
        ax2.plot(xs,series('storage_health'),color=GREEN,linewidth=1.7,label='SSD salud %')
        ax2.plot(xs,series('battery_health'),color=AMBER,linewidth=1.7,label='Batería salud %')
        ax2.plot(xs,series('system_score'),color=CYAN,linewidth=1.3,alpha=.8,label='Índice sistema')
        for ax in (ax1,ax2):
            ax.grid(True,color=theme_color('#334155'),linewidth=.5,alpha=.55)
            ax.tick_params(colors=MUTED,labelsize=7)
            for spine in ax.spines.values(): spine.set_color(BORDER)
            leg=ax.legend(fontsize=7,loc='best',facecolor=CARD,edgecolor=BORDER)
            for t in leg.get_texts(): t.set_color(TEXT)
        ax1.set_ylabel('Temperatura',color=TEXT2,fontsize=8); ax2.set_ylabel('Salud / índice',color=TEXT2,fontsize=8)
        fig.autofmt_xdate(rotation=0,ha='center'); fig.tight_layout(pad=1.2)
        agg=FigureCanvasAgg(fig); agg.draw(); size=agg.get_width_height(); image=Image.frombuffer('RGBA',size,agg.buffer_rgba(),'raw','RGBA',0,1).copy()
        photo=ImageTk.PhotoImage(image=image,master=card); self._health_chart_photo=photo
        lbl=tk.Label(card,image=photo,bg=CARD,bd=0,highlightthickness=0); lbl.pack(fill='x',padx=10,pady=(0,10))
        fig.clear()

    def _render_recovery(self):
        self._title('Restore / Rollback','Punto de restauración antes de cambios delicados. CorePulse no habilita System Restore a escondidas.')
        r=self._restore
        card=self._card(); card.pack(fill='x',padx=8,pady=5)
        self._kv(card,'Administrador','Sí' if (r or {}).get('admin') else 'No')
        self._kv(card,'System Restore','Disponible' if (r or {}).get('available') else 'No disponible / pendiente',GREEN if (r or {}).get('available') else AMBER)
        if r and r.get('error'): self._kv(card,'Detalle',_short(r.get('error'),180),AMBER)
        pts=(r or {}).get('points') or []
        for p in pts[:5]: self._line(card,f"{p.get('Description') or 'Punto de restauración'} · secuencia {p.get('SequenceNumber')}")
        self.btn_restore=ctk.CTkButton(card,text='Crear punto de restauración ahora',height=32,corner_radius=8,fg_color=theme_color('#164f7d'),hover_color=theme_color('#1b5c8f'),command=self._create_restore); self.btn_restore.pack(anchor='w',padx=12,pady=(7,11))
        note=self._card(); note.pack(fill='x',padx=8,pady=5)
        ctk.CTkLabel(note,text='Rollback de Tweaks',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,3))
        ctk.CTkLabel(note,text='Los tweaks de Registro conservan su valor previo exacto. Para cambios delicados, usa además el punto de restauración.',font=(FONT,9),text_color=MUTED,wraplength=1000,justify='left').pack(anchor='w',padx=12,pady=(0,6))
        ctk.CTkButton(note,text='Abrir Tweaks Windows 11',height=30,command=getattr(self.app,'open_windows_tweaks',lambda:None)).pack(anchor='w',padx=12,pady=(0,11))

    def _line(self,parent,text): ctk.CTkLabel(parent,text='• '+str(text),font=(FONT,8),text_color=TEXT2,anchor='w',justify='left',wraplength=1050).pack(fill='x',padx=14,pady=2)
    def _notice(self,text,color=MUTED):
        c=self._card(); c.pack(fill='x',padx=8,pady=7); ctk.CTkLabel(c,text=text,font=(FONT,10),text_color=color,wraplength=1050,justify='left').pack(anchor='w',padx=14,pady=14)
    def _loading(self,text): self._notice(text,CYAN)

    def _async(self,name,fn,on_done):
        if name in self._jobs: return
        self._jobs.add(name)
        def worker():
            try: result=fn(); error=None
            except Exception as exc: result=None; error=str(exc)
            def done():
                self._jobs.discard(name)
                if not self._alive: return
                on_done(result,error); self._render()
            try: self.app.after(0,done)
            except Exception: pass
        threading.Thread(target=worker,daemon=True,name='CorePulse-Health-'+name).start()

    def _lazy_load(self,key):
        if key in ('summary','battery') and self._battery is None:
            cached=getattr(self.app,'battery_health_cache',None)
            if isinstance(cached,dict):
                self._battery=copy.deepcopy(cached)
            else:
                snap=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {}); self._async('battery',lambda:collect_battery_health(snap),lambda r,e:setattr(self,'_battery',r or {'present':False,'error':e}))
        if key in ('summary','history') and self._hw is None: self._load_hw_compare()
        if key=='recovery' and self._restore is None: self._async('restore',restore_point_status,lambda r,e:setattr(self,'_restore',r or {'error':e}))

    def _load_hw_compare(self):
        tele=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {}); disks=copy.deepcopy(getattr(self.app,'latest_disks',[]) or [])
        def work(): return compare_hardware_inventory(collect_hardware_inventory(tele,disks))
        self._async('hardware',work,lambda r,e:setattr(self,'_hw',r or {'changes':[],'error':e}))

    def _run_windows(self,name,fn):
        attr='_'+name
        self._async(name,fn,lambda r,e:setattr(self,attr,r or {'error':e,'items':[]}))

    def _run_benchmark(self):
        if 'benchmark' in self._jobs: return
        try: self.btn_bench.configure(text='Ejecutando…',state='disabled')
        except Exception: pass
        tele_before=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {})
        disks_before=copy.deepcopy(getattr(self.app,'latest_disks',[]) or [])
        before_snapshot=capture_metrics(tele_before,disks_before,None,label='benchmark_before')
        def work(): return run_quick_suite()
        def done(r,e):
            self._bench=r or {'error':e}
            tele_after=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {})
            disks_after=copy.deepcopy(getattr(self.app,'latest_disks',[]) or [])
            self._bench_compare=compare(before_snapshot,capture_metrics(tele_after,disks_after,None,label='benchmark_after'))
            store=getattr(self.app,'health_history_store',None)
            if store and isinstance(r,dict):
                for key in ('cpu','ram','ssd','gpu'):
                    try: store.record_benchmark(r.get(key) or {})
                    except Exception: pass
            try: self.btn_bench.configure(text='Ejecutar benchmark rápido',state='normal')
            except Exception: pass
        self._async('benchmark',work,done)

    def _capture_slot(self,slot):
        tele=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {}); disks=copy.deepcopy(getattr(self.app,'latest_disks',[]) or [])
        batt=self._battery or collect_battery_health(tele)
        save_snapshot(capture_metrics(tele,disks,batt,label=slot),slot=slot); self._render()

    def _save_hw_baseline(self):
        tele=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {}); disks=copy.deepcopy(getattr(self.app,'latest_disks',[]) or [])
        def work(): return save_hardware_baseline(collect_hardware_inventory(tele,disks))
        self._async('save_hw',work,lambda r,e:(setattr(self,'_hw',{'baseline_exists':True,'changes':[],'current':r}) if r else None))

    def _create_restore(self):
        if not messagebox.askyesno('CorePulse','¿Crear un punto de restauración de Windows antes de realizar cambios?\n\nPuede requerir privilegios de administrador.'):
            return
        try: self.btn_restore.configure(text='Creando…',state='disabled')
        except Exception: pass
        def done(r,e):
            if r and r.get('ok'): messagebox.showinfo('CorePulse','Punto de restauración creado correctamente.')
            else: messagebox.showwarning('CorePulse','No se pudo crear el punto de restauración.\n\n'+str((r or {}).get('error') or e or 'Error desconocido'))
            self._restore=None; self._lazy_load('recovery')
        self._async('create_restore',lambda:create_restore_point('CorePulse - antes de cambios'),done)

    def refresh(self):
        self._lazy_load(self._tab); self._render()

    def destroy(self):
        self._alive=False
        try: self.frame.destroy()
        except Exception: pass
