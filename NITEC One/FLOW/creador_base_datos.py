import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from concurrent.futures import ThreadPoolExecutor

print("⚖️ Iniciando el Archivador Legal (Ingesta de Normativas)...")

# 1. LAS NUEVAS RUTAS (Separación de base de datos)
CARPETA_LEYES = "./normativas_pdf" # Carpeta donde el administrativo dejará los PDFs del BOJA/Ayuntamientos
RUTA_BD_LEGAL = "./bd_normativas"  # El nuevo archivador vectorial independiente

if not os.path.exists(CARPETA_LEYES):
    os.makedirs(CARPETA_LEYES)
    print(f"📂 Carpeta creada: {CARPETA_LEYES}. Por favor, mete aquí los PDFs legales.")

archivos_pdf = [f for f in os.listdir(CARPETA_LEYES) if f.endswith('.pdf')]
if not archivos_pdf:
    print("⚠️ No hay normativas para procesar. Fin del programa.")
    exit()

# Ordenar por tamaño (Shortest Job First) para proteger la memoria
archivos_pdf.sort(key=lambda x: os.path.getsize(os.path.join(CARPETA_LEYES, x)))

def procesar_pdf(archivo):
    ruta_completa = os.path.join(CARPETA_LEYES, archivo)
    try:
        cargador = PyPDFLoader(ruta_completa)
        paginas = cargador.load()
        for i, pagina in enumerate(paginas):
            pagina.metadata['categoria'] = 'NORMATIVA_LEGAL' # Etiqueta específica
        return paginas
    except Exception as e:
        print(f"Error leyendo {archivo}: {e}")
        return []

# 2. LECTURA SEGURA
documentos_legales = []
with ThreadPoolExecutor(max_workers=4) as ejecutor:
    resultados = ejecutor.map(procesar_pdf, archivos_pdf)
    for paginas in resultados:
        documentos_legales.extend(paginas)

print(f"📚 Total de páginas legales leídas: {len(documentos_legales)}")

# 3. FRAGMENTACIÓN
guillotina = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
fragmentos_legales = guillotina.split_documents(documentos_legales)

# 4. CREACIÓN DE LA BASE DE DATOS INDEPENDIENTE
modelo_coordenadas = OllamaEmbeddings(model="nomic-embed-text")

print(f"💾 Guardando normativas de forma permanente en: {RUTA_BD_LEGAL}")
base_de_datos_leyes = Chroma.from_documents(
    documents=fragmentos_legales,
    embedding=modelo_coordenadas,
    persist_directory=RUTA_BD_LEGAL
)

print("✅ Archivador Legal completado. Las leyes están listas para ser consultadas.")
