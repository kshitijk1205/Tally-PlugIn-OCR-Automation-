# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

datas = []
for f in ['config.py', 'connect_qr.png', 'mappings.db', '.env']:
    p = Path(f)
    if p.exists():
        datas.append((str(p.resolve()), '.'))

Path('mobile_uploads').mkdir(exist_ok=True)
datas.append(('mobile_uploads', 'mobile_uploads'))

HEAVY = [
    'torch', 'torchvision', 'torchaudio',
    'tensorflow', 'keras', 'tensorboard',
    'scipy', 'scipy.special', 'scipy.spatial', 'scipy.stats', 'scipy.linalg',
    'scipy.io', 'scipy.sparse', 'scipy.optimize', 'scipy.integrate',
    'scipy.interpolate', 'scipy.signal', 'scipy.ndimage',
    'pandas', 'pandas.io', 'pandas.plotting',
    'numpy', 'numpy.random', 'numpy.linalg',
    'matplotlib', 'mpl_toolkits',
    'sklearn', 'skimage', 'cv2', 'opencv',
    'nltk', 'spacy', 'gensim',
    'transformers', 'tokenizers', 'datasets',
    'sentence_transformers',
    'PIL.ImageQt', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    'notebook', 'jupyter', 'ipykernel', 'ipython', 'jedi', 'parso',
    'plotly', 'bokeh', 'seaborn',
    'sympy', 'statsmodels',
    'networkx', 'dask',
    'flask_sqlalchemy', 'flask_login', 'flask_wtf',
    'pydantic', 'uvicorn', 'fastapi', 'starlette',
    'anyio', 'httpx', 'httpcore',
    'websockets', 'aiohttp', 'aiofiles',
    'pydub', 'soundfile', 'sounddevice',
    'moviepy', 'ffmpeg',
    'pyarrow', 'fastparquet',
    'openpyxl', 'xlrd', 'xlwt', 'odf',
    'lxml', 'beautifulsoup4', 'soupsieve',
    'sphinx', 'alabaster',
    'zmq', 'pyzmq',
    'cryptography',
    'pycparser', 'cffi',
    'altair', 'narwhals',
    'regex',  # the regex module (not re)
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL._imaging',
        'google.genai',
        'google.genai.errors',
        'sqlite3',
        'xml.etree.ElementTree',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=HEAVY,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CardioFlow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
