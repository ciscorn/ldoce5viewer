# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ['ldoce5viewer.py'],
    pathex=[],
    binaries=[],
    datas=[('ldoce5viewer/static', 'static')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ldoce5viewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ldoce5viewer',
)
app = BUNDLE(
    coll,
    name='LDOCE5 Viewer.app',
    icon='./ldoce5viewer/qtgui/resources/ldoce5viewer.icns',
    bundle_identifier=None,
)
