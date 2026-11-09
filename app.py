import os
import json
import math
import uuid
import traceback
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
from datetime import datetime
from typing import List, Dict

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA
# ==============================================================================
st.set_page_config(page_title="Sistema Integral FV - CECyT 7", page_icon="☀️", layout="wide")

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

# ==============================================================================
# 1. CONSTANTES GLOBALES Y GESTOR DE SISTEMA
# ==============================================================================
RESISTIVIDAD_COBRE_OHM_MM2_M = 0.0193
FACTOR_SEGURIDAD_CORRIENTE_NEC = 1.25  
FACTOR_PROTECCION_GPV_NEC = 1.56       
FACTOR_RENDIMIENTO_GLOBAL = 0.80       
TEMP_MINIMA_DISENO_C = 5.0
TEMP_STC_C = 25.0

class GestorSistemaFV:
    def __init__(self, ruta_dir: str):
        self.ruta_dir = ruta_dir
        os.makedirs(self.ruta_dir, exist_ok=True)
        self.ruta_equipos = os.path.join(ruta_dir, 'equipos_fv_v15.json')
        self.ruta_usuarios = os.path.join(ruta_dir, 'usuarios_sistema_v15.json')
        self.ruta_auditoria = os.path.join(ruta_dir, 'auditoria_accesos_v15.json')
        self.ruta_historial = os.path.join(ruta_dir, 'historial_cotizaciones_v15.json')
        
        self.datos = self._cargar_equipos()
        self.usuarios = self._cargar_usuarios()
        self.auditoria = self._cargar_auditoria()
        self.historial = self._cargar_historial()

    def _generar_equipos_base(self):
        return {
            "paneles": [
                {"id": "PAN-001", "marca": "Jinko Solar", "modelo": "Tiger Neo 550W", "potencia_w": 550, "vmp": 41.58, "voc": 49.80, "area_m2": 2.56, "eficiencia_pct": 21.3, "precio_mxn": 2430.0},
                {"id": "PAN-002", "marca": "Trina Solar", "modelo": "Vertex S 450W", "potencia_w": 450, "vmp": 34.60, "voc": 41.40, "area_m2": 1.99, "eficiencia_pct": 20.6, "precio_mxn": 1764.0}
            ],
            "inversores": [
                {"id": "INV-001", "marca": "Growatt", "modelo": "MIN 3000TL-X", "potencia_ac_kw": 3.0, "precio_mxn": 9900.0},
                {"id": "INV-002", "marca": "SMA", "modelo": "Sunny Boy 6.0", "potencia_ac_kw": 6.0, "precio_mxn": 27000.0}
            ],
            "baterias": [
                {"id": "BAT-001", "marca": "Pylontech", "modelo": "US3000C", "energia_kwh": 3.55, "dod_recomendado_pct": 90.0, "precio_mxn": 20700.0}
            ]
        }

    def _cargar_equipos(self):
        if not os.path.exists(self.ruta_equipos):
            b = self._generar_equipos_base()
            with open(self.ruta_equipos, 'w', encoding='utf-8') as f: json.dump(b, f, indent=4)
            return b
        try:
            with open(self.ruta_equipos, 'r', encoding='utf-8') as f: return json.load(f)
        except: return self._generar_equipos_base()

    def _cargar_usuarios(self):
        usuarios_base = {
            "admin": {"pass": "solar2026", "rol": "admin", "activo": True, "sesiones": 0, "ver_ganancia": True, "ganancia_pct": 40.0, "contador_folios": 1},
            "socio1": {"pass": "renovable2026", "rol": "admin_tec", "activo": True, "sesiones": 0, "ver_ganancia": True, "ganancia_pct": 40.0, "contador_folios": 1},
            "cliente": {"pass": "solar2026", "rol": "usuario", "activo": True, "sesiones": 0, "ver_ganancia": False, "ganancia_pct": 25.0, "contador_folios": 1}
        }
        if not os.path.exists(self.ruta_usuarios):
            with open(self.ruta_usuarios, 'w', encoding='utf-8') as f: json.dump(usuarios_base, f, indent=4)
            return usuarios_base
        try:
            with open(self.ruta_usuarios, 'r', encoding='utf-8') as f: 
                usrs = json.load(f)
                for u in usrs:
                    if "contador_folios" not in usrs[u]: usrs[u]["contador_folios"] = 1
                    if "activo" not in usrs[u]: usrs[u]["activo"] = True
                return usrs
        except: return usuarios_base

    def _cargar_auditoria(self):
        if not os.path.exists(self.ruta_auditoria): return []
        try:
            with open(self.ruta_auditoria, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []

    def _cargar_historial(self):
        if not os.path.exists(self.ruta_historial): return []
        try:
            with open(self.ruta_historial, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []

    def guardar_usuarios(self):
        try:
            with open(self.ruta_usuarios, 'w', encoding='utf-8') as f: json.dump(self.usuarios, f, indent=4)
        except: pass

    def guardar_equipos(self):
        try:
            with open(self.ruta_equipos, 'w', encoding='utf-8') as f: json.dump(self.datos, f, indent=4)
        except: pass

    def registrar_cotizacion(self, reg):
        self.historial.insert(0, reg)
        try:
            with open(self.ruta_historial, 'w', encoding='utf-8') as f: json.dump(self.historial, f, indent=4, ensure_ascii=False)
        except: pass

    def login_usuario(self, usr: str) -> bool:
        self.usuarios = self._cargar_usuarios()
        if self.usuarios[usr].get("sesiones", 0) >= 2: return False 
        self.usuarios[usr]["sesiones"] = self.usuarios[usr].get("sesiones", 0) + 1
        self.guardar_usuarios()
        return True

    def logout_usuario(self, usr: str):
        self.usuarios = self._cargar_usuarios()
        if usr in self.usuarios:
            self.usuarios[usr]["sesiones"] = max(0, self.usuarios[usr].get("sesiones", 1) - 1)
            self.guardar_usuarios()

    def registrar_acceso(self, usuario: str, rol: str):
        self.auditoria.insert(0, {"fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "usuario": usuario, "rol": rol})
        try:
            with open(self.ruta_auditoria, 'w', encoding='utf-8') as f: json.dump(self.auditoria, f, indent=4)
        except: pass

    def obtener_paneles(self): return self.datos.get("paneles", [])
    def obtener_inversores(self): return self.datos.get("inversores", [])
    def obtener_baterias(self): return self.datos.get("baterias", [])
    
    def agregar_registro(self, cat, data):
        self.datos.setdefault(cat, []).append(data)
        self.guardar_equipos()
        
    def eliminar_registro(self, cat, item_id):
        self.datos[cat] = [x for x in self.datos.get(cat, []) if x['id'].upper() != item_id.upper()]
        self.guardar_equipos()

# Instanciar Gestor BD
db = GestorSistemaFV('./data')

# ==============================================================================
# 2. MOTOR DE CÁLCULO E INGENIERÍA
# ==============================================================================
class MotorCalculoFV:
    @staticmethod
    def evaluar_mejor_panel(prioridad: str, area_disp: float) -> List[Dict]:
        evaluados = []
        for p in db.obtener_paneles():
            cabe = p.get('area_m2', 2) <= area_disp
            if prioridad == 'Espacio Reducido': pt = (p.get('eficiencia_pct', 20) * 2) + (p.get('potencia_w', 1) / max(0.1, p.get('area_m2', 1)))
            elif prioridad == 'Economía': pt = (p.get('potencia_w', 1) / max(1, p.get('precio_mxn', 1))) * 1000
            else: pt = p.get('eficiencia_pct', 20) + (20 if 'Bifacial' in p.get('tecnologia', '') else 0)
            evaluados.append({'panel': p, 'puntaje': pt, 'cabe': cabe})
        return sorted(evaluados, key=lambda x: x['puntaje'], reverse=True)

    @staticmethod
    def evaluar_mejor_inversor(potencia_sistema_kwp: float, prioridad: str) -> List[Dict]:
        evaluados = []
        for inv in db.obtener_inversores():
            apto = inv.get('potencia_ac_kw', 1) >= (potencia_sistema_kwp * 0.70)
            if prioridad == 'Máxima Eficiencia': pt = inv.get('eficiencia_pct', 97) * 10
            elif prioridad == 'Economía': pt = (inv.get('potencia_ac_kw', 1) / max(1, inv.get('precio_mxn', 1))) * 10000
            else: pt = inv.get('eficiencia_pct', 97) + (inv.get('num_mppt', 2) * 2)
            evaluados.append({'inversor': inv, 'puntaje': pt, 'apto': apto})
        return sorted(evaluados, key=lambda x: x['puntaje'], reverse=True)

    @staticmethod
    def evaluar_mejor_bateria(prioridad: str) -> List[Dict]:
        evaluados = []
        for b in db.obtener_baterias():
            ciclos = b.get('ciclos_vida', 1000)
            kwh_util = b.get('energia_kwh', 1) * (b.get('dod_recomendado_pct', 90) / 100.0)
            if prioridad == 'Mayor Vida Útil': pt = ciclos
            elif prioridad == 'Economía': pt = (kwh_util / max(1, b.get('precio_mxn', 1))) * 100000
            else: pt = kwh_util 
            evaluados.append({'bateria': b, 'puntaje': pt})
        return sorted(evaluados, key=lambda x: x['puntaje'], reverse=True)

    @staticmethod
    def generar_diagrama_arreglo(ns, np_arr, panel_w):
        fig, ax = plt.subplots(figsize=(max(4, np_arr*1.8), max(3, ns*1.2)))
        for p in range(np_arr):
            for s in range(ns):
                rect = plt.Rectangle((p*2, s*1.5), 1.5, 1.0, fill=True, color='#0284c7', ec='black', lw=1.5)
                ax.add_patch(rect)
                ax.text(p*2 + 0.75, s*1.5 + 0.5, f"Panel\n{panel_w}W", ha='center', va='center', color='white', fontsize=8, fontweight='bold')
            ax.plot([p*2 + 0.75, p*2 + 0.75], [-0.3, ns*1.5], color='#ef4444', lw=2, zorder=0)
        
        ax.plot([-0.5, np_arr*2], [-0.3, -0.3], color='black', lw=3, label='Bus Negativo (-)')
        ax.plot([-0.5, np_arr*2], [ns*1.5, ns*1.5], color='#ef4444', lw=3, label='Bus Positivo (+)')
        ax.set_xlim(-1, np_arr*2 + 1)
        ax.set_ylim(-1, ns*1.5 + 1)
        ax.axis('off')
        plt.title(f"Configuración del Arreglo: {np_arr} Paralelo(s) x {ns} Serie(s)\nTotal: {ns*np_arr} Piezas", pad=15)
        plt.legend(loc='lower center', bbox_to_anchor=(0.5, -0.2), ncol=2)
        plt.tight_layout()
        return fig

    @staticmethod
    def generar_grafica_roi(costo, ahorro):
        anos = np.arange(0, 26)
        flujo = (ahorro * anos) - costo
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(anos, flujo, color='#10b981', lw=2, marker='o', markersize=4)
        ax.fill_between(anos, flujo, 0, where=(flujo>0), color='#10b981', alpha=0.3)
        ax.fill_between(anos, flujo, 0, where=(flujo<=0), color='#ef4444', alpha=0.3)
        ax.axhline(0, color='black', lw=1.5, linestyle='--')
        ax.set_xlabel('Años de Operación')
        ax.set_ylabel('Balance (MXN)')
        ax.set_title('Recuperación de Inversión a 25 Años (ROI)')
        ax.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()
        return fig

    @staticmethod
    def dimensionar_sistema(cons_bim, hsp, pid, iid, costo, modo_operacion, bid, horas_respaldo, ganancia_pct, extras_mxn):
        panel = next((p for p in db.obtener_paneles() if p["id"] == pid), None)
        inv = next((i for i in db.obtener_inversores() if i["id"] == iid), None)
        
        cons_diario = cons_bim / 60.0
        pot_req = (cons_diario / FACTOR_RENDIMIENTO_GLOBAL) / max(0.1, hsp)
        n_pan = max(1, math.ceil((pot_req * 1000) / max(1, panel.get("potencia_w", 1))))
        
        ns = max(1, min(10, n_pan)) 
        np_arr = max(1, math.ceil(n_pan / ns))
        n_pan_real = ns * np_arr
        pot_real = (n_pan_real * panel.get("potencia_w", 0)) / 1000.0

        costo_baterias_mxn, n_bat, bobj = 0, 0, None
        if modo_operacion != 'Interconectado (CFE)' and bid:
            bobj = next((b for b in db.obtener_baterias() if b["id"] == bid), None)
            if bobj:
                e_req = cons_diario * (horas_respaldo / 24.0)
                energia_util = bobj.get("energia_kwh", 1) * (bobj.get("dod_recomendado_pct", 90) / 100.0)
                n_bat = math.ceil(e_req / max(0.1, energia_util))
                costo_baterias_mxn = n_bat * bobj.get("precio_mxn", 0)

        costo_directo = (n_pan_real * panel.get("precio_mxn", 0)) + inv.get("precio_mxn", 0) + costo_baterias_mxn + extras_mxn
        precio_venta = costo_directo * (1.0 + (max(0, ganancia_pct) / 100.0))
        ahorro_anual = pot_real * max(0.1, hsp) * FACTOR_RENDIMIENTO_GLOBAL * 365 * costo
        
        fig_arr = MotorCalculoFV.generar_diagrama_arreglo(ns, np_arr, panel.get("potencia_w", 0))
        fig_roi = MotorCalculoFV.generar_grafica_roi(precio_venta, ahorro_anual)

        return {
            'panel': panel, 'inversor': inv, 'n_pan': n_pan_real, 'ns': ns, 'np': np_arr,
            'bateria': bobj, 'n_bat': n_bat, 'costo_directo': costo_directo, 
            'precio_venta': precio_venta, 'ahorro_anual': ahorro_anual, 
            'roi': precio_venta / ahorro_anual if ahorro_anual > 0 else 0,
            'ganancia_pct': ganancia_pct, 'fig_arr': fig_arr, 'fig_roi': fig_roi
        }

# ==============================================================================
# 3. GENERADOR DE PDF PROFESIONAL
# ==============================================================================
class GeneradorReportes:
    @staticmethod
    def generar_pdf_bytes(datos, folio_str, mostrar_precios_internos):
        # Manejo de imágenes temporales únicas para web
        temp_id = str(uuid.uuid4())[:8]
        ruta_arr = f"temp_arr_{temp_id}.png"
        ruta_roi = f"temp_roi_{temp_id}.png"
        
        datos['fig_arr'].savefig(ruta_arr, dpi=100, bbox_inches='tight')
        datos['fig_roi'].savefig(ruta_roi, dpi=100, bbox_inches='tight')

        ruta_pdf = f"Cotizacion_{folio_str}_{temp_id}.pdf"
        doc = SimpleDocTemplate(ruta_pdf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        story = [Paragraph(f"MEMORIA TÉCNICA - CECyT 7 | Folio: {folio_str}", styles['Heading1']), Spacer(1, 10)]
        
        marca_bat = datos['bateria'].get('marca', 'N/A') if datos['bateria'] else 'N/A'
        precio_bat = datos['bateria'].get('precio_mxn', 0.0) if datos['bateria'] else 0.0
        precio_p = datos['panel'].get('precio_mxn', 0.0)
        precio_i = datos['inversor'].get('precio_mxn', 0.0)

        if mostrar_precios_internos:
            t_data = [
                ["Equipos (Piezas Totales)", "Especificación", "Costo Unitario Interno"],
                [f"Paneles ({datos['n_pan']} piezas)", f"{datos['panel'].get('marca', '')} {datos['panel'].get('potencia_w', 0)}W", f"${precio_p:,.2f}"],
                ["Inversor", f"{datos['inversor'].get('marca', '')} {datos['inversor'].get('potencia_ac_kw', 0)}kW", f"${precio_i:,.2f}"],
                ["Banco Baterías", f"{datos['n_bat']} uds", f"${precio_bat:,.2f}"],
                ["PRECIO FINAL CLIENTE", f"Ahorro Anual: ${datos['ahorro_anual']:,.2f}", f"${datos['precio_venta']:,.2f}"]
            ]
        else:
            t_data = [
                ["Equipos Incluidos", "Especificación", "Cantidad Instalada"],
                ["Paneles Solares", f"{datos['panel'].get('marca', '')} {datos['panel'].get('potencia_w', 0)}W", f"{datos['n_pan']} uds"],
                ["Inversor Fotovoltaico", f"{datos['inversor'].get('marca', '')} {datos['inversor'].get('potencia_ac_kw', 0)}kW", "1 ud"],
                ["Banco Baterías", f"{marca_bat}", f"{datos['n_bat']} uds"],
                ["INVERSIÓN TOTAL", f"Ahorro Anual: ${datos['ahorro_anual']:,.2f}", f"${datos['precio_venta']:,.2f}"]
            ]

        t = Table(t_data, colWidths=[2.2*inch, 3.2*inch, 1.6*inch])
        t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        story.append(t)
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("<b>Diagrama Eléctrico del Arreglo Fotovoltaico:</b>", styles['Normal']))
        story.append(RLImage(ruta_arr, width=4.5*inch, height=2.5*inch))
        
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Análisis de Retorno de Inversión (A 25 años):</b>", styles['Normal']))
        story.append(RLImage(ruta_roi, width=5.0*inch, height=2.8*inch))
        
        doc.build(story)

        # Leer archivo para descargarlo y limpiar temporales
        with open(ruta_pdf, "rb") as f:
            pdf_bytes = f.read()
        
        for p in [ruta_arr, ruta_roi, ruta_pdf]:
            if os.path.exists(p): os.remove(p)

        return pdf_bytes

# ==============================================================================
# 4. GESTIÓN DE SESIONES EN STREAMLIT
# ==============================================================================
if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'usuario': None, 'rol': None})
if 'cotizacion_activa' not in st.session_state:
    st.session_state.cotizacion_activa = None
if 'default_p' not in st.session_state:
    st.session_state.update({'default_p': 0, 'default_i': 0, 'default_b': 0})

def login_ui():
    st.markdown("<h1 style='text-align: center; color: #0284c7;'>☀️ Sistema Integral FV CECyT 7</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.subheader("🔒 Acceso Seguro")
        usr = st.text_input("Usuario", placeholder="Ingresa tu usuario")
        pwd = st.text_input("Contraseña", placeholder="Ingresa tu contraseña", type="password")
        
        if st.button("🔑 Iniciar Sesión", use_container_width=True, type="primary"):
            if usr in db.usuarios:
                if not db.usuarios[usr].get("activo", True):
                    st.error("❌ Acceso denegado: Esta cuenta ha sido inhabilitada.")
                elif db.usuarios[usr]["pass"] == pwd:
                    if db.login_usuario(usr):
                        rol = db.usuarios[usr].get("rol", "usuario")
                        db.registrar_acceso(usr, rol)
                        st.session_state.autenticado = True
                        st.session_state.usuario = usr
                        st.session_state.rol = rol
                        st.rerun()
                    else:
                        st.error("❌ Límite de sesiones alcanzado (Máx 2).")
                else:
                    st.error("❌ Contraseña incorrecta.")
            else:
                st.error("❌ Usuario no encontrado.")

def logout():
    if st.session_state.usuario:
        db.logout_usuario(st.session_state.usuario)
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.rol = None
    st.rerun()

# ==============================================================================
# 5. APLICACIÓN PRINCIPAL (VISTAS)
# ==============================================================================
if not st.session_state.autenticado:
    login_ui()
else:
    # --- MENÚ LATERAL ---
    usuario_actual = st.session_state.usuario
    rol_usuario = st.session_state.rol
    usr_data = db.usuarios.get(usuario_actual, {})

    st.sidebar.title("☀️ CECyT 7")
    st.sidebar.markdown(f"**👤 Usuario:** {usuario_actual.upper()}")
    st.sidebar.markdown(f"**🛠️ Rol:** {rol_usuario.upper()}")
    if st.sidebar.button("🚪 Cerrar Sesión", type="primary"):
        logout()

    # --- PESTAÑAS DINÁMICAS POR ROL ---
    if rol_usuario == "admin":
        tabs = st.tabs(['⚡ Cotizador', '🧠 Asesor Inteligente', '📦 Inventario', '📜 Historial', '🛡️ Admin Principal'])
    elif rol_usuario == "admin_tec":
        tabs = st.tabs(['⚡ Cotizador', '🧠 Asesor Inteligente', '📦 Inventario', '📜 Historial'])
    else:
        tabs = st.tabs(['⚡ Cotizador', '🧠 Asesor Inteligente'])

    # --- DATOS DE EQUIPOS FORMATEADOS ---
    paneles_ops = [p['id'] for p in db.obtener_paneles()]
    paneles_desc = {p['id']: f"{p.get('marca','')} {p.get('modelo','')} (${p.get('precio_mxn',0):,.0f})" for p in db.obtener_paneles()}
    
    inversores_ops = [i['id'] for i in db.obtener_inversores()]
    inversores_desc = {i['id']: f"{i.get('marca','')} {i.get('modelo','')} ({i.get('potencia_ac_kw',0)}kW)" for i in db.obtener_inversores()}
    
    baterias_ops = [''] + [b['id'] for b in db.obtener_baterias()]
    baterias_desc = {'': 'Ninguna / No Aplica'}
    baterias_desc.update({b['id']: f"{b.get('marca','')} {b.get('modelo','')} (${b.get('precio_mxn',0):,.0f})" for b in db.obtener_baterias()})

    # ==============================================================================
    # TAB 1: COTIZADOR
    # ==============================================================================
    with tabs[0]:
        st.header("⚡ Dimensionamiento y Cotización")
        
        col1, col2 = st.columns(2)
        with col1:
            c_bim = st.number_input('Consumo Bimestral (kWh):', value=550, min_value=50, max_value=10000)
            hsp = st.slider('HSP (Horas Solar Pico):', min_value=3.0, max_value=7.0, value=5.3)
            modo = st.selectbox('Modo de Operación:', ['Interconectado (CFE)', 'Híbrido'])
            costo = st.number_input('Costo promedio kWh ($):', value=3.50)

        with col2:
            pid = st.selectbox('Panel Solar:', options=paneles_ops, format_func=lambda x: paneles_desc[x], index=st.session_state.default_p)
            iid = st.selectbox('Inversor:', options=inversores_ops, format_func=lambda x: inversores_desc[x], index=st.session_state.default_i)
            bid = st.selectbox('Batería (Si aplica):', options=baterias_ops, format_func=lambda x: baterias_desc[x], index=st.session_state.default_b)
            
            ganancia_actual = usr_data.get('ganancia_pct', 25.0)
            if rol_usuario != "usuario" or usr_data.get("ver_ganancia", False):
                ganancia_actual = st.slider('% Ganancia Comercial:', 0.0, 100.0, float(ganancia_actual))
                if ganancia_actual != usr_data.get('ganancia_pct'):
                    db.usuarios[usuario_actual]['ganancia_pct'] = ganancia_actual
                    db.guardar_usuarios()

        if st.button("⚡ Calcular y Cotizar", type="primary", use_container_width=True):
            try:
                res = MotorCalculoFV.dimensionar_sistema(c_bim, hsp, pid, iid, costo, modo, bid, 4, ganancia_actual, 15000.0)
                st.session_state.cotizacion_activa = res
            except Exception as e:
                st.error(f"Error al calcular: {e}")

        # --- RESULTADOS COTIZACIÓN ---
        if st.session_state.cotizacion_activa:
            res = st.session_state.cotizacion_activa
            st.markdown("---")
            st.subheader("📋 Resumen de Cotización")
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Total Paneles", f"{res['n_pan']} piezas", f"{res['np']}P x {res['ns']}S")
            col_m2.metric("Baterías", f"{res['n_bat']} uds")
            col_m3.metric("Inversión Total", f"${res['precio_venta']:,.2f}")
            col_m4.metric("Retorno (ROI)", f"{res['roi']:.1f} años", "Amortización")

            c_graf1, c_graf2 = st.columns(2)
            with c_graf1: st.pyplot(res['fig_arr'])
            with c_graf2: st.pyplot(res['fig_roi'])

            # --- GENERACIÓN DE PDF ---
            rol_prefijo = "ADM" if rol_usuario == "admin" else ("SOC" if rol_usuario == "admin_tec" else "CLI")
            contador = usr_data.get("contador_folios", 1)
            folio_str = f"{rol_prefijo}-{usuario_actual.upper()[:10]}-{contador:03d}"
            mostrar_precios = True if (rol_usuario != "usuario" or usr_data.get("ver_ganancia", False)) else False

            pdf_bytes = GeneradorReportes.generar_pdf_bytes(res, folio_str, mostrar_precios)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.download_button(label=f"📄 Generar y Descargar PDF (Folio: {folio_str})",
                                  data=pdf_bytes,
                                  file_name=f"Cotizacion_{folio_str}.pdf",
                                  mime="application/pdf",
                                  type="primary"):
                # Registrar en historial y aumentar folio SOLO cuando descarga
                db.registrar_cotizacion({
                    "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "folio": folio_str, "usuario": usuario_actual, "rol": rol_usuario,
                    "precio_total_mxn": round(res['precio_venta'], 2)
                })
                db.usuarios[usuario_actual]["contador_folios"] = contador + 1
                db.guardar_usuarios()
                st.success(f"✅ Cotización {folio_str} guardada en el historial.")

    # ==============================================================================
    # TAB 2: ASESOR INTELIGENTE
    # ==============================================================================
    with tabs[1]:
        st.header("🧠 Asesor Inteligente de Equipos")
        st.markdown("Selecciona las prioridades del cliente y el sistema autocompletará la mejor opción en el Cotizador.")
        
        p_panel = st.selectbox('Prioridad Panel:', ['Alta Eficiencia / Bifacial', 'Espacio Reducido', 'Economía'])
        p_inv = st.selectbox('Prioridad Inversor:', ['Máxima Eficiencia', 'Versatilidad (Más MPPT)', 'Economía'])
        p_bat = st.selectbox('Prioridad Batería:', ['Mayor Vida Útil', 'Mayor Capacidad', 'Economía'])
        
        if st.button("🧠 Evaluar y Auto-Completar", type="primary"):
            pot_preliminar_kwp = (550 / 60.0) / (0.80 * 5.3) # Estimado base
            rank_p = MotorCalculoFV.evaluar_mejor_panel(p_panel, 100)
            rank_i = MotorCalculoFV.evaluar_mejor_inversor(pot_preliminar_kwp, p_inv)
            rank_b = MotorCalculoFV.evaluar_mejor_bateria(p_bat)
            
            if rank_p and rank_i:
                st.session_state.default_p = paneles_ops.index(rank_p[0]['panel']['id'])
                st.session_state.default_i = inversores_ops.index(rank_i[0]['inversor']['id'])
                if rank_b:
                    st.session_state.default_b = baterias_ops.index(rank_b[0]['bateria']['id'])
                st.success("✅ ¡Selección automática aplicada! Ve a la pestaña 'Cotizador' para ver los equipos seleccionados.")

    # ==============================================================================
    # TAB 3: INVENTARIO (Admin & Socio)
    # ==============================================================================
    if rol_usuario in ["admin", "admin_tec"]:
        with tabs[2]:
            st.header("📦 Gestión de Inventario")
            
            col_reg, col_del = st.columns(2)
            with col_reg:
                st.subheader("➕ Registrar Nuevo Equipo")
                with st.form("form_inventario"):
                    t_equipo = st.selectbox('Tipo de Equipo:', ['Panel', 'Inversor', 'Batería'])
                    n_marca = st.text_input("Marca")
                    n_modelo = st.text_input("Modelo")
                    n_precio = st.number_input("Precio Interno (MXN)", min_value=1.0, value=2500.0)
                    
                    if st.form_submit_button("💾 Guardar Equipo"):
                        if n_marca and n_modelo:
                            if t_equipo == 'Panel':
                                db.agregar_registro('paneles', {"id": f"PAN-{len(db.obtener_paneles())+1:03d}", "marca": n_marca, "modelo": n_modelo, "potencia_w": 550, "precio_mxn": n_precio})
                            elif t_equipo == 'Inversor':
                                db.agregar_registro('inversores', {"id": f"INV-{len(db.obtener_inversores())+1:03d}", "marca": n_marca, "modelo": n_modelo, "potencia_ac_kw": 5.0, "precio_mxn": n_precio})
                            elif t_equipo == 'Batería':
                                db.agregar_registro('baterias', {"id": f"BAT-{len(db.obtener_baterias())+1:03d}", "marca": n_marca, "modelo": n_modelo, "energia_kwh": 4.8, "precio_mxn": n_precio})
                            st.success(f"✅ {t_equipo} guardado con éxito.")
                            st.rerun()

            with col_del:
                st.subheader("🗑️ Eliminar Equipo")
                cat_del = st.selectbox("Categoría a visualizar:", [('Paneles', 'paneles'), ('Inversores', 'inversores'), ('Baterías', 'baterias')], format_func=lambda x: x[0])
                
                df_equipos = pd.DataFrame(db.datos.get(cat_del[1], []))
                st.dataframe(df_equipos, use_container_width=True)
                
                id_eliminar = st.text_input("ID a Eliminar (ej. PAN-001):")
                if st.button("Eliminar", type="primary"):
                    if id_eliminar:
                        db.eliminar_registro(cat_del[1], id_eliminar)
                        st.success(f"🗑️ Equipo {id_eliminar} eliminado.")
                        st.rerun()

    # ==============================================================================
    # TAB 4: HISTORIAL (Admin & Socio)
    # ==============================================================================
    if rol_usuario in ["admin", "admin_tec"]:
        with tabs[3]:
            st.header("📜 Historial de Cotizaciones")
            if st.button("🔄 Refrescar Historial"):
                db.historial = db._cargar_historial()
            
            if db.historial:
                st.dataframe(pd.DataFrame(db.historial), use_container_width=True)
            else:
                st.info("No hay cotizaciones registradas aún.")

    # ==============================================================================
    # TAB 5: ADMIN PRINCIPAL (Solo Admin)
    # ==============================================================================
    if rol_usuario == "admin":
        with tabs[4]:
            st.header("🛡️ Monitor y Administración de Usuarios")
            
            # Tabla de Usuarios
            st.subheader("Estado Actual de Cuentas")
            lista_usuarios = []
            for u, d in db.usuarios.items():
                estado = "OFFLINE"
                if not d.get("activo", True): estado = "BAJA / INACTIVO"
                elif d.get("sesiones", 0) > 0: estado = "ONLINE (ACTIVO)"
                
                lista_usuarios.append({
                    "Usuario": u, "Rol": d['rol'], "Sesiones": f"{d.get('sesiones',0)}/2",
                    "Folio": d.get('contador_folios',1), "Ganancia %": d.get('ganancia_pct', 0.0),
                    "Visible a Cliente": "Sí" if d.get('ver_ganancia') else "No", "Estado": estado
                })
            st.dataframe(pd.DataFrame(lista_usuarios), use_container_width=True)

            # Controles
            col_u1, col_u2, col_u3 = st.columns(3)
            
            ops_usuarios = [u for u in db.usuarios.keys() if u != 'admin']
            
            with col_u1:
                st.markdown("#### 👁️ Permisos de Ganancia")
                usr_permiso = st.selectbox("Seleccionar Usuario:", ops_usuarios, key="u_permiso")
                ver_gan = st.selectbox("¿Visible al cliente?:", [(True, 'Sí, permitir ver y editar'), (False, 'No, ocultar ganancia en UI/PDF')], format_func=lambda x: x[1])
                set_gan = st.slider("Fijar Ganancia %:", 0.0, 100.0, 40.0)
                if st.button("💾 Aplicar Reglas", use_container_width=True):
                    db.usuarios[usr_permiso]["ver_ganancia"] = ver_gan[0]
                    db.usuarios[usr_permiso]["ganancia_pct"] = set_gan
                    db.guardar_usuarios(); st.rerun()

            with col_u2:
                st.markdown("#### ✏️ Modificar Cuenta Existente")
                usr_editar = st.selectbox("Usuario a Modificar:", ops_usuarios, key="u_editar")
                nuevo_rol = st.selectbox("Cambiar Rol:", [('admin_tec', 'Admin Técnico / Socio'), ('usuario', 'Cliente')], format_func=lambda x: x[1])
                nueva_pass = st.text_input("Nueva Contraseña (dejar en blanco si no cambia):", type="password")
                
                c_btn1, c_btn2 = st.columns(2)
                with c_btn1:
                    if st.button("🔴 Dar Baja", use_container_width=True):
                        db.usuarios[usr_editar]["activo"] = False; db.guardar_usuarios(); st.rerun()
                with c_btn2:
                    if st.button("🟢 Activar", use_container_width=True):
                        db.usuarios[usr_editar]["activo"] = True; db.guardar_usuarios(); st.rerun()
                        
                if st.button("💾 Guardar Rol/Pass", use_container_width=True):
                    if nueva_pass: db.usuarios[usr_editar]["pass"] = nueva_pass
                    db.usuarios[usr_editar]["rol"] = nuevo_rol[0]
                    db.guardar_usuarios(); st.rerun()
                    
                if st.button("🔓 Forzar Cierre Sesiones", use_container_width=True):
                    db.usuarios[usr_editar]["sesiones"] = 0
                    db.guardar_usuarios(); st.rerun()

            with col_u3:
                st.markdown("#### ➕ Registrar Nuevo Usuario")
                with st.form("form_nuevo_usr"):
                    new_uid = st.text_input("ID de Usuario:")
                    new_pwd = st.text_input("Contraseña:")
                    new_rol = st.selectbox("Rol:", [('admin_tec', 'Socio'), ('usuario', 'Cliente')], format_func=lambda x: x[1])
                    if st.form_submit_button("Crear Perfil"):
                        if not new_uid or not new_pwd or new_uid in db.usuarios:
                            st.error("⚠️ Datos inválidos o usuario ya existe.")
                        else:
                            db.usuarios[new_uid] = {"pass": new_pwd, "rol": new_rol[0], "activo": True, "sesiones": 0, "ver_ganancia": False, "ganancia_pct": 25.0, "contador_folios": 1}
                            db.guardar_usuarios(); st.rerun()
