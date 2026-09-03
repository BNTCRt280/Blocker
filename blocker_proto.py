import tkinter as tk
from tkinter import messagebox
import winreg
import ctypes
import threading
import psutil
import time
import os

JUNK_SOFTWARE = [
    "opera.exe", "operagx.exe", "browser.exe", "yandexbrowser.exe",
    "360tray.exe", "360sd.exe", "360doctor.exe", "360total.exe",
    "amigo.exe", "orbitum.exe", "mailruupdater.exe",
    "toolbar.exe", "yarunin.exe", "helper.exe", "webalta.exe",
    "installer.exe", "setup.exe", "updater.exe", "update.exe",
    "accelerator.exe", "optimizer.exe", "cleaner.exe", "booster.exe",
    "speedup.exe", "fastboot.exe", "quickstart.exe",
    "mysearch.exe", "searchhelper.exe", "websearch.exe",
    "adhelper.exe", "admanager.exe", "banner.exe",
]

SUSPICIOUS_KEYWORDS = [
    "yandex", "opera", "mail", "toolbar", "amigo",
    "orbitum", "webalta", "360",
    "updater", "accelerator", "optimizer", "cleaner",
    "booster", "speedup", "fast", "quick",
    "search", "ad", "banner",
]

JUNK_LOWER = [name.lower() for name in JUNK_SOFTWARE]

monitor_active = False
monitor_thread = None

def set_policy(enabled: bool):
    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
    except FileNotFoundError:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)

    winreg.SetValueEx(key, "DisallowRun", 0, winreg.REG_DWORD, 1 if enabled else 0)
    winreg.CloseKey(key)

    if enabled:
        _write_block_list()
    else:
        _clear_block_list()
    _refresh_policy()

def _write_block_list():
    subkey_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer\DisallowRun"
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, subkey_path)
    for i, exe_name in enumerate(JUNK_SOFTWARE, start=1):
        winreg.SetValueEx(key, str(i), 0, winreg.REG_SZ, exe_name)
    winreg.CloseKey(key)

def _clear_block_list():
    subkey_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer\DisallowRun"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey_path, 0, winreg.KEY_SET_VALUE)
        i = 0
        while True:
            try:
                value_name = winreg.EnumValue(key, i)[0]
                winreg.DeleteValue(key, value_name)
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass

def _refresh_policy():
    try:
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Policy", 0x0002, 5000, None
        )
    except Exception:
        pass

def is_policy_active() -> bool:
    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "DisallowRun")
        winreg.CloseKey(key)
        return value == 1
    except FileNotFoundError:
        return False

def is_junk_process(name: str) -> bool:
    name_lower = name.lower()
    if name_lower in JUNK_LOWER:
        return True
    for word in SUSPICIOUS_KEYWORDS:
        if word in name_lower:
            return True
    return False

def monitor_loop(log_callback):
    while monitor_active:
        killed = []
        for proc in psutil.process_iter(['pid', 'name', 'username']):
            try:
                name = proc.info['name']
                if not name:
                    continue
                if is_junk_process(name):
                    try:
                        exe_path = proc.exe()
                        system_paths = [r"C:\Windows", r"C:\Program Files", r"C:\Program Files (x86)"]
                        if any(exe_path.lower().startswith(p.lower()) for p in system_paths):
                            continue
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                    proc.terminate()
                    killed.append(f"{name} (PID {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if killed:
            for entry in killed:
                log_callback(f"[KILL] {entry}")
        time.sleep(1)

def start_monitor(log_callback):
    global monitor_active, monitor_thread
    monitor_active = True
    monitor_thread = threading.Thread(target=monitor_loop, args=(log_callback,), daemon=True)
    monitor_thread.start()

def stop_monitor():
    global monitor_active
    monitor_active = False

def build_ui():
    root = tk.Tk()
    root.title("Блокировщик мусорного софта")
    root.geometry("440x460")
    root.resizable(False, False)

    tk.Label(root, text="Управление блокировкой мусорного ПО",
             font=("Arial", 12, "bold")).pack(pady=10)

    policy_status = tk.StringVar(value="Проверяю...")
    tk.Label(root, textvariable=policy_status, font=("Arial", 10)).pack(pady=3)

    monitor_status = tk.StringVar(value="Монитор: выключен")
    tk.Label(root, textvariable=monitor_status, font=("Arial", 10),
             fg="gray").pack(pady=3)

    log_frame = tk.Frame(root)
    log_frame.pack(pady=5, fill="x", padx=15)
    log_text = tk.Text(log_frame, height=12, width=50, font=("Consolas", 9))
    log_scroll = tk.Scrollbar(log_frame, command=log_text.yview)
    log_text.configure(yscrollcommand=log_scroll.set)
    log_scroll.pack(side="right", fill="y")
    log_text.pack(side="left", fill="both", expand=True)
    log_text.configure(state="disabled")

    def log(msg):
        log_text.configure(state="normal")
        log_text.insert("end", msg + "\n")
        log_text.see("end")
        log_text.configure(state="disabled")

    def update_status():
        policy_status.set(
            "● Блокировка ВКЛЮЧЕНА" if is_policy_active() else "○ Блокировка отключена"
        )
        monitor_status.set(
            "● Монитор: работает" if monitor_active else "○ Монитор: выключен"
        )

    def on_enable():
        try:
            set_policy(True)
            start_monitor(log)
            log(f"[OK] Политика включена, монитор запущен. Заблокировано: {len(JUNK_SOFTWARE)} программ.")
            update_status()
        except PermissionError:
            messagebox.showerror("Ошибка", "Нет прав! Запусти от имени администратора.")

    def on_disable():
        try:
            set_policy(False)
            stop_monitor()
            log("[OK] Политика снята, монитор остановлен.")
            update_status()
        except PermissionError:
            messagebox.showerror("Ошибка", "Нет прав! Запусти от имени администратора.")

    def on_toggle_monitor():
        if monitor_active:
            stop_monitor()
            log("[OK] Монитор остановлен.")
        else:
            start_monitor(log)
            log("[OK] Монитор запущен.")
        update_status()

    tk.Button(root, text="🔒 Включить всё (политика + монитор)",
              command=on_enable, font=("Arial", 11),
              bg="#d9534f", fg="white", height=2, width=36).pack(pady=8)

    tk.Button(root, text="🔓 Выключить всё",
              command=on_disable, font=("Arial", 11),
              bg="#5cb85c", fg="white", height=2, width=36).pack(pady=3)

    tk.Button(root, text="⏯ Монитор вкл/выкл",
              command=on_toggle_monitor, font=("Arial", 10),
              bg="#f0ad4e", fg="white", height=1, width=36).pack(pady=3)

    tk.Label(root, text=f"В списке: {len(JUNK_SOFTWARE)} программ",
             font=("Arial", 9), fg="gray").pack(pady=5)

    update_status()
    root.mainloop()

if __name__ == "__main__":
    build_ui()
