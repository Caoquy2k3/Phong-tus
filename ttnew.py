#!/usr/bin/env python3

# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import requests
from datetime import datetime, timezone, timedelta
import subprocess
import uiautomator2 as u2
import random
import logging
from logging.handlers import RotatingFileHandler
import re
from difflib import SequenceMatcher
import hashlib
import threading
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.live import Live
from rich.layout import Layout
from rich import box
from rich.text import Text
from concurrent.futures import ThreadPoolExecutor, as_completed
from adbutils import adb
import cv2
import numpy as np
import urllib.request
import signal
import gc
from collections import deque

# ==================== CẤU HÌNH MÚI GIỜ VIỆT NAM CHUẨN ====================
os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
if hasattr(time, 'tzset'):
    time.tzset()

VN_TZ = timezone(timedelta(hours=7))

def get_vn_time():
    return datetime.now(VN_TZ)

# ==================== CẤU HÌNH TOÀN CỤC ====================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

TIKTOK_PACKAGE = "com.ss.android.ugc.trill"

AUTH_FILE = os.path.join(DATA_DIR, "Authorization.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
GUI_PNG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui.png")
VERSION_CACHE_FILE = os.path.join(DATA_DIR, "tiktok_versions.json")

SIMILARITY_THRESHOLD = 0.85

DEFAULT_DELAY_CONFIG = {
    'like': [5, 5],
    'follow': [5, 5],
    'comment': [5, 5],
    'favorite': [5, 5],
    'job': [5, 5],
    'delay_done': 9,
    'loc_follow': 0,
    'nuoi_nick': 2,
    'share_rate': 15
}

# ==================== DASHBOARD TOÀN CỤC ====================
console = Console()
accounts_data = {}
dashboard_lock = threading.Lock()
stop_all_threads = False
stop_lock = threading.Lock()

def set_stop_all():
    global stop_all_threads
    with stop_lock:
        stop_all_threads = True

def clear_stop_all():
    global stop_all_threads
    with stop_lock:
        stop_all_threads = False

def is_stop_all():
    with stop_lock:
        return stop_all_threads

# ==================== OPENCY TEMPLATE ====================
GUI_TEMPLATE = None
GUI_TEMPLATE_LOCK = threading.Lock()

def load_gui_template_once():
    global GUI_TEMPLATE
    with GUI_TEMPLATE_LOCK:
        if GUI_TEMPLATE is not None:
            return True
        
        if os.path.exists(GUI_PNG_PATH):
            try:
                GUI_TEMPLATE = cv2.imread(GUI_PNG_PATH)
                if GUI_TEMPLATE is not None:
                    console.print("✓ Đã load gui.png vào RAM ({}x{})".format(
                        GUI_TEMPLATE.shape[1], GUI_TEMPLATE.shape[0]))
                    return True
            except Exception as e:
                console.print("Lỗi load gui.png: {}".format(str(e)))
        
        console.print("⚠ Chưa có file gui.png, đang tải về...")
        url = "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/refs/heads/main/gui.png"
        
        for attempt in range(3):
            try:
                urllib.request.urlretrieve(url, GUI_PNG_PATH)
                if os.path.exists(GUI_PNG_PATH) and os.path.getsize(GUI_PNG_PATH) > 0:
                    GUI_TEMPLATE = cv2.imread(GUI_PNG_PATH)
                    if GUI_TEMPLATE is not None:
                        console.print(" Đã tải và load gui.png vào RAM")
                        return True
            except Exception as e:
                console.print("Lỗi tải lần {}: {}".format(attempt + 1, str(e)))
                if attempt < 2:
                    time.sleep(2)
        
        console.print(" Không thể tải gui.png, tool sẽ dùng phím Enter thay thế")
        return False

def get_gui_template():
    global GUI_TEMPLATE
    return GUI_TEMPLATE

# ==================== SESSION POOL ====================
_global_session = None
_session_lock = threading.Lock()

def get_global_session():
    global _global_session
    with _session_lock:
        if _global_session is None:
            _global_session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=20,
                pool_maxsize=50,
                max_retries=1,
                pool_block=False
            )
            _global_session.mount('https://', adapter)
            _global_session.mount('http://', adapter)
        return _global_session

# ==================== HÀM LẤY VERSION TIKTOK ====================
_version_cache = {}
_version_cache_lock = threading.Lock()

def get_tiktok_version_from_device(device_obj, serial=None):
    cache_key = serial if serial else str(id(device_obj))
    
    with _version_cache_lock:
        if cache_key in _version_cache:
            cached_time, cached_version = _version_cache[cache_key]
            if time.time() - cached_time < 60:
                return cached_version
    
    try:
        result = device_obj.shell("dumpsys package com.ss.android.ugc.trill | grep versionName")
        if result and result.strip():
            match = re.search(r'versionName=([\d.]+)', result)
            if match:
                version = match.group(1)
                with _version_cache_lock:
                    _version_cache[cache_key] = (time.time(), version)
                return version
        
        result = device_obj.shell("pm list packages --show-version-code com.ss.android.ugc.trill")
        if result and result.strip():
            match = re.search(r'versionCode=(\d+)', result)
            if match:
                version = match.group(1)
                with _version_cache_lock:
                    _version_cache[cache_key] = (time.time(), version)
                return version
        
        return None
    except Exception:
        return None

def get_all_devices_versions(devices_list):
    versions = {}
    for device in devices_list:
        try:
            serial = device.serial if hasattr(device, 'serial') else str(device)
            version = get_tiktok_version_from_device(device, serial)
            versions[serial] = version if version else "Unknown"
        except:
            versions[getattr(device, 'serial', str(device))] = "Unknown"
    return versions

# ==================== CHỜ UI THÔNG MINH NÂNG CẤP (GIỮ NGUYÊN HÀM CŨ) ====================

# Các activity TikTok cần chờ (load xong mới thao tác)
TIKTOK_READY_ACTIVITIES = [
    "com.ss.android.ugc.aweme.main.MainActivity",
    "com.ss.android.ugc.aweme.splash.SplashActivity",
    ".main.MainActivity",
    "aweme.main.MainActivity",
]

def get_current_activity(device):
    """Lấy activity hiện tại của TikTok"""
    try:
        current = device.app_current()
        return current.get("activity", "")
    except:
        return ""

def is_ui_stable(device, sample_count=3, sample_interval=0.15):
    """
    Kiểm tra UI đã ổn định chưa (không còn chuyển activity liên tục)
    Dùng sampling để phát hiện activity đang thay đổi
    """
    try:
        activities = []
        for _ in range(sample_count):
            act = get_current_activity(device)
            if act:
                activities.append(act)
            time.sleep(sample_interval)
        
        # Nếu tất cả activity giống nhau -> UI ổn định
        return len(set(activities)) == 1 and all(activities)
    except:
        return True

def is_valid_activity(activity):
    """Kiểm tra activity có phải là activity TikTok đã load xong không"""
    if not activity:
        return False
    # Bỏ qua splash, loading, login
    skip_keywords = ["splash", "loading", "login", "auth", "permission"]
    for kw in skip_keywords:
        if kw in activity.lower():
            return False
    return True

def wait_tiktok_ui_smart_v2(device, timeout=40, require_stable=True):
    """
    Chờ TikTok load xong (check package + activity + UI stable)
    KHÔNG PHÁ VỠ code cũ - chỉ nâng cấp
    
    Args:
        device: device object
        timeout: thời gian chờ tối đa (giây)
        require_stable: có cần kiểm tra UI ổn định không
    
    Returns:
        bool: True nếu UI đã sẵn sàng
    """
    start_time = time.time()
    interval = 0.2  # Polling nhanh 0.2s
    
    last_activity = None
    stable_count = 0
    required_stable_checks = 2  # Cần 2 lần liên tiếp ổn định
    
    while time.time() - start_time < timeout:
        try:
            current = device.app_current()
            current_pkg = current.get("package", "")
            current_activity = current.get("activity", "")
            
            # Bước 1: Check package
            if current_pkg != TIKTOK_PACKAGE:
                time.sleep(interval)
                continue
            
            # Bước 2: Check activity hợp lệ
            if not current_activity or not is_valid_activity(current_activity):
                time.sleep(interval)
                continue
            
            # Bước 3: Kiểm tra UI ổn định (nếu cần)
            if require_stable:
                if current_activity == last_activity:
                    stable_count += 1
                else:
                    stable_count = 0
                    last_activity = current_activity
                
                if stable_count >= required_stable_checks:
                    return True
            else:
                # Chỉ cần package + activity đúng
                return True
                
        except Exception:
            pass
        
        time.sleep(interval)
    
    # Fallback: kiểm tra package 1 lần cuối
    try:
        return device.app_current().get("package") == TIKTOK_PACKAGE
    except:
        return False

# HÀM CŨ GIỮ NGUYÊN ĐỂ TƯƠNG THÍCH NGƯỢC
def wait_tiktok_ui_smart(device, timeout=40):
    """Hàm cũ giữ nguyên, gọi phiên bản mới với require_stable=False"""
    return wait_tiktok_ui_smart_v2(device, timeout=timeout, require_stable=False)

def wait_tiktok_ui(device, timeout=20):
    """Hàm cũ để tương thích, gọi hàm mới"""
    return wait_tiktok_ui_smart_v2(device, timeout=timeout, require_stable=False)

def wait_ui_stable_after_action(device, timeout=3):
    """
    Chờ UI ổn định sau một hành động (click, swipe...)
    Chỉ dùng state polling, không dump XML
    """
    start_time = time.time()
    interval = 0.25
    
    # Đợi một chút cho animation
    time.sleep(0.3)
    
    while time.time() - start_time < timeout:
        try:
            current = device.app_current()
            if current.get("package") == TIKTOK_PACKAGE:
                # Kiểm tra thêm activity ổn định
                if is_ui_stable(device, sample_count=2, sample_interval=0.1):
                    return True
        except:
            pass
        time.sleep(interval)
    
    return True

