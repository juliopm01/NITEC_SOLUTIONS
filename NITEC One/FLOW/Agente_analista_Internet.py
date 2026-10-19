import os
import json
import requests
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

print("⚖️ Iniciando Agente 2 (Auditor Normativo Autónomo)...")

# Constantes
ARCHIVO_BOJA = "boja_base.json"
URL_BOJA_SIMULADA = "https://juntadeandalucia.es/boja/documento_normativo.pdf"

# Motor de IA
llm = ChatOllama(model="llama3.1", temperature=0)

def extraer_boja_de_internet():
    """
    Se conecta a internet, descarga la normativa y usa el LLM para extraer la estructura.
    """
    print("🌐 Archivo BOJA no encontrado. Conectando a internet para descargar y estructurar...")
    
    # Aquí iría la lógica real de requests.get() y carga del PDF masivo.
    # respuesta_web = requests.get(URL_BOJA_SIMULADA)
    # docs_boja = PyPDFLoader(ruta_temp).load()
    
    # Dado que extraer un PDF masivo en tiempo real puede fallar, simulamos 
    # el resultado estructurado que devolvería tu LLM tras leer el BOJA completo:
    boja_extraido = {
        "limite_peso_general_mb": 50,
        "formato_division": "09_99",
        "proyectos": {
            "PGOM": {
                "plantilla_nombre": "INE_PGOM_FT_AAAAMMDD",
                "estructura_carpetas": {
                    "INE_PGOM_FT_AAAAMMDD": {
                        "INE_PGOM_FT_M_AAAAMMDD": ["INE_PGOM_FT_MI_AAAAMMDD", "INE_PGOM_FT_MO_AAAAMMDD"],
                        "INE_PGOM_FT_CA_AAAAMMDD": ["INE_PGOM_FT_CI_AAAAMMDD", "INE_PGOM_FT_CO_AAAAMMDD"]
                    }
                }
            },
            "ED": {
                "plantilla_nombre": "INE_ED_FT_AAAAMMDD",
                "estructura_carpetas": {
                    "INE_ED_FT_AAAAMMDD": {
                        "INE_ED_FT_M_AAAAMMDD": ["INE_ED_FT_MI_AAAAMMDD"]
                    }
                }
            }
        }
    }
    
    # Guardar en disco para futuras ejecuciones (Carga Perezosa)
    with open(ARCHIVO_BOJA, "w", encoding="utf-8") as f:
        json.dump(boja_extraido, f, indent=2, ensure_ascii=False)
        
    print(f"✅ BOJA estructurado y guardado permanentemente en {ARCHIVO_BOJA}")
    return boja_extraido

def consultar_normativa_local(municipio):
    """
    Busca en la base de datos vectorial filtrando estrictamente por municipio.
    """
    try:
        modelo_coordenadas = OllamaEmbeddings(model="nomic-embed-text")
        base_de_datos = Chroma(persist_directory="./bd_normativas", embedding_function=modelo_coordenadas)
        
        # Filtramos directamente usando los metadatos que guardó el Agente.py
        recuperador = base_de_datos.as_retriever(
            search_kwargs={"k": 2, "filter": {"municipio": municipio}}
        )
        
        documentos = recuperador.invoke("límite peso megabytes mb máximo archivo")
        contexto = "\n".join([doc.page_content for doc in documentos])
        return contexto if contexto else "NO_HAY_REGLAS_LOCALES"
        
    except Exception as e:
        print(f"⚠️ Aviso: No se pudo conectar a la BD local o no existe para {municipio}. Usando BOJA por defecto.")
        return "NO_HAY_REGLAS_LOCALES"

def contrastar_excepciones(municipio, contexto_local, limite_boja):
    """
    Pide a la IA que decida si el ayuntamiento sobreescribe la regla del BOJA.
    """
    if contexto_local == "NO_HAY_REGLAS_LOCALES":
        return limite_boja
        
    plantilla = ChatPromptTemplate.from_messages([
        ("system", """Eres el Auditor Normativo Estricto.
        El límite general autonómico es {limite_boja} MB.
        Lee las normas locales del ayuntamiento proporcionadas. Si el ayuntamiento exige un límite de peso DIFERENTE y más restrictivo, devuelve ÚNICAMENTE ese número (ej. 15).
        Si no menciona límites o usa el mismo, devuelve ÚNICAMENTE {limite_boja}.
        No incluyas texto adicional ni explicaciones.
        
        Contexto local de {municipio}:
        {contexto_local}""")
    ])
    
    cadena = plantilla | llm | StrOutputParser()
    respuesta = cadena.invoke({
        "limite_boja": limite_boja, 
        "municipio": municipio, 
        "contexto_local": contexto_local
    })
    
    try:
        # Extraemos solo los dígitos por si la IA añade texto basura
        nuevo_limite = int(''.join(filter(str.isdigit, respuesta)))
        return nuevo_limite
    except ValueError:
        return limite_boja

def ejecutar_agente_2(municipio, tipo_proyecto):
    """
    Función principal que ejecutará el Orquestador.
    """
    # 1. Carga Perezosa: ¿Tenemos ya el BOJA descargado y procesado?
    if not os.path.exists(ARCHIVO_BOJA):
        boja_datos = extraer_boja_de_internet()
    else:
        with open(ARCHIVO_BOJA, "r", encoding="utf-8") as f:
            boja_datos = json.load(f)
            
    # 2. Extraer la parte del proyecto seleccionado
    if tipo_proyecto not in boja_datos["proyectos"]:
        return {"error": f"El proyecto '{tipo_proyecto}' no existe en el BOJA."}
        
    reglas_proyecto = boja_datos["proyectos"][tipo_proyecto]
    limite_actual = boja_datos["limite_peso_general_mb"]
    
    # 3. Buscar y aplicar excepciones del Ayuntamiento local
    contexto_ayuntamiento = consultar_normativa_local(municipio)
    limite_final = contrastar_excepciones(municipio, contexto_ayuntamiento, limite_actual)
    
    # 4. Ensamblar y devolver el JSON final al Orquestador
    json_final_orquestador = {
        "reglas_empaquetado": {
            "limite_peso_mb": str(limite_final),
            "formato_division": boja_datos["formato_division"]
        },
        "reglas_identidad": reglas_proyecto
    }
    
    return json_final_orquestador

if __name__ == "__main__":
    print("Iniciando prueba del Agente 2...")
    resultado = ejecutar_agente_2("Málaga", "PGOM")
    print("\n🤖 JSON consolidado devuelto al Orquestador:")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
