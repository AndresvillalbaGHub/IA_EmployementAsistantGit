import ollama
import json

class CVAdapter:
    def __init__(self, master_cv_path="master_cv.json", modelo="gemma4:31b-cloud"):
        self.modelo = modelo
        self.master_cv_path = master_cv_path
        # Cargamos y pre-procesamos el CV al instanciar la clase
        self.cv_optimizado = self._cargar_y_preparar_cv()

    def _transformar_cv_a_markdown(self, cv):
        """Transforma el nuevo JSON en Markdown de alta densidad para la IA."""
        md = []
        
        # 1. Perfil (Nueva llave: perfil_profesional)
        md.append(f"# PERFIL PROFESIONAL\n{cv.get('perfil_profesional', '')}")
        
        # 2. Educación (Importante por tus promedios de 4.2 y 4.6)
        md.append("\n## FORMACIÓN ACADÉMICA")
        for edu in cv.get('educacion', []):
            md.append(f"- {edu.get('titulo')} en {edu.get('institucion')} ({edu.get('logros')})")
        
        # 3. Competencias Técnicas (Ahora es un diccionario anidado)
        md.append("\n## COMPETENCIAS TÉCNICAS")
        comp = cv.get('competencias_tecnicas', {})
        for categoria, subcategorias in comp.items():
            # Convertimos subcategorías (dict o list) a string para la IA
            md.append(f"### {categoria.replace('_', ' ').upper()}")
            if isinstance(subcategorias, dict):
                for sub_key, sub_val in subcategorias.items():
                    md.append(f"- **{sub_key}**: {sub_val}")
            else:
                md.append(f"- {subcategorias}")
        
        # 4. Proyectos (Nueva llave: proyectos_principales)
        md.append("\n## EXPERIENCIA Y PROYECTOS DETALLADOS")
        for p in cv.get('proyectos_principales', []):
            techs = ", ".join(p.get('tecnologias', []))
            md.append(f"### {p.get('nombre')} | Tech: {techs}")
            md.append(f"Contexto: {p.get('descripcion')}")
            logros = "\n".join([f"  * {l}" for l in p.get('logros', [])])
            md.append(f"Logros clave:\n{logros}")

        md.append("\n## BIBLIOTECA DE VALORES Y HABILIDADES (SOFT SKILLS)")
    
        # Iteramos sobre las categorías (ejecucion_y_eficiencia, etc.)
        biblioteca = cv.get('biblioteca_habilidades', {})
        for categoria, items in biblioteca.items():
            # Formateamos el título de la categoría
            titulo_cat = categoria.replace('_', ' ').upper()
            md.append(f"### {titulo_cat}")
            
            for item in items:
                # Extraemos los datos del objeto JSON
                id_skill = item.get('id', 'N/A')
                texto = item.get('texto', '')
                claves = item.get('clave', '')
                
                # Construimos la línea de Markdown que la IA analizará
                md.append(f"- **ID: {id_skill}** | {texto} | *Palabras Clave: {claves}*")

        return "\n".join(md)

    def _cargar_y_preparar_cv(self):
        try:
            with open(self.master_cv_path, 'r', encoding='utf-8') as f:
                cv_json = json.load(f)
            resultado = self._transformar_cv_a_markdown(cv_json)
            
            # DEBUG: Verifica si el CV tiene contenido
            return resultado
        except Exception as e:
            return ""

    def obtener_redaccion_optimizada(self, analisis_txt):#master_cv_path="master_cv.json"
       # with open(master_cv_path, 'r', encoding='utf-8') as f:
       #     cv_data = json.load(f)

        prompt = f"""
    [ROL: HEADHUNTER TÉCNICO DE ÉLITE]

    ### DATA:
    Analisis de Vacante: {analisis_txt}
    Master CV: {self.cv_optimizado}

    Tu misión es transformar este CV en una oferta irresistible para ESTA vacante específica, usando el análisis de la vacante ({analisis_txt}) y el CV optimizado que te doy ({self.cv_optimizado}).

    ### REGLAS DE ORO:
    1. PROHIBIDO usar frases genéricas como "Ingeniero proactivo" o "Busco aprender". 
    2. ESPEJO: Usa las mismas palabras técnicas que usa la vacante (si piden "SCADA", no pongas "Sistemas de monitoreo").
    3. SELECCIÓN: Elige solo las 5 habilidades técnicas relevantes para la vacante. El resto descártalas.
    4. SOFT SKILLS(valor agregado): Identifica 5 habilidades blandas de la BIBLIOTECA DE VALORES Y HABILIDADES (SOFT SKILLS).
    5. PROYECTOS: Elige unicamente 2 proyectos relacionados con lo que pide la vacante. 
   

    ### SALIDA JSON (ESTRICTA):
    {{
    "resumen": "redacta un resumen para el cv con las siguientes instrucciones":(

    Instrucciones de Redacción:

    Longitud: Máximo 60-70 palabras (4 a 5 líneas).

        Estructura: Comienza con mi título y especialidad. Integra las 3 palabras clave más importantes de la vacante.
        Logros: Incluye una mención a la optimización de procesos, proyectos o diseño de sistemas complejos, usando verbos de acción (Diseñé, Programé, Automaticé).
        Tono: Profesional, técnico, directo y orientado a la resolución de problemas.
        Restricción: No uses clichés como "pasión por aprender", "proactivo" o "trabajo bajo presión". Enfócate en competencias duras y valor añadido. ademas, no uses palabras como "experto", "profesional", "senior", mejor usa palabras como "habilidoso", "capaz", "eficiente", "con conocimiento" o "destacado" para describirme.
      
        
    )",
    
    "skills_tech": ["Skill1", "Skill2", "Skill3", "Skill4","Skill5"],
    "soft_skills": ["Habilidad1", "Habilidad2", "Habilidad3","Habilidad4"],
    "proyectos_html": "HTML de unicamnte 2 proyectos que demuestren que ya he hecho lo que ellos piden."(usa extrictamente este formato a continuación :
    <div>
        <h3 class="text-lg font-semibold text-gray-700">Nombre del Proyecto Reescrito</h3>
        <p class="text-xs text-gray-500 mb-2">Rol: Liderazgo Técnico / Automatización</p>
        <ul class="list-disc list-inside text-gray-600 text-sm space-y-1">
            <li>Logro adaptado a la vacante...</li>
            <li>Tecnología clave utilizada...</li>
        </ul>
    </div>)
    }}
    """
            
        try:
            response = ollama.chat(model=self.modelo, messages=[{'role': 'user', 'content': prompt}])
            # Limpiamos la respuesta para obtener solo el JSON
            res_text = response['message']['content']
            return json.loads(res_text[res_text.find("{"):res_text.rfind("}")+1])
        except:
            return None