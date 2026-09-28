// Asistente TUP — pantalla. Sin build: HTML + este archivo.
'use strict';

const $vista = document.getElementById('vista');
const E = {}; // estado global: estado del sistema, catálogo, tarea en curso
let tarea = null; // { sid, receta, trabajando }

// ------------------------------------------------------------------ utilidades
function h(tag, attrs = {}, ...hijos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'html') el.innerHTML = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of hijos.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const md = (t) => DOMPurify.sanitize(marked.parse(t || '', { breaks: false, gfm: true }));
async function api(ruta, opts = {}) {
  const r = await fetch(ruta, {
    headers: opts.body && !(opts.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {},
    ...opts,
    body: opts.body && !(opts.body instanceof FormData) ? JSON.stringify(opts.body) : opts.body,
  });
  if (!r.ok) {
    let msg = `Error ${r.status}`;
    try { msg = (await r.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return r.json();
}
function montar(...nodos) {
  $vista.replaceChildren(...nodos.filter(Boolean));
  $vista.focus({ preventScroll: true });
  window.scrollTo({ top: 0 });
}

// ------------------------------------------------------------------ arranque
async function cargar() {
  // /api/campus es no-esencial: si falla (o el archivo del campus está corrompido)
  // el resto de la pantalla (catálogo, estado) no tiene por qué quedar inutilizable.
  const [estadoR, catalogoR, campusR] = await Promise.allSettled([api('/api/estado'), api('/api/catalogo'), api('/api/campus')]);
  if (estadoR.status === 'rejected') throw estadoR.reason;
  if (catalogoR.status === 'rejected') throw catalogoR.reason;
  E.estado = estadoR.value;
  E.catalogo = catalogoR.value;
  E.campus = campusR.status === 'fulfilled' ? campusR.value : { campus: [], activo: null };
  pintarCampus();
  const mal = E.estado.chequeos.filter((c) => !c.ok);
  document.getElementById('estado-punto').className = 'punto ' + (mal.length ? 'mal' : 'ok');
  document.getElementById('estado-texto').textContent = mal.length ? `Falta configurar ${mal.length === 1 ? 'algo' : mal.length + ' cosas'}` : 'Todo listo';
}

function pintarCampus() {
  const chip = document.getElementById('campus-chip');
  const lista = E.campus?.campus || [];
  const activo = lista.find((k) => String(k.id) === String(E.campus?.activo));
  chip.hidden = false;
  document.getElementById('campus-nombre').textContent = activo ? activo.nombre : (lista.length ? 'Elegir…' : 'Agregar');
}

async function recargar() {
  E.estado = null;
  await cargar();
}

async function ruta() {
  if (tarea && tarea.trabajando && !location.hash.startsWith('#/tarea')) {
    if (!confirmarSalida()) { history.back(); return; }
  }
  if (!E.estado) {
    try { await cargar(); } catch (e) { montar(h('p', { class: 'error' }, 'No pude hablar con el asistente. ¿Se cerró la ventana negra? Volvé a abrirlo con «Abrir asistente».')); return; }
  }
  const [, vista, id] = location.hash.split('/');
  if (vista === 'tarea' && tarea) return; // la tarea ya está montada
  if (tarea) cerrarTarea();
  if (vista === 'receta' && id) return verReceta(id);
  if (vista === 'estado') return verEstado();
  if (vista === 'ayuda') return verAyuda();
  if (vista === 'campus') return verCampus();
  verInicio();
}
function confirmarSalida() {
  return window.confirm('Claude todavía está trabajando en esta tarea. ¿Salir igual? Lo que esté haciendo se va a cortar.');
}

// ------------------------------------------------------------------ inicio
function verInicio() {
  const nombre = (E.estado.tutor || '').split(' ')[0];
  const secciones = E.estado.skills.map((s) => {
    const recs = E.catalogo.recetas.filter((r) => r.skill === s.id);
    const deshabilitada = s.bloqueada || !s.instalada;
    return h('section', { class: 'seccion', 'aria-labelledby': 'sec-' + s.id },
      h('div', { class: 'seccion-cabeza' },
        h('h2', { id: 'sec-' + s.id }, s.titulo),
        h('p', {}, s.bajada)),
      h('div', {},
        deshabilitada ? h('p', { class: 'aviso' }, s.motivo) : null,
        h('ul', { class: 'acciones' }, recs.map((r) =>
          h('li', {}, h('button', {
            class: 'accion', type: 'button', disabled: deshabilitada,
            onclick: () => { location.hash = '#/receta/' + r.id; },
          },
          h('span', { class: 'accion-texto' },
            h('span', { class: 'accion-titulo' }, r.titulo),
            h('span', { class: 'accion-bajada' }, r.bajada)),
          h('span', { class: 'flecha', 'aria-hidden': 'true' }, '→')))))));
  });
  const mal = E.estado.chequeos.filter((c) => !c.ok);
  montar(
    h('div', { class: 'saludo' },
      h('h1', {}, nombre ? `Hola, ${nombre}.` : 'Hola.'),
      h('p', {}, 'Elegí qué querés hacer. Te voy a pedir sólo lo necesario y te muestro cada paso.'),
      (() => {
        const activo = (E.campus?.campus || []).find((k) => String(k.id) === String(E.campus.activo));
        return h('p', { class: 'meta', style: 'margin-top:10px' }, 'Trabajando en el campus: ', h('strong', {}, activo ? activo.nombre : 'sin elegir'), ' · ', h('a', { href: '#/campus' }, 'Cambiar o agregar otro'));
      })()),
    mal.length ? h('p', { class: 'aviso' }, 'Hay cosas por configurar antes de usar todo. ', h('a', { href: '#/estado' }, 'Ver qué falta')) : null,
    ...secciones,
  );
}

// ------------------------------------------------------------------ receta
function verReceta(id) {
  const r = E.catalogo.recetas.find((x) => x.id === id);
  if (!r) { location.hash = '#/'; return; }
  const skill = E.estado.skills.find((s) => s.id === r.skill);
  const valores = {};
  const errores = h('p', { class: 'error-form', role: 'alert' });
  const bus = new EventTarget(); // avisa a comisión/tarea que cambió la materia
  const campos = r.campos.map((c) => campo(c, valores, bus));
  const boton = h('button', { class: 'boton', type: 'submit' }, 'Empezar');
  const form = h('form', { class: 'formulario', onsubmit: (ev) => {
    ev.preventDefault();
    const falta = r.campos.filter((c) => !c.opcional && !(valores[c.id] || '').trim()).map((c) => c.etiqueta);
    if (falta.length) { errores.textContent = 'Falta completar: ' + falta.join(', ') + '.'; return; }
    if (Object.values(valores).includes('__subiendo__')) { errores.textContent = 'Esperá a que terminen de subir los archivos.'; return; }
    empezar(r, valores);
  } }, ...campos, errores, h('div', {}, boton));

  montar(
    h('button', { class: 'volver', type: 'button', onclick: () => { location.hash = '#/'; } }, '← Volver al inicio'),
    h('p', { class: 'ruta' }, skill ? skill.titulo : ''),
    h('h1', {}, r.titulo),
    h('p', { class: 'meta', style: 'font-size:15px' }, r.bajada),
    h('div', { class: 'obtenes' }, h('strong', {}, 'Qué vas a obtener'), r.resultado),
    r.campos.length ? form : h('div', {}, h('button', { class: 'boton', type: 'button', onclick: () => empezar(r, valores) }, 'Empezar')),
  );
  const primero = form.querySelector('input, select, textarea');
  if (primero) primero.focus();
}

function campo(c, valores, bus) {
  const id = 'c-' + c.id;
  const etiqueta = h('label', { for: id }, c.etiqueta, c.opcional && !/opcional/i.test(c.etiqueta) ? h('span', { class: 'opcional' }, ' (opcional)') : null);
  const ayuda = c.ayuda ? h('span', { class: 'ayuda' }, c.ayuda) : null;
  const cursos = E.catalogo.cursos;
  let control;

  const set = (v) => { valores[c.id] = v; };

  if ((c.tipo === 'curso' || c.tipo === 'comision' || c.tipo === 'tarea') && cursos.length) {
    control = h('select', { id });
    const llenar = () => {
      const opciones = [h('option', { value: '' }, c.opcional ? 'Todas' : 'Elegí…')];
      if (c.tipo === 'curso') {
        cursos.forEach((k) => opciones.push(h('option', { value: `${k.nombre} (course_id ${k.id})`, 'data-id': k.id }, k.nombre)));
      } else {
        const elegido = cursos.find((k) => String(k.id) === String(valores.__curso_id));
        const lista = elegido ? (c.tipo === 'comision' ? elegido.comisiones : elegido.tareas) : [];
        const clave = c.tipo === 'comision' ? 'group_id' : 'assign_id';
        lista.forEach((x) => opciones.push(h('option', { value: `${x.nombre} (${clave} ${x.id})` }, x.nombre)));
        control.disabled = !elegido;
        if (!elegido) opciones[0].textContent = 'Primero elegí la materia';
      }
      control.replaceChildren(...opciones);
      set('');
    };
    control.addEventListener('change', () => {
      set(control.value);
      if (c.tipo === 'curso') {
        valores.__curso_id = control.selectedOptions[0]?.dataset.id || '';
        bus.dispatchEvent(new Event('curso-cambio'));
      }
    });
    if (c.tipo !== 'curso') bus.addEventListener('curso-cambio', llenar);
    llenar();
  } else if (c.tipo === 'archivo' || c.tipo === 'archivos') {
    const input = h('input', { type: 'file', id, accept: c.acepta || null, multiple: c.tipo === 'archivos' });
    const lista = h('div', { class: 'lista-subidos', 'aria-live': 'polite' });
    const elegir = h('button', { type: 'button', class: 'boton secundario chico', onclick: () => input.click() }, c.tipo === 'archivos' ? 'Elegir archivos' : 'Elegir archivo');
    const subirArchivos = async (files) => {
      if (!files.length) return;
      const fd = new FormData();
      [...files].forEach((f) => fd.append('archivos', f));
      set('__subiendo__');
      lista.textContent = 'Subiendo…';
      try {
        const r = await api('/api/subir', { method: 'POST', body: fd });
        set(r.archivos.map((a) => a.ruta).join(', '));
        lista.replaceChildren(...r.archivos.map((a) => h('div', {}, '✓ ', a.nombre)));
      } catch (e) {
        set('');
        lista.textContent = 'No se pudo subir: ' + e.message;
      }
    };
    input.addEventListener('change', () => subirArchivos(input.files));
    control = h('div', { class: 'subir' }, elegir, h('span', { class: 'ayuda' }, 'o arrastralo acá'), input, lista);
    control.addEventListener('dragover', (e) => { e.preventDefault(); control.classList.add('arrastrando'); });
    control.addEventListener('dragleave', () => control.classList.remove('arrastrando'));
    control.addEventListener('drop', (e) => { e.preventDefault(); control.classList.remove('arrastrando'); subirArchivos(c.tipo === 'archivo' ? [...e.dataTransfer.files].slice(0, 1) : e.dataTransfer.files); });
  } else if (c.tipo === 'opcion') {
    control = h('select', { id, onchange: (e) => set(e.target.value) }, h('option', { value: '' }, 'Elegí…'), c.opciones.map((o) => h('option', { value: o }, o)));
  } else if (c.tipo === 'parrafo') {
    control = h('textarea', { id, oninput: (e) => set(e.target.value) });
  } else {
    control = h('input', { type: 'text', id, oninput: (e) => set(e.target.value), placeholder: c.tipo === 'curso' ? 'Nombre de la materia' : null });
  }
  return h('div', { class: 'campo' }, etiqueta, ayuda, control);
}

// ------------------------------------------------------------------ tarea
function empezar(receta, valores) {
  const limpio = Object.fromEntries(Object.entries(valores).filter(([k]) => !k.startsWith('__')));
  tarea = { sid: null, receta, trabajando: false };
  history.pushState(null, '', '#/tarea');
  montarTarea(receta);
  correr({ receta: receta.id, valores: limpio });
}

function montarTarea(receta) {
  const T = tarea;
  T.$pedido = h('details', { class: 'pedido-hecho' }, h('summary', {}, 'Lo que le pedí a Claude'), h('p', {}));
  T.$cuerpo = h('div', {});
  T.$texto = h('textarea', { placeholder: '¿Querés ajustar algo o seguir con otra cosa sobre esto? Escribilo acá…', 'aria-label': 'Seguir la tarea' });
  T.$enviar = h('button', { class: 'boton', type: 'submit' }, 'Enviar');
  const seguir = h('div', { class: 'seguir' },
    T.$form = h('form', { hidden: true, onsubmit: (e) => { e.preventDefault(); const t = T.$texto.value.trim(); if (t && !T.trabajando) { T.$texto.value = ''; correr({ texto: t }); } } }, T.$texto, T.$enviar),
    h('div', { class: 'pie-tarea' },
      h('button', { class: 'boton secundario chico', type: 'button', onclick: () => { if (!T.trabajando || confirmarSalida()) { cerrarTarea(); location.hash = '#/'; } } }, 'Terminar y volver al inicio'),
      h('button', { class: 'boton secundario chico', type: 'button', onclick: () => { if (!T.trabajando || confirmarSalida()) { const r = T.receta; cerrarTarea(); location.hash = '#/receta/' + r.id; } } }, 'Hacer lo mismo con otros datos')));
  T.$texto.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); T.$texto.form.requestSubmit(); } });
  montar(h('p', { class: 'ruta' }, 'Tarea'), h('h1', {}, receta.titulo), T.$pedido, T.$cuerpo, seguir);
}

