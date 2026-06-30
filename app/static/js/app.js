/* =========================================================================
   app.js · Lógica de la interfaz de la página principal
   ========================================================================= */

// ----------------------------- Utilidades ------------------------------ //
function mostrarModal(id) {
    new bootstrap.Modal(document.getElementById(id)).show();
}

function cerrarModal(id) {
    const inst = bootstrap.Modal.getInstance(document.getElementById(id));
    if (inst) inst.hide();
}

function toggleCriterio() {
    const esBfs = document.getElementById('selAlgoritmo').value === 'bfs';
    document.getElementById('selCriterio').disabled = esBfs;
    document.getElementById('campoCriterio').classList.toggle('is-off', esBfs);
}

function postJSON(url, body) {
    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    }).then(r => r.json());
}

function toast(mensaje, tipo = 'info', ms = 3400) {
    const stack = document.getElementById('toastStack');
    if (!stack) { console.log(`[${tipo}] ${mensaje}`); return; }
    const el = document.createElement('div');
    el.className = `toast-msg is-${tipo}`;
    el.textContent = mensaje;
    stack.appendChild(el);
    setTimeout(() => {
        el.classList.add('fade-out');
        setTimeout(() => el.remove(), 300);
    }, ms);
}

function abrirResultados(titulo, html) {
    document.getElementById('tituloResultados').textContent = titulo;
    document.getElementById('cuerpoResultados').innerHTML = html;
    new bootstrap.Modal(document.getElementById('modalResultados')).show();
}

// --------------------------------- CRUD -------------------------------- //
function agregarCiudad() {
    const data = Object.fromEntries(new FormData(document.getElementById('formCiudad')));
    if (!data.nombre || !data.nombre.trim()) return toast('Escribe un nombre de ciudad.', 'error');
    postJSON('/api/ciudades', data).then(r => {
        if (r.error) return toast(r.error, 'error');
        toast(r.mensaje, 'success');
        setTimeout(() => location.reload(), 700);
    }).catch(e => toast('Error: ' + e, 'error'));
}

function eliminarCiudad() {
    const ciudad = document.getElementById('selectEliminarCiudad').value;
    if (!confirm(`¿Eliminar la ciudad "${ciudad}" y todas sus carreteras?`)) return;
    postJSON('/api/eliminar-ciudad', { nombre: ciudad }).then(r => {
        if (r.error) return toast(r.error, 'error');
        toast(r.mensaje, 'success');
        setTimeout(() => location.reload(), 700);
    }).catch(e => toast('Error: ' + e, 'error'));
}

function agregarRuta() {
    const data = Object.fromEntries(new FormData(document.getElementById('formRuta')));
    if (data.origen === data.destino) return toast('Origen y destino deben ser distintos.', 'error');
    data.distancia = parseInt(data.distancia);
    data.tiempo = parseInt(data.tiempo);
    data.peaje = parseInt(data.peaje);
    postJSON('/api/rutas', data).then(r => {
        if (r.error) return toast(r.error, 'error');
        toast(r.mensaje, 'success');
        setTimeout(() => location.reload(), 700);
    }).catch(e => toast('Error: ' + e, 'error'));
}

function eliminarRuta() {
    const origen = document.getElementById('selectEliminarOrigen').value;
    const destino = document.getElementById('selectEliminarDestino').value;
    if (!confirm(`¿Eliminar la carretera entre "${origen}" y "${destino}"?`)) return;
    postJSON('/api/eliminar-carretera', { origen, destino }).then(r => {
        if (r.error) return toast(r.error, 'error');
        toast(r.mensaje, 'success');
        setTimeout(() => location.reload(), 700);
    }).catch(e => toast('Error: ' + e, 'error'));
}

function restaurarEjemplo() {
    if (!confirm('¿Restaurar el mapa de ejemplo? Se perderán los cambios actuales.')) return;
    postJSON('/api/reset', {}).then(r => {
        if (r.error) return toast(r.error, 'error');
        toast(r.mensaje, 'success');
        setTimeout(() => location.reload(), 700);
    }).catch(e => toast('Error: ' + e, 'error'));
}

// ------------------------------ Listados ------------------------------- //
function listarRutas() {
    fetch('/api/rutas').then(r => r.json()).then(data => {
        let html = `<p class="hint">Total de carreteras: <strong>${data.total_rutas}</strong></p>`;
        if (data.rutas && data.rutas.length) {
            html += tablaHTML(['Origen', 'Destino', 'km', 'min', 'Bs'],
                data.rutas.map(x => [x.origen, x.destino, x.distancia, x.tiempo, x.peaje]));
        } else {
            html += '<p class="hint">No hay carreteras.</p>';
        }
        abrirResultados('Carreteras', html);
    }).catch(e => toast('Error: ' + e, 'error'));
}

function listarCiudades() {
    fetch('/api/ciudades').then(r => r.json()).then(data => {
        let html = `<p class="hint">Total de ciudades: <strong>${data.length}</strong></p>`;
        html += tablaHTML(['Ciudad', 'Tipo', 'Conexiones'],
            data.map(c => [c.nombre, c.tipo, c.conexiones || 0]));
        abrirResultados('Ciudades', html);
    }).catch(e => toast('Error: ' + e, 'error'));
}

