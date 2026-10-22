import os
import sys
import shutil
import gc
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

CARPETA_LEYES = "./normativas_pdf"
RUTA_BD_LEGAL = "./bd_normativas"

def _normalizar(texto):
    texto = texto.strip().lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

def detectar_municipio_en_nombre(nombre_archivo):
    nombre_norm = _normalizar(os.path.splitext(nombre_archivo)[0])
    municipios_conocidos = [
        "marbella", "malaga", "sevilla", "dos hermanas", "cordoba",
        "granada", "cadiz", "huelva", "jaen", "almeria", "estepona",
        "mijas", "fuengirola", "madrid", "barcelona", "valencia"
    ]
    for muni in municipios_conocidos:
        if muni.replace(" ", "_") in nombre_norm or muni in nombre_norm:
            return muni
    return "general"

def procesar_pdf(archivo):
    ruta_completa = os.path.join(CARPETA_LEYES, archivo)
    muni_detectado = detectar_municipio_en_nombre(archivo)
    try:
        cargador = PyPDFLoader(ruta_completa)
        paginas = cargador.load()
        for pagina in paginas:
            pagina.metadata['categoria'] = 'NORMATIVA_LEGAL'
            pagina.metadata['archivo_origen'] = archivo
            pagina.metadata['municipio'] = muni_detectado
        return paginas
    except Exception as e:
        print(f"   ⚠️ Error leyendo {archivo}: {e}")
        return []

def ingestar_normativas(ruta_pdf_extra=None):
    print("⚖️ Iniciando el Archivador Legal (Ingesta de Normativas)...")

    if not os.path.exists(CARPETA_LEYES):
        os.makedirs(CARPETA_LEYES, exist_ok=True)
        print(f"📂 Carpeta creada: {CARPETA_LEYES}.")

    # Si se pasa un PDF externo (ej. desde main.py), lo incorporamos a normativas_pdf
    if ruta_pdf_extra:
        ruta_limpia = ruta_pdf_extra.strip().strip('"').strip("'")
        if os.path.isfile(ruta_limpia) and ruta_limpia.lower().endswith('.pdf'):
            destino = os.path.join(CARPETA_LEYES, os.path.basename(ruta_limpia))
            if os.path.abspath(ruta_limpia) != os.path.abspath(destino):
                shutil.copy2(ruta_limpia, destino)
                print(f"📥 PDF normativo copiado a {CARPETA_LEYES}: {os.path.basename(ruta_limpia)}")

    archivos_pdf = [f for f in os.listdir(CARPETA_LEYES) if f.lower().endswith('.pdf')]
    if not archivos_pdf:
        print("⚠️ No hay normativas en './normativas_pdf' para procesar. Fin del archivador legal.")
        return {"estado": "SIN_NORMATIVAS", "paginas": 0}

    archivos_pdf.sort(key=lambda x: os.path.getsize(os.path.join(CARPETA_LEYES, x)))

    documentos_legales = []
    with ThreadPoolExecutor(max_workers=4) as ejecutor:
        resultados = ejecutor.map(procesar_pdf, archivos_pdf)
        for paginas in resultados:
            documentos_legales.extend(paginas)

    if not documentos_legales:
        print("⚠️ No se pudo extraer texto de los PDFs legales.")
        return {"estado": "ERROR", "mensaje": "PDFs sin texto extraíble"}

    print(f"📚 Total de páginas legales leídas: {len(documentos_legales)}")

    guillotina = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    fragmentos_legales = guillotina.split_documents(documentos_legales)

    modelo_coordenadas = OllamaEmbeddings(model="nomic-embed-text")

    print(f"💾 Guardando normativas de forma permanente en: {RUTA_BD_LEGAL}")
    base_de_datos_leyes = Chroma.from_documents(
        documents=fragmentos_legales,
        embedding=modelo_coordenadas,
        persist_directory=RUTA_BD_LEGAL
    )

    # Liberar recursos SQLite para evitar bloqueos en Windows
    del base_de_datos_leyes
    gc.collect()

    print("✅ Archivador Legal completado. Las leyes están listas para ser consultadas.")
    return {"estado": "COMPLETADO", "paginas": len(documentos_legales)}

if __name__ == "__main__":
    ruta_arg = sys.argv[1] if len(sys.argv) > 1 else None
    ingestar_normativas(ruta_arg)
