import os
import re
import gc
import json
import shutil
import unicodedata
from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

ARCHIVO_BOJA = "boja_base.json"
ARCHIVO_AYUNTAMIENTOS = "normativas_ayuntamientos.json"
CARPETA_LEYES = "./normativas_pdf"
RUTA_BD_LEGAL = "./bd_normativas"

llm = ChatOllama(model="llama3.1", temperature=0, format="json")

def _normalizar(texto):
    if not texto:
        return ""
    texto = texto.strip().lower().replace(" ", "_")
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

def _extraer_json_de_texto(texto):
    if not texto or not texto.strip():
        raise ValueError("El LLM devolvió una respuesta vacía.")
    texto_limpio = texto.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(texto_limpio)
    except json.JSONDecodeError:
        coincidencia = re.search(r'\{[\s\S]*\}', texto_limpio)
        if coincidencia:
            return json.loads(coincidencia.group(0))
        raise

def _localizar_pdf_boja(ruta_pdf=None):
    """Localiza el PDF del BOJA ya sea por la ruta recibida o buscando en ./normativas_pdf."""
    if ruta_pdf:
        ruta_limpia = ruta_pdf.strip().strip('"').strip("'")
        if os.path.isfile(ruta_limpia):
            os.makedirs(CARPETA_LEYES, exist_ok=True)
            destino = os.path.join(CARPETA_LEYES, os.path.basename(ruta_limpia))
            if os.path.abspath(ruta_limpia) != os.path.abspath(destino):
                try:
                    shutil.copy2(ruta_limpia, destino)
                except Exception:
                    pass
            return ruta_limpia

    if os.path.exists(CARPETA_LEYES):
        pdfs = [
            os.path.join(CARPETA_LEYES, f)
            for f in os.listdir(CARPETA_LEYES)
            if f.lower().endswith('.pdf')
        ]
        if pdfs:
            return pdfs[0]
    return None

