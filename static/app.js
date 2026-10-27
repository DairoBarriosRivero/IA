// La interfaz NO contiene calificaciones: todo viene de /api/estudiantes,
// que lee estudiantes.json y calcula con calculos.py (RF07).

const formato = new Intl.NumberFormat("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nota = (n) => (n === null || n === undefined ? "—" : formato.format(n));

const CLASES = {
  "Perdió": { css: "perdio", icono: "✕" },
  "Ganó": { css: "gano", icono: "✓" },
  "Sobresaliente": { css: "sobresaliente", icono: "★" },
  "Pendiente": { css: "pendiente", icono: "○" },
};

function el(etiqueta, atributos = {}, ...hijos) {
  const nodo = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(atributos)) {
    if (clave === "class") nodo.className = valor;
    else nodo.setAttribute(clave, valor);
  }
  for (const hijo of hijos) nodo.append(hijo);
  return nodo;
}

function insignia(clasificacion) {
  const { css, icono } = CLASES[clasificacion];
  return el("span", { class: `insignia ${css}` }, el("span", { "aria-hidden": "true" }, icono), ` ${clasificacion}`);
}

let datos = null;
let seleccionado = null;
let editando = false;
let temporizadorAviso = null;

// --- Avisos y comunicación con el servidor ----------------------------------
function avisar(texto, tipo = "ok") {
  const aviso = document.getElementById("aviso");
  aviso.textContent = texto;
  aviso.className = `aviso ${tipo}`;
  aviso.hidden = false;
  clearTimeout(temporizadorAviso);
  if (tipo === "ok") temporizadorAviso = setTimeout(() => (aviso.hidden = true), 6000);
}

function ocultarAviso() {
  clearTimeout(temporizadorAviso);
  document.getElementById("aviso").hidden = true;
}

