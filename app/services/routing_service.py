"""
SERVICIO · RoutingService (enrutamiento vial sobre OSRM)
=======================================================
Cliente del servicio de enrutamiento que traza el recorrido **siguiendo la red
vial real** (carreteras de OpenStreetMap) en lugar de una linea recta entre dos
puntos.

Por que OSRM y no la API de MapTiler:
    MapTiler Cloud ofrece mapas, tiles, geocoding y elevacion, pero su API de
    enrutamiento (Directions) esta en *beta cerrada* y requiere solicitar
    acceso; no funciona con una clave gratuita estandar. OSRM (Open Source
    Routing Machine) expone un servidor publico de demostracion, sin clave,
    que devuelve la geometria de la ruta en GeoJSON y respeta el perfil.

Pertenece a la capa SERVICIO: aisla los detalles del proveedor (URL, formato de
respuesta, errores de red) para que `MapaService` solo pida "dame la geometria
vial entre A y B" y el controlador/vista nunca toquen HTTP externo. Devuelve
siempre datos planos (listas de [lon, lat]) o ``None`` si no hay ruta; nunca
lanza excepciones de red hacia arriba.
"""

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


class RoutingService:
    """Cliente de enrutamiento vial (OSRM)."""

    def __init__(
        self,
        base_url="https://router.project-osrm.org",
        perfil="driving",
        timeout=8.0,
        habilitado=True,
    ):
        self.base_url = base_url.rstrip("/")
        self.perfil = perfil
        self.timeout = float(timeout)
        self.habilitado = bool(habilitado)

    @classmethod
    def desde_config(cls, config):
        """Crea el servicio leyendo la configuracion de Flask (o un dict)."""

        def leer(clave, defecto):
            try:
                return config.get(clave, defecto)
            except AttributeError:
                return getattr(config, clave, defecto)

        return cls(
            base_url=leer("OSRM_URL", "https://router.project-osrm.org"),
            perfil=leer("ROUTING_PERFIL", "driving"),
            timeout=leer("ROUTING_TIMEOUT", 8.0),
            habilitado=leer("ROUTING_HABILITADO", True),
        )

    def disponible(self):
        """True si el enrutamiento esta habilitado por configuracion."""
        return self.habilitado

    # ------------------------------------------------------------------ #
    # Consulta de ruta vial
    # ------------------------------------------------------------------ #
    def ruta_vial(self, coord_origen, coord_destino):
        """Consulta la geometria de la carretera entre dos coordenadas.

        Parametros:
            coord_origen, coord_destino: objetos con ``.lon`` y ``.lat``
                (p. ej. ``Coordenada``) o tuplas/listas ``(lat, lon)``.

        Retorna siempre un dict con la clave ``estado``; nunca lanza
        excepciones de red. El llamador decide el respaldo (linea recta)::

            {"estado": "ok", "coordinates": [[lon, lat], ...],
             "distancia_m": float, "duracion_s": float}
            {"estado": "sin_ruta"}        # no existe ruta vial entre A y B
            {"estado": "error_red"}       # OSRM no respondio / fallo de red
            {"estado": "deshabilitado"}   # enrutamiento apagado por config

        Distinguir ``sin_ruta`` de ``error_red`` permite al servicio cachear
        los "sin ruta" y cortar las llamadas cuando OSRM esta caido (evita
        encadenar timeouts y degradar el tiempo de respuesta).
        """
        if not self.habilitado:
            return {"estado": "deshabilitado"}

        lon1, lat1 = self._lon_lat(coord_origen)
        lon2, lat2 = self._lon_lat(coord_destino)
        url = (
            f"{self.base_url}/route/v1/{self.perfil}/"
            f"{lon1},{lat1};{lon2},{lat2}"
            "?overview=simplified&geometries=geojson"
        )
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.load(resp)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            logger.warning("OSRM no respondio (%s): %s", url, e)
            return {"estado": "error_red"}

        if data.get("code") != "Ok" or not data.get("routes"):
            logger.info(
                "OSRM sin ruta vial entre los puntos (%s).", data.get("code")
            )
            return {"estado": "sin_ruta"}

        ruta = data["routes"][0]
        coords = (ruta.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2:
            return {"estado": "sin_ruta"}
        return {
            "estado": "ok",
            "coordinates": coords,
            "distancia_m": ruta.get("distance", 0.0),
            "duracion_s": ruta.get("duration", 0.0),
        }

    @staticmethod
    def _lon_lat(punto):
        """Normaliza el punto de entrada a la tupla (lon, lat) de OSRM."""
        if hasattr(punto, "lon") and hasattr(punto, "lat"):
            return punto.lon, punto.lat
        lat, lon = punto  # tupla/lista (lat, lon)
        return lon, lat
