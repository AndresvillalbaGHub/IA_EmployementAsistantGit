import asyncio
import random
import os
import hashlib
import re
import sys
import io
from playwright.async_api import async_playwright
import ollama

# --- CONFIGURACIÓN DE SISTEMA ---
# Forzamos UTF-8 para evitar errores de codificación en la Raspberry Pi 5
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

MAX_VACANTES_POR_QUERY = 2 # Para evitar saturar el sistema con demasiadas vacantes de una sola búsqueda 
CARPETA_VACANTES = "vacantes"
HISTORIAL_LOG = "historial_vacantes.log"
MODELO_CLOUD = "gemma4:31b-cloud"

# Queries optimizadas para el mercado de automatización en Colombia
QUERIES = [
    "Ingeniero de Automatización",
    "Ingeniero Electrónico junior",
    "Programador PLC",
    "Ingeniero de Control",
    "Automatización Industrial",
    "Ingeniero de Instrumentación",
    "Ingeniero de soporte técnico junior"
]

def auditoria_ia_rapida(titulo, descripcion):
    """
    Filtro de Inteligencia: Evalúa la vacante según el perfil de Ingeniero especialista (GPA 4.6).
    """
    prompt = f"""
    [ROL: RECLUTADOR TÉCNICO SENIOR]
    Evalúa si esta vacante es apta para un Ingeniero Electrónico Especialista en Automatización recién egresado (Promedio 4.6). 
    Perfil: Experto en Edge AI, Control, PLC (ControlLogix) y Python. Buscamos primer empleo profesional.
    
    RECHAZA SI:
    - Es 'Senior', 'Lead' o requiere +5 años de experiencia.
    - Es puramente ventas o mantenimiento eléctrico básico (electricista).
    
    ACEPTA SI:
    - Es 'Junior', 'Entry Level', 'Profesional I' o 'Recién egresado'.
    - Incluye: PLC, SCADA, Instrumentación, Visión Artificial, C++, o Control Industrial.
    - Es una buena oportunidad de crecimiento técnico.

    TÍTULO: {titulo}
    DESCRIPCIÓN: {descripcion[:700]}

    Responde ÚNICAMENTE con: 'APTO' o 'RECHAZADO'.
    """
    try:
        res = ollama.chat(model=MODELO_CLOUD, messages=[{'role': 'user', 'content': prompt}])
        return "APTO" in res['message']['content'].strip().upper()
    except:
        return True # Por seguridad ante fallos de red

def cargar_historial():
    if not os.path.exists(HISTORIAL_LOG): return set()
    with open(HISTORIAL_LOG, "r") as f:
        return set(line.strip() for line in f)

def guardar_en_historial(job_id):
    with open(HISTORIAL_LOG, "a") as f:
        f.write(f"{job_id}\n")

async def ejecutar_radar_computrabajo():
    if not os.path.exists(CARPETA_VACANTES): os.makedirs(CARPETA_VACANTES)
    historial = cargar_historial()
    
    async with async_playwright() as p:
        print("[*] Iniciando Radar Computrabajo Stealth en Pi 5...")
        browser = await p.chromium.launch(headless=True)
        # User-Agent real para evitar ser detectado como bot
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()

        total_sesion = 0

        for q in QUERIES:
            print(f"\n[>] Buscando en Computrabajo: '{q}'")
            nuevas_este_query = 0
            
            try:
                # Vamos directo a Computrabajo Colombia
                await page.goto("https://www.computrabajo.com.co/", wait_until="networkidle")
                
                # Selector de búsqueda de Computrabajo
                search_input = "#prof-cat-search-input"
                await page.wait_for_selector(search_input)
                await page.fill(search_input, q)
                await page.press(search_input, "Enter")
                
                # Espera táctica para carga dinámica de resultados
                await asyncio.sleep(random.uniform(5, 8))

                # Localizamos los contenedores de ofertas (articles con clase box_offer)
                ofertas = await page.query_selector_all("article.box_offer")
                
                for oferta in ofertas:
                    if nuevas_este_query >= MAX_VACANTES_POR_QUERY: break

                    # Extraemos link y título del elemento <a> con clase js-o-link
                    link_el = await oferta.query_selector("a.js-o-link")
                    if not link_el: continue
                    
                    titulo = await link_el.inner_text()
                    href = await link_el.get_attribute("href")
                    link_final = f"https://www.computrabajo.com.co{href}" if href.startswith("/") else href

                    # Generar ID único basado en el link para evitar duplicados
                    job_id = hashlib.md5(link_final.encode()).hexdigest()
                    if job_id in historial: continue

                    # Obtenemos un snippet de la descripción inicial
                    snippet_el = await oferta.query_selector("p.fs16")
                    descripcion_breve = await snippet_el.inner_text() if snippet_el else ""

                    # --- CAPA DE INTELIGENCIA (IA) ---
                    if not auditoria_ia_rapida(titulo, descripcion_breve):
                        print(f"   [X] Rechazada por IA: {titulo[:30]}")
                        continue

                    # --- EXTRACCIÓN PROFUNDA (Entrar a la vacante) ---
                    print(f"      [.] Extrayendo detalles técnicos...")
                    detalle_page = await context.new_page()
                    try:
                        await detalle_page.goto(link_final, wait_until="domcontentloaded", timeout=45000)
                        await asyncio.sleep(2)
                        # Capturamos toda la descripción detallada
                        desc_completa = await detalle_page.inner_text("body")
                        
                        # Extraer empresa (Computrabajo usa breadcrumbs o clases específicas)
                        empresa_el = await detalle_page.query_selector("a.js-o-link-fc")
                        nombre_empresa = await empresa_el.inner_text() if empresa_el else "Empresa_Oculta"
                        nombre_empresa = re.sub(r'[^a-zA-Z0-9]', '_', nombre_empresa)[:15]

                        # Guardado del archivo normalizado
                        nombre_archivo = f"{CARPETA_VACANTES}/SPE_{nombre_empresa}_{job_id[:8]}.txt"
                        with open(nombre_archivo, "w", encoding="utf-8") as f:
                            f.write(f"TITULO: {titulo}\n")
                            f.write(f"EMPRESA: {nombre_empresa}\n")
                            f.write(f"LINK: {link_final}\n")
                            f.write(f"ORIGEN: COMPUTRABAJO COLOMBIA\n")
                            f.write(f"\n--- DESCRIPCION DETALLADA ---\n{desc_completa}")

                        guardar_en_historial(job_id)
                        historial.add(job_id)
                        nuevas_este_query += 1
                        total_sesion += 1
                        print(f"   [+] {nuevas_este_query}/{MAX_VACANTES_POR_QUERY} Inyectada: {titulo[:35]}")
                    except Exception as e:
                        print(f"      [!] Error al abrir detalle: {e}")
                    finally:
                        await detalle_page.close()

            except Exception as e:
                print(f"   [!] Error en query '{q}': {e}")
                continue

        await browser.close()
        print(f"\n[!] Radar completado. {total_sesion} señales nacionales capturadas.")

if __name__ == "__main__":
    asyncio.run(ejecutar_radar_computrabajo())