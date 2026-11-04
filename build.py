import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(ROOT, "icon.ico")
DIST = os.path.join(ROOT, "dist")

def run(cmd):
    print(">>", " ".join(cmd))
    subprocess.check_call(cmd)

def build_backend():
    print("\n=== Build backend server ===")
    entry = os.path.join(ROOT, "backend", "server_app.py")
    # PyInstaller entry that imports the app
    with open(entry, "w") as f:
        f.write("import sys, os\n"
                "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
                "from backend.main import app\n")
    spec = os.path.join(ROOT, "backend-server.spec")
    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--console",
        "--name", "lingua-pilot-server",
        "--icon", ICON,
        "--paths", ROOT,
        "--add-data", os.path.join(ROOT, "static") + os.pathsep + "static",
        entry,
    ])

def build_launcher():
    print("\n=== Build launcher GUI ===")
    launcher = os.path.join(ROOT, "launcher", "launcher.py")
    # Return the path to our own server exe no matter where the launcher is extracted
    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", "LinguaPilot",
        "--icon", ICON,
        "--paths", ROOT,
        "--add-binary", os.path.join(DIST, "lingua-pilot-server.exe") + os.pathsep + "backend",
        "--add-data", ICON + os.pathsep + ".",
        launcher,
    ])

def main():
    build_backend()
    build_launcher()
    print("\n=== Done ===")
    print("Server exe:", os.path.join(DIST, "lingua-pilot-server.exe"))
    print("Launcher exe:", os.path.join(DIST, "LinguaPilot.exe"))

if __name__ == "__main__":
    main()