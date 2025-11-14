import tkinter as tk
from tkinter import ttk, messagebox
import os
import fnmatch
from pathlib import Path
import sys

# === Платформа ===
IS_WINDOWS = sys.platform == "win32"

# === Импорты для Windows ===
if IS_WINDOWS:
    import winreg

# === Цвета ===
BG_COLOR = "#f9fafb"
ACCENT_COLOR = "#4f46e5"
TEXT_COLOR = "#111827"
MUTED_COLOR = "#6b7280"
WARNING_COLOR = "#dc2626"
SAFE_COLOR = "#059669"
CARD_BG = "#ffffff"

# === Паттерны мусора ===
SAFE_PATTERNS = ["*.tmp", "*.temp", "*.log", "*.bak", "*~", ".DS_Store", "Thumbs.db", "desktop.ini"]
SAFE_DIRS = ["__pycache__"]
RISKY_PATTERNS = ["*.py", "*.ipynb", "*.js", "*.ts", "*.json", "*.yaml", "*.yml", "requirements.txt", "package.json", "Dockerfile", ".env", "Makefile"]

def is_safe_garbage(name, is_dir=False):
    if is_dir:
        return name in SAFE_DIRS
    return any(fnmatch.fnmatch(name, pat) for pat in SAFE_PATTERNS)

def is_risky_garbage(name, is_dir=False):
    if is_dir:
        return False
    return any(fnmatch.fnmatch(name, pat) for pat in RISKY_PATTERNS)

def classify_item(path):
    name = os.path.basename(path)
    is_dir = os.path.isdir(path)
    if is_safe_garbage(name, is_dir):
        return "safe"
    elif is_risky_garbage(name, is_dir):
        return "risky"
    return None

def scan_home(max_items=150):
    home = str(Path.home())
    garbage = {"safe": [], "risky": []}
    count = 0
    try:
        for dirpath, dirnames, filenames in os.walk(home):
            dirnames[:] = [d for d in dirnames if not d.startswith('.') or d == '__pycache__']
            for f in filenames:
                if count >= max_items: break
                p = os.path.join(dirpath, f)
                k = classify_item(p)
                if k:
                    garbage[k].append(p)
                    count += 1
            for d in dirnames[:]:
                if count >= max_items: break
                p = os.path.join(dirpath, d)
                k = classify_item(p)
                if k:
                    garbage[k].append(p)
                    count += 1
            if count >= max_items: break
        for dirpath, dirnames, filenames in os.walk(home, topdown=False):
            if count >= max_items: break
            if not dirnames and not filenames:
                garbage["safe"].append(dirpath)
                count += 1
    except (PermissionError, OSError):
        pass
    return garbage

# === Автозагрузка (Windows) ===
def get_startup_apps():
    if not IS_WINDOWS:
        return []
    apps = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        i = 0
        while True:
            try:
                name, value, _ = winreg.EnumValue(key, i)
                apps.append({"name": name, "path": value, "enabled": True})
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception:
        pass

    try:
        startup_path = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
        if os.path.exists(startup_path):
            for item in os.listdir(startup_path):
                full_path = os.path.join(startup_path, item)
                if os.path.isfile(full_path) and item.endswith(('.lnk', '.exe', '.bat', '.cmd')):
                    apps.append({
                        "name": os.path.splitext(item)[0],
                        "path": full_path,
                        "enabled": True,
                        "type": "shortcut"
                    })
    except Exception:
        pass

    return apps

def toggle_startup_app(name, path, enable, is_shortcut=False):
    if not IS_WINDOWS:
        return False
    try:
        if is_shortcut:
            if enable:
                new_path = path.replace(".disabled", "")
                if os.path.exists(new_path):
                    return False
                os.rename(path, new_path)
            else:
                disabled_path = path + ".disabled"
                os.rename(path, disabled_path)
            return True
        else:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_WRITE)
            if enable:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, path)
            else:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
    except Exception:
        return False

# === Анимация ===
class AnimatedSpinner:
    def __init__(self, parent, text="Сканирование…"):
        self.parent = parent
        self.text = text
        self.label = ttk.Label(parent, text="", foreground=ACCENT_COLOR, font=("Segoe UI", 11))
        self.frames = ["🔍", "🌀", "🔍", "🔍"]
        self.idx = 0
        self.running = False

    def start(self):
        self.running = True
        self._animate()

    def stop(self):
        self.running = False
        self.label.config(text="")

    def pack(self, **kwargs):
        self.label.pack(**kwargs)

    def _animate(self):
        if self.running:
            self.label.config(text=f"{self.frames[self.idx]} {self.text}")
            self.idx = (self.idx + 1) % len(self.frames)
            self.parent.after(300, self._animate)

