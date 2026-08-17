# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [('design/Icon.ico', 'design')] + collect_data_files('customtkinter')
hiddenimports = [
    'customtkinter',
    'pygrabber',
    'pygrabber.dshow_graph',
    'comtypes',
    'screeninfo',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'cv2',
    'cv2.aruco',
    'av',
    'serial',
    'serial.tools.list_ports',
] + collect_submodules('customtkinter')

a = Analysis(
    ['python/main.py'],
    pathex=['python', '.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='MoCapSTR',
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
    icon=['design/Icon.ico'],
)