async function enviar(metodo, url, cuerpo) {
  const respuesta = await fetch(url, {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
  const json = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) throw new Error(json.error || "Error del servidor.");
  return json;
}

// --- Dibujo -----------------------------------------------------------------
function dibujarEncabezado() {
  const { grupo, estudiantes } = datos;
  document.getElementById("subtitulo").textContent =
    `${grupo.total_estudiantes} estudiantes, ${estudiantes[0].asignaturas.length} asignaturas y 3 cortes por asignatura. ` +
    `${grupo.estudiantes_con_perdidas} tienen al menos una asignatura perdida.`;
  document.getElementById("grupo-valor").textContent = nota(grupo.promedio_general);
  document.getElementById("grupo").hidden = false;
}

function dibujarLista() {
  const lista = document.getElementById("lista");
  lista.replaceChildren();
  for (const est of datos.estudiantes) {
    const franja = el("div", { class: "franja", "aria-hidden": "true" });
    for (const asig of est.asignaturas) {
      const detalle = asig.definitiva === null ? "pendiente" : `${nota(asig.definitiva)} (${asig.clasificacion})`;
      franja.append(el("span", { class: CLASES[asig.clasificacion].css, title: `${asig.nombre}: ${detalle}` }));
    }
    const boton = el(
      "button",
      { class: "estudiante", type: "button", "data-codigo": est.codigo, "aria-current": String(est.codigo === seleccionado) },
      el("span", { class: "nombre" }, est.nombre),
      el("span", { class: "promedio" }, nota(est.promedio_general)),
      el("span", { class: "codigo" }, `Código ${est.codigo}`),
      franja
    );
    boton.addEventListener("click", () => {
      seleccionar(est.codigo);
      document.querySelector('.estudiante[aria-current="true"]')?.focus();
    });
    lista.append(el("li", {}, boton));
  }
}

function dato(etiqueta, valor, css = "", pie = "") {
  const nodo = el("div", { class: `dato ${css}` }, el("span", { class: "etiqueta" }, etiqueta), el("span", { class: "valor" }, String(valor)));
  if (pie) nodo.append(el("span", { class: "pie" }, pie));
  return nodo;
}

function celdaCorte(asig, i, j) {
  const valor = asig.cortes[j];
  if (!editando) return el("td", { class: valor !== null && valor < 3 ? "baja" : "" }, nota(valor));
  return el(
    "td",
    {},
    el("input", {
      type: "number", min: "0", max: "5", step: "0.01", inputmode: "decimal",
      "data-asig": String(i), "data-corte": String(j),
      "aria-label": `${asig.nombre}, corte ${j + 1}`,
      value: valor === null ? "" : String(valor),
    })
  );
}

function dibujarDetalle() {
  const est = datos.estudiantes.find((e) => e.codigo === seleccionado);
  const detalle = document.getElementById("detalle");
  detalle.replaceChildren();
  if (!est) return;

  const filas = est.asignaturas.map((a, i) =>
    el(
      "tr",
      { class: CLASES[a.clasificacion].css },
      el("th", { scope: "row" }, a.nombre),
      ...[0, 1, 2].map((j) => celdaCorte(a, i, j)),
      el("td", { class: "definitiva" }, nota(a.definitiva)),
      el("td", {}, insignia(a.clasificacion))
    )
  );

  const tabla = el(
    "table",
    {},
    el("caption", { class: "sr-only" }, `Notas de ${est.nombre}`),
    el("thead", {}, el("tr", {}, ...["Asignatura", "Corte 1", "Corte 2", "Corte 3", "Definitiva", "Resultado"].map((t) => el("th", { scope: "col" }, t)))),
    el("tbody", {}, ...filas)
  );

  const acciones = el("div", { class: "acciones" });
  if (editando) {
    const guardar = el("button", { class: "boton primario", type: "button" }, "Guardar notas");
    const cancelar = el("button", { class: "boton", type: "button" }, "Cancelar");
    guardar.addEventListener("click", guardarNotas);
    cancelar.addEventListener("click", () => { editando = false; ocultarAviso(); dibujarDetalle(); });
    acciones.append(guardar, cancelar);
  } else {
    const editar = el("button", { class: "boton primario", type: "button" }, "Editar notas");
    editar.addEventListener("click", () => entrarEdicion());
    acciones.append(editar);
  }

  const r = est.resumen;
  const pieProm = est.promedio_general === null
    ? "Aún no hay asignaturas completas"
    : est.asignaturas_calificadas < est.asignaturas.length
      ? `Con ${est.asignaturas_calificadas} de ${est.asignaturas.length} asignaturas completas`
      : "";
  const resumen = el(
    "div",
    { class: "resumen" },
    dato("Promedio general", nota(est.promedio_general), "", pieProm),
    dato("Aprobadas", r.aprobadas, "gano"),
    dato("Reprobadas", r.reprobadas, "perdio"),
    dato("Sobresalientes", r.sobresalientes, "sobresaliente")
  );
  if (r.pendientes > 0) resumen.append(dato("Pendientes", r.pendientes, "pendiente"));

  detalle.append(
    el("div", { class: "detalle-cabecera" }, el("div", {}, el("h2", {}, est.nombre), el("p", { class: "codigo" }, `Código ${est.codigo}`)), acciones),
    resumen
  );
  if (editando) {
    detalle.append(el("p", { class: "ayuda" }, "Notas de 0,0 a 5,0 con hasta dos decimales. Deja vacío un corte que aún no tenga nota."));
  }
  detalle.append(el("div", { class: "tabla-contenedor" }, tabla));
}

function refrescar() {
  dibujarEncabezado();
  dibujarLista();
  dibujarDetalle();
}

function entrarEdicion() {
  editando = true;
  ocultarAviso();
  dibujarDetalle();
  document.querySelector("#detalle input")?.focus();
}

function seleccionar(codigo) {
  seleccionado = codigo;
  editando = false;
  history.replaceState(null, "", `#${encodeURIComponent(codigo)}`);
  ocultarAviso();
  dibujarLista();
  dibujarDetalle();
}

// --- Registrar notas --------------------------------------------------------
async function guardarNotas() {
  const est = datos.estudiantes.find((e) => e.codigo === seleccionado);
  const entradas = [...document.querySelectorAll("#detalle input")];

  if (entradas.some((i) => i.validity.badInput)) {
    avisar("Hay una nota con un formato no válido. Usa números como 3,5 o 4,25.", "error");
    return;
  }
  const asignaturas = est.asignaturas.map((a, i) => ({
    nombre: a.nombre,
    cortes: [0, 1, 2].map((j) => {
      const texto = entradas.find((x) => x.dataset.asig === String(i) && x.dataset.corte === String(j)).value.trim();
      return texto === "" ? null : Number(texto);
    }),
  }));

  try {
    datos = await enviar("PUT", `/api/estudiantes/${encodeURIComponent(est.codigo)}/notas`, { asignaturas });
    editando = false;
    refrescar();
    avisar(`Notas de ${est.nombre} guardadas.`);
  } catch (error) {
    avisar(error.message, "error");
  }
}

// --- Agregar estudiante -----------------------------------------------------
const dialogo = document.getElementById("dialogo-nuevo");
const formulario = document.getElementById("form-nuevo");
const errorDialogo = document.getElementById("error-dialogo");

document.getElementById("btn-nuevo").addEventListener("click", () => {
  formulario.reset();
  errorDialogo.textContent = "";
  dialogo.showModal();
  document.getElementById("campo-nombre").focus();
});

document.getElementById("btn-cancelar-nuevo").addEventListener("click", () => dialogo.close());

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  errorDialogo.textContent = "";
  const nombre = document.getElementById("campo-nombre").value;
  const codigo = document.getElementById("campo-codigo").value.trim();
  try {
    datos = await enviar("POST", "/api/estudiantes", { nombre, codigo: codigo || null });
  } catch (error) {
    errorDialogo.textContent = error.message;
    return;
  }
  dialogo.close();
  seleccionar(datos.codigo);
  refrescar();
  entrarEdicion();
  avisar(`Estudiante creado con el código ${datos.codigo}. Registra sus notas y guarda.`);
  document.querySelector(`.estudiante[data-codigo="${CSS.escape(datos.codigo)}"]`)?.scrollIntoView({ block: "nearest" });
});

// --- Inicio -----------------------------------------------------------------
function mostrarError(mensaje) {
  document.getElementById("subtitulo").textContent = "No fue posible cargar los datos";
  document.getElementById("detalle").replaceChildren(
    el("p", { class: "mensaje error" }, `${mensaje} Revisa el archivo estudiantes.json y recarga la página.`)
  );
}

async function iniciar() {
  try {
    const respuesta = await fetch("/api/estudiantes", { cache: "no-store" });
    const cuerpo = await respuesta.json();
    if (!respuesta.ok) throw new Error(cuerpo.error || "Error del servidor.");
    datos = cuerpo;
  } catch (error) {
    mostrarError(error.message);
    return;
  }

  const deHash = decodeURIComponent(location.hash.slice(1));
  seleccionar(datos.estudiantes.some((e) => e.codigo === deHash) ? deHash : datos.estudiantes[0].codigo);
  dibujarEncabezado();
}

iniciar();
