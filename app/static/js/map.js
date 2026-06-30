/* =========================================================================
   map.js · Mapa real con MapLibre GL JS + MapTiler
   -------------------------------------------------------------------------
   Capa VISTA. Solo presentacion: pide la configuracion y los datos
   georreferenciados a los endpoints de Flask (/api/map-config, /api/geojson)
   y los dibuja. No contiene logica de negocio ni de algoritmos.

   Se usa tanto en index.html (mapa editable) como en resultado.html (mapa
   con la ruta calculada resaltada via la variable global `rutaCamino`).
   ========================================================================= */
let map = null;
let carreterasFeatures = [];     // cache para resaltar la ruta
let modoSeleccion = false;       // true mientras el usuario elige una ubicacion
let marcadorTemporal = null;     // marcador al elegir ubicacion en el mapa

// Colores por tipo de ciudad (coinciden con la leyenda del HTML).
const COLORES_TIPO = [
    'match', ['get', 'tipo'],
    'capital', '#6366f1',
    'normal', '#0ea5e9',
    'turistica', '#10b981',
    'comercial', '#f59e0b',
    'industrial', '#8b5cf6',
    /* otro */ '#0ea5e9',
];
const COLOR_CARRETERA = '#64748b';
const COLOR_RUTA = '#fb7185';

