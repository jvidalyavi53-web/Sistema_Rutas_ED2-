"""
Punto de entrada de la aplicación
==================================
Ejecuta:  py run.py

Crea la aplicación mediante el *application factory* y la levanta.
El puerto 5057 evita el conflicto con otra app Flask del usuario en el 5000.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5057, debug=True)
