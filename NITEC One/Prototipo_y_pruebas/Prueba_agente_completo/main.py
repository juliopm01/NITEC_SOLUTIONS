import json
import sys
import os
import subprocess
from agente_3_procesador import procesar_y_dividir_pdfs

def comprobar_y_crear_bases_datos(ruta_carpeta_proyecto, ruta_pdf_normativa=None):
    print("\n🔍 [Pre-vuelo] Comprobando el estado de las bases de datos...")
    
    if not os.path.exists("./bd_normativas"):
        print("   ⚠️ No se encontró './bd_normativas'. Lanzando ingestor legal en segundo plano...")
        try:
            cmd = [sys.executable, "creador_base_datos.py"]
            if ruta_pdf_normativa:
                cmd.append(ruta_pdf_normativa)
            subprocess.run(cmd, check=True)
            print("   ✅ Base de datos legal construida.")
        except Exception as e:
            print(f"   ❌ Error al crear bd_normativas: {e}")
    else:
        print("   ✅ Base de datos legal lista.")

    print(f"   🔄 Procesando la carpeta del proyecto: {ruta_carpeta_proyecto}")
    try:
        subprocess.run([sys.executable, "creador_base_vectores.py", ruta_carpeta_proyecto], check=True)
    except Exception as e:
        print(f"   ❌ Error al procesar el proyecto: {e}")

try:
    from agente_1_extractor import extraer_metadatos
    AGENTE_1_DISPONIBLE = True
except ModuleNotFoundError as e:
    if e.name == "agente_1_extractor":
        AGENTE_1_DISPONIBLE = False
    else:
        raise

from agente_2_normativo_local import ejecutar_agente_2
from geo_localizador import obtener_datos_geograficos

def main():
    print("==================================================")
    print("🚀 INICIANDO ORQUESTADOR DE PROYECTOS URBANÍSTICOS")
    print("==================================================\n")
    
    print("📋 DATOS DEL PROYECTO")
    municipio = input("👉 Introduce el municipio (ej. Málaga): ").strip()
    
    datos_geo = obtener_datos_geograficos(municipio)
    if datos_geo:
        comunidad = datos_geo["comunidad"]
        provincia = datos_geo["provincia"]
        print(f"   📍 Detectado automáticamente: Provincia de {provincia}, {comunidad}.")
    else:
        print("   ⚠️ Municipio no encontrado en la base de datos local.")
        provincia = input("   👉 Introduce la provincia manualmente: ").strip()
        comunidad = input("   👉 Introduce la Comunidad Autónoma manualmente: ").strip()

    tipo_proyecto = input("👉 Introduce el tipo de proyecto (ej. PGOM, ED): ").strip()
    ruta_carpeta_proyecto = input("👉 Introduce la ruta a la CARPETA del proyecto (con todos los PDFs): ").strip()
    ruta_pdf_proyecto = input("👉 Introduce la ruta al PDF principal (ej. memoria descriptiva) para la carátula: ").strip()
    
    ruta_pdf_normativa = None
    if not os.path.exists("boja_base.json") or not os.path.exists("./bd_normativas"): 
        if comunidad.lower() == "andalucía":
            ruta_pdf_normativa = input("👉 [Configuración Inicial] Introduce la ruta al PDF del BOJA: ").strip()
        else:
            ruta_pdf_normativa = input(f"👉 [Configuración Inicial] Introduce la ruta al PDF del boletín de {comunidad}: ").strip()
    
    comprobar_y_crear_bases_datos(ruta_carpeta_proyecto, ruta_pdf_normativa)

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

    limite_mb = reglas_normativas.get("limite_peso_mb", 20)

    print("\n⚙️ [Paso 3] Ejecutando Agente 3 (Procesador y Partición de PDFs)...")
    resultados_procesador = procesar_y_dividir_pdfs(ruta_carpeta_proyecto, limite_mb)

    print("\n==================================================")
    print("✅ DATOS CONSOLIDADOS Y ARCHIVOS PROCESADOS")
    print("==================================================")
    
    resultado_final = {
        "municipio": municipio,
        "provincia": provincia,
        "comunidad_autonoma": comunidad,
        "tipo_proyecto": tipo_proyecto,
        "carpeta_proyecto": ruta_carpeta_proyecto,
        "archivo_origen": ruta_pdf_proyecto,
        "metadatos_caratula": datos_caratula,
        "normativas_empaquetado": reglas_normativas,
        "resultados_agente_3": resultados_procesador
    }
    
    print(json.dumps(resultado_final, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
