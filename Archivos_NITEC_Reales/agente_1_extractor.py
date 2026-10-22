import os
import json
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever

print("🧠 Inicializando el motor del Agente Documentalista (Modo Extractor)...")

# 1. Base de datos y Recuperadores (Igual de protegidos para la RAM)
modelo_coordenadas = OllamaEmbeddings(model="nomic-embed-text")
base_de_datos = Chroma(persist_directory="./bd_vectores", embedding_function=modelo_coordenadas)

recuperador_vectores = base_de_datos.as_retriever(search_kwargs={"k": 2})

datos_guardados = base_de_datos.get()
textos_completos = datos_guardados.get('documents', [])
metadatos = datos_guardados.get('metadatas', [])

docs_memoria = [Document(page_content=txt, metadata=meta) for txt, meta in zip(textos_completos, metadatos)]

if docs_memoria:
    recuperador_palabras = BM25Retriever.from_documents(docs_memoria)
    recuperador_palabras.k = 2
else:
    recuperador_palabras = None

def buscar_fusion_hibrida(pregunta):
    if not recuperador_palabras:
        return recuperador_vectores.invoke(pregunta)[:3]
        
    docs_v = recuperador_vectores.invoke(pregunta)
    docs_p = recuperador_palabras.invoke(pregunta)
    
    fusion = []
    textos_vistos = set()
    for doc in docs_v + docs_p:
        if doc.page_content not in textos_vistos:
            fusion.append(doc)
            textos_vistos.add(doc.page_content)
            
    return fusion[:3]

# 2. Cerebro y Prompt Maestro (Blindado con reglas de negocio)
llm = ChatOllama(model="llama3.1", temperature=0, num_ctx=16000)

plantilla = ChatPromptTemplate.from_messages([
    ("system", """Eres el Agente Documentalista (Rastreador Implacable).
    Tu objetivo es extraer dos datos legales específicos del proyecto urbanístico basándote ÚNICAMENTE en el contexto proporcionado.
    
    Reglas estrictas:
    1. Fase de Tramitación: Detecta la fase (ej. AI para Aprobación Inicial, AD para Aprobación Definitiva).
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

# --- 3. LA FUNCIÓN MAESTRA (Modo Francotirador sin Chat) ---
def extraer_metadatos(ruta_pdf=None):
    # NOTA: Adaptado para ser importado por el orquestador bajo el nombre extraer_metadatos.
    # Lanzamos una "búsqueda señuelo" para atraer los fragmentos que nos interesan de la base de datos
    pregunta_busqueda = "Aprobación definitiva inicial fase tramitación resolución acuerdo pleno fecha firma"
    
    documentos_encontrados = buscar_fusion_hibrida(pregunta_busqueda)
    textos_con_fuentes = []
    for doc in documentos_encontrados:
        origen = os.path.basename(doc.metadata.get('source', 'desconocido'))
        pagina = doc.metadata.get('page', 'N/A')
        textos_con_fuentes.append(f"[Archivo: {origen} | Pág: {pagina}]\n{doc.page_content}")
        
    texto_contexto = "\n\n".join(textos_con_fuentes)
    
    respuesta_bruta = cadena.invoke({
        "context": texto_contexto
    })
    
    diccionario_datos = {"error": "El LLM no devolvió JSON válido"}
    try:
        texto_limpio = respuesta_bruta.replace("```json", "").replace("```", "").strip()
        diccionario_datos = json.loads(texto_limpio)
    except Exception as e:
        print(f"[Error Crítico] Fallo al leer el JSON del Agente 1: {e}")
        
    return diccionario_datos

if __name__ == "__main__":
    print("Iniciando Agente 1 (Documentalista)...")
    resultado = extraer_metadatos()
    
    print("\n🤖 Datos extraídos listos para el Orquestador:")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))