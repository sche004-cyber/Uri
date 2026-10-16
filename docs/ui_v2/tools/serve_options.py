"""Local, read-only design preview. Never imports or starts URI services."""
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

if __name__ == '__main__':
    directory=Path(__file__).resolve().parents[1]
    ThreadingHTTPServer(('127.0.0.1',8137),partial(SimpleHTTPRequestHandler,directory=str(directory))).serve_forever()
