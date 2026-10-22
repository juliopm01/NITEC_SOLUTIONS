import os
import sys
import shutil
import stat
import time
import gc
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

RUTA_BD_PROYECTO = "./bd_vectores"

def _forzar_desbloqueo(func, path, exc_info):
    """Elimina atributo de solo lectura en Windows y reintenta borrar."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def limpiar_bd_anterior(ruta_bd):
    if not os.path.exists(ruta_bd):
        return
    print("   🗑️ Borrando memoria anterior del proyecto...")
    gc.collect()
    for intento in range(5):
        try:
            shutil.rmtree(ruta_bd, onerror=_forzar_desbloqueo)
            if not os.path.exists(ruta_bd):
                break
        except PermissionError:
            gc.collect()
            time.sleep(0.5 * (intento + 1))
        except Exception:
            time.sleep(0.3)

    # Si tras los intentos aún queda algún archivo suelto, vaciar contenido
    if os.path.exists(ruta_bd):
        for root, dirs, files in os.walk(ruta_bd, topdown=False):
            for name in files:
                ruta_f = os.path.join(root, name)
                try:
                    os.chmod(ruta_f, stat.S_IWRITE)
                    os.unlink(ruta_f)
                except Exception:
                    pass
            for name in dirs:
                try:
                    os.rmdir(os.path.join(root, name))
                except Exception:
                    pass

def ingestar_proyecto(ruta_carpeta):
    ruta_carpeta = ruta_carpeta.strip().strip('"').strip("'")
    print(f"⚙️ Construyendo base de datos del proyecto desde: {ruta_carpeta}")
    
    if not os.path.exists(ruta_carpeta):
        print(f"   ❌ La carpeta no existe: {ruta_carpeta}")
        return {"estado": "ERROR", "mensaje": "La carpeta no existe."}
        
    archivos_pdf = sorted([
        f for f in os.listdir(ruta_carpeta)
        if f.lower().endswith('.pdf') and "_tomo_" not in f.lower() and "_parte_" not in f.lower()
    ])
    if not archivos_pdf:
        print("   ⚠️ No se encontraron PDFs en la carpeta.")
        return {"estado": "ERROR", "mensaje": "No se encontraron PDFs."}

    # 1. Limpiamos la memoria del proyecto anterior de forma segura
    limpiar_bd_anterior(RUTA_BD_PROYECTO)

    # 2. Escaneamos los PDFs
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
    
    db = Chroma.from_documents(
        documents=fragmentos, 
        embedding=modelo_coordenadas, 
        persist_directory=RUTA_BD_PROYECTO
    )
    
    # Liberamos la conexión para que el proceso cierre el descriptor de chroma.sqlite3
    del db
    gc.collect()
    
    print("   ✅ Base de datos del proyecto lista.")
    return {"estado": "COMPLETADO", "fragmentos": len(fragmentos)}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        res = ingestar_proyecto(sys.argv[1])
        if res.get("estado") == "ERROR":
            sys.exit(1)
    else:
        print("Uso: python creador_base_vectores.py <ruta_carpeta>")