def analizar_indice_y_extraer_boja(ruta_pdf):
    print(f"   📖 [Agente 2] Analizando el PDF del BOJA ({os.path.basename(ruta_pdf)}) para generar '{ARCHIVO_BOJA}'...")
    cargador = PyPDFLoader(ruta_pdf)
    paginas = cargador.load()
    if not paginas:
        raise ValueError("No se pudo extraer texto del PDF del BOJA.")

    texto_inicial = "\n".join([p.page_content for p in paginas[:15]])
    
    plantilla_indice = ChatPromptTemplate.from_messages([
        ("system", """Busca en este texto inicial el número de página donde se detalla la 'Estructura de proyectos' o anexos técnicos.
        Devuelve ÚNICAMENTE el número de página (ej. 25). Si no lo encuentras, devuelve 0.
        Texto: {texto}""")
    ])
    
    respuesta_indice = (plantilla_indice | llm | StrOutputParser()).invoke({"texto": texto_inicial})
    try:
        num_pagina = int(''.join(filter(str.isdigit, respuesta_indice)))
    except ValueError:
        num_pagina = 0

    # Combinamos las páginas del índice detectado con aquellas páginas que mencionen palabras clave técnicas
    indices_seleccionados = set()
    if 0 < num_pagina < len(paginas):
        for idx in range(max(0, num_pagina - 2), min(len(paginas), num_pagina + 5)):
            indices_seleccionados.add(idx)

    palabras_clave = ["estructura", "megabytes", "mb", "pgom", "estudio de detalle", "ed", "pou", "plan parcial", "plantilla", "carpetas"]
    for idx, p in enumerate(paginas):
        contenido_lower = p.page_content.lower()
        if any(pal in contenido_lower for pal in palabras_clave):
            indices_seleccionados.add(idx)
            if len(indices_seleccionados) >= 25:
                break

    if not indices_seleccionados:
        indices_seleccionados = set(range(min(len(paginas), 30)))

    bloque_texto = "\n".join([paginas[i].page_content for i in sorted(indices_seleccionados)])

    plantilla_extraccion = ChatPromptTemplate.from_messages([
        ("system", """Eres un Auditor Normativo Experto. Extrae TODOS los tipos de proyectos urbanísticos que aparezcan en la normativa (ej. PGOM, POU, ED, PP, PERI, PA, PU) junto con el límite general de peso en MB y el formato de división.
        FORMATO ESTRICTO JSON (No incluyas texto fuera del JSON):
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
    
    #json_extraido_texto = (plantilla_extraccion | llm | StrOutputParser()).invoke({"bloque_texto": bloque_texto})
    #datos = _extraer_json_de_texto(json_extraido_texto)
    json_extraido_texto = (
    plantilla_extraccion | llm | StrOutputParser()
    ).invoke({"bloque_texto": bloque_texto})
    print("\n========== RESPUESTA BRUTA DE LLAMA 3.1 ==========")
    print(repr(json_extraido_texto))
    print("========== FIN DE RESPUESTA ==========\n")

    datos = _extraer_json_de_texto(json_extraido_texto)

    # Normalizar las claves de proyectos a mayúsculas
    proyectos_norm = {}
    for k, v in datos.get("proyectos", {}).items():
        proyectos_norm[k.strip().upper()] = v
    datos["proyectos"] = proyectos_norm
    datos.setdefault("limite_peso_general_mb", 50)
    datos.setdefault("formato_division", "09_99")
    datos["ruta_pdf_origen"] = ruta_pdf
    return datos

def extraer_proyecto_especifico_de_boja(tipo_proyecto, ruta_pdf):
    """Si un tipo de proyecto concreto no se extrajo en la pasada general, lo busca en el PDF del BOJA con el LLM."""
    if ruta_pdf and os.path.isfile(ruta_pdf):
        try:
            cargador = PyPDFLoader(ruta_pdf)
            paginas = cargador.load()
            relevantes = [
                p.page_content for p in paginas
                if tipo_proyecto.lower() in p.page_content.lower() or "estructura" in p.page_content.lower()
            ]
            bloque = "\n".join(relevantes[:10]) if relevantes else "\n".join([p.page_content for p in paginas[:15]])
            plantilla_proy = ChatPromptTemplate.from_messages([
                ("system", """Extrae del siguiente texto normativo la plantilla de nombre y estructura de carpetas para el proyecto urbanístico '{tipo_proyecto}'.
                Devuelve ÚNICAMENTE un JSON válido con este formato exacto:
                {{
                  "plantilla_nombre": "INE_{tipo_proyecto}_FT_AAAAMMDD",
                  "estructura_carpetas": {{}}
                }}
                Texto: {bloque_texto}""")
            ])
            resp = (plantilla_proy | llm | StrOutputParser()).invoke({
                "tipo_proyecto": tipo_proyecto,
                "bloque_texto": bloque
            })
            datos_proy = _extraer_json_de_texto(resp)
            if isinstance(datos_proy, dict) and "plantilla_nombre" in datos_proy:
                return datos_proy
        except Exception as e:
            print(f"   ⚠️ Aviso buscando '{tipo_proyecto}' en PDF del BOJA: {e}")

    return {
        "plantilla_nombre": f"INE_{tipo_proyecto}_FT_AAAAMMDD",
        "estructura_carpetas": {}
    }

def extraer_boja_de_local(ruta_pdf):
    ruta_real = _localizar_pdf_boja(ruta_pdf)
    if not ruta_real:
        raise FileNotFoundError("No se encontró el archivo PDF del BOJA.")

    boja_extraido = analizar_indice_y_extraer_boja(ruta_real)
    
    with open(ARCHIVO_BOJA, "w", encoding="utf-8") as f:
        json.dump(boja_extraido, f, indent=2, ensure_ascii=False)
    print(f"   💾 '{ARCHIVO_BOJA}' generado y guardado permanentemente por el Agente 2.")
    return boja_extraido

# --- GESTIÓN PERSISTENTE DE NORMATIVAS DE AYUNTAMIENTOS (INTRODUCIDAS A MANO) ---
def cargar_normativas_ayuntamientos():
    if os.path.exists(ARCHIVO_AYUNTAMIENTOS):
        try:
            with open(ARCHIVO_AYUNTAMIENTOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def guardar_normativa_ayuntamiento(municipio, limite_mb):
    datos = cargar_normativas_ayuntamientos()
    clave = _normalizar(municipio)
    datos[clave] = {
        "municipio": municipio.strip(),
        "limite_peso_mb": int(limite_mb)
    }
    with open(ARCHIVO_AYUNTAMIENTOS, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    print(f"   💾 Normativa del Ayuntamiento de {municipio} ({limite_mb} MB) guardada permanentemente en '{ARCHIVO_AYUNTAMIENTOS}'.")

def obtener_limite_guardado_ayuntamiento(municipio):
    datos = cargar_normativas_ayuntamientos()
    clave = _normalizar(municipio)
    if clave in datos and "limite_peso_mb" in datos[clave]:
        return int(datos[clave]["limite_peso_mb"])
    return None

def consultar_normativa_local(municipio):
    if not os.path.exists(RUTA_BD_LEGAL):
        return "NO_HAY_REGLAS_LOCALES"
    base_de_datos = None
    try:
        muni_norm = _normalizar(municipio)
        modelo_coordenadas = OllamaEmbeddings(model="nomic-embed-text")
        base_de_datos = Chroma(persist_directory=RUTA_BD_LEGAL, embedding_function=modelo_coordenadas)
        recuperador = base_de_datos.as_retriever(search_kwargs={"k": 2, "filter": {"municipio": muni_norm}})
        documentos = recuperador.invoke("límite peso megabytes mb máximo archivo")
        contexto = "\n".join([doc.page_content for doc in documentos])
        return contexto if contexto else "NO_HAY_REGLAS_LOCALES"
    except Exception:
        return "NO_HAY_REGLAS_LOCALES"
    finally:
        if base_de_datos is not None:
            del base_de_datos
        gc.collect()

def contrastar_excepciones(municipio, contexto_local, limite_boja):
    plantilla = ChatPromptTemplate.from_messages([
        ("system", """El límite general es {limite_boja} MB.
        Lee las normas locales. Si exige un límite DIFERENTE y más restrictivo, devuelve ÚNICAMENTE ese número (ej. 15).
        Si no, devuelve ÚNICAMENTE {limite_boja}. No incluyas explicaciones.
        Contexto local: {contexto_local}""")
    ])
    respuesta = (plantilla | llm | StrOutputParser()).invoke({
        "limite_boja": limite_boja,
        "municipio": municipio,
        "contexto_local": contexto_local
    })
    try:
        return int(''.join(filter(str.isdigit, respuesta)))
    except ValueError:
        return int(limite_boja)

def ejecutar_agente_2(municipio, tipo_proyecto, ruta_boja_pdf=None, limite_manual_mb=None):
    municipio = municipio.strip()
    tipo_proyecto = tipo_proyecto.strip().upper()
    print(f"⚖️ [Agente 2] Auditando normativa para el municipio: {municipio} (Proyecto: {tipo_proyecto})...")

    # 1. Cargar o generar boja_base.json directamente desde el PDF del BOJA mediante el Agente 2
    if not os.path.exists(ARCHIVO_BOJA):
        ruta_boja_real = _localizar_pdf_boja(ruta_boja_pdf)
        if not ruta_boja_real:
            return {
                "estado": "REQUIERE_BOJA_PDF",
                "mensaje": "No existe boja_base.json y se requiere la ruta al PDF del BOJA para generarlo."
            }
        try:
            boja_datos = extraer_boja_de_local(ruta_boja_real)
        except Exception as e:
            return {"estado": "ERROR", "mensaje": f"Fallo al generar boja_base.json desde el PDF: {e}"}
    else:
        with open(ARCHIVO_BOJA, "r", encoding="utf-8") as f:
            boja_datos = json.load(f)

    # Si el tipo de proyecto no estaba en la extracción inicial del BOJA, el Agente 2 lo extrae y actualiza boja_base.json
    if "proyectos" not in boja_datos or not isinstance(boja_datos["proyectos"], dict):
        boja_datos["proyectos"] = {}

    if tipo_proyecto not in boja_datos["proyectos"]:
        print(f"   🔍 El proyecto '{tipo_proyecto}' no figuraba en caché. Extrayendo del BOJA y actualizando '{ARCHIVO_BOJA}'...")
        ruta_origen = boja_datos.get("ruta_pdf_origen") or _localizar_pdf_boja(ruta_boja_pdf)
        boja_datos["proyectos"][tipo_proyecto] = extraer_proyecto_especifico_de_boja(tipo_proyecto, ruta_origen)
        with open(ARCHIVO_BOJA, "w", encoding="utf-8") as f:
            json.dump(boja_datos, f, indent=2, ensure_ascii=False)

    reglas_proyecto = boja_datos["proyectos"][tipo_proyecto]
    limite_boja = int(boja_datos.get("limite_peso_general_mb", 50))

    # 2. Comprobar si el usuario acaba de introducir un límite manual para este ayuntamiento -> Guardarlo para siempre
    if limite_manual_mb is not None:
        guardar_normativa_ayuntamiento(municipio, int(limite_manual_mb))
        limite_final = min(limite_boja, int(limite_manual_mb))
        return {
            "estado": "COMPLETADO",
            "reglas_empaquetado": {
                "limite_peso_mb": str(limite_final),
                "formato_division": boja_datos.get("formato_division", "09_99")
            },
            "reglas_identidad": reglas_proyecto
        }

    # 3. Comprobar si el ayuntamiento ya fue introducido a mano anteriormente (guardado en normativas_ayuntamientos.json)
    limite_guardado = obtener_limite_guardado_ayuntamiento(municipio)
    if limite_guardado is not None:
        print(f"   ✅ Normativa del Ayuntamiento de {municipio} recuperada de memoria ('{ARCHIVO_AYUNTAMIENTOS}'): {limite_guardado} MB.")
        limite_final = min(limite_boja, limite_guardado)
        return {
            "estado": "COMPLETADO",
            "reglas_empaquetado": {
                "limite_peso_mb": str(limite_final),
                "formato_division": boja_datos.get("formato_division", "09_99")
            },
            "reglas_identidad": reglas_proyecto
        }

    # 4. Consultar si existe en la base vectorial legal (./bd_normativas) y, si no, pedirlo a mano por consola
    contexto_ayuntamiento = consultar_normativa_local(municipio)
    if contexto_ayuntamiento == "NO_HAY_REGLAS_LOCALES":
        return {"estado": "REQUIERE_LIMITE_MANUAL", "mensaje": f"Falta límite local para {municipio}"}
    else:
        limite_final = contrastar_excepciones(municipio, contexto_ayuntamiento, limite_boja)
        guardar_normativa_ayuntamiento(municipio, limite_final)

    return {
        "estado": "COMPLETADO",
        "reglas_empaquetado": {
            "limite_peso_mb": str(limite_final),
            "formato_division": boja_datos.get("formato_division", "09_99")
        },
        "reglas_identidad": reglas_proyecto
    }
