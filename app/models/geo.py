"""
MODELO · Coordenada (informacion georreferenciada)
==================================================
*Value object* que representa un punto geografico (latitud, longitud) con
**validacion de dominio**. Se usa para ubicar cada ciudad del grafo sobre un
mapa real (MapTiler + MapLibre GL JS).

Pertenece a la capa MODELO: es logica de dominio pura, sin dependencias de
Flask ni de la herramienta de mapas. La relacion con otras entidades del
proyecto es directa: cada `Coordenada` ubica geograficamente a una ciudad
(nodo) del `Grafo`; la asociacion ciudad -> coordenada la mantiene el propio
`Grafo` (ver `grafo.py`).
"""


class Coordenada:
    """Punto geografico validado en grados decimales (WGS84)."""

    # Rangos geograficos validos universales.
    LAT_MIN, LAT_MAX = -90.0, 90.0
    LON_MIN, LON_MAX = -180.0, 180.0

    # Caja envolvente aproximada de Bolivia (validacion de dominio del
    # proyecto: se espera que las ciudades caigan dentro del pais).
    BOLIVIA_LAT = (-23.5, -9.5)
    BOLIVIA_LON = (-70.0, -57.0)

    def __init__(self, lat, lon):
        self.lat, self.lon = self.validar(lat, lon)

    # ------------------------------------------------------------------ #
    # Validacion
    # ------------------------------------------------------------------ #
    @classmethod
    def validar(cls, lat, lon):
        """Valida y normaliza un par (lat, lon).

        Devuelve la tupla (lat, lon) como floats. Lanza ``ValueError`` si
        algun valor no es numerico o cae fuera de los rangos geograficos.
        """
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            raise ValueError("La latitud y la longitud deben ser numericas")

        if not (cls.LAT_MIN <= lat <= cls.LAT_MAX):
            raise ValueError(
                "Latitud fuera de rango "
                f"[{cls.LAT_MIN}, {cls.LAT_MAX}]: {lat}"
            )
        if not (cls.LON_MIN <= lon <= cls.LON_MAX):
            raise ValueError(
                "Longitud fuera de rango "
                f"[{cls.LON_MIN}, {cls.LON_MAX}]: {lon}"
            )
        return lat, lon

    def en_bolivia(self):
        """True si la coordenada cae dentro de la caja de Bolivia."""
        return (
            self.BOLIVIA_LAT[0] <= self.lat <= self.BOLIVIA_LAT[1]
            and self.BOLIVIA_LON[0] <= self.lon <= self.BOLIVIA_LON[1]
        )

    # ------------------------------------------------------------------ #
    # Serializacion
    # ------------------------------------------------------------------ #
    def to_dict(self):
        """Representacion para persistencia/JSON: {lat, lon}."""
        return {"lat": self.lat, "lon": self.lon}

    def to_geojson(self):
        """Posicion en formato GeoJSON: [longitud, latitud]."""
        return [self.lon, self.lat]

    @classmethod
    def desde_dict(cls, data):
        """Crea una Coordenada desde un dict {lat, lon}; None si no aplica."""
        if not data:
            return None
        return cls(data.get("lat"), data.get("lon"))

    def __eq__(self, other):
        return (
            isinstance(other, Coordenada)
            and self.lat == other.lat
            and self.lon == other.lon
        )

    def __repr__(self):
        return f"Coordenada(lat={self.lat}, lon={self.lon})"
