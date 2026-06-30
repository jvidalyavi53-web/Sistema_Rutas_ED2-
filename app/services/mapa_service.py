"""
SERVICIO · MapaService
======================
Capa intermedia entre los controladores (Flask) y el modelo (Grafo).
Se encarga de:

    * mantener la instancia del grafo en memoria,
    * cargar los datos de ejemplo (departamentos de Bolivia),
    * serializar / deserializar el grafo,
    * persistir el estado en disco (mapa.json).

Los controladores nunca tocan el archivo ni arman el JSON directamente:
delegan en este servicio para mantener la lógica de negocio en un solo lugar.
"""

import json
import logging
import os

from app.models.grafo import Grafo
from app.models.geo import Coordenada
from app.services.routing_service import RoutingService

logger = logging.getLogger(__name__)

# Coordenadas reales (lat, lon) de la capital de cada departamento de Bolivia.
# Se usan para situar las ciudades de ejemplo sobre el mapa real y como
# respaldo de migracion cuando un mapa.json antiguo no trae coordenadas.
COORDENADAS_DEPARTAMENTOS = {
    "La Paz": (-16.5000, -68.1500),
    "Cochabamba": (-17.3895, -66.1568),
    "Santa Cruz": (-17.7833, -63.1821),
    "Chuquisaca": (-19.0333, -65.2627),  # Sucre
    "Oruro": (-17.9833, -67.1500),
    "Potosí": (-19.5836, -65.7531),
    "Tarija": (-21.5355, -64.7296),
    "Beni": (-14.8333, -64.9000),  # Trinidad
    "Pando": (-11.0267, -68.7692),  # Cobija
}


