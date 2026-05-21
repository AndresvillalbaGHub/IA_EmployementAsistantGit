import os
import re
import csv
import shutil
import json
from datetime import datetime
from master_matcher import CVMatcher  # type: ignore
from AdaptadorCV import CVAdapter # type: ignore

# --- CONFIGURACIÓN ---
UMBRAL_EXITO = 65
DIR_RESULTADOS = "resultados"
DIR_VACANTES = "vacantes"
MASTER_CV_PATH = "master_cv.json"

# Aseguramos carpetas base
if not os.path.exists(DIR_RESULTADOS):
    os.makedirs(DIR_RESULTADOS)

# Crear subcarpetas de aceptado y rechazados
DIR_ACEPTADO = os.path.join(DIR_RESULTADOS, "aceptado")
DIR_RECHAZADO = os.path.join(DIR_RESULTADOS, "rechazados")
os.makedirs(DIR_ACEPTADO, exist_ok=True)
os.makedirs(DIR_RECHAZADO, exist_ok=True)

def limpiar_consola(texto):
    """Evita errores de encoding en la terminal de la Raspberry Pi."""
    return str(texto).encode('ascii', 'ignore').decode('ascii')

def cargar_biblioteca_habilidades():
    """Carga las frases de habilidades desde el JSON unificado."""
    try:
        with open(MASTER_CV_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("biblioteca_habilidades", {})
    except Exception as e:
        print(f"   [!] Error cargando master_cv.json: {e}")
        return {}

def registrar_en_log_maestro(datos_vacante, score):
    archivo_log = "LOG_APLICACIONES.csv"
    existe = os.path.exists(archivo_log)
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with open(archivo_log, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(["Fecha", "Empresa", "Vacante", "Score Match", "URL Postulación"])
        writer.writerow([fecha, datos_vacante['empresa'], datos_vacante['titulo'], f"{score}%", datos_vacante['url']])

def ejecutar_sistema_completo():
    matcher = CVMatcher() 
    escritor = CVAdapter()
    biblioteca = cargar_biblioteca_habilidades()
    
    with open("TemplateCV.html", "r", encoding="utf-8") as f:
        html_base = f.read()

    # Listado de archivos .txt en la carpeta de vacantes
    vacantes = [f for f in os.listdir(DIR_VACANTES) if f.endswith(".txt")]

    for v in vacantes:
        nombre_base = v.replace(".txt", "")
        ruta_vacante_original = os.path.join(DIR_VACANTES, v)

        print(f"\n[*] PROCESANDO: {limpiar_consola(nombre_base)}")

        if not os.path.exists(ruta_vacante_original):
            print(f"   [!] Señal perdida: {v} ya no está en la carpeta. Saltando...")
            continue  # <--- CRÍTICO: Pasa a la siguiente vacante sin ejecutar el resto

        try:
            with open(ruta_vacante_original, "r", encoding="utf-8") as f:
                texto_vacante = f.read()
        except Exception as e:
            print(f"   [!] Error al leer {v}: {e}")
            continue # Si falla la lectura, saltamos
        # --- FASE 1: AUDITORÍA (MODIFICADA) ---
        # Pasamos el texto Y el nombre del archivo (v) para detectar el prefijo (SEP/GJ/etc)
        reporte = matcher.analizar(texto_vacante,v)
        
        # Extraer Datos
        score_match = re.search(r"SCORE\s*FINAL.*?(\d+)", reporte, re.I | re.S)
        score = int(score_match.group(1)) if score_match else 0

        # Determinar carpeta de destino según score
        if score >= UMBRAL_EXITO:
            ruta_carpeta_destino = os.path.join(DIR_ACEPTADO, nombre_base)
        else:
            ruta_carpeta_destino = os.path.join(DIR_RECHAZADO, nombre_base)
        
        os.makedirs(ruta_carpeta_destino, exist_ok=True)

        # Guardar Análisis
        ruta_reporte = os.path.join(ruta_carpeta_destino, f"Analisis_{nombre_base}.txt")
        with open(ruta_reporte, "w", encoding="utf-8") as f_rep:
            f_rep.write(reporte)
        
        # EXTRACCIÓN BLINDADA DE IDS_SELECCIONADOS
        # Maneja si la IA pone negritas o espacios extra antes de los corchetes
        ids_match = re.search(r"IDS_SELECCIONADOS.*?\[(.*?)\]", reporte, re.I | re.S)
        ids_vistos = [i.strip().replace("'", "").replace('"', '') for i in ids_match.group(1).split(",")] if ids_match else []

        info_origen = {
            'empresa': (re.search(r"EMPRESA:\s*(.*)", texto_vacante)).group(1) if re.search(r"EMPRESA:\s*(.*)", texto_vacante) else "Empresa N/A",
            'titulo': (re.search(r"TITULO:\s*(.*)", texto_vacante)).group(1) if re.search(r"TITULO:\s*(.*)", texto_vacante) else "Vacante N/A",
            'url': (re.search(r"LINK:\s*(.*)", texto_vacante) or re.search(r"URL:\s*(.*)", texto_vacante)).group(1) if re.search(r"LINK:\s*(.*)|URL:\s*(.*)", texto_vacante) else "N/A"
        }

        registrar_en_log_maestro(info_origen, score)

        # --- FASE 2: CONSTRUCCIÓN ---
        if score >= UMBRAL_EXITO:
            print(f"   [!] Match de {score}%. Generando entregables...")
            data_nueva = escritor.obtener_redaccion_optimizada(reporte)
            
            if data_nueva:
                # INTEGRACIÓN DE BIBLIOTECA DE VALORES
                soft_skills_finales = []
                for cat in biblioteca.values():
                    for item in cat:
                        if item['id'] in ids_vistos:
                            soft_skills_finales.append(item['texto'])
                
                if not soft_skills_finales:
                    soft_skills_finales = data_nueva.get('soft_skills', [])

                badges_tech = "".join([f'<span class="skill-tag px-3 py-1 rounded-full text-xs font-bold">{s}</span>' for s in data_nueva.get('skills_tech', [])])
                list_soft = "".join([f'<li class="flex items-center gap-2"><span class="text-blue-500">•</span> <span>{h}</span></li>' for h in soft_skills_finales])
                proyectos_html = "".join(data_nueva.get('proyectos_html', [])) if isinstance(data_nueva.get('proyectos_html'), list) else data_nueva.get('proyectos_html', '')

                nuevo_cv = html_base.replace("{{RESUMEN}}", data_nueva.get('resumen', ''))
                nuevo_cv = nuevo_cv.replace("{{SKILLS_TECH}}", badges_tech)
                nuevo_cv = nuevo_cv.replace("{{SOFT_SKILLS}}", list_soft)
                nuevo_cv = nuevo_cv.replace("{{PROYECTOS}}", proyectos_html)
                
                nombre_archivo_cv = f"{nombre_base}_CV.html"
                ruta_final_cv = os.path.join(ruta_carpeta_destino, nombre_archivo_cv)
                
                with open(ruta_final_cv, "w", encoding="utf-8") as f_res:
                    f_res.write(nuevo_cv)
                
                if os.path.exists(ruta_final_cv):
                    print(f"   [OK] CV Guardado en: {ruta_final_cv}")
                else:
                    print(f"   [ERROR] No se pudo escribir el archivo {nombre_archivo_cv}")
        else:
            print(f"   [.] Score bajo ({score}%). No se requiere CV.")

        # --- FASE 3: LIMPIEZA DE ENTRADA ---
        try:
            shutil.move(ruta_vacante_original, os.path.join(ruta_carpeta_destino, v))
        except Exception as e:
            print(f"   [!] Error moviendo vacante: {e}")

    print("\n" + "="*40)
    print("SISTEMA FINALIZADO CON ÉXITO.")

if __name__ == "__main__":
    ejecutar_sistema_completo()