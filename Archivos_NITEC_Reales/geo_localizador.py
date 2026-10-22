import json
import os

ARCHIVO_MUNICIPIOS = "municipios_espana.json"

def cargar_base_datos():
    # Generamos una mini base de datos de ejemplo si no existe. 
    if not os.path.exists(ARCHIVO_MUNICIPIOS):
        datos_ejemplo = {
            "málaga": {"provincia": "Málaga", "comunidad": "Andalucía"},
            "marbella": {"provincia": "Málaga", "comunidad": "Andalucía"},
            "dos hermanas": {"provincia": "Sevilla", "comunidad": "Andalucía"},
            "sevilla": {"provincia": "Sevilla", "comunidad": "Andalucía"},
            "madrid": {"provincia": "Madrid", "comunidad": "Comunidad de Madrid"},
            "barcelona": {"provincia": "Barcelona", "comunidad": "Cataluña"},
            "valencia": {"provincia": "Valencia", "comunidad": "Comunidad Valenciana"}
        }
        with open(ARCHIVO_MUNICIPIOS, "w", encoding="utf-8") as f:
            json.dump(datos_ejemplo, f, ensure_ascii=False, indent=2)
        return datos_ejemplo
    
    with open(ARCHIVO_MUNICIPIOS, "r", encoding="utf-8") as f:
        return json.load(f)

def obtener_datos_geograficos(nombre_municipio):
    db = cargar_base_datos()
    # Limpiamos el texto: minúsculas y sin espacios extra para asegurar coincidencia
    municipio_limpio = nombre_municipio.strip().lower()
    
    if municipio_limpio in db:
        return db[municipio_limpio]
    else:
        return None