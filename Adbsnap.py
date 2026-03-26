#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import json
import time
import datetime
import requests
import urllib.request
import urllib.parse
from xml.dom import minidom
from http.client import HTTPResponse
from typing import Tuple, Optional, List, Dict, Any
import subprocess
import re

# --- ADB / UIAutomator2 support ---
try:
    import uiautomator2 as u2
    U2_AVAILABLE = True
except Exception:
    U2_AVAILABLE = False

# Global device handle (uiautomator2) or None
DEVICE = None
DEVICE_SERIAL = None  # Thêm biến lưu serial hiện tại

# Thiết lập timezone (mô phỏng PHP)
os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
if hasattr(time, 'tzset'):
    time.tzset()

# -------- Helper: adb / device init --------

def init_device(adb_serial: Optional[str] = None) -> Optional[object]:
    """Kết nối uiautomator2 (nếu có), nếu không chỉ xác nhận adb.
    Trả về DEVICE nếu connect thành công (uiautomator2), ngược lại None.
    """
    global DEVICE, DEVICE_SERIAL
    DEVICE_SERIAL = adb_serial  # Lưu serial để dùng cho ADB commands
    
    if U2_AVAILABLE:
        try:
            if adb_serial:
                DEVICE = u2.connect(adb_serial)
            else:
                DEVICE = u2.connect()  # auto chọn thiết bị
                # Lấy serial từ device đã connect
                if hasattr(DEVICE, 'serial'):
                    DEVICE_SERIAL = DEVICE.serial
                else:
                    # Nếu không lấy được serial, thử lấy từ adb devices
                    try:
                        proc = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
                        lines = proc.stdout.splitlines()
                        for line in lines:
                            if '\tdevice' in line:
                                DEVICE_SERIAL = line.split('\t')[0].strip()
                                break
                    except Exception:
                        pass
            # kiểm tra service alive
            try:
                svc = getattr(DEVICE, "service", None)
                if svc:
                    if DEVICE.service("uiautomator").alive:
                        print(f"[+] uiautomator2: Connected to device {DEVICE_SERIAL}.")
                        return DEVICE
                # một số build không expose .service - chấp nhận best-effort
                print(f"[+] uiautomator2: Connected (best-effort) to device {DEVICE_SERIAL}.")
                return DEVICE
            except Exception:
                print(f"[+] uiautomator2: Connected (best-effort) to device {DEVICE_SERIAL}.")
                return DEVICE
        except Exception as e:
            print(f"[!] uiautomator2 connect failed: {e}")
            DEVICE = None
            DEVICE_SERIAL = None

    # fallback: check adb existence
    try:
        subprocess.run(['adb', 'devices'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[i] adb available. Will use adb shell as fallback.")
    except Exception:
        print("[!] adb not available or not in PATH.")
    return None

def adb_shell(cmd: List[str], check: bool = False, serial: str = None) -> subprocess.CompletedProcess:
    """Chạy adb shell command với serial binding, trả về CompletedProcess."""
    if serial:
        full = ['adb', '-s', serial, 'shell'] + cmd
    elif DEVICE_SERIAL:
        full = ['adb', '-s', DEVICE_SERIAL, 'shell'] + cmd
    else:
        full = ['adb', 'shell'] + cmd
    return subprocess.run(full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)

def get_screen_size(serial: str = None) -> Tuple[int, int]:
    """Lấy kích thước màn hình thiết bị qua adb wm size với serial binding."""
    try:
        if serial:
            out = subprocess.run(['adb', '-s', serial, 'shell', 'wm', 'size'], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        elif DEVICE_SERIAL:
            out = subprocess.run(['adb', '-s', DEVICE_SERIAL, 'shell', 'wm', 'size'], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        else:
            out = subprocess.run(['adb', 'shell', 'wm', 'size'], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        
        if out.stdout:
            m = re.search(r'Physical size:\s*(\d+)x(\d+)', out.stdout)
            if m:
                return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    # fallback common
    return 1080, 1920

# =========================================================================
# FIXED V2: Hàm mở link ép buộc qua App (Deep Link snapchat://)
# =========================================================================

def open_link_on_device(link: str, package: Optional[str] = None, serial: str = None) -> bool:
    """
    Mở link trên device bằng intent với serial binding.
    FIX: Tự động convert link HTTPS sang URI scheme (snapchat://) để trình duyệt KHÔNG THỂ mở được.
    """
    if not link:
        print("[!] Link rỗng, bỏ qua!")
        return False
        
    # Nếu không truyền package, mặc định dùng snapchat
    target_pkg = package if package else "com.snapchat.android"

    # --- LOGIC FIX: Convert HTTPS -> URI Scheme (Deep Link) ---
    # Link gốc: https://www.snapchat.com/add/username?share_id=...
    # Convert thành: snapchat://add/username
    final_link = link
    try:
        if "snapchat.com/add/" in link:
            # Tách lấy phần username
            parts = link.split("snapchat.com/add/")
            if len(parts) > 1:
                user_part = parts[1]
                # Bỏ các tham số query (?share_id=...) để tránh lỗi
                if "?" in user_part:
                    user_part = user_part.split("?")[0]
                # Tạo deep link
                final_link = f"snapchat://add/{user_part}"
                # Debug nhẹ để biết đã convert
                # print(f"[i] Converted to DeepLink: {final_link}")
    except Exception as e:
        print(f"[!] Lỗi convert deep link: {e}, dùng link gốc.")
        final_link = link

    # --- THỰC THI LỆNH ---
    
    # 1. Ưu tiên dùng Uiautomator2 (kết nối sẵn)
    if DEVICE and (serial is None or serial == DEVICE_SERIAL):
        try:
            # Dùng quote kép bao quanh link để an toàn
            # Lệnh: am start -a android.intent.action.VIEW -d "snapchat://..." -p com.snapchat.android
            cmd = f'am start -a android.intent.action.VIEW -d "{final_link}" -p {target_pkg}'
            
            DEVICE.shell(cmd)
            # Tăng thời gian chờ lên xíu để app kịp switch từ background lên
            time.sleep(2.5) 
            return True
        except Exception as e:
            print(f"[!] Lỗi mở link qua u2 (thử fallback ADB): {e}")

    # 2. Fallback dùng ADB thuần (subprocess) với serial binding
    try:
        # Build command với serial binding
        if serial:
            cmd_args = ['adb', '-s', serial, 'shell', 'am', 'start', 
                       '-a', 'android.intent.action.VIEW', 
                       '-d', final_link, 
                       '-p', target_pkg]
        elif DEVICE_SERIAL:
            cmd_args = ['adb', '-s', DEVICE_SERIAL, 'shell', 'am', 'start', 
                       '-a', 'android.intent.action.VIEW', 
                       '-d', final_link, 
                       '-p', target_pkg]
        else:
            cmd_args = ['adb', 'shell', 'am', 'start', 
                       '-a', 'android.intent.action.VIEW', 
                       '-d', final_link, 
                       '-p', target_pkg]
        
        res = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Check output xem có lỗi không
        combined = (res.stdout or "") + (res.stderr or "")
        if "Error" in combined or "Exception" in combined:
            # Nếu deep link fail (hiếm gặp), thử lại bằng link gốc HTTPS
            if final_link != link:
                print("[!] DeepLink fail, thử lại bằng link gốc...")
                cmd_args[7 if serial or DEVICE_SERIAL else 5] = link
                subprocess.run(cmd_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2.0)
                return True
                
            print(f"[!] ADB mở link thất bại: {combined}")
            return False
            
        time.sleep(2.0)
        return True
    except Exception as e:
        print(f"[!] open_link_on_device error: {e}")
        return False

def adb_tap(x: int, y: int, serial: str = None) -> bool:
    """Tap bằng adb input tap với serial binding"""
    try:
        adb_shell(['input', 'tap', str(x), str(y)], serial=serial)
        return True
    except Exception as e:
        print(f"[!] adb_tap failed: {e}")
        return False

# --- MOD: Hàm tap theo tọa độ dùng chung cho u2/adb với serial binding ---

def tap_xy(device, x: int, y: int, serial: str = None) -> bool:
    """Chạm tại tọa độ (x,y). Dùng uiautomator2 nếu có, ngược lại dùng adb với serial binding. Trả True nếu gọi tap thành công."""
    try:
        if device:
            try:
                # một số u2 có click(x,y); một số có tap
                if hasattr(device, "click"):
                    device.click(x, y)
                elif hasattr(device, "tap"):
                    device.tap(x, y)
                else:
                    adb_tap(x, y, serial)
            except Exception:
                adb_tap(x, y, serial)
        else:
            adb_tap(x, y, serial)
        return True
    except Exception as e:
        print(f"[!] tap_xy error: {e}")
        return False

# -------- Device manager (ADB) với hiển thị tên thiết bị --------

def adb_list_devices() -> List[Dict[str, str]]:
    """Lấy danh sách thiết bị từ 'adb devices' 
    Trả về danh sách dict: {"name": "Tên thiết bị", "id": serial, "model": "Model thiết bị"}"""
    devices = []
    try:
        # Lấy danh sách devices
        proc = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        lines = proc.stdout.splitlines()
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            if "\tdevice" in line:
                serial = line.split("\t")[0].strip()
                
                # Lấy thông tin chi tiết thiết bị
                device_name = "Android"  # Mặc định
                device_model = "Unknown"  # Mặc định
                
                try:
                    # Lấy model từ adb shell getprop
                    model_proc = subprocess.run(["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
                    if model_proc.stdout:
                        device_model = model_proc.stdout.strip()
                    
                    # Lấy tên thiết bị (có thể là model hoặc brand+model)
                    brand_proc = subprocess.run(["adb", "-s", serial, "shell", "getprop", "ro.product.brand"],
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
                    if brand_proc.stdout:
                        brand = brand_proc.stdout.strip()
                        device_name = f"{brand} {device_model}" if brand else device_model
                    else:
                        device_name = device_model
                        
                    # Nếu tên quá dài, cắt bớt
                    if len(device_name) > 25:
                        device_name = device_name[:22] + "..."
                        
                except Exception:
                    # Nếu không lấy được thông tin, dùng serial làm tên
                    device_name = f"Device_{serial[:8]}"
                
                devices.append({
                    "name": device_name, 
                    "id": serial, 
                    "model": device_model
                })
    except Exception as e:
        print(f"[!] Lỗi khi lấy danh sách thiết bị: {e}")
    return devices

def adb_add_device(ip_port: str, pin: str = "") -> bool:
    """
    Thêm thiết bị qua WiFi ADB (adb pair + adb connect).
    """
    try:
        ip_port = ip_port.strip()
        if not ip_port:
            return False

        # Nếu có PIN -> validate
        if pin:
            pin = pin.strip()
            if not re.fullmatch(r'\d{4,8}', pin):
                print("[!] PIN không hợp lệ. PIN phải là 4-8 chữ số (thường 6).")
                return False

            out_combined = ""

            # 1) Thử truyền pin trực tiếp
            try:
                res = subprocess.run(["adb", "pair", ip_port, pin],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                out_combined = (res.stdout or "") + (res.stderr or "")
            except Exception:
                out_combined = ""

            # Nếu output không rõ ràng -> fallback interactive
            if not out_combined or ("pair" not in out_combined.lower() and "succeed" not in out_combined.lower() and "paired" not in out_combined.lower()):
                try:
                    p = subprocess.Popen(["adb", "pair", ip_port],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    try:
                        out, err = p.communicate(pin + "\n", timeout=20)
                        out_combined = (out or "") + (err or "")
                    except Exception:
                        try:
                            p.kill()
                        except Exception:
                            pass
                        out_combined = ""
                except Exception:
                    out_combined = ""

            # Sau pair cố gắng connect
            try:
                res2 = subprocess.run(["adb", "connect", ip_port], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
                out2 = (res2.stdout or "") + (res2.stderr or "")
            except Exception:
                out2 = ""

            out_all = (out_combined or "") + (out2 or "")
            out_all_l = out_all.lower()

            if "connected" in out_all_l or "already" in out_all_l or "connected to" in out_all_l:
                return True
            if "success" in out_all_l and ("pair" in out_all_l or "paired" in out_all_l):
                try:
                    res3 = subprocess.run(["adb", "connect", ip_port], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
                    out3 = (res3.stdout or "") + (res3.stderr or "")
                    if "connected" in out3.lower() or "already" in out3.lower():
                        return True
                except Exception:
                    pass
            return False

        else:
            # Không có PIN: chỉ connect trực tiếp
            try:
                res = subprocess.run(["adb", "connect", ip_port], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
                out = (res.stdout or "") + (res.stderr or "")
                out_l = out.lower()
                return ("connected" in out_l) or ("already" in out_l)
            except Exception:
                return False

    except Exception as e:
        print(f"[!] adb_add_device unexpected error: {e}")
        return False

def device_manager_select() -> Optional[str]:
    while True:
        clear_screen()
        banner()
        print("\033[1;97m═══════════════════════════════════════════════════════════════")
        print("\033[1;33mSTT ║ NAME DEVICES                ║ ID DEVICES")
        print("\033[1;97m═══════════════════════════════════════════════════════════════")

        devices = adb_list_devices()
        if not devices:
            print("\033[1;31m[!] Không tìm thấy thiết bị ADB nào.")
        for i, d in enumerate(devices, 1):
            device_name = d['name']
            device_id = d['id']
            # Hiển thị tên thiết bị thay vì chỉ "Android"
            print(f"\033[1;36m[{i:2}] ║ {device_name:<28} ║ {device_id}")
        print("\033[1;97m═══════════════════════════════════════════════════════════════")
        print("\033[1;32m[add] ✈ Nhập add để thêm thiết bị (ADB)")
        print("\033[1;32m[refresh] ✈ Nhập refresh để làm mới danh sách")
        print("\033[1;97m═══════════════════════════════════════════════════════════════")

        choice = input("\033[1;36m[❣] ✈ Nhập STT thiết bị cần chạy (1 | all | add | refresh | none): ").strip().lower()

        if choice == "add":
            ip = input("\033[1;36m[</>] ✈ Nhập IP:PORT (VD 192.168.1.5:5555): ").strip()
            pin = input("\033[1;36m[❣] ✈ Nhập mã PIN 6 số (bỏ trống nếu đã xác minh): ").strip()
            pin = pin if pin else ""
            if pin and not re.fullmatch(r'\d{4,8}', pin):
                print("\033[1;31m[✖] PIN không hợp lệ. Vui lòng nhập 4-8 chữ số (thường 6).")
                time.sleep(1.2)
                continue
            ok = adb_add_device(ip, pin)
            print("\033[1;32m[✔] Đã thêm thiết bị thành công!" if ok else "\033[1;31m[✖] Thêm thiết bị thất bại!")
            time.sleep(2)
            continue
        elif choice == "refresh":
            continue
        elif choice == "none":
            return None
        elif choice == "all" and devices:
            # Trả về serial của thiết bị đầu tiên
            return devices[0]["id"]
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx]["id"]
        print("\033[1;31m[✖] Lựa chọn không hợp lệ! Thử lại...")
        time.sleep(1.5)

# -------- UI interaction helpers (uiautomator2 best-effort) --------

def try_find_and_click(device, texts: List[str], descs: List[str] = None, classes: List[str] = None, timeout: int = 6) -> bool:
    """Thử tìm element theo text/description/class với uiautomator2 và click. Trả True nếu click thành công."""
    if device is None:
        return False
    descs = descs or []
    classes = classes or []
    end = time.time() + timeout
    try:
        while time.time() < end:
            # theo text exact hoặc contains
            for t in texts:
                try:
                    el = device(text=t)
                    if getattr(el, "exists", False):
                        el.click()
                        return True
                    el2 = device(textContains=t)
                    if getattr(el2, "exists", False):
                        el2.click()
                        return True
                except Exception:
                    pass
            # theo description
            for d in descs:
                try:
                    el = device(description=d)
                    if getattr(el, "exists", False):
                        el.click()
                        return True
                    el2 = device(descriptionContains=d)
                    if getattr(el2, "exists", False):
                        el2.click()
                        return True
                except Exception:
                    pass
            # theo className
            for cls in classes:
                try:
                    els = device(className=cls)
                    if getattr(els, "exists", False):
                        try:
                            els.click()
                            return True
                        except Exception:
                            try:
                                # thử các instance nếu list-like
                                for i in range(6):
                                    try:
                                        els[i].click()
                                        return True
                                    except Exception:
                                        continue
                            except Exception:
                                pass
                except Exception:
                    pass
            time.sleep(0.4)
    except Exception as e:
        print(f"[!] try_find_and_click error: {e}")
    return False

def find_avatar_bounds(device) -> Optional[Dict[str, int]]:
    """Cố gắng tìm phần tử avatar. Trả về dict bounds nếu tìm được."""
    if device is None:
        return None
    try:
        # thử bằng resourceId patterns
        for rid_pattern in ['avatar', 'profile', 'user_avatar', 'iv_avatar']:
            try:
                el = device(resourceIdMatches=f".*{rid_pattern}.*")
                if getattr(el, "exists", False):
                    info = el.info
                    if info and 'bounds' in info:
                        return info['bounds']
            except Exception:
                pass
        # thử bằng descriptionContains
        for clue in ['Profile', 'profile', 'avatar', 'photo']:
            try:
                el = device(descriptionContains=clue)
                if getattr(el, "exists", False):
                    info = el.info
                    if info and 'bounds' in info:
                        return info['bounds']
            except Exception:
                pass
    except Exception:
        pass
    return None

# -------- New: check snapchat link error (uiautomator2) --------

def check_snapchat_link_error(device, timeout: int = 5) -> bool:
    """Check lỗi Snapchat: 'Rất tiếc! Có vẻ link này không hoạt động' Trả về True nếu phát hiện lỗi."""
    if device is None:
        return False
    # Một số biến thể tiếng Việt / tiếng Anh
    error_texts = [
        "Rất tiếc",
        "Có vẻ link này không hoạt động",
        "link này không hoạt động",
        "This link isn't working",
        "This link is not working",
        "Sorry, this link isn't working",
    ]
    end = time.time() + timeout
    try:
        while time.time() < end:
            for txt in error_texts:
                try:
                    el = device(text=txt)
                    if getattr(el, "exists", False):
                        return True
                    el2 = device(textContains=txt)
                    if getattr(el2, "exists", False):
                        return True
                    el3 = device(description=txt)
                    if getattr(el3, "exists", False):
                        return True
                    el4 = device(descriptionContains=txt)
                    if getattr(el4, "exists", False):
                        return True
                except Exception:
                    pass
            time.sleep(0.3)
    except Exception:
        return False
    return False

# NEW: Check popup lỗi "Ôi! Có lỗi xảy ra..." - CẢI TIẾN

def check_generic_popup_error(device, timeout: int = 4) -> bool:
    """Check popup lỗi: 'Ôi! Có lỗi xảy ra. Vui lòng thử lại!' hoặc nút 'Ok' Trả về True nếu phát hiện lỗi."""
    if device is None:
        return False
    # Danh sách các từ khóa xuất hiện trong popup lỗi - MỞ RỘNG
    error_texts = [
        "Ôi!", "Có lỗi xảy ra", "Vui lòng thử lại",
        "Oops!", "Something went wrong", "Please try again",
        "Ok", "OK", "Okay",  # Nút ok thường đi kèm
        "Thử lại", "Try again", "Retry",
        "Lỗi", "Error", "Failed",
        "Đã xảy ra lỗi", "An error occurred",
        "Không thể hoàn thành", "Could not complete",
        "Thất bại", "Failure"
    ]
    end = time.time() + timeout
    try:
        while time.time() < end:
            for txt in error_texts:
                try:
                    if getattr(device(text=txt), "exists", False):
                        print(f"\033[1;31m[!] Phát hiện popup lỗi: '{txt}'")
                        return True
                    if getattr(device(textContains=txt), "exists", False):
                        print(f"\033[1;31m[!] Phát hiện popup lỗi (contains): '{txt}'")
                        return True
                    if getattr(device(description=txt), "exists", False):
                        return True
                    if getattr(device(descriptionContains=txt), "exists", False):
                        return True
                except Exception:
                    pass
            time.sleep(0.3)
    except Exception:
        pass
    return False

# NEW: Hàm xử lý popup lỗi khi phát hiện
def handle_error_popup(device, serial: str = None) -> bool:
    """Xử lý popup lỗi 'Ôi! Có lỗi xảy ra' bằng cách bấm nút OK/Thử lại hoặc back."""
    if device is None:
        return False
    
    print("\033[1;33m[!] Đang xử lý popup lỗi...")
    
    try:
        # Thử tìm và bấm các nút thông thường trong popup lỗi
        ok_buttons = ["OK", "Ok", "Okay", "Đồng ý", "Xong", "Close", "Đóng", "Thử lại", "Try again", "Retry"]
        
        for btn_text in ok_buttons:
            try:
                if getattr(device(text=btn_text), "exists", False):
                    device(text=btn_text).click()
                    print(f"\033[1;32m[✔] Đã bấm nút '{btn_text}' để đóng popup lỗi")
                    time.sleep(1)
                    return True
                if getattr(device(textContains=btn_text), "exists", False):
                    device(textContains=btn_text).click()
                    print(f"\033[1;32m[✔] Đã bấm nút chứa '{btn_text}' để đóng popup lỗi")
                    time.sleep(1)
                    return True
            except Exception:
                pass
        
        # Nếu không tìm thấy nút, thử bấm back
        print("\033[1;33m[!] Không tìm thấy nút OK, thử bấm nút back...")
        if serial:
            subprocess.run(['adb', '-s', serial, 'shell', 'input', 'keyevent', 'KEYCODE_BACK'], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif DEVICE_SERIAL:
            subprocess.run(['adb', '-s', DEVICE_SERIAL, 'shell', 'input', 'keyevent', 'KEYCODE_BACK'], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            adb_shell(['input', 'keyevent', 'KEYCODE_BACK'])
        
        time.sleep(1)
        return True
        
    except Exception as e:
        print(f"\033[1;31m[✖] Lỗi khi xử lý popup lỗi: {e}")
        return False

# -------- New: verify follow/like happened (tiếng Việt ưu tiên) --------

def verify_followed(device, timeout: int = 6) -> bool:
    """Verify trạng thái 'đã thêm' bằng các chuỗi tiếng Việt phổ biến. Trả True nếu phát hiện dấu hiệu đã follow/added."""
    if device is None:
        return False
    # Các mẫu tiếng Việt phổ biến trên UI Snapchat / biến thể nút
    candidates = [
        "Đã thêm", "Đã gửi", "Đã gửi lời mời", "Đã gửi yêu cầu", "Bạn đã thêm",
        "Đã kết bạn", "Đã gửi lời mời kết bạn", "Đã gửi lời mời kết bạn",
        "Đã kết nối", "Đang chờ", "+ Thêm", "Thêm", "Đã được thêm"
    ]
    end = time.time() + timeout
    while time.time() < end:
        try:
            # kiểm tra text/contains/description
            for txt in candidates:
                try:
                    if getattr(device(text=txt), "exists", False):
                        return True
                    if getattr(device(textContains=txt), "exists", False):
                        return True
                    if getattr(device(description=txt), "exists", False):
                        return True
                    if getattr(device(descriptionContains=txt), "exists", False):
                        return True
                except Exception:
                    pass

            # kiểm tra button resourceId có thể chứa 'add'/'them'/'friend' nhưng text hiển thị khác
            try:
                sel = device(resourceIdMatches=".*(add|them|friend|follow|add_friend|follow_btn).*")
                if getattr(sel, "exists", False):
                    try:
                        info = None
                        if hasattr(sel, "__len__") and len(sel) > 0:
                            try:
                                info = sel[0].info
                            except Exception:
                                info = sel.info
                        else:
                            info = sel.info
                        if isinstance(info, dict):
                            # nếu button không còn clickable hoặc enabled -> có thể đã thêm
                            if info.get("clickable") in [False, None] or info.get("enabled") is False:
                                return True
                            if info.get("selected") or info.get("checked"):
                                return True
                    except Exception:
                        pass
            except Exception:
                pass

        except Exception:
            pass
        time.sleep(0.35)
    return False

def verify_liked(device, timeout: int = 6) -> bool:
    """Kiểm tra UI có thay đổi trạng thái Like (heart filled / Liked). Trả True nếu phát hiện dấu hiệu đã like."""
    if device is None:
        return False
    candidates = ["Liked", "Thích", "Đã thích", "Bạn đã thích", "Favorited", "Like"]
    end = time.time() + timeout
    while time.time() < end:
        for txt in candidates:
            try:
                if getattr(device(text=txt), "exists", False):
                    return True
                if getattr(device(textContains=txt), "exists", False):
                    return True
                if getattr(device(description=txt), "exists", False):
                    return True
                if getattr(device(descriptionContains=txt), "exists", False):
                    return True
            except Exception:
                pass
        # thử resourceId generic
        try:
            el = device(resourceIdMatches=".*like.*")
            if getattr(el, "exists", False):
                try:
                    info = el.info
                    if info and (info.get("checked") or info.get("selected") or info.get("enabled")):
                        return True
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.35)
    return False

# -------- Auto actions: follow & like --------

def auto_tap_follow_button(device, max_wait=8, serial: str = None) -> bool:
    """Best-effort tìm và bấm nút Follow/Add Friend với serial binding"""
    possible_desc = ["Add Friend", "Theo dõi", "Add", "Follow", "Thêm bạn", "Add +", "+ Thêm", "Thêm"]
    if try_find_and_click(device, texts=[], descs=possible_desc, classes=['android.widget.ImageButton', 'android.widget.ImageView'], timeout=3):
        return True

    if try_find_and_click(device, texts=[], descs=[], classes=['android.widget.ImageButton', 'android.widget.ImageView', 'android.widget.ImageView'], timeout=2):
        return True

    bounds = find_avatar_bounds(device)
    if bounds:
        try:
            left = bounds.get('left')
            top = bounds.get('top')
            right = bounds.get('right')
            bottom = bounds.get('bottom')
            click_x = (left + right) // 2
            delta = max(30, (bottom - top) // 2)
            click_y = bottom + delta
            try:
                if device:
                    device.click(click_x, click_y)
                    return True
            except Exception:
                pass
            adb_tap(click_x, click_y, serial)
            return True
        except Exception:
            pass

    w, h = get_screen_size(serial)
    coords = [(w//2, h//4), (int(w*0.75), int(h*0.2)), (int(w*0.2), int(h*0.2))]
    for x, y in coords:
        try:
            if device:
                device.click(x, y)
            else:
                adb_tap(x, y, serial)
            time.sleep(0.5)
            return True
        except Exception:
            continue
    return False

def auto_tap_like_button(device, max_wait=8, serial: str = None) -> bool:
    """Best-effort tìm và bấm nút Like (trái tim) với serial binding"""
    possible_desc = ["Like", "Thích", "Favorite", "Heart"]
    if try_find_and_click(device, texts=[], descs=possible_desc, classes=['android.widget.ImageButton', 'android.widget.ImageView'], timeout=3):
        return True

    if try_find_and_click(device, texts=[], descs=[], classes=['android.widget.ImageView', 'android.widget.ImageButton'], timeout=2):
        return True

    w, h = get_screen_size(serial)
    coords = [(int(w*0.9), int(h*0.9)), (int(w*0.8), int(h*0.85)), (int(w*0.7), int(h*0.9))]
    for x, y in coords:
        try:
            if device:
                device.click(x, y)
            else:
                adb_tap(x, y, serial)
            time.sleep(0.5)
            return True
        except Exception:
            continue
    return False

# =========================================================================
# NEW: Hàm check nếu link mở trong trình duyệt thay vì Snapchat
# =========================================================================

def check_web_browser_opened(device, timeout: int = 5) -> bool:
    """Kiểm tra xem link có mở trong trình duyệt web không (thay vì Snapchat).
    Nhận diện qua các indicator đặc trưng của trình duyệt Chrome/WebView.
    """
    if device is None:
        return False
    
    # Các indicator của trình duyệt web
    browser_indicators = [
        # Chrome indicators
        "chrome", "Chrome", "Google", "address", "url", 
        # WebView/common browser elements
        "refresh", "reload", "forward", "back", "search",
        # Tiếng Việt
        "tìm kiếm", "địa chỉ", "trang web", "duyệt web"
    ]
    
    end = time.time() + timeout
    try:
        while time.time() < end:
            for indicator in browser_indicators:
                # Check by text
                try:
                    if getattr(device(textContains=indicator), "exists", False):
                        print(f"\033[1;33m[!] Phát hiện trình duyệt web: '{indicator}'")
                        return True
                except Exception:
                    pass
                
                # Check by description
                try:
                    if getattr(device(descriptionContains=indicator), "exists", False):
                        print(f"\033[1;33m[!] Phát hiện trình duyệt web (description): '{indicator}'")
                        return True
                except Exception:
                    pass
            
            # Check resourceId có chứa chrome/browser
            try:
                if getattr(device(resourceIdMatches=".*chrome.*"), "exists", False):
                    print(f"\033[1;33m[!] Phát hiện Chrome qua resourceId")
                    return True
                if getattr(device(resourceIdMatches=".*browser.*"), "exists", False):
                    print(f"\033[1;33m[!] Phát hiện Browser qua resourceId")
                    return True
            except Exception:
                pass
            
            time.sleep(0.3)
    except Exception as e:
        print(f"[!] Lỗi khi check trình duyệt: {e}")
    
    return False

# =========================================================================
# NEW: Hàm check nếu đang ở trong Snapchat (để xác định link mở thẳng vào app)
# =========================================================================

def check_snapchat_opened(device, timeout: int = 5) -> bool:
    """Kiểm tra xem có đang ở trong Snapchat không.
    Nhận diện qua các indicator đặc trưng của Snapchat.
    """
    if device is None:
        return False
    
    # Các indicator của Snapchat
    snapchat_indicators = [
        "Snapchat", "SNAP", "Snap", "chat", "Camera",
        "Stories", "Spotlight", "Map", "Chat", "Memories",
        # Tiếng Việt
        "Máy ảnh", "Câu chuyện", "Bản đồ", "Trò chuyện", "Kỷ niệm"
    ]
    
    end = time.time() + timeout
    try:
        while time.time() < end:
            for indicator in snapchat_indicators:
                # Check by text
                try:
                    if getattr(device(textContains=indicator), "exists", False):
                        print(f"\033[1;32m[✔] Phát hiện Snapchat: '{indicator}'")
                        return True
                except Exception:
                    pass
                
                # Check by description
                try:
                    if getattr(device(descriptionContains=indicator), "exists", False):
                        print(f"\033[1;32m[✔] Phát hiện Snapchat (description): '{indicator}'")
                        return True
                except Exception:
                    pass
            
            # Check resourceId có chứa snapchat
            try:
                if getattr(device(resourceIdMatches=".*snapchat.*"), "exists", False):
                    print(f"\033[1;32m[✔] Phát hiện Snapchat qua resourceId")
                    return True
            except Exception:
                pass
            
            time.sleep(0.3)
    except Exception as e:
        print(f"[!] Lỗi khi check Snapchat: {e}")
    
    return False

# =========================================================================
# NEW: Hàm xử lý khi link mở trong trình duyệt
# =========================================================================

def handle_web_browser_fallback(device, web_open_x: int, web_open_y: int, serial: str = None) -> bool:
    """Xử lý fallback khi link mở trong trình duyệt thay vì Snapchat.
    Thực hiện: 1. Đóng trình duyệt, 2. Mở Snapchat thủ công, 3. Thực hiện hành động.
    """
    print("\033[1;33m[!] Link đã mở trong trình duyệt, xử lý fallback...")
    
    try:
        # 1. Tap vào nút "Mở bằng Snapchat" nếu có (thường ở vị trí web_open_x, web_open_y)
        print(f"\033[1;36m[•] Tap vào nút 'Mở bằng Snapchat' tại ({web_open_x}, {web_open_y})")
        tap_xy(device, web_open_x, web_open_y, serial)
        time.sleep(2)
        
        # 2. Kiểm tra xem đã chuyển sang Snapchat chưa
        if check_snapchat_opened(device, timeout=3):
            print("\033[1;32m[✔] Đã chuyển sang Snapchat thành công!")
            return True
        else:
            # Nếu vẫn còn trong trình duyệt, thử đóng trình duyệt
            if check_web_browser_opened(device, timeout=2):
                print("\033[1;33m[!] Vẫn trong trình duyệt, thử đóng...")
                # Thử nút back hoặc close với serial binding
                if serial:
                    subprocess.run(['adb', '-s', serial, 'shell', 'input', 'keyevent', 'KEYCODE_BACK'], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1)
                    subprocess.run(['adb', '-s', serial, 'shell', 'input', 'keyevent', 'KEYCODE_BACK'], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif DEVICE_SERIAL:
                    subprocess.run(['adb', '-s', DEVICE_SERIAL, 'shell', 'input', 'keyevent', 'KEYCODE_BACK'], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1)
                    subprocess.run(['adb', '-s', DEVICE_SERIAL, 'shell', 'input', 'keyevent', 'KEYCODE_BACK'], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    adb_shell(['input', 'keyevent', 'KEYCODE_BACK'])
                    time.sleep(1)
                    adb_shell(['input', 'keyevent', 'KEYCODE_BACK'])
                time.sleep(1)
                
                # 3. Mở Snapchat thủ công với serial binding
                print("\033[1;36m[•] Mở Snapchat thủ công...")
                if serial:
                    subprocess.run(['adb', '-s', serial, 'shell', 'am', 'start', '-n', 'com.snapchat.android/.LandingPageActivity'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif DEVICE_SERIAL:
                    subprocess.run(['adb', '-s', DEVICE_SERIAL, 'shell', 'am', 'start', '-n', 'com.snapchat.android/.LandingPageActivity'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    adb_shell(['am', 'start', '-n', 'com.snapchat.android/.LandingPageActivity'])
                time.sleep(3)
                
                if check_snapchat_opened(device, timeout=3):
                    print("\033[1;32m[✔] Mở Snapchat thủ công thành công!")
                    return True
                else:
                    print("\033[1;31m[✖] Không thể mở Snapchat!")
                    return False
            else:
                # Không phát hiện trình duyệt, có thể đã chuyển app khác
                print("\033[1;33m[!] Không phát hiện trình duyệt, tiếp tục...")
                return True
                
    except Exception as e:
        print(f"\033[1;31m[✖] Lỗi khi xử lý web fallback: {e}")
        return False

# -------- Existing tool functions (API calls, UI, banner...) --------

def bes4(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Hàm lấy version và maintenance từ URL"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')
            version_match = re.search(r'<span[^>]*id=["\']version_keyADB["\'][^>]*>(.*?)', html)
            maintenance_match = re.search(r'<span[^>]*id=["\']maintenance_keyADB["\'][^>]*>(.*?)', html)
            version = version_match.group(1).strip() if version_match else None
            maintenance = maintenance_match.group(1).strip() if maintenance_match else None
            return version, maintenance
    except Exception:
        return None, None

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def banner():
    clear_screen()
    banner_text = """
\033[38;2;153;51;255m▄▄▄█████▓ █    ██   ██████    ▄▄▄█████▓ ▒█████   ▒█████   ██▓
\033[38;2;153;51;255m▓  ██▒ ▓▒ ██  ▓██▒▒██    ▒    ▓  ██▒ ▓▒▒██▒  ██▒▒██▒  ██▒▓██▒
\033[38;2;153;51;255m▒ ▓██░ ▒░▓██  ▒██░░ ▓██▄      ▒ ▓██░ ▒░▒██░  ██▒▒██░  ██▒▒██░
\033[38;2;153;51;255m░ ▓██▓ ░ ▓▓█  ░██░  ▒   ██▒   ░ ▓██▓ ░ ▒██   ██░▒██   ██░▒██░
\033[38;2;153;51;255m  ▒██▒ ░ ▒▒█████▓ ▒██████▒▒     ▒██▒ ░ ░ ████▓▒░░ ████▓▒░░██████▒
\033[38;2;153;51;255m  ▒ ░░   ░▒▓▒ ▒ ▒ ▒ ▒▓▒ ▒ ░     ▒ ░░   ░ ▒░▒░▒░ ░ ▒░▒░▒░ ░ ▒░▓  ░
\033[38;2;153;51;255m    ░    ░░▒░ ░ ░ ░ ░▒  ░ ░       ░      ░ ▒ ▒░   ░ ▒ ▒░ ░ ░ ▒  ░
\033[38;2;153;51;255m  ░       ░░░ ░ ░ ░  ░  ░       ░      ░ ░ ░ ▒  ░ ░ ░ ▒    ░ ░
\033[38;2;153;51;255m            ░           ░                  ░ ░      ░ ░      ░  ░
\033[0m
\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m\033[1;32mADMIN:\033[38;2;255;190;0m NHƯ ANH ĐÃ THẤY EM
\033[1;32mPhiên Bản: \033[38;2;255;190;0mV6 (Fix Multi-Device + Error Popup Handling)
\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m\033[1;32mNHóm Telegram: \033[38;2;255;190;0mhttps://t.me/se_meo_bao_an
\033[97m═══════════════════════════════════════════════════════════════════════
\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37mADB snapchat\033[1;31m    : \033[1;97m\033[1;32mTool Sử Dụng golike snapchat
\033[1;97m════════════════════════════════════════════════
"""
    for char in banner_text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.001)

def build_headers(headers_dict: Dict[str, str]) -> Dict[str, str]:
    return headers_dict

def chonacc(headers: Dict[str, str]) -> Dict[str, Any]:
    try:
        response = requests.get('https://gateway.golike.net/api/snapchat-account', headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        return {"status": 500, "error": str(e)}

def nhannv(account_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
    try:
        params = {'account_id': account_id, 'data': 'null'}
        response = requests.get('https://gateway.golike.net/api/advertising/publishers/snapchat/jobs', headers=headers, params=params, timeout=10)
        return response.json()
    except Exception as e:
        return {"status": 500, "error": str(e)}

def hoanthanh(ads_id: str, account_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
    try:
        json_data = {'ads_id': ads_id, 'account_id': account_id, 'async': True, 'data': None}
        response = requests.post('https://gateway.golike.net/api/advertising/publishers/snapchat/complete-jobs', headers=headers, json=json_data, timeout=10)
        return response.json()
    except Exception as e:
        return {"status": 500, "error": str(e)}

def baoloi(ads_id: str, object_id: str, account_id: str, loai: str, headers: Dict[str, str]) -> bool:
    try:
        json_data1 = {
            'description': 'Báo cáo hoàn thành thất bại',
            'users_advertising_id': ads_id,
            'type': 'ads',
            'provider': 'snapchat',
            'fb_id': account_id,
            'error_type': 6
        }
        requests.post('https://gateway.golike.net/api/report/send', headers=headers, json=json_data1, timeout=5)
        json_data = {'ads_id': ads_id, 'object_id': object_id, 'account_id': account_id, 'type': loai}
        response = requests.post('https://gateway.golike.net/api/advertising/publishers/snapchat/skip-jobs', headers=headers, json=json_data, timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def dsacc(chontk_snapchat: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    while True:
        try:
            if chontk_snapchat.get("status") != 200:
                print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;31mAuthorization hoặc T sai hãy nhập lại!!!")
                print("\033[1;97m════════════════════════════════════════════════")
                sys.exit(1)
            banner()
            print("\033[1;97m[\033[1;91m❣\033[1;97m]\033[1;97m Địa chỉ Ip\033[1;32m  : \033[1;32m☞\033[1;31m♔ \033[1;32m83.86.8888\033[1;31m♔ \033[1;97m☜")
            print("\033[1;97m════════════════════════════════════════════════")
            print("\033[1;97m[\033[1;91m❣\033[1;97m]\033[1;33m Danh sách acc Snapchat : ")
            print("\033[1;97m════════════════════════════════════════════════")
            account_map: Dict[str, Dict[str, str]] = {}
            for i, account in enumerate(chontk_snapchat.get("data", []), 1):
                username = account.get("snap_username", "N/A")
                account_id = account.get("id", "")
                account_map[str(i)] = {"username": username, "account_id": account_id}
                print(f"\033[1;36m[{i}] \033[1;36m✈ \033[1;97mID\033[1;32m㊪ :\033[1;93m {username} \033[1;97m|\033[1;31m㊪ :\033[1;32m Hoạt Động")
                print("\033[1;97m════════════════════════════════════════════════")
            return account_map
        except Exception as e:
            print(f"\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32m{json.dumps(chontk_snapchat)}")
            time.sleep(10)

# -------- Main program flow (headless open link via adb, no prompt) --------

def main():
    global DEVICE, DEVICE_SERIAL
    
    # Chọn thiết bị trước khi init
    adb_serial = device_manager_select()
    
    # In thông tin thiết bị đã chọn
    if adb_serial:
        devices = adb_list_devices()
        for d in devices:
            if d['id'] == adb_serial:
                print(f"\033[1;32m[✔] Đã chọn thiết bị: {d['name']} ({adb_serial})")
                break
    
    init_device(adb_serial)

    banner()
    print("\033[1;97m[\033[1;91m❣\033[1;97m]\033[1;97m Địa chỉ Ip\033[1;32m  : \033[1;32m☞\033[1;31m♔ \033[1;32m83.86.8888\033[1;31m♔ \033[1;97m☜")
    print("\033[1;97m════════════════════════════════════════════════")
    print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhập \033[1;31m1 \033[1;33mđể vào \033[1;34mTool Snapchat\033[1;33m")
    print("\033[1;31m\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;31mNhập 2 Để Xóa Authorization Hiện Tại'")

    while True:
        try:
            choose = input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhập Lựa Chọn (1 hoặc 2): ").strip()
            if choose == "1" or choose == "2":
                break
            print("\033[1;31m\n❌ Lựa chọn không hợp lệ! Hãy nhập lại.\n")
        except Exception:
            print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;31mSai định dạng! Vui lòng nhập số.\n")

    if choose == "2":
        file = "Authorization.txt"
        if os.path.exists(file):
            try:
                os.remove(file)
                print("\033[1;32m[✔] Đã xóa Authorization.txt!")
            except Exception:
                print("\033[1;31m[✖] Không thể xóa Authorization.txt!")
        else:
            print("\033[1;33m[!] File Authorization.txt không tồn tại!")
        print("\033[1;33m👉 Vui lòng nhập lại thông tin!")

    file = "Authorization.txt"
    if not os.path.exists(file):
        try:
            with open(file, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            print("\033[1;31m[✖] Không thể tạo file Authorization.txt!")
            sys.exit(1)

    author = ""
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                author = f.read().strip()
        except Exception:
            print("\033[1;31m[✖] Không thể đọc file Authorization.txt!")
            sys.exit(1)

    while not author:
        print("\033[1;97m════════════════════════════════════════════════")
        author = input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhập Authorization: ").strip()
        try:
            with open(file, "w", encoding="utf-8") as f:
                f.write(author)
        except Exception:
            print("\033[1;31m[✖] Không thể ghi vào file Authorization.txt!")
            sys.exit(1)

    headers = {
        'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://app.golike.net/',
        'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': "Windows",
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        # Anti-browser token header (giữ như trước)
        'T': 'VFZSak1FMTZZM3BOZWtFd1RtYzlQUT09',
        # Giả user-agent trình duyệt mobile để tránh block
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
        "Authorization": author,
        'Content-Type': 'application/json;charset=utf-8'
    }

    print("\033[1;97m════════════════════════════════════════════════")
    print("\033[1;32m🚀 Đăng nhập thành công! Đang vào Tool Snapchat...")
    time.sleep(1)

    chontk_snapchat = chonacc(headers)
    account_map = dsacc(chontk_snapchat)

    # chọn acc
    while True:
        try:
            choice = input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhập số thứ tự acc Snapchat (1, 2, 3...): ").strip()
            if choice in account_map:
                selected_account = account_map[choice]
                username = selected_account["username"]
                account_id = selected_account["account_id"]
                print(f"\033[1;32m[✔] Đã chọn tài khoản: {username}")
                break
            else:
                username_found = False
                for acc_num, acc_info in account_map.items():
                    if acc_info["username"] == choice:
                        username = acc_info["username"]
                        account_id = acc_info["account_id"]
                        username_found = True
                        print(f"\033[1;32m[✔] Đã chọn tài khoản: {username}")
                        break
                if username_found:
                    break
                else:
                    print("\033[1;31m[✖] Số thứ tự hoặc username không hợp lệ! Vui lòng nhập lại.")
        except Exception as e:
            print(f"\033[1;31m[✖] Lỗi: {e}")

    # nhập delay
    while True:
        try:
            delay = int(input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhập thời gian làm job (giây): ").strip())
            if delay > 0:
                break
            else:
                print("\033[1;31m[✖] Thời gian phải lớn hơn 0!")
        except ValueError:
            print("\033[1;31m[✖] Sai định dạng! Vui lòng nhập số.")

    while True:
        lannhan = input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhận tiền lần 2 nếu lần 1 fail? (y/n): ").strip().lower()
        if lannhan in ["y", "n"]:
            break
        print("\033[1;31m[✖] Nhập sai! Vui lòng nhập 'y' hoặc 'n'.")

    while True:
        try:
            doiacc = int(input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mSố job fail để đổi acc Snapchat (nhập 1 nếu không muốn dừng): ").strip())
            if doiacc >= 1:
                break
            else:
                print("\033[1;31m[✖] Số phải lớn hơn hoặc bằng 1!")
        except ValueError:
            print("\033[1;31m[✖] Sai định dạng! Vui lòng nhập số.")

    while True:
        try:
            print("\033[1;97m════════════════════════════════════════════════")
            print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhập 1 : \033[1;33mChỉ nhận nhiệm vụ Follow")
            print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhập 2 : \033[1;33mChỉ nhận nhiệm vụ like")
            print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhập 12 : \033[1;33mKết hợp cả Like và Follow")
            print("\033[1;97m════════════════════════════════════════════════")
            chedo = int(input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;34mChọn lựa chọn: ").strip())
            if chedo in [1, 2, 12]:
                break
            else:
                print("\033[1;31m[✖] Chỉ được nhập 1, 2 hoặc 12!")
        except ValueError:
            print("\033[1;31m[✖] Sai định dạng! Vui lòng nhập số.")

    if chedo == 1:
        lam = ["follow"]
    elif chedo == 2:
        lam = ["like"]
    else:
        lam = ["follow", "like"]

    # --- MOD: Nhập tọa độ X Y nếu muốn dùng manual tap cho hành động FOLLOW ---
    use_manual_xy = False
    follow_x = None
    follow_y = None

    if "follow" in lam:
        while True:
            chon_xy = input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ Dùng tọa độ X Y cho FOLLOW? (y/n): ").strip().lower()
            if chon_xy in ["y", "n"]:
                break
            print("\033[1;31m[✖] Nhập sai! Vui lòng nhập 'y' hoặc 'n'.")
        if chon_xy == "y":
            use_manual_xy = True
            while True:
                try:
                    follow_x = int(input("\033[1;32m[❣] Nhập tọa độ X FOLLOW: ").strip())
                    follow_y = int(input("\033[1;32m[❣] Nhập tọa độ Y FOLLOW: ").strip())
                    # optional: validate trong bounds màn hình
                    w, h = get_screen_size(DEVICE_SERIAL)
                    if 0 <= follow_x <= max(w, 10000) and 0 <= follow_y <= max(h, 10000):
                        break
                    else:
                        print("\033[1;31m[✖] Tọa độ có vẻ không hợp lệ theo kích thước màn hình. Vui lòng kiểm tra lại.")
                except ValueError:
                    print("\033[1;31m[✖] X Y phải là số!")

    # =========================================================================
    # NEW: Hỏi người dùng có muốn nhập tọa độ X Y khi link mở trong trình duyệt không
    # =========================================================================
    use_web_fallback_xy = False
    web_open_x = None
    web_open_y = None
    
    print("\033[1;97m════════════════════════════════════════════════")
    print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;33mCẤU HÌNH FALLBACK KHI LINK MỞ TRONG TRÌNH DUYỆT")
    print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32m(Nếu link không mở trong Snapchat mà mở trong trình duyệt)")
    print("\033[1;97m════════════════════════════════════════════════")
    
    while True:
        chon_web_fallback = input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ Cấu hình tọa độ X Y khi link mở trong trình duyệt? (y/n): ").strip().lower()
        if chon_web_fallback in ["y", "n"]:
            break
        print("\033[1;31m[✖] Nhập sai! Vui lòng nhập 'y' hoặc 'n'.")
    
    if chon_web_fallback == "y":
        use_web_fallback_xy = True
        print("\033[1;33m[!] Hướng dẫn: Khi link mở trong trình duyệt, thường có nút 'MỞ BẰNG SNAPCHAT'")
        print("\033[1;33m[!] Hãy chạy tool, khi link mở trong trình duyệt, dùng ADB để lấy tọa độ nút đó")
        print("\033[1;33m[!] Ví dụ: Dùng 'adb shell getevent' hoặc công cụ hiển thị tọa độ")
        
        while True:
            try:
                web_open_x = int(input("\033[1;32m[❣] Nhập tọa độ X của nút 'Mở bằng Snapchat' (trong trình duyệt): ").strip())
                web_open_y = int(input("\033[1;32m[❣] Nhập tọa độ Y của nút 'Mở bằng Snapchat' (trong trình duyệt): ").strip())
                # optional: validate trong bounds màn hình
                w, h = get_screen_size(DEVICE_SERIAL)
                if 0 <= web_open_x <= max(w, 10000) and 0 <= web_open_y <= max(h, 10000):
                    print(f"\033[1;32m[✔] Đã lưu tọa độ fallback: ({web_open_x}, {web_open_y})")
                    break
                else:
                    print("\033[1;31m[✖] Tọa độ có vẻ không hợp lệ theo kích thước màn hình.")
                    print(f"\033[1;33m[!] Kích thước màn hình hiện tại: {w}x{h}")
            except ValueError:
                print("\033[1;31m[✖] X Y phải là số!")
    
    # -------------------------------------------------------------------------
    dem = 0
    tong = 0
    checkdoiacc = 0
    previous_job = None
    colors = [
        "\033[1;37mT\033[1;36mu\033[1;35ms \033[1;32mT\033[1;31mO\033[1;34mO\033[1;33mL\033[1;36m - Phong\033[1;36m Tus \033[1;31m\033[1;32m",
        "\033[1;34mT\033[1;31mu\033[1;37ms \033[1;36mT\033[1;32mO\033[1;35mO\033[1;37mL\033[1;32m - Phong\033[1;34m Tus \033[1;31m\033[1;32m",
    ]

    banner()
    print("\033[1;97m════════════════════════════════════════════════")
    print("\033[1;36m|STT\033[1;97m| \033[1;33mThời gian ┊ \033[1;32mStatus | \033[1;31mType Job | \033[1;32mID Acc | \033[1;32mXu |\033[1;33m Tổng")
    print("\033[1;97m════════════════════════════════════════════════")

    while True:
        if checkdoiacc == doiacc:
            print("\033[1;31m[!] Đã đạt giới hạn job fail, đổi tài khoản...")
            account_map = dsacc(chontk_snapchat)
            while True:
                try:
                    choice = input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;31mNhập số thứ tự acc mới: ").strip()
                    if choice in account_map:
                        selected_account = account_map[choice]
                        username = selected_account["username"]
                        account_id = selected_account["account_id"]
                        print(f"\033[1;32m[✔] Đã đổi sang tài khoản: {username}")
                        break
                    else:
                        print("\033[1;31m[✖] Số thứ tự không hợp lệ!")
                except Exception as e:
                    print(f"\033[1;31m[✖] Lỗi: {e}")
            checkdoiacc = 0

        print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;35mĐang Tìm Nhiệm vụ:>        ", end='\r')

        # fetch job
        while True:
            try:
                nhanjob = nhannv(account_id, headers)
                break
            except Exception:
                time.sleep(1)

        if not nhanjob.get("data", {}).get("link"):
            print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;31mJob die - Không có link!        ", end='\r')
            time.sleep(2)
            try:
                baoloi(nhanjob.get("data", {}).get("id", ""), nhanjob.get("data", {}).get("object_id", ""), account_id, nhanjob.get("data", {}).get("type", ""), headers)
            except Exception:
                pass
            continue

        # skip duplicate job
        if (previous_job is not None and
            previous_job.get("data", {}).get("link") == nhanjob.get("data", {}).get("link") and
            previous_job.get("data", {}).get("type") == nhanjob.get("data", {}).get("type")):
            print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;31mJob trùng với job trước đó - Bỏ qua!        ", end='\r')
            time.sleep(2)
            try:
                baoloi(nhanjob.get("data", {}).get("id", ""), nhanjob.get("data", {}).get("object_id", ""), account_id, nhanjob.get("data", {}).get("type", ""), headers)
            except Exception:
                pass
            continue

        previous_job = nhanjob

        if nhanjob.get("status") == 200:
            data = nhanjob.get("data", {})
            ads_id = data.get("id", "")
            link = data.get("link", "")
            object_id = data.get("object_id", "")
            loai = data.get("type", "")

            if loai not in lam:
                try:
                    baoloi(ads_id, object_id, account_id, loai, headers)
                    print(f"\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;31mĐã bỏ qua job {loai}!        ", end='\r')
                    time.sleep(1)
                    continue
                except Exception:
                    pass

            # Mở link trên device với serial binding
            opened_on_device = False
            try:
                # ÉP MỞ QUA PACKAGE com.snapchat.android + DEEP LINK FIX
                opened_on_device = open_link_on_device(link, 'com.snapchat.android', DEVICE_SERIAL)
            except Exception:
                opened_on_device = False

            if not opened_on_device:
                # Nếu mở intent thất bại -> báo lỗi và skip job
                print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;31mKhông thể mở link trên device - Job die!")
                try:
                    baoloi(ads_id, object_id, account_id, loai, headers)
                except Exception:
                    pass
                continue

            # chờ load UI
            time.sleep(2)
            
            # =========================================================================
            # NEW: Kiểm tra xem link có mở trong trình duyệt không - CHỈ KIỂM TRA NẾU ĐÃ CẤU HÌNH
            # =========================================================================
            web_opened = False
            snapchat_opened = False
            
            # Ưu tiên kiểm tra Snapchat trước
            if DEVICE is not None:
                snapchat_opened = check_snapchat_opened(DEVICE, timeout=3)
                
                # Nếu đã mở thẳng vào Snapchat thì bỏ qua kiểm tra trình duyệt
                if snapchat_opened:
                    print("\033[1;32m[✔] Link đã mở thẳng vào Snapchat!")
                else:
                    # Chỉ kiểm tra trình duyệt nếu đã cấu hình fallback
                    if use_web_fallback_xy:
                        web_opened = check_web_browser_opened(DEVICE, timeout=3)
                
            if web_opened:
                print("\033[1;33m[!] Phát hiện link mở trong trình duyệt web!")
                
                # Xử lý fallback nếu người dùng đã cấu hình tọa độ
                if use_web_fallback_xy and web_open_x is not None and web_open_y is not None:
                    print("\033[1;36m[•] Áp dụng fallback khi mở trong trình duyệt...")
                    fallback_success = handle_web_browser_fallback(DEVICE, web_open_x, web_open_y, DEVICE_SERIAL)
                    
                    if fallback_success:
                        print("\033[1;32m[✔] Xử lý fallback trình duyệt thành công!")
                        time.sleep(2)  # Chờ Snapchat load
                    else:
                        print("\033[1;31m[✖] Xử lý fallback trình duyệt thất bại!")
                        try:
                            baoloi(ads_id, object_id, account_id, loai, headers)
                        except Exception:
                            pass
                        checkdoiacc += 1
                        continue
                else:
                    print("\033[1;31m[✖] Link mở trong trình duyệt nhưng chưa cấu hình tọa độ fallback!")
                    try:
                        baoloi(ads_id, object_id, account_id, loai, headers)
                    except Exception:
                        pass
                    checkdoiacc += 1
                    continue
            elif not snapchat_opened and DEVICE is not None:
                # Không phát hiện Snapchat cũng không phát hiện trình duyệt
                print("\033[1;33m[!] Không xác định được app đang mở, tiếp tục thực hiện hành động...")

            # ===== CHECK LỖI SNAPCHAT: LINK KHÔNG HOẠT ĐỘNG HOẶC POPUP LỖI =====
            link_error = False
            try:
                if check_snapchat_link_error(DEVICE, timeout=5):
                    print("\033[1;31m[✖] Link Snapchat không hoạt động - Skip job!\033[0m")
                    link_error = True

                # Check thêm lỗi popup "Ôi! Có lỗi xảy ra" - CẢI TIẾN
                if not link_error and check_generic_popup_error(DEVICE, timeout=3):
                    print("\033[1;31m[✖] Phát hiện popup 'Có lỗi xảy ra' - Bỏ qua job!\033[0m")
                    # Thử xử lý popup lỗi trước khi bỏ qua
                    handle_error_popup(DEVICE, DEVICE_SERIAL)
                    link_error = True
                    
            except Exception as e:
                print("[!] Lỗi check error:", e)

            if link_error:
                try:
                    baoloi(ads_id, object_id, account_id, loai, headers)
                except Exception:
                    pass
                checkdoiacc += 1
                # Đợi một chút để popup biến mất
                time.sleep(2)
                continue

            # thực hiện hành động auto (follow / like) với serial binding
            action_ok = False
            try:
                if loai == "follow":
                    # --- MOD: nếu user nhập manual XY thì tap vào tọa độ đó ---
                    if use_manual_xy and follow_x is not None and follow_y is not None:
                        print(f"\033[1;36m[•] FOLLOW bằng tọa độ ({follow_x}, {follow_y})")
                        # tap 1 lần, chờ, tap lần 2 (tùy chọn) để tăng độ chắc chắn
                        action_ok = tap_xy(DEVICE, follow_x, follow_y, DEVICE_SERIAL)
                        time.sleep(0.5)
                        try:
                            tap_xy(DEVICE, follow_x, follow_y, DEVICE_SERIAL)
                        except Exception:
                            pass
                    else:
                        action_ok = auto_tap_follow_button(DEVICE, max_wait=6, serial=DEVICE_SERIAL)
                elif loai == "like":
                    action_ok = auto_tap_like_button(DEVICE, max_wait=6, serial=DEVICE_SERIAL)
            except Exception as e:
                print(f"[!] action error: {e}")
                action_ok = False

            # cho UI thời gian update
            time.sleep(1.2)

            # VERIFY: ưu tiên uiautomator2 + tiếng Việt; retry 1 lần nếu chưa thấy
            verified = False
            try:
                if DEVICE is not None:
                    if loai == "follow":
                        verified = verify_followed(DEVICE, timeout=5)
                    elif loai == "like":
                        verified = verify_liked(DEVICE, timeout=5)

                    # nếu chưa verify nhưng action_ok True -> retry click 1 lần rồi verify lại
                    if not verified and action_ok:
                        try:
                            time.sleep(0.4)
                            if loai == "follow":
                                # nếu dùng manual xy -> retry tap manual
                                if use_manual_xy and follow_x is not None and follow_y is not None:
                                    tap_xy(DEVICE, follow_x, follow_y, DEVICE_SERIAL)
                                else:
                                    auto_tap_follow_button(DEVICE, max_wait=3, serial=DEVICE_SERIAL)
                            elif loai == "like":
                                auto_tap_like_button(DEVICE, max_wait=3, serial=DEVICE_SERIAL)
                            time.sleep(1.0)
                            if loai == "follow":
                                verified = verify_followed(DEVICE, timeout=4)
                            elif loai == "like":
                                verified = verify_liked(DEVICE, timeout=4)
                        except Exception:
                            pass
                else:
                    # fallback: nếu không có uiautomator2 thì giữ hành vi cũ (tin action_ok)
                    verified = True if action_ok else False
            except Exception as e:
                print("[!] Lỗi verify action:", e)
                verified = False

            if not verified:
                print("\033[1;31m[✖] Không xác nhận hành động trên UI -> Skip job và báo lỗi!\033[0m")
                try:
                    baoloi(ads_id, object_id, account_id, loai, headers)
                except Exception:
                    pass
                checkdoiacc += 1
                continue

            # hiển thị và đếm ngược thời gian
            for remaining_time in range(delay, -1, -1):
                for color in colors:
                    print(f"\r{color}|{remaining_time}| \033[1;31m", end='', flush=True)
                    time.sleep(2)
            print("\r                          \r", end='')
            print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;35mĐang Nhận Tiền Lần 1:>        ", end='\r')

            while True:
                try:
                    nhantien = hoanthanh(ads_id, account_id, headers)
                    break
                except Exception:
                    time.sleep(1)

            if lannhan == "y":
                checklan = 1
            else:
                checklan = 2

            ok = 0
            while checklan <= 2:
                if nhantien.get("status") == 200:
                    ok = 1
                    dem += 1
                    tien = nhantien.get("data", {}).get("prices", 0)
                    try:
                        tien = int(tien)
                    except Exception:
                        pass
                    tong += tien

                    now = datetime.datetime.now()
                    h = now.hour
                    m = now.minute
                    s = now.second

                    h = f"0{h}" if h < 10 else str(h)
                    m = f"0{m}" if m < 10 else str(m)
                    s = f"0{s}" if s < 10 else str(s)

                    print("                                                    \r", end='')
                    chuoi = (f"\033[1;31m| \033[1;36m{dem}\033[1;31m\033[1;97m | " +
                             f"\033[1;33m{h}:{m}:{s}\033[1;31m\033[1;97m | " +
                             f"\033[1;32msuccess\033[1;31m\033[1;97m | " +
                             f"\033[1;31m{nhantien.get('data', {}).get('type', '')}\033[1;31m\033[1;32m\033[1;32m\033[1;97m |" +
                             f"\033[1;32m {username}\033[1;97m |\033[1;97m \033[1;32m+{tien} \033[1;97m| " +
                             f"\033[1;33m{tong}")
                    print(chuoi)
                    checkdoiacc = 0
                    break
                else:
                    checklan += 1
                    if checklan == 3:
                        break
                    print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;35mĐang Nhận Tiền Lần 2:>        ", end='\r')
                    nhantien = hoanthanh(ads_id, account_id, headers)

            if ok != 1:
                while True:
                    try:
                        baoloi(ads_id, object_id, account_id, loai, headers)
                        print("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;31mĐã bỏ qua job:>        ", end='\r')
                        time.sleep(1)
                        checkdoiacc += 1
                        break
                    except Exception:
                        time.sleep(1)
        else:
            time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n\033[1;31m[!] Đã dừng tool!")
        sys.exit(0)
    except Exception as e:
        print(f"\n\033[1;31m[✖] Lỗi: {e}")
        sys.exit(1)