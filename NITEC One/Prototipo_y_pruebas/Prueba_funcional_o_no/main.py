import json
import sys
import os
import subprocess
import unicodedata

from geo_localizador import obtener_datos_geograficos
from agente_2_normativo_local import ejecutar_agente_2

try:
    from agente_1_extractor import extraer_metadatos
    AGENTE_1_DISPONIBLE = True
except ImportError:
    AGENTE_1_DISPONIBLE = False

def _limpiar_ruta(ruta):
    if not ruta:
        return ""
    return ruta.strip().strip('"').strip("'")

def _normalizar(texto):
    texto = texto.strip().lower().replace(" ", "_")
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

def comprobar_y_crear_bases_datos(ruta_carpeta_proyecto, ruta_pdf_normativa=None):
    print("\n🔍 [Pre-vuelo] Comprobando el estado de las bases de datos...")
    
    # Comprobación de la base de datos legal
    if not os.path.exists("./bd_normativas"):
        print("   ⚠️ No se encontró './bd_normativas'. Lanzando ingestor legal en segundo plano...")
        try:
            cmd = [sys.executable, "creador_base_datos.py"]
            if ruta_pdf_normativa:
                cmd.append(ruta_pdf_normativa)
            subprocess.run(cmd, check=True)
            print("   ✅ Proceso de base de datos legal finalizado.")
        except Exception as e:
            print(f"   ❌ Error al crear bd_normativas: {e}")
    else:
        print("   ✅ Base de datos legal lista.")

    # Creación/Actualización de la base de datos del proyecto
    print(f"   🔄 Procesando la carpeta del proyecto: {ruta_carpeta_proyecto}")
    try:
        subprocess.run([sys.executable, "creador_base_vectores.py", ruta_carpeta_proyecto], check=True)
    except Exception as e:
        print(f"   ❌ Error al procesar el proyecto: {e}")

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

    tipo_proyecto = input("👉 Introduce el tipo de proyecto (ej. PGOM, ED): ").strip().upper()
    
    ruta_carpeta_proyecto = _limpiar_ruta(
        input("👉 Introduce la ruta a la CARPETA del proyecto (con todos los PDFs): ")
    )
    ruta_pdf_proyecto = _limpiar_ruta(
        input("👉 Introduce la ruta al PDF principal que quieres procesar/cortar (o Enter para autodetectar): ")
    )

    if (not ruta_pdf_proyecto or os.path.isdir(ruta_pdf_proyecto)) and os.path.isdir(ruta_carpeta_proyecto):
        pdfs = sorted([
            os.path.join(ruta_carpeta_proyecto, f)
            for f in os.listdir(ruta_carpeta_proyecto)
            if f.lower().endswith(".pdf")
        ])
        if pdfs:
            ruta_pdf_proyecto = pdfs[0]
            print(f"   📄 PDF principal autodetectado: {ruta_pdf_proyecto}")

    # Si aún no existe boja_base.json (primera ejecución), comprobamos si hay PDF en ./normativas_pdf o lo pedimos
    ruta_pdf_normativa = None
    if not os.path.exists("boja_base.json"):
        pdfs_legales = [
            os.path.join("./normativas_pdf", f)
            for f in os.listdir("./normativas_pdf")
            if f.lower().endswith(".pdf")
        ] if os.path.exists("./normativas_pdf") else []

        if pdfs_legales:
            ruta_pdf_normativa = pdfs_legales[0]
            print(f"   📄 Detectado PDF normativo en carpeta: {ruta_pdf_normativa}")
        else:
            if _normalizar(comunidad) == "andalucia":
                ruta_pdf_normativa = _limpiar_ruta(
                    input("👉 [Configuración Inicial - Solo 1ª vez] Introduce la ruta al PDF del BOJA: ")
                )
            else:
                ruta_pdf_normativa = _limpiar_ruta(
                    input(f"👉 [Configuración Inicial - Solo 1ª vez] Introduce la ruta al PDF del boletín de {comunidad}: ")
                )
    
    # Lanzamos el pre-vuelo con la carpeta introducida y el PDF normativo (si se indicó)
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
    
    # Si falta el PDF del BOJA porque se dejó en blanco en la 1ª vez
    while reglas_normativas.get("estado") == "REQUIERE_BOJA_PDF":
        print(f"\n⚠️ {reglas_normativas.get('mensaje')}")
        ruta_pdf_normativa = _limpiar_ruta(input("👉 Introduce la ruta válida al PDF del BOJA: "))
        reglas_normativas = ejecutar_agente_2(municipio, tipo_proyecto, ruta_boja_pdf=ruta_pdf_normativa)

    # Si el Ayuntamiento no está guardado todavía, lo pedimos a mano y el Agente 2 lo guarda para siempre
    if reglas_normativas.get("estado") == "REQUIERE_LIMITE_MANUAL":
        print(f"\n⚠️ El Ayuntamiento de {municipio} aún no tiene límite registrado en memoria.")
        while True:
            limite_manual = input(f"👉 Introduce a mano el límite de peso en MB para {municipio} (se guardará para futuras ejecuciones): ").strip()
            if limite_manual.isdigit():
                reglas_normativas = ejecutar_agente_2(
                    municipio, tipo_proyecto, 
                    ruta_boja_pdf=ruta_pdf_normativa, 
                    limite_manual_mb=int(limite_manual)
                )
                break
            else:
                print("❌ Por favor, introduce un número entero válido.")

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
    return resultado_final

if __name__ == "__main__":
    main()
