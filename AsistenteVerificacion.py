import os
import ollama
import shutil
import json

class AgenteInteligente:
    
    def __init__(self,master_cv_path="master_cv.json", modelo="gemma4:31b-cloud"):
        self.modelo = modelo
        self.ruta_raiz = "resultados/aceptado"
        self.ruta_rechazados = "resultados/rechazados" # <-- CAMBIADO A PLURAL
        # RUTA ACTUALIZADA: Fuera de resultados
        self.destino_aprobadas = "por_postular"
        self.master_cv_path = master_cv_path
        self.cv_optimizado = self._cargar_y_preparar_cv()
        
        # PERFIL TÉCNICO INTEGRADO (Basado en tu trayectoria real)
        # Se inyecta como contexto para que Qwen actúe como tu representante
        self.perfil_contexto = """
        PERFIL: Ingeniero Electrónico Junior con Especialización en Automatización Industrial.
        ESTADO: Recién egresado buscando primera experiencia profesional.
        FORTALEZA ACADÉMICA: GPA Pregrado 4.2 | GPA Posgrado 4.6 (Excelencia técnica).
        PROYECTOS CLAVE (Experiencia Técnica):
        1. Sistema de bombeo automatizado en minas de carbón en simulacion (ControlLogix, HART).
        2. Visión artificial con YOLOv5 en Raspberry Pi (Edge AI).
        3. Control de cobot jaka con pulsos EMG.
        FILOSOFÍA: Optimización de procesos y mejora constante.
        UBICACIÓN: Residente en Sogamoso, Boyacá.
        META: Cargo Junior/Trainee que permita programar PLCs o desarrollar en Python.
        SALARIO ESPERADO: Rango realista para Junior Especializado ($2.8M - $4.0M COP).
        """

    # --- AGREGAR ESTE MÉTODO A TU CLASE AgenteInteligente ---
    def _transformar_cv_a_markdown(self, cv):
        md = []
        # Perfil optimizado
        md.append(f"P: {self._limpiar_para_ia(cv.get('perfil_profesional', ''))[:180]}")
        
        # Educación y promedios destacados
        md.append("\nE:")
        for edu in cv.get('educacion', []):
            t = self._limpiar_para_ia(edu.get('titulo'))
            l = self._limpiar_para_ia(edu.get('logros'))
            md.append(f"- {t}|{l}")
        
        # Competencias técnicas
        md.append("\nT:")
        comp = cv.get('competencias_tecnicas', {})
        skills_limpias = []
        for v in comp.values():
            if isinstance(v, (dict, list)):
                iterable = v.values() if isinstance(v, dict) else v
                skills_limpias.extend([self._limpiar_para_ia(item) for item in iterable])
            else:
                skills_limpias.append(self._limpiar_para_ia(v))
        
        md.append(", ".join(set(filter(None, skills_limpias))))
        
        # Proyectos (Diferencial para vacantes SEP)
        md.append("\nX:")
        for p in cv.get('proyectos_principales', []):
            n = self._limpiar_para_ia(p.get('nombre'))
            logro = self._limpiar_para_ia(p.get('logros', [""])[0])
            md.append(f"* {n}: {logro}")

        return "\n".join(md)
    
    def _cargar_y_preparar_cv(self):
        try:
            with open(self.master_cv_path, 'r', encoding='utf-8') as f:
                cv_json = json.load(f)
            return self._transformar_cv_a_markdown(cv_json)
        except Exception as e:
            print(f"[ERROR] {e}")
            return ""
    
    def rescatar_vacante(self, ruta_carpeta):
        """Mueve una vacante desde rechazados de vuelta al flujo de aceptados."""
        # Aseguramos que la carpeta de destino existe
        if not os.path.exists(self.ruta_raiz):
            os.makedirs(self.ruta_raiz)
            
        nombre = os.path.basename(ruta_carpeta)
        destino = os.path.join(self.ruta_raiz, nombre)
        
        try:
            shutil.move(ruta_carpeta, destino)
            return True
        except Exception as e:
            print(f"Error al rescatar señal: {e}")
            return False

    def analizar_vacante_seleccionada(self, ruta_carpeta):
        """Prepara el análisis inicial para la discusión en el chat."""
        archivos = os.listdir(ruta_carpeta)
        vacante_raw, analisis_previo = "", ""
        for f_name in archivos:
            ruta_f = os.path.join(ruta_carpeta, f_name)
            if os.path.isfile(ruta_f) and f_name.endswith('.txt'):
                with open(ruta_f, 'r', encoding='utf-8', errors='replace') as f:
                    contenido = f.read()
                    if 'analisis' in f_name.lower(): analisis_previo = contenido
                    else: vacante_raw = contenido
        
        contexto_total = f"--perfil--\n{self.cv_optimizado}\n\n--- VACANTE ---\n{vacante_raw}\n\n--- ANÁLISIS ---\n{analisis_previo}"
        
        # Generamos el reporte estructurado de inmediato
        prompt = f"""
        [ROL: SENIOR CAREER MENTOR & TECHNICAL STRATEGIST]
        Tu objetivo es actuar como un filtro de alta exigencia para un Ingeniero Electrónico con especialización en Automatización Industrial (GPA 4.6) recien egresado en busqueda de su primer trabajo. 

        ### CRITERIOS DE EVALUACIÓN PRIORITARIOS:
        1. CRECIMIENTO PROFESIONAL: ¿La vacante ofrece una ruta hacia Seniority o R&D,vale la pena como oportunidad de primer empleo, o es un puesto operativo estancado?
        2. STACK TECNOLÓGICO: Prioriza proyectos que integren Edge AI (Python, OpenCV, YOLOv5) con hardware industrial (ControlLogix, FPGA, ARM). Desestima puestos que solo pidan mantenimiento básico.
        3. UBICACIÓN/MODALIDAD: Evalúa el impacto de la ubicación (Sogamoso vs. otras ciudades) o si el esquema Remoto/Híbrido justifica la posición.
        4. SINERGIA DE HABILIDADES: 
        - Técnicas: Uso de instrumentación avanzada (HART, sensores hidrostáticos).
        - Blandas: Busca entornos que valoren la "Optimización constante" y el "No conformismo".

        
        DATOS COMPLETS:
        {contexto_total}

        RESPONDE:
        - BREVE RESUMEN: (1-2 líneas destacando lo más relevante de la vacante)
        - VERDICTO: [POSTULAR / DESCARTAR]
        - POR QUÉ: (Análisis de crecimiento y tecnología)
        - RIESGO: (¿Qué es lo peor de esta vacante?)
        - PREGUNTA CLAVE: (Una pregunta para que el candidato reflexione)
        """
        try:
            response = ollama.chat(model=self.modelo, messages=[{'role': 'user', 'content': prompt}])
            return response['message']['content']
        except Exception as e:
            return f"Error de conexión: {e}"

    def conversar(self, historial_mensajes):
        """Gestiona la discusión por escrito sobre la vacante."""
        try:
            response = ollama.chat(model=self.modelo, messages=historial_mensajes)
            return response['message']['content']
        except Exception as e:
            return f"Error: {e}"

    def ejecutar_movimiento(self, ruta_carpeta, accion):
        """Mueve la carpeta a 'por_postular' o la elimina."""
        if not os.path.exists(self.destino_aprobadas): 
            os.makedirs(self.destino_aprobadas)
        
        nombre = os.path.basename(ruta_carpeta)
        if accion == "APROBAR":
            # Movimiento fuera de resultados
            shutil.move(ruta_carpeta, os.path.join(self.destino_aprobadas, nombre))
        elif accion == "DESCARTAR":
            shutil.rmtree(ruta_carpeta)
        return True