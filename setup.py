"""setup.py — cx_Freeze 打包配置。

构建 MSI:
    python setup.py bdist_msi

产物:  dist/ScrumBan-<version>-win64.msi
"""

import sys
from pathlib import Path

from cx_Freeze import Executable, setup

BASE = Path(__file__).parent

build_exe_options = {
    "packages": ["customtkinter", "zeroconf", "PIL"],
    "excludes": [
        "tkinter.test", "unittest", "pydoc_data",
        "setuptools", "pip", "wheel",
    ],
    "include_files": [
        (str(BASE / "assets" / "icon.ico"), "assets/icon.ico"),
    ],
    "include_msvcr": True,
}

bdist_msi_options = {
    # 固定 UpgradeCode:同 code 的 MSI 可互相升级/被"程序与功能"卸载
    "upgrade_code": "{002B7758-1FE4-4618-A72D-AC556D2F4FA8}",
    "add_to_path": False,
}

executables = [
    Executable(
        script=str(BASE / "run.py"),
        base="Win32GUI",
        target_name="ScrumBan.exe",
        icon=str(BASE / "assets" / "icon.ico"),
        shortcut_name="ScrumBan 敏捷看板",
        shortcut_dir="DesktopFolder",
    ),
]

setup(
    name="ScrumBan",
    version="1.4.0",
    description="商业级敏捷项目管理看板 (P2P 局域网协作版)",
    author="ScrumBan Team",
    executables=executables,
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
)