// Estilo base de respaldo (OpenStreetMap) cuando no hay clave de MapTiler.
function estiloOSM() {
    return {
        version: 8,
        // Servidor de glifos publico que SI sirve las fuentes usadas (Open
        // Sans Regular/Bold). Es imprescindible: si los glifos no cargan, las
        // capas de texto (symbol) dejan el tile en estado "errored" y se
        // pierden tambien los circulos de las ciudades de esa misma fuente.
        glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
        sources: {
            osm: {
                type: 'raster',
                tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                tileSize: 256,
                attribution: '© OpenStreetMap',
            },
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
    };
}

// ------------------------------------------------------------------ //
// Inicializacion
// ------------------------------------------------------------------ //
function iniciarMapa() {
    const contenedor = document.getElementById('map');
    if (!contenedor || typeof maplibregl === 'undefined') return;

    fetch('/api/map-config')
        .then(res => res.json())
        .then(cfg => {
            const estilo = cfg.hasKey ? cfg.styleUrl : estiloOSM();
            map = new maplibregl.Map({
                container: 'map',
                style: estilo,
                center: cfg.center,
                zoom: cfg.zoom,
                attributionControl: { compact: true },
            });
            map.addControl(new maplibregl.NavigationControl(), 'top-right');
            map.on('load', cargarDatosGeo);
        })
        .catch(err => console.error('Error cargando configuracion del mapa:', err));
}

function cargarDatosGeo() {
    fetch('/api/geojson')
        .then(res => res.json())
        .then(data => {
            carreterasFeatures = (data.carreteras && data.carreteras.features) || [];
            dibujarCarreteras(data.carreteras);
            dibujarCiudades(data.ciudades);
            ajustarVista(data.ciudades);
            avisarTrazadoVial(data.routing);

            // Si la pagina trae una ruta calculada, resaltarla.
            if (typeof rutaCamino !== 'undefined' && rutaCamino && rutaCamino.length > 0) {
                resaltarRuta(rutaCamino);
            }
        })
        .catch(err => console.error('Error cargando datos del mapa:', err));
}

// Aviso cuando alguna carretera no pudo trazarse siguiendo vias reales.
// Funciona en index y en resultado (no depende de toast, que solo existe en
// la pagina principal): inserta un mensaje sobre el contenedor del mapa.
function avisarTrazadoVial(routing) {
    if (!routing || !routing.habilitado) return;

    let mensaje = '';
    if (routing.servicio_caido) {
        mensaje = 'No se pudo conectar al servicio de rutas viales: ' +
            'algunas carreteras se muestran como linea recta.';
    } else if (routing.fallidos && routing.fallidos.length) {
        mensaje = 'Sin ruta vial disponible para ' +
            routing.fallidos.length + ' carretera(s): ' +
            routing.fallidos.join(', ') +
            '. Se muestran como linea recta.';
    } else {
        return;  // todo el trazado siguio las carreteras
    }

    if (typeof toast === 'function') {
        toast(mensaje, 'error', 6000);
        return;
    }
    mostrarAvisoMapa(mensaje);
}

function mostrarAvisoMapa(mensaje) {
    const contenedor = document.getElementById('map');
    if (!contenedor || !contenedor.parentNode) return;
    let aviso = document.getElementById('mapAviso');
    if (!aviso) {
        aviso = document.createElement('div');
        aviso.id = 'mapAviso';
        aviso.className = 'map-aviso';
        contenedor.parentNode.insertBefore(aviso, contenedor);
    }
    aviso.textContent = mensaje;
}

// ------------------------------------------------------------------ //
// Capas: carreteras y ciudades
// ------------------------------------------------------------------ //
function dibujarCarreteras(geojson) {
    map.addSource('carreteras', { type: 'geojson', data: geojson });

    // Carreteras base.
    map.addLayer({
        id: 'carreteras-linea',
        type: 'line',
        source: 'carreteras',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': COLOR_CARRETERA, 'line-width': 3, 'line-opacity': 0.8 },
    });

    // Carreteras de la ruta resaltada (vacia hasta que se calcule una ruta).
    map.addLayer({
        id: 'carreteras-ruta',
        type: 'line',
        source: 'carreteras',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': COLOR_RUTA, 'line-width': 6 },
        filter: ['in', ['get', 'id'], ['literal', []]],
    });

    // Etiqueta con los costos de cada carretera.
    map.addLayer({
        id: 'carreteras-texto',
        type: 'symbol',
        source: 'carreteras',
        layout: {
            'symbol-placement': 'line-center',
            'text-field': [
                'concat', ['get', 'distancia'], ' km',
            ],
            'text-size': 11,
            // Una sola fuente: el servidor de glifos compone el "fontstack"
            // pidiendo la lista unida por comas. Si se incluye una fuente que
            // el servidor no tiene (p. ej. "Arial Unicode MS"), responde una
            // pagina HTML en vez del PBF y el tile entero queda "errored".
            'text-font': ['Open Sans Regular'],
        },
        paint: {
            'text-color': '#e2e8f0',
            'text-halo-color': '#0b1120',
            'text-halo-width': 1.4,
        },
    });
}

function dibujarCiudades(geojson) {
    map.addSource('ciudades', { type: 'geojson', data: geojson });

    // Circulo de cada ciudad coloreado por tipo.
    map.addLayer({
        id: 'ciudades-punto',
        type: 'circle',
        source: 'ciudades',
        paint: {
            'circle-radius': 8,
            'circle-color': COLORES_TIPO,
            'circle-stroke-width': 2,
            'circle-stroke-color': '#f8fafc',
        },
    });

    // Realce de las ciudades que forman parte de la ruta.
    map.addLayer({
        id: 'ciudades-ruta',
        type: 'circle',
        source: 'ciudades',
        paint: {
            'circle-radius': 11,
            'circle-color': COLOR_RUTA,
            'circle-stroke-width': 3,
            'circle-stroke-color': '#f43f5e',
        },
        filter: ['in', ['get', 'nombre'], ['literal', []]],
    });

    // Nombre de la ciudad.
    map.addLayer({
        id: 'ciudades-texto',
        type: 'symbol',
        source: 'ciudades',
        layout: {
            'text-field': ['get', 'nombre'],
            'text-size': 13,
            'text-offset': [0, 1.4],
            'text-anchor': 'top',
            'text-font': ['Open Sans Bold'],
        },
        paint: {
            'text-color': '#f1f5f9',
            'text-halo-color': '#0b1120',
            'text-halo-width': 1.6,
        },
    });

    // Interaccion: clic en una ciudad -> detalle; cursor de mano.
    map.on('click', 'ciudades-punto', e => {
        const nombre = e.features[0].properties.nombre;
        mostrarInfoCiudad(nombre, e.lngLat);
    });
    map.on('mouseenter', 'ciudades-punto', () => {
        map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', 'ciudades-punto', () => {
        map.getCanvas().style.cursor = '';
    });

    // Clic en el mapa (fuera de una ciudad) durante el modo seleccion.
    map.on('click', e => {
        if (modoSeleccion) fijarUbicacion(e.lngLat);
    });
}

function ajustarVista(geojson) {
    const features = (geojson && geojson.features) || [];
    if (!features.length) return;
    const bounds = new maplibregl.LngLatBounds();
    features.forEach(f => bounds.extend(f.geometry.coordinates));
    map.fitBounds(bounds, { padding: 60, maxZoom: 7, duration: 0 });
}

// ------------------------------------------------------------------ //
// Resaltado de la ruta calculada
// ------------------------------------------------------------------ //
function resaltarRuta(camino) {
    if (!map || !camino || camino.length === 0) return;

    // Ids de las carreteras que unen ciudades consecutivas del camino.
    const ids = [];
    for (let i = 0; i < camino.length - 1; i++) {
        const a = camino[i], b = camino[i + 1];
        const f = carreterasFeatures.find(f =>
            (f.properties.origen === a && f.properties.destino === b) ||
            (f.properties.origen === b && f.properties.destino === a));
        if (f) ids.push(f.properties.id);
    }
    if (map.getLayer('carreteras-ruta')) {
        map.setFilter('carreteras-ruta', ['in', ['get', 'id'], ['literal', ids]]);
    }
    if (map.getLayer('ciudades-ruta')) {
        map.setFilter('ciudades-ruta', ['in', ['get', 'nombre'], ['literal', camino]]);
    }
}

// ------------------------------------------------------------------ //
// Detalle de ciudad (popup + modal en la pagina principal)
// ------------------------------------------------------------------ //
function mostrarInfoCiudad(nombre, lngLat) {
    fetch(`/api/ciudad/${encodeURIComponent(nombre)}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) return;
            // En la pagina principal hay un modal mas completo.
            if (typeof window.mostrarCiudadEnModal === 'function') {
                window.mostrarCiudadEnModal(data);
                return;
            }
            // En el resultado, un popup sencillo sobre el mapa.
            let html = `<strong>${data.nombre}</strong><br>Tipo: ${data.tipo}` +
                `<br>Conexiones: ${data.conexiones}`;
            new maplibregl.Popup({ closeButton: true })
                .setLngLat(lngLat)
                .setHTML(`<div class="map-popup">${html}</div>`)
                .addTo(map);
        })
        .catch(err => console.error('Error obteniendo info de ciudad:', err));
}

// ------------------------------------------------------------------ //
// Modo "elegir ubicacion en el mapa" (alta de ciudad)
// ------------------------------------------------------------------ //
// `reiniciar = true` arranca una ciudad NUEVA desde el mapa: limpia el
// formulario y el marcador previo para que, tras el clic, el modal aparezca en
// blanco (solo falta escribir nombre y tipo). Llamado sin argumento desde el
// boton dentro del modal, conserva lo que el usuario ya haya escrito.
function elegirEnMapa(reiniciar) {
    if (!map) return;
    modoSeleccion = true;
    if (reiniciar) {
        const form = document.getElementById('formCiudad');
        if (form) form.reset();
        if (marcadorTemporal) {
            marcadorTemporal.remove();
            marcadorTemporal = null;
        }
    }
    if (typeof cerrarModal === 'function') cerrarModal('modalCiudad');
    if (typeof toast === 'function') {
        toast('Haz clic en el mapa para ubicar la nueva ciudad.', 'info');
    }
    map.getCanvas().style.cursor = 'crosshair';
}

function fijarUbicacion(lngLat) {
    modoSeleccion = false;
    map.getCanvas().style.cursor = '';

    const lat = document.getElementById('ciudadLat');
    const lon = document.getElementById('ciudadLon');
    if (lat) lat.value = lngLat.lat.toFixed(5);
    if (lon) lon.value = lngLat.lng.toFixed(5);

    if (marcadorTemporal) marcadorTemporal.remove();
    marcadorTemporal = new maplibregl.Marker({ color: '#fb7185' })
        .setLngLat(lngLat)
        .addTo(map);

    if (typeof mostrarModal === 'function') mostrarModal('modalCiudad');
}

// Permitir reajuste tras cambios de tamano del contenedor.
window.addEventListener('resize', () => { if (map) map.resize(); });

document.addEventListener('DOMContentLoaded', iniciarMapa);
