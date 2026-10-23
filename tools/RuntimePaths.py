"""All production paths are relative to the portable application directory."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
TOOLS=ROOT/'tools'
PACKAGES=ROOT/'runtime'/'python'/'Lib'/'site-packages'
def dependencies():
    if not PACKAGES.is_dir():raise RuntimeError('Portable runtime/python/Lib/site-packages is missing')
    if str(PACKAGES) not in sys.path:sys.path.insert(0,str(PACKAGES))
def asset(value,base=ROOT):
    path=Path(value)
    return str(path.resolve() if path.is_absolute() else (base/path).resolve())
