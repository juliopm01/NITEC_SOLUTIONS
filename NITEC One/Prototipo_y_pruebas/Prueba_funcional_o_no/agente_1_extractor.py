import os
import re
import gc
import json
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_loaders import PyPDFLoader

RUTA_BD_PROYECTO = "./bd_vectores"

# Configuramos el LLM y la plantilla sin abrir aún la base de datos en disco
llm = ChatOllama(model="llama3.1", temperature=0, num_ctx=16000)

plantilla = ChatPromptTemplate.from_messages([
    ("system", """Eres el Agente Documentalista (Rastreador Implacable).
    Tu objetivo es extraer dos datos legales específicos del proyecto urbanístico basándote ÚNICAMENTE en el contexto proporcionado.
    
    Reglas estrictas:
    1. Fase de Tramitación: Detecta la fase (ej. AI para Aprobación Inicial, AD para Aprobación Definitiva, AP para Aprobación Provisional).
    2. Fecha de aprobación: Formato AAAAMMDD. Busca ÚNICAMENTE fechas ligadas a firmas oficiales, 'Acuerdo de Pleno', 'Resolución' o 'Aprobación'. Ignora explícitamente fechas de topografías, mediciones o certificados antiguos.
    3. Si tras analizar el contexto el dato no existe, debes escribir estrictamente el valor "NO_ENCONTRADA".
    
    Contexto extraído de los documentos:
    {context}
    
    Tu respuesta DEBE ser EXCLUSIVAMENTE un objeto JSON válido. No incluyas texto antes ni después. No saludes ni uses markdown.
    Usa estrictamente esta estructura:
    {{
        "fase_tramitacion": "valor_o_NO_ENCONTRADA",
        "fecha_aprobacion": "valor_o_NO_ENCONTRADA"
    }}""")
])

cadena = plantilla | llm | StrOutputParser()

def buscar_fusion_hibrida(pregunta, ruta_pdf_respaldo=None):
    """
    Se conecta a ./bd_vectores BAJO DEMANDA (después de que creador_base_vectores haya terminado),
    realiza la búsqueda híbrida (Vectorial + BM25) y libera inmediatamente el archivo SQLite.
    """
    documentos_fusion = []
    if os.path.exists(RUTA_BD_PROYECTO):
        base_de_datos = None
        try:
            modelo_coordenadas = OllamaEmbeddings(model="nomic-embed-text")
            base_de_datos = Chroma(
                persist_directory=RUTA_BD_PROYECTO,
                embedding_function=modelo_coordenadas
            )
            recuperador_vectores = base_de_datos.as_retriever(search_kwargs={"k": 2})

            datos_guardados = base_de_datos.get()
            textos_completos = datos_guardados.get('documents', [])
            metadatos = datos_guardados.get('metadatas', [])

            docs_memoria = [
                Document(page_content=txt, metadata=meta or {})
                for txt, meta in zip(textos_completos, metadatos)
                if txt and txt.strip()
            ]

            docs_v = recuperador_vectores.invoke(pregunta) if docs_memoria else []
            if docs_memoria:
                recuperador_palabras = BM25Retriever.from_documents(docs_memoria)
                recuperador_palabras.k = 2
                docs_p = recuperador_palabras.invoke(pregunta)
            else:
                docs_p = []

            textos_vistos = set()
            for doc in docs_v + docs_p:
                if doc.page_content not in textos_vistos:
                    documentos_fusion.append(doc)
                    textos_vistos.add(doc.page_content)
        except Exception as e:
            print(f"   ⚠️ Aviso al consultar base vectorial en Agente 1: {e}")
        finally:
            if base_de_datos is not None:
                del base_de_datos
            gc.collect()

    # Respaldo directo con PyPDFLoader si la base de vectores no devolvió fragmentos
    if not documentos_fusion and ruta_pdf_respaldo and os.path.isfile(ruta_pdf_respaldo):
        try:
            cargador = PyPDFLoader(ruta_pdf_respaldo)
            paginas = cargador.load()
            documentos_fusion = paginas[:3]
        except Exception as e:
            print(f"   ⚠️ Error en lectura de respaldo PDF ({ruta_pdf_respaldo}): {e}")

    return documentos_fusion[:3]

def _parsear_json_seguro(respuesta_bruta):
    if not respuesta_bruta or not respuesta_bruta.strip():
        raise ValueError("Respuesta vacía del modelo LLM.")
    texto_limpio = respuesta_bruta.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(texto_limpio)
    except json.JSONDecodeError:
        coincidencia = re.search(r'\{[\s\S]*\}', texto_limpio)
        if coincidencia:
            return json.loads(coincidencia.group(0))
        raise

def extraer_metadatos(ruta_pdf=None):
    print("🧠 Inicializando el motor del Agente Documentalista (Modo Extractor)...")
    if ruta_pdf:
        ruta_pdf = ruta_pdf.strip().strip('"').strip("'")

    pregunta_busqueda = "Aprobación definitiva inicial fase tramitación resolución acuerdo pleno fecha firma"
    documentos_encontrados = buscar_fusion_hibrida(pregunta_busqueda, ruta_pdf_respaldo=ruta_pdf)

    if not documentos_encontrados:
        print("   ⚠️ No se encontraron fragmentos de texto para analizar en el proyecto.")
        return {
            "fase_tramitacion": "NO_ENCONTRADA",
            "fecha_aprobacion": "NO_ENCONTRADA"
        }

    textos_con_fuentes = []
    for doc in documentos_encontrados:
        origen = os.path.basename(doc.metadata.get('source', 'desconocido'))
        pagina = doc.metadata.get('page', 'N/A')
        textos_con_fuentes.append(f"[Archivo: {origen} | Pág: {pagina}]\n{doc.page_content}")

    texto_contexto = "\n\n".join(textos_con_fuentes)

    try:
        respuesta_bruta = cadena.invoke({"context": texto_contexto})
        diccionario_datos = _parsear_json_seguro(respuesta_bruta)
        return {
            "fase_tramitacion": diccionario_datos.get("fase_tramitacion", "NO_ENCONTRADA"),
            "fecha_aprobacion": diccionario_datos.get("fecha_aprobacion", "NO_ENCONTRADA")
        }
    except Exception as e:
        print(f"[Error Crítico] Fallo al leer el JSON del Agente 1: {e}")
        return {"error": "El LLM no devolvió JSON válido"}

if __name__ == "__main__":
    print("Iniciando Agente 1 (Documentalista)...")
    resultado = extraer_metadatos()
    print("\n🤖 Datos extraídos listos para el Orquestador:")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
