import os
import shutil
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

RUTA_BD_PROYECTO = "./bd_vectores"

def ingestar_proyecto(ruta_carpeta):
    print(f"⚙️ Construyendo base de datos del proyecto desde: {ruta_carpeta}")
    
    # 1. Limpiamos la memoria del proyecto anterior
    if os.path.exists(RUTA_BD_PROYECTO):
        print("   🗑️ Borrando memoria anterior del proyecto...")
        shutil.rmtree(RUTA_BD_PROYECTO)
        
    if not os.path.exists(ruta_carpeta):
        return {"estado": "ERROR", "mensaje": "La carpeta no existe."}
        
    # 2. Escaneamos los PDFs
    archivos_pdf = [f for f in os.listdir(ruta_carpeta) if f.endswith('.pdf')]
    if not archivos_pdf:
        return {"estado": "ERROR", "mensaje": "No se encontraron PDFs."}

    documentos = []
    for archivo in archivos_pdf:
        ruta_completa = os.path.join(ruta_carpeta, archivo)
        try:
            cargador = PyPDFLoader(ruta_completa)
            documentos.extend(cargador.load())
        except Exception as e:
            print(f"   ⚠️ Error leyendo {archivo}: {e}")

    if not documentos:
        return {"estado": "ERROR", "mensaje": "No se pudo extraer texto."}

    # 3. Troceamos y guardamos en ChromaDB
    guillotina = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    fragmentos = guillotina.split_documents(documentos)
    modelo_coordenadas = OllamaEmbeddings(model="nomic-embed-text")
    
    Chroma.from_documents(
        documents=fragmentos, 
        embedding=modelo_coordenadas, 
        persist_directory=RUTA_BD_PROYECTO
    )
    
    print("   ✅ Base de datos del proyecto lista.")
    return {"estado": "COMPLETADO"}

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        ingestar_proyecto(sys.argv[1])
    else:
        print("Uso: python creador_base_vectores.py <ruta_carpeta>")
