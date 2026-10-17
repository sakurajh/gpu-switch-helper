# -*- mode: python ; coding: utf-8 -*-
# 打包配置：全部使用与本文件同级的相对路径，换机器 / 发给别人后重新打包同样可用。
# 重新打包（在本目录下执行）：  build.bat   或   pyinstaller --noconfirm GPU切换助手.spec

import os

# SPECPATH 由 PyInstaller 注入，指向本 spec 所在目录；用它拼出图标路径，避免任何写死的盘符。
ICON = os.path.join(SPECPATH, 'icon.ico')

a = Analysis(
    [os.path.join(SPECPATH, 'gpu_switch_app.py')],
    pathex=[],
    binaries=[],
    datas=[(ICON, '.')],
    hiddenimports=[],
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
    name='GPU切换助手',
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
    icon=ICON,
)