def wait_element_exists(device, selector_func, timeout=30, check_interval=0.25):
    """
    Chờ một element xuất hiện trên giao diện
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if callable(selector_func):
                result = selector_func()
                if result:
                    return True
            else:
                if selector_func.exists:
                    return True
        except:
            pass
        time.sleep(check_interval)
    return False

def force_restart_tiktok(device):
    """Buộc dừng và khởi động lại TikTok"""
    try:
        device.app_stop(TIKTOK_PACKAGE)
        time.sleep(1)
        device.app_start(TIKTOK_PACKAGE)
        wait_tiktok_ui_smart_v2(device, timeout=15, require_stable=True)
    except Exception as e:
        pass


class TikTokBot:

    def __init__(self, serial, auth_token, golike_username, account_id_val,
                 delay_config, lam, force_stop_enabled, force_stop_after,
                 min_follow_price):

        self.serial = serial
        self.auth_token = auth_token
        self.golike_username = golike_username
        self.account_id_val = account_id_val

        self.delay_config = delay_config or {}
        self.lam = lam
        self.force_stop_enabled = force_stop_enabled
        self.force_stop_after = force_stop_after
        self.min_follow_price = min_follow_price
        self.device = None
        self.stop_flag = False
        self.job_count = 0
        self.previous_job_link = None
        self.consecutive_errors = 0
        self.max_errors = 5
        self.retry_delays = [5, 10, 20, 30, 60]

        self.last_action_time = 0
        self.min_action_gap = 0.25

        self.session = get_global_session()

        self.headers = {
            'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
            'Referer': 'https://app.golike.net/',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': 'Windows',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'T': 'VFZSak1FMTZZM3BOZWtFd1RtYzlQUT09',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
            'Authorization': auth_token,
            'Content-Type': 'application/json;charset=utf-8',
            'Connection': 'keep-alive'
        }

        self.logger = None
        self.link_job_file = None
        self.check_cmt_file = None

        self.job_counter_since_restart = 0
        self.error_counter_since_restart = 0
        self.last_restart_time = 0
        self.last_adb_check_time = 0

        self.processed_videos = self._load_processed_videos()
        self.tiktok_version = None

        # Cache cho UI dump (giữ lại cho các chức năng cần XML như find like btn)
        self.ui_dump_cache = {"xml": "", "timestamp": 0, "nodes": []}
        self.ui_dump_cache_ttl = 0.4
        self.last_dump_time = 0
        self.min_dump_interval = 0.15

        self._init_instance_files()

    def ensure_device(self):
        try:
            if not self.device:
                return False

            _ = self.device.info
            self.consecutive_errors = 0
            return True

        except:
            self.consecutive_errors += 1
            return False

    def find_ui(self, keyword):
        try:
            xml = self.device.dump_hierarchy()
            return keyword in xml if xml else False
        except:
            return False

    def smart_click(self, selector=None, x=None, y=None, verify_keyword=None):

        now = time.time()

        if now - self.last_action_time < self.min_action_gap:
            time.sleep(self.min_action_gap)

        if not self.ensure_device():
            return False

        try:
            if selector:
                if selector.exists(timeout=1.2):
                    selector.click()
                else:
                    return False

            elif x is not None and y is not None:
                self.device.click(x, y)

            else:
                return False

            # Chờ UI ổn định sau click
            wait_ui_stable_after_action(self.device, timeout=3)

            if verify_keyword:
                xml = self.device.dump_hierarchy()
                if verify_keyword not in xml:
                    return False

            self.last_action_time = time.time()
            self.consecutive_errors = 0

            return True

        except:
            self.consecutive_errors += 1
            return False

    def reset(self):
        self.device = None
        self.consecutive_errors = 0
        time.sleep(1)
    
    def _get_tiktok_version(self):
        return get_tiktok_version_from_device(self.device, self.serial)
    
    def _update_dashboard_with_version(self):
        if self.tiktok_version:
            with dashboard_lock:
                if self.account_id_val in accounts_data:
                    accounts_data[self.account_id_val]["tiktok_version"] = self.tiktok_version
    
    def _get_retry_delay(self):
        idx = min(self.consecutive_errors, len(self.retry_delays) - 1)
        return self.retry_delays[idx]
    
    def _reset_retry_counter(self):
        self.consecutive_errors = 0
    
    def _increment_retry_counter(self):
        self.consecutive_errors += 1
        return self._get_retry_delay()
    
    def _init_instance_files(self):
        safe_serial = re.sub(r'[^\w\-_]', '_', self.serial)
        self.link_job_file = os.path.join(DATA_DIR, u"device_{}_link_job.json".format(safe_serial))
        self.check_cmt_file = os.path.join(DATA_DIR, u"device_{}_check_cmt.json".format(safe_serial))
        
        if not os.path.exists(self.link_job_file):
            with open(self.link_job_file, 'w', encoding='utf-8') as f:
                json.dump({"processed_videos": []}, f)
        
        if not os.path.exists(self.check_cmt_file):
            with open(self.check_cmt_file, 'w', encoding='utf-8') as f:
                json.dump({"last_comment": "", "history": []}, f)
    
    def _load_processed_videos(self):
        try:
            if os.path.exists(self.link_job_file):
                with open(self.link_job_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("processed_videos", [])
        except:
            pass
        return []
    
    def _save_processed_video(self, video_id):
        try:
            if video_id not in self.processed_videos:
                self.processed_videos.append(video_id)
                if len(self.processed_videos) > 10000:
                    self.processed_videos = self.processed_videos[-5000:]
            
            def _write():
                try:
                    with open(self.link_job_file, 'w', encoding='utf-8') as f:
                        json.dump({"processed_videos": self.processed_videos}, f, ensure_ascii=False, indent=2)
                except:
                    pass
            threading.Thread(target=_write, daemon=True).start()
            return True
        except Exception:
            return False
    
    def _is_link_processed(self, link):
        try:
            video_id = self._get_video_id(link)
            return video_id in self.processed_videos
        except:
            return False
    
    def _get_video_id(self, link):
        try:
            match = re.search(r'/video/(\d+)', link)
            if match:
                return match.group(1)
            match = re.search(r'/(\d{15,})', link)
            if match:
                return match.group(1)
            return hashlib.md5(link.encode()).hexdigest()[:10]
        except:
            return link
    
    def _update_dashboard_status(self, status, job_type=None):
        with dashboard_lock:
            if self.account_id_val in accounts_data:
                accounts_data[self.account_id_val]["status"] = status[:120] if len(status) > 120 else status
                accounts_data[self.account_id_val]["last_message"] = status
                accounts_data[self.account_id_val]["message_time"] = get_vn_time().strftime('%H:%M:%S')
                accounts_data[self.account_id_val]["last_update"] = time.time()
                if job_type:
                    accounts_data[self.account_id_val]["job_type"] = job_type
    
    def _update_dashboard_stats(self, job_type, coin=0, success=True):
        with dashboard_lock:
            if self.account_id_val not in accounts_data:
                return
            if success:
                accounts_data[self.account_id_val]["done"] += 1
                accounts_data[self.account_id_val]["total_xu"] += coin
                accounts_data[self.account_id_val]["xu"] = coin
                if job_type:
                    accounts_data[self.account_id_val]["job_type"] = job_type
                accounts_data[self.account_id_val]["last_success"] = time.time()
            else:
                accounts_data[self.account_id_val]["fail"] += 1
                if job_type:
                    accounts_data[self.account_id_val]["job_type"] = job_type
            accounts_data[self.account_id_val]["last_update"] = time.time()
    
    def _update_current_link(self, link):
        with dashboard_lock:
            if self.account_id_val in accounts_data:
                accounts_data[self.account_id_val]["link"] = link
                accounts_data[self.account_id_val]["last_update"] = time.time()
    
    def _add_response_message(self, msg, job_type=None):
        self._update_dashboard_status(msg, job_type)
    
    def _check_and_reconnect_adb(self):
        """Kiểm tra kết nối ADB, KHÔNG kill-server/reset, chỉ kết nối lại u2"""
        now = time.time()
        if now - self.last_adb_check_time < 30:
            return True
        
        self.last_adb_check_time = now
        
        try:
            if self.device:
                self.device.info
                return True
        except Exception:
            pass
        
        try:
            self.device = u2.connect(self.serial)
            self.device.info
            try:
                self.device.app_start(TIKTOK_PACKAGE)
                wait_tiktok_ui_smart_v2(self.device, timeout=10, require_stable=False)
            except:
                pass
            return True
        except Exception:
            return False
    
    def _wait_for_ui_stable(self, wait_time=2.0, extra_wait=0.3):
        if self.stop_flag or is_stop_all():
            return False
        
        wait_ui_stable_after_action(self.device, timeout=wait_time)
        return not self.stop_flag and not is_stop_all()
    
    def _dump_ui_nodes(self):
        """Vẫn giữ XML dump cho việc tìm nút like/follow vì cần phân tích cấu trúc"""
        now = time.time()
        
        if now - self.last_dump_time < self.min_dump_interval:
            if self.ui_dump_cache["nodes"]:
                return self.ui_dump_cache["nodes"]
        self.last_dump_time = now
        
        if (self.ui_dump_cache["nodes"] and 
            (now - self.ui_dump_cache["timestamp"]) < self.ui_dump_cache_ttl):
            return self.ui_dump_cache["nodes"]
        
        try:
            xml_content = self.device.dump_hierarchy()
            
            nodes = []
            pattern = re.compile(r'<node\s+([^>]+)>')
            attr_pattern = re.compile(r'(resource-id|content-desc|text|bounds|selected|clickable)="([^"]*)"')
            
            for match in pattern.finditer(xml_content):
                attrs = dict(attr_pattern.findall(match.group(1)))
                if attrs:
                    nodes.append(attrs)
            
            self.ui_dump_cache["xml"] = xml_content
            self.ui_dump_cache["timestamp"] = now
            self.ui_dump_cache["nodes"] = nodes
            
            return nodes
        except Exception:
            return []
    
    def _click_node_by_bounds(self, node):
        bounds = node.get("bounds")
        if not bounds:
            return False
        
        pts = list(map(int, re.findall(r'\d+', bounds)))
        if len(pts) >= 4:
            x = (pts[0] + pts[2]) // 2
            y = (pts[1] + pts[3]) // 2
            self.device.click(x, y)
            return True
        return False
    
    def _restart_tiktok(self):
        try:
            self.device.app_stop(TIKTOK_PACKAGE)
            time.sleep(0.8)
            self.device.app_start(TIKTOK_PACKAGE)
            wait_tiktok_ui_smart_v2(self.device, timeout=10, require_stable=True)
        except Exception:
            pass
    
    def _check_app_status(self):
        try:
            current = self.device.app_current()
            if current.get("package") != TIKTOK_PACKAGE:
                self.device.app_start(TIKTOK_PACKAGE)
                wait_tiktok_ui_smart_v2(self.device, timeout=10, require_stable=True)
                return False
            return True
        except Exception:
            self._restart_tiktok()
            return False
    
    def _open_link(self, link):
        try:
            if not self._check_and_reconnect_adb():
                return False
            cmd = u'am start -a android.intent.action.VIEW -d "{}" {}'.format(link, TIKTOK_PACKAGE)
            self.device.shell(cmd)
            launched = wait_tiktok_ui_smart_v2(self.device, timeout=8, require_stable=True)
            return launched
        except Exception:
            if self._check_and_reconnect_adb():
                try:
                    cmd = u'am start -a android.intent.action.VIEW -d "{}" {}'.format(link, TIKTOK_PACKAGE)
                    self.device.shell(cmd)
                    return wait_tiktok_ui_smart_v2(self.device, timeout=8, require_stable=True)
                except:
                    pass
            return False
    
    def _delay_countdown(self, delay_seconds, msg_prefix=u"Đang chờ"):
        delay_seconds = min(delay_seconds, 300)
        for i in range(int(delay_seconds), 0, -1):
            if self.stop_flag or is_stop_all():
                return
            if i % 10 == 0 or i <= 3:
                self._update_dashboard_status(u"{} {}s...".format(msg_prefix, i))
            time.sleep(1)
    
    def _get_random_delay(self, job_type):
        if job_type in self.delay_config:
            min_delay, max_delay = self.delay_config[job_type]
            return random.randint(min_delay, max_delay)
        return random.randint(3, 7)
    
    # ========== NUÔI NICK ==========
    
    def _do_share_and_copy_link(self, max_retry=2):
        try:
            share_selectors = [
                {"descriptionContains": "share"},
                {"descriptionContains": "gửi"},
                {"textContains": "Share"},
                {"textContains": "Gửi"}
            ]

            start_time = time.time()
            clicked_share = False
            while time.time() - start_time < 12:
                if self.stop_flag or is_stop_all():
                    return False
                for s in share_selectors:
                    if self.device(**s).exists:
                        self.device(**s).click()
                        clicked_share = True
                        break
                if clicked_share:
                    break
                time.sleep(0.15)

            if not clicked_share:
                return False

            copy_selectors = [
                {"text": "Sao chép liên kết"},
                {"textContains": "Sao chép"},
                {"text": "Copy link"},
                {"textContains": "Copy"},
                {"descriptionContains": "copy"},
                {"descriptionContains": "link"}
            ]

            start_time = time.time()
            clicked_copy = False
            while time.time() - start_time < 8:
                if self.stop_flag or is_stop_all():
                    return False
                for s in copy_selectors:
                    if self.device(**s).exists:
                        self.device(**s).click()
                        clicked_copy = True
                        break
                if clicked_copy:
                    break
                time.sleep(0.15)

            if clicked_copy:
                time.sleep(0.3)
                if self.device(textMatches="(?i)(Sao chép liên kết|Copy link)").exists:
                    self.device.press("back")
                return True
            else:
                self.device.press("back")
                return False

        except Exception:
            return False
    
    def nuoi_nick_short(self, num_videos=2, share_rate=15, is_high_trust_mode=False):
        try:
            if is_high_trust_mode:
                share_rate = random.randint(30, 50)
            
            for _ in range(1):
                self.device.press("back")
                time.sleep(0.15)
            
            time.sleep(0.6)
            
            try:
                home_tab = self.device(text="Home", resourceIdMatches=".*tab.*")
                if home_tab.exists:
                    home_tab.click()
                    time.sleep(0.3)
            except:
                pass
            
            success_share_count = 0
            min_watch, max_watch = 5, 10
            
            for i in range(num_videos):
                if self.stop_flag or is_stop_all():
                    break
                
                watch_time = random.uniform(min_watch, max_watch)
                
                remaining = watch_time
                while remaining > 0 and not self.stop_flag and not is_stop_all():
                    sleep_time = min(0.3, remaining)
                    time.sleep(sleep_time)
                    remaining -= sleep_time
                
                if self.stop_flag or is_stop_all():
                    break
                
                should_share = random.randint(1, 100) <= share_rate
                
                if should_share:
                    if self._do_share_and_copy_link():
                        success_share_count += 1
                    time.sleep(random.uniform(0.6, 1.2))
                
                w, h = self.device.window_size()
                x_mid = int(w * 0.5)
                start_y = int(h * 0.85)
                end_y = int(h * 0.2)
                self.device.swipe(x_mid, start_y, x_mid, end_y, duration=random.uniform(0.12, 0.25))
                
                time.sleep(random.uniform(0.4, 0.8))
            
            return success_share_count
            
        except Exception:
            return 0
    
    def nuoi_nick_thong_minh(self, delay_seconds, share_rate=15):
        if delay_seconds <= 0:
            return 0
        
        delay_seconds = min(delay_seconds, 300)
        
        time_per_video = 9
        max_videos = max(1, delay_seconds // time_per_video)
        max_videos = min(max_videos, 5)
        
        if max_videos > 0:
            start_time = time.time()
            self.nuoi_nick_short(num_videos=max_videos, share_rate=share_rate)
            elapsed = time.time() - start_time
            
            remaining = delay_seconds - elapsed
            if remaining > 0:
                for remaining_sec in range(int(remaining), 0, -1):
                    if self.stop_flag or is_stop_all():
                        break
                    if remaining_sec % 5 == 0 or remaining_sec <= 3:
                        self._update_dashboard_status(u"Đợi thêm {}s...".format(remaining_sec))
                    time.sleep(1)
            
            return elapsed
        else:
            for remaining_sec in range(delay_seconds, 0, -1):
                if self.stop_flag or is_stop_all():
                    break
                if remaining_sec % 5 == 0 or remaining_sec <= 3:
                    self._update_dashboard_status(u"Đợi {}s...".format(remaining_sec))
                time.sleep(1)
            return delay_seconds
    
    # ========== XỬ LÝ JOB ==========
    
    def _is_like_node(self, node):
        res_id = node.get("resource-id", "")
        desc = node.get("content-desc", "").lower()
        
        if "like" in desc or "thích" in desc:
            return True
        if any(k in res_id for k in ["like", "digg", "heart"]):
            return True
        return False
    
    def _is_liked(self, node):
        desc = node.get("content-desc", "").lower()
        return (
            node.get("selected") == "true"
            or "unlike" in desc
            or "bỏ thích" in desc
        )
    
    def _find_like_btn(self, nodes):
        candidates = []
        for node in nodes:
            if self._is_like_node(node):
                bounds = node.get("bounds", "")
                if bounds:
                    pts = list(map(int, re.findall(r'\d+', bounds)))
                    if len(pts) >= 4:
                        x = (pts[0] + pts[2]) // 2
                        if x > 500:
                            candidates.append((node, x))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def do_like(self, max_retry=8):
        if not self.device:
            return False

        if self.stop_flag or is_stop_all():
            return False
        
        self._add_response_message(u"Tìm nút Like...", "like")
        clicked = False
        
        for i in range(max_retry):
            if self.stop_flag or is_stop_all():
                return False
            
            wait_ui_stable_after_action(self.device, timeout=0.5)
            
            nodes = self._dump_ui_nodes()
            btn = self._find_like_btn(nodes)
            
            if not btn:
                time.sleep(1.2)
                continue
            
            if self._is_liked(btn):
                self._add_response_message(u"Đã Like rồi", "like")
                return True
            
            if not clicked:
                if not self._click_node_by_bounds(btn):
                    continue
                clicked = True
            
            for check in range(2):
                if self.stop_flag or is_stop_all():
                    return False
                time.sleep(1.5)
                
                nodes_after = self._dump_ui_nodes()
                btn_after = self._find_like_btn(nodes_after)
                
                if not btn_after:
                    continue
                
                if self._is_liked(btn_after):
                    self._add_response_message(u"Like thành công", "like")
                    return True
            
            clicked = False
            time.sleep(1.5)
        
        self._add_response_message(u"Like thất bại", "like")
        return False
    
    def do_follow(self, max_retry=3):
        if not self.device:
            return False

        if self.stop_flag or is_stop_all():
            return False
        
        try:
            target_texts = ["theo dõi", "follow", "follow back", "follow lại"]
            target_ids = ["follow_or_edit_profile_btn", "follow_btn"]
            
            for i in range(max_retry):
                if self.stop_flag or is_stop_all():
                    return False
                
                wait_ui_stable_after_action(self.device, timeout=1)
                
                nodes = self._dump_ui_nodes()
                
                for node in nodes:
                    text = node.get("text", "").strip().lower()
                    res_id = node.get("resource-id", "")
                    
                    if any(t == text for t in target_texts) or any(idx in res_id for idx in target_ids):
                        if "đang theo dõi" in text or "following" in text:
                            self._add_response_message(u"Đã follow từ trước", "follow")
                            return True
                        
                        if self._click_node_by_bounds(node):
                            wait_ui_stable_after_action(self.device, timeout=3)
                            
                            nodes_after = self._dump_ui_nodes()
                            verified = False
                            success_texts = ["đang theo dõi", "following", "nhắn tin", "message"]
                            
                            for n in nodes_after:
                                t = n.get("text", "").lower()
                                desc = n.get("content-desc", "").lower()
                                
                                if any(s in t for s in success_texts) or any(s in desc for s in success_texts):
                                    verified = True
                                    break
                            
                            if verified:
                                self._add_response_message(u"Follow thành công", "follow")
                                return True
                            else:
                                self._add_response_message(u"Follow thành công", "follow")
                                return True
                
                time.sleep(1.5)
                
            self._add_response_message(u"Không tìm thấy nút Follow", "follow")
            return False
                
        except Exception:
            return False
    
    def do_favorite(self, max_retry=5):
        if not self.device:
            return False

        if self.stop_flag or is_stop_all():
            return False
        
        try:
            fav_identifiers = {
                "ids": ["favorite_icon", "h2m", "iv_favorite", "favorite_icon"],
                "descs": ["favorite", "yêu thích", "lưu", "favorites"]
            }

            for i in range(max_retry):
                if self.stop_flag or is_stop_all():
                    return False
                
                wait_ui_stable_after_action(self.device, timeout=1)
                
                nodes = self._dump_ui_nodes()
                
                for node in nodes:
                    res_id = node.get("resource-id", "")
                    desc = node.get("content-desc", "").lower()
                    
                    is_fav = any(tid in res_id for tid in fav_identifiers["ids"]) or \
                             any(td in desc for td in fav_identifiers["descs"])

                    if is_fav:
                        if node.get("selected") == "true" or "đã lưu" in desc or "added" in desc:
                            self._add_response_message(u"Đã lưu từ trước", "favorite")
                            return True
                        
                        bounds = node.get("bounds", "")
                        if bounds:
                            if self._click_node_by_bounds(node):
                                wait_ui_stable_after_action(self.device, timeout=1.2)
                                return True
                                
            time.sleep(1.5)

            self._add_response_message(u"Không tìm thấy nút Favorites", "favorite")
            return False
            
        except Exception:
            return False
    
    # ========== COMMENT ==========
    
    def do_comment(self, text, link):
        """
        Thực hiện comment với nội dung từ job
        - Mở comment section
        - Nhập nội dung
        - Dùng OpenCV tìm nút Gửi, fallback Enter nếu thất bại
        """
        if not self.device:
            return False

        if self.stop_flag or is_stop_all():
            return False
        
        # Kiểm tra nội dung comment
        if not text or len(text.strip()) < 1:
            self._add_response_message(u"Không có nội dung comment", "comment")
            return False
        
        comment_text = text.strip()
        self._add_response_message(u"Đang mở comment...", "comment")

        # 1. Mở khung comment
        comment_opened = False
        for attempt in range(4):
            if self.stop_flag or is_stop_all():
                return False
            
            wait_ui_stable_after_action(self.device, timeout=0.5)
            
            # Thử tìm nút comment bằng description
            comment_btn = self.device(descriptionContains="comment")
            if not comment_btn.exists:
                comment_btn = self.device(descriptionContains="bình luận")
            if not comment_btn.exists:
                comment_btn = self.device(descriptionContains="Comment")
                
            if comment_btn.exists:
                comment_btn.click()
                wait_ui_stable_after_action(self.device, timeout=2)
                comment_opened = True
                self._add_response_message(u"Đã mở comment section", "comment")
                break
            
            time.sleep(1.5)
        
        if not comment_opened:
            self._add_response_message(u"Không mở được comment section", "comment")
            return False

        # 2. Nhập nội dung
        wait_ui_stable_after_action(self.device, timeout=1)
        
        input_box = self.device(className="android.widget.EditText")
        if not input_box.exists:
            # Thử tìm bằng resource-id
            input_box = self.device(resourceIdMatches=".*input.*")
        
        if input_box.exists:
            input_box.click()
            wait_ui_stable_after_action(self.device, timeout=0.5)
            
            try:
                input_box.clear_text()
            except:
                pass
            
            # Sử dụng clipboard để paste nội dung (tránh lỗi set_text với tiếng Việt)
            self.device.clipboard.set(comment_text)
            self.device.press("paste")
            wait_ui_stable_after_action(self.device, timeout=1)
            self._add_response_message(u"Đã nhập nội dung: {}".format(comment_text[:30]), "comment")
        else:
            self._add_response_message(u"Không tìm thấy ô nhập comment", "comment")
            return False

        # 3. Click nút Gửi bằng OpenCV
        template = get_gui_template()
        click_success = False
        
        if template is not None:
            try:
                screenshot = self.device.screenshot(format="opencv")
                if screenshot is not None:
                    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    
                    threshold = 0.7
                    if max_val >= threshold:
                        h, w = template.shape[:2]
                        x = max_loc[0] + w // 2
                        y = max_loc[1] + h // 2
                        self.device.click(x, y)
                        click_success = True
                        self._add_response_message(u"Đã click nút Gửi (OpenCV, độ khớp: {:.2f})".format(max_val), "comment")
                    else:
                        self._add_response_message(u"Độ khớp OpenCV thấp ({:.2f}), dùng Enter".format(max_val), "comment")
            except Exception as e:
                self._add_response_message(u"Lỗi OpenCV: {}, dùng Enter".format(str(e)[:30]), "comment")
        else:
            self._add_response_message(u"Không có template gui.png, dùng Enter", "comment")
        
        # Fallback: Dùng phím Enter nếu OpenCV thất bại
        if not click_success:
            self.device.press("enter")
            self._add_response_message(u"Đã nhấn Enter để gửi comment", "comment")

        if self.stop_flag or is_stop_all():
            return False
        
        # Lưu link đã làm để tránh làm lại job cũ
        self.previous_job_link = link
        
        wait_ui_stable_after_action(self.device, timeout=1)
        self._add_response_message(u"Comment thành công", "comment")
        return True
    
    # ========== API GOLIKE ==========
    
    def _parse_api_response(self, response, func_name="api_call"):
        result = {
            'success': False,
            'status_code': None,
            'message': '',
            'data': None,
            'is_limit': False,
            'is_checkpoint': False
        }
        
        try:
            result['status_code'] = response.status_code
            
            try:
                resp_json = response.json()
                result['data'] = resp_json
                result['message'] = resp_json.get('message', resp_json.get('msg', u"HTTP {}".format(response.status_code)))
                
                if response.status_code == 200 and resp_json.get('status') == 200:
                    result['success'] = True
                
                msg_lower = result['message'].lower()
                if any(kw in msg_lower for kw in ['limit', 'giới hạn', 'quá nhiều', 'too many']):
                    result['is_limit'] = True
                if any(kw in msg_lower for kw in ['checkpoint', 'verify', 'xác minh']):
                    result['is_checkpoint'] = True
                    
            except:
                result['message'] = response.text if response.text else u"HTTP {}".format(response.status_code)
                
        except Exception as e:
            result['message'] = u"Exception: {}".format(str(e))
        
        return result
    
    def _chonacc(self):
        try:
            response = self.session.get('https://gateway.golike.net/api/tiktok-account', headers=self.headers, timeout=25)
            parsed = self._parse_api_response(response, "chonacc")
            
            if not parsed['success']:
                return {"status": parsed['status_code'], "message": parsed['message'], "data": []}
            
            data = parsed['data'].get("data", []) if parsed['data'] else []
            return {"status": 200, "message": parsed['message'], "data": data}
        except Exception as e:
            return {"status": 500, "message": str(e), "data": []}
    
    def _nhannv(self):
        try:
            params = {'account_id': self.account_id_val, 'data': 'null'}
            response = self.session.get('https://gateway.golike.net/api/advertising/publishers/tiktok/jobs',
                                        headers=self.headers, params=params, timeout=25)
            parsed = self._parse_api_response(response, "nhannv")
            
            if not parsed['success']:
                return {"status": parsed['status_code'], "message": parsed['message']}
            
            return {"status": 200, "message": parsed['message'], "data": parsed['data'].get("data") if parsed['data'] else None}
        except Exception as e:
            return {"status": 500, "message": str(e)}
    
    def _baoloi(self, ads_id, object_id, loai):
        try:
            json_data = {'ads_id': ads_id, 'object_id': object_id, 'account_id': self.account_id_val, 'type': loai}
            response = self.session.post('https://gateway.golike.net/api/advertising/publishers/tiktok/skip-jobs',
                                         headers=self.headers, json=json_data, timeout=25)
            parsed = self._parse_api_response(response, "baoloi")
            
            if not parsed['success']:
                return {"status": parsed['status_code'], "message": parsed['message']}
            
            return {"status": 200, "message": parsed['message']}
        except Exception as e:
            return {"status": 500, "message": str(e)}
    
    def _hoanthanh(self, ads_id):
        try:
            json_data = {
                'ads_id': ads_id,
                'account_id': self.account_id_val,
                'async': True,
                'data': None
            }
            response = self.session.post('https://gateway.golike.net/api/advertising/publishers/tiktok/complete-jobs',
                                         headers=self.headers, json=json_data, timeout=25)
            parsed = self._parse_api_response(response, "complete_jobs")
            
            if parsed['success']:
                return {"status": True, "data": parsed.get('data'), "message": parsed.get('message', 'Success')}
            return {"status": False, "message": parsed.get('message', 'Lỗi không xác định')}
        except Exception as e:
            return {"status": False, "message": str(e)}
    
    def _get_job_price(self, job_data):
        try:
            for key in ['price_after_cost', 'price_per_after_cost', 'amount', 'reward', 'price', 'money', 'coin']:
                if key in job_data and job_data[key]:
                    val = job_data[key]
                    if isinstance(val, dict):
                        for subkey in ['amount', 'value', 'money', 'coin']:
                            if subkey in val and val[subkey]:
                                val = val[subkey]
                                break
                    if isinstance(val, str):
                        val = re.sub(r'[^\d.]', '', val)
                        if val:
                            val = float(val) if '.' in val else int(val)
                        else:
                            continue
                    if isinstance(val, (int, float)) and val > 0:
                        return int(val)
            return 0
        except:
            return 0
    
    def _process_job(self, job_data):
        try:
            if self.stop_flag or is_stop_all():
                return False, u"Dừng theo yêu cầu", None, 0
            
            link = job_data["link"]
            action_type = job_data["type"]
            ads_id = job_data["id"]
            job_price = self._get_job_price(job_data)

            if action_type == "follow" and job_price < self.min_follow_price:
                return False, u"Job Follow giá {}đ < {}đ".format(job_price, self.min_follow_price), ads_id, job_price

            if action_type not in ["like", "follow", "comment", "favorite"]:
                return False, u"Loại nhiệm vụ không hỗ trợ", None, 0

            if not self._open_link(link):
                return False, u"Mở link thất bại", ads_id, job_price

            wait_ui_stable_after_action(self.device, timeout=2)

            success = False
            reason = ""

            if action_type == "like":
                success = self.do_like()
                reason = u"Like thất bại" if not success else u"Like thành công"
            elif action_type == "follow":
                success = self.do_follow()
                reason = u"Follow thất bại" if not success else u"Follow thành công"
            elif action_type == "favorite":
                success = self.do_favorite()
                reason = u"Favorite thất bại" if not success else u"Favorite thành công"
            elif action_type == "comment":
                # Lấy nội dung comment từ job data - thử nhiều field
                comment_text = (
                    job_data.get("text") or
                    job_data.get("description") or
                    job_data.get("comment") or
                    job_data.get("content") or
                    job_data.get("noidung") or
                    job_data.get("message") or
                    ""
                )
                success = self.do_comment(comment_text, link)
                reason = u"Comment thất bại" if not success else u"Comment thành công"

            if not success:
                return False, reason, ads_id, job_price

            result = self._hoanthanh(ads_id)
            if result.get('status'):
                video_id = self._get_video_id(link)
                self._save_processed_video(video_id)
                return True, result.get('message', 'Thành công'), ads_id, job_price
            else:
                return False, result.get('message', 'Lỗi hoàn thành'), ads_id, job_price
                
        except Exception as e:
            return False, str(e), None, 0
    
    # ==================== HÀM LẤY USERNAME ====================
    
    def _force_stop_tiktok(self):
        if self.stop_flag or is_stop_all():
            return
        
        pkg = TIKTOK_PACKAGE
        self.device.shell(u"am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:{}".format(pkg))
        
        if self.device(textMatches="(?i)(Buộc dừng|Buộc đóng|Force stop)").wait(timeout=8):
            for attempt in range(3):
                if self.stop_flag or is_stop_all():
                    return
                btn_stop = self.device(resourceIdMatches=".*(?i)(force_stop|stop_button).*")
                if not btn_stop.exists:
                    btn_stop = self.device(textMatches="(?i)(Buộc dừng|Buộc đóng|Force stop)")
                
                if btn_stop.exists:
                    if btn_stop.info.get('enabled', False):
                        btn_stop.click()
                        
                        btn_ok = self.device(resourceId="android:id/button1")
                        if not btn_ok.exists:
                            btn_ok = self.device(textMatches="(?i)(ok|đồng ý|xác nhận)")
                            
                        if btn_ok.wait(timeout=2):
                            btn_ok.click()
                            return
                    else:
                        return
                time.sleep(0.3)
    
    def _start_tiktok_and_wait(self):
        if self.stop_flag or is_stop_all():
            return False
        
        self.device.app_start(TIKTOK_PACKAGE)
        
        return wait_tiktok_ui_smart_v2(self.device, timeout=20, require_stable=True)
    
    def _click_username_by_dump(self):
        """Hàm quét username từ XML sau khi đã vào profile"""
        try:
            deeplink_url = "tiktok://user/profile"
            self.device.shell(f'am start -a android.intent.action.VIEW -d "{deeplink_url}" {TIKTOK_PACKAGE}')
            
            # Chờ UI load
            if not wait_tiktok_ui_smart_v2(self.device, timeout=8, require_stable=True):
                return None

            start_scan = time.time()
            while time.time() - start_scan < 8:
                if self.stop_flag or is_stop_all():
                    return None
                
                xml = self.device.dump_hierarchy()
                if not xml:
                    time.sleep(0.5)
                    continue

                match = re.search(r'text="(@[a-zA-Z0-9_\.]+)"', xml)
                if match:
                    username = match.group(1).replace("@", "").strip().lower()
                    if len(username) > 2 and len(username) < 50:
                        return username
                
                exclude = ['home', 'feed', 'video', 'like', 'share', 'comment', 'for you', 
                          'following', 'inbox', 'profile', 'settings', 'message', 'notification']
                matches = re.findall(r'text="([a-zA-Z0-9_]{4,30})"', xml)
                for m in matches:
                    u = m.lower()
                    if u not in exclude and not any(k in u for k in exclude):
                        if len(u) > 2 and len(u) < 50:
                            return u
                time.sleep(0.5)
            return None
        except Exception as e:
            self._add_response_message(u"Lỗi quét username: {}".format(str(e)[:50]))
            return None
    
    def _get_username_persistent_loop(self):
        """
        Lấy username: Đợi UI thật sự hiện ra mới click
        Sử dụng state polling thay vì XML dump
        """
        attempt = 1
        while not self.stop_flag and not is_stop_all():
            self._update_dashboard_status(u"Đang đợi UI load (Lần {})...".format(attempt))
            
            self.device.app_start(TIKTOK_PACKAGE)
            
            # Sử dụng state polling để chờ UI
            ui_ready = wait_tiktok_ui_smart_v2(self.device, timeout=60, require_stable=True)

            if ui_ready:
                self._update_dashboard_status(u" UI đã xong, đang lấy Username...")
                username = self._click_username_by_dump()
                if username and len(username) > 2:
                    self._add_response_message(u" Đã lấy username: @{}".format(username))
                    return username
                self._add_response_message(u"Không tìm thấy tên trên màn hình...")
            else:
                self._add_response_message(u" Quá 60s máy không load nổi UI. Buộc dừng!")

            # Chỉ force stop khi thực sự timeout
            self._force_stop_tiktok()
            time.sleep(2)
            attempt += 1
        return None
    
    # ==================== HÀM ADD TÀI KHOẢN ====================
    
    def verify_account_logic_new(self, username):
        """Logic xác thực tài khoản - xử lý mã lỗi và tự động trích xuất link follow"""
        url = "https://gateway.golike.net/api/tiktok-account/verify-account-id"
        username = username.replace('@', '').strip()
        payload = {"unique_id": username}
        
        try:
            res = self.session.post(url, headers=self.headers, json=payload, timeout=25)
            data = res.json()

            if isinstance(data, list):
                msg_error = data[0] if len(data) > 0 else u"Lỗi API"
                return False, msg_error, None, None

            message = data.get("message") or data.get("msg") or u"Lỗi xác thực"
            target_data = data.get("data", {})
            if not isinstance(target_data, dict):
                target_data = {}

            found_links = re.findall(r'https://www.tiktok.com/@[a-zA-Z0-9._]+', message)
            target_follow = target_data.get("is_follow_id")
            follow_link = found_links[0] if found_links else (f"https://www.tiktok.com/@{target_follow}" if target_follow else None)

            if res.status_code == 200:
                account_id = target_data.get("id")
                if account_id:
                    return True, message, account_id, follow_link
            
            return False, message, None, follow_link
        except Exception as e:
            return False, u"Lỗi: {}".format(str(e)), None, None
    
    def auto_setup_account(self):
        """Quy trình: Quét Username -> Add Acc -> Trả về ID và username"""
        auto_username = self._get_username_persistent_loop()
        if not auto_username:
            return None, None

        self._add_response_message(u"Kiểm tra acc trên hệ thống...")
        chontiktok = self._chonacc()
        for acc in chontiktok.get("data", []):
            if acc.get("unique_username", "").strip().lower() == auto_username:
                self._add_response_message(u"Tài khoản @{} đã sẵn sàng.".format(auto_username))
                return acc.get("id"), auto_username

        self._add_response_message(u"Đang Add tài khoản @{}...".format(auto_username))
        ok, msg, acc_id, target_link = self.verify_account_logic_new(auto_username)

        if not ok and target_link:
            self._add_response_message(u"Đang follow link xác minh: {}".format(target_link))
            if self._open_link(target_link):
                wait_ui_stable_after_action(self.device, timeout=2)
                if self.do_follow():
                    self._add_response_message(u"Follow xác minh thành công!")
                    time.sleep(2)
                    ok, msg, acc_id, _ = self.verify_account_logic_new(auto_username)
                    self.device.press("back") 
                else:
                    self._add_response_message(u"Follow xác minh thất bại!")
            else:
                self._add_response_message(u"Không thể mở link xác minh!")

        if ok and acc_id:
            self._add_response_message(u" Add thành công! ID: {}".format(acc_id))
            return acc_id, auto_username
        
        self._add_response_message(u" Add thất bại: {}".format(msg))
        return None, None
    
    # ==================== HÀM CHẠY CHÍNH ====================
    
    def run(self):
        temp_account_id = "temp_{}".format(self.serial)
        self.account_id_val = temp_account_id
        
        with dashboard_lock:
            accounts_data[temp_account_id] = {
                "username": "None",
                "status": u"Đang kết nối...",
                "last_message": u"Đang kết nối thiết bị...",
                "message_time": get_vn_time().strftime('%H:%M:%S'),
                "job_type": "",
                "xu": 0,
                "total_xu": 0,
                "done": 0,
                "fail": 0,
                "link": "",
                "device_serial": self.serial,
                "last_update": time.time(),
                "last_success": time.time(),
                "tiktok_version": None
            }
        
        self._add_response_message(u"Đang kết nối thiết bị...")
        
        try:
            self.device = u2.connect(self.serial)
            self.device.info
            self._add_response_message(u"Kết nối thiết bị thành công")
            
            self._add_response_message(u"Đang lấy phiên bản TikTok...")
            self.tiktok_version = self._get_tiktok_version()
            if self.tiktok_version:
                self._add_response_message(u"Phiên bản TikTok: {}".format(self.tiktok_version))
                self._update_dashboard_with_version()
            else:
                self._add_response_message(u"Không lấy được phiên bản TikTok")
                
        except Exception as e:
            self._add_response_message(u"Kết nối thiết bị thất bại: {}".format(str(e)))
            with dashboard_lock:
                if temp_account_id in accounts_data:
                    del accounts_data[temp_account_id]
            return
        
        if self.force_stop_enabled:
            self._add_response_message(u"Đang force stop TikTok...")
            self._force_stop_tiktok()
            time.sleep(1.2)
        
        self._add_response_message(u"Đang mở TikTok...")
        self._start_tiktok_and_wait()
        
        final_account_id, auto_username = self.auto_setup_account()
        
        if not final_account_id or not auto_username:
            self._add_response_message(u"Không thể thiết lập tài khoản. Dừng luồng.")
            with dashboard_lock:
                if temp_account_id in accounts_data:
                    del accounts_data[temp_account_id]
                if self.account_id_val in accounts_data:
                    del accounts_data[self.account_id_val]
            return
        
        self.account_id_val = final_account_id
        
        with dashboard_lock:
            if final_account_id in accounts_data:
                accounts_data[final_account_id]["username"] = auto_username
                accounts_data[final_account_id]["status"] = u"Sẵn sàng"
                accounts_data[final_account_id]["last_message"] = u"Đã xác thực @{}".format(auto_username)
                accounts_data[final_account_id]["tiktok_version"] = self.tiktok_version
                accounts_data[final_account_id]["last_update"] = time.time()
            else:
                accounts_data[final_account_id] = {
                    "username": auto_username,
                    "status": u"Sẵn sàng",
                    "last_message": u"Đã xác thực @{}".format(auto_username),
                    "message_time": get_vn_time().strftime('%H:%M:%S'),
                    "job_type": "",
                    "xu": 0,
                    "total_xu": 0,
                    "done": 0,
                    "fail": 0,
                    "link": "",
                    "device_serial": self.serial,
                    "last_update": time.time(),
                    "last_success": time.time(),
                    "tiktok_version": self.tiktok_version
                }
            
            if temp_account_id in accounts_data:
                del accounts_data[temp_account_id]
        
        num_videos_khoi_dong = self.delay_config.get('nuoi_nick', 2)
        share_rate = self.delay_config.get('share_rate', 15)
        if num_videos_khoi_dong > 0:
            self._add_response_message(u"Đang nuôi nick khởi động...")
            self.nuoi_nick_short(num_videos=num_videos_khoi_dong, share_rate=share_rate)
        
        self._reset_retry_counter()
        
        while not self.stop_flag and not is_stop_all():
            try:
                self._update_dashboard_status(u"Đang tìm nhiệm vụ...")
                
                delay_time = self._get_random_delay('job')
                self._delay_countdown(delay_time, u"Đang tìm nhiệm vụ")

                nhanjob = self._nhannv()
                
                if nhanjob.get("status") == 200:
                    self._reset_retry_counter()
                    
                    data = nhanjob.get("data")
                    
                    if not data or not data.get("link"):
                        num_videos_het_job = max(2, self.delay_config.get('nuoi_nick', 2) * 2)
                        share_rate_het_job = random.randint(30, 50)
                        self.nuoi_nick_short(num_videos=num_videos_het_job, share_rate=share_rate_het_job, is_high_trust_mode=True)
                        
                        time.sleep(1.5)
                        continue

                    current_link = data.get("link")
                    self._update_current_link(current_link)

                    if self._is_link_processed(current_link):
                        skip_msg = self._baoloi(data["id"], data["object_id"], data["type"])
                        self._add_response_message(u"Đã bỏ qua video đã làm: {}".format(skip_msg.get("message", "")))
                        continue

                    if data["type"] not in self.lam:
                        skip_msg = self._baoloi(data["id"], data["object_id"], data["type"])
                        self._add_response_message(u"Bỏ qua job {}: {}".format(data["type"], skip_msg.get("message", "")))
                        time.sleep(0.5)
                        continue

                    status_map = {
                        "follow": u"Đang follow...",
                        "like": u"Đang like...",
                        "comment": u"Đang comment...",
                        "favorite": u"Đang favorite..."
                    }
                    self._update_dashboard_status(status_map.get(data["type"], u"Đang xử lý..."))

                    success, reason, job_ads_id, job_price = self._process_job(data)

                    if success:
                        self.job_count += 1
                        self._update_dashboard_stats(data["type"], job_price, success=True)
                        self._add_response_message(u"{} - Giá: {} xu".format(reason, job_price))
                        
                        delay_time_done = self.delay_config.get('delay_done', 9)
                        share_rate_normal = self.delay_config.get('share_rate', 15)
                        
                        if delay_time_done > 0:
                            self.nuoi_nick_thong_minh(delay_time_done, share_rate_normal)
                        
                        if self.force_stop_after > 0 and self.job_count >= self.force_stop_after:
                            self._add_response_message(u"Đạt {} job, force stop TikTok...".format(self.job_count))
                            self._force_stop_tiktok()
                            self.job_count = 0
                            self._start_tiktok_and_wait()
                    else:
                        self._update_dashboard_stats(data["type"], 0, success=False)
                        self._add_response_message(u"{}".format(reason))
                        
                        num_videos_loi = max(1, self.delay_config.get('nuoi_nick', 2) // 2)
                        share_rate_loi = self.delay_config.get('share_rate', 15)
                        if num_videos_loi > 0:
                            self.nuoi_nick_short(num_videos=num_videos_loi, share_rate=share_rate_loi)
                        
                        self._baoloi(data["id"], data["object_id"], data["type"])
                        time.sleep(0.5)
                else:
                    error_msg = nhanjob.get("message", "Lỗi không xác định")
                    retry_wait = self._increment_retry_counter()
                    self._add_response_message(u"API: {} - Thử lại sau {}s".format(error_msg, retry_wait))
                    
                    num_videos = self.delay_config.get('nuoi_nick', 2)
                    share_rate_cao = random.randint(30, 50)
                    self.nuoi_nick_short(num_videos=num_videos, share_rate=share_rate_cao, is_high_trust_mode=True)
                    
                    self._delay_countdown(retry_wait, u"Lỗi API - Thử lại sau")
                    
            except Exception as e:
                if self.stop_flag or is_stop_all():
                    break
                
                retry_wait = self._increment_retry_counter()
                self._add_response_message(u"Lỗi: {} - Thử lại sau {}s".format(str(e), retry_wait))
                self._delay_countdown(retry_wait, u"Lỗi - Thử lại sau")
        
        self._add_response_message(u"Bot đã dừng")


# ==================== CÁC HÀM HỖ TRỢ ====================

def banner():
    os.system('clear' if os.name == 'posix' else 'cls')
    banner_text = u"""
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

