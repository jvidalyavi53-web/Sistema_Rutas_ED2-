"""Configuracion de la aplicacion Flask."""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Carga opcional de variables desde un archivo .env (no se versiona).
# Si python-dotenv no esta instalado, la app sigue funcionando leyendo las
# variables de entorno del sistema.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "sistema-rutas-ed2-dev")
    # Archivo donde se persiste el grafo entre ejecuciones
    MAPA_FILE = os.environ.get(
        "MAPA_FILE", os.path.join(BASE_DIR, "mapa.json")
    )
    JSON_AS_ASCII = False

    # --- Mapa real (MapTiler + MapLibre GL JS) ---------------------------
    # La clave NUNCA se escribe en el codigo: se lee de la variable de
    # entorno MAPTILER_API_KEY (o del archivo .env local). Si esta vacia, el
    # frontend usa un mapa base de OpenStreetMap como respaldo de desarrollo.
    MAPTILER_API_KEY = os.environ.get("MAPTILER_API_KEY", "")
    # Estilo de MapTiler a usar (streets-v2, basic-v2, topo-v2, ...).
    MAP_STYLE = os.environ.get("MAP_STYLE", "streets-v2")
    # Vista inicial del mapa: centro de Bolivia y nivel de zoom.
    MAP_CENTER_LON = float(os.environ.get("MAP_CENTER_LON", "-64.9"))
    MAP_CENTER_LAT = float(os.environ.get("MAP_CENTER_LAT", "-16.9"))
    MAP_ZOOM = float(os.environ.get("MAP_ZOOM", "4.6"))

    # --- Enrutamiento vial (OSRM) ----------------------------------------
    # Traza las carreteras siguiendo la red vial real en vez de una linea
    # recta. Se usa OSRM (sin clave) porque la API de routing de MapTiler
    # esta en beta cerrada. El servicio corre del lado del servidor; el
    # cliente solo recibe la geometria ya calculada (no llama a OSRM).
    ROUTING_HABILITADO = (
        os.environ.get("ROUTING_HABILITADO", "true").lower() == "true"
    )
    OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org")
    ROUTING_PERFIL = os.environ.get("ROUTING_PERFIL", "driving")
    ROUTING_TIMEOUT = float(os.environ.get("ROUTING_TIMEOUT", "8"))
