import os
import json
from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

ARCHIVO_BOJA = "boja_base.json"
llm = ChatOllama(model="llama3.1", temperature=0)

def analizar_indice_y_extraer_boja(ruta_pdf):
    cargador = PyPDFLoader(ruta_pdf)
    paginas = cargador.load()
    
    texto_inicial = "\n".join([p.page_content for p in paginas[:15]])
    
    plantilla_indice = ChatPromptTemplate.from_messages([
        ("system", """Busca en este texto inicial el número de página donde se detalla la 'Estructura de proyectos'.
        Devuelve ÚNICAMENTE el número de página (ej. 25). Si no lo encuentras, devuelve 0.
        Texto: {texto}""")
    ])
    
    respuesta_indice = (plantilla_indice | llm | StrOutputParser()).invoke({"texto": texto_inicial})
    try:
        num_pagina = int(''.join(filter(str.isdigit, respuesta_indice)))
    except ValueError:
        num_pagina = 0
        
    if num_pagina > 0 and num_pagina < len(paginas):
        inicio = max(0, num_pagina - 2)
        fin = min(len(paginas), num_pagina + 3)
        bloque_texto = "\n".join([p.page_content for p in paginas[inicio:fin]])
    else:
        bloque_texto = "\n".join([p.page_content for p in paginas[:30]])

    plantilla_extraccion = ChatPromptTemplate.from_messages([
        ("system", """Eres un Auditor Normativo Experto. Extrae TODOS los tipos de proyectos urbanísticos.
        FORMATO ESTRICTO JSON:
        {{
          "limite_peso_general_mb": 50,
          "formato_division": "09_99",
          "proyectos": {{
            "SIGLAS_DEL_PROYECTO": {{
              "plantilla_nombre": "...",
              "estructura_carpetas": {{}}
            }}
          }}
        }}
        Texto: {bloque_texto}""")
    ])
    
    json_extraido_texto = (plantilla_extraccion | llm | StrOutputParser()).invoke({"bloque_texto": bloque_texto})
    
    texto_limpio = json_extraido_texto.strip()
    if texto_limpio.startswith("```json"):
        texto_limpio = texto_limpio[7:-3].strip()
    elif texto_limpio.startswith("```"):
         texto_limpio = texto_limpio[3:-3].strip()
        
    return json.loads(texto_limpio)

def extraer_boja_de_local(ruta_pdf):
    try:
        boja_extraido = analizar_indice_y_extraer_boja(ruta_pdf)
    except Exception:
        boja_extraido = {
            "limite_peso_general_mb": 50, "formato_division": "09_99",
            "proyectos": {"PGOM": {"plantilla_nombre": "INE_PGOM_FT_AAAAMMDD", "estructura_carpetas": {}}}
        }
    
    with open(ARCHIVO_BOJA, "w", encoding="utf-8") as f:
        json.dump(boja_extraido, f, indent=2, ensure_ascii=False)
        
    return boja_extraido

def consultar_normativa_local(municipio):
    try:
        modelo_coordenadas = OllamaEmbeddings(model="nomic-embed-text")
        base_de_datos = Chroma(persist_directory="./bd_normativas", embedding_function=modelo_coordenadas)
        recuperador = base_de_datos.as_retriever(search_kwargs={"k": 2, "filter": {"municipio": municipio}})
        documentos = recuperador.invoke("límite peso megabytes mb máximo archivo")
        contexto = "\n".join([doc.page_content for doc in documentos])
        return contexto if contexto else "NO_HAY_REGLAS_LOCALES"
    except Exception:
        return "NO_HAY_REGLAS_LOCALES"

def contrastar_excepciones(municipio, contexto_local, limite_boja):
    plantilla = ChatPromptTemplate.from_messages([
        ("system", """El límite general es {limite_boja} MB.
        Lee las normas locales. Si exige un límite DIFERENTE y más restrictivo, devuelve ÚNICAMENTE ese número (ej. 15).
        Si no, devuelve ÚNICAMENTE {limite_boja}. No incluyas explicaciones.
        Contexto local: {contexto_local}""")
    ])
    respuesta = (plantilla | llm | StrOutputParser()).invoke({"limite_boja": limite_boja, "municipio": municipio, "contexto_local": contexto_local})
    try: return int(''.join(filter(str.isdigit, respuesta)))
    except ValueError: return limite_boja

def ejecutar_agente_2(municipio, tipo_proyecto, ruta_boja_pdf=None, limite_manual_mb=None):
    if not os.path.exists(ARCHIVO_BOJA):
        if not ruta_boja_pdf or not os.path.exists(ruta_boja_pdf):
            return {"estado": "ERROR", "mensaje": "No existe boja_base.json y no se proporcionó un PDF válido."}
        boja_datos = extraer_boja_de_local(ruta_boja_pdf)
    else:
        with open(ARCHIVO_BOJA, "r", encoding="utf-8") as f:
            boja_datos = json.load(f)
            
    if tipo_proyecto not in boja_datos["proyectos"]:
        return {"estado": "ERROR", "mensaje": f"El proyecto '{tipo_proyecto}' no existe en el BOJA."}
        
    reglas_proyecto = boja_datos["proyectos"][tipo_proyecto]
    limite_actual = boja_datos["limite_peso_general_mb"]
    
    contexto_ayuntamiento = consultar_normativa_local(municipio)
    
    if contexto_ayuntamiento == "NO_HAY_REGLAS_LOCALES":
        # GUI READY: El Agente nunca interrumpe con input(). Devuelve un flag al orquestador.
        if limite_manual_mb is None:
            return {"estado": "REQUIERE_LIMITE_MANUAL", "mensaje": f"Falta límite local para {municipio}"}
        else:
            limite_final = limite_manual_mb
    else:
        limite_final = contrastar_excepciones(municipio, contexto_ayuntamiento, limite_actual)
    
    return {
        "estado": "COMPLETADO",
        "reglas_empaquetado": {"limite_peso_mb": str(limite_final), "formato_division": boja_datos["formato_division"]},
        "reglas_identidad": reglas_proyecto
    }
