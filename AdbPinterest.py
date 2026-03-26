#!/usr/bin/env python3
# -- coding: utf-8 --

import os
import sys
import time
import json
import random
import string
import base64
import subprocess
import socket
import hashlib
import importlib
from time import sleep
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, List, Dict
import re
import ast

# Optional libs (may be installed at runtime)
_module_map = {
    "requests": "requests",
    "cloudscraper": "cloudscraper",
    "colorama": "colorama",
    "pystyle": "pystyle",
    "rich": "rich",
    "bs4": "bs4",
    "uiautomator2": "uiautomator2",
}

_missing = []
for mod_name in _module_map:
    try:
        importlib.import_module(mod_name)
    except ModuleNotFoundError:
        _missing.append(mod_name)

if _missing:
    print(f"Thiếu thư viện {_missing}, đang cài đặt...")
    try:
        for pkg in _missing:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
    except subprocess.CalledProcessError:
        print(f"Không thể cài đặt {_missing}. Vui lòng cài tay và chạy lại.")
        sys.exit(1)
    # restart script after installing
    os.execv(sys.executable, [sys.executable] + sys.argv)

import requests
import cloudscraper
from colorama import Fore, init as colorama_init
from pystyle import Colors, Colorate
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from bs4 import BeautifulSoup

# uiautomator2 import
try:
    import uiautomator2 as u2
    UIAUTOMATOR2_AVAILABLE = True
except Exception:
    u2 = None
    UIAUTOMATOR2_AVAILABLE = False

colorama_init(autoreset=True)

# ---------------------------
# Màu và format (tùy biến)
# ---------------------------
RESET = "\033[0m"
BOLD = "\033[1m"

# ---------------------------
# Hàm tiện ích
# ---------------------------
def thanhngang(so):
    """In dấu gạch ngang"""
    print('-' * so)

def kiem_tra_mang():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
    except OSError:
        print("Mạng không ổn định hoặc bị mất kết nối. Vui lòng kiểm tra lại mạng.")
        return False
    return True

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    s = """
▄▄▄█████▓ █    ██   ██████    ▄▄▄█████▓ ▒█████   ▒█████   ██▓    
▓  ██▒ ▓▒ ██  ▓██▒▒██    ▒    ▓  ██▒ ▓▒▒██▒  ██▒▒██▒  ██▒▓██▒    
▒ ▓██░ ▒░▓██  ▒██░░ ▓██▄      ▒ ▓██░ ▒░▒██░  ██▒▒██░  ██▒▒██░    
░ ▓██▓ ░ ▓▓█  ░██░  ▒   ██▒   ░ ▓██▓ ░ ▒██   ██░▒██   ██░▒██░    
  ▒██▒ ░ ▒▒█████▓ ▒██████▒▒     ▒██▒ ░ ░ ████▓▒░░ ████▓▒░░██████▒
  ▒ ░░   ░▒▓▒ ▒ ▒ ▒ ▒▓▒ ▒ ░     ▒ ░░   ░ ▒░▒░▒░ ░ ▒░▒░▒░ ░ ▒░▓  ░
    ░    ░░▒░ ░ ░ ░ ░▒  ░ ░       ░      ░ ▒ ▒░   ░ ▒ ▒░ ░ ░ ▒  ░
  ░       ░░░ ░ ░ ░  ░  ░       ░      ░ ░ ░ ▒  ░ ░ ░ ▒    ░ ░   
            ░           ░                  ░ ░      ░ ░      ░  ░
"""
    try:
        print("\033[38;2;153;51;255m" + s + "\033[0m")
    except Exception:
        print(tim + s + RESET)

# ---------------------------
# ADB device helper functions
# ---------------------------
def adb_list_devices() -> List[Dict[str, str]]:
    devices = []
    try:
        out = subprocess.check_output(["adb", "devices", "-l"], stderr=subprocess.STDOUT)
        out = out.decode(errors="ignore").strip().splitlines()
        for line in out[1:]:
            line = line.strip()
            if not line:
                continue
            if "unauthorized" in line or "offline" in line:
                parts = line.split()
                devices.append({"name": f"unauthorized/offline", "id": parts[0]})
                continue
            if "device" in line:
                parts = line.split()
                serial = parts[0]
                model = "Unknown"
                for p in parts:
                    if p.startswith("model:"):
                        model = p.split("model:")[1]
                        break
                devices.append({"name": model, "id": serial})
    except Exception:
        pass
    return devices

