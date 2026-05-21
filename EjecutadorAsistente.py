import os
import shutil
from BuscadorVacantes import ejecutar_explorador_inteligente # type: ignore
from BuscadorVacantesLinkedin import ejecutar_sonda_limitada # type: ignore
from ConstructorCVs import ejecutar_sistema_completo # type: ignore
from BuscadorVacantesCompuTra import ejecutar_radar_computrabajo # type: ignore
import asyncio


def limpiar_entorno():
    print("\n" + "="*40)
    print("--- FASE DE PREPARACIÓN ---")
    opcion = input("¿Deseas borrar las vacantes y CVs de la sesión anterior? (s/n): ").lower()
    
    if opcion == 's':
        # Limpiamos carpetas temporales pero NO los logs permanentes
        directorios = ['vacantes', 'resultados']
        for carpeta in directorios:
            if os.path.exists(carpeta):
                for archivo in os.listdir(carpeta):
                    ruta = os.path.join(carpeta, archivo)
                    try:
                        if os.path.isfile(ruta):
                            os.remove(ruta)
                    except Exception as e:
                        print(f"Error borrando {archivo}: {e}")
        print("[OK] Entorno limpio. Listo para nueva búsqueda.")
    else:
        print("[!] Conservando archivos previos. Las nuevas vacantes se añadirán a las existentes.")

async def main():
    print("--- INICIANDO SISTEMA INTEGRADO DE EMPLEO ---")    # 1. LIMPIEZA INICIAL 
    
    #limpiar_entorno()
    
    # 2. EXPLORACIÓN (Llenado de /vacantes)

    nuevas_serp = ejecutar_explorador_inteligente()
    nuevas_spe = await ejecutar_sonda_limitada()
    nuevas_computra = await ejecutar_radar_computrabajo()
    
    #total_recolectadas = nuevas_serp + nuevas_spe
    print(f"\n[!] Fase de captura terminada.")
    #print("\n--- FASE DE EXPLORACIÓN ---")
    #BuscadorVacantes.ejecutar_explorador_iterativo()
    #BuscadorVacantesLinkedin.ejecutar_sonda_limitada()
    
    # 3. CONSTRUCCIÓN (Generación de /resultados)
    print("\n--- FASE DE CONSTRUCCIÓN ---")

    ejecutar_sistema_completo()
    #ConstructorCVs.ejecutar_sistema_completo()
    
    print("\n" + "="*40)
    print("PROCESO FINALIZADO.")
    print("Revisa /vacantes para el contexto y /resultados para tus CVs.")

if __name__ == "__main__":
    asyncio.run(main())