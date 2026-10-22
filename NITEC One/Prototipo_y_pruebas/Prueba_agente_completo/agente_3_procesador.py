import os
from pypdf import PdfReader, PdfWriter

def procesar_y_dividir_pdfs(ruta_carpeta, limite_mb=20):
    print(f"📂 Escaneando PDFs en '{ruta_carpeta}' para evaluación de tamaño (Límite: {limite_mb} MB)...")
    
    if not os.path.exists(ruta_carpeta):
        print("   ❌ La carpeta no existe.")
        return []

    archivos_pdf = [f for f in os.listdir(ruta_carpeta) if f.lower().endswith('.pdf')]
    resultados = []

    for archivo in archivos_pdf:
        ruta_pdf = os.path.join(ruta_carpeta, archivo)
        peso_bytes = os.path.getsize(ruta_pdf)
        peso_mb = peso_bytes / (1024 * 1024)
        
        print(f"   📄 Archivo: {archivo} ({peso_mb:.2f} MB)")
        
        if peso_mb <= limite_mb:
            print(f"      ✅ El archivo cumple con el límite. No requiere división.")
            resultados.append({"archivo": archivo, "estado": "OK", "tomos": [archivo]})
        else:
            print(f"      ✂️ Supera el límite. Iniciando división por páginas con pypdf...")
            reader = PdfReader(ruta_pdf)
            total_paginas = len(reader.pages)
            
            paginas_por_tomo = max(1, int(total_paginas * (limite_mb / peso_mb)))
            
            tomo_num = 1
            tomos_generados = []
            
            writer = PdfWriter()
            contador_paginas_tomo = 0
            
            for i, pagina in enumerate(reader.pages):
                writer.add_page(pagina)
                contador_paginas_tomo += 1
                
                if contador_paginas_tomo >= paginas_por_tomo or (i + 1) == total_paginas:
                    nombre_base, ext = os.path.splitext(archivo)
                    nombre_tomo = f"{nombre_base}_tomo_{tomo_num}{ext}"
                    ruta_tomo = os.path.join(ruta_carpeta, nombre_tomo)
                    
                    with open(ruta_tomo, "wb") as f_out:
                        writer.write(f_out)
                    
                    tomos_generados.append(nombre_tomo)
                    print(f"         📦 Generado: {nombre_tomo} ({contador_paginas_tomo} páginas)")
                    
                    writer = PdfWriter()
                    contador_paginas_tomo = 0
                    tomo_num += 1
            
            resultados.append({"archivo": archivo, "estado": "DIVIDIDO", "tomos": tomos_generados})

    return resultados
