import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlette.routing import Route
from mcp_server import mcp

app = mcp.streamable_http_app()

# Vercel puede entregar la ruta como /mcp, /api/index, /api o /:
# se registra el mismo endpoint MCP en todas para que cualquiera funcione.
_mcp_route = next(r for r in app.routes if getattr(r, "path", None) == "/mcp")
for _ruta in ("/", "/api", "/api/index"):
    app.router.routes.append(Route(_ruta, endpoint=_mcp_route.endpoint))