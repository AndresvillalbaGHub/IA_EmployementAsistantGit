import ollama
import json
import unicodedata

class CVMatcher:
    def __init__(self, master_cv_path="master_cv.json", modelo="gemma4:31b-cloud"):
        self.modelo = modelo
        self.master_cv_path = master_cv_path
        self.cv_optimizado = self._cargar_y_preparar_cv()

    def _limpiar_para_ia(self, texto):
        if texto is None: return ""
        if isinstance(texto, list):
            texto = " ".join([str(i) for i in texto])
        texto_str = str(texto)
        normalized = unicodedata.normalize('NFKD', texto_str).encode('ascii', 'ignore').decode('ascii')
        return " ".join(normalized.split())

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

    def analizar(self, vacante_raw, nombre_archivo):
        """
        Analiza la vacante ajustando el criterio según el prefijo del archivo.
        SEP: Modo Internacional / Elite (Alta tecnología)
        Otros (GJ, CO, SPE): Modo Industrial Nacional
        """
        es_internacional = nombre_archivo.startswith("GJ")
        vacante_final = self._limpiar_para_ia(vacante_raw)[:950]

        if es_internacional:
            contexto = """
            - MODO: INTERNATIONAL & HIGH-TECH (SerpApi).
             - ### INSTRUCCIONES CRÍTICAS ###
            -NO uses encabezados con '#' o '##'.
            -Usa exclusivamente el formato de abajo.
            - ENFOQUE: Valora la capacidad de desarrollo (C++, Python, Linux, Embedded) y la excelencia académica (GPA 4.2/4.6).
            - NO penalices por falta de experiencia en años a menos que se solicite mas de 3 años.
            - Se flexible con tecnologías específicas siempre que el candidato muestre habilidades transferibles y un perfil de alto potencial.
            - Valora especialmente la mención de proyectos relevantes.
            """
        else:
            contexto = """
            - MODO: INDUSTRIAL NACIONAL (Bolsas locales).
            - ### INSTRUCCIONES CRÍTICAS ###
            1. NO uses encabezados con '#' o '##'.
            2. Usa exclusivamente el formato de abajo.
            3. Si no hay evidencia literal en el CV, el SCORE debe ser bajo.
            4. si el cv menciona una habilidad que no esta en la vacante, no le des puntos ni quites puntos, solo cuenta lo que la vacante pide.
            5. no penalices por falta de experiencia si el cv menciona la habilidad, aunque no tenga años de experiencia, cuenta como match, pero si la vacante pide 3 años o mas y el cv no menciona años, no le des mas de 50% de puntos por esa habilidad.
            6. Considera que el candidato esta en busqueda de su primer empleo, por lo que si el cv menciona habilidades clave aunque no tenga experiencia, puede ser un buen match.
            ### REGLA DE ORO DE AUDITORÍA ###
            
            1 EVIDENCIA LITERAL: Por cada match, debes extraer la frase exacta del CV. Si no hay frase, no hay puntos.
            """

        prompt = f"""
    [ROL: AUDITOR TÉCNICO DE CARRERA]
    Ajusta tu evaluación según este contexto: {contexto}
    
    ### INFORMACIÓN DEL CANDIDATO ###
    {self.cv_optimizado}

    ### REQUISITOS DE LA VACANTE ###
    {vacante_final}

    ### ESTRUCTURA DE RESPUESTA OBLIGATORIA ###
    Responde estrictamente en este formato:

    - RESUMEN DE LA VACANTE: (Un párrafo técnico que resuma la vacante y sus requisitos clave)
    - COINCIDENCIAS: (Lista de habilidades encontradas con evidencia literal)
    - DISCREPANCIAS: (Lista de requisitos de la vacante NO encontrados en el CV)
    - SCORE FINAL: (Número de 0 a 100 basado en el cumplimiento de requisitos críticos)
    - JUSTIFICACIÓN: (Un párrafo técnico explicando por qué es o no viable aplicar)
    """

        try:
            response = ollama.chat(
                model=self.modelo,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'temperature': 0.2,
                    'num_ctx': 4096,
                    'num_thread': 4,
                    'num_predict': 800,
                    'top_p': 0.9,
                    'stop': ["<|endoftext|>", "###"]
                }
            )
            return response['message']['content']
        except Exception as e:
            return f"ERROR_IA: {e}"
        
       