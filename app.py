"""Aplicación web de gestión de calificaciones (solo biblioteca estándar).

Uso:  python app.py   ->  http://localhost:8000

API:
  GET  /api/estudiantes               -> estudiantes y grupo, ya calculados
  POST /api/estudiantes               -> {"nombre": "...", "codigo": "..."(opcional)}
  PUT  /api/estudiantes/<codigo>/notas -> {"asignaturas": [{"nombre": "...", "cortes": [n1, n2, n3]}]}
"""

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import calculos

CARPETA_ESTATICA = Path(__file__).resolve().parent / "static"
PUERTO = 8000
LIMITE_CUERPO = 64 * 1024
RUTA_NOTAS = re.compile(r"^/api/estudiantes/([^/]+)/notas$")


class Manejador(BaseHTTPRequestHandler):
    def _responder(self, estado, contenido, tipo, sin_cache=False):
        self.send_response(estado)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(contenido)))
        if sin_cache:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(contenido)

    def _json(self, estado, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self._responder(estado, cuerpo, "application/json; charset=utf-8", sin_cache=True)

    def _leer_json(self):
        # Exigir application/json obliga al navegador a hacer una verificación previa (CORS),
        # lo que impide que otra página web escriba en esta app desde el navegador del usuario.
        tipo = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if tipo != "application/json":
            raise ValueError("La petición debe enviarse como application/json.")
        try:
            largo = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            largo = 0
        if not 0 < largo <= LIMITE_CUERPO:
            raise ValueError("El cuerpo de la petición está vacío o es demasiado grande.")
        try:
            cuerpo = json.loads(self.rfile.read(largo).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("El cuerpo no es un JSON válido.")
        if not isinstance(cuerpo, dict):
            raise ValueError("El cuerpo debe ser un objeto JSON.")
        return cuerpo

    def _escribir(self, accion, estado_ok):
        """Ejecuta una operación de escritura y responde con los datos recalculados."""
        try:
            codigo = accion(self._leer_json())
            self._json(estado_ok, {**calculos.calcular_todo(), "codigo": codigo})
        except calculos.NoEncontrado as error:
            self._json(404, {"error": str(error)})
        except ValueError as error:
            self._json(400, {"error": str(error)})

    # -- GET: API de lectura y archivos estáticos ---------------------------
    def do_GET(self):
        ruta = urlparse(self.path).path

        if ruta == "/api/estudiantes":
            # Se lee estudiantes.json en cada petición: si se edita, se refleja al recargar.
            try:
                self._json(200, calculos.calcular_todo())
            except ValueError as error:
                self._json(500, {"error": str(error)})
            return

        relativa = "index.html" if ruta == "/" else ruta.lstrip("/")
        archivo = (CARPETA_ESTATICA / relativa).resolve()
        if CARPETA_ESTATICA not in archivo.parents or not archivo.is_file():
            self._json(404, {"error": "Recurso no encontrado"})
            return

        tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo == "application/javascript":
            tipo += "; charset=utf-8"
        self._responder(200, archivo.read_bytes(), tipo)

    # -- POST: agregar estudiante -------------------------------------------
    def do_POST(self):
        if urlparse(self.path).path != "/api/estudiantes":
            self._json(404, {"error": "Recurso no encontrado"})
            return
        self._escribir(
            lambda c: calculos.agregar_estudiante(c.get("nombre"), c.get("codigo")), 201
        )

    # -- PUT: registrar o corregir notas ------------------------------------
    def do_PUT(self):
        coincide = RUTA_NOTAS.match(urlparse(self.path).path)
        if not coincide:
            self._json(404, {"error": "Recurso no encontrado"})
            return
        codigo = unquote(coincide.group(1))

        def accion(cuerpo):
            calculos.registrar_notas(codigo, cuerpo.get("asignaturas"))
            return codigo

        self._escribir(accion, 200)

    def log_message(self, formato, *args):
        print(f"{self.address_string()} - {formato % args}")


if __name__ == "__main__":
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    print(f"Aplicación disponible en http://localhost:{PUERTO}  (Ctrl+C para detener)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