def adb_add_device(ip: str, pin: str = "") -> bool:
    try:
        if ":" not in ip:
            ip = ip.strip()
            ip = f"{ip}:5555"
        if pin:
            try:
                subprocess.run(["adb", "pair", ip], input=pin.encode(), timeout=10)
            except Exception:
                pass
        res = subprocess.run(["adb", "connect", ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        out = res.stdout.decode(errors="ignore") + res.stderr.decode(errors="ignore")
        if "connected" in out.lower() or "already" in out.lower():
            return True
        return False
    except Exception:
        return False

def device_manager_select() -> Optional[str]:
    while True:
        clear_screen()
        banner()
        print("════════════════════════════════════════════════")
        print("STT ║ NAME DEVICES        ║ ID DEVICES")
        print("════════════════════════════════════════════════")
        devices = adb_list_devices()
        if not devices:
            print("[!] Không tìm thấy thiết bị ADB nào.")
        for i, d in enumerate(devices, 1):
            print(f"[{i}] ║ {d['name']:<18} ║ {d['id']}")
        print("════════════════════════════════════════════════")
        print("[add] ✈ Nhập add để thêm thiết bị (ADB)")
        print("════════════════════════════════════════════════")
        choice = input("[❣] ✈ Nhập STT thiết bị cần chạy (1 | all | add | none): ").strip().lower()
        if choice == "add":
            ip = input("[</>] ✈ Nhập IP:PORT (VD 192.168.1.5:5555): ").strip()
            pin = input("[❣] ✈ Nhập mã PIN 6 số (bỏ trống nếu đã xác minh): ").strip()
            ok = adb_add_device(ip, pin)
            print("[✔] Đã thêm thiết bị thành công!" if ok else "[✖] Thêm thiết bị thất bại!")
            time.sleep(2)
            continue
        if choice == "none":
            return None
        if choice == "all" and devices:
            return devices[0]["id"]
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx]["id"]
        print("[✖] Lựa chọn không hợp lệ! Thử lại...")
        time.sleep(1.5)

# ---------------------------
# Helper: detect homepage more robustly
# ---------------------------
def is_homepage(d, CONFIG) -> bool:
    """Trả True nếu có dấu hiệu đang ở trang Home/Feed."""
    try:
        # 1) xpath indicators for hx in CONFIG.get("homepage_indicators", []):
        for hx in CONFIG.get("homepage_indicators", []):
            try:
                if d.xpath(hx).exists:
                    return True
            except Exception:
                pass
        # 2) common resource-ids (variants)
        common_home_ids = [
            "com.pinterest:id/home_feed",
            "com.pinterest:id/home",
            "com.pinterest:id/explore_feed",
            "com.pinterest:id/home_tab"
        ]
        for rid in common_home_ids:
            try:
                if d(resourceId=rid).exists:
                    return True
            except Exception:
                pass
        # 3) check current app/activity info if available
        try:
            cur = d.app_current()
            pkg = cur.get('package', '') if isinstance(cur, dict) else ''
            act = cur.get('activity', '') if isinstance(cur, dict) else ''
            if 'com.pinterest' in str(pkg).lower():
                if 'home' in str(act).lower() or 'feed' in str(act).lower():
                    return True
        except Exception:
            pass
    except Exception:
        pass
    return False

# ---------------------------
# Helper: find heart (favorite) button ONLY
# ---------------------------
def find_favorite_button(d):
    """
    Tìm nút Tim / Yêu Thích (ưu tiên) — KHÔNG trả về nút Save/Lưu.
    Trả lại đối tượng element (uiautomator) nếu tìm được, ngược lại None.
    Cải tiến: cố gắng bắt nhiều biến thể selector (resource-id, content-desc, text, xpath contains).
    """
    try:
        # common resource-id variants observed in Pinterest APKs (thêm/điều chỉnh nếu cần)
        resource_id_variants = [
            "com.pinterest:id/like_button",
            "com.pinterest:id/heart_button",
            "com.pinterest:id/pin_like_button",
            "com.pinterest:id/closeup_heart_button",
            "com.pinterest:id/ux_like_button",
            "com.pinterest:id/like_button_large",
            "com.pinterest:id/pin_action_bar_like_button",
            # fallback ids that sometimes used for "like" icons - adjust if you inspect APK/UI
            "com.pinterest:id/btn_like",
            "com.pinterest:id/btn_heart",
        ]
        # Try resource-id first (fast and reliable)
        for rid in resource_id_variants:
            try:
                el = d(resourceId=rid)
                if el.exists:
                    return el
            except Exception:
                pass

        # keywords to search in content-desc or text (supports multiple languages)
        keywords = [
            "Yêu", "Yêu thích", "Yêu Thích", "Thả tim", "Thích",
            "Like", "Liked", "favorite", "heart", "❤", "Love", "Đã thích", "Đã lưu"
        ]

        # Try content-desc (description / accessibility id)
        for kw in keywords:
            try:
                el = d(description=kw)
                if el.exists:
                    return el
            except Exception:
                pass

        # Try text variants
        for kw in keywords:
            try:
                el = d(text=kw)
                if el.exists:
                    return el
            except Exception:
                pass

        # Try xpath contains on content-desc or text for partial matches
        for kw in keywords:
            try:
                xpath_expr = f"//*[contains(@content-desc, '{kw}') or contains(@text, '{kw}')]"
                el = d.xpath(xpath_expr)
                if el.exists:
                    return el
            except Exception:
                pass

        # As last resort, try to find image buttons near typical action bar areas:
        small_kw = ["heart", "like", "favorite", "tim", "thích"]
        for kw in small_kw:
            try:
                xpath_expr = f"//android.widget.ImageView[contains(@content-desc, '{kw}') or contains(@resource-id, '{kw}')]"
                el = d.xpath(xpath_expr)
                if el.exists:
                    return el
            except Exception:
                pass

        # ---- Detect heart icon with NO TEXT (Pinterest real behavior) ----
        # Pinterest often uses ImageView clickable/focusable with no content-desc/text.
        # We search for android.widget.ImageView elements that are clickable & focusable,
        # and prefer those that appear near action bar (heuristic: presence and bounds).
        try:
            hearts = d.xpath("//android.widget.ImageView[@clickable='true' and @enabled='true']")
            if hearts.exists:
                for el in hearts.all():
                    try:
                        info = {}
                        try:
                            info = el.info or {}
                        except Exception:
                            info = {}
                        # resourceName may be returned as 'resourceName' or 'resource-id'
                        rid = info.get("resourceName", "") or info.get("resource-id", "") or ""
                        desc = (info.get("contentDescription") or info.get("content-desc") or info.get("description") or "").lower()
                        # If resource id or desc hints it's a heart/like -> good
                        if any(tok in rid.lower() for tok in ("heart", "like", "favorite", "pin_like", "btn_like")) or \
                           any(tok in desc for tok in ("heart", "like", "favorite", "tim", "thích", "yêu")):
                            return el
                        # If element is focusable and clickable, and has bounds -> likely an icon
                        focusable = info.get("focusable") or info.get("focusableInTouchMode") or False
                        clickable = info.get("clickable") or True  # we already searched clickable ones
                        bounds = info.get("bounds", "") or info.get("visibleBounds", "")
                        if focusable and clickable and bounds:
                            # Heuristic: treat it as heart (Pinterest often uses ImageView heart without text)
                            return el
                    except Exception:
                        pass
        except Exception:
            pass

    except Exception:
        pass

    return None

# ---------------------------
# Robust click helper + bounds parser (works across resolutions)
# ---------------------------
def _parse_bounds(bounds):
    """
    Nhận bounds ở nhiều định dạng:
    - dict: {'left':..,'top':..,'right':..,'bottom':..}
    - str: "[left,top][right,bottom]" hoặc "{'left':..,'top':..,'right':..,'bottom':..}"
    Trả về tuple (left, top, right, bottom) hoặc None nếu không parse được.
    """
    try:
        if not bounds:
            return None
        if isinstance(bounds, dict):
            left = int(bounds.get('left') or bounds.get('l') or bounds.get('x') or 0)
            top = int(bounds.get('top') or bounds.get('t') or bounds.get('y') or 0)
            right = int(bounds.get('right') or bounds.get('r') or 0)
            bottom = int(bounds.get('bottom') or bounds.get('b') or 0)
            return (left, top, right, bottom)
        if isinstance(bounds, str):
            # Try to extract numbers
            nums = re.findall(r'-?\d+', bounds)
            if len(nums) >= 4:
                left, top, right, bottom = int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3])
                return (left, top, right, bottom)
            # try to literal_eval if it's a dict string
            try:
                obj = ast.literal_eval(bounds)
                if isinstance(obj, dict):
                    return _parse_bounds(obj)
            except Exception:
                pass
    except Exception:
        pass
    return None

