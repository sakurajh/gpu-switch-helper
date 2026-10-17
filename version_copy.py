# -*- coding: utf-8 -*-
"""打包收尾用：把 dist 里的成品复制成  GPU切换助手.exe  和  GPU切换助手_vX.Y.exe。
版本号从源码里读，避免脚本和源码两处手写版本对不上。"""
import io
import os
import re
import shutil
import sys

here = os.path.dirname(os.path.abspath(__file__))
src = io.open(os.path.join(here, "gpu_switch_app.py"), encoding="utf-8").read()
m = re.search(r'VERSION\s*=\s*"([0-9.]+)"', src)
ver = m.group(1) if m else "unknown"

built = os.path.join(here, "dist", "GPU切换助手.exe")
if not os.path.isfile(built):
    print("[FAIL] 找不到打包产物：", built)
    sys.exit(1)

main_exe = os.path.join(here, "GPU切换助手.exe")
shutil.copy2(built, main_exe)
ver_exe = os.path.join(here, "GPU切换助手_v%s.exe" % ver)
shutil.copy2(built, ver_exe)
print("[OK] 已生成：")
print("     %s   (%d 字节)" % (main_exe, os.path.getsize(main_exe)))
print("     %s" % ver_exe)
