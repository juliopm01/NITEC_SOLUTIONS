import os
import shutil
import time
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

RUTA_BD_PROYECTO = "./bd_vectores"

def ingestar_proyecto(ruta_carpeta):
    print(f"⚙️ Construyendo base de datos del proyecto desde: {ruta_carpeta}")
    
    if os.path.exists(RUTA_BD_PROYECTO):
        print("   🗑️ Borrando memoria anterior del proyecto...")
        for intento in range(3):
            try:
                shutil.rmtree(RUTA_BD_PROYECTO)
                break
            except PermissionError:
                if intento < 2:
                    time.sleep(1)
                else:
                    for root, dirs, files in os.walk(RUTA_BD_PROYECTO, topdown=False):
                        for name in files:
                            try:
                                os.unlink(os.path.join(root, name))
                            except:
                                pass
                        for name in dirs:
                            try:
                                os.rmdir(os.path.join(root, name))
                            except:
                                pass
        
    if not os.path.exists(ruta_carpeta):
        return {"estado": "ERROR", "mensaje": "La carpeta no existe."}
        
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
