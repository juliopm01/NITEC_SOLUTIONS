import os

def procesar_pdf(ruta_pdf, limite_mb):
    limite_mb = float(limite_mb)
    if os.path.exists(ruta_pdf):
        peso_bytes = os.path.getsize(ruta_pdf)
        peso_mb = peso_bytes / (1024 * 1024)
        print(f"El archivo pesa {peso_mb:.2f} MB.")
        
        if peso_mb > limite_mb:
            print("El archivo supera el límite. Iniciando división con pypdf...")
            # Aquí contaremos las páginas y dividiremos
        else:
            print("El archivo cumple con el peso normativo.")
    else:
        print("El archivo no existe.")
