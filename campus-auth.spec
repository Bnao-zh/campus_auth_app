# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['campus_auth_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('network.jar', '.'), ('tray.png', '.')],
    hiddenimports=['pystray._appindicator', 'pystray._util.gtk'],
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
    name='campus-auth',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['ec.ico'],
)
