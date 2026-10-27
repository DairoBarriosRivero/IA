"""Lógica académica compartida por la aplicación web y el servidor MCP.

Ambas interfaces importan este módulo y leen el mismo archivo
``estudiantes.json``, lo que garantiza resultados idénticos (RF07 y sección 4).

Decisión de diseño: las notas se manejan con ``Fraction`` (aritmética exacta).
Así la clasificación se hace con la definitiva SIN redondear y no hay errores de
punto flotante en los límites (por ejemplo, 3.0 exacto o 2.99, 3.0, 3.0 que se
muestra como 3,00 pero sigue siendo "Perdió").

Notas pendientes: un corte sin nota se guarda como ``null``. Una asignatura con
algún corte pendiente no tiene definitiva ni clasificación ("Pendiente").
"""

import json
import math
import os
import re
import threading
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

RUTA_JSON = Path(
    os.environ.get("ESTUDIANTES_JSON", Path(__file__).resolve().parent / "estudiantes.json")
)

NOTA_MIN = 0
NOTA_MAX = 5
NUM_CORTES = 3
NUM_ASIGNATURAS = 5
ASIGNATURAS = [
    "Programación II",
    "Matemáticas Discretas",
    "Bases de Datos",
    "Arquitectura de Computadores",
    "Estadística",
]

PERDIO = "Perdió"
GANO = "Ganó"
SOBRESALIENTE = "Sobresaliente"
PENDIENTE = "Pendiente"

_BLOQUEO = threading.Lock()  # evita que dos peticiones escriban el JSON a la vez
_RE_CODIGO = re.compile(r"^[A-Za-z0-9_-]{3,20}$")


class NoEncontrado(ValueError):
    """El estudiante solicitado no existe."""


# ----------------------------------------------------------------------------
# Validación
# ----------------------------------------------------------------------------
def _validar_nota(nota, contexto):
    """Una nota es un número de 0,0 a 5,0 con máximo dos decimales, o None (pendiente)."""
    if nota is None:
        return
    if isinstance(nota, bool) or not isinstance(nota, (int, float)) or not math.isfinite(nota):
        raise ValueError(f"{contexto}: la nota debe ser un número (o quedar vacía si aún no existe).")
    if not NOTA_MIN <= nota <= NOTA_MAX:
        raise ValueError(f"{contexto}: la nota {nota} está fuera de 0,0 a 5,0.")
    if (Fraction(str(nota)) * 100).denominator != 1:
        raise ValueError(f"{contexto}: usa máximo dos decimales (recibido {nota}).")


# ----------------------------------------------------------------------------
# Lectura y escritura del JSON
# ----------------------------------------------------------------------------
def cargar_datos(ruta=None):
    """Lee estudiantes.json, valida su estructura y devuelve la lista de estudiantes."""
    ruta = Path(ruta) if ruta else RUTA_JSON
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except FileNotFoundError:
        raise ValueError(f"No se encontró el archivo de datos: {ruta}")
    except json.JSONDecodeError as error:
        raise ValueError(f"El archivo {ruta.name} no es un JSON válido: {error}")

    estudiantes = datos.get("estudiantes") if isinstance(datos, dict) else None
    if not isinstance(estudiantes, list) or not estudiantes:
        raise ValueError('El JSON debe tener la clave "estudiantes" con una lista no vacía.')

    codigos = set()
    for est in estudiantes:
        codigo = est.get("codigo")
        if not codigo or not est.get("nombre"):
            raise ValueError("Todo estudiante necesita 'codigo' y 'nombre'.")
        if codigo in codigos:
            raise ValueError(f"Código de estudiante repetido: {codigo}")
        codigos.add(codigo)

        asignaturas = est.get("asignaturas", [])
        if len(asignaturas) != NUM_ASIGNATURAS:
            raise ValueError(f"El estudiante {codigo} debe tener {NUM_ASIGNATURAS} asignaturas.")
        for asig in asignaturas:
            cortes = asig.get("cortes", [])
            if len(cortes) != NUM_CORTES:
                raise ValueError(
                    f"{codigo} / {asig.get('nombre')}: se requieren {NUM_CORTES} cortes."
                )
            for nota in cortes:
                _validar_nota(nota, f"{codigo} / {asig.get('nombre')}")
    return estudiantes


