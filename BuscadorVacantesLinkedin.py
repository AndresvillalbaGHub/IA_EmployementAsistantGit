import asyncio
import random
import os
import hashlib
import re
from playwright.async_api import async_playwright
import ollama


# --- CONFIGURACIÓN ---
MAX_VACANTES_POR_QUERY = 5 # Para evitar saturar el sistema con demasiadas vacantes de una sola búsqueda 
CARPETA_VACANTES = "vacantes"
HISTORIAL_LOG = "historial_vacantes.log"
MODELO_CLOUD = "gemma4:31b-cloud" # El que ya te funcionó


QUERIES = [
    "ingeniero de automatizacion",
    "ingeniero electronico",
    "ingeniero de proyectos",
    "ingeniero de control",
    "automatizacion industrial",
    "Ingeniero Electrónico junior",
    "Ingeniero de Automatización",
    "Programador PLC",
    "Ingeniero de Control",
    "Ingeniero de Instrumentación",
    "Ingeniero de Proyectos Eléctricos",
    "Ingeniero de soporte técnico junior" # Excelente para entrar a grandes como ABB o Rockwell

    
]
def auditoria_ia_rapida(titulo, descripcion):

    titulo_limpio = titulo.encode('utf-8', 'ignore').decode('utf-8')
    desc_limpia = descripcion[:500].encode('utf-8', 'ignore').decode('utf-8')
    
    """
    Filtro de Liga: Determina si la vacante es digna de un ingeniero electronico en busqueda de su primer empleo.
    """
    prompt = f"""
    [ROL: RECLUTADOR TÉCNICO SENIOR]
    Evalúa si esta vacante es apta para un Ingeniero Electrónico con Especialización recien egresado (Promedio 4.6), Gran habilidad en Edge AI, Control y Automatización, no seas tan duro ya que estas en busqueda de un primer empleo.
    
    RECHAZA SI:
    - Es 'Senior', 'Lead' o 'Manager' (+5 años exp).
    - Es de Ventas o Mantenimiento básico.
    
    ACEPTA SI:
    - Es 'Junior', 'Entry Level' o 'New Grad',' recien egresado'.
    - Se enfoca en: Automatizacion Industrial,Electronica,Robotica,Embedded, Firmware, C++, Python, Edge AI, Robotics, PLC o programacion de sistemas IA.
    - Menos de 3 años de experiencia o no menciona años pero si las habilidades clave.
    - consideras que es una buena oportunidad para alguien con su perfil, aunque no sea 100% perfecto.
    

    Querty Usada: {titulo}
    DESCRIPCIÓN CORTA: {descripcion[:600]}

    Responde únicamente con la palabra: 'APTO' o 'RECHAZADO'.
    """
    try:
        # Aprovechamos la velocidad de tu modelo 31B en la nube
        res = ollama.chat(model=MODELO_CLOUD, messages=[{'role': 'user', 'content': prompt}])
        veredicto = res['message']['content'].strip().upper()
        return "APTO" in veredicto
    except:
        return True # En caso de error, dejamos pasar para no perder la oportunidad
    
def cargar_historial():
    if not os.path.exists(HISTORIAL_LOG): return set()
    with open(HISTORIAL_LOG, "r") as f:
        return set(line.strip() for line in f)

def guardar_en_historial(job_id):
    with open(HISTORIAL_LOG, "a") as f:
        f.write(f"{job_id}\n")

def limpiar_texto_seguro(texto):
    if not texto: return ""
    return texto.encode('utf-8', 'ignore').decode('utf-8')