// --------------------------- DFS: todas rutas -------------------------- //
function calcularDFS() {
    const origen = document.getElementById('selOrigen').value;
    const destino = document.getElementById('selDestino').value;
    if (origen === destino) return toast('Elige un origen y un destino distintos.', 'error');
    postJSON('/api/todas-rutas', { origen, destino }).then(data => {
        if (data.error) return toast(data.error, 'error');
        let html = `<p class="hint">Se encontraron <strong>${data.total}</strong> ruta(s) de <strong>${data.origen}</strong> a <strong>${data.destino}</strong> (ordenadas por nº de paradas):</p>`;
        if (data.rutas.length) {
            const filas = data.rutas.map((r, i) => [
                i + 1,
                `<span class="camino">${r.camino.join(' → ')}</span>`,
                r.paradas, r.distancia, r.tiempo, r.peaje,
            ]);
            html += tablaHTML(['#', 'Ruta', 'Paradas', 'km', 'min', 'Bs'], filas);
        } else {
            html += '<p class="hint">No existe ninguna ruta entre esas ciudades.</p>';
        }
        abrirResultados('Todas las rutas (DFS)', html);
    }).catch(e => toast('Error: ' + e, 'error'));
}

// ------------------------ Comparar algoritmos -------------------------- //
function compararAlgoritmos() {
    const origen = document.getElementById('selOrigen').value;
    const destino = document.getElementById('selDestino').value;
    if (origen === destino) return toast('Elige un origen y un destino distintos.', 'error');
    postJSON('/api/comparar', { origen, destino }).then(data => {
        if (data.error) return toast(data.error, 'error');
        const res = data.resultados || [];
        if (!res.length) return abrirResultados('Comparación', '<p class="hint">No hay rutas para comparar.</p>');
        const min = k => Math.min(...res.map(r => r[k]));
        const mins = { distancia: min('distancia'), tiempo: min('tiempo'), peaje: min('peaje'), paradas: min('paradas') };
        const mark = (v, k) => v === mins[k] ? `<span class="best">${v}</span>` : v;
        let html = `<p class="hint">Comparación para <strong>${data.origen} → ${data.destino}</strong> (resaltado el mejor de cada columna):</p>`;
        const filas = res.map(r => [
            r.algoritmo,
            `<span class="camino">${r.camino.join(' → ')}</span>`,
            mark(r.paradas, 'paradas'), mark(r.distancia, 'distancia'),
            mark(r.tiempo, 'tiempo'), mark(r.peaje, 'peaje'),
        ]);
        html += tablaHTML(['Algoritmo', 'Ruta', 'Paradas', 'km', 'min', 'Bs'], filas);
        abrirResultados('Comparación de algoritmos', html);
    }).catch(e => toast('Error: ' + e, 'error'));
}

// --------------------------- Matriz adyacencia ------------------------- //
function mostrarMatriz() {
    const modalEl = document.getElementById('modalMatriz');
    const criterio = document.getElementById('matrizCriterio').value;
    fetch(`/api/matriz?criterio=${criterio}`).then(r => r.json()).then(data => {
        const ciudades = data.ciudades;
        let html = '<table class="tabla-matriz"><thead><tr><th>·</th>';
        ciudades.forEach(c => html += `<th>${c}</th>`);
        html += '</tr></thead><tbody>';
        data.matriz.forEach((fila, i) => {
            html += `<tr><th>${ciudades[i]}</th>`;
            fila.forEach(v => html += `<td class="${v === 0 ? 'cero' : ''}">${v}</td>`);
            html += '</tr>';
        });
        html += '</tbody></table>';
        document.getElementById('cuerpoMatriz').innerHTML = html;
        if (!modalEl.classList.contains('show')) new bootstrap.Modal(modalEl).show();
    }).catch(e => toast('Error: ' + e, 'error'));
}

// ------------------------- Info de ciudad (mapa) ----------------------- //
window.mostrarCiudadEnModal = function (data) {
    let html = `<p class="hint">Tipo: <strong>${data.tipo}</strong> · Conexiones: <strong>${data.conexiones}</strong></p>`;
    if (data.rutas && data.rutas.length) {
        html += tablaHTML(['Destino', 'km', 'min', 'Bs'],
            data.rutas.map(r => [r.destino, r.distancia, r.tiempo, r.peaje]));
    } else {
        html += '<p class="hint">Sin carreteras conectadas.</p>';
    }
    abrirResultados(`Ciudad: ${data.nombre}`, html);
};

// ------------------------------ Helpers -------------------------------- //
function tablaHTML(cabeceras, filas) {
    let html = '<div class="table-responsive"><table class="data-table"><thead><tr>';
    cabeceras.forEach(c => html += `<th>${c}</th>`);
    html += '</tr></thead><tbody>';
    filas.forEach(fila => {
        html += '<tr>' + fila.map(celda => `<td>${celda}</td>`).join('') + '</tr>';
    });
    html += '</tbody></table></div>';
    return html;
}

// ----------------------------- Inicio ---------------------------------- //
document.addEventListener('DOMContentLoaded', function () {
    toggleCriterio();
    fetch('/api/estadisticas').then(r => r.json()).then(data => {
        document.getElementById('total-ciudades').textContent = data.total_ciudades;
        document.getElementById('total-rutas').textContent = data.total_rutas;
        document.getElementById('distancia-promedio').textContent = data.distancia_promedio;
        document.getElementById('tiempo-promedio').textContent = data.tiempo_promedio;
    }).catch(e => console.error('Error estadísticas:', e));
});
