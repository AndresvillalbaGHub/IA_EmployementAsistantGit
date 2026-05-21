import requests
import json
import os
import time
import re
import ollama  
import sys
import io
from dotenv import load_dotenv

load_dotenv()

# Forzamos la salida de sistema a UTF-8 para evitar errores con guiones especiales
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CONFIGURACIÓN ---
API_KEY = os.getenv("SERPAPI_KEY") # llave de SerpAPI (Google Jobs)
CARPETA_VACANTES = "vacantes"
HISTORIAL_IDS = "historial_vacantes.log"
MINIMO_VACANTES = 5 # Subimos un poco el cupo para Europa
MODELO_CLOUD = "gemma4:31b-cloud"

# --- LISTA DE REGIONES EUROPEAS CLAVE ---
# Usamos 'gl' para decirle a Google desde qué país estamos "buscando"
REGIONES = [
    {"loc": "United States", "gl": "us"}, # Mercado principal
    {"loc": "United Kingdom", "gl": "uk"}, # Hub tecnológico en Europa
    {"loc": "Europe", "gl": "us"}          # Búsqueda continental desde motor global
]

def limpiar_texto_seguro(texto):
    if not texto: return ""
    # Normaliza a UTF-8 y elimina caracteres que no pertenezcan a la codificación
    return str(texto).encode('utf-8', 'ignore').decode('utf-8')

def auditoria_ia_rapida(titulo, descripcion):
    """
    Filtro de Liga: Evalúa la vacante con el perfil de Ingeniero 4.6 GPA.
    """
    prompt = f"""
    [ROL: RECLUTADOR TÉCNICO SENIOR]
    Evalúa si esta vacante es apta para un Ingeniero Electrónico/Automatización (GPA 4.6).
    Perfil: Edge AI, Control, PLC, Python, Embedded.
    
    RECHAZA SI:
    - Nivel Técnico/Electricista o Senior/Lead (+5 años).
    - Presencial fuera de Colombia.
    
    ACEPTA SI:
    - Junior, Entry Level, Graduate o No especifica pero pide habilidades clave.
    - Remoto 100%.

    VACANTE: {titulo}
    DESCRIPCIÓN: {descripcion[:600]}
    Responde: 'APTO' o 'RECHAZADO'.
    """
    try:
        res = ollama.chat(model=MODELO_CLOUD, messages=[{'role': 'user', 'content': prompt}])
        return "APTO" in res['message']['content'].strip().upper()
    except:
        return True

def ejecutar_explorador_inteligente():
    if not os.path.exists(CARPETA_VACANTES): os.makedirs(CARPETA_VACANTES)
    historial = set()
    if os.path.exists(HISTORIAL_IDS):
        with open(HISTORIAL_IDS, "r") as f:
            historial = set(line.strip() for line in f)

    QUERIES = [
        "Embedded Engineer 'work from home'",
        "Junior Automation Engineer remote",
        "PLC Programmer 'remote'",
        "Edge AI Python Engineer junior",
        "Firmware Developer telecommute",
        "Control Systems Engineer graduate remote",
        # Wildcard para descubrimiento (Mandato de Diversidad)
        "Renewable Energy Systems Engineer remote" 
    ]

    total_nuevas = 0
    print(f"[*] INICIANDO BÚSQUEDA EURO-GLOBAL (Objetivo: {MINIMO_VACANTES})", flush=True)

    # Rotación de Regiones y Queries
    for region in REGIONES:
        if total_nuevas >= MINIMO_VACANTES: break
        
        for q_base in QUERIES:
            if total_nuevas >= MINIMO_VACANTES: break
            
            q_actual = f"{q_base} in {region['loc']}"
            print(f"\n[>] Explorando {region['loc']} ({region['gl']}): {q_base}...", flush=True)
            
            params = {
                "engine": "google_jobs",
                "q": q_base,
                "gl": region['gl'], # El código de país (de, nl, es) es el filtro real
                "hl": "en",         # Buscamos descripciones en inglés
                "api_key": API_KEY
                # Nota: Eliminamos 'location' y 'remote:true' para que no choquen con 'gl'
            }

            try:
                res = requests.get("https://serpapi.com/search", params=params, timeout=15)
                jobs = res.json().get("jobs_results", [])

                for job in jobs:
                    if total_nuevas >= MINIMO_VACANTES: break
                    
                    job_id = job.get("job_id")
                    titulo = job.get("title", "")
                    
                    if job_id in historial: continue

                    # Filtro programático
                    prohibidas = ["technician", "electrician", "senior", "lead", "manager", "sales"]
                    if any(p in titulo.lower() for p in prohibidas): continue

                    # Auditoría IA
                    descripcion = job.get("description", "")
                    if not auditoria_ia_rapida(titulo, descripcion): continue

                    # Datos y Guardado
                    empresa = job.get("company_name", "Anonima")
                    opciones = job.get("apply_options", [])
                    link = opciones[0].get("link", "N/A") if opciones else "N/A"
                    empresa_fs = re.sub(r'[^a-zA-Z0-9]', '', empresa)[:12]
                    
                    # --- CAMBIO DE PREFIJO A 'GJ' PARA EL HMI ---
                    nombre_archivo = f"{CARPETA_VACANTES}/GJ_{empresa_fs}_{job_id[:6]}.txt"
                    
                    with open(nombre_archivo, "w", encoding="utf-8", errors="replace") as f:
                        f.write(f"TITULO: {limpiar_texto_seguro(titulo)}\n")
                        f.write(f"EMPRESA: {limpiar_texto_seguro(empresa)}\n")
                        f.write(f"LINK: {link}\n")
                        f.write(f"\n--- DESCRIPCION ---\n{limpiar_texto_seguro(descripcion)}")
                    
                    with open(HISTORIAL_IDS, "a") as f: f.write(f"{job_id}\n")
                    historial.add(job_id)
                    total_nuevas += 1
                    print(f"   [+] ¡EURO-APTO! {limpiar_texto_seguro(titulo)} @ {limpiar_texto_seguro(empresa)} ({region['loc']})", flush=True)

            except Exception as e:
                print(f"   [!] Error: {e}", flush=True)

    print(f"\n[!] Fin. {total_nuevas} vacantes listas para auditoría en el HMI.", flush=True)

if __name__ == "__main__":
    ejecutar_explorador_inteligente()