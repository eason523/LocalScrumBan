# ScrumBan — Commercial-Grade Agile Project Management Kanban

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A Python + CustomTkinter desktop kanban board recreating TODO.html, with **LAN P2P multi-machine collaboration** and **bilingual (Chinese/English) UI**.

## ✨ Features

- 🌑 Dark theme (one-to-one mapping with the original HTML CSS variables)
- 📁 Multi-project workspaces: create / switch / delete (with confirmation dialog)
- 📊 Statistics dashboard: overdue / urgent & high-priority / due-today counters + per-project progress bar
- 📋 Three-column kanban: To Do → In Progress → Archived
- 🖱️ Task cards: drag & drop across columns, double-click title for inline editing, delete
- 🔀 Smart sorting: due date ascending → priority descending
- 🌐 **P2P LAN collaboration**: automatic mDNS discovery of peers on the same network, real-time broadcast sync of create/update/delete (Lamport-clock eventual consistency)
- 🌍 **Bilingual (CN/EN)**: one-click switch in the sidebar, instant refresh of the entire UI
- 💾 Local JSON persistence: `~/.kanban_app/store.json`

## 📦 Project Structure

```
ScrumBan/
├── kanban_app/            # main package
│   ├── __init__.py        # version & constants
│   ├── __main__.py        # python -m kanban_app entry point
│   ├── i18n.py            # CN/EN translation tables + t()/set_lang()
│   ├── config.py          # palette / fonts / kanban column definitions
│   ├── models.py          # Project/Task dataclasses + Store
│   ├── peer.py            # zeroconf mDNS + HTTP sync (P2P layer)
│   ├── app.py             # main window / layout / drag & drop / status bar
│   └── widgets/
│       ├── task_card.py       # task card
│       ├── kanban_column.py   # kanban column
│       ├── sidebar.py         # project sidebar + language switch
│       ├── dashboard.py       # statistics dashboard
│       └── task_form.py       # task creation form
├── run.py                 # dev launch: python run.py
├── make_icon.py           # generates assets/icon.ico
├── setup.py               # cx_Freeze MSI packaging config
├── assets/icon.ico        # app icon
├── requirements.txt
└── TODO.html              # original prototype
```

## 🚀 Running (Development)

```bash
pip install -r requirements.txt
python run.py              # or: python -m kanban_app
```

## 📦 Building the MSI Installer

```bash
pip install cx_Freeze pillow
python make_icon.py        # generate the icon (skippable if already committed)
python setup.py bdist_msi  # output: dist/ScrumBan-<ver>-win64.msi
```

After installation:
- A "ScrumBan Agile Kanban" shortcut appears on the desktop
- Uninstall / upgrade via "Settings → Apps" (fixed UpgradeCode)
- Fully frozen build — no Python runtime required

## 🌐 P2P Collaboration Notes

Any machine on the same LAN joins the network automatically on startup (`_kanban._tcp.local.`):
- The bottom status bar shows the number of online peers and this node's address
- Any create/update/delete syncs to other peers within ~1s
- A newly started node bootstraps the full state from an online peer automatically
- If Windows Firewall blocks mDNS, allow UDP 5353 as administrator:

```powershell
netsh advfirewall firewall add rule name="mDNS" dir=in action=allow protocol=udp localport=5353
```

## 🧪 Testing

```bash
# Two-node sync smoke test
python - <<'EOF'
import sys; sys.path.insert(0, '.')
# See the session test script, or manually run python run.py in two terminals
EOF
```

## 📄 License

This project is licensed under the [MIT License](LICENSE).