# === Прокручиваемый фрейм ===
class ScrolledFrame(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg=BG_COLOR, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Button-4>", self._on_mousewheel)
        self.bind_all("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def clear(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

# === Основное приложение ===
class CleanSweepApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🧹 CleanSweep — Умная очистка")
        self.root.geometry("880x660")
        self.root.minsize(700, 500)
        self.root.configure(bg=BG_COLOR)
        self.items = {"safe": [], "risky": []}
        self.vars = {"safe": [], "risky": []}
        self.startup_apps = []
        self.current_view = "risky"

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG_COLOR)
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Accent.TButton", foreground="white", background=ACCENT_COLOR)
        style.map("Accent.TButton", background=[("active", "#4338ca")])
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), background=BG_COLOR, foreground=TEXT_COLOR)
        style.configure("TLabel", background=BG_COLOR, foreground=TEXT_COLOR)
        style.configure("Card.TFrame", background=CARD_BG)

        header = ttk.Frame(root)
        header.pack(fill=tk.X, padx=40, pady=(20, 10))
        ttk.Label(header, text="🧹 CleanSweep", style="Header.TLabel").pack()
        ttk.Label(header, text="Очистка временных файлов и управление автозагрузкой", foreground=MUTED_COLOR).pack()

        self.scan_btn = ttk.Button(root, text="Начать сканирование", command=self.start_scan, style="Accent.TButton")
        self.scan_btn.pack(pady=10)

        self.spinner = AnimatedSpinner(root, text="Анализ файловой системы…")
        self.spinner.pack()

        tab_frame = ttk.Frame(root)
        tab_frame.pack(pady=(0, 10))
        self.risky_btn = ttk.Button(tab_frame, text="⚠️ Важные файлы", command=lambda: self.switch_view("risky"))
        self.safe_btn = ttk.Button(tab_frame, text="✅ Безопасный мусор", command=lambda: self.switch_view("safe"))
        self.startup_btn = ttk.Button(tab_frame, text="🚀 Автозагрузка", command=self.show_startup)
        self.risky_btn.pack(side=tk.LEFT, padx=5)
        self.safe_btn.pack(side=tk.LEFT, padx=5)
        if IS_WINDOWS:
            self.startup_btn.pack(side=tk.LEFT, padx=5)

        self.list_container = ScrolledFrame(root)
        self.list_container.pack(fill=tk.BOTH, expand=True, padx=40, pady=(0, 20))

        bottom = ttk.Frame(root)
        bottom.pack(fill=tk.X, padx=40, pady=(0, 20))
        self.status = ttk.Label(bottom, text="Готово к сканированию", foreground=MUTED_COLOR)
        self.status.pack(side=tk.LEFT)
        self.delete_btn = ttk.Button(bottom, text="🗑️ Удалить выбранные", state=tk.DISABLED, style="Accent.TButton", command=self.delete_selected)
        self.delete_btn.pack(side=tk.RIGHT)

    def start_scan(self):
        self.scan_btn.config(state=tk.DISABLED)
        self.spinner.start()
        self.status.config(text="Сканирование запущено…")
        self.root.after(200, self.perform_scan)

    def perform_scan(self):
        self.items = scan_home()
        self.spinner.stop()
        self.show_view(self.current_view)
        total = len(self.items["safe"]) + len(self.items["risky"])
        self.status.config(text=f"Найдено: {total} элементов")
        self.scan_btn.config(state=tk.NORMAL)
        self.delete_btn.config(state=tk.NORMAL if total > 0 else tk.DISABLED)

    def switch_view(self, view):
        self.current_view = view
        self.show_view(view)

    def show_view(self, view):
        self.list_container.clear()
        items = self.items[view]

        if not items:
            msg = "⚠️ Потенциально важные файлы не найдены." if view == "risky" else "✅ Безопасный мусор не найден."
            label = ttk.Label(self.list_container.scrollable_frame, text=msg, foreground=MUTED_COLOR, font=("Segoe UI", 11))
            label.pack(pady=30)
            return

        display_items = items[:100]
        info = ttk.Label(self.list_container.scrollable_frame, text=f"Показано {len(display_items)} из {len(items)}", foreground=MUTED_COLOR)
        info.pack(anchor=tk.W, padx=10, pady=(0, 10))

        for path in display_items:
            var = tk.BooleanVar(value=True)
            self.vars[view].append((var, path))

            card = ttk.Frame(self.list_container.scrollable_frame, style="Card.TFrame")
            card.pack(fill=tk.X, padx=10, pady=4, ipady=6)

            color = WARNING_COLOR if view == "risky" else SAFE_COLOR
            indicator = tk.Canvas(card, width=6, height=24, bg=color, highlightthickness=0)
            indicator.pack(side=tk.LEFT, padx=(0, 12))

            name = os.path.basename(path)
            dir_part = os.path.dirname(path).replace(os.path.expanduser("~"), "~")
            full_text = f"{name}\n{dir_part}"

            label = tk.Label(card, text=full_text, justify=tk.LEFT, bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10))
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            cb = ttk.Checkbutton(card, variable=var)
            cb.pack(side=tk.RIGHT, padx=(0, 10))

        if len(items) > 100:
            extra = ttk.Label(self.list_container.scrollable_frame, text="… список сокращён для удобства", foreground=MUTED_COLOR)
            extra.pack(pady=(10, 0))

    def show_startup(self):
        if not IS_WINDOWS:
            messagebox.showinfo("Инфо", "Управление автозагрузкой доступно только на Windows.")
            return

        self.list_container.clear()
        self.startup_apps = get_startup_apps()

        if not self.startup_apps:
            label = ttk.Label(self.list_container.scrollable_frame, text="Автозагрузка пуста", foreground=MUTED_COLOR, font=("Segoe UI", 11))
            label.pack(pady=30)
            return

        info = ttk.Label(self.list_container.scrollable_frame, text=f"Программ в автозагрузке: {len(self.startup_apps)}", foreground=MUTED_COLOR)
        info.pack(anchor=tk.W, padx=10, pady=(0, 10))

        for app in self.startup_apps:
            card = ttk.Frame(self.list_container.scrollable_frame, style="Card.TFrame")
            card.pack(fill=tk.X, padx=10, pady=4, ipady=6)

            status = "✔️ Включено" if app.get("enabled", True) else "⛔ Отключено"
            status_color = SAFE_COLOR if app.get("enabled", True) else MUTED_COLOR
            status_label = ttk.Label(card, text=status, foreground=status_color, font=("Segoe UI", 9, "bold"))
            status_label.pack(side=tk.LEFT, padx=(0, 12))

            name_label = tk.Label(card, text=app["name"], bg=CARD_BG, fg=TEXT_COLOR, font=("Segoe UI", 10, "bold"))
            name_label.pack(anchor=tk.W, padx=(0, 10))

            path_label = tk.Label(card, text=app["path"], bg=CARD_BG, fg=MUTED_COLOR, font=("Segoe UI", 9))
            path_label.pack(anchor=tk.W, padx=(0, 10))

            is_shortcut = app.get("type") == "shortcut"
            if app.get("enabled", True):
                btn = ttk.Button(card, text="Отключить", command=lambda a=app, s=is_shortcut: self.toggle_app(a, False, s))
            else:
                btn = ttk.Button(card, text="Включить", command=lambda a=app, s=is_shortcut: self.toggle_app(a, True, s))
            btn.pack(side=tk.RIGHT, padx=(0, 10))

    def toggle_app(self, app, enable, is_shortcut):
        success = toggle_startup_app(app["name"], app["path"], enable, is_shortcut)
        if success:
            self.show_startup()
            action = "включена" if enable else "отключена"
            messagebox.showinfo("Готово", f"Программа «{app['name']}» {action} в автозагрузке.")
        else:
            messagebox.showerror("Ошибка", "Не удалось изменить автозагрузку.")

    def delete_selected(self):
        to_delete = []
        for var, path in self.vars["risky"]:
            if var.get():
                to_delete.append(("risky", path))
        for var, path in self.vars["safe"]:
            if var.get():
                to_delete.append(("safe", path))

        if not to_delete:
            messagebox.showinfo("Инфо", "Нет выбранных файлов.")
            return

        risky_count = sum(1 for k, _ in to_delete if k == "risky")
        if risky_count > 0:
            if not messagebox.askyesno("Внимание!", f"Вы выбрали {risky_count} потенциально важных файлов.\nУдаление может повредить проекты!\nПродолжить?", icon="warning"):
                return

        success = 0
        for _, path in to_delete:
            try:
                if os.path.isfile(path) or os.path.islink(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    os.rmdir(path)
                success += 1
            except Exception:
                pass

        messagebox.showinfo("Готово", f"Удалено: {success} элементов.")
        self.start_scan()

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = CleanSweepApp(root)
    root.mainloop()