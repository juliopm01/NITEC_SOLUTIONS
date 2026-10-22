import json
import sys
import os
import subprocess

# --- NUEVO: PRE-VUELO PARA BASES DE DATOS ---
def comprobar_y_crear_bases_datos(ruta_carpeta_proyecto):
    print("\n🔍 [Pre-vuelo] Comprobando el estado de las bases de datos...")
    
    # Comprobación de la base de datos legal
    if not os.path.exists("./bd_normativas"):
        print("   ⚠️ No se encontró './bd_normativas'. Lanzando ingestor legal en segundo plano...")
        try:
            subprocess.run([sys.executable, "creador_base_datos.py"], check=True)
            print("   ✅ Base de datos legal construida.")
        except Exception as e:
            print(f"   ❌ Error al crear bd_normativas: {e}")
    else:
        print("   ✅ Base de datos legal lista.")

    # Creación/Actualización de la base de datos del proyecto
    print(f"   🔄 Procesando la carpeta del proyecto: {ruta_carpeta_proyecto}")
    try:
        # Llamamos al nuevo creador silencioso pasándole la ruta que introdujo el usuario
        subprocess.run([sys.executable, "creador_base_vectores.py", ruta_carpeta_proyecto], check=True)
    except Exception as e:
        print(f"   ❌ Error al procesar el proyecto: {e}")
# -------------------------------------------

try:
    from agente_1_extractor import extraer_metadatos
    AGENTE_1_DISPONIBLE = True
except ImportError:
    AGENTE_1_DISPONIBLE = False

from agente_2_normativo_local import ejecutar_agente_2
from geo_localizador import obtener_datos_geograficos

def main():
    print("==================================================")
    print("🚀 INICIANDO ORQUESTADOR DE PROYECTOS URBANÍSTICOS")
    print("==================================================\n")
    
    print("📋 DATOS DEL PROYECTO")
    municipio = input("👉 Introduce el municipio (ej. Málaga): ").strip()
    
    # --- RESOLUCIÓN GEOGRÁFICA LOCAL ---
    datos_geo = obtener_datos_geograficos(municipio)
    if datos_geo:
        comunidad = datos_geo["comunidad"]
        provincia = datos_geo["provincia"]
        print(f"   📍 Detectado automáticamente: Provincia de {provincia}, {comunidad}.")
    else:
        print("   ⚠️ Municipio no encontrado en la base de datos local.")
        provincia = input("   👉 Introduce la provincia manualmente: ").strip()
        comunidad = input("   👉 Introduce la Comunidad Autónoma manualmente: ").strip()
    # ------------------------------------------

    tipo_proyecto = input("👉 Introduce el tipo de proyecto (ej. PGOM, ED): ").strip()
    
    # NUEVO: Pedimos la carpeta entera para el Agente 1
    ruta_carpeta_proyecto = input("👉 Introduce la ruta a la CARPETA del proyecto (con todos los PDFs): ").strip()
    # Mantenemos el PDF individual para el Agente 3
    ruta_pdf_proyecto = input("👉 Introduce la ruta al PDF principal que quieres procesar/cortar: ").strip()
    
    archivo_normativa_cache = f"normativa_{comunidad.replace(' ', '_').lower()}.json"
    ruta_pdf_normativa = None
    
    if not os.path.exists("boja_base.json"): 
        if comunidad.lower() == "andalucía":
            ruta_pdf_normativa = input("👉 [Configuración Inicial] Introduce la ruta al PDF del BOJA: ").strip()
        else:
            ruta_pdf_normativa = input(f"👉 [Configuración Inicial] Introduce la ruta al PDF del boletín de {comunidad}: ").strip()
    
    # Lanzamos el pre-vuelo con la carpeta introducida
    comprobar_y_crear_bases_datos(ruta_carpeta_proyecto)

    print("\n==================================================")
    
    print("\n⚙️ [Paso 1] Ejecutando Agente 1 (Extractor de Carátula)...")
    if AGENTE_1_DISPONIBLE:
        try:
            datos_caratula = extraer_metadatos(ruta_pdf_proyecto)
        except Exception as e:
            print(f"⚠️ Error en Agente 1: {e}")
            datos_caratula = {"error": "Fallo en la extracción"}
    else:
        print("⚠️ Archivo 'agente_1_extractor.py' no encontrado. Usando datos simulados...")
        datos_caratula = {"fecha": "2026-10-22", "autor": "Estudio Arquitectura", "titulo": "Proyecto Simulado"}
            
    print("\n⚙️ [Paso 2] Ejecutando Agente 2 (Auditor Normativo Local)...")
    reglas_normativas = ejecutar_agente_2(municipio, tipo_proyecto, ruta_boja_pdf=ruta_pdf_normativa)
    
    if reglas_normativas.get("estado") == "REQUIERE_LIMITE_MANUAL":
        print(f"\n⚠️ ATENCIÓN: No se encontró normativa local automática para {municipio}.")
        while True:
            limite_manual = input("👉 Introduce el límite de peso en MB para este ayuntamiento: ").strip()
            if limite_manual.isdigit():
                reglas_normativas = ejecutar_agente_2(
                    municipio, tipo_proyecto, 
                    ruta_boja_pdf=ruta_pdf_normativa, 
                    limite_manual_mb=int(limite_manual)
                )
                break
            else:
                print("❌ Por favor, introduce un número válido.")

    if reglas_normativas.get("estado") == "COMPLETADO":
        del reglas_normativas["estado"]

    print("\n==================================================")
    print("✅ DATOS CONSOLIDADOS CON ÉXITO")
    print("==================================================")
    
    resultado_final = {
        "municipio": municipio,
        "provincia": provincia,
        "comunidad_autonoma": comunidad,
        "tipo_proyecto": tipo_proyecto,
        "carpeta_proyecto": ruta_carpeta_proyecto,
        "archivo_origen": ruta_pdf_proyecto,
        "metadatos_caratula": datos_caratula,
        "normativas_empaquetado": reglas_normativas
    }
    
    print(json.dumps(resultado_final, indent=2, ensure_ascii=False))
    print("\n🔜 Próximo paso: Enviar JSON al Agente 3 (Procesador de PDFs).")

if __name__ == "__main__":
    main()