function cerrarTarea() {
  if (tarea?.sid) api('/api/tarea/' + tarea.sid, { method: 'DELETE' }).catch(() => {});
  tarea?.ctrl?.abort();
  tarea = null;
}

async function correr(pedido) {
  const T = tarea;
  T.trabajando = true;
  T.$enviar.disabled = true;
  // Mientras trabaja la caja de seguimiento no sirve y taparía las tarjetas de pregunta.
  T.$form.hidden = true;
  // Cada turno arma su bloque: línea de pasos + respuesta.
  const turno = h('div', {});
  if (pedido.texto) turno.append(h('p', { class: 'meta', style: 'margin:32px 0 12px' }, 'Vos: ', pedido.texto));
  let linea, resp;
  // Tramo nuevo de pasos + respuesta. Se abre otro después de cada tarjeta, para que lo que
  // Claude hace tras una respuesta o una confirmación aparezca debajo y no arriba.
  const tramo = () => {
    linea = h('ol', { class: 'linea', 'aria-live': 'polite' });
    resp = h('div', { class: 'respuesta' });
    turno.append(linea, resp);
  };
  tramo();
  T.$cuerpo.append(turno);

  let texto = '';
  let pintar = 0;
  let pasoActivo = null;
  let reloj = 0;
  const cerrarPaso = () => {
    clearInterval(reloj);
    if (pasoActivo) { pasoActivo.classList.remove('activo'); pasoActivo.querySelector('.icono').textContent = '✓'; pasoActivo = null; }
  };
  const paso = (t) => {
    if (pasoActivo && pasoActivo.dataset.t === t) return; // no repetir el mismo paso seguido
    cerrarPaso();
    // Contador visible: un paso lento (el panorama de 16 comisiones) no tiene que parecer colgado.
    const seg = h('span', { class: 'segundos' });
    const desde = Date.now();
    reloj = setInterval(() => { const s = Math.round((Date.now() - desde) / 1000); if (s >= 5) seg.textContent = ` ${s} s`; }, 1000);
    pasoActivo = h('li', { class: 'activo', 'data-t': t }, h('span', { class: 'icono', 'aria-hidden': 'true' }), h('span', {}, t + '…', seg));
    linea.append(pasoActivo);
  };
  const volcarNota = () => {
    // El texto intermedio ("voy a revisar…") pasa a la línea de pasos; sólo el último queda como respuesta.
    if (texto.trim()) linea.append(h('li', { class: 'nota' }, h('span', { class: 'icono', 'aria-hidden': 'true' }, '·'), h('div', { html: md(texto) })));
    texto = ''; resp.innerHTML = '';
  };
  const render = () => { pintar = 0; resp.innerHTML = md(texto); };

  T.ctrl = new AbortController();
  try {
    const r = await fetch('/api/tarea', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: T.ctrl.signal,
      body: JSON.stringify({ ...pedido, sesion: T.sid }),
    });
    if (!r.ok) { let m = 'Error ' + r.status; try { m = (await r.json()).detail || m; } catch (e) {} throw new Error(m); }
    const lector = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await lector.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const bloque = buf.slice(0, i); buf = buf.slice(i + 2);
        const linea_ = bloque.split('\n').find((l) => l.startsWith('data: '));
        if (!linea_) continue;
        const ev = JSON.parse(linea_.slice(6));
        switch (ev.tipo) {
          case 'sesion':
            T.sid = ev.id;
            if (ev.pedido && !T.$pedido.querySelector('p').textContent) T.$pedido.querySelector('p').textContent = ev.pedido;
            break;
          case 'paso':
            if (texto.trim()) volcarNota();
            paso(ev.texto);
            break;
          case 'texto':
            cerrarPaso();
            texto += ev.delta;
            if (!pintar) pintar = requestAnimationFrame(render);
            break;
          case 'corte':
            break;
          case 'pregunta':
            if (texto.trim()) volcarNota();
            cerrarPaso();
            turno.append(tarjetaPregunta(ev));
            tramo();
            break;
          case 'confirmacion':
            if (texto.trim()) volcarNota();
            cerrarPaso();
            turno.append(tarjetaConfirmar(ev));
            tramo();
            break;
          case 'archivos':
            turno.append(listaArchivos(ev.archivos));
            break;
          case 'error':
            turno.append(h('p', { class: 'error', role: 'alert' }, ev.mensaje));
            break;
          case 'fin':
            cerrarPaso();
            if (pintar) { cancelAnimationFrame(pintar); render(); }
            // Si la receta usó `usar_campus` el tenant activo pudo haber cambiado en
            // ~/.moodle-skill/estado.json; se refresca acá (no sólo al guardar config)
            // para que la próxima pantalla de receta muestre el «(activo)» correcto.
            api('/api/campus').then((c) => { E.campus = c; }).catch(() => {});
            break;
        }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') turno.append(h('p', { class: 'error', role: 'alert' }, e.message));
  } finally {
    cerrarPaso();
    if (tarea === T) { T.trabajando = false; T.$enviar.disabled = false; T.$form.hidden = false; }
  }
}

