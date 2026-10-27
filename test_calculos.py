"""Pruebas: python -m unittest -v

Las pruebas de escritura usan un archivo temporal con datos propios (un conjunto
fijo de 3 estudiantes), así que no dependen de ni modifican el estudiantes.json real.
"""

import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import calculos

ORIGINAL = Path(__file__).resolve().parent / "estudiantes.json"


def _estudiante_base(codigo, nombre, notas):
    return {
        "codigo": codigo,
        "nombre": nombre,
        "asignaturas": [{"nombre": n, "cortes": notas} for n in calculos.ASIGNATURAS],
    }


BASE = [
    _estudiante_base("2026001", "Ana Uno", [4.0, 4.0, 4.0]),
    _estudiante_base("2026002", "Beto Dos", [3.0, 3.0, 3.0]),
    _estudiante_base("2026003", "Carla Tres", [2.0, 2.0, 2.0]),
]


class PruebasClasificacion(unittest.TestCase):
    def test_limites(self):
        self.assertEqual(calculos.clasificar(Fraction(0)), "Perdió")
        self.assertEqual(calculos.clasificar(Fraction(3)), "Ganó")
        self.assertEqual(calculos.clasificar(Fraction(4)), "Sobresaliente")
        self.assertEqual(calculos.clasificar(Fraction(5)), "Sobresaliente")

    def test_clasifica_sin_redondear(self):
        # (2,99 + 3,0 + 3,0) / 3 = 2,9966... se muestra 3,00 pero sigue perdiendo.
        r, _ = calculos._procesar_asignatura({"nombre": "X", "cortes": [2.99, 3.0, 3.0]})
        self.assertEqual(r["definitiva"], 3.0)
        self.assertEqual(r["clasificacion"], "Perdió")
        # (3,99 + 4,0 + 4,0) / 3 = 3,9966... se muestra 4,00 pero solo "Ganó".
        r, _ = calculos._procesar_asignatura({"nombre": "X", "cortes": [3.99, 4.0, 4.0]})
        self.assertEqual(r["definitiva"], 4.0)
        self.assertEqual(r["clasificacion"], "Ganó")

    def test_limite_exacto_sin_error_de_flotantes(self):
        r, _ = calculos._procesar_asignatura({"nombre": "X", "cortes": [2.9, 3.0, 3.1]})
        self.assertEqual(r["clasificacion"], "Ganó")

    def test_corte_pendiente_no_tiene_definitiva(self):
        r, d = calculos._procesar_asignatura({"nombre": "X", "cortes": [4.0, None, 5.0]})
        self.assertIsNone(r["definitiva"])
        self.assertIsNone(d)
        self.assertEqual(r["clasificacion"], "Pendiente")


class PruebasDatos(unittest.TestCase):
    def setUp(self):
        self.todo = calculos.calcular_todo(calculos.cargar_datos(ORIGINAL))

    def test_estructura_del_reto(self):
        self.assertGreaterEqual(len(self.todo["estudiantes"]), 10)
        for est in self.todo["estudiantes"]:
            self.assertEqual(len(est["asignaturas"]), 5)
            for asig in est["asignaturas"]:
                self.assertEqual(len(asig["cortes"]), 3)
                self.assertTrue(all(c is None or 0 <= c <= 5 for c in asig["cortes"]))

    def test_resumen_coherente(self):
        for est in self.todo["estudiantes"]:
            r = est["resumen"]
            self.assertEqual(r["aprobadas"] + r["reprobadas"] + r["pendientes"], 5)
            self.assertLessEqual(r["sobresalientes"], r["aprobadas"])

    def test_promedio_del_grupo(self):
        promedios = [e["promedio_general"] for e in self.todo["estudiantes"] if e["promedio_general"] is not None]
        self.assertAlmostEqual(self.todo["grupo"]["promedio_general"], sum(promedios) / len(promedios), places=1)

    def test_buscar_codigo_inexistente(self):
        with self.assertRaises(calculos.NoEncontrado):
            calculos.buscar_estudiante("0000000", self.todo)