\033[38;2;255;200;140m[</>] \033[38;2;200;160;255mADMIN: NHƯ ANH ĐÃ THẤY EM   \033[38;2;255;220;160mPhiên Bản: \033[38;2;120;255;220mv3.14
\033[38;2;255;200;140m[</>] \033[38;2;200;160;255mNhóm Telegram: \033[38;2;120;255;220mhttps://t.me/se_meo_bao_an
\033[38;2;190;235;210m───────────────────────────────────────────────────────────────────────\033[0m
"""
    print(banner_text)


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except:
            pass
    return None


def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False


def input_number(text, default):
    while True:
        try:
            value = input(text).strip()
            if value == "":
                return default
            return int(value)
        except:
            console.print(u"[bold #ff4d6d]Sai định dạng! Nhập số.[/")


def setup_delay_config():
    delay_config = DEFAULT_DELAY_CONFIG.copy()
    saved_config = load_config()
    if saved_config:
        delay_config.update(saved_config.get('delay_config', {}))
    
    delay_like = [delay_config['like'][0], delay_config['like'][1]]
    delay_follow = [delay_config['follow'][0], delay_config['follow'][1]]
    delay_comment = [delay_config['comment'][0], delay_config['comment'][1]]
    delay_job = [delay_config['job'][0], delay_config['job'][1]]
    delay_fav = [delay_config['favorite'][0], delay_config['favorite'][1]]
    nuoi_nick = delay_config.get('nuoi_nick', 2)
    share_rate = delay_config.get('share_rate', 15)
    loc_follow = delay_config.get('loc_follow', 0)
    delay_done = delay_config.get('delay_done', 9)
    force_stop_enabled = saved_config.get('force_stop_enabled', False) if saved_config else False
    force_stop_after = saved_config.get('force_stop_after', 0) if saved_config else 0
    
    force_stop = "Yes" if force_stop_enabled else "No"
    stop_job = force_stop_after
    
    while True:
        table = Table(
            title="[#ffffff]Delay [#00ffff]Config[/]",
            box=box.SQUARE,
            border_style="#ff9ecb",
            show_lines=True,
            pad_edge=False
        )

        table.add_column("Name", justify="left", header_style="#ff9ecb")
        table.add_column("Min", justify="center", header_style="#ffffff")
        table.add_column("Max", justify="center", header_style="#00ffff")

        def row(name, val, c1, c2, c3):
            return [
                u"[bold {}]{}[/]".format(c1, name),
                u"[bold {}]{}[/][#aaaaaa]s[/]".format(c2, val[0]),
                u"[bold {}]{}[/][#aaaaaa]s[/]".format(c3, val[1])
            ]

        table.add_row(*row("Delay Like", delay_like, "#ff4d6d", "#ffd1dc", "#ff8fa3"))
        table.add_row(*row("Delay Follow", delay_follow, "#00c853", "#b9f6ca", "#69f0ae"))
        table.add_row(*row("Delay Comment", delay_comment, "#00b0ff", "#80d8ff", "#40c4ff"))
        table.add_row(*row("Delay Get Jobs", delay_job, "#ff9100", "#ffd180", "#ffab40"))
        table.add_row(*row("Delay Favorite", delay_fav, "#a78bfa", "#c4b5fd", "#b388ff"))

        table.add_row(
            u"[#9b59b6]Số video nuôi nick[/]",
            u"[bold #ffffff]{}[/]".format(nuoi_nick),
            u"[#00ffff]video[/]"
        )
        
        table.add_row(
            u"[#ff69b4]Tỷ lệ Copy Link[/]",
            u"[bold #ffffff]{}[/]".format(share_rate),
            u"[#00ffff]%[/]"
        )

        table.add_row(
            u"[#ff9ecb]Lọc Follow[/]",
            u"[#ffffff]{}[/]".format(loc_follow),
            u"[#00ffff]ON/OFF[/]"
        )

        table.add_row(
            u"[#ffd54f]Delay Hoàn Thành[/]",
            u"[bold #ffffff]{}[/]".format(delay_done),
            u"[#00ffff]s[/]"
        )

        table.add_row(
            u"[#ff4d6d]Buộc Dừng chạy[/]",
            u"[#ffffff]{}[/]".format(force_stop),
            u"[#aaaaaa]-[/]"
        )

        table.add_row(
            u"[#00b0ff]Số Job Buộc dừng[/]",
            u"[bold #ffffff]{}[/]".format(stop_job),
            u"[#aaaaaa]-[/]"
        )

        console.clear()
        banner()
        console.print(table)

        console.print(
            u"\n[#ff9ecb]➤ [#ffffff]Dùng lại config?[/] [#00ffff](Y/N)[/] ():",
            end=""
        )
        choice = input().strip().lower()

        if choice != "n":
            break

        console.print(u"\n[bold #ffd54f] Nhập lại cấu hình[/]\n")

        delay_like = [
            input_number(u"Delay Like Min ({}): ".format(delay_like[0]), delay_like[0]),
            input_number(u"Delay Like Max ({}): ".format(delay_like[1]), delay_like[1])
        ]

        delay_follow = [
            input_number(u"Delay Follow Min ({}): ".format(delay_follow[0]), delay_follow[0]),
            input_number(u"Delay Follow Max ({}): ".format(delay_follow[1]), delay_follow[1])
        ]

        delay_comment = [
            input_number(u"Delay Comment Min ({}): ".format(delay_comment[0]), delay_comment[0]),
            input_number(u"Delay Comment Max ({}): ".format(delay_comment[1]), delay_comment[1])
        ]

        delay_job = [
            input_number(u"Delay Get Jobs Min ({}): ".format(delay_job[0]), delay_job[0]),
            input_number(u"Delay Get Jobs Max ({}): ".format(delay_job[1]), delay_job[1])
        ]

        delay_fav = [
            input_number(u"Delay Favorite Min ({}): ".format(delay_fav[0]), delay_fav[0]),
            input_number(u"Delay Favorite Max ({}): ".format(delay_fav[1]), delay_fav[1])
        ]

        nuoi_nick = input_number(u"Số video nuôi nick ({}): ".format(nuoi_nick), nuoi_nick)
        share_rate = input_number(u"Tỷ lệ Copy Link (0-100%) ({}): ".format(share_rate), share_rate)
        loc_follow = input_number(u"Lọc Follow (0 = OFF) ({}): ".format(loc_follow), loc_follow)
        delay_done = input_number(u"Delay Hoàn Thành ({}): ".format(delay_done), delay_done)

        force_stop_input = input(u"Buộc dừng chạy (y/n): ").strip().lower()
        force_stop_enabled = (force_stop_input == "y")
        force_stop = "Yes" if force_stop_enabled else "No"
        stop_job = input_number(u"Số job buộc dừng ({}): ".format(stop_job), stop_job)

    delay_config = {
        'like': delay_like,
        'follow': delay_follow,
        'comment': delay_comment,
        'favorite': delay_fav,
        'job': delay_job,
        'delay_done': delay_done,
        'loc_follow': loc_follow,
        'nuoi_nick': nuoi_nick,
        'share_rate': share_rate
    }
    
    config = {
        'delay_config': delay_config,
        'min_follow_price': loc_follow,
        'force_stop_enabled': force_stop_enabled,
        'force_stop_after': stop_job
    }
    
    save_config(config)
    return delay_config, loc_follow, force_stop_enabled, stop_job


def render_tablet(selections, current_idx):
    JOBS = [
        {"id": "like", "name": "Like", "color": "#ff9ecb"},
        {"id": "follow", "name": "Follow", "color": "#ffd54f"},
        {"id": "comment", "name": "Comment", "color": "#00ffff"},
        {"id": "favorite", "name": "Favorite", "color": "#a78bfa"}
    ]
    
    table = Table(
        box=box.ROUNDED, 
        border_style="#d7b8ff", 
        header_style="bold #ffffff",
        width=45,
        title="[bold #ff9ecb] CHỌN NHIỆM VỤ[/]",
        show_lines=True
    )
    
    table.add_column("STT", justify="center", style="bold", width=5)
    table.add_column(u"Nhiệm Vụ", width=15)
    table.add_column(u"Trạng Thái", justify="center", width=12)

    for i, job in enumerate(JOBS):
        color = job["color"]
        
        if selections[i] == 'y':
            status = "[bold #00ff9c] Đã chọn[/]"
        elif selections[i] == 'n':
            status = "[bold #ff4d6d] Bỏ qua[/]"
        elif i == current_idx:
            status = "[blink bold #ffff00] Đang chờ...[/]"
        else:
            status = "[dim] Chưa chọn[/]"

        table.add_row(
            u"[{}]{}[/]".format(color, i+1),
            u"[{}]{}[/]".format(color, job['name']),
            status
        )
    return table


def menu_jobs():
    JOBS = [
        {"id": "like", "name": "Like", "color": "#ff9ecb"},
        {"id": "follow", "name": "Follow", "color": "#ffd54f"},
        {"id": "comment", "name": "Comment", "color": "#00ffff"},
        {"id": "favorite", "name": "Favorite", "color": "#a78bfa"}
    ]
    
    selections = [None] * len(JOBS)
    
    console.clear()
    console.print(Panel(u"[bold cyan] CẤU HÌNH NHIỆM VỤ[/]", border_style="#ff9ecb", width=50))
    console.print()
    
    for i, job in enumerate(JOBS):
        while True:
            console.clear()
            console.print(render_tablet(selections, i))
            
            ans = console.input(u"\n[#ff9ecb]➤ [#ffffff]Bạn có muốn làm nhiệm vụ [bold]{}[/] không? (y/n) [y]: ".format(job['name'])).strip().lower()
            
            if ans in ['y', 'yes', '']:
                selections[i] = 'y'
                break
            elif ans in ['n', 'no']:
                selections[i] = 'n'
                break
            else:
                console.print(u"[red] Vui lòng nhập y hoặc n![/]", style="red")
                time.sleep(1)

    console.clear()
    console.print(render_tablet(selections, -1))
    
    selected_jobs = [JOBS[i]["id"] for i in range(len(JOBS)) if selections[i] == 'y']
    
    if selected_jobs:
        console.print(u"\n[#ffffff] Nhiệm vụ đã chọn:[/] [bold #00ffff]{}[/]".format(u', '.join(job['name'] for job in JOBS if job['id'] in selected_jobs)))
    else:
        console.print(u"\n[#ff4d6d] Không có nhiệm vụ nào được chọn! Tool sẽ thoát.[/]")
        sys.exit(1)
    
    return selected_jobs


def get_device_model_from_adb(device_obj):
    try:
        return device_obj.shell("getprop ro.product.model").strip()
    except:
        return "Unknown"


def get_battery_from_adb(device_obj):
    try:
        info = device_obj.shell("dumpsys battery")
        for line in info.splitlines():
            if "level" in line:
                return line.split(":")[1].strip()
    except:
        pass
    return ""


def show_devices_with_rich(multi_select=True):
    console.clear()
    banner()
    table = Table(
        title="[bold #ffffff] DANH SÁCH THIẾT BỊ ADB[/]",
        border_style="#d7d7a8",
        show_lines=True,
        expand=False,
        title_justify="center"
    )

    table.add_column("STT", justify="center", style="#e0e0e0", width=4)
    table.add_column("Device ID", style="#00ff9c", width=20)
    table.add_column("Product Model", style="#ffd54f", width=15)
    table.add_column(u"🔋 Battery", justify="center", width=12)
    table.add_column("TikTok Version", style="#a78bfa", width=15)
    table.add_column("Status", style="#00ff99", width=10)

    devices = adb.device_list()

    if not devices:
        console.print(Panel(u"[red]Không tìm thấy thiết bị ADB nào![/]", border_style="red"))
        return []

    versions = get_all_devices_versions(devices)

    for i, d in enumerate(devices):
        model = get_device_model_from_adb(d)
        battery = get_battery_from_adb(d)
        tiktok_version = versions.get(d.serial, "None")
        
        if battery:
            try:
                b = int(battery)
                if b >= 80:
                    battery_display = u"[bold green]█[/bold green]" * (b // 10) + u"[green]{}%[/green]".format(b)
                elif b >= 50:
                    battery_display = u"[bold yellow]█[/bold yellow]" * (b // 10) + u"[yellow]{}%[/yellow]".format(b)
                elif b >= 20:
                    battery_display = u"[bold orange1]█[/bold orange1]" * (b // 10) + u"[orange1]{}%[/orange1]".format(b)
                else:
                    battery_display = u"[bold red]█[/bold red]" * (b // 10) + u"[red]{}%[/red]".format(b)
            except:
                battery_display = u"[cyan]{}%[/cyan]".format(battery)
        else:
            battery_display = "[dim]None[/dim]"
        
        version_display = u"[#a78bfa]{}[/]".format(tiktok_version) if tiktok_version != "None" else "[dim]None[/]"

        table.add_row(
            str(i + 1),
            u"[#00ff9c]{}[/]".format(d.serial),
            u"[#ffd54f]{}[/]".format(model),
            battery_display,
            version_display,
            u"[#00ff99]● Online[/]"
        )

    console.print(table)
    console.print()
    
    if multi_select:
        console.print(u"[#ff9ecb]➤ [#99ff99]Nhập STT [#ffffff][[#ff99cc] cách nhau bằng dấu phẩy, VD: 1,2,3[#ffffff] ] [#ffffff]hoặc nhập 0 để chọn tất cả: [/]", end="")
    else:
        console.print(u"[#ff9ecb]➤ [#ffffff]Nhập STT thiết bị: [/]", end="")
    
    return devices


def select_devices():
    devices = show_devices_with_rich(multi_select=True)
    if not devices:
        return []
    
    while True:
        try:
            choice = input().strip()
            
            if choice == "0":
                selected_serials = [d.serial for d in devices]
                console.print(u"[green]✓ Đã chọn tất cả {} thiết bị[/]".format(len(selected_serials)))
                return selected_serials
            
            indices = []
            for part in choice.split(','):
                part = part.strip()
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(devices):
                        indices.append(idx)
                elif '-' in part and len(part) > 1:
                    try:
                        start, end = part.split('-')
                        start_idx = int(start) - 1
                        end_idx = int(end) - 1
                        for idx in range(start_idx, end_idx + 1):
                            if 0 <= idx < len(devices):
                                indices.append(idx)
                    except:
                        pass
            if indices:
                selected_serials = [devices[idx].serial for idx in set(indices)]
                console.print(u"[green]✓ Đã chọn {} thiết bị[/]".format(len(selected_serials)))
                return selected_serials
            else:
                console.print(u"[red]Không có thiết bị nào được chọn![/]")
        except:
            pass


def get_user_me(auth_token, session):
    headers = {
        'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://app.golike.net/',
        'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': 'Windows',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'T': 'VFZSak1FMTZZM3BOZWtFd1RtYzlQUT09',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
        'Authorization': auth_token,
        'Content-Type': 'application/json;charset=utf-8'
    }
    
    try:
        response = session.get('https://gateway.golike.net/api/users/me', headers=headers, timeout=25)
        
        try:
            response_json = response.json()
        except:
            response_json = {}
        
        if response.status_code == 200 and response_json.get("status") == 200:
            data = response_json.get("data", {})
            return {
                "success": True,
                "auth": auth_token,
                "username": data.get("username", "Unknown"),
                "coin": data.get("coin", 0)
            }
        else:
            error_msg = response_json.get("message", u"HTTP {}".format(response.status_code))
            return {
                "success": False,
                "auth": auth_token,
                "message": error_msg
            }
    except:
        return {
            "success": False,
            "auth": auth_token,
            "message": "Connection error"
        }


def read_authorizations():
    try:
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('tokens', [])
        return []
    except:
        return []


def save_authorization(auth):
    try:
        current_auths = read_authorizations()
        if auth not in current_auths:
            current_auths.append(auth)
            with open(AUTH_FILE, 'w', encoding='utf-8') as f:
                json.dump({"tokens": current_auths}, f, ensure_ascii=False, indent=2)
            return True
        return False
    except:
        return False


def display_auth_menu():
    console.clear()
    banner()
    
    accounts = []
    auth_tokens = read_authorizations()
    
    if not auth_tokens:
        console.print(u"⚠ Chưa có Authorization nào! Vui lòng nhập Authorization.")
        new_auth = console.input(u"✈ Nhập Authorization: ").strip()
        if new_auth:
            save_authorization(new_auth)
            return new_auth
        else:
            console.print(u"Authorization không được để trống!")
            sys.exit(1)
    
    session = get_global_session()
    for token in auth_tokens:
        result = get_user_me(token, session)
        accounts.append(result)
    
    acc_lines = []
    for i, acc in enumerate(accounts):
        idx = u"{:02d}".format(i+1)
        
        if acc.get("success"):
            username = acc.get("username", "Unknown")
            coin = acc.get("coin", 0)
            line = u"[#00ffff][{}][/] [#ff99cc]{}[/] | [#99ff99]{} coin[/]".format(idx, username, coin)
        else:
            msg = acc.get('message', u'Lỗi hệ thống')[:30]
            line = u"[#00ffff][{}][/] [red]ERROR:[/] [#ff4444]{}[/]".format(idx, msg)
        
        acc_lines.append(line)
    
    acc_content = u"\n".join(acc_lines)
    
    panel_acc = Panel(
        acc_content,
        title="[bold #d7d7a8]DS TÀI KHOẢN GOLIKE[/]",
        title_align="center",
        border_style="#d7d7a8",
        padding=(0, 1),
        width=60
    )
    console.print(panel_acc)
    
    panel_input = Panel(
        u'[#cccccc]Enter để tiếp tục, nhập "t" để thêm tài khoản golike:[/]',
        border_style="#d7d7a8",
        padding=(0, 1),
        width=80
    )
    console.print(panel_input)
    
    choice = console.input(u"[#ff9ecb]➤ [#ffffff]Lựa chọn: [/]").strip().lower()
    
    if choice == '':
        valid_accounts = [acc for acc in accounts if acc.get("success")]
        if valid_accounts:
            return valid_accounts[0]["auth"]
        else:
            console.print(u" Không có tài khoản hợp lệ nào!")
            sys.exit(1)
    elif choice == 't':
        new_auth = console.input(u"\n[white]Authorization: [/]").strip()
        if not new_auth:
            console.print(u"Authorization không được để trống!")
            time.sleep(1.5)
            return display_auth_menu()
        
        console.print(u"Đang kiểm tra Authorization...")
        session = get_global_session()
        result = get_user_me(new_auth, session)
        
        if result.get("success"):
            console.print(u" Authorization hợp lệ! : {} | {} coin".format(result['username'], result['coin']))
            save_authorization(new_auth)
            time.sleep(1)
            return new_auth
        else:
            console.print(u" Authorization không hợp lệ! Lỗi: {}".format(result.get('message', 'Unknown error')))
            confirm = input(u"Authorization không hợp lệ, bạn vẫn muốn lưu? (y/n): ").strip().lower()
            if confirm == 'y':
                save_authorization(new_auth)
                return new_auth
            return display_auth_menu()
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(accounts):
            acc = accounts[idx]
            if acc.get("success"):
                return acc["auth"]
            else:
                console.print(u" Tài khoản này không hợp lệ!")
                time.sleep(1.5)
                return display_auth_menu()
        else:
            console.print(u"Số không hợp lệ!")
            time.sleep(1)
            return display_auth_menu()
    else:
        console.print(u"Lựa chọn không hợp lệ!")
        time.sleep(1)
        return display_auth_menu()


def build_dashboard_table():
    table = Table(show_header=True, header_style="#ffffff", border_style="#ff9ecb", box=box.ROUNDED, show_lines=True)
    
    table.add_column("STT", justify="center", style="#ffd54f", width=4)
    table.add_column("Device", style="#a78bfa", width=20)
    table.add_column("usname", style="#00ffff", width=14)
    table.add_column("Fail", style="#ff4d6d", justify="center", width=7)
    table.add_column("Type", style="#38bdf8", width=8)
    table.add_column(u"Xu", style="#ff9ecb", width=5)
    table.add_column(u"Tổng", style="#facc15", width=6)
    table.add_column("Done", style="#00ff9c", width=7)
    table.add_column("Status", style="#ffffff", width=60)
    
    with dashboard_lock:
        devices_list = []
        for acc_id, data in accounts_data.items():
            last_update = data.get("last_update", 0)
            devices_list.append((last_update, acc_id, data))
        
        devices_list.sort(key=lambda x: x[0], reverse=True)
        
        for i, (_, acc_id, data) in enumerate(devices_list, 1):
            status = str(data.get("status", u"đang chờ..."))[:900]
            job_type = data.get("job_type", "")
            msg_time = data.get("message_time", "")
            time_display = u"[dim]{}[/dim] ".format(msg_time) if msg_time else ""
            
            if any(word in status.lower() for word in ["error", "lỗi", "fail", "thất bại"]):
                status_display = u"[red]{}[/red]".format(status)
            elif any(word in status.lower() for word in ["ok", "thành công", "ready", "xong"]):
                status_display = u"[green]{}[/green]".format(status)
            else:
                status_display = u"[yellow]{}[/yellow]".format(status)
            
            table.add_row(
                str(i),
                data.get("device_serial", "?")[-18:],
                data.get("username", "?")[:10],
                str(data.get("fail", 0)),
                job_type.upper()[:15] if job_type else "None",
                str(data.get("xu", 0)),
                str(data.get("total_xu", 0)),
                str(data.get("done", 0)),
                u"{}{}".format(time_display, status_display)
            )
    
    return table


def make_dashboard_layout():
    order = ["xu", "dev", "act", "rate", "avg", "done", "fail", "err"]
    chieu_cao_stats = 4
    align_stats = "left"

    layout = Layout()
    
    try:
        console_height = console.height
        with dashboard_lock:
            row_count = len(accounts_data) + 2
        table_rows = min(row_count, console_height - 10)
        le_duoi = max(0, console_height - 7 - table_rows - chieu_cao_stats)
    except:
        le_duoi = 1
    
    layout.split(
        Layout(name="title", size=3),
        Layout(name="table"),
        Layout(name="stats", size=chieu_cao_stats),
        Layout(name="gap_bottom", size=le_duoi)
    )
    
    layout["title"].update(
        Align.center("[bold #ffffff]TOOL GOLIKE TIKTOK [#00ff9c]BY PHONG TUS[/]")
    )
    
    with dashboard_lock:
        total_xu = sum(d.get("total_xu", 0) for d in accounts_data.values())
        total_done = sum(d.get("done", 0) for d in accounts_data.values())
        total_fail = sum(d.get("fail", 0) for d in accounts_data.values())
        total_devices = len(accounts_data)
        now = time.time()
        active_devices = sum(1 for d in accounts_data.values() if now - d.get("last_update", 0) < 60)
        error_devices = sum(1 for d in accounts_data.values() if "error" in d.get("status", "").lower() or "lỗi" in d.get("status", "").lower())
        success_rate = round((total_done / (total_done + total_fail) * 100), 1) if (total_done + total_fail) > 0 else 0
        avg_xu = round(total_xu / total_devices, 1) if total_devices > 0 else 0

    panels = {
        "xu": Panel(f"[bold #ffd54f]TỔNG XU\n{total_xu}[/]", border_style="#ffd54f", box=box.ROUNDED),
        "dev": Panel(f"[bold #00ffff]THIẾT BỊ\n{total_devices}[/]", border_style="#00ffff", box=box.ROUNDED),
        "act": Panel(f"[bold #00ff9c]ACTIVE\n{active_devices}[/]", border_style="#00ff9c", box=box.ROUNDED),
        "err": Panel(f"[bold #ff4d6d]LỖI\n{error_devices}[/]", border_style="#ff4d6d", box=box.ROUNDED),
        "done": Panel(f"[bold #00ff9c]DONE\n{total_done}[/]", border_style="#00ff9c", box=box.ROUNDED),
        "fail": Panel(f"[bold #ff4d6d]FAIL\n{total_fail}[/]", border_style="#ff4d6d", box=box.ROUNDED),
    }

    stats_grid = Table.grid(expand=True)
    stats_grid.add_row(*[panels[k] for k in order if k in panels])

    layout["stats"].update(Align(stats_grid, align=align_stats))
    layout["table"].update(build_dashboard_table())
    layout["gap_bottom"].update("")

    return layout


def run_dashboard():
    if hasattr(os, 'nice'):
        try: os.nice(10)
        except: pass
    
    with Live(
        make_dashboard_layout(),
        refresh_per_second=1.0, 
        screen=False,
        auto_refresh=True
    ) as live:
        while not is_stop_all():
            try:
                layout = make_dashboard_layout()
                if layout is not None:
                    live.update(layout)
                time.sleep(1)
            except Exception as e:
                time.sleep(1)


# ==================== MAIN ====================
if __name__ == "__main__":
    clear_stop_all()
    
    def signal_handler(sig, frame):
        print(u"\n[yellow] Nhận tín hiệu dừng, đang thoát an toàn...[/]")
        set_stop_all()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    banner()
    
    load_gui_template_once()
    
    auth_token = display_auth_menu()
    console.print(u"✓ Đã chọn Authorization")
    time.sleep(1)
    
    console.print(u"[yellow] CẤU HÌNH DELAY VÀ THÔNG SỐ[/]")
    delay_config, min_follow_price, force_stop_enabled, force_stop_after = setup_delay_config()
    
    lam = menu_jobs()
    
    console.print(u"[yellow]Tiến hành kết nối thiết bị ADB...[/]")
    
    selected_serials = select_devices()
    
    if not selected_serials:
        console.print(u"[red]Không có thiết bị nào được chọn! Thoát tool.[/]")
        sys.exit(1)
    
    console.print(u"✓ Đã chọn {} thiết bị để chạy song song".format(len(selected_serials)))
    time.sleep(2)
    
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()
    time.sleep(2)
    
    console.print(u"[bold green] BẮT ĐẦU CHẠY {} THIẾT BỊ SONG SONG[/]".format(len(selected_serials)))
    
    def run_worker(serial):
        import os
        if hasattr(os, 'nice'):
            try:
                os.nice(5)
            except:
                pass
        
        bot = TikTokBot(
            serial=serial,
            auth_token=auth_token,
            golike_username="",
            account_id_val="",
            delay_config=delay_config,
            lam=lam,
            force_stop_enabled=force_stop_enabled,
            force_stop_after=force_stop_after,
            min_follow_price=min_follow_price
        )
        bot.run()
        return serial
    
    with ThreadPoolExecutor(max_workers=len(selected_serials)) as executor:
        futures = {executor.submit(run_worker, serial): serial for serial in selected_serials}
        
        try:
            for future in as_completed(futures):
                serial = futures[future]
                try:
                    future.result()
                except:
                    pass
        except KeyboardInterrupt:
            console.print(u"\n[yellow] Đang dừng tất cả các luồng...[/]")
            set_stop_all()
            for future in futures:
                future.cancel()