def _serializar(estudiantes):
    """Genera el JSON con el mismo formato legible del archivo original."""
    bloques = []
    for est in estudiantes:
        filas = ",\n".join(
            '        {"nombre": %s, "cortes": [%s]}'
            % (json.dumps(a["nombre"], ensure_ascii=False), ", ".join(json.dumps(n) for n in a["cortes"]))
            for a in est["asignaturas"]
        )
        bloques.append(
            '    {\n      "codigo": %s,\n      "nombre": %s,\n      "asignaturas": [\n%s\n      ]\n    }'
            % (json.dumps(est["codigo"], ensure_ascii=False), json.dumps(est["nombre"], ensure_ascii=False), filas)
        )
    return '{\n  "estudiantes": [\n' + ",\n".join(bloques) + "\n  ]\n}\n"


def guardar_datos(estudiantes, ruta=None):
    """Escribe el JSON de forma atómica (archivo temporal + reemplazo), así el
    servidor MCP nunca lee un archivo a medio escribir."""
    ruta = Path(ruta) if ruta else RUTA_JSON
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(_serializar(estudiantes), encoding="utf-8")
    os.replace(temporal, ruta)


def _siguiente_codigo(existentes):
    numericos = [c for c in existentes if c.isdigit()]
    if not numericos:
        return "2026001"
    ancho = max(len(c) for c in numericos)
    return str(max(int(c) for c in numericos) + 1).zfill(ancho)


def agregar_estudiante(nombre, codigo=None, ruta=None):
    """Agrega un estudiante con sus 5 asignaturas y todos los cortes pendientes.
    Si no se indica código se genera el siguiente. Devuelve el código asignado."""
    nombre = " ".join(str(nombre or "").split())
    if not 2 <= len(nombre) <= 80:
        raise ValueError("El nombre debe tener entre 2 y 80 caracteres.")

    with _BLOQUEO:
        estudiantes = cargar_datos(ruta)
        existentes = {e["codigo"] for e in estudiantes}
        codigo = str(codigo).strip() if codigo not in (None, "") else ""
        if not codigo:
            codigo = _siguiente_codigo(existentes)
        elif not _RE_CODIGO.match(codigo):
            raise ValueError("El código debe tener de 3 a 20 caracteres (letras, números, guion o guion bajo).")
        elif codigo in existentes:
            raise ValueError(f"Ya existe un estudiante con el código {codigo}.")

        estudiantes.append(
            {
                "codigo": codigo,
                "nombre": nombre,
                "asignaturas": [{"nombre": n, "cortes": [None] * NUM_CORTES} for n in ASIGNATURAS],
            }
        )
        guardar_datos(estudiantes, ruta)
    return codigo


def registrar_notas(codigo, asignaturas, ruta=None):
    """Registra o corrige notas de un estudiante.

    ``asignaturas``: lista de {"nombre": ..., "cortes": [n1, n2, n3]}, donde cada
    nota es un número de 0,0 a 5,0 o None (pendiente). Solo se modifican las
    asignaturas enviadas. Todo se valida antes de escribir (todo o nada).
    """
    if not isinstance(asignaturas, list) or not asignaturas:
        raise ValueError("Envía la lista 'asignaturas' con las notas a registrar.")

    with _BLOQUEO:
        estudiantes = cargar_datos(ruta)
        codigo = str(codigo).strip()
        est = next((e for e in estudiantes if e["codigo"] == codigo), None)
        if est is None:
            raise NoEncontrado(f"No existe un estudiante con el código '{codigo}'.")

        por_nombre = {a["nombre"]: a for a in est["asignaturas"]}
        cambios = {}
        for item in asignaturas:
            nombre = item.get("nombre") if isinstance(item, dict) else None
            cortes = item.get("cortes") if isinstance(item, dict) else None
            if not isinstance(nombre, str) or nombre not in por_nombre:
                raise ValueError(f"La asignatura '{nombre}' no existe para este estudiante.")
            if not isinstance(cortes, list) or len(cortes) != NUM_CORTES:
                raise ValueError(f"{nombre}: se requieren exactamente {NUM_CORTES} cortes.")
            for n, nota in enumerate(cortes, start=1):
                _validar_nota(nota, f"{nombre}, corte {n}")
            cambios[nombre] = cortes

        for nombre, cortes in cambios.items():
            por_nombre[nombre]["cortes"] = cortes
        guardar_datos(estudiantes, ruta)


