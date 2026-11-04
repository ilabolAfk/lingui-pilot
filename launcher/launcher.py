import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "LinguaPilot"
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

# Location of the bundled backend executable (set by PyInstaller build).
BACKEND_EXE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(BACKEND_EXE, "backend", "lingua-pilot-server.exe")
if not os.path.exists(BACKEND):
    BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lingua-pilot-server.exe")

API = f"http://{HOST}:{PORT}"


def ollama_bin():
    cand = [shutil.which("ollama"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
            r"C:\Program Files\Ollama\ollama.exe"]
    for c in cand:
        if c and os.path.exists(c):
            return c
    return None


def is_ollama_running():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=2)
        return True
    except Exception:
        return False


def wait_ollama(timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        if is_ollama_running():
            return True
        time.sleep(1)
    return False


def download_ollama_installer(dest):
    url = "https://ollama.com/download/OllamaSetup.exe"
    urllib.request.urlretrieve(url, dest)
    return dest


class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("520x520")
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap(os.path.join(BACKEND_EXE, "icon.ico"))
        except Exception:
            pass

        self.model_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Проверка окружения...")
        self.model_buttons = {}

        self._build_ui()
        self.root.after(300, self._bootstrap)

    def _build_ui(self):
        pad = {"padx": 16, "pady": 6}
        title = ttk.Label(self.root, text="LinguaPilot", font=("Segoe UI", 20, "bold"))
        title.pack(**pad)
        sub = ttk.Label(self.root, text="Обучайтесь языкам с локальным ИИ")
        sub.pack(padx=16)

        self.ollama_frame = ttk.LabelFrame(self.root, text=" Локальная модель (Ollama) ")
        self.ollama_frame.pack(fill="x", padx=16, pady=10)

        self.model_list = ttk.Frame(self.ollama_frame)
        self.model_list.pack(fill="x", padx=8, pady=6)

        self.ollama_status = ttk.Label(self.ollama_frame, text="", foreground="#666")
        self.ollama_status.pack(padx=8, pady=(0, 8))

        self.action_frame = ttk.Frame(self.root)
        self.action_frame.pack(fill="x", padx=16, pady=6)
        ttk.Button(self.action_frame, text="Скачать модель", command=self.download_selected).pack(side="left", padx=4)
        ttk.Button(self.action_frame, text="Открыть приложение", command=self.open_app).pack(side="left", padx=4)

        status_bar = ttk.Label(self.root, textvariable=self.status_var, anchor="w",
                               foreground="#333", font=("Segoe UI", 9))
        status_bar.pack(fill="x", side="bottom", padx=12, pady=8)

    def _bootstrap(self):
        self.set_status("Проверяю Ollama...")
        threading.Thread(target=self._ensure_ollama, daemon=True).start()

    def set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def _ensure_ollama(self):
        if not is_ollama_running():
            if ollama_bin():
                self.set_status("Запускаю Ollama...")
                subprocess.Popen([ollama_bin(), "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
                if wait_ollama():
                    pass
                else:
                    self.set_status("Ollama запущена, но API ещё отвечает...")
            else:
                self.set_status("Устанавливаю Ollama...")
                try:
                    dest = os.path.join(os.environ.get("TEMP", "."), "OllamaSetup.exe")
                    download_ollama_installer(dest)
                    subprocess.run([dest, "/VERYSILENT"], check=False)
                    if wait_ollama(60):
                        self.set_status("Ollama установлена и запущена")
                    else:
                        self.set_status("Ollama установлена, запустите её вручную")
                except Exception as e:
                    self.set_status(f"Не удалось установить Ollama: {e}")
        self.root.after(0, self._load_models)

    def _load_models(self):
        self.set_status("Загружаю список моделей...")
        try:
            data = self._api_get("/api/models")
            catalog = data.get("catalog", [])
            installed = set(data.get("installed", []))
            for child in self.model_list.winfo_children():
                child.destroy()
            self.model_var.set("")
            self.model_buttons.clear()
            for m in catalog:
                is_inst = m["model"] in installed
                rb = ttk.Radiobutton(self.model_list, text=f"{m['label']}  ({m['size']})",
                                     value=m["model"], variable=self.model_var)
                rb.pack(anchor="w", pady=2)
                tag = " ✓ установлена" if is_inst else " — не загружена"
                ttk.Label(self.model_list, text=tag,
                          foreground="#2e7d32" if is_inst else "#8a8a8a").pack(anchor="w", padx=20)
                self.model_buttons[m["model"]] = is_inst
            if catalog:
                self.model_var.set(next((m["model"] for m in catalog), ""))
            self.set_status("Модели загружены. Выберите нейросеть.")
        except Exception as e:
            self.set_status(f"Ошибка получения моделей: {e}")

    def download_selected(self):
        model = self.model_var.get()
        if not model:
            messagebox.showwarning("LinguaPilot", "Выберите модель для скачивания.")
            return
        if self.model_buttons.get(model):
            messagebox.showinfo("LinguaPilot", "Эта модель уже установлена.")
            return
        self.set_status(f"Скачиваю {model}... это может занять время.")
        threading.Thread(target=self._do_download, args=(model,), daemon=True).start()

    def _do_download(self, model):
        try:
            data = self._api_post("/api/models/pull", {"model": model})
            self.root.after(0, lambda: messagebox.showinfo("LinguaPilot", f"Модель {model} установлена."))
            self.root.after(0, self._load_models)
        except Exception as e:
            self.set_status(f"Ошибка скачивания: {e}")

    def _api_get(self, path):
        with urllib.request.urlopen(API + path, timeout=10) as r:
            import json
            return json.loads(r.read().decode())

    def _api_post(self, path, payload):
        import json
        data = json.dumps(payload).encode()
        req = urllib.request.Request(API + path, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    def open_app(self):
        if not is_server_running():
            self.set_status("Запускаю сервер...")
            threading.Thread(target=start_server, daemon=True).start()
            time.sleep(1.5)
        webbrowser.open(URL)


def is_server_running():
    try:
        urllib.request.urlopen(URL, timeout=2)
        return True
    except Exception:
        return False


def start_server():
    if os.path.exists(BACKEND):
        # deterministic port
        env = dict(os.environ)
        env.setdefault("LINGUA_PORT", str(PORT))
        subprocess.Popen([BACKEND], env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app",
                          "--host", HOST, "--port", str(PORT)],
                         cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         creationflags=subprocess.CREATE_NO_WINDOW)


def main():
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()