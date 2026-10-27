"""Servidor MCP independiente para consultar las calificaciones académicas.

Lee el MISMO estudiantes.json que la aplicación web y reutiliza calculos.py,
por lo que ambas interfaces siempre entregan los mismos resultados.

Transporte: stdio (el que usan Claude Desktop, Claude Code y la mayoría de clientes MCP).
"""

from mcp.server.fastmcp import FastMCP

import calculos

mcp = FastMCP("calificaciones-academicas", stateless_http=True, host="0.0.0.0")

@mcp.tool()
def listar_estudiantes() -> list[dict]:
    """Lista todos los estudiantes registrados (código y nombre completo)."""
    todo = calculos.calcular_todo()
    return [{"codigo": e["codigo"], "nombre": e["nombre"]} for e in todo["estudiantes"]]


@mcp.tool()
def consultar_estudiante(codigo: str) -> dict:
    """Devuelve los datos académicos completos de un estudiante: notas por corte,
    definitivas, clasificación, promedio general y resumen de aprobadas,
    reprobadas y sobresalientes. Requiere el código del estudiante (ej. '2026001')."""
    return calculos.buscar_estudiante(codigo)


@mcp.tool()
def consultar_notas(codigo: str) -> dict:
    """Devuelve las calificaciones de las cinco asignaturas de un estudiante
    (tres cortes, nota definitiva y clasificación de cada una)."""
    est = calculos.buscar_estudiante(codigo)
    return {"codigo": est["codigo"], "nombre": est["nombre"], "asignaturas": est["asignaturas"]}


@mcp.tool()
def consultar_promedio(codigo: str) -> dict:
    """Devuelve el promedio general de un estudiante (promedio de sus definitivas)
    junto con el promedio general del grupo para comparar. Es null si el estudiante
    aún no tiene ninguna asignatura con sus tres cortes calificados; 'asignaturas_calificadas'
    indica con cuántas asignaturas se calculó."""
    todo = calculos.calcular_todo()
    est = calculos.buscar_estudiante(codigo, todo)
    return {
        "codigo": est["codigo"],
        "nombre": est["nombre"],
        "promedio_general": est["promedio_general"],
        "asignaturas_calificadas": est["asignaturas_calificadas"],
        "promedio_general_grupo": todo["grupo"]["promedio_general"],
    }


@mcp.tool()
def consultar_reprobados() -> list[dict]:
    """Devuelve los estudiantes que tienen al menos una asignatura perdida
    (definitiva menor que 3,0), indicando cuáles asignaturas perdieron."""
    resultado = []
    for est in calculos.calcular_todo()["estudiantes"]:
        perdidas = [
            {"asignatura": a["nombre"], "definitiva": a["definitiva"]}
            for a in est["asignaturas"]
            if a["clasificacion"] == calculos.PERDIO
        ]
        if perdidas:
            resultado.append(
                {
                    "codigo": est["codigo"],
                    "nombre": est["nombre"],
                    "cantidad_perdidas": len(perdidas),
                    "asignaturas_perdidas": perdidas,
                }
            )
    return resultado


if __name__ == "__main__":
    import sys
    # sin argumentos: stdio (Claude Desktop/Code); con "http": versión remota
    mcp.run(transport="streamable-http" if "http" in sys.argv else "stdio")
    
    mcp.run()