class MapaService:
    def __init__(self, ruta_archivo, routing=None):
        self.ruta_archivo = ruta_archivo
        # Enrutamiento vial opcional. Por defecto (None) queda deshabilitado:
        # la app real inyecta uno habilitado vía create_app; en pruebas o uso
        # directo no se hacen llamadas de red salvo que se pida explícitamente.
        self.routing = routing or RoutingService(habilitado=False)
        self._cache_file = self._ruta_cache(ruta_archivo)
        self.rutas_cache = self._cargar_cache()
        # "Sin ruta" recordado solo en memoria (un reinicio vuelve a intentar).
        self._sin_ruta = set()
        self.grafo = Grafo()
        self.inicializar()

    # ------------------------------------------------------------------ #
    # Datos de ejemplo
    # ------------------------------------------------------------------ #
    def seed_default(self):
        """Carga el mapa de ejemplo: departamentos de Bolivia."""
        g = self.grafo
        g.adyacencia.clear()
        g.tipos_ciudad.clear()

        departamentos = {
            "La Paz": "capital",
            "Cochabamba": "capital",
            "Santa Cruz": "capital",
            "Chuquisaca": "capital",
            "Oruro": "normal",
            "Potosí": "normal",
            "Tarija": "normal",
            "Beni": "turistica",
            "Pando": "turistica",
        }
        for nombre, tipo in departamentos.items():
            coord = COORDENADAS_DEPARTAMENTOS.get(nombre)
            coordenada = Coordenada(*coord) if coord else None
            g.agregar_ciudad(nombre, tipo, coordenada)

        # (origen, destino, distancia km, tiempo min, peaje Bs)
        aristas = [
            ("La Paz", "Oruro", 230, 180, 10),
            ("Oruro", "Cochabamba", 204, 240, 15),
            ("Cochabamba", "Santa Cruz", 473, 420, 20),
            ("La Paz", "Beni", 525, 480, 5),
            ("Beni", "Pando", 598, 720, 0),
            ("Santa Cruz", "Beni", 502, 540, 10),
            ("Oruro", "Potosí", 237, 240, 8),
            ("Potosí", "Chuquisaca", 165, 180, 5),
            ("Chuquisaca", "Tarija", 250, 300, 12),
            ("Cochabamba", "Chuquisaca", 410, 480, 15),
            ("Santa Cruz", "Tarija", 650, 720, 25),
            ("Cochabamba", "Beni", 560, 600, 8),
        ]
        for o, d, dist, t, p in aristas:
            g.agregar_arista(o, d, dist, t, p)

    # ------------------------------------------------------------------ #
    # Serialización / persistencia
    # ------------------------------------------------------------------ #
    def serializar(self):
        """Convierte el grafo a un dict JSON (aristas sin duplicar)."""
        g = self.grafo
        vistas = set()
        aristas = []
        for ciudad, conexiones in g.adyacencia.items():
            for vecino, dist, t, p in conexiones:
                clave = tuple(sorted([ciudad, vecino]))
                if clave not in vistas:
                    vistas.add(clave)
                    aristas.append(
                        {
                            "origen": ciudad,
                            "destino": vecino,
                            "distancia": int(dist),
                            "tiempo": int(t),
                            "peaje": int(p),
                        }
                    )
        ciudades = []
        for c in g.obtener_ciudades():
            coord = g.coordenadas.get(c)
            ciudades.append(
                {
                    "nombre": c,
                    "tipo": g.tipos_ciudad.get(c, "normal"),
                    "lat": coord.lat if coord else None,
                    "lon": coord.lon if coord else None,
                }
            )
        return {"ciudades": ciudades, "aristas": aristas}

    def cargar_desde_dict(self, data):
        """Reconstruye el grafo a partir de un dict serializado.

        Si una ciudad no trae coordenadas (mapa.json antiguo) pero su nombre
        coincide con un departamento conocido, se le asigna su coordenada por
        defecto (migracion transparente).
        """
        g = self.grafo
        g.adyacencia.clear()
        g.tipos_ciudad.clear()
        g.coordenadas.clear()
        for c in data.get("ciudades", []):
            nombre = c["nombre"]
            g.agregar_ciudad(nombre, c.get("tipo", "normal"))
            coordenada = self._resolver_coordenada(nombre, c)
            if coordenada is not None:
                g.asignar_coordenada(nombre, coordenada)
        for a in data.get("aristas", []):
            g.agregar_arista(
                a["origen"],
                a["destino"],
                int(a["distancia"]),
                int(a["tiempo"]),
                int(a["peaje"]),
            )

    @staticmethod
    def _resolver_coordenada(nombre, ciudad_dict):
        """Obtiene la Coordenada de una ciudad: primero del dict guardado,
        luego del catalogo de departamentos. Devuelve None si no hay datos o
        si las coordenadas guardadas son invalidas."""
        lat = ciudad_dict.get("lat")
        lon = ciudad_dict.get("lon")
        if lat is not None and lon is not None:
            try:
                return Coordenada(lat, lon)
            except ValueError:
                logger.warning(
                    "Coordenada invalida para %s; se ignora.", nombre
                )
        respaldo = COORDENADAS_DEPARTAMENTOS.get(nombre)
        return Coordenada(*respaldo) if respaldo else None

    def guardar(self):
        """Persiste el estado actual del grafo en disco."""
        try:
            with open(self.ruta_archivo, "w", encoding="utf-8") as f:
                json.dump(self.serializar(), f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("No se pudo guardar el mapa: %s", e)

    def inicializar(self):
        """Carga el mapa desde disco si existe; si no, usa el de ejemplo."""
        if os.path.exists(self.ruta_archivo):
            try:
                with open(self.ruta_archivo, encoding="utf-8") as f:
                    self.cargar_desde_dict(json.load(f))
                return
            except (OSError, ValueError, KeyError):
                logger.warning("mapa.json corrupto; se carga el ejemplo.")
        self.seed_default()

    def restaurar_ejemplo(self):
        """Vuelve al mapa de ejemplo y lo persiste."""
        self.seed_default()
        self.guardar()

    # ------------------------------------------------------------------ #
    # Enrutamiento vial: caché en disco de la geometría de carreteras
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ruta_cache(ruta_archivo):
        """Ruta del archivo de caché de geometrías viales (junto al mapa)."""
        base, _ = os.path.splitext(ruta_archivo)
        return f"{base}_rutas_viales.json"

    def _cargar_cache(self):
        """Lee la caché de rutas viales del disco (dict clave -> coords)."""
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except (OSError, ValueError):
                logger.warning("Caché de rutas viales corrupta; se ignora.")
        return {}

    def _guardar_cache(self):
        """Persiste la caché de rutas viales (evita re-consultar a OSRM)."""
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self.rutas_cache, f, ensure_ascii=False)
        except OSError as e:
            logger.warning("No se pudo guardar la caché de rutas: %s", e)

    @staticmethod
    def _clave_ruta(ciudad1, coord1, ciudad2, coord2):
        """Clave de caché estable por par de ciudades y sus coordenadas.

        Ordena las dos ciudades para que la clave sea la misma en ambos
        sentidos e incluye las coordenadas redondeadas, de modo que reubicar
        una ciudad invalide su entrada (se vuelve a calcular la ruta).
        """
        a = (ciudad1, round(coord1.lat, 4), round(coord1.lon, 4))
        b = (ciudad2, round(coord2.lat, 4), round(coord2.lon, 4))
        ini, fin = sorted([a, b])
        return f"{ini[0]}@{ini[1]},{ini[2]}|{fin[0]}@{fin[1]},{fin[2]}"

    def _geometria_vial(self, ciudad1, coord1, ciudad2, coord2, estado):
        """Geometría de la carretera siguiendo vías reales (con caché).

        Devuelve la lista de ``[lon, lat]`` del recorrido vial, o ``None`` si
        no hay ruta o el enrutamiento no está disponible (el llamador usa la
        línea recta). ``estado`` es un dict mutable que acumula el estado de
        esta construcción (corte de circuito y archivo de caché por escribir).
        """
        if not self.routing.disponible() or estado["caido"]:
            return None
        clave = self._clave_ruta(ciudad1, coord1, ciudad2, coord2)
        if clave in self.rutas_cache:
            return self.rutas_cache[clave]
        if clave in self._sin_ruta:
            return None

        resultado = self.routing.ruta_vial(coord1, coord2)
        situacion = resultado.get("estado")
        if situacion == "ok":
            self.rutas_cache[clave] = resultado["coordinates"]
            estado["sucio"] = True
            return resultado["coordinates"]
        if situacion == "error_red":
            # OSRM no responde: corta las siguientes consultas de esta
            # construcción para no encadenar timeouts (protege el tiempo de
            # respuesta). Un reinicio del proceso vuelve a intentar.
            estado["caido"] = True
        else:  # sin_ruta / deshabilitado
            self._sin_ruta.add(clave)
        return None

    # ------------------------------------------------------------------ #
    # Datos georreferenciados (GeoJSON para el mapa real)
    # ------------------------------------------------------------------ #
    def geojson(self):
        """Construye los datos del mapa en formato GeoJSON.

        Devuelve dos *FeatureCollection*:
            * `ciudades`   -> puntos (Point) con nombre, tipo y conexiones.
            * `carreteras` -> lineas (LineString) entre ciudades y sus costos.

        Solo se incluyen las entidades con coordenadas validas; una carretera
        se dibuja unicamente si sus dos extremos estan georreferenciados.
        """
        g = self.grafo

        ciudades = []
        for nombre in g.obtener_ciudades():
            coord = g.coordenadas.get(nombre)
            if coord is None:
                continue
            ciudades.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": coord.to_geojson(),
                    },
                    "properties": {
                        "nombre": nombre,
                        "tipo": g.tipos_ciudad.get(nombre, "normal"),
                        "conexiones": len(g.adyacencia.get(nombre, [])),
                    },
                }
            )

        carreteras = []
        fallidos = []
        vistas = set()
        # Estado mutable de esta construcción (corte de circuito y caché).
        estado = {"caido": False, "sucio": False}
        for ciudad1, conexiones in g.adyacencia.items():
            coord1 = g.coordenadas.get(ciudad1)
            if coord1 is None:
                continue
            for ciudad2, distancia, tiempo, peaje in conexiones:
                coord2 = g.coordenadas.get(ciudad2)
                if coord2 is None:
                    continue
                clave = tuple(sorted([ciudad1, ciudad2]))
                if clave in vistas:
                    continue
                vistas.add(clave)

                # Geometría vial (sigue carreteras); si no hay, línea recta.
                vial = self._geometria_vial(
                    ciudad1, coord1, ciudad2, coord2, estado
                )
                if vial:
                    coordenadas = vial
                    trazado = "vial"
                else:
                    coordenadas = [coord1.to_geojson(), coord2.to_geojson()]
                    trazado = "recta"
                    if self.routing.disponible():
                        fallidos.append(f"{ciudad1} ↔ {ciudad2}")

                carreteras.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coordenadas,
                        },
                        "properties": {
                            "id": f"{ciudad1}-{ciudad2}",
                            "origen": ciudad1,
                            "destino": ciudad2,
                            "distancia": int(distancia),
                            "tiempo": int(tiempo),
                            "peaje": int(peaje),
                            "trazado": trazado,
                        },
                    }
                )

        if estado["sucio"]:
            self._guardar_cache()

        return {
            "ciudades": {
                "type": "FeatureCollection",
                "features": ciudades,
            },
            "carreteras": {
                "type": "FeatureCollection",
                "features": carreteras,
            },
            "routing": {
                "habilitado": self.routing.disponible(),
                "perfil": self.routing.perfil,
                "servicio_caido": estado["caido"],
                "fallidos": fallidos,
            },
        }

    # ------------------------------------------------------------------ #
    # Estadísticas
    # ------------------------------------------------------------------ #
    def estadisticas(self):
        """Resumen numérico del grafo para el panel de la interfaz."""
        g = self.grafo
        distancias, tiempos, peajes = [], [], []
        for conexiones in g.adyacencia.values():
            for _, dist, tiempo, peaje in conexiones:
                distancias.append(int(dist))
                tiempos.append(int(tiempo))
                peajes.append(int(peaje))

        total_rutas = sum(len(c) for c in g.adyacencia.values()) // 2
        prom_dist = sum(distancias) // len(distancias) if distancias else 0
        prom_tiempo = sum(tiempos) // len(tiempos) if tiempos else 0
        prom_peaje = sum(peajes) // len(peajes) if peajes else 0
        return {
            "total_ciudades": len(g.adyacencia),
            "total_rutas": total_rutas,
            "distancia_promedio": prom_dist,
            "tiempo_promedio": prom_tiempo,
            "peaje_promedio": prom_peaje,
        }