class PruebasEscritura(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta = Path(self.carpeta.name) / "estudiantes.json"
        calculos.guardar_datos(BASE, self.ruta)
        self.cantidad_inicial = len(calculos.cargar_datos(self.ruta))

    def tearDown(self):
        self.carpeta.cleanup()

    def _estudiante(self, codigo):
        return calculos.buscar_estudiante(codigo, calculos.calcular_todo(calculos.cargar_datos(self.ruta)))

    def test_agregar_estudiante_con_codigo_automatico(self):
        codigo = calculos.agregar_estudiante("  Pedro   Pérez  ", ruta=self.ruta)
        self.assertEqual(codigo, "2026004")
        est = self._estudiante(codigo)
        self.assertEqual(est["nombre"], "Pedro Pérez")
        self.assertEqual(len(est["asignaturas"]), 5)
        self.assertEqual(est["resumen"]["pendientes"], 5)
        self.assertIsNone(est["promedio_general"])
        self.assertEqual(len(calculos.cargar_datos(self.ruta)), self.cantidad_inicial + 1)

    def test_agregar_con_codigo_propio_y_duplicado(self):
        self.assertEqual(calculos.agregar_estudiante("Ana Ruiz", "ABC-1", ruta=self.ruta), "ABC-1")
        with self.assertRaises(ValueError):
            calculos.agregar_estudiante("Otra Persona", "ABC-1", ruta=self.ruta)
        with self.assertRaises(ValueError):
            calculos.agregar_estudiante("Otra Persona", "a b", ruta=self.ruta)

    def test_nombre_invalido(self):
        for nombre in ("", "   ", "A", None, "x" * 81):
            with self.assertRaises(ValueError):
                calculos.agregar_estudiante(nombre, ruta=self.ruta)

    def test_notas_parciales_y_completas(self):
        codigo = calculos.agregar_estudiante("Pedro Pérez", ruta=self.ruta)
        calculos.registrar_notas(codigo, [{"nombre": "Estadística", "cortes": [4.0, 4.5, None]}], ruta=self.ruta)
        est = self._estudiante(codigo)
        self.assertEqual(est["asignaturas"][4]["clasificacion"], "Pendiente")
        self.assertIsNone(est["promedio_general"])

        calculos.registrar_notas(codigo, [{"nombre": "Estadística", "cortes": [4.0, 4.5, 3.5]}], ruta=self.ruta)
        est = self._estudiante(codigo)
        self.assertEqual(est["asignaturas"][4]["definitiva"], 4.0)
        self.assertEqual(est["asignaturas"][4]["clasificacion"], "Sobresaliente")
        self.assertEqual(est["promedio_general"], 4.0)
        self.assertEqual(est["asignaturas_calificadas"], 1)

    def test_corregir_nota_existente(self):
        calculos.registrar_notas("2026003", [{"nombre": "Programación II", "cortes": [5.0, 5.0, 5.0]}], ruta=self.ruta)
        asig = self._estudiante("2026003")["asignaturas"][0]
        self.assertEqual(asig["clasificacion"], "Sobresaliente")

    def test_rechaza_notas_invalidas_y_no_modifica_el_archivo(self):
        antes = self.ruta.read_text(encoding="utf-8")
        malas = [5.1, -0.1, 3.456, "4", True, float("nan"), [3]]
        for mala in malas:
            with self.assertRaises(ValueError, msg=repr(mala)):
                calculos.registrar_notas("2026001", [{"nombre": "Estadística", "cortes": [mala, 3.0, 3.0]}], ruta=self.ruta)
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)

    def test_todo_o_nada(self):
        antes = self.ruta.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            calculos.registrar_notas(
                "2026001",
                [{"nombre": "Estadística", "cortes": [1.0, 1.0, 1.0]}, {"nombre": "Inexistente", "cortes": [1.0, 1.0, 1.0]}],
                ruta=self.ruta,
            )
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)

    def test_codigo_inexistente_y_cortes_incorrectos(self):
        with self.assertRaises(calculos.NoEncontrado):
            calculos.registrar_notas("0000", [{"nombre": "Estadística", "cortes": [1, 1, 1]}], ruta=self.ruta)
        with self.assertRaises(ValueError):
            calculos.registrar_notas("2026001", [{"nombre": "Estadística", "cortes": [1, 1]}], ruta=self.ruta)
        with self.assertRaises(ValueError):
            calculos.registrar_notas("2026001", [], ruta=self.ruta)

    def test_guardar_conserva_formato(self):
        antes = self.ruta.read_text(encoding="utf-8")
        calculos.guardar_datos(calculos.cargar_datos(self.ruta), self.ruta)
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)


if __name__ == "__main__":
    unittest.main()
