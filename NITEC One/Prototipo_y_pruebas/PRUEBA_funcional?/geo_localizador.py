import json
import os
import unicodedata

ARCHIVO_MUNICIPIOS = "municipios_espana.json"

def _normalizar(texto):
    texto = texto.strip().lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

def cargar_base_datos():
    datos_base = {
        "málaga": {"provincia": "Málaga", "comunidad": "Andalucía"},
        "marbella": {"provincia": "Málaga", "comunidad": "Andalucía"},
        "estepona": {"provincia": "Málaga", "comunidad": "Andalucía"},
        "mijas": {"provincia": "Málaga", "comunidad": "Andalucía"},
        "fuengirola": {"provincia": "Málaga", "comunidad": "Andalucía"},
        "vélez-málaga": {"provincia": "Málaga", "comunidad": "Andalucía"},
        "dos hermanas": {"provincia": "Sevilla", "comunidad": "Andalucía"},
        "sevilla": {"provincia": "Sevilla", "comunidad": "Andalucía"},
        "córdoba": {"provincia": "Córdoba", "comunidad": "Andalucía"},
        "granada": {"provincia": "Granada", "comunidad": "Andalucía"},
        "cádiz": {"provincia": "Cádiz", "comunidad": "Andalucía"},
        "huelva": {"provincia": "Huelva", "comunidad": "Andalucía"},
        "jaén": {"provincia": "Jaén", "comunidad": "Andalucía"},
        "almería": {"provincia": "Almería", "comunidad": "Andalucía"},
        "madrid": {"provincia": "Madrid", "comunidad": "Comunidad de Madrid"},
        "barcelona": {"provincia": "Barcelona", "comunidad": "Cataluña"},
        "valencia": {"provincia": "Valencia", "comunidad": "Comunidad Valenciana"}
    }
    if not os.path.exists(ARCHIVO_MUNICIPIOS):
        with open(ARCHIVO_MUNICIPIOS, "w", encoding="utf-8") as f:
            json.dump(datos_base, f, ensure_ascii=False, indent=2)
        return datos_base
    
    try:
        with open(ARCHIVO_MUNICIPIOS, "r", encoding="utf-8") as f:
            datos_disco = json.load(f)
            datos_base.update(datos_disco)
            return datos_base
    except Exception:
        return datos_base

def obtener_datos_geograficos(nombre_municipio):
    if not nombre_municipio:
        return None
    db = cargar_base_datos()
    municipio_limpio = nombre_municipio.strip().lower()
    
    # Coincidencia exacta primero
    if municipio_limpio in db:
        return db[municipio_limpio]
    
    # Coincidencia insensible a tildes
    municipio_norm = _normalizar(nombre_municipio)
    for clave, valor in db.items():
        if _normalizar(clave) == municipio_norm:
            return valor
            
    return None
