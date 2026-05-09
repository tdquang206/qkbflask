# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates'), ('static', 'static'), ('routes', 'routes'), ('db.json', 'db.json'), ('db_mua_thuoc.json', 'db_mua_thuoc.json'), ('db_services.json', 'db_services.json'), ('user_settings.json', 'user_settings.json'), ('exam_template.json', 'exam_template.json'), ('money_log.json', 'money_log.json'), ('app_icon.ico', 'app_icon.ico')],
    hiddenimports=['pystray', 'PIL', 'waitress'],
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
    [],
    exclude_binaries=True,
    name='QKBFlask',
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
    icon='app_icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='QKBFlask',
)
