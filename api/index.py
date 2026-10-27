import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from mcp_server import mcp

app = mcp.streamable_http_app()