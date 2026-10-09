import os
import json
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, messages_to_dict, messages_from_dict
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever

print("🧠 Inicializando el motor del Agente Documentalista (Versión Optimizada)...")

# 1. Base de datos y Recuperadores
modelo_coordenadas = OllamaEmbeddings(model="nomic-embed-text")
base_de_datos = Chroma(persist_directory="./bd_vectores", embedding_function=modelo_coordenadas)

# ⚡ OPTIMIZACIÓN: Reducido a 2 fragmentos para no saturar la VRAM
recuperador_vectores = base_de_datos.as_retriever(search_kwargs={"k": 2})

datos_guardados = base_de_datos.get()
textos_completos = datos_guardados.get('documents', [])
metadatos = datos_guardados.get('metadatas', [])

docs_memoria = [Document(page_content=txt, metadata=meta) for txt, meta in zip(textos_completos, metadatos)]

if docs_memoria:
    recuperador_palabras = BM25Retriever.from_documents(docs_memoria)
    # ⚡ OPTIMIZACIÓN: Reducido a 2 fragmentos
    recuperador_palabras.k = 2
else:
    recuperador_palabras = None

def buscar_fusion_hibrida(pregunta):
    if not recuperador_palabras:
        # ⚡ OPTIMIZACIÓN: Límite de seguridad de 3 fragmentos en total
        return recuperador_vectores.invoke(pregunta)[:3]
        
    docs_v = recuperador_vectores.invoke(pregunta)
    docs_p = recuperador_palabras.invoke(pregunta)
    
    fusion = []
    textos_vistos = set()
    for doc in docs_v + docs_p:
        if doc.page_content not in textos_vistos:
            fusion.append(doc)
            textos_vistos.add(doc.page_content)
            
    # ⚡ OPTIMIZACIÓN: Solo pasamos los 3 mejores fragmentos (aprox 3000 caracteres) a Llama
    return fusion[:3]

# 2. Cerebro
llm = ChatOllama(model="llama3.1", temperature=0, num_ctx=16000)

plantilla = ChatPromptTemplate.from_messages([
    ("system", """Eres el Agente Documentalista de un sistema automatizado.
    Responde a la pregunta basándote ÚNICAMENTE en este contexto extraído de los documentos del proyecto:
    
    {context}
    
    Tu respuesta DEBE ser EXCLUSIVAMENTE un objeto JSON válido. No incluyas texto antes ni después. No saludes.
    Usa estrictamente esta estructura:
    {{
        "respuesta": "Tu respuesta a la pregunta o 'No lo sé'",
        "fuentes_utilizadas": [
            {{
                "archivo": "nombre_del_archivo.ext",
                "categoria": "CATEGORIA_DEL_ARCHIVO",
                "pagina": numero_de_pagina_o_null
            }}
        ]
    }}"""),
    MessagesPlaceholder(variable_name="historial"),
    ("human", "{question}")
])

cadena = plantilla | llm | StrOutputParser()
ARCHIVO_MEMORIA = "memoria_chat.json"

# --- 3. LA FUNCIÓN MAESTRA (API INTERNA) ---
def consultar(pregunta):
    historial_chat = []
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                datos_memoria = json.load(f)
                historial_chat = messages_from_dict(datos_memoria)
        except Exception:
            pass

    documentos_encontrados = buscar_fusion_hibrida(pregunta)
    textos_con_fuentes = []
    for doc in documentos_encontrados:
        origen = os.path.basename(doc.metadata.get('source', 'desconocido'))
        categoria = doc.metadata.get('categoria', 'OTRO')
        pagina = doc.metadata.get('page')
        
        if pagina is not None:
            etiqueta_fuente = f"Archivo: {origen} | Categoría: {categoria} | Página: {pagina + 1}"
        else:
            etiqueta_fuente = f"Archivo: {origen} | Categoría: {categoria}"
            
        textos_con_fuentes.append(f"[{etiqueta_fuente}]\n{doc.page_content}")
        
    texto_contexto = "\n\n".join(textos_con_fuentes)
    
    respuesta_bruta = cadena.invoke({
        "context": texto_contexto,
        "historial": historial_chat,
        "question": pregunta
    })
    
    diccionario_datos = {"error": "El LLM no devolvió JSON válido", "texto_bruto": respuesta_bruta}
    try:
        texto_limpio = respuesta_bruta.replace("```json", "").replace("```", "").strip()
        diccionario_datos = json.loads(texto_limpio)
    except Exception:
        pass
        
    historial_chat.append(HumanMessage(content=pregunta))
    historial_chat.append(AIMessage(content=respuesta_bruta))
    if len(historial_chat) > 6:
        historial_chat = historial_chat[-6:]
        
    with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(messages_to_dict(historial_chat), f, ensure_ascii=False, indent=2)

    return diccionario_datos


# --- 4. ZONA DE PRUEBAS (Simulador de Interfaz) ---
if __name__ == "__main__":
    print("\n⚙️ MODO PRUEBA MANUAL ACTIVADO (Banco de pruebas del motor)")
    print("Escribe 'salir' para apagar el motor.\n")
    print("-" * 50)
    
    while True:
        pregunta_prueba = input("Administrativo (Tú): ")
        if pregunta_prueba.lower() == 'salir':
            break
            
        print("⏳ Consultando al Agente Documentalista en segundo plano...")
        resultado = consultar(pregunta_prueba)
        
        print("\n🤖 Respuesta estructurada (JSON listo para código):")
        print(json.dumps(resultado, indent=4, ensure_ascii=False))
        print("-" * 50)