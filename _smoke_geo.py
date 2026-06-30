"""Prueba de humo de la integracion del mapa real (no toca mapa.json real)."""

import os
import tempfile

os.environ["MAPA_FILE"] = os.path.join(
    tempfile.gettempdir(), "_smoke_mapa.json"
)
os.environ.pop("MAPTILER_API_KEY", None)  # forzar el respaldo OSM
# Prueba hermetica: sin enrutamiento (no se hacen llamadas de red a OSRM).
os.environ["ROUTING_HABILITADO"] = "false"

# Estado limpio: descartar cualquier mapa/cache temporal de una corrida
# anterior para que la prueba sea repetible (parte del ejemplo de 9 ciudades).
base, _ = os.path.splitext(os.environ["MAPA_FILE"])
for f in (os.environ["MAPA_FILE"], f"{base}_rutas_viales.json"):
    if os.path.exists(f):
        os.remove(f)

from app import create_app  # noqa: E402
from app.models.geo import Coordenada  # noqa: E402

fallos = []


def check(nombre, cond):
    estado = "OK " if cond else "FALLA"
    if not cond:
        fallos.append(nombre)
    print(f"[{estado}] {nombre}")


# --- Modelo: validacion de coordenadas ---
try:
    Coordenada(999, 0)
    check("Coordenada rechaza latitud invalida", False)
except ValueError:
    check("Coordenada rechaza latitud invalida", True)
c = Coordenada(-16.5, -68.15)
check("Coordenada valida en Bolivia", c.en_bolivia())
check("Coordenada to_geojson [lon,lat]", c.to_geojson() == [-68.15, -16.5])

app = create_app()
cli = app.test_client()

# --- /api/map-config ---
r = cli.get("/api/map-config")
j = r.get_json()
check("map-config responde 200", r.status_code == 200)
check(
    "map-config usa respaldo OSM sin clave",
    j["provider"] == "osm" and j["hasKey"] is False,
)
check("map-config NO expone styleUrl sin clave", "styleUrl" not in j)
check("map-config trae center y zoom", "center" in j and "zoom" in j)

# --- /api/geojson ---
r = cli.get("/api/geojson")
g = r.get_json()
check("geojson responde 200", r.status_code == 200)
check(
    "geojson FeatureCollection ciudades",
    g["ciudades"]["type"] == "FeatureCollection",
)
check(
    "geojson 9 ciudades georreferenciadas", len(g["ciudades"]["features"]) == 9
)
check("geojson 12 carreteras", len(g["carreteras"]["features"]) == 12)
f0 = g["ciudades"]["features"][0]
check(
    "ciudad es Point con [lon,lat]",
    f0["geometry"]["type"] == "Point"
    and len(f0["geometry"]["coordinates"]) == 2,
)
car0 = g["carreteras"]["features"][0]
check("carretera es LineString", car0["geometry"]["type"] == "LineString")
check("geojson trae meta routing", "routing" in g)
check(
    "routing deshabilitado en prueba hermetica",
    g["routing"]["habilitado"] is False,
)
check(
    "sin routing la carretera es recta (2 puntos)",
    car0["properties"]["trazado"] == "recta"
    and len(car0["geometry"]["coordinates"]) == 2,
)
check("sin routing no hay carreteras fallidas", g["routing"]["fallidos"] == [])

# --- alta de ciudad con coordenadas validas ---
r = cli.post(
    "/api/ciudades",
    json={
        "nombre": "Yacuiba",
        "tipo": "comercial",
        "lat": -22.01,
        "lon": -63.68,
    },
)
check(
    "alta ciudad con coords OK",
    r.status_code == 200 and "error" not in r.get_json(),
)
r = cli.get("/api/geojson")
check(
    "nueva ciudad aparece en geojson",
    len(r.get_json()["ciudades"]["features"]) == 10,
)

# --- alta con coordenada invalida -> error 400 ---
r = cli.post("/api/ciudades", json={"nombre": "Mala", "lat": 200, "lon": 0})
check(
    "alta con coord invalida rechazada",
    r.status_code == 400 and "error" in r.get_json(),
)

# --- /api/ciudad incluye coordenada ---
r = cli.get("/api/ciudad/La%20Paz")
check(
    "detalle ciudad incluye coordenada",
    r.get_json().get("coordenada") is not None,
)

# --- persistencia: recargar el servicio lee las coords del disco ---
from app.services.mapa_service import MapaService  # noqa: E402

s2 = MapaService(os.environ["MAPA_FILE"])
check(
    "persistencia conserva coordenada",
    s2.grafo.obtener_coordenada("Yacuiba") is not None,
)

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} fallo(s) -> {fallos}")
    raise SystemExit(1)
print("RESULTADO: todas las pruebas OK")
