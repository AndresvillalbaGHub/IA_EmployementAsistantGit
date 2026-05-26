import streamlit as st # type: ignore
import pandas as pd # type: ignore
import os
import re
import shutil
import streamlit.components.v1 as components
from AsistenteVerificacion import AgenteInteligente
import subprocess 
import sys
import ollama
import time
import hashlib
import base64
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright
import json
import edge_tts
import asyncio

# --- CONFIGURACIÓN DE RUTAS ---
CARPETA_RESULTADOS = "resultados"
CARPETA_POSTULAR = "por_postular" # Ajustado a tu estructura local
CARPETA_ENVIADAS = "enviadas" 
MODELO_IA = "gemma4:31b-cloud"
CARPETA_VACANTES = "vacantes"


# --- CONFIGURACIÓN DE INTERFAZ HMI ---
st.set_page_config(
    page_title="HMI Ingenia-Match 5.5", 
    layout="wide", 
    initial_sidebar_state="expanded" 
)

# --- ESTILOS DE CONSOLA INDUSTRIAL BLINDADOS ---
st.markdown("""
    <style>
    .stTextArea textarea {
        color: #00FF00 !important; 
        background-color: #1E1E1E !important; 
        font-family: 'Courier New', monospace !important;
        border: 1px solid #333 !important;
    }
    .stTextArea textarea:disabled {
        color: #00FF00 !important;
        -webkit-text-fill-color: #00FF00 !important;
        background-color: #0A0A0A !important; 
        opacity: 1 !important;
        cursor: not-allowed;
    }
    [data-testid="stMetricValue"] { color: #0e1117; font-weight: bold; }
    .block-container { padding-top: 1.5rem; }
    .stButton button { width: 100%; border-radius: 8px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZACIÓN DE COMPONENTES ---
revisor = AgenteInteligente()

for p in [CARPETA_POSTULAR, CARPETA_ENVIADAS]:
    os.makedirs(p, exist_ok=True)

# --- MÁQUINA DE ESTADOS ---
if 'modo_barrido' not in st.session_state: st.session_state.modo_barrido = False
if 'indice_barrido' not in st.session_state: st.session_state.indice_barrido = 0
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'last_folder' not in st.session_state: st.session_state.last_folder = ""
if 'pitch_text' not in st.session_state: st.session_state.pitch_text = ""
if 'manos_libres' not in st.session_state: st.session_state.manos_libres = False
if 'ultimo_audio_id' not in st.session_state: st.session_state.ultimo_audio_id = ""

# --- FUNCIONES DE SOPORTE TÉCNICO ---

def ejecutar_briefing_neuronal(texto):
    """Motor de voz neuronal compatible con Safari/iPadOS"""
    async def generar():
        VOZ = "es-CO-GonzaloNeural" 
        texto_limpio = re.sub(r'[*#`-]', '', texto).replace('\n', ' ')
        communicate = edge_tts.Communicate(texto_limpio, VOZ)
        tmp_file = f"tmp_audio_{int(time.time())}.mp3"
        await communicate.save(tmp_file)
        with open(tmp_file, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        if os.path.exists(tmp_file): os.remove(tmp_file)
        return b64
    try:
        b64_audio = asyncio.run(generar())
        audio_html = f'<audio autoplay style="display:none;"><source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3"></audio>'
        components.html(audio_html, height=0)
    except Exception as e:
        st.error(f"Falla en bus de audio: {e}")

def adaptar_cv_ingles(html_original):
    """Transcreación técnica con limpieza de bloques Markdown"""
    prompt = f"""
    [ROL: EXPERTO EN RECLUTAMIENTO TÉCNICO INTERNACIONAL]
    Traduce y adapta el siguiente CV de Español a Inglés (USA/UK Standard).
    REGLAS:
    1. NO uses traducción literal. Usa terminología de ingeniería (Ladder Logic, Edge AI, SCADA).
    2. MANTÉN TODA LA ESTRUCTURA HTML y clases de Tailwind.
    3. Devuelve ÚNICAMENTE el código HTML. No añadas bloques de Markdown (```html).
    4. no inventes información que no esté en el original, pero adapta términos técnicos al inglés.
    HTML ORIGINAL: {html_original}
    """
    try:
        res = ollama.chat(model=MODELO_IA, messages=[{'role': 'user', 'content': prompt}])
        contenido = res['message']['content']
        if "```html" in contenido:
            contenido = contenido.split("```html")[1].split("```")[0]
        elif "```" in contenido:
            contenido = contenido.split("```")[1].split("```")[0]
        return contenido.strip()
    except Exception as e:
        return f"Error en transcreación: {e}"

def procesar_vacante_con_vision(img_file):
    """Envía la imagen directamente al modelo multimodal para análisis semántico"""
    try:
        buffered = BytesIO()
        img = Image.open(img_file)
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt_vision = """
        [ROL: INGENIERO DE SISTEMAS DE VISIÓN]
        Analiza esta imagen de una vacante de empleo de forma exhaustiva.
        
        SALIDA REQUERIDA (ESTRICTA):
        TITULO: [Nombre del puesto]
        EMPRESA: [Empresa]
        REQUISITOS TÉCNICOS: [Habilidades, software, herramientas]
        DATOS DE CONTACTO: [Extrae emails, teléfonos o nombres de reclutadores. Si no hay, pon "No detectado"]
        DESCRIPCION: [Resumen de funciones]
        """

        res = ollama.chat(
            model=MODELO_IA,
            messages=[{
                'role': 'user',
                'content': prompt_vision,
                'images': [img_str]
            }],
            options={
                    'num_predict': 1000,
                }
        )
        return res['message']['content']
    except Exception as e:
        return f"Error en el procesamiento de visión: {e}"
    
def generar_pdf_playwright(ruta_html, ruta_pdf):
    """Renderizado Chromium A3 de alta fidelidad"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        path_abs = f"file://{os.path.abspath(ruta_html)}"
        page.goto(path_abs)
        page.wait_for_load_state("networkidle")
        page.pdf(
            path=ruta_pdf,
            format="A3",
            print_background=True,
            margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"}
        )
        browser.close()

def filtrar_link_real(texto):
    enlaces = re.findall(r'(https?://[^\s\'"<>\[\]]+)', texto)
    blacklist = ['cdn.', 'tailwindcss', 'fonts.', 'scripts']
    for link in enlaces:
        link_limpio = re.sub(r'[^a-zA-Z0-9/&=?%\-_]+$', '', link)
        if not any(ruido in link_limpio.lower() for ruido in blacklist):
            return link_limpio
    return None

def monitor_log_envivo(ruta_log="ejecucion_asistente.log", n=15):
    """Sintoniza las últimas n líneas del log de ejecución"""
    if os.path.exists(ruta_log):
        try:
            with open(ruta_log, "r", encoding="utf-8", errors="replace") as f:
                lineas = f.readlines()
                return "".join(lineas[-n:])
        except Exception as e:
            return f"Error de lectura en bus de datos: {e}"
    return "Esperando señal de proceso... (Archivo log no detectado)"

def cargar_datos_hmi(carpeta_objetivo):
    datos = []
    path_base = os.path.join(CARPETA_RESULTADOS, carpeta_objetivo)
    if not os.path.exists(path_base): return pd.DataFrame(columns=["Empresa", "Score", "Origen", "Carpeta", "Contenido", "Link"])
    for sub in os.listdir(path_base):
        r_sub = os.path.join(path_base, sub)
        if os.path.isdir(r_sub):
            archivos = os.listdir(r_sub)
            f_an = next((f for f in archivos if f.lower().startswith("analisis_")), None)
            
            # --- CORRECCIÓN DE FILTRO: Añadimos soporte para el prefijo RES_ ---
            f_va = next((f for f in archivos if (f.upper().startswith(("GJ", "SPE", "SEP", "RES_"))) and f.endswith(".txt") and "CV" not in f.upper()), None)
            
            if f_va:
                try:
                    score = 0
                    cont_an = "⚠️ Sin reporte."
                    if f_an:
                        with open(os.path.join(r_sub, f_an), "r", encoding="utf-8", errors="replace") as fa:
                            cont_an = fa.read()
                        score_m = re.search(r"SCORE\s*FINAL.*?(\d+)", cont_an, re.I)
                        score = int(score_m.group(1)) if score_m else 0
                    with open(os.path.join(r_sub, f_va), "r", encoding="utf-8", errors="replace") as fv:
                        cont_va = fv.read()
                    
                    # Identificación visual en el dataframe del HMI
                    if "RES_" in f_va.upper():
                        origen = "💎 RESCATE"
                    else:
                        origen = "🌍 SEP/GJ" if ("GJ" in f_va.upper() or "SEP" in f_va.upper()) else "🇨🇴 SPE"
                        
                    datos.append({"Empresa": sub[:25], "Score": score, "Origen": origen, "Carpeta": r_sub, "Contenido": cont_an, "Link": filtrar_link_real(cont_va)})
                except: continue 
    return pd.DataFrame(datos)

# --- NAVEGACIÓN ---
with st.sidebar:
    st.title("🤖 Estación Central")
    seccion = st.radio("Módulo:", ["🔍 Explorador", "🎯 Postulación"])
    st.divider()

# --- MÓDULO DE INGESTA MULTIMODAL MEJORADO (HMI 6.1) ---
with st.sidebar:
    st.divider()
    st.subheader("📸 Ingesta de Alta Fidelidad")
    
    with st.container(border=True):
        img_captura = st.file_uploader("Subir pantallazo (PNG/JPG):", type=["png", "jpg", "jpeg"])
        url_manual_v = st.text_input("🔗 Link de la vacante (Opcional):", placeholder="https://...")
        
        if img_captura:
            st.image(img_captura, caption="Previsualización de captura", use_container_width=True)
            
            if st.button("🚀 INYECTAR PROYECTO", type="primary"):
                with st.spinner("Analizando imagen y consolidando datos..."):
                    try:
                        resultado_ia = procesar_vacante_con_vision(img_captura)
                        link_final = url_manual_v if url_manual_v.strip() != "" else "No proporcionado por el usuario"
                        id_v = hashlib.md5(img_captura.getvalue()).hexdigest()[:8]
                        nombre_f = f"{CARPETA_VACANTES}/GJ_MANUAL_VIS_{id_v}.txt"
                        
                        with open(nombre_f, "w", encoding="utf-8") as f:
                            f.write(f"--- INYECCIÓN MULTIMODAL (HMI 6.1) ---\n")
                            f.write(f"LINK DE ORIGEN: {link_final}\n")
                            f.write(f"ID DE CAPTURA: {id_v}\n")
                            f.write(f"{'='*40}\n\n")
                            f.write(resultado_ia)
                        
                        st.success("✅ Inyección completada.")
                        if url_manual_v.strip() == "":
                            st.info("ℹ️ Procesado sin link de referencia.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Falla en el bus de inyección: {e}")

# --- SECCIÓN 1: EXPLORADOR (Monitor de Señales y Barrido Táctico) ---
if seccion == "🔍 Explorador":
    col_izq, col_der = st.columns([1, 1])
    
    with col_izq:
        with st.container(border=True):
            st.subheader("🚀 Radar de Vacantes")
            
            if not st.session_state.get('p_activo', False):
                if st.button("🔥 INICIAR BÚSQUEDA", type="primary", use_container_width=True):
                    ruta_log = "ejecucion_asistente.log"
                    log_f = open(ruta_log, "a", encoding="utf-8")
                    log_f.write(f"\n{'='*20}\n[SISTEMA] INICIO: {time.strftime('%Y-%m-%d %H:%M:%S')}\n{'='*20}\n")
                    log_f.flush()

                    subprocess.Popen(
                        [sys.executable, "-u", "EjecutadorAsistente.py"],
                        stdout=log_f,
                        stderr=log_f,
                        start_new_session=True
                    )
                    
                    st.session_state.p_activo = True
                    st.rerun()
            else:
                st.warning("⚙️ Rastreando señales internacionales y nacionales...")
                if st.button("✅ Detener Rastreo", use_container_width=True):
                    st.session_state.p_activo = False
                    st.rerun()

            st.divider()
            with st.expander("📟 Terminal de Proceso (ejecucion_asistente.log)", expanded=st.session_state.get('p_activo', False)):
                log_data = monitor_log_envivo()
                st.code(log_data, language="log")
                if st.button("🛰️ SINCRONIZAR LOGS", use_container_width=True):
                    st.rerun()

        fuente = st.radio("Cámara de Origen:", ["Aceptados", "Rechazados"], horizontal=True)
        df = cargar_datos_hmi("aceptado" if fuente == "Aceptados" else "rechazados")
        
        if not st.session_state.modo_barrido:
            if st.button(f"🚀 INICIAR BARRIDO DE {fuente.upper()}", type="primary", use_container_width=True):
                if not df.empty:
                    st.session_state.modo_barrido = True
                    st.session_state.indice_barrido = 0
                    st.rerun()
        else:
            st.warning(f"🕵️ Barrido en Progreso: {st.session_state.indice_barrido + 1} de {len(df)}")
            if st.button("🛑 DETENER BARRIDO", use_container_width=True):
                st.session_state.modo_barrido = False
                st.rerun()

        if not df.empty:
            sel = st.dataframe(
                df, 
                use_container_width=True, 
                hide_index=True, 
                on_select="rerun", 
                selection_mode="single-row",
                column_config={"Carpeta": None, "Contenido": None, "Link": None}
            )
            if st.session_state.modo_barrido:
                if st.session_state.indice_barrido >= len(df):
                    st.session_state.modo_barrido = False
                    st.session_state.indice_barrido = 0
                    st.rerun()
                v_sel = df.iloc[st.session_state.indice_barrido]
            else:
                v_sel = df.iloc[sel.selection.rows[0]] if sel.selection.rows else None
        else:
            v_sel = None
            st.info(f"Bandeja de {fuente} sin señales detectadas.")

    with col_der:
        if v_sel is not None:
            if st.session_state.last_folder != v_sel['Carpeta']:
                with st.spinner("Sintonizando Auditoría..."):
                    reporte_ia = revisor.analizar_vacante_seleccionada(v_sel['Carpeta'])
                    st.session_state.chat_history = [{"role": "assistant", "content": f"### 📊 Auditoría Técnica: {v_sel['Empresa']}\n\n{reporte_ia}"}]
                    st.session_state.last_folder = v_sel['Carpeta']
            
            # --- PANEL DE CONTROL SUPERIOR (ERGONOMÍA IPAD) ---
            st.subheader(f"🔍 {v_sel['Empresa']}")

            # FILA 1: Controles de Voz
            c_audio_info, c_audio_btn = st.columns([0.7, 0.3])
            with c_audio_info:
                st.session_state.manos_libres = st.toggle("🛰️ MODO MANOS LIBRES", value=st.session_state.manos_libres)
            
            current_id = hashlib.md5(v_sel['Carpeta'].encode()).hexdigest()
            btn_brief = c_audio_btn.button("🎙️ BRIEF", use_container_width=True)

            # FILA 2: Acceso Directo al Enlace
            url_target = v_sel.get('Link')
            if isinstance(url_target, str) and url_target.startswith("http"):
                st.link_button("🌐 ABRIR LINK ORIGINAL", url_target, use_container_width=True)
            else:
                st.info("ℹ️ Sin enlace externo detectable.")

            # FILA 3: Actuadores de Decisión (Aceptar, Descartar, Saltar)
            def avanzar(saltar=False):
                """Lógica de puntero optimizada"""
                if st.session_state.modo_barrido:
                    if saltar:
                        st.session_state.indice_barrido += 1
                    if st.session_state.indice_barrido >= (len(df) - (0 if saltar else 1)):
                        st.session_state.modo_barrido = False
                        st.session_state.indice_barrido = 0
                st.session_state.chat_history, st.session_state.last_folder = [], ""
                st.rerun()

            c1, c2, c3 = st.columns(3)
            with c1:
                if fuente == "Aceptados":
                    if st.button("✅ POSTULAR", type="primary", use_container_width=True):
                        revisor.ejecutar_movimiento(v_sel['Carpeta'], "APROBAR")
                        avanzar(saltar=False)
                else:
                    # --- LAZO DE RESCATE POR PREFIJO DE CONTROL (DIRECCIONAMIENTO SUB-CARPETAS) ---
                    if st.button("💎 RESCATAR", type="primary", use_container_width=True):
                        with st.spinner("Cambiando prefijo y reinyectando señal..."):
                            ruta_carpeta_rechazado = v_sel['Carpeta'] # Ejemplo: resultados/rechazados/NombreVacante_XYZ
                            
                            # CORRECTO: Escaneamos el INTERIOR de la subcarpeta de la vacante seleccionada
                            f_va = next((f for f in os.listdir(ruta_carpeta_rechazado) if f.lower().endswith(".txt") and "cv" not in f.lower() and "analisis" not in f.lower()), None)
                            
                            if f_va:
                                # La ruta de origen real incluye la subcarpeta del proyecto
                                ruta_origen_txt = os.path.join(ruta_carpeta_rechazado, f_va)
                                
                                # Definimos el nuevo Tag de control de rescate
                                nuevo_nombre_txt = f"RES_{f_va}"
                                ruta_destino_txt = os.path.join(CARPETA_VACANTES, nuevo_nombre_txt) # Destino: vacantes/RES_...
                                
                                # Copiamos la señal original a la entrada del radar
                                shutil.copy(ruta_origen_txt, ruta_destino_txt)
                                
                                # Destruimos la subcarpeta completa de rechazados con todo lo que tiene dentro (Txt y Análisis viejo)
                                try:
                                    shutil.rmtree(ruta_carpeta_rechazado)
                                except Exception as e:
                                    st.sidebar.error(f"Aviso de limpieza en disco: {e}")
                                
                                # Ejecutamos el constructor lineal en background
                                subprocess.Popen(
                                    [sys.executable, "-u", "ConstructorCVs.py"],
                                    start_new_session=True
                                )
                                
                                st.success(f"✅ Señal reconfigurada como {nuevo_nombre_txt} e inyectada con éxito.")
                                avanzar(saltar=False)
                            else:
                                st.error("❌ Error de bus: No se encontró el archivo .txt de la vacante dentro de su subcarpeta.")
            with c2:
                if st.button("🗑️ DESCARTAR", use_container_width=True):
                    revisor.ejecutar_movimiento(v_sel['Carpeta'], "DESCARTAR")
                    avanzar(saltar=False)
            with c3:
                if st.button("⏭️ SALTAR", use_container_width=True):
                    avanzar(saltar=True)

            # --- LÓGICA DE DISPARO DE AUDIO (CENTINELA) ---
            if (st.session_state.manos_libres and st.session_state.ultimo_audio_id != current_id) or btn_brief:
                if st.session_state.chat_history:
                    with st.spinner("Sintonizando voz..."):
                        ultimo_analisis = st.session_state.chat_history[0]['content']
                        prompt_voz = f"""
                        [ROL: CONSULTOR SENIOR DE AUTOMATIZACIÓN]
                        Estás comentando una vacante con tu colega Andrés Villalba (Ingeniero Electrónico, GPA 4.6).
                        Tu objetivo es darle un reporte ejecutivo RÁPIDO y NATURAL.

                        REGLAS DE ORO:
                        1. PROHIBICIÓN TOTAL: No empieces con "Hola", "Ingeniero", "Según he revisado", "He analizado" ni "He encontrado". 
                        2. APERTURA DINÁMICA: Empieza directamente con un dato sobre {v_sel['Empresa']}.
                        3. ARGUMENTO TÉCNICO: Menciona por qué su GPA de 4.6 o experiencia en Automatización es clave.
                        4. ESTRUCTURA: Máximo 3 párrafos cortos y fluidos.
                        5. SALIDA LIMPIA: Sin preámbulos robóticos.

                        ANÁLISIS TÉCNICO: {ultimo_analisis[:800]}
                        """
                        res = ollama.chat(model=MODELO_IA, messages=[{'role': 'user', 'content': prompt_voz}])
                        guion_humano = res['message']['content']
                        ejecutar_briefing_neuronal(guion_humano)
                        st.session_state.ultimo_audio_id = current_id

            st.divider()

            # --- ZONA DE CONSULTA Y DETALLE (TABS) ---
            t_ia, t_raw, t_cht = st.tabs(["🧠 Consultoría IA", "📝 Texto Original", "💬 Chat"])
            
            with t_ia:
                st.write("### 🧠 Consultoría de Perfil")
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])
    
            with t_raw:
                st.text_area("Cuerpo del Archivo:", v_sel['Contenido'], height=400, disabled=True)

            with t_cht:
                st.write("### 💬 Interacción Directa consulta")
                if prompt := st.chat_input("Consulta detalles técnicos..."):
                    st.session_state.chat_history.append({"role": "user", "content": prompt})
                    with st.chat_message("user"): 
                        st.write(prompt)
                    
                    with st.chat_message("assistant"):
                        with st.spinner("Procesando señal..."):
                            contexto_ia = st.session_state.chat_history.copy()
                            if st.session_state.get('manos_libres', False):
                                contexto_ia[-1]['content'] += " (REGLA: Responde de forma técnica, directa y muy breve. Máximo 2 párrafos. Sin saludos ni preámbulos. Ve al grano)."
                            
                            resp = revisor.conversar(contexto_ia)
                            st.write(resp)
                            st.session_state.chat_history.append({"role": "assistant", "content": resp})
                            
                            if st.session_state.get('manos_libres', False):
                                ejecutar_briefing_neuronal(resp)
        else:
            st.info("Seleccione una señal en el radar para iniciar la auditoría.")

# --- SECCIÓN 2: POSTULACIÓN (Sincronización ES/EN) ---
elif seccion == "🎯 Postulación":
    st.title("🎯 Centro de Despacho Estratégico")
    carpetas_v = [d for d in os.listdir(CARPETA_POSTULAR) if os.path.isdir(os.path.join(CARPETA_POSTULAR, d))]

    if not carpetas_v:
        st.info("Cola vacía.")
    else:
        v_activa = st.selectbox("Proyecto Activo:", carpetas_v, index=0)
        ruta_full = os.path.join(CARPETA_POSTULAR, v_activa)
        
        f_es = next((f for f in os.listdir(ruta_full) if f.endswith(".html") and "_EN" not in f), None)
        f_en = next((f for f in os.listdir(ruta_full) if f.endswith("_EN.html")), None)

        st.write("### 🌐 Configuración de Salida")
        op_idioma = ["Español"]
        if f_en: op_idioma.append("Inglés")
        idioma_sel = st.radio("Idioma del CV:", op_idioma, horizontal=True)

        target_html = f_es if idioma_sel == "Español" else f_en
        label_id = "ES" if idioma_sel == "Español" else "EN"
        ruta_h_target = os.path.join(ruta_full, target_html)
        ruta_p_target = ruta_h_target.replace(".html", ".pdf")

        col_v, col_p = st.columns(2)
        with col_v:
            st.subheader("📝 Vacante")
            f_txt = next((f for f in os.listdir(ruta_full) if f.endswith(".txt") and "CV" not in f.upper() and "ANALISIS" not in f.upper()), None)
            if f_txt:
                with open(os.path.join(ruta_full, f_txt), "r", encoding="utf-8") as f:
                    info_v = f.read()
                st.text_area("Descripción (Protegida):", info_v, height=200, disabled=True)
                lk = filtrar_link_real(info_v)
                if lk: st.link_button("🌐 IR A POSTULACIÓN", lk, type="primary")

        with col_p:
            st.subheader(f"✨ Pitch ({idioma_sel})")
            if st.button(f"🪄 Generar en {idioma_sel}"):
                lang = "English" if idioma_sel == "Inglés" else "Español"
                res = ollama.chat(model=MODELO_IA, messages=[{'role': 'user', 'content': f"Pitch corto en {lang} para: {info_v[:600]}"}])
                st.session_state.pitch_text = res['message']['content']
            st.text_area("Copia Segura:", st.session_state.pitch_text, height=200, disabled=True)

        st.divider()
        st.subheader(f"📄 Gestión CV: Versión {label_id}")
        if st.button(f"🛡️ RENDERIZAR PDF MAESTRO ({label_id})", type="primary"):
            with st.spinner("Chromium en proceso..."):
                generar_pdf_playwright(ruta_h_target, ruta_p_target)
                st.success("Listo.")

        c_d, c_e, c_x = st.columns(3)
        with c_d:
            if os.path.exists(ruta_p_target):
                with open(ruta_p_target, "rb") as fp:
                    st.download_button(f"📥 DESCARGAR PDF ({label_id})", fp, f"CV_Villalba_{label_id}.pdf", "application/pdf")
            else: st.warning("Genere PDF.")
        with c_e:
            if st.button("🏁 ENVIADA"): shutil.move(ruta_full, os.path.join(CARPETA_ENVIADAS, v_activa)); st.rerun()
        with c_x:
            if st.button("🗑️ ELIMINAR"): shutil.rmtree(ruta_full); st.rerun()

        if not f_en:
            st.divider()
            if st.button("🇺🇸 TRANSCREAR A INGLÉS (NATIVE PRO)"):
                with open(os.path.join(ruta_full, f_es), "r", encoding="utf-8") as f:
                    html_en = adaptar_cv_ingles(f.read())
                with open(os.path.join(ruta_full, f_es.replace(".html", "_EN.html")), "w", encoding="utf-8") as f:
                    f.write(html_en)
                st.success("Creado."); st.rerun()

        with st.expander(f"👁️ Previsualización {idioma_sel}", expanded=True):
            with open(ruta_h_target, "r", encoding="utf-8") as f:
                components.html(f.read(), height=800, scrolling=True)

# --- MÉTRICAS ---
st.divider()
m1, m2 = st.columns(2)
m1.metric("Perfil", "Andrés Villalba | GPA 4.6")
m2.metric("Proyectos en Cola", len(carpetas_v) if 'carpetas_v' in locals() else 0)