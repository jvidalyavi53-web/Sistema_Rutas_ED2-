"""Prueba del enrutamiento vial (OSRM). REQUIERE INTERNET.

Verifica que las carreteras se tracen siguiendo vias reales (no en linea
recta) en distintos escenarios y que el manejo de errores funcione cuando el
servicio de rutas no responde. No toca el mapa.json real (usa un temporal).
"""

import math
import os
import tempfile

from app.models.geo import Coordenada  # noqa: E402
from app.services.mapa_service import MapaService  # noqa: E402
from app.services.routing_service import RoutingService  # noqa: E402

fallos = []


def check(nombre, cond):
    estado = "OK " if cond else "FALLA"
    if not cond:
        fallos.append(nombre)
    print(f"[{estado}] {nombre}")


def km_recta(a, b):
    """Distancia aproximada en linea recta (haversine, solo de referencia)."""
    r = 6371.0
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    s = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(a.lat))
        * math.cos(math.radians(b.lat))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(s))


# Coordenadas reales (lat, lon).
la_paz = Coordenada(-16.5000, -68.1500)
santa_cruz = Coordenada(-17.7833, -63.1821)
cochabamba = Coordenada(-17.3895, -66.1568)
tarija = Coordenada(-21.5355, -64.7296)
# Dos puntos cercanos dentro de La Paz (escenario urbano).
urb_a = Coordenada(-16.4955, -68.1336)
urb_b = Coordenada(-16.5040, -68.1190)

rs = RoutingService()  # OSRM publico por defecto

# --- Escenario interurbano: sigue carreteras, no linea recta ---
res = rs.ruta_vial(la_paz, santa_cruz)
ok = res.get("estado") == "ok"
check("interurbano La Paz->Santa Cruz responde OK", ok)
if ok:
    pts = res["coordinates"]
    check("interurbano: geometria con muchos puntos (no recta)", len(pts) > 10)
    check(
        "interurbano: arranca en el origen",
        abs(pts[0][0] - la_paz.lon) < 0.2
        and abs(pts[0][1] - la_paz.lat) < 0.2,
    )
    # Por carretera la distancia es mayor que la linea recta.
    check(
        "interurbano: distancia vial > linea recta",
        res["distancia_m"] / 1000.0 > km_recta(la_paz, santa_cruz),
    )

# --- Escenario con obstaculos geograficos (cordillera/valles) ---
res2 = rs.ruta_vial(la_paz, tarija)
check(
    "La Paz->Tarija (terreno complejo) sigue vias",
    res2.get("estado") == "ok" and len(res2.get("coordinates", [])) > 10,
)

# --- Escenario urbano (puntos cercanos en la ciudad) ---
res3 = rs.ruta_vial(urb_a, urb_b)
check(
    "urbano (La Paz) traza por calles",
    res3.get("estado") == "ok" and len(res3.get("coordinates", [])) >= 2,
)

# --- Otro interurbano ---
res4 = rs.ruta_vial(cochabamba, santa_cruz)
check("interurbano Cochabamba->Santa Cruz OK", res4.get("estado") == "ok")

# --- Manejo de error: servicio inalcanzable -> estado error_red ---
rs_caido = RoutingService(base_url="http://127.0.0.1:9", timeout=2)
check(
    "servicio caido -> error_red",
    rs_caido.ruta_vial(la_paz, santa_cruz).get("estado") == "error_red",
)

# --- Integracion en el servicio: geojson traza vias y cachea ---
ruta_tmp = os.path.join(tempfile.gettempdir(), "_smoke_routing_mapa.json")
base, _ = os.path.splitext(ruta_tmp)
cache_tmp = f"{base}_rutas_viales.json"
for f in (ruta_tmp, cache_tmp):
    if os.path.exists(f):
        os.remove(f)

svc = MapaService(ruta_tmp, routing=RoutingService())
gj = svc.geojson()
viales = [
    f
    for f in gj["carreteras"]["features"]
    if f["properties"]["trazado"] == "vial"
]
check("geojson: la mayoria de carreteras son viales", len(viales) >= 10)
check(
    "geojson: una carretera vial tiene geometria detallada",
    any(len(f["geometry"]["coordinates"]) > 5 for f in viales),
)
check(
    "geojson: routing habilitado y sin caida",
    gj["routing"]["habilitado"] is True
    and gj["routing"]["servicio_caido"] is False,
)
check("geojson: se creo la cache de rutas en disco", os.path.exists(cache_tmp))

# --- Integracion: servicio de rutas caido -> respaldo recta + aviso ---
ruta_tmp2 = os.path.join(tempfile.gettempdir(), "_smoke_routing_mapa2.json")
base2, _ = os.path.splitext(ruta_tmp2)
for f in (ruta_tmp2, f"{base2}_rutas_viales.json"):
    if os.path.exists(f):
        os.remove(f)

svc_caido = MapaService(
    ruta_tmp2,
    routing=RoutingService(base_url="http://127.0.0.1:9", timeout=2),
)
gj2 = svc_caido.geojson()
todas_rectas = all(
    f["properties"]["trazado"] == "recta"
    for f in gj2["carreteras"]["features"]
)
check("servicio caido: carreteras en linea recta (respaldo)", todas_rectas)
check(
    "servicio caido: meta marca servicio_caido",
    gj2["routing"]["servicio_caido"] is True,
)

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} fallo(s) -> {fallos}")
    raise SystemExit(1)
print("RESULTADO: todas las pruebas de enrutamiento OK")