# ----------------------------------------------------------------------------
# Cálculos
# ----------------------------------------------------------------------------
def a_dos_decimales(valor):
    """Redondea (solo para mostrar) a dos decimales, mitad hacia arriba."""
    decimal = Decimal(valor.numerator) / Decimal(valor.denominator)
    return float(decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def clasificar(definitiva):
    """Clasifica la nota definitiva EXACTA (sin redondear)."""
    if definitiva < 3:
        return PERDIO
    if definitiva < 4:
        return GANO
    return SOBRESALIENTE


def _procesar_asignatura(asig):
    cortes = [None if n is None else float(n) for n in asig["cortes"]]
    if any(n is None for n in asig["cortes"]):
        return {"nombre": asig["nombre"], "cortes": cortes, "definitiva": None, "clasificacion": PENDIENTE}, None

    notas = [Fraction(str(n)) for n in asig["cortes"]]
    definitiva = sum(notas, Fraction(0)) / len(notas)  # promedio aritmético
    resultado = {
        "nombre": asig["nombre"],
        "cortes": cortes,
        "definitiva": a_dos_decimales(definitiva),
        "clasificacion": clasificar(definitiva),
    }
    return resultado, definitiva


def _procesar_estudiante(est):
    asignaturas, definitivas = [], []
    for asig in est["asignaturas"]:
        resultado, definitiva = _procesar_asignatura(asig)
        asignaturas.append(resultado)
        if definitiva is not None:
            definitivas.append(definitiva)

    # El promedio general solo usa asignaturas con los 3 cortes; si no hay ninguna es None.
    promedio = sum(definitivas, Fraction(0)) / len(definitivas) if definitivas else None
    clases = [a["clasificacion"] for a in asignaturas]
    resultado = {
        "codigo": est["codigo"],
        "nombre": est["nombre"],
        "asignaturas": asignaturas,
        "promedio_general": None if promedio is None else a_dos_decimales(promedio),
        "asignaturas_calificadas": len(definitivas),
        "resumen": {
            # "Aprobadas" incluye las sobresalientes (definitiva >= 3,0).
            "aprobadas": clases.count(GANO) + clases.count(SOBRESALIENTE),
            "reprobadas": clases.count(PERDIO),
            "sobresalientes": clases.count(SOBRESALIENTE),
            "pendientes": clases.count(PENDIENTE),
        },
    }
    return resultado, promedio


def calcular_todo(estudiantes=None):
    """Devuelve {'estudiantes': [...], 'grupo': {...}} con todo calculado."""
    if estudiantes is None:
        estudiantes = cargar_datos()
    procesados, promedios = [], []
    for est in estudiantes:
        resultado, promedio = _procesar_estudiante(est)
        procesados.append(resultado)
        if promedio is not None:
            promedios.append(promedio)

    promedio_grupo = sum(promedios, Fraction(0)) / len(promedios) if promedios else None
    return {
        "estudiantes": procesados,
        "grupo": {
            "total_estudiantes": len(procesados),
            # Promedio de los promedios de los estudiantes que ya tienen al menos una asignatura completa.
            "promedio_general": None if promedio_grupo is None else a_dos_decimales(promedio_grupo),
            "estudiantes_con_perdidas": sum(1 for e in procesados if e["resumen"]["reprobadas"]),
        },
    }


def buscar_estudiante(codigo, resultado=None):
    """Busca un estudiante ya calculado por su código; lanza NoEncontrado si no existe."""
    resultado = resultado or calcular_todo()
    codigo = str(codigo).strip()
    for est in resultado["estudiantes"]:
        if est["codigo"] == codigo:
            return est
    raise NoEncontrado(f"No existe un estudiante con el código '{codigo}'.")