def click_element(el, d, debug=False):
    """
    Click an element robustly.
    - Prefer el.click()
    - Fallback: compute center from element bounds and d.click(cx, cy)
    - If bounds missing, attempt to use visibleCenter (if present).
    - If neither available, return False.
    - Return True if a click attempt was made, False otherwise.
    """
    try:
        # 1) Preferred / fastest: element native click
        try:
            el.click()
            if debug:
                print("[DBG] el.click() invoked")
            return True
        except Exception:
            if debug:
                print("[DBG] el.click() failed, trying bounds-based tap")

        # 2) Try to read info.bounds or visibleBounds
        try:
            info = {}
            try:
                info = el.info or {}
            except Exception:
                info = {}
        except Exception:
            info = {}

        bounds = info.get('bounds') or info.get('visibleBounds') or info.get('boundsInScreen') or None
        parsed = _parse_bounds(bounds)
        if parsed:
            left, top, right, bottom = parsed
            cx = int((left + right) / 2)
            cy = int((top + bottom) / 2)
            try:
                d.click(cx, cy)
                if debug:
                    print(f"[DBG] Clicked at bounds center: ({cx},{cy})")
                return True
            except Exception:
                if debug:
                    print("[DBG] d.click at bounds center failed")
                pass

        # 3) Try common helpers returned by some uiautomator implementations
        try:
            vc = info.get('visibleCenter') or info.get('center') or None
            if vc and isinstance(vc, dict):
                cx = int(vc.get('x') or vc.get('centerX') or vc.get('cx'))
                cy = int(vc.get('y') or vc.get('centerY') or vc.get('cy'))
                d.click(cx, cy)
                if debug:
                    print(f"[DBG] Clicked at visibleCenter: ({cx},{cy})")
                return True
        except Exception:
            pass

        # 4) NO hardcoded coordinate fallback here. If we cannot compute a safe coordinate, return False.
        if debug:
            print("[DBG] click_element: no reliable coordinate available, aborting (no hardcoded fallback).")
        return False
    except Exception as e:
        if debug:
            print("[DBG] click_element exception:", e)
    return False