async def ejecutar_sonda_limitada():
    if not os.path.exists(CARPETA_VACANTES): os.makedirs(CARPETA_VACANTES)
    historial = cargar_historial()
    
    async with async_playwright() as p:
        print("[*] Iniciando Buscador con Corrector de Links en la Pi 5...")
        # Headless=False para que puedas supervisar si lo deseas
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        total_sesion = 0

        for q in QUERIES:
            print(f"\n[>] Buscando: '{q}'")
            nuevas_este_query = 0
            
            try:
                await page.goto("https://www.buscadordeempleo.gov.co/#/home", wait_until="load", timeout=60000)
                
                selector_input = "input[type='text']"
                await page.wait_for_selector(selector_input, state="visible")
                await page.fill(selector_input, q)
                await page.press(selector_input, "Enter")
                
                await asyncio.sleep(12) 

                ofertas = await page.query_selector_all("div[class*='card'], .vacante-item, article")
                
                for oferta in ofertas:
                    if nuevas_este_query >= MAX_VACANTES_POR_QUERY:
                        print(f"   [!] Límite de {MAX_VACANTES_POR_QUERY} alcanzado. Saltando...")
                        break

                    texto_raw = await oferta.inner_text()
                    
                    # Generar ID único para el log
                    job_id = hashlib.md5(texto_raw[:200].encode()).hexdigest()


                    if job_id in historial:
                        continue 

                    # Filtro técnico
                    keywords = ["ingeniero", "junior", "pasantia", "profesional", "egresado", "automatización", "control", "electrónico", "industrial", "plc", "controllogix", "instrumentación", "hart", "python", "opencv", "yolo", "automation", "engineer", "electronic", "control"]
                    if any(k in texto_raw.lower() for k in keywords):

                        # --- CAPA 2: INTELIGENCIA ARTIFICIAL (Gemma 4) ---
                        descripcion = texto_raw[:600]  # Limitar para la IA
                        if not auditoria_ia_rapida(q, descripcion):
                            print(f"   [X] Rechazado por IA: {q[:30]}...")
                            continue
                        
                        # --- EXTRACTOR Y CORRECTOR DE LINK ---
                        link_element = await oferta.query_selector("a")
                        link_href = await link_element.get_attribute("href") if link_element else "N/A"
                        
                        if link_href.startswith("/"):
                            link_href = "https://www.buscadordeempleo.gov.co" + link_href

                        link_final = link_href # Por defecto el original

                        # Rutina del Corrector: Entramos al link para obtener la URL real
                        if link_href != "N/A":
                            print(f"      [.] Corrigiendo link de transición...")
                            nueva_pestana = await context.new_page()
                            try:
                                # Navegamos y esperamos a que la URL se estabilice
                                await nueva_pestana.goto(link_href, wait_until="load", timeout=45000)
                                await asyncio.sleep(2)
                                link_final = nueva_pestana.url # Esta es la URL de Computrabajo/Magneto final
                            except Exception:
                                print("      [!] No se pudo resolver el link final, se usará el original.")
                            finally:
                                await nueva_pestana.close()

                        # Extraer nombre de la empresa del texto
                        match_empresa = re.search(r"EMPRESA:\s*(.+?)(?:\n|$)", texto_raw, re.IGNORECASE)
                        nombre_empresa = match_empresa.group(1).strip() if match_empresa else "Empresa_Desconocida"
                        
                        # Limpiar el nombre para que sea válido como nombre de archivo
                        nombre_empresa = re.sub(r'[<>:"/\\|?*]', '_', nombre_empresa)
                        nombre_empresa = nombre_empresa.replace(" ", "_")[:20]  # Limitar longitud
                       
                        # Guardado con toda la información (texto_raw) y el link corregido
                        nombre_archivo = f"{CARPETA_VACANTES}/SPE_{q}_{job_id[:8]}.txt"
                        with open(nombre_archivo, "w", encoding="utf-8") as f:
                            f.write(f"--- ORIGEN: SPE COLOMBIA ---\n")
                            f.write(f"--- LINK REAL/CORREGIDO: {link_final} ---\n")
                            f.write(f"--- CATEGORIA: {q} ---\n\n")
                            f.write(texto_raw)
                        
                        guardar_en_historial(job_id)
                        historial.add(job_id)
                        nuevas_este_query += 1
                        total_sesion += 1
                        print(f"   [+] {nuevas_este_query}/{MAX_VACANTES_POR_QUERY} guardada con link corregido.")

            except Exception as e:
                print(f"   [!] Error en query '{q}': {e}")
                continue

        await browser.close()
        print(f"\n{'='*40}\nSESIÓN FINALIZADA: {total_sesion} vacantes listas.\n{'='*40}")

if __name__ == "__main__":
    asyncio.run(ejecutar_sonda_limitada())