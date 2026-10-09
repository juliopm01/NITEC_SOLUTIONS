import os
import shutil
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader, UnstructuredExcelLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama

print("🤖 Iniciando el agente documentalista masivo...")

# --- MOTOR DE ETIQUETADO INTELIGENTE ---
llm_clasificador = ChatOllama(model="llama3.1", temperature=0)

def clasificar_archivo(texto_muestra):
    prompt = f"""Eres un clasificador de documentos para concursos de arquitectura.
    Lee el siguiente fragmento (inicio del documento) y clasifícalo en UNA sola de estas categorías:
    - PRESUPUESTO
    - MEMORIA_TECNICA
    - PLIEGOS_BASES
    - ADMINISTRATIVO
    - PLANOS
    - OTRO
    
    Devuelve ÚNICAMENTE el nombre de la categoría en mayúsculas, sin saludos ni explicaciones.
    
    Texto a analizar:
    {texto_muestra[:1000]}
    """
    respuesta = llm_clasificador.invoke(prompt).content.strip().upper()
    
    categorias = ["PRESUPUESTO", "MEMORIA_TECNICA", "PLIEGOS_BASES", "ADMINISTRATIVO", "PLANOS"]
    for cat in categorias:
        if cat in respuesta:
            return cat
    return "OTRO"
# ----------------------------------------

ruta_carpeta = input("📁 Introduce el nombre o la ruta de la carpeta a escanear: ").strip()

if not os.path.exists(ruta_carpeta) or not os.path.isdir(ruta_carpeta):
    print(f"❌ Error: No se ha encontrado ninguna carpeta llamada '{ruta_carpeta}'.")
    exit()

directorio_bd = "./bd_vectores"
if os.path.exists(directorio_bd):
    print("🗑️ Borrando base de datos antigua...")
    shutil.rmtree(directorio_bd)

documentos_totales = []
archivos_procesados = 0

print(f"🔍 Escaneando el interior de '{ruta_carpeta}' y sus subcarpetas...")

for raiz, carpetas, archivos in os.walk(ruta_carpeta):
    for archivo in archivos:
        ruta_completa = os.path.join(raiz, archivo)
        
        try:
            docs_cargados = []
            
            if archivo.lower().endswith(".pdf"):
                docs_cargados = PyPDFLoader(ruta_completa).load()
                tipo = "📄"
            elif archivo.lower().endswith(".txt"):
                docs_cargados = TextLoader(ruta_completa, autodetect_encoding=True).load()
                tipo = "📝"
            elif archivo.lower().endswith(".docx"):
                docs_cargados = Docx2txtLoader(ruta_completa).load()
                tipo = "📘"
            elif archivo.lower().endswith(".xlsx"):
                docs_cargados = UnstructuredExcelLoader(ruta_completa).load()
                tipo = "📊"
            else:
                continue 
                
            if docs_cargados:
                texto_inicial = docs_cargados[0].page_content 
                etiqueta = clasificar_archivo(texto_inicial)
                
                for doc in docs_cargados:
                    doc.metadata['categoria'] = etiqueta
                    
                documentos_totales.extend(docs_cargados)
                archivos_procesados += 1
                print(f"  {tipo} Leído: {archivo} --> 🏷️ Etiqueta: {etiqueta}")
                
        except Exception as e:
            print(f"  ⚠️ Ignorado '{archivo}': Error al leer ({e})")

if archivos_procesados == 0:
    print("❌ No se encontraron archivos legibles en esa ruta.")
    exit()

print(f"\n✅ Escaneo completado. Se han absorbido y etiquetado {archivos_procesados} archivos.")

print("✂️ Troceando todo el contenido...")
troceador = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=400)
trozos = troceador.split_documents(documentos_totales)

print("🗄️ Guardando en la base de datos...")
modelo_coordenadas = OllamaEmbeddings(model="nomic-embed-text")
base_de_datos = Chroma.from_documents(
    documents=trozos, 
    embedding=modelo_coordenadas,
    persist_directory=directorio_bd
)
print(f"✅ Base de datos masiva lista en la carpeta '{directorio_bd}'.")