# ---------------------------
# UPDATED: ADB + UIAutomator2 High Performance Action
# ---------------------------
def perform_action_on_device(serial: str, link: str, job_type: str, timeout: int = 20) -> str:
    """
    Phiên bản High Performance:
    - Với job_type == 'like' chỉ tìm và click TIM (heart). KHÔNG click Save/Lưu.
    - Với follow/love giữ logic cũ.
    - Trả về: "OK", "FAIL", "DIE", "PRIVATE", "NO_HEART"
    """
    if not UIAUTOMATOR2_AVAILABLE:
        return "FAIL"

    try:
        # 1. Connect Device
        try:
            d = u2.connect(serial)
        except:
            try:
                d = u2.connect(f"adb://{serial}")
            except:
                return "FAIL"

        # Wake up screen nếu đang tắt
        try:
            d.screen_on()
        except:
            pass

        # 2. Open Link (Deep Link)
        cmd = f"am start -W -a android.intent.action.VIEW -d \"{link}\" com.pinterest"
        try:
            d.shell(cmd)
        except Exception:
            # fallback shell via adb
            try:
                subprocess.run(["adb", "-s", serial, "shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", link], timeout=8)
            except Exception:
                pass

        # 3. CẤU HÌNH SELECTOR (Cập nhật mới nhất)
        CONFIG = {
            "keywords_die_xpath": [
                "//*[contains(@text, \"Pin not found\")]",
                "//*[contains(@text, \"couldn't find\")]",
                "//*[contains(@text, \"account isn't available\")]",
                "//*[contains(@text, \"trang này không khả dụng\")]",
                "//*[contains(@text, \"liên kết hỏng\")]"
            ],
            "keywords_private_xpath": [
                "//*[contains(@text, \"private\")]",
                "//*[contains(@text, \"riêng tư\")]",
                "//*[contains(@text, \"bảng bí mật\")]"
            ],
            "homepage_indicators": [
                "//*[contains(@text, \"Home\")]",
                "//*[contains(@text, \"Trang chủ\")]",
                "//*[contains(@resource-id, 'home')]",
                "//*[contains(@text, \"For you\")]",
                "//*[contains(@text, \"Explore\")]"
            ],
            "follow": {
                "btn_ids": [
                    "com.pinterest:id/follow_button",
                    "com.pinterest:id/profile_header_follow_button",
                    "com.pinterest:id/user_follow_btn",
                    "com.pinterest:id/lego_user_follow_button",
                    "com.pinterest:id/follow_btn",
                    "com.pinterest:id/ux_follow_button",
                    "com.pinterest:id/follow_cta",
                    "com.pinterest:id/follow_toggle"
                ],
                "btn_texts": ["Follow", "Theo dõi", "Theo dõi+", "Follow back", "Theo Dõi"],
                "success_texts": ["Following", "Đang theo dõi", "Đã theo dõi"]
            },
            # keep save ids for reference but for 'like' we will NOT use them
            "like": {
                "btn_ids": [
                    "com.pinterest:id/save_button",
                    "com.pinterest:id/pin_action_bar_save_button",
                    "com.pinterest:id/closeup_action_bar_save_button",
                    "com.pinterest:id/lego_pin_grid_cell_save_button",
                    "com.pinterest:id/like_button",
                    "com.pinterest:id/pin_action_bar_like_button",
                    "com.pinterest:id/closeup_like_button",
                    "com.pinterest:id/ux_like_button",
                    "com.pinterest:id/like_button_large"
                ],
                "btn_texts": [
                    "Save", "Lưu", "Pin it", "Lưu ghim",
                    "Yêu thích", "Yêu Thích", "❤", "Like", "Thích"
                ],
                "success_texts": ["Saved", "Đã lưu", "Liked", "Đã thích"]
            },
            "love": {
                "btn_ids": [
                    "com.pinterest:id/like_button",
                    "com.pinterest:id/heart_button",
                    "com.pinterest:id/pin_like_button",
                    "com.pinterest:id/closeup_heart_button"
                ],
                "btn_texts": ["Like", "Yêu thích", "Thả tim", "❤", "Thích"],
                "success_texts": ["Liked", "Đã thích"]
            }
        }

        # ensure compatibility if server returns "favorite"
        if job_type == "favorite":
            job_type = "like"

        current_job = CONFIG.get(job_type)
        if not current_job:
            return "FAIL"

        # Logic để phát hiện nếu đang ở trang chủ:
        HOME_DETECT_SECONDS = 3
        home_detect_start = None

        # Special handling: if job_type is like -> ONLY try heart button; DO NOT click save
        if job_type == "like":
            start_time = time.time()
            while time.time() - start_time < timeout:
                # 1) quick success check
                for s_txt in current_job.get("success_texts", []):
                    try:
                        if d(text=s_txt).exists or d(description=s_txt).exists or d.xpath(f"//*[contains(@text, '{s_txt}')]").exists:
                            return "OK"
                    except Exception:
                        pass

                # 2) detect homepage (if deep link returned home)
                try:
                    homepage_found = is_homepage(d, CONFIG)
                except Exception:
                    homepage_found = False

                # 3) try to find heart specifically (do NOT fall back to save)
                try:
                    fav_el = find_favorite_button(d)
                    if fav_el:
                        # click heart (robust, no hardcoded coords)
                        clicked = click_element(fav_el, d)
                        if not clicked:
                            # cannot click safely (no coords) -> treat as failure for this loop iteration
                            time.sleep(0.6)
                            continue

                        # verify
                        verify_start = time.time()
                        verified = False
                        while time.time() - verify_start < 4:
                            for s_txt in current_job.get("success_texts", []):
                                try:
                                    if d(text=s_txt).exists or d(description=s_txt).exists or d.xpath(f"//*[contains(@text, '{s_txt}')]").exists:
                                        verified = True
                                        break
                                except Exception:
                                    pass
                            if verified:
                                return "OK"

                            # additional heuristic: if the favorite element toggled (no longer identical or has 'selected'/'checked' state)
                            try:
                                info = fav_el.info
                                if isinstance(info, dict):
                                    if info.get('checked') or info.get('selected'):
                                        return "OK"
                                    cd = info.get('contentDescription') or info.get('content-desc') or info.get('description')
                                    if cd and any(tok in str(cd) for tok in ["Liked", "Đã thích", "Đã lưu", "liked"]):
                                        return "OK"
                            except Exception:
                                pass
                            time.sleep(0.4)

                        # if clicking heart didn't immediately show success, still treat as OK if element disappeared/changed
                        try:
                            if not fav_el.exists:
                                return "OK"
                        except Exception:
                            pass
                except Exception:
                    pass

                # If homepage detected and no heart available -> DIE
                try:
                    if homepage_found:
                        try:
                            if not find_favorite_button(d):
                                return "DIE"
                        except Exception:
                            return "DIE"
                except Exception:
                    pass

                time.sleep(0.8)
            # timeout reached - no heart clicked
            return "NO_HEART"

        # For other job types (follow / love) follow the general loop
        start_time = time.time()
        while time.time() - start_time < timeout:
            # --- A. CHECK SUCCESS TRƯỚC (Nhanh nhất) ---
            for s_txt in current_job.get("success_texts", []):
                try:
                    if d(text=s_txt).exists or d(description=s_txt).exists or d.xpath(f"//*[contains(@text, '{s_txt}')]").exists:
                        return "OK"
                except Exception:
                    pass

            # --- CHECK HOME INDICATORS ---
            homepage_found = is_homepage(d, CONFIG)

            # Nếu thấy home indicator, nhưng vẫn có nút hành động thì không coi là home
            action_element_found = False
            try:
                for bid in current_job.get("btn_ids", []):
                    try:
                        if d(resourceId=bid).exists:
                            action_element_found = True
                            break
                    except Exception:
                        pass
            except Exception:
                pass

            if not action_element_found:
                try:
                    for btxt in current_job.get("btn_texts", []):
                        try:
                            if d(text=btxt).exists or d(description=btxt).exists:
                                action_element_found = True
                                break
                        except Exception:
                            pass
                    # also check content-desc via xpath fragments
                    if not action_element_found:
                        for btxt in current_job.get("btn_texts", []):
                            xpath_expr = f"//*[contains(@content-desc, '{btxt}')]"
                            try:
                                if d.xpath(xpath_expr).exists:
                                    action_element_found = True
                                    break
                            except Exception:
                                pass
                except Exception:
                    pass

            if homepage_found and not action_element_found:
                if home_detect_start is None:
                    home_detect_start = time.time()
                else:
                    if time.time() - home_detect_start >= HOME_DETECT_SECONDS:
                        print("[!] Deep link trả về trang chủ — Skip job (treat as DIE)")
                        return "DIE"
            else:
                home_detect_start = None

            # --- B. TÌM NÚT & CLICK ---
            btn_found = None
            try:
                # Try resource-id first
                for bid in current_job.get("btn_ids", []):
                    try:
                        el = d(resourceId=bid)
                        if el.exists:
                            btn_found = el
                            break
                    except Exception:
                        pass
            except Exception:
                pass

            if not btn_found:
                try:
                    # Try by text
                    for btxt in current_job.get("btn_texts", []):
                        try:
                            el = d(text=btxt)
                            if el.exists:
                                btn_found = el
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

            if not btn_found:
                try:
                    # Try by description (content-desc)
                    for btxt in current_job.get("btn_texts", []):
                        try:
                            el = d(description=btxt)
                            if el.exists:
                                btn_found = el
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

            if not btn_found:
                try:
                    # Try xpath contains content-desc or text (fallback)
                    for btxt in current_job.get("btn_texts", []):
                        xpath_expr = f"//*[contains(@content-desc, '{btxt}') or contains(@text, '{btxt}')]"
                        try:
                            if d.xpath(xpath_expr).exists:
                                btn_found = d.xpath(xpath_expr)
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

            # --- C. XỬ LÝ CLICK & VERIFY ---
            if btn_found:
                try:
                    # robust click using shared helper (no hardcoded coords)
                    clicked = click_element(btn_found, d)
                    if not clicked:
                        # unable to click safely, retry loop
                        print("[!] Không thể click phần tử một cách an toàn, thử lại...")
                        time.sleep(0.6)
                        continue
                except Exception:
                    pass

                verify_start = time.time()
                while time.time() - verify_start < 4:
                    for s_txt in current_job.get("success_texts", []):
                        try:
                            if d(text=s_txt).exists or d(description=s_txt).exists or d.xpath(f"//*[contains(@text, '{s_txt}')]").exists:
                                return "OK"
                        except Exception:
                            pass
                    try:
                        # if the button disappeared, likely the action succeeded
                        if not btn_found.exists:
                            time.sleep(0.4)
                            for s_txt in current_job.get("success_texts", []):
                                try:
                                    if d(text=s_txt).exists or d(description=s_txt).exists:
                                        return "OK"
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    time.sleep(0.5)

                # If verify didn't find success, try one more loop (click retry)
                print("[!] Click chưa ăn, thử lại...")
                continue

            # --- D. CHECK LỖI (Fallback từ page content) ---
            for xpath_die in CONFIG.get("keywords_die_xpath", []):
                try:
                    if d.xpath(xpath_die).exists:
                        print("[!] Link Die Detected")
                        return "DIE"
                except Exception:
                    pass

            for xpath_priv in CONFIG.get("keywords_private_xpath", []):
                try:
                    if d.xpath(xpath_priv).exists:
                        print("[!] Private Content Detected")
                        return "PRIVATE"
                except Exception:
                    pass

            time.sleep(1)

        return "FAIL"
    except Exception:
        return "FAIL"

