"""S1 fallback: run under LibreOffice's python with -I, then add only the (integrity-checked) LibreOffice program
folder to sys.path before importing uno. argv: <bridge script> <its args...>"""
import os, runpy, sys
PROGRAM = os.path.join(os.environ["LOCALAPPDATA"], "URI", "engines", "libreoffice-26.8.1", "program")
sys.path[:0] = [PROGRAM]
target = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(target, run_name="__main__")