function tarjetaPregunta(ev) {
  const respuestas = {};
  const bloques = ev.preguntas.map((q) => {
    const elegidas = new Set();
    const otra = h('input', { type: 'text', class: 'otra', placeholder: 'Otra respuesta (opcional)', 'aria-label': 'Otra respuesta para: ' + q.question });
    const botones = (q.options || []).map((o) => {
      const b = h('button', { type: 'button', class: 'opcion', 'aria-pressed': 'false', onclick: () => {
        if (q.multiSelect) { elegidas.has(o.label) ? elegidas.delete(o.label) : elegidas.add(o.label); }
        else { elegidas.clear(); elegidas.add(o.label); botones.forEach((x) => x.setAttribute('aria-pressed', 'false')); }
        b.setAttribute('aria-pressed', elegidas.has(o.label) ? 'true' : 'false');
      } }, h('strong', {}, o.label), o.description ? h('span', {}, o.description) : null);
      return b;
    });
    respuestas[q.question] = () => (otra.value.trim() ? [...elegidas, otra.value.trim()] : [...elegidas]).join(', ');
    return h('div', { class: 'pregunta' },
      q.header ? h('span', { class: 'chip' }, q.header) : null,
      h('p', {}, q.question, q.multiSelect ? h('span', { class: 'meta' }, ' (podés elegir varias)') : null),
      h('div', { class: 'opciones' }, botones), otra);
  });
  const aviso = h('p', { class: 'error-form', role: 'alert' });
  const enviar = h('button', { class: 'boton', type: 'button' }, 'Responder');
  const saltar = h('button', { class: 'boton secundario', type: 'button' }, 'Prefiero no contestar');
  const tarjeta = h('div', { class: 'tarjeta' }, h('h3', {}, 'Claude necesita que decidas'), ...bloques, aviso, h('div', { class: 'botones' }, enviar, saltar));
  const cerrar = (texto) => { tarjeta.querySelectorAll('button, input').forEach((x) => { x.disabled = true; }); tarjeta.querySelector('.botones').replaceWith(h('p', { class: 'hecho-confirmar' }, texto)); };
  enviar.onclick = async () => {
    const r = Object.fromEntries(Object.entries(respuestas).map(([k, f]) => [k, f()]));
    if (Object.values(r).some((v) => !v)) { aviso.textContent = 'Elegí una opción en cada pregunta (o escribí otra respuesta).'; return; }
    try { await api(`/api/tarea/${tarea.sid}/responder`, { method: 'POST', body: { id: ev.id, ok: true, respuestas: r } }); cerrar('Respondido: ' + Object.values(r).join(' · ')); }
    catch (e) { aviso.textContent = e.message; }
  };
  saltar.onclick = async () => {
    try { await api(`/api/tarea/${tarea.sid}/responder`, { method: 'POST', body: { id: ev.id, ok: false } }); cerrar('No contestaste esta pregunta.'); }
    catch (e) { aviso.textContent = e.message; }
  };
  setTimeout(() => tarjeta.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
  return tarjeta;
}

const ETIQUETAS = {
  nota: 'Nota', grade: 'Nota', calificacion: 'Nota', feedback: 'Devolución', devolucion: 'Devolución', comentario: 'Comentario',
  texto: 'Texto', mensaje: 'Mensaje', asunto: 'Asunto', alumno: 'Alumno', tarea: 'Tarea', userid: 'Alumno (id)', assign_id: 'Tarea (id)',
};
function tarjetaConfirmar(ev) {
  const entrada = { ...ev.entrada };
  const editables = h('div', {});
  const leer = {};
  for (const [k, v] of Object.entries(entrada)) {
    if (k === 'confirmado') continue;
    const id = 'conf-' + ev.id + '-' + k;
    const crudo = k.replaceAll('_', ' ');
    const etq = ETIQUETAS[k] || crudo.charAt(0).toUpperCase() + crudo.slice(1);
    if (typeof v === 'string' || typeof v === 'number') {
      const largo = String(v).length > 60 || /feedback|devol|texto|mensaje|coment/i.test(k);
      const ctrl = largo ? h('textarea', { id }, String(v)) : h('input', { type: 'text', id, value: String(v) });
      leer[k] = () => (typeof v === 'number' && ctrl.value.trim() !== '' && !isNaN(+ctrl.value) ? +ctrl.value : ctrl.value);
      editables.append(h('div', { class: 'campo' }, h('label', { for: id }, etq), ctrl));
    } else if (typeof v === 'boolean') {
      // se manda tal cual
    } else {
      editables.append(h('div', { class: 'campo' }, h('span', { class: 'meta' }, etq), h('pre', {}, JSON.stringify(v, null, 2))));
    }
  }
  const aviso = h('p', { class: 'error-form', role: 'alert' });
  const si = h('button', { class: 'boton ' + (ev.irreversible ? 'peligro' : ''), type: 'button' }, ev.irreversible ? 'Confirmar y escribir en el campus' : 'Confirmar');
  const no = h('button', { class: 'boton secundario', type: 'button' }, 'No, cancelar');
  const tarjeta = h('div', { class: 'tarjeta confirmar' + (ev.irreversible ? '' : ' suave'), role: 'group', 'aria-label': 'Confirmación' },
    h('h3', {}, ev.irreversible ? 'Antes de escribir en el campus' : 'Antes de seguir'),
    h('p', { style: 'margin:0' }, ev.accion + '. ', ev.irreversible ? 'Revisá y corregí lo que haga falta: una vez confirmado no se puede deshacer desde acá.' : 'Esto cambia tu configuración local.'),
    editables, aviso, h('div', { class: 'botones' }, si, no));
  const cerrar = (t) => { tarjeta.querySelectorAll('button, input, textarea').forEach((x) => { x.disabled = true; }); tarjeta.querySelector('.botones').replaceWith(h('p', { class: 'hecho-confirmar' }, t)); };
  si.onclick = async () => {
    const final = { ...entrada };
    for (const [k, f] of Object.entries(leer)) final[k] = f();
    try { await api(`/api/tarea/${tarea.sid}/responder`, { method: 'POST', body: { id: ev.id, ok: true, entrada: final } }); cerrar('Confirmado.'); }
    catch (e) { aviso.textContent = e.message; }
  };
  no.onclick = async () => {
    try { await api(`/api/tarea/${tarea.sid}/responder`, { method: 'POST', body: { id: ev.id, ok: false, motivo: 'La persona canceló esta operación desde la pantalla.' } }); cerrar('Cancelado. No se escribió nada.'); }
    catch (e) { aviso.textContent = e.message; }
  };
  setTimeout(() => tarjeta.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
  return tarjeta;
}

function listaArchivos(archivos) {
  const abrir = (ruta, carpeta) => api('/api/abrir', { method: 'POST', body: { ruta, carpeta } }).catch((e) => alertaSuave(e.message));
  return h('div', { class: 'archivos' },
    h('h3', {}, archivos.length === 1 ? 'Archivo que quedó' : 'Archivos que quedaron'),
    archivos.map((a) => h('div', { class: 'archivo' },
      h('span', { class: 'nombre' }, a.nombre),
      h('button', { class: 'boton chico', type: 'button', onclick: () => abrir(a.ruta, false) }, 'Abrir'),
      h('button', { class: 'boton secundario chico', type: 'button', onclick: () => abrir(a.ruta, true) }, 'Mostrar en la carpeta'),
      h('span', { class: 'donde' }, a.ruta))));
}
function alertaSuave(msg) {
  const p = h('p', { class: 'error', role: 'alert' }, msg);
  $vista.append(p); setTimeout(() => p.remove(), 5000);
}

// ------------------------------------------------------------------ estado
function verEstado() {
  const s = E.estado;
  const trabajo = h('input', { type: 'text', id: 'cfg-trabajo', value: s.carpeta_trabajo });
  const informes = h('input', { type: 'text', id: 'cfg-informes', value: s.carpeta_informes });
  const msg = h('p', { class: 'meta', 'aria-live': 'polite' });
  montar(
    h('button', { class: 'volver', type: 'button', onclick: () => { location.hash = '#/'; } }, '← Volver al inicio'),
    h('h1', {}, '¿Está todo listo?'),
    h('p', { class: 'meta', style: 'font-size:15px' }, 'Lo que el asistente necesita para funcionar en esta computadora.'),
    h('ul', { class: 'chequeos' },
      s.chequeos.map((c) => h('li', { class: 'chequeo' },
        h('span', { class: 'marca-estado ' + (c.ok ? 'ok' : 'mal') }, c.ok ? '✓ Listo' : '! Falta'),
        h('div', {}, h('h3', {}, c.titulo), h('p', {}, c.ok ? (c.detalle || '') : c.si_falla)))),
      s.skills.map((k) => h('li', { class: 'chequeo' },
        h('span', { class: 'marca-estado ' + (k.instalada && !k.bloqueada ? 'ok' : 'mal') }, k.instalada && !k.bloqueada ? '✓ Lista' : '! No disponible'),
        h('div', {}, h('h3', {}, k.titulo), h('p', {}, k.motivo || `Skill «${k.skill}» instalada.`))))),
    h('h2', {}, 'Carpetas'),
    h('form', { class: 'formulario', style: 'margin-top:16px', onsubmit: async (e) => {
      e.preventDefault();
      try {
        await api('/api/config', { method: 'POST', body: { carpeta_trabajo: trabajo.value, carpeta_informes: informes.value } });
        E.estado = null; await cargar(); msg.textContent = 'Guardado.';
      } catch (err) { msg.textContent = err.message; }
    } },
    h('div', { class: 'campo' }, h('label', { for: 'cfg-trabajo' }, 'Carpeta de trabajo'), h('span', { class: 'ayuda' }, 'Acá quedan los archivos que subís y lo que Claude produce (rúbricas, apuntes…).'), trabajo),
    h('div', { class: 'campo' }, h('label', { for: 'cfg-informes' }, 'Carpeta de informes'), h('span', { class: 'ayuda' }, 'Los PDF del campus se copian acá al terminar cada tarea.'), informes),
    h('div', {}, h('button', { class: 'boton', type: 'submit' }, 'Guardar')), msg),
  );
}

// ------------------------------------------------------------------ campus
function verCampus() {
  const lista = E.campus?.campus || [];
  const msg = h('p', { class: 'error-form', role: 'alert', 'aria-live': 'polite' });
  const ok = h('p', { class: 'meta', role: 'status', 'aria-live': 'polite' });

  const cambiar = async (k, boton) => {
    msg.textContent = ''; ok.textContent = '';
    boton.disabled = true;
    try {
      E.campus = await api('/api/campus/activo', { method: 'POST', body: { id: k.id } });
      await recargar();
      verCampus();
    } catch (e) { msg.textContent = e.message; boton.disabled = false; }
  };

  const items = lista.map((k) => {
    const activo = String(k.id) === String(E.campus.activo);
    const boton = h('button', { type: 'button', class: 'boton secundario chico' }, 'Usar este');
    boton.addEventListener('click', () => cambiar(k, boton));
    return h('li', { class: 'campus-item' + (activo ? ' activo' : '') },
      h('div', { class: 'campus-datos' }, h('strong', {}, k.nombre), h('span', {}, k.url || '')),
      activo ? h('span', { class: 'campus-insignia' }, '● Activo') : boton);
  });

  const v = {};
  const campoForm = (id, etiqueta, tipo, ayuda, extra = {}) => {
    const input = h('input', { type: tipo, id: 'f-' + id, autocomplete: 'off', ...extra });
    input.addEventListener('input', () => { v[id] = input.value; });
    return h('div', { class: 'campo' }, h('label', { for: 'f-' + id }, etiqueta), input, ayuda ? h('span', { class: 'ayuda' }, ayuda) : null);
  };
  const enviar = h('button', { class: 'boton', type: 'submit' }, 'Probar conexión y agregar');
  const form = h('form', { class: 'formulario campus-form', novalidate: true, onsubmit: async (ev) => {
    ev.preventDefault();
    msg.textContent = ''; ok.textContent = '';
    // Se lee del DOM y no de los eventos 'input': el autocompletado del navegador no siempre los dispara.
    form.querySelectorAll('input').forEach((i) => { v[i.id.replace(/^f-/, '')] = i.value; });
    const falta = [['nombre', 'el nombre'], ['url', 'la dirección'], ['moodle_user', 'el usuario'], ['moodle_pass', 'la contraseña']]
      .filter(([k]) => !(v[k] || '').trim()).map(([, t]) => t);
    if (falta.length) { msg.textContent = 'Falta completar ' + falta.join(', ') + '.'; return; }
    if (!!(v.activeia_user || '').trim() !== !!v.activeia_pass) { msg.textContent = 'Para Active-IA cargá usuario y contraseña, o dejá los dos vacíos.'; return; }
    enviar.disabled = true; enviar.textContent = 'Probando la conexión… (puede tardar un minuto)';
    try {
      E.campus = await api('/api/campus', { method: 'POST', body: {
        nombre: v.nombre, url: v.url, moodle_user: v.moodle_user, moodle_pass: v.moodle_pass,
        activeia_user: v.activeia_user || '', activeia_pass: v.activeia_pass || '',
      } });
      await recargar();
      location.hash = '#/';
    } catch (e) {
      msg.textContent = e.message;
      enviar.disabled = false; enviar.textContent = 'Probar conexión y agregar';
    }
  } },
  h('fieldset', {}, h('legend', {}, 'Campus'),
    campoForm('nombre', 'Nombre', 'text', 'Como querés verlo en la lista. Ej.: «UTN Mendoza».'),
    campoForm('url', 'Dirección del campus', 'url', 'La URL de tu Moodle. Ej.: https://campus.miuniversidad.edu.ar', { placeholder: 'https://' }),
    campoForm('moodle_user', 'Usuario del campus', 'text'),
    campoForm('moodle_pass', 'Contraseña del campus', 'password')),
  h('fieldset', {}, h('legend', {}, 'Active-IA (opcional)'),
    h('p', { class: 'meta', style: 'margin:0' }, 'Si en Active-IA usás otro usuario para este campus, cargalo acá. Si no corregís con Active-IA, dejalo vacío.'),
    campoForm('activeia_user', 'Usuario de Active-IA', 'text'),
    campoForm('activeia_pass', 'Contraseña de Active-IA', 'password')),
  h('p', { class: 'meta', style: 'margin:0' }, 'Antes de guardar se prueba el ingreso. Los datos quedan sólo en esta computadora. Después se buscan tus materias y comisiones y el campus pasa a ser el activo.'),
  msg, h('div', {}, enviar));

  montar(
    h('button', { class: 'volver', type: 'button', onclick: () => { location.hash = '#/'; } }, '← Volver al inicio'),
    h('h1', {}, 'Campus'),
    h('p', { class: 'meta', style: 'font-size:15px' }, 'Las materias, comisiones y acciones dependen del campus activo. Elegí con cuál trabajar o sumá otro.'),
    lista.length ? h('ul', { class: 'campus-lista' }, items) : h('p', { class: 'aviso' }, 'Todavía no hay ningún campus dado de alta.'),
    ok,
    h('h2', { style: 'margin-top:32px' }, 'Agregar un campus'),
    form,
  );
}

// ------------------------------------------------------------------ ayuda
async function verAyuda() {
  let texto;
  try { texto = (await api('/api/guia')).texto; } catch (e) { montar(h('p', { class: 'error' }, 'No pude cargar la guía.')); return; }
  const cuerpo = h('div', { class: 'respuesta guia', html: md(texto) });
  const slug = (t) => t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 -]/g, '').trim().replace(/ +/g, '-');
  cuerpo.querySelectorAll('h1, h2, h3').forEach((el) => { el.id = 'g-' + slug(el.textContent); });
  cuerpo.querySelectorAll('a[href]').forEach((a) => {
    const href = a.getAttribute('href');
    if (href.startsWith('#')) {
      // Los enlaces internos de la guía no pueden tocar el hash: es la navegación de la app.
      a.addEventListener('click', (e) => { e.preventDefault(); document.getElementById('g-' + href.slice(1))?.scrollIntoView(); });
    } else {
      a.target = '_blank'; a.rel = 'noopener';
    }
  });
  montar(h('button', { class: 'volver', type: 'button', onclick: () => { location.hash = '#/'; } }, '← Volver al inicio'), cuerpo);
}

// ------------------------------------------------------------------ barra
const $tema = document.getElementById('tema');
function temaActual() {
  const t = document.documentElement.dataset.theme;
  if (t) return t;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
function pintarTema() { $tema.textContent = temaActual() === 'dark' ? 'Modo claro' : 'Modo oscuro'; }
$tema.addEventListener('click', () => {
  const nuevo = temaActual() === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = nuevo;
  try { localStorage.setItem('tema', nuevo); } catch (e) {}
  pintarTema();
});
pintarTema();

document.getElementById('apagar').addEventListener('click', async () => {
  if (tarea?.trabajando && !confirmarSalida()) return;
  try { await api('/api/apagar', { method: 'POST' }); } catch (e) {}
  montar(h('h1', {}, 'El asistente se cerró.'), h('p', { class: 'meta', style: 'font-size:15px' }, 'Ya podés cerrar esta pestaña. Para volver a usarlo, abrí «Abrir asistente».'));
});

window.addEventListener('hashchange', ruta);
window.addEventListener('beforeunload', (e) => { if (tarea?.trabajando) { e.preventDefault(); e.returnValue = ''; } });
ruta();
