#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import subprocess
import runpy
from pathlib import Path
import requests
import tempfile
import hashlib
import platform
import uuid
import json
import time
from datetime import datetime, timedelta
import random
import string
import threading
import ast

# ===== FIX ENCODING CHO MỌI ĐIỀU HÀNH =====
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# ===== CÀI THƯ VIỆN THIẾU =====
REQUIRED = ["pystyle", "requests", "colorama", "rich"]
for pkg in REQUIRED:
    try:
        __import__(pkg)
    except ImportError:
        print(f"[*] Đang tự động cài đặt thư viện thiếu: {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        print(f"[+] Cài đặt {pkg} thành công!")

# ===== IMPORT RICH =====
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

# ===== CẤU HÌNH =====
LINK4M_API_KEY = "68b724432ecbb063ee12123a"
KEY_WEB_URL = "https://caoquy2k3.github.io/Phong-tus/"
SETUP_JSON_URL = "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/refs/heads/main/setup.json"

# ===== KEYS =====
SPECIAL_KEY_20032007 = "20032007"  # Key này sẽ bị xóa sau 1.5h
ADMIN_KEY_PHONGANH = "phonganh"   # Key admin mới, vĩnh viễn, không giới hạn

BASE_DIR = Path(__file__).parent.absolute()
KEY_DIR = BASE_DIR / "key"
KEY_FILE = KEY_DIR / "license_key.txt"
USED_KEYS_FILE = KEY_DIR / "used_keys.txt"
DEVICE_FILE = KEY_DIR / "device_id.txt"
KEY_DATA_FILE = KEY_DIR / "key_data.json"
LAST_CHECK_FILE = KEY_DIR / "last_check.txt"

try:
    KEY_DIR.mkdir(exist_ok=True)
except:
    pass


# ===== SETUP =====
def setup_prompt():
    choice = input("Chạy setup? (y/n): ").strip().lower()
    if choice == 'y':
        try:
            for cmd in requests.get(SETUP_JSON_URL).json().get("setup", []):
                os.system(cmd)
        except:
            pass
    return False


# ===== License Manager =====
class LicenseManager:
    def __init__(self):
        self.key_dir = KEY_DIR
        self.key_file = KEY_FILE
        self.used_keys_file = USED_KEYS_FILE
        self.device_file = DEVICE_FILE
        self.key_data_file = KEY_DATA_FILE
        self.last_check_file = LAST_CHECK_FILE
        self.api_key = LINK4M_API_KEY
        self.key_web = KEY_WEB_URL
        self.special_key_20032007 = SPECIAL_KEY_20032007
        self.admin_key_phonganh = ADMIN_KEY_PHONGANH
        self._current_device_id = None
        self._is_valid = False
        self._key_data = None
        self._check_thread = None
        self._stop_check = False
        self._remaining_time_callback = None
        self._special_key_delete_time = None  # Thời gian sẽ xóa key 20032007

    def create_link4m(self, target_url=None):
        if target_url is None:
            target_url = self.key_web
        try:
            api_url = f"https://link4m.co/api-shorten/v2?api={self.api_key}&url={target_url}"
            resp = requests.get(api_url, timeout=8)
            data = resp.json()
            if data.get("status") == "success":
                return data.get("shortenedUrl")
            return target_url
        except Exception:
            return target_url

    def get_device_id(self, force_new=False):
        if force_new:
            self._current_device_id = None
            if self.device_file.exists():
                try:
                    os.remove(self.device_file)
                except:
                    pass

        if self._current_device_id:
            return self._current_device_id

        if self.device_file.exists() and not force_new:
            try:
                with open(self.device_file, 'r', encoding='utf-8') as f:
                    device_id = f.read().strip()
                    if device_id and len(device_id) == 64:
                        self._current_device_id = device_id
                        return device_id
            except:
                pass

        try:
            machine_info = []
            mac = uuid.getnode()
            machine_info.append(str(mac))
            machine_info.append(platform.node())
            machine_info.append(platform.processor() or "unknown")
            machine_info.append(platform.machine())
            machine_info.append(platform.system())
            machine_info.append(sys.prefix)

            if sys.platform == "win32":
                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                         "SOFTWARE\\Microsoft\\Cryptography")
                    machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                    machine_info.append(machine_guid)
                    winreg.CloseKey(key)
                except:
                    pass
            else:
                try:
                    with open('/etc/machine-id', 'r') as f:
                        machine_info.append(f.read().strip())
                except:
                    pass

            combined = "|".join(machine_info)
            device_id = hashlib.sha256(combined.encode()).hexdigest()

            with open(self.device_file, 'w', encoding='utf-8') as f:
                f.write(device_id)

            self._current_device_id = device_id
            return device_id

        except Exception:
            fallback_id = hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()
            with open(self.device_file, 'w', encoding='utf-8') as f:
                f.write(fallback_id)
            self._current_device_id = fallback_id
            return fallback_id

    def reset_device_id(self):
        if self.device_file.exists():
            try:
                os.remove(self.device_file)
                console.print("[#ff9ecb] Đã reset device ID[/]")
            except:
                pass
        self._current_device_id = None

    def load_key_data(self):
        try:
            if not self.key_data_file.exists():
                return None
            with open(self.key_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None

    def save_key_data(self, data):
        try:
            with open(self.key_data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False

    def delete_key_data(self):
        try:
            if self.key_data_file.exists():
                os.remove(self.key_data_file)
            return True
        except:
            return False

    def load_key_from_file(self):
        try:
            if not self.key_file.exists():
                return None
            with open(self.key_file, 'r', encoding='utf-8') as f:
                key = f.read().strip()
            return key if key else None
        except:
            return None

    def save_key_to_file(self, key):
        try:
            with open(self.key_file, 'w', encoding='utf-8') as f:
                f.write(key)
            return True
        except:
            return False

    def delete_key_file(self):
        try:
            if self.key_file.exists():
                os.remove(self.key_file)
                console.print("[#ff9ecb] Đã xóa file key cũ[/]")
            return True
        except:
            return False

    def load_used_keys(self):
        try:
            if not self.used_keys_file.exists():
                return []
            with open(self.used_keys_file, 'r', encoding='utf-8') as f:
                keys = [line.strip() for line in f.readlines() if line.strip()]
            return keys
        except:
            return []

    def save_used_key(self, key):
        if key == self.admin_key_phonganh:
            return True
        try:
            used_keys = self.load_used_keys()
            if key not in used_keys:
                used_keys.append(key)
            if len(used_keys) > 5000:
                used_keys = used_keys[-5000:]
            with open(self.used_keys_file, 'w', encoding='utf-8') as f:
                for k in used_keys:
                    f.write(k + '\n')
            return True
        except:
            return False

    def is_key_used(self, key):
        if key == self.admin_key_phonganh:
            return False
        used_keys = self.load_used_keys()
        return key in used_keys

    def check_expiry(self, expiry_str):
        if not expiry_str:
            return False, 0, "Không có thông tin hết hạn"
        try:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            if now > expiry:
                return False, 0, "Key đã hết hạn"
            remaining = expiry - now
            remaining_minutes = int(remaining.total_seconds() / 60)
            remaining_hours = remaining_minutes // 60
            remaining_mins = remaining_minutes % 60
            if remaining_hours > 0:
                msg = f"Còn {remaining_hours}h {remaining_mins}p"
            else:
                msg = f"Còn {remaining_minutes} phút"
            return True, remaining_minutes, msg
        except Exception as e:
            return False, 0, f"Lỗi kiểm tra: {e}"

    def verify_key(self, key):
        device_id = self.get_device_id()
        
        # Key admin mới phonganh - vĩnh viễn, không giới hạn
        if key == self.admin_key_phonganh:
            return True, {
                "key": key,
                "expiry": "2099-12-31 23:59:59",
                "device_id": device_id,
                "is_admin": True,
                "is_special_20032007": False
            }
        
        # Key 20032007 - free vĩnh viễn nhưng sẽ bị xóa sau 1.5h
        if key == self.special_key_20032007:
            # Lưu thời gian sẽ xóa (1.5 giờ = 5400 giây)
            delete_time = datetime.now() + timedelta(hours=1.5)
            return True, {
                "key": key,
                "expiry": "2099-12-31 23:59:59",  # Hiển thị vĩnh viễn
                "device_id": device_id,
                "is_admin": False,
                "is_special_20032007": True,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "delete_at": delete_time.strftime("%Y-%m-%d %H:%M:%S")  # Thời gian sẽ xóa file key
            }
        
        # Key thường
        if not key.startswith("PHONG-TUS-") or len(key) != 26:
            return False, "invalid_format"
        if self.is_key_used(key):
            return False, "already_used"
        saved_key_data = self.load_key_data()
        saved_key = self.load_key_from_file()
        if saved_key and saved_key != key:
            return False, "different_device"
        if saved_key_data:
            saved_device_id = saved_key_data.get("device_id")
            if saved_device_id and saved_device_id != device_id:
                self.reset_device_id()
                self.delete_key_file()
                self.delete_key_data()
                return False, "device_mismatch"
            expiry_str = saved_key_data.get("expiry")
            if expiry_str:
                is_valid, _, _ = self.check_expiry(expiry_str)
                if not is_valid:
                    self.delete_key_file()
                    self.delete_key_data()
                    return False, "expired"
        expiry_time = datetime.now() + timedelta(hours=24)
        return True, {
            "key": key,
            "expiry": expiry_time.strftime("%Y-%m-%d %H:%M:%S"),
            "device_id": device_id,
            "is_admin": False,
            "is_special_20032007": False
        }

    def save_key_with_data(self, key, key_data):
        if not self.save_key_to_file(key):
            return False
        if not self.save_key_data(key_data):
            return False
        if key != self.admin_key_phonganh:
            self.save_used_key(key)
        self._key_data = key_data
        
        # Nếu là key 20032007, lưu thời gian xóa
        if key == self.special_key_20032007:
            self._special_key_delete_time = datetime.strptime(key_data.get("delete_at"), "%Y-%m-%d %H:%M:%S")
        
        self._is_valid = True
        return True

    def check_anti_share(self):
        saved_key_data = self.load_key_data()
        saved_key = self.load_key_from_file()
        if not saved_key or not saved_key_data:
            return True
        
        # Key admin phonganh không check share
        if saved_key == self.admin_key_phonganh:
            return True
        
        current_device_id = self.get_device_id()
        saved_device_id = saved_key_data.get("device_id")
        if saved_device_id and saved_device_id != current_device_id:
            console.print(Panel(
                f"[#ff4d6d] PHÁT HIỆN COPY TOOL SANG MÁY KHÁC![/]\n\n"
                f"[#ffffff]Tool này đã được kích hoạt trên máy khác.\n"
                f"Vui lòng lấy key mới để sử dụng.[/]",
                border_style="#ff4d6d",
                box=box.DOUBLE,
                title="[#ff9ecb]CHỐNG SHARE[/]"
            ))
            self.delete_key_file()
            self.delete_key_data()
            self.reset_device_id()
            return False
        return True

    def get_remaining_time(self):
        if not self._key_data:
            key_data = self.load_key_data()
            if not key_data:
                return None
            self._key_data = key_data
        expiry_str = self._key_data.get("expiry")
        if not expiry_str:
            return None
        try:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            if now > expiry:
                return None
            remaining = expiry - now
            return remaining
        except:
            return None

    def get_remaining_display(self):
        if not self._key_data:
            key_data = self.load_key_data()
            if not key_data:
                return None
            self._key_data = key_data
        
        # Key admin phonganh - vĩnh viễn
        if self._key_data.get("is_admin") and self._key_data.get("key") == self.admin_key_phonganh:
            return "[#00ff9c]👑 ADMIN  [ phonganh ] - Vĩnh viễn[/]"
        
        # Key 20032007 - hiển thị thời gian còn lại đến khi xóa file
        if self._key_data.get("is_special_20032007"):
            delete_at_str = self._key_data.get("delete_at")
            if delete_at_str:
                try:
                    delete_time = datetime.strptime(delete_at_str, "%Y-%m-%d %H:%M:%S")
                    now = datetime.now()
                    if now >= delete_time:
                        return "[#ff4d6d] KEY SẼ BỊ XÓA NGAY[/]"
                    remaining = delete_time - now
                    remaining_minutes = int(remaining.total_seconds() / 60)
                    remaining_hours = remaining_minutes // 60
                    remaining_mins = remaining_minutes % 60
                    return f"[#ffffff] Key [#ff9ecb] Free [#ffffff]Còn {remaining_hours}h {remaining_mins}p nữa sẽ tự động xóa file key (Free vĩnh viễn)[/]"
                except:
                    pass
            return f"[#ffffff] Key [#ff9ecb] Free [#ffffff]Vĩnh viễn[/]"
        
        expiry_str = self._key_data.get("expiry")
        if not expiry_str:
            return None
        try:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            if now > expiry:
                return "[#ff4d6d] KEY ĐÃ HẾT HẠN[/]"
            remaining = expiry - now
            remaining_minutes = int(remaining.total_seconds() / 60)
            remaining_hours = remaining_minutes // 60
            remaining_mins = remaining_minutes % 60
            
            if remaining_hours > 0:
                return f"[#00ffff] Còn {remaining_hours}h {remaining_mins}p | Hết: {expiry_str[:16]}[/]"
            else:
                return f"[#ff9ecb] Còn {remaining_minutes} phút | Hết: {expiry_str[:16]}[/]"
        except:
            return None

    def continuous_check(self, callback=None):
        while not self._stop_check:
            try:
                saved_key = self.load_key_from_file()
                saved_key_data = self.load_key_data()
                if saved_key and saved_key_data:
                    self._key_data = saved_key_data
                    
                    # Kiểm tra key 20032007 - xóa file sau 1.5h
                    if saved_key == self.special_key_20032007:
                        delete_at_str = saved_key_data.get("delete_at")
                        if delete_at_str:
                            delete_time = datetime.strptime(delete_at_str, "%Y-%m-%d %H:%M:%S")
                            now = datetime.now()
                            if now >= delete_time:
                                console.print("\n" + "=" * 50)
                                console.print(Panel(
                                    f"[#ff9ecb] KEY ĐÃ HẾT THỜI GIAN SỬ DỤNG 1.5 GIỜ![/]\n\n"
                                    f"Tool sẽ tự động xóa file key và chuyển sang nhập key mới sau 10 giây...[/]",
                                    border_style="#ff9ecb",
                                    box=box.DOUBLE,
                                    title="[#ff9ecb]XÓA KEY[/]"
                                ))
                                console.print("=" * 50 + "\n")
                                self.delete_key_file()
                                self.delete_key_data()
                                self._is_valid = False
                                for i in range(10, 0, -1):
                                    console.print(f"[#ff9ecb]Chuyển sang nhập key sau {i} giây...[/]", end="\r")
                                    time.sleep(1)
                                self._stop_check = True
                                return
                    
                    # Kiểm tra key thường hết hạn
                    elif saved_key != self.admin_key_phonganh:
                        expiry_str = saved_key_data.get("expiry")
                        if expiry_str and expiry_str != "2099-12-31 23:59:59":
                            is_valid, minutes_left, msg = self.check_expiry(expiry_str)
                            if not is_valid:
                                console.print("\n" + "=" * 50)
                                console.print(Panel(
                                    f"[#ff4d6d] KEY ĐÃ HẾT HẠN![/]\n\n"
                                    f"[#ffffff]{msg}\n"
                                    f"Tool sẽ tự động thoát sau 10 giây...\n"
                                    f"Vui lòng chạy lại và lấy key mới.[/]",
                                    border_style="#ff4d6d",
                                    box=box.DOUBLE,
                                    title="[#ff9ecb]HẾT HẠN[/]"
                                ))
                                console.print("=" * 50 + "\n")
                                self.delete_key_file()
                                self.delete_key_data()
                                self._is_valid = False
                                for i in range(10, 0, -1):
                                    console.print(f"[#ff4d6d]Thoát sau {i} giây...[/]", end="\r")
                                    time.sleep(1)
                                os._exit(0)
                            else:
                                self._is_valid = True
                                if callback:
                                    callback()
                else:
                    if self._stop_check:
                        break
                    console.print("\n" + "=" * 50)
                    console.print(Panel(
                        f"[#ff4d6d] KHÔNG TÌM THẤY KEY![/]\n\n"
                        f"[#ffffff]Tool sẽ tự động thoát sau 10 giây...\n"
                        f"Vui lòng chạy lại và nhập key.[/]",
                        border_style="#ff4d6d",
                        box=box.DOUBLE,
                        title="[#ff9ecb]LỖI[/]"
                    ))
                    console.print("=" * 50 + "\n")
                    for i in range(10, 0, -1):
                        console.print(f"[#ff4d6d]Thoát sau {i} giây...[/]", end="\r")
                        time.sleep(1)
                    os._exit(0)
            except Exception as e:
                pass
            for _ in range(60):
                if self._stop_check:
                    break
                time.sleep(1)
    
    def start_continuous_check(self, callback=None):
        self._stop_check = False
        self._remaining_time_callback = callback
        self._check_thread = threading.Thread(target=self.continuous_check, args=(callback,), daemon=True)
        self._check_thread.start()
    
    def stop_continuous_check(self):
        self._stop_check = True
        if self._check_thread:
            self._check_thread.join(timeout=2)

    def check_and_activate(self):
        if not self.check_anti_share():
            time.sleep(2)
            return self.activate_with_key()
        saved_key = self.load_key_from_file()
        saved_key_data = self.load_key_data()
        if saved_key and saved_key_data:
            console.print("[#00ffff]  Đang kiểm tra key...[/]")
            expiry_str = saved_key_data.get("expiry")
            
            # Key admin phonganh - hợp lệ vĩnh viễn
            if saved_key == self.admin_key_phonganh:
                console.print(Panel(
                    f"[#00ff9c] KEY ADMIN HỢP LỆ![/]\n"
                    f"[#ffffff]Key: {saved_key}\n"
                    f"Hạn sử dụng: Vĩnh viễn\n"
                    f"Chế độ: [bold]Admin - Không giới hạn[/]\n"
                    f"Đã kích hoạt thành công![/]",
                    border_style="#a78bfa",
                    box=box.DOUBLE,
                    title="[#ff9ecb]LICENSE[/]",
                    title_align="center", 
                    width=38,
                    height=8 
                ))
                self._key_data = saved_key_data
                self._is_valid = True
                time.sleep(2)
                return True
            
            # Key 20032007
            if saved_key == self.special_key_20032007:
                delete_at_str = saved_key_data.get("delete_at")
                if delete_at_str:
                    delete_time = datetime.strptime(delete_at_str, "%Y-%m-%d %H:%M:%S")
                    now = datetime.now()
                    if now >= delete_time:
                        console.print(Panel(
                            f"[#ffab40] KEY ĐÃ HẾT THỜI GIAN SỬ DỤNG![/]\n\n"
                            f"[#ffffff]Key này đã được sử dụng được 1.5 giờ.\n"
                            f"Vui lòng lấy key mới để tiếp tục.[/]",
                            border_style="#ffab40",
                            box=box.DOUBLE,
                            title="[#ff9ecb]HẾT HẠN[/]"
                        ))
                        self.delete_key_file()
                        self.delete_key_data()
                        time.sleep(2)
                        return self.activate_with_key()
                    
                    remaining = delete_time - now
                    remaining_minutes = int(remaining.total_seconds() / 60)
                    remaining_hours = remaining_minutes // 60
                    remaining_mins = remaining_minutes % 60
                    
                    console.print(Panel(
                        f"[#ff9ecb] KEY HỢP LỆ![/]\n\n"
                        f"Hạn sử dụng: Free vĩnh viễn\n"
                        f"[#00ffff] Sẽ tự động xóa file key sau {remaining_hours}h {remaining_mins}p[/]\n"
                        f"[#ff9ecb][/]",
                        border_style="#ff9ecb",
                        box=box.DOUBLE,
                        title="[#ff9ecb]LICENSE[/]",
                        title_align="center", 
                        width=45,
                        height=7
                    ))
                else:
                    console.print(Panel(
                        f"[#ff9ecb] KEY HỢP LỆ![/]\n\n"
                        f"Hạn sử dụng: Free vĩnh viễn\n"
                        f"Sẽ tự động xóa file key sau 1.5 giờ[/]",
                        border_style="#ff9ecb",
                        box=box.DOUBLE,
                        title="[#ff9ecb]LICENSE[/]",
                        title_align="center", 
                        width=40,
                        height=6
                    ))
                self._key_data = saved_key_data
                self._is_valid = True
                time.sleep(2)
                return True
            
            if expiry_str:
                is_valid, minutes_left, msg = self.check_expiry(expiry_str)
                if not is_valid:
                    console.print(Panel(
                        f"[#ffab40] KEY ĐÃ HẾT HẠN![/]\n\n"
                        f"[#ffffff]{msg}\n"
                        f"Vui lòng lấy key mới để tiếp tục.[/]",
                        border_style="#ffab40",
                        box=box.DOUBLE,
                        title="[#ff9ecb]HẾT HẠN[/]"
                    ))
                    self.delete_key_file()
                    self.delete_key_data()
                    time.sleep(2)
                    return self.activate_with_key()
                
                console.print(Panel(
                    f"[#00ff9c] KEY HỢP LỆ![/]\n\n"
                    f"[#ffffff]Key: {saved_key}\n"
                    f"Hạn sử dụng: {expiry_str}\n"
                    f"[#00ffff] {msg}[/]\n"
                    f"Key Đã gắn cứng với máy này[/]",
                    border_style="#a78bfa",
                    box=box.DOUBLE,
                    title="[#ff9ecb]LICENSE[/]",
                    title_align="center", 
                    width=38,
                    height=8
                ))
                self._key_data = saved_key_data
                self._is_valid = True
                time.sleep(2)
                return True
        return self.activate_with_key()

    def activate_with_key(self):
        current_url = self.key_web
        short_link = None
        while True:
            console.print(Panel(
                f"[#00ffff] HƯỚNG DẪN LẤY KEY[/]\n\n"
                f"[#ffffff]1. Bạn sẽ nhận được 1 link bên dưới\n"
                f"2. Copy link và mở trong trình duyệt\n"
                f"3. Web sẽ tự tạo key ngẫu nhiên cho bạn\n"
                f"4. Copy key và paste vào đây để kích hoạt\n\n"
                f"[#ff9ecb]  LƯU Ý QUAN TRỌNG:[/]\n"
                f"• Mỗi key thường chỉ dùng 1 lần duy nhất\n"
                f"[#00ffff]• Gõ 'doilink' để đổi link lấy key mới[/]",
                border_style="#a78bfa",
                title="[#ff9ecb]KÍCH HOẠT[/]",
                title_align="center",
                box=box.DOUBLE, 
                width=50,
                height=14
            ))
            console.print("[#00ffff]  Đang tạo link...[/]")
            short_link = self.create_link4m(current_url)
            if not short_link:
                short_link = current_url
                console.print("[#ff9ecb]  Không thể tạo link rút gọn, dùng link gốc[/]")
            console.print(Panel(
                f"[#00ff9c] LINK CỦA BẠN (COPY LINK NÀY)[/]\n\n"
                f"[#ffffff]➤[bold #ff9ecb] {short_link}[/]\n\n"
                f"[#ff9ecb]➤[#ffffff]  Copy link trên và mở trong trình duyệt\n"
                f"[#ff9ecb]➤[#ffffff] Web sẽ tự tạo key ngẫu nhiên\n"
                f"[#ff9ecb]➤[#ffffff] Copy key và paste vào bên dưới\n"
                f"[#00ffff]➤ [#ffffff]Gõ [#00ffff]'doilink' [#ffffff]để đổi link lấy key mới[/]\n", 
                border_style="#a78bfa", 
                title="[#ff9ecb]LINK LẤY KEY[/]",
                title_align="center",
                box=box.DOUBLE,
                width=50,
                height=10
            ))
            console.print("[#ff9ecb]➤ [#ffffff]Nhập Key Vào Đây [#ffffff]hoặc [#00ffff]doilink [#ffffff]để lấy key mới: [#ffffff]", end="")
            user_input = input().strip().lower()
            
            if user_input == "doilink":
                separator = "&" if "?" in self.key_web else "?"
                current_url = f"{self.key_web}{separator}t={int(time.time())}"
                console.print("[#00ffff]  Đang đổi link vượt mới...[/]\n")
                time.sleep(1)
                continue
            
            user_key = user_input.upper() if user_input not in ["phonganh", "20032007"] else user_input.lower()
            
            if not user_key:
                console.print("[#ff4d6d]  Chưa nhập key![/]")
                time.sleep(1)
                continue
            
            console.print("[#00ffff]  Đang xác thực key...[/]")
            valid, result = self.verify_key(user_key)
            if not valid:
                if result == "already_used":
                    console.print(Panel(
                        f"[#ff4d6d] KEY NÀY ĐÃ ĐƯỢC SỬ DỤNG![/]\n\n"
                        f"[#ffffff]Mỗi key chỉ dùng 1 lần duy nhất.\n"
                        f"Vui lòng lấy key mới từ web.[/]",
                        title="[#ff9ecb]LỖI[/]",
                        border_style="#ff4d6d",
                        box=box.DOUBLE
                    ))
                elif result == "expired":
                    console.print(Panel(
                        f"[#ffab40] KEY ĐÃ HẾT HẠN![/]\n\n"
                        f"[#ffffff]Vui lòng lấy key mới từ web.[/]",
                        title="[#ff9ecb]HẾT HẠN[/]",
                        border_style="#ffab40",
                        box=box.DOUBLE
                    ))
                elif result == "invalid_format":
                    console.print(Panel(
                        f"[#ff4d6d] KEY KHÔNG ĐÚNG ĐỊNH DẠNG![/]\n\n"
                        f"[#ffffff]Vui lòng kiểm tra lại key[/]",
                        title="[#ff9ecb]LỖI[/]",
                        border_style="#ff4d6d",
                        box=box.DOUBLE, 
                        width=37,
                        height=5
                    ))
                elif result == "device_mismatch":
                    console.print(Panel(
                        f"[#ff4d6d] PHÁT HIỆN COPY TOOL![/]\n\n"
                        f"[#ffffff]Tool này đã được kích hoạt trên máy khác.\n"
                        f"Đã reset thiết bị. Vui lòng lấy key mới.[/]",
                        title="[#ff9ecb]CHỐNG SHARE[/]",
                        border_style="#ff4d6d",
                        box=box.DOUBLE
                    ))
                else:
                    console.print(Panel(
                        f"[#ff4d6d] KEY KHÔNG HỢP LỆ![/]\n\n"
                        f"[#ffffff]Vui lòng kiểm tra lại key hoặc lấy key mới.[/]",
                        title="[#ff9ecb]LỖI[/]",
                        border_style="#ff4d6d",
                        box=box.DOUBLE
                    ))
                console.print("\n[#888888]Nhấn Enter để thử lại...[/]", end="")
                input()
                continue
            
            if self.save_key_with_data(user_key, result):
                # Key 20032007
                if user_key == self.special_key_20032007:
                    console.print(Panel(
                        f"[#ff9ecb]✓ KÍCH HOẠT KEY THÀNH CÔNG![/]\n\n"
                        f"[#ffffff]Key: {user_key}\n"
                        f"Hạn sử dụng: FREE VĨNH VIỄN\n"
                        f"Sẽ tự động xóa file key sau 1.5 giờ\n"
                        f"Đã kích hoạt thành công![/]",
                        border_style="#ff9ecb",
                        box=box.DOUBLE,
                        title="[#ff9ecb]LICENSE[/]",
                        title_align="center",
                        width=45
                    ))
                # Key admin phonganh
                elif user_key == self.admin_key_phonganh:
                    console.print(Panel(
                        f"[#00ff9c]✓ KÍCH HOẠT KEY ADMIN THÀNH CÔNG![/]\n\n"
                        f"[#ffffff]Key: {user_key}\n"
                        f"Hạn sử dụng: [bold]VĨNH VIỄN[/]\n"
                        f"Chế độ: Admin - Không giới hạn\n"
                        f"Không check device, không giới hạn số máy\n"
                        f"Đã kích hoạt thành công![/]",
                        border_style="#a78bfa",
                        box=box.DOUBLE,
                        title="[#ff9ecb]LICENSE[/]",
                        title_align="center", 
                        width=50,
                        height=10
                    ))
                else:
                    is_valid, minutes_left, msg = self.check_expiry(result.get("expiry", ""))
                    console.print(Panel(
                        f"[#00ff9c]✓ KÍCH HOẠT THÀNH CÔNG![/]\n\n"
                        f"[#ffffff]Key: {user_key}\n"
                        f"Hạn sử dụng: {result.get('expiry', 'N/A')}\n"
                        f"[#00ffff] {msg}[/]\n", 
                        border_style="#a78bfa",
                        box=box.DOUBLE,
                        title="[#ff9ecb]LICENSE[/]",
                        title_align="center"
                    ))
                time.sleep(2)
                return True
            else:
                console.print("[#ff4d6d]  Không thể lưu key![/]")
                time.sleep(1)
                continue

    def is_license_valid(self):
        if not self._is_valid:
            return False
        if self._key_data:
            expiry_str = self._key_data.get("expiry")
            if expiry_str:
                is_valid, _, _ = self.check_expiry(expiry_str)
                return is_valid
        return self._is_valid


# ===== CÁC HÀM HIỂN THỊ =====
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def banner():
    os.system('clear' if os.name == 'posix' else 'cls')
    banner_text = """
      \033[38;2;153;51;255m▄▄▄█████▓ █    ██   ██████    ▄▄▄█████▓ ▒█████   ▒█████   ██▓
      \033[38;2;170;70;255m▓  ██▒ ▓▒ ██  ▓██▒▒██    ▒    ▓  ██▒ ▓▒▒██▒  ██▒▒██▒  ██▒▓██▒
      \033[38;2;190;90;255m▒ ▓██░ ▒░▓██  ▒██░░ ▓██▄      ▒ ▓██░ ▒░▒██░  ██▒▒██░  ██▒▒██░
      \033[38;2;210;110;240m░ ▓██▓ ░ ▓▓█  ░██░  ▒   ██▒   ░ ▓██▓ ░ ▒██   ██░▒██   ██░▒██░
      \033[38;2;230;130;220m  ▒██▒ ░ ▒▒█████▓ ▒██████▒▒     ▒██▒ ░ ░ ████▓▒░░ ████▓▒░░██████▒
      \033[38;2;240;150;200m  ▒ ░░   ░▒▓▒ ▒ ▒ ▒ ▒▓▒ ▒ ░     ▒ ░░   ░ ▒░▒░▒░ ░ ▒░▒░▒░ ░ ▒░▓  ░
      \033[38;2;200;200;255m    ░    ░░▒░ ░ ░ ░ ░▒  ░ ░       ░      ░ ▒ ▒░   ░ ▒ ▒░ ░ ░ ▒  ░
      \033[38;2;150;230;255m  ░       ░░░ ░ ░ ░  ░  ░       ░      ░ ░ ░ ▒  ░ ░ ░ ▒    ░ ░
      \033[38;2;120;255;230m            ░           ░                  ░ ░      ░ ░      ░  ░
\033[0m
\033[38;2;255;200;140m[</>] \033[38;2;200;160;255mADMIN:\033[38;2;255;235;180m NHƯ ANH ĐÃ THẤY EM   \033[38;2;255;220;160mPhiên Bản: \033[38;2;120;255;220mv3.14
\033[38;2;255;200;140m[</>] \033[38;2;200;160;255mNhóm Telegram: \033[38;2;120;255;220mhttps://t.me/se_meo_bao_an
\033[38;2;190;235;210m───────────────────────────────────────────────────────────────────────\033[0m
"""
    print(banner_text)


def get_ip_info():
    try:
        # Lấy IP bằng ipify
        response = requests.get("https://api.ipify.org?format=json", timeout=6)
        data = response.json()
        ip_address = data.get('ip')
        
        if not ip_address:
            ip_address = "Không xác định"
            console.print(Text("IP: ", style="#a78bfa") + Text(f"{ip_address} ", style="#ffffff"))
            return
            
        # Lấy thông tin vị trí từ ip-api.com
        try:
            location_response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=6)
            location_data = location_response.json()
            
            ip_text = Text()
            ip_text.append("IP: ", style="#a78bfa")
            ip_text.append(f"{ip_address} ", style="#ffffff")
            
            if location_data.get('status') == 'success':
                city = location_data.get('city')
                country_code = location_data.get('countryCode')
                
                if city:
                    ip_text.append("| TP: ", style="#ff9ecb")
                    ip_text.append(f"{city} ", style="#ffffff")
                else:
                    ip_text.append("| TP: ", style="#ff9ecb")
                    ip_text.append("Không rõ ", style="#ffffff")
                    
                if country_code:
                    ip_text.append("| QG: ", style="#00ffff")
                    ip_text.append(f"{country_code}", style="#ffffff")
                else:
                    ip_text.append("| QG: ", style="#00ffff")
                    ip_text.append("Không rõ", style="#ffffff")
            else:
                ip_text.append("| TP: ", style="#ff9ecb")
                ip_text.append("Không rõ ", style="#ffffff")
                ip_text.append("| QG: ", style="#00ffff")
                ip_text.append("Không rõ", style="#ffffff")
                
            console.print(ip_text)
            
        except Exception:
            # Fallback khi lỗi lấy vị trí
            ip_text = Text()
            ip_text.append("IP: ", style="#a78bfa")
            ip_text.append(f"{ip_address} ", style="#ffffff")
            ip_text.append("| TP: ", style="#ff9ecb")
            ip_text.append("Không rõ ", style="#ffffff")
            ip_text.append("| QG: ", style="#00ffff")
            ip_text.append("Không rõ", style="#ffffff")
            console.print(ip_text)
            
    except Exception:
        console.print("[#ff4d6d]Lỗi lấy IP: Mạng không ổn định hoặc bị chặn.[/]")


def create_menu_table():
    table = Table(
        title="[#ff9ecb]MENU TOOL[/]",
        border_style="#a78bfa",
        box=box.HEAVY_EDGE,
        show_header=False,
        show_lines=True,
        padding=(0, 2)
    )
    table.add_column("STT", justify="center", style="#00ffff", width=5)
    table.add_column("CHỨC NĂNG", justify="left", width=60)
    modes = [
        ("1", "[#ffffff]Auto Golike [#ff9ecb]Instagram[/] [#a5f3fc] request [#ffffff][[bold #38bdf8] Mobile + PC[#ffffff] ][/]"),
        ("2", "[#ffffff]Auto Golike [bold #00ffff]TikTok[/] [#ffd54f]ADB[/] [#ffffff]full job[/] [bold #ff9ecb]Like[/] [bold #00ff9c]Follow[/] [bold #38bdf8]Cmt[/] [bold #a78bfa]Favorites[/]"),
        ("3", "[#ffffff]Auto Golike [bold #38bdf8]Instagram[/] [bold #ff9ecb]selenium TERMUX[/] [bold #38bdf8] ưu [/] [bold #a78bfa]tiên[/][/] [bold #00ff9c] chạy termux"),
        ("4", "[#ffffff]Auto Golike [bold #00ffff]Instagram[/] [#ffd54f]selenium PC[/] [#ffffff][ ưu tiên chạy[/] [bold #ff9ecb]Windows[#ffffff] ][/] [/]"), 
        ("5", "[#ffffff]Tool 5 - Đang phát triển[/]"),
        ("6", "[#ffffff]Tool 6 - Đang phát triển[/]")
    ]
    for stt, name in modes:
        table.add_row(stt, name)
    return table


def create_footer():
    return Panel(
        "[#888888]Nhập số để chọn tool (0 thoát) - [#00ffff]https://t.me/se_meo_bao_an[/]",
        border_style="#a78bfa",
        box=box.ROUNDED,
        width=70,
        height=3, 
    )


def loveTCP(so=5):
    for i in range(so):
        time.sleep(0.002)
    console.print()


def fix_syntax_errors(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        lines = content.splitlines()
        fixed_lines = []
        for line in lines:
            if line.strip().startswith('print ') and not line.strip().startswith('print('):
                line = line.replace('print ', 'print(', 1)
                if not line.rstrip().endswith(')'):
                    line = line.rstrip() + ')'
            if 'except ' in line and ', ' in line and ' as ' not in line:
                line = line.replace(', ', ' as ', 1)
            if '<>' in line:
                line = line.replace('<>', '!=')
            fixed_lines.append(line)
        fixed_content = '\n'.join(fixed_lines)
        try:
            ast.parse(fixed_content)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            return True, "Đã fix syntax thành công"
        except SyntaxError as e:
            return False, f"Không thể tự động fix: {e}"
    except Exception as e:
        return False, f"Lỗi khi fix: {e}"


def run_from_raw(url):
    tmp_path = None
    try:
        clear_screen()
        console.print("[#00ffff] ĐANG TẢI TOOL...[/]")
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        clear_screen()
        console.print("[#ff9ecb] ĐANG CHẠY TOOL...[/]")
        time.sleep(1)
        clear_screen()
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".py") as tmp:
            tmp.write(res.content)
            tmp.flush()
            tmp_path = tmp.name
        try:
            with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            ast.parse(content)
            runpy.run_path(tmp_path, run_name="__main__")
        except SyntaxError as e:
            console.print(f"[#ffab40] Phát hiện lỗi syntax: {e.msg} tại dòng {e.lineno}[/]")
            console.print("[#00ffff] Đang thử tự động fix...[/]")
            success, msg = fix_syntax_errors(tmp_path)
            if success:
                console.print(f"[#00ff9c] {msg}[/]")
                console.print("[#ff9ecb] Đang chạy lại tool...[/]")
                time.sleep(2)
                clear_screen()
                try:
                    runpy.run_path(tmp_path, run_name="__main__")
                except Exception as e2:
                    console.print(f"[#ff4d6d] Vẫn còn lỗi: {e2}[/]")
                    console.print("[#888888]Enter để tiếp tục...[/]", end="")
                    input()
            else:
                console.print(f"[#ff4d6d] {msg}[/]")
                console.print("[#888888]Enter để tiếp tục...[/]", end="")
                input()
        except Exception as e:
            console.print(f"[#ff4d6d] Lỗi khi chạy tool: {e}[/]")
            console.print("[#888888]Enter để tiếp tục...[/]", end="")
            input()
    except requests.exceptions.RequestException as e:
        console.print(f"[#ff4d6d] Lỗi tải tool: {e}[/]")
        console.print("[#888888]Enter để tiếp tục...[/]", end="")
        input()
    except Exception as e:
        console.print(f"[#ff4d6d] Lỗi không xác định: {e}[/]")
        console.print("[#888888]Enter để tiếp tục...[/]", end="")
        input()
    finally:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except:
            pass


def check_license_and_run():
    license_manager = LicenseManager()
    success = license_manager.check_and_activate()
    if success:
        license_manager.start_continuous_check()
    return success, license_manager


# ===== DANH SÁCH LINK TOOL =====
RAW_LINKS = {
    "1": "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/main/ig.py",
    "2": "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/main/ttnew.py",
    "3": "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/refs/heads/main/igchrome.py",
    "4": "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/refs/heads/main/igpc.py",
    "5": "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/main/AdbPinterest.py",
    "6": "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/main/tool6.py",
    "7": "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/main/tool7.py",
    "8": "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/main/tool8.py",
    "9": "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/main/tool9.py",
    "10": "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/main/tool10.py"
}


# ===== MAIN =====
if __name__ == "__main__":
    setup_prompt()
    
    while True:
        success, license_manager = check_license_and_run()
        
        if not success:
            sys.exit(1)
        
        while True:
            banner()
            get_ip_info()
            
            if license_manager:
                remaining_text = license_manager.get_remaining_display()
                if remaining_text:
                    console.print(remaining_text)
            
            loveTCP(5)
            console.print(create_menu_table())
            console.print(create_footer())

            console.print("[#ff9ecb]➤[/] [bold #ffffff]Chọn[/] ([#00ffff]0 để thoát[/]): [#ffffff]", end="")
            choice = input().strip()

            if choice in ("0", "q", "quit", "exit"):
                console.print("[#888888] Tạm biệt![/]")
                if license_manager:
                    license_manager.stop_continuous_check()
                sys.exit(0)

            if choice in RAW_LINKS:
                run_from_raw(RAW_LINKS[choice])
                clear_screen()
                console.print("[#888888]Enter để về menu...[/]", end="")
                input()
                # Sau khi chạy tool xong, kiểm tra lại license (có thể key 20032007 đã hết hạn)
                break
            else:
                console.print("[#ff4d6d] Số không hợp lệ![/]")
                time.sleep(1)