# ---------------------------
# Các hàm tương tác API
# ---------------------------
headers = {}
scraper = cloudscraper.create_scraper()

def chonacc():
    try:
        response = scraper.get('https://gateway.golike.net/api/pinterest-account', headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        print("Lỗi khi gọi chonacc:", e)
        return {"status": 500, "data": []}

def nhannv(account_id):
    try:
        params = {'account_id': account_id, 'data': 'null'}
        response = requests.get('https://gateway.golike.net/api/advertising/publishers/pinterest/jobs', params=params, headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        print("Lỗi khi gọi nhannv:", e)
        return None

def hoanthanh(ads_id, account_id):
    try:
        json_data = {'account_id': account_id, 'ads_id': ads_id}
        response = requests.post('https://gateway.golike.net/api/advertising/publishers/pinterest/complete-jobs', headers=headers, json=json_data, timeout=10)
        return response.json()
    except Exception as e:
        print("Lỗi khi gọi hoanthanh:", e)
        return None

def baoloi(ads_id, object_id, account_id, loai):
    try:
        json_data1 = {
            'description': 'Tôi đã làm Job này rồi hoặc lỗi khi thực hiện',
            'users_advertising_id': ads_id,
            'type': 'ads',
            'provider': 'tiktok',
            'fb_id': account_id,
            'error_type': 6,
        }
        try:
            scraper.post('https://gateway.golike.net/api/report/send', headers=headers, json=json_data1, timeout=6)
        except Exception:
            pass
        json_data2 = {
            'ads_id': ads_id,
            'object_id': object_id,
            'account_id': account_id,
            'type': loai,
        }
        try:
            response = requests.post('https://gateway.golike.net/api/advertising/publishers/pinterest/skip-jobs', headers=headers, json=json_data2, timeout=6)
            return response.json()
        except Exception:
            return None
    except Exception as e:
        print("Lỗi khi gửi báo lỗi:", e)
        return None

# ---------------------------
# Helper: thực hiện 1 hoặc nhiều actions (follow/like/love)
# ---------------------------
def execute_actions_on_link(serial: Optional[str], link: str, job_type_from_server: str, user_pref: int, timeout_per_action: int = 20) -> (bool, str):
    """
    Trả về (action_ok: bool, reason: str)
    - serial: thiết bị ADB (None nếu không có)
    - link: deep link
    - job_type_from_server: 'follow' | 'like' | 'both' | 'love'
    - user_pref: 1=follow only, 2=Yêu Thích (like) only, 3=both, 4=love only
    """
    # server có thể trả "favorite" -> map về "like" để giữ tương thích
    if job_type_from_server == "favorite":
        job_type_from_server = "like"

    # Xác định actions từ server
    if job_type_from_server == "both":
        server_actions = ["follow", "like"]
    else:
        server_actions = [job_type_from_server]

    # Lọc theo user_pref
    if user_pref == 1:
        need_actions = [a for a in server_actions if a == "follow"]
    elif user_pref == 2:
        need_actions = [a for a in server_actions if a == "like"]
    elif user_pref == 4:
        need_actions = [a for a in server_actions if a == "love"]
    else:
        need_actions = server_actions.copy()  # user_pref == 3 => both

    if not need_actions:
        return False, "SKIP_BY_USER_PREF"

    # Thực hiện từng action
    for action in need_actions:
        action_done = False

        # 1) Nếu có thiết bị ADB -> try perform_action_on_device
        if serial:
            try:
                status = perform_action_on_device(serial, link, action, timeout=timeout_per_action)
                if status == "OK":
                    action_done = True
                elif status in ("DIE", "PRIVATE"):
                    return False, status  # Không cố nữa, báo lỗi link
                elif status == "NO_HEART":
                    # Special: like job but no heart found -> don't fallback to save or HTTP; report and skip
                    return False, "NO_HEART"
                else:
                    # status == FAIL -> will attempt fallback for non-like actions below
                    pass
            except Exception:
                pass

        # 2) Fallback HTTP (best-effort) - BUT FOR 'like' WE DO NOT FALLBACK
        if not action_done:
            if action == "like":
                # Do not perform HTTP fallback for like jobs (we removed Save fallback).
                return False, "NO_HEART_OR_NO_ADB"
            try:
                r = requests.get(link, headers={'User-Agent': headers.get('User-Agent', 'Mozilla/5.0')}, timeout=8, allow_redirects=True)
                if r.status_code in (200, 301, 302):
                    # Fallback GET như cũ (không chắc action thực sự thành công nhưng giữ hành vi cũ)
                    action_done = True
                else:
                    action_done = False
            except Exception:
                action_done = False

        if not action_done:
            return False, "FAIL_ACTION_" + action.upper()

    return True, "OK"

# ---------------------------
# SETUP & AUTH
# ---------------------------
banner()

def ensure_auth_files_fn():
    # Kiểm tra và tạo Authorization.txt nếu chưa có
    if not os.path.exists("Authorization.txt"):
        try:
            open("Authorization.txt", "w").close()
        except Exception:
            pass
            
    # Kiểm tra và tạo token.txt nếu chưa có
    if not os.path.exists("token.txt"):
        try:
            open("token.txt", "w").close()
        except Exception:
            pass

ensure_auth_files_fn()

with open("Authorization.txt", "r", encoding="utf-8") as f:
    author = f.read().strip()
with open("token.txt", "r", encoding="utf-8") as f:
    token = f.read().strip()

if not author:
    author = input(Colorate.Diagonal(Colors.blue_to_white, " 💸 NHẬP AUTHORIZATION GOLIKE : ")).strip()
    with open("Authorization.txt", "w", encoding="utf-8") as f:
        f.write(author)
    with open("token.txt", "w", encoding="utf-8") as f:
        f.write(token)
else:
    print(Colorate.Diagonal(Colors.white_to_black, "=================================================="))
    print(Colorate.Diagonal(Colors.cyan_to_green, "Nhập [1] Để Vào Tool  "))
    print(Colorate.Diagonal(Colors.cyan_to_green, "Nhập [2] Để Thay Auth Golike Mới "))
    print(Colorate.Diagonal(Colors.white_to_black, "=================================================="))
    select = input(f"Nhập số : ").strip()
    kiem_tra_mang()
    if select == "2":
        for i in range(1, 101):
            sys.stdout.write(f"\r ĐANG TIẾN HÀNH XÓA AUTH CŨ : [{i}% {'║' * (i // 2)}]")
            sys.stdout.flush()
            sleep(0.01)
        os.system('cls' if os.name == 'nt' else 'clear')
        banner()
        author = input("Nhập Authorization Golike Mới : ").strip()
        with open("Authorization.txt", "w", encoding="utf-8") as f:
            f.write(author)
        with open("token.txt", "w", encoding="utf-8") as f:
            f.write(token)
        os.system('cls' if os.name == 'nt' else 'clear')
        banner()

headers = {
    'Accept': 'application/json, text/plain, /',
    'Content-Type': 'application/json;charset=utf-8',
    'Authorization': author,
    'T': 'VFZSak1FMTZZM3BOZWtFd1RtYzlQUT09',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
    'Referer': 'https://app.golike.net/account/manager/snapchat',
}

scraper = cloudscraper.create_scraper()
chontktiktok = chonacc()

def dsacc():
    if chontktiktok.get("status") != 200:
        print("Authorization hoăc T sai 😂")
        sys.exit(1)
    for i, d in enumerate(chontktiktok["data"]):
        clear_screen()
        banner()
        print(f"[{i+1}] {d['name']} | 🍉 Online")

dsacc()
print("==================================")

while True:
    try:
        luachon = int(input("Chọn tài khoản snapchat bạn muốn chạy 🤑: "))
        while luachon < 1 or luachon > len(chontktiktok["data"]):
            luachon = int(input("Acc Này Không Có Trong Danh Sách Cấu Hình , Nhập Lại : "))
        account_id = chontktiktok["data"][luachon - 1]["id"]
        break
    except Exception:
        print(" Sai Định Dạng ")

while True:
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
        delay = int(input(f"Delay thực hiện job (giây) 🍉 : "))
        break
    except Exception:
        print(" Sai Định Dạng ")

banner()
print("        CHỌN JOB ĐỂ LÀM KIẾM TIỀN")
print("")
print("Nhập [1] Thực Hiện NV Follow")
print("Nhập [2] Thực Hiện NV Yêu Thích")
print("Nhập [3] Thực Hiện NV Cả Follow + Yêu Thích")
print("Nhập [4] Thực Hiện NV Yêu Thích (Thả tim)")

while True:
    try:
        loai_nhiem_vu = int(input("Chọn loại nv cần kiếm tiền (1=Follow,2=Yêu Thích,3=Cả 2,4=Thả tim) : "))
        if loai_nhiem_vu in [1, 2, 3, 4]:
            break
        else:
            print("Vui lòng chọn số 1, 2, 3 hoặc 4")
    except Exception:
        print("Sai định dạng! Vui lòng nhập số.")

# Chọn thiết bị ADB
selected_device_serial = device_manager_select()
if selected_device_serial:
    print(f"[✔] Đã chọn thiết bị: {selected_device_serial}")
else:
    print(f"[!] Không chọn thiết bị ADB — script sẽ fallback truy cập link bằng HTTP (requests).")
time.sleep(1.2)

dem = 0
tong = 0
dsaccloi = []
accloi = ""
checkdoiacc = 0
os.system('cls' if os.name == 'nt' else 'clear')

banner()
print("")

# ---------------------------
# MAIN LOOP
# ---------------------------
while True:
    print(' ĐANG TÌM JOB KIẾM TIỀN 🍉 ', end="\r")
    max_retries = 3
    retry_count = 0
    nhanjob = None
    while retry_count < max_retries:
        try:
            nhanjob = nhannv(account_id)
            if nhanjob and nhanjob.get("status") == 200 and nhanjob["data"].get("link") and nhanjob["data"].get("object_id"):
                break
            else:
                retry_count += 1
                time.sleep(2)
        except Exception:
            retry_count += 1
            time.sleep(1)

    if not nhanjob or retry_count >= max_retries:
        time.sleep(1)
        continue

    # LẤY THÔNG TIN JOB
    ads_id = nhanjob["data"]["id"]
    link = nhanjob["data"]["link"]
    object_id = nhanjob["data"]["object_id"]
    job_type = nhanjob["data"].get("type", "")

    # ACCEPT both naming: nếu server gửi "favorite" thì map về "like"
    if job_type == "favorite":
        job_type = "like"

    # CHẤP NHẬN: follow | like | both | love
    if job_type not in ["follow", "like", "both", "love"]:
        baoloi(ads_id, object_id, account_id, job_type)
        continue

    # Nếu user chỉ muốn Follow (1) hoặc Yêu Thích (2) hoặc Thả tim (4), bỏ qua job không phù hợp
    if loai_nhiem_vu == 1 and job_type == "like":
        baoloi(ads_id, object_id, account_id, job_type)
        continue
    if loai_nhiem_vu == 2 and job_type == "follow":
        baoloi(ads_id, object_id, account_id, job_type)
        continue
    if loai_nhiem_vu == 4 and job_type in ["follow", "like", "both"]:
        # user chọn Thả tim nhưng job không phải love
        baoloi(ads_id, object_id, account_id, job_type)
        continue

    # Delay trước khi chạy
    for remaining_time in range(delay, -1, -1):
        color = "\033[1;35m" if remaining_time % 2 == 0 else "\033[1;36m"
        print(f"\r{color} NP-TOOL Kiếm Tiền Online 🍉 [{remaining_time}s]   ", end="")
        time.sleep(1)
    print("\r                          \r", end="")

    print(" Đang thực hiện hành động trên link... ", end="\r")

    # Thực hiện actions (có thể 1 hoặc 2 hành động)
    action_ok = False
    try:
        action_ok, reason = execute_actions_on_link(selected_device_serial, link, job_type, loai_nhiem_vu)
        if not action_ok:
            if reason in ("DIE", "PRIVATE", "NO_HEART", "NO_HEART_OR_NO_ADB"):
                print(f" Bỏ qua do: {reason}", end="\r")
            elif reason == "SKIP_BY_USER_PREF":
                print(f" Bỏ qua do không phù hợp preference người dùng ({reason})", end="\r")
            else:
                print(f" Thực hiện thất bại: {reason}", end="\r")
    except Exception:
        action_ok = False

    if not action_ok:
        # Báo lỗi và skip job (theo flow hiện tại)
        baoloi(ads_id, object_id, account_id, job_type)
        print(" Không thể truy cập link hoặc lỗi → Bỏ qua job", end="\r")
        sleep(1.2)
        continue

    # Hoàn thành job
    max_attempts = 2
    attempts = 0
    nhantien = None
    while attempts < max_attempts:
        try:
            nhantien = hoanthanh(ads_id, account_id)
            if nhantien and nhantien.get("status") == 200:
                break
        except Exception:
            pass
        attempts += 1
        time.sleep(1)

    if nhantien and nhantien.get("status") == 200:
        dem += 1
        tien = nhantien["data"].get("prices", 0)
        try:
            tien = int(tien)
        except Exception:
            try:
                tien = int(float(tien))
            except Exception:
                tien = 0
        tong += tien
        thoigian = time.strftime("%H:%M:%S", time.localtime())
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("STT", style="bold yellow")
        table.add_column("Thời gian", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Tiền ", style="bold green")
        table.add_column("Tổng Tiền", style="bold white")
        table.add_row(
            str(dem),
            thoigian,
            "[green]SUCCESS[/green]",
            f"[bold green]+{tien}đ",
            f"[bold yellow]{tong} vnđ"
        )

        os.system('cls' if os.name == 'nt' else 'clear')
        banner()
        console.print(table)
        time.sleep(0.7)
        checkdoiacc = 0
    else:
        try:
            baoloi(ads_id, object_id, account_id, job_type)
            print(" Bỏ qua job lỗi thành công 🍉", end="\r")
            sleep(1.5)
            checkdoiacc += 1
        except Exception:
            pass
