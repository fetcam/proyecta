#!/usr/bin/env python3
"""Optional Linux Mint menu shortcut. Uses the current extraction directory."""
import os
import sys
from pathlib import Path

if not sys.platform.startswith('linux'):
    raise SystemExit('Este acceso de menú es para Linux. En otros sistemas usa app.py o start.bat.')
root = Path(__file__).resolve().parent
# Desktop Entry specification: double-quoted arguments with reserved characters escaped.
def quote(arg):
    return '"' + str(arg).replace('\\','\\\\\\\\').replace('"','\\\\"').replace('`','\\\\`').replace('$','\\\\$').replace('%','%%') + '"'
applications = Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local'/'share'))/'applications'
applications.mkdir(parents=True,exist_ok=True)
entry = applications/'proyecta.desktop'
entry.write_text('[Desktop Entry]\nType=Application\nName=Proyecta\nComment=Centro de control local de proyectos\nExec='+quote(sys.executable)+' '+quote(root/'app.py')+'\nIcon='+str(root/'static'/'icon.svg')+'\nTerminal=true\nCategories=Office;ProjectManagement;\n',encoding='utf-8')
print(f'Acceso creado: {entry}\nBusca Proyecta en el menú. Mantén la carpeta de la aplicación en {root}.')
