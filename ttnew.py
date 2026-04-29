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
import urllib.request
import signal
import gc
from collections import deque
from math import sin, cos, pi
import dns.resolver

# ==================== CẤU HÌNH DNS RESOLVER TÙY CHỈNH ====================
def get_custom_resolver():
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
    resolver.timeout = 5
    resolver.lifetime = 10
    return resolver

class CustomDNSAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, resolver=None, *args, **kwargs):
        self.resolver = resolver or get_custom_resolver()
        super().__init__(*args, **kwargs)
    
    def get_connection(self, url, proxies=None):
        from urllib3.util.connection import create_connection
        import urllib3.util.connection as urllib3_conn
        
        original_create_connection = create_connection
        
        def custom_create_connection(address, *args, **kwargs):
            host, port = address
            try:
                answers = self.resolver.resolve(host, 'A')
                if answers:
                    ip = str(answers[0])
                    return original_create_connection((ip, port), *args, **kwargs)
            except Exception:
                pass
            return original_create_connection(address, *args, **kwargs)
        
        original = urllib3_conn.create_connection
        urllib3_conn.create_connection = custom_create_connection
        
        try:
            return super().get_connection(url, proxies)
        finally:
            urllib3_conn.create_connection = original

def patch_session_with_custom_dns(session):
    try:
        adapter = CustomDNSAdapter()
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        return True
    except Exception:
        return False

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

SIMILARITY_THRESHOLD = 0.85

DEFAULT_DELAY_CONFIG = {
    'like': [5, 5],
    'follow': [5, 5],
    'favorite': [5, 5],
    'job': [5, 5],
    'delay_done': 9,
    'delay_open': 10,
    'loc_follow': 0,
    'nuoi_nick': 2,
    'share_rate': 15,
    'follow_via_search': 0
}

# ==================== DASHBOARD TOÀN CỤC ====================
console = Console()
accounts_data = {}
dashboard_lock = threading.RLock()
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


# ==================== ANIMATION BORDER HIGHLIGHT ====================
class BorderAnimator:
    def __init__(self, width=80, height=20):
        self.width = width
        self.height = height
        self.perimeter = 2 * width + 2 * height
        self.pos = 0
        self.frame_count = 0
        self.speed = 1
        self.tail_length = 2
        self.hue_offset = 0
        
    def update(self):
        self.pos = (self.pos + self.speed) % self.perimeter
        self.frame_count += 1
        self.hue_offset = (self.hue_offset + 5) % 360
    
    def get_position_info(self, perimeter_pos):
        w, h = self.width, self.height
        if perimeter_pos < w:
            return 'top', perimeter_pos, w, h
        elif perimeter_pos < w + h:
            return 'right', perimeter_pos - w, w, h
        elif perimeter_pos < w + h + w:
            return 'bottom', perimeter_pos - (w + h), w, h
        else:
            return 'left', perimeter_pos - (w + h + w), w, h
    
    def is_highlight_position(self, edge, edge_index):
        current_edge, current_edge_pos, _, _ = self.get_position_info(self.pos)
        if current_edge == edge and current_edge_pos == edge_index:
            return True
        for tail_offset in range(1, self.tail_length + 1):
            tail_pos = (self.pos - tail_offset) % self.perimeter
            tail_edge, tail_edge_pos, _, _ = self.get_position_info(tail_pos)
            if tail_edge == edge and tail_edge_pos == edge_index:
                return True
        return False
    
    def get_brightness_for_position(self, edge, edge_index):
        current_edge, current_edge_pos, _, _ = self.get_position_info(self.pos)
        if current_edge == edge and current_edge_pos == edge_index:
            return 1.0
        for tail_offset in range(1, self.tail_length + 1):
            tail_pos = (self.pos - tail_offset) % self.perimeter
            tail_edge, tail_edge_pos, _, _ = self.get_position_info(tail_pos)
            if tail_edge == edge and tail_edge_pos == edge_index:
                return 1.0 - (tail_offset / (self.tail_length + 1))
        return 0.0
    
    def get_highlight_char(self, edge_char, edge, edge_index):
        brightness = self.get_brightness_for_position(edge, edge_index)
        if brightness <= 0:
            return edge_char
        
        hue = (self.hue_offset + brightness * 60) % 360
        
        if edge_char in ['─', '╌', '┄']:
            highlight_char = '━'
        elif edge_char in ['│', '┆', '┊']:
            highlight_char = '┃'
        elif edge_char == '┌':
            highlight_char = '┏'
        elif edge_char == '┐':
            highlight_char = '┓'
        elif edge_char == '└':
            highlight_char = '┗'
        elif edge_char == '┘':
            highlight_char = '┛'
        elif edge_char == '├':
            highlight_char = '┣'
        elif edge_char == '┤':
            highlight_char = '┫'
        elif edge_char == '┬':
            highlight_char = '┳'
        elif edge_char == '┴':
            highlight_char = '┻'
        elif edge_char == '┼':
            highlight_char = '╋'
        else:
            highlight_char = edge_char
        
        if brightness >= 0.8:
            color = f"#ff{int(100 + hue/3):02x}00"
        elif brightness >= 0.5:
            color = f"#ff{int(150 + hue/4):02x}00"
        else:
            color = f"#ff{int(200 + hue/5):02x}00"
        
        return f"[bold {color}]{highlight_char}[/]"
    
    def render_border_with_highlight(self, top_edge, bottom_edge, left_edge, right_edge, 
                                      top_chars, bottom_chars, left_chars, right_chars):
        result = []
        top_result = []
        for i, ch in enumerate(top_chars):
            if self.is_highlight_position('top', i):
                top_result.append(self.get_highlight_char(ch, 'top', i))
            else:
                top_result.append(ch)
        result.append(''.join(top_result))
        
        for i in range(len(left_chars)):
            left_char = left_chars[i]
            right_char = right_chars[i]
            left_highlighted = self.get_highlight_char(left_char, 'left', i) if self.is_highlight_position('left', i) else left_char
            right_highlighted = self.get_highlight_char(right_char, 'right', i) if self.is_highlight_position('right', i) else right_char
            result.append(f"{left_highlighted}{' ' * (len(top_chars) - 2)}{right_highlighted}")
        
        bottom_result = []
        for i, ch in enumerate(bottom_chars):
            if self.is_highlight_position('bottom', i):
                bottom_result.append(self.get_highlight_char(ch, 'bottom', i))
            else:
                bottom_result.append(ch)
        result.append(''.join(bottom_result))
        return '\n'.join(result)


class AnimatedBox:
    def __init__(self, border_animator):
        self.animator = border_animator
    
    def render(self, content, title="", border_style="#ff9ecb"):
        lines = content.split('\n')
        height = len(lines)
        width = max(len(line) for line in lines) if lines else 40
        width = max(width + 4, 40)
        
        self.animator.width = width
        self.animator.height = height + 2
        
        top_chars = ['┌'] + ['─'] * (width - 2) + ['┐']
        bottom_chars = ['└'] + ['─'] * (width - 2) + ['┘']
        left_chars = ['│'] * height
        right_chars = ['│'] * height
        
        if title:
            title_display = f" {title} "
            for i, ch in enumerate(title_display):
                if 1 + i < len(top_chars) - 1:
                    top_chars[1 + i] = ch
        
        bordered = self.animator.render_border_with_highlight(
            top_chars, bottom_chars, left_chars, right_chars,
            top_chars, bottom_chars, left_chars, right_chars
        )
        
        result_lines = bordered.split('\n')
        for i, line in enumerate(lines):
            if i + 1 < len(result_lines):
                padding = width - len(line) - 2
                result_lines[i + 1] = result_lines[i + 1][0] + f" {line}{' ' * padding}" + result_lines[i + 1][-1]
        
        return '\n'.join(result_lines)


# ==================== HÀM LẤY VERSION TIKTOK ====================
def get_tiktok_version_from_device(device_obj, serial=None):
    try:
        result = device_obj.shell("dumpsys package com.ss.android.ugc.trill | grep versionName")
        if result and result.strip():
            match = re.search(r'versionName=([\d.]+)', result)
            if match:
                return match.group(1)
        result = device_obj.shell("pm list packages --show-version-code com.ss.android.ugc.trill")
        if result and result.strip():
            match = re.search(r'versionCode=(\d+)', result)
            if match:
                return match.group(1)
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


def wait_tiktok_ui_smart(device, timeout=40):
    start_time = time.time()
    interval = 0.25
    while time.time() - start_time < timeout:
        try:
            current = device.app_current()
            if current.get("package") == TIKTOK_PACKAGE:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def wait_ui_stable_after_action(device, timeout=3):
    time.sleep(0.3)
    start_time = time.time()
    interval = 0.25
    while time.time() - start_time < timeout:
        try:
            current = device.app_current()
            if current.get("package") == TIKTOK_PACKAGE:
                return True
        except:
            pass
        time.sleep(interval)
    return True


def wait_tiktok_ui(device, timeout=20):
    return wait_tiktok_ui_smart(device, timeout=timeout)


def force_restart_tiktok(device):
    try:
        device.app_stop(TIKTOK_PACKAGE)
        time.sleep(1)
        device.app_start(TIKTOK_PACKAGE)
        wait_tiktok_ui_smart(device, timeout=15)
    except Exception:
        pass


def click_search_icon(d):
    for _ in range(5):
        try:
            xml = d.dump_hierarchy()
            nodes = re.findall(
                r'<node[^>]*class="android\.widget\.ImageView"[^>]*content-desc="([^"]*)"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"',
                xml
            )
            w, h = d.window_size()
            for desc, bounds in nodes:
                if desc not in ["Tìm kiếm", "Search"]:
                    continue
                nums = list(map(int, re.findall(r'\d+', bounds)))
                if len(nums) >= 4:
                    x1, y1, x2, y2 = nums[:4]
                    if y2 < h * 0.18 and x1 > w * 0.6:
                        x = (x1 + x2) // 2
                        y = (y1 + y2) // 2
                        d.click(x, y)
                        time.sleep(1)
                        if d(className="android.widget.EditText").exists:
                            return True
            time.sleep(0.5)
        except Exception:
            pass
    return False


def type_text_slow(d, text):
    for ch in text:
        d.send_keys(ch)
        time.sleep(0.05)


def wait_search_ui(d, timeout=6):
    start = time.time()
    while time.time() - start < timeout:
        try:
            if d(className="android.widget.EditText").exists:
                return True
        except:
            pass
        time.sleep(0.3)
    return False


def swipe_down_from_point_little(device, x, y, screen_height, distance_ratio=0.3, duration=400):
    distance = int(screen_height * distance_ratio)
    y_end = min(screen_height - 10, y + distance)
    device.shell(f"input swipe {x} {y} {x} {y_end} {duration}")

def checknha(device, x, y):
    w, h = device.window_size()
    swipe_down_from_point_little(device, x, y, h)


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
        self.session = requests.Session()
        
        patch_session_with_custom_dns(self.session)
        
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=1,
            pool_block=False
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        
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

        self.stop_flag = False
        self.job_count = 0
        self.previous_job_link = None
        self.consecutive_errors = 0
        self.max_errors = 5
        self.retry_delays = [5, 10, 20, 30, 60]

        self.last_action_time = 0
        self.min_action_gap = 0.25

        self.ui_dump_cache = {"xml": "", "timestamp": 0, "nodes": []}
        self.ui_dump_cache_ttl = 0
        self.last_dump_time = 0
        self.min_dump_interval = 0.05

        self.link_job_file = None
        self.processed_videos = []
        
        self.job_counter_since_restart = 0
        self.error_counter_since_restart = 0
        self.last_restart_time = 0
        self.last_adb_check_time = 0
        
        self.username_retry_count = 0
        self.max_username_retries = 5
        
        self.tiktok_version = None
        
        # Biến cho delay + nuôi nick song song
        self._last_delay_second = -1
        self._last_log_second = -1

        self._init_instance_files()

    def swipe_down_from_point_little(self, x, y, distance_ratio=0.3, duration=400):
        if not self.device:
            return
        try:
            w, h = self.device.window_size()
            distance = int(h * distance_ratio)
            y_end = min(h - 10, y + distance)
            self.device.shell(f"input swipe {x} {y} {x} {y_end} {duration}")
        except Exception:
            pass
    
    def checknha(self, x, y):
        self.swipe_down_from_point_little(x, y)

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
        self.link_job_file = os.path.join(DATA_DIR, f"device_{safe_serial}_link_job.json")
        
        if not os.path.exists(self.link_job_file):
            with open(self.link_job_file, 'w', encoding='utf-8') as f:
                json.dump({"processed_videos": []}, f)
        
        self._load_processed_videos()
    
    def _load_processed_videos(self):
        try:
            if os.path.exists(self.link_job_file):
                with open(self.link_job_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed_videos = data.get("processed_videos", [])
        except:
            self.processed_videos = []
    
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
    
    def _extract_video_id_from_link(self, link):
        try:
            match = re.search(r'/video/(\d+)', link)
            if match:
                return match.group(1)
            match = re.search(r'/(\d{15,})', link)
            if match:
                return match.group(1)
            return None
        except Exception:
            return None
    
    def _extract_user_id_from_link(self, link):
        try:
            match = re.search(r'@([a-zA-Z0-9_\.]+)', link)
            if match:
                return match.group(1)
            return None
        except Exception:
            return None
    
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
                wait_tiktok_ui_smart(self.device, timeout=10)
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
        now = time.time()
        
        if now - self.last_dump_time < self.min_dump_interval:
            if self.ui_dump_cache["nodes"]:
                return self.ui_dump_cache["nodes"]
        
        self.last_dump_time = now
        
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
            return self.ui_dump_cache.get("nodes", [])
    
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
            wait_tiktok_ui_smart(self.device, timeout=10)
        except Exception:
            pass
    
    def _check_app_status(self):
        """Kiểm tra app có đang chạy không, nếu không thì mở lại"""
        try:
            current = self.device.app_current()
            if current.get("package") != TIKTOK_PACKAGE:
                self._add_response_message("Phát hiện thoát app, đang mở lại TikTok")
                self.device.app_start(TIKTOK_PACKAGE)
                wait_tiktok_ui_smart(self.device, timeout=10)
                return False
            return True
        except Exception:
            self._restart_tiktok()
            return False

    def _open_link(self, link):
        """Mở link TikTok - ưu tiên ADB command"""
        try:
            if not link or not isinstance(link, str):
                self._add_response_message(f"LỖI: Link không hợp lệ (None/Rỗng)")
                return False
            
            link = link.strip()
            self._add_response_message(f" {link[:80]}")
            
            if not self._check_and_reconnect_adb():
                self._add_response_message(f"LỖI: Mất kết nối ADB với {self.serial}")
                return False
            
            if not link.startswith("http"):
                self._add_response_message(f"LỖI: Link sai định dạng http: {link[:50]}")
                return False
            
            # Dùng ADB command thay vì intent
            cmd = f'am start -a android.intent.action.VIEW -d "{link}" -p {TIKTOK_PACKAGE}'
            self.device.shell(cmd)
            
            time.sleep(5)
            
            current = self.device.app_current()
            current_pkg = current.get("package", "")
            
            if current_pkg == TIKTOK_PACKAGE:
                self._add_response_message(f"✓ Mở link thành công")
                return True
            else:
                self._add_response_message(f"✗ Mở link thất bại. App hiện tại: {current_pkg}")
                self.device.app_start(TIKTOK_PACKAGE)
                wait_tiktok_ui_smart(self.device, timeout=8)
                return False
                
        except Exception as e:
            self._add_response_message(f"Lỗi hệ thống mở link: {str(e)[:80]}")
            return False

    def _get_random_delay(self, job_type):
        if job_type in self.delay_config:
            min_delay, max_delay = self.delay_config[job_type]
            return random.randint(min_delay, max_delay)
        return random.randint(3, 7)

    # ==================== DELAY + NUÔI NICK SONG SONG ====================
    
    def _delay_voi_nuoi_nick(self, delay_seconds, msg_prefix="Đang chờ", share_rate=15):
        """
        Delay kết hợp nuôi nick - LUÔN CÓ HÀNH ĐỘNG
        KHÔNG sleep thuần, countdown log mỗi giây
        """
        if delay_seconds <= 0:
            return
        
        delay_seconds = min(delay_seconds, 300)
        start_time = time.time()
        
        # Thời gian mỗi video
        video_duration = random.uniform(4, 8)
        current_video_start = time.time()
        action_count = 0
        
        # Reset counter log
        self._last_delay_second = -1
        
        while time.time() - start_time < delay_seconds:
            if self.stop_flag or is_stop_all():
                break
            
            elapsed = time.time() - start_time
            remaining = delay_seconds - elapsed
            
            # Log mỗi giây - HIỂN THỊ COUNTDOWN
            current_second = int(elapsed)
            if current_second > self._last_delay_second:
                self._last_delay_second = current_second
                self._update_dashboard_status(f"{msg_prefix} {int(remaining)}s | Đang nuôi nick...")
            
            # Xử lý video hiện tại
            video_elapsed = time.time() - current_video_start
            
            if video_elapsed >= video_duration:
                # Chuyển sang video mới
                action_count += 1
                
                # Random share
                if random.randint(1, 100) <= share_rate:
                    self._do_share_and_copy_link()
                    time.sleep(0.2)
                
                # Swipe lên video tiếp theo
                try:
                    w, h = self.device.window_size()
                    x_mid = int(w * 0.5)
                    start_y = int(h * 0.85)
                    end_y = int(h * 0.2)
                    self.device.swipe(x_mid, start_y, x_mid, end_y, duration=random.uniform(0.1, 0.2))
                except:
                    pass
                
                # Reset video mới
                current_video_start = time.time()
                video_duration = random.uniform(3, 7)
                
                # Thỉnh thoảng like
                if action_count % 4 == 0 and random.randint(1, 100) <= 25:
                    try:
                        self.do_like()
                    except:
                        pass
            
            # Sleep rất ngắn để không tốn CPU
            time.sleep(0.05)
        
        # Reset counter cho lần sau
        self._last_delay_second = -1

    # ========== SHARE VÀ COPY LINK ==========
    
    def _do_share_and_copy_link(self, max_retry=2):
        """Share và copy link"""
        try:
            # Tìm và click nút share
            share_btn = None
            
            # Cách 1: Tìm bằng resource-id
            for res_id in ["share", "share_button", "icon_share", "iv_share"]:
                try:
                    btn = self.device(resourceIdMatches=f".*{res_id}.*")
                    if btn.exists:
                        share_btn = btn
                        break
                except:
                    pass
            
            # Cách 2: Tìm bằng content-desc
            if not share_btn:
                try:
                    btn = self.device(descriptionMatches="(?i)(share|chia sẻ|gửi)")
                    if btn.exists:
                        share_btn = btn
                except:
                    pass
            
            # Cách 3: Tìm bằng text
            if not share_btn:
                try:
                    btn = self.device(textMatches="(?i)(share|chia sẻ)")
                    if btn.exists:
                        share_btn = btn
                except:
                    pass
            
            # Cách 4: Tìm bằng vị trí (nút share thường ở góc phải màn hình)
            if not share_btn:
                try:
                    w, h = self.device.window_size()
                    # Quét vùng góc phải
                    for x in range(w - 180, w - 30, 40):
                        for y in range(150, 450, 60):
                            try:
                                # Click thử
                                self.device.click(x, y)
                                time.sleep(0.5)
                                # Kiểm tra xem có menu share hiện ra không
                                if self.device(textMatches="(?i)(sao chép|copy|link)").exists:
                                    share_btn = True
                                    break
                            except:
                                pass
                        if share_btn:
                            break
                except:
                    pass
            
            if not share_btn:
                return False
            
            # Click nút share
            if hasattr(share_btn, 'click'):
                share_btn.click()
            time.sleep(0.8)
            
            # Tìm và click nút copy link
            copy_selectors = [
                ("text", "Sao chép liên kết"),
                ("text", "Copy link"),
                ("textContains", "Sao chép"),
                ("textContains", "Copy"),
                ("descriptionContains", "copy"),
                ("descriptionContains", "link"),
                ("resourceIdMatches", ".*copy.*"),
            ]
            
            for attr, value in copy_selectors:
                try:
                    btn = self.device(**{attr: value})
                    if btn.exists:
                        btn.click()
                        time.sleep(0.3)
                        return True
                except:
                    pass
            
            # Back nếu không tìm thấy
            self.device.press("back")
            return False
            
        except Exception as e:
            return False
    
    # ========== NUÔI NICK ==========
    
    def nuoi_nick_lien_tuc(self, duration_seconds, share_rate=15):
        """Nuôi nick liên tục trong thời gian duration_seconds"""
        if duration_seconds <= 0:
            return 0
        
        duration_seconds = min(duration_seconds, 300)
        start_time = time.time()
        action_count = 0
        
        # Thời gian mỗi video
        video_duration = random.uniform(4, 8)
        current_video_start = time.time()
        
        # Reset counter log
        self._last_log_second = -1
        
        while time.time() - start_time < duration_seconds:
            if self.stop_flag or is_stop_all():
                break
            
            elapsed = time.time() - start_time
            remaining = duration_seconds - elapsed
            
            # Log mỗi giây
            current_second = int(elapsed)
            if current_second > self._last_log_second:
                self._last_log_second = current_second
                self._update_dashboard_status(f"Nuôi nick... {int(remaining)}s còn lại")
            
            # Xử lý video hiện tại
            video_elapsed = time.time() - current_video_start
            
            if video_elapsed >= video_duration:
                # Chuyển sang video mới
                action_count += 1
                
                # Random share
                if random.randint(1, 100) <= share_rate:
                    self._do_share_and_copy_link()
                    time.sleep(0.2)
                
                # Swipe lên video tiếp theo
                try:
                    w, h = self.device.window_size()
                    x_mid = int(w * 0.5)
                    start_y = int(h * 0.85)
                    end_y = int(h * 0.2)
                    self.device.swipe(x_mid, start_y, x_mid, end_y, duration=random.uniform(0.1, 0.2))
                except:
                    pass
                
                # Reset video mới
                current_video_start = time.time()
                video_duration = random.uniform(3, 7)
                
                # Thỉnh thoảng like
                if action_count % 5 == 0 and random.randint(1, 100) <= 30:
                    try:
                        self.do_like()
                    except:
                        pass
            
            # Sleep rất ngắn
            time.sleep(0.05)
        
        self._last_log_second = -1
        return action_count
    
    def nuoi_nick_short(self, num_videos=2, share_rate=15, is_high_trust_mode=False):
        """Nuôi nick số lượng video nhất định"""
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
            
            for i in range(num_videos):
                if self.stop_flag or is_stop_all():
                    break
                
                watch_time = random.uniform(5, 10)
                
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

    # ========== FOLLOW QUA TÌM KIẾM ==========
    
    def _extract_username_from_link(self, link):
        try:
            match = re.search(r'@([a-zA-Z0-9_\.]+)', link)
            if match:
                return match.group(1).strip().lower()
            return None
        except Exception:
            return None
    
    def _click_search_icon(self):
        return click_search_icon(self.device)
    
    def _wait_search_ui(self, timeout=6):
        return wait_search_ui(self.device, timeout)
    
    def _type_text_slow(self, text):
        try:
            self.device.set_clipboard(text)
            time.sleep(0.05)
            self.device.press("paste")
        except Exception:
            pass
    
    def _search_username(self, username):
        try:
            search_input = self.device(className="android.widget.EditText")
            if not search_input.exists:
                search_input = self.device(resourceIdMatches=".*search.input.")
        
            if not search_input.exists:
                return False
        
            search_input.click()
            time.sleep(0.1)
        
            try:
                search_input.clear_text()
            except:
                pass
        
            search_input.set_text(username)
        
            time.sleep(0.1)
            self.device.press("enter")
            return True
        
        except Exception:
            return False
    
    def _switch_to_users_tab(self):
        try:
            users_tab = self.device(textMatches="(?i)(người dùng|users|people)")
            if users_tab.exists:
                users_tab.click()
                time.sleep(1.5)
                return True
            
            users_tab = self.device(resourceIdMatches=".*tab.*users.*")
            if users_tab.exists:
                users_tab.click()
                time.sleep(1.5)
                return True
            
            return False
        except Exception:
            return False
    
    def _find_and_click_follow_in_search_results(self, username):
        try:
            nodes = self._dump_ui_nodes()
        
            for node in nodes:
                text = node.get("text", "").strip().lower()
                res_id = node.get("resource-id", "")
            
                if "đang theo dõi" in text or "following" in text:
                    self._add_response_message(f"Đã follow @{username} từ trước", "follow")
                    return True
            
                if text in ["theo dõi", "follow"] or "follow" in res_id:
                    if self._click_node_by_bounds(node):
                        time.sleep(1.5)
                        self._add_response_message(f"Đã nhấn Follow @{username}", "follow")
                        return True
        
            self._add_response_message(f"Không tìm thấy nút Follow cho @{username}, bỏ qua", "follow")
            return True
        
        except Exception as e:
            self._add_response_message(f"Lỗi khi tìm Follow: {str(e)[:50]}, bỏ qua", "follow")
            return True
    
    def _go_back_to_home(self):
        """Chỉ dùng để quay về Home, KHÔNG thoát app"""
        try:
            for _ in range(2):
                self.device.press("back")
                time.sleep(0.3)
            
            try:
                home_tab = self.device(text="Home", resourceIdMatches=".*tab.*")
                if home_tab.exists:
                    home_tab.click()
                    time.sleep(0.5)
            except:
                pass
        except Exception:
            pass
    
    def do_follow_via_search(self, link):
        """Follow qua tìm kiếm"""
        if not self.device:
            self._add_response_message("[Follow Search] Device không khả dụng", "follow")
            return False

        if self.stop_flag or is_stop_all():
            self._add_response_message("[Follow Search] Bị dừng", "follow")
            return False

        username = self._extract_username_from_link(link)
        if not username:
            self._add_response_message("[Follow Search] Không thể trích xuất username từ link", "follow")
            return False

        self._add_response_message(f"[Follow Search] Bắt đầu tìm kiếm và follow @{username}", "follow")

        try:
            self._go_back_to_home()
            self._check_app_status()

            if not self._click_search_icon():
                self._add_response_message("[Follow Search] Không tìm thấy icon tìm kiếm", "follow")
                self._go_back_to_home()
                return False
            
            if not self._wait_search_ui(timeout=6):
                self._add_response_message("[Follow Search] Không chờ được UI tìm kiếm", "follow")
                self._go_back_to_home()
                return False
            
            if not self._search_username(username):
                self._add_response_message("[Follow Search] Không thể nhập username", "follow")
                self._go_back_to_home()
                return False
            time.sleep(2)

            if not self._switch_to_users_tab():
                self._add_response_message("[Follow Search] Không tìm thấy tab Người dùng", "follow")
                self._go_back_to_home()
                return False
            time.sleep(1.5)

            follow_success = self._find_and_click_follow_in_search_results(username)

            self._go_back_to_home()
            self._go_back_to_home()
            if follow_success:
                self._add_response_message(f"[Follow Search] Follow @{username} thành công!", "follow")
            else:
                self._add_response_message(f"[Follow Search] Follow @{username} thất bại", "follow")

            return follow_success

        except Exception as e:
            self._add_response_message(f"[Follow Search] Lỗi: {str(e)[:50]}", "follow")
            try:
                self._go_back_to_home()
            except:
                pass
            return False

    # ========== FOLLOW QUA LINK ==========
    
    def do_follow_via_link(self, max_retry=3):
        """Follow qua link"""
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
                            self._add_response_message("Đã follow từ trước", "follow")
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
                                self._add_response_message("Follow thành công", "follow")
                                try:
                                    w, h = self.device.window_size()
                                    random_x = random.randint(int(w * 0.2), int(w * 0.8))
                                    random_y = random.randint(int(h * 0.3), int(h * 0.7))
                                    self.checknha(random_x, random_y)
                                    self._add_response_message("Đã vuốt xuống sau follow", "follow")
                                except Exception as e:
                                    self._add_response_message(f"Vuốt sau follow lỗi: {str(e)[:30]}", "follow")
                                return True
                            else:
                                try:
                                    w, h = self.device.window_size()
                                    random_x = random.randint(int(w * 0.2), int(w * 0.8))
                                    random_y = random.randint(int(h * 0.3), int(h * 0.7))
                                    self.checknha(random_x, random_y)
                                except:
                                    pass
                                self._add_response_message("Follow thành công", "follow")
                                return True
                
                time.sleep(1.5)
                
            self._add_response_message("Không tìm thấy nút Follow", "follow")
            return False
                
        except Exception:
            return False

    def do_follow(self, max_retry=3, link=None):
        """Follow - Điều hướng dựa trên follow_via_search"""
        follow_via_search = self.delay_config.get('follow_via_search', 0)
        
        if follow_via_search == 1:
            if not link:
                self._add_response_message("[Follow Search] Không có link để follow", "follow")
                return False
            return self.do_follow_via_search(link)
        else:
            return self.do_follow_via_link(max_retry)
    
    # ========== LIKE ==========
    
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
        """Like - KHÔNG dùng lệnh bank, KHÔNG thoát app"""
        if not self.device:
            return False

        if self.stop_flag or is_stop_all():
            return False
        
        self._check_app_status()
        
        self._add_response_message("Đang làm nhiệm vụ Like", "like")
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
                self._add_response_message("Đã Like rồi", "like")
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
                    self._add_response_message("Like thành công", "like")
                    return True
            
            clicked = False
            time.sleep(1.5)
        
        self._add_response_message("Like thất bại", "like")
        return False
    
    # ========== FAVORITE ==========
    
    def do_favorite(self, max_retry=5):
        """Favorite - KHÔNG dùng lệnh bank, KHÔNG thoát app"""
        if not self.device:
            return False

        if self.stop_flag or is_stop_all():
            return False
        
        self._check_app_status()
        
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
                            self._add_response_message("Đã lưu từ trước", "favorite")
                            return True
                        
                        bounds = node.get("bounds", "")
                        if bounds:
                            if self._click_node_by_bounds(node):
                                wait_ui_stable_after_action(self.device, timeout=1.2)
                                return True
                                
            time.sleep(1.5)

            self._add_response_message("Không tìm thấy nút Favorites", "favorite")
            return False
            
        except Exception:
            return False
    
    # ========== API GOLIKE ==========
    
    def _parse_api_response(self, response, func_name="api_call"):
        result = {
            'success': False,
            'status_code': None,
            'message': '',
            'data': None,
            'is_limit': False,
            'is_checkpoint': False,
            'raw_response': None
        }
        
        try:
            result['status_code'] = response.status_code
            
            try:
                resp_json = response.json()
                result['data'] = resp_json
                result['raw_response'] = resp_json
                
                result['message'] = resp_json.get('message', '')
                if not result['message']:
                    result['message'] = resp_json.get('msg', '')
                if not result['message']:
                    result['message'] = resp_json.get('status_message', '')
                if not result['message']:
                    result['message'] = f"HTTP {response.status_code}"
                
                if response.status_code == 200:
                    status_val = resp_json.get('status')
                    if status_val == 200 or status_val is True:
                        result['success'] = True
                    elif isinstance(status_val, int) and status_val < 300:
                        result['success'] = True
                    elif resp_json.get('success') is True:
                        result['success'] = True
                
                msg_lower = result['message'].lower()
                if any(kw in msg_lower for kw in ['limit', 'giới hạn', 'quá nhiều', 'too many']):
                    result['is_limit'] = True
                if any(kw in msg_lower for kw in ['checkpoint', 'verify', 'xác minh']):
                    result['is_checkpoint'] = True
                    
            except json.JSONDecodeError:
                result['message'] = response.text if response.text else f"HTTP {response.status_code}"
                
        except Exception as e:
            result['message'] = f"Exception: {str(e)}"
        
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
            
            data_response = parsed['data'].get("data") if parsed['data'] else None
            
            return {"status": 200, "message": parsed['message'], "data": data_response}
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
                message = parsed.get('message', 'Thành công')
                if parsed.get('data') and isinstance(parsed['data'], dict):
                    message = parsed['data'].get('message', message)
                return {"status": True, "data": parsed.get('data'), "message": message}
            return {"status": False, "message": parsed.get('message', 'Lỗi hoàn thành không xác định')}
        except Exception as e:
            return {"status": False, "message": str(e)}
    
    def _get_job_price(self, job_data):
        try:
            price_keys = ['price_after_cost', 'price_per_after_cost', 'amount', 'reward', 'price', 'money', 'coin']
            for key in price_keys:
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
                return False, "Dừng theo yêu cầu", None, 0
            
            link = job_data.get("link")
            action_type = job_data.get("type")
            ads_id = job_data.get("id")
            job_price = self._get_job_price(job_data)
            
            server_message = job_data.get("message", "")

            if action_type == "follow" and job_price < self.min_follow_price:
                return False, f"Job Follow giá {job_price}đ < {self.min_follow_price}đ", ads_id, job_price

            # Chỉ hỗ trợ like, follow, favorite - KHÔNG comment
            if action_type not in ["like", "follow", "favorite"]:
                return False, "Loại nhiệm vụ không hỗ trợ", None, 0

            if not link or link == "" or link == "null":
                object_id = job_data.get("object_id")
                if object_id:
                    link = f"https://www.tiktok.com/@user/video/{object_id}"
                    self._add_response_message(f"🔧 Build link từ object_id: {object_id} -> {link}")

            if not self._open_link(link):
                return False, "Mở link thất bại", ads_id, job_price

            wait_ui_stable_after_action(self.device, timeout=2)

            success = False
            reason = ""

            if action_type == "like":
                success = self.do_like()
                reason = "Like thất bại" if not success else "Like thành công"
            elif action_type == "follow":
                success = self.do_follow(link=link)
                reason = "Follow thất bại" if not success else "Follow thành công"
            elif action_type == "favorite":
                success = self.do_favorite()
                reason = "Favorite thất bại" if not success else "Favorite thành công"

            if not success:
                return False, reason, ads_id, job_price

            result = self._hoanthanh(ads_id)
            if result.get('status'):
                video_id = self._get_video_id(link)
                self._save_processed_video(video_id)
                success_msg = result.get('message', 'Thành công')
                if server_message:
                    success_msg = f"{success_msg} - {server_message}"
                return True, success_msg, ads_id, job_price
            else:
                return False, result.get('message', 'Lỗi hoàn thành'), ads_id, job_price                
        except Exception as e:
            return False, str(e), None, 0
    
    # ==================== HÀM LẤY USERNAME ====================
    
    def _force_stop_tiktok(self):
        if self.stop_flag or is_stop_all():
            return
        
        pkg = TIKTOK_PACKAGE
        self.device.shell(f"am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:{pkg}")
        
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
        return wait_tiktok_ui_smart(self.device, timeout=20)
    
    def _click_username_by_dump(self):
        try:
            deeplink_url = "tiktok://user/profile"
            self.device.shell(f'am start -a android.intent.action.VIEW -d "{deeplink_url}" {TIKTOK_PACKAGE}')
            
            if not wait_tiktok_ui_smart(self.device, timeout=8):
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
            self._add_response_message(f"Lỗi quét username: {str(e)[:50]}")
            return None
    
    def _get_username_persistent_loop(self):
        self.username_retry_count = 0
        
        while self.username_retry_count < self.max_username_retries and not self.stop_flag and not is_stop_all():
            self.username_retry_count += 1
            self._update_dashboard_status(f"Đang đợi UI load (Lần {self.username_retry_count}/{self.max_username_retries})")
            
            self.device.app_start(TIKTOK_PACKAGE)
            
            wait_time = self.delay_config.get('delay_open', 10)
            self._update_dashboard_status(f"Chờ {wait_time}s TikTok load xong")
            
            elapsed = 0
            while elapsed < wait_time and not self.stop_flag and not is_stop_all():
                sleep_step = min(0.5, wait_time - elapsed)
                time.sleep(sleep_step)
                elapsed += sleep_step
            
            if self.stop_flag or is_stop_all():
                return None
            
            ui_ready = wait_tiktok_ui_smart(self.device, timeout=20)

            if ui_ready:
                self._update_dashboard_status("UI đã xong, đang get Username")
                username = self._click_username_by_dump()
                if username and len(username) > 2:
                    self._add_response_message(f"Đã lấy username: @{username}")
                    self.username_retry_count = 0
                    return username
                self._add_response_message("Không tìm thấy tên trên màn hình")
            else:
                self._add_response_message(f"Quá {wait_time + 20}s máy không load nổi UI. Buộc dừng!")

            if self.username_retry_count < self.max_username_retries:
                self._force_stop_tiktok()
                time.sleep(2)
        
        self._add_response_message(f"Không thể lấy username sau {self.max_username_retries} lần thử. Bỏ qua thiết bị này!")
        return None
    
    # ==================== HÀM ADD TÀI KHOẢN ====================
    
    def verify_account_logic_new(self, username):
        url = "https://gateway.golike.net/api/tiktok-account/verify-account-id"
        username = username.replace('@', '').strip()
        payload = {"unique_id": username}
        
        try:
            res = self.session.post(url, headers=self.headers, json=payload, timeout=25)
            data = res.json()

            if isinstance(data, list):
                msg_error = data[0] if len(data) > 0 else "Lỗi API"
                return False, msg_error, None, None

            message = data.get("message") or data.get("msg") or "Lỗi xác thực"
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
            return False, f"Lỗi: {str(e)}", None, None
    
    def auto_setup_account(self):
        auto_username = self._get_username_persistent_loop()
        if not auto_username:
            return None, None

        self._add_response_message("Kiểm tra acc trên hệ thống")
        chontiktok = self._chonacc()
        for acc in chontiktok.get("data", []):
            if acc.get("unique_username", "").strip().lower() == auto_username:
                self._add_response_message(f" Tài khoản @{auto_username} đã sẵn sàng.")
                return acc.get("id"), auto_username

        self._add_response_message(f" Đang Add tài khoản @{auto_username}")
        ok, msg, acc_id, target_link = self.verify_account_logic_new(auto_username)

        if not ok and target_link:
            self._add_response_message(f" Đang follow link xác minh: {target_link}")
            if self._open_link(target_link):
                wait_ui_stable_after_action(self.device, timeout=2)
                if self.do_follow():
                    self._add_response_message(" Follow xác minh thành công!")
                    time.sleep(2)
                    ok, msg, acc_id, _ = self.verify_account_logic_new(auto_username)
                    self.device.press("back") 
                    time.sleep(1)
                    self.device.press("back") 
                else:
                    self._add_response_message(" Follow xác minh thất bại!")
                    self.device.press("back") 
            else:
                self._add_response_message(" Không thể mở link xác minh!")

        if ok and acc_id:
            self._add_response_message(f" Add thành công! ID: {acc_id}")
            return acc_id, auto_username
        
        self._add_response_message(f" Add thất bại: {msg}")
        return None, None
    
    # ==================== HÀM CHẠY CHÍNH ====================
    
    def run(self):
        temp_account_id = f"temp_{self.serial}"
        self.account_id_val = temp_account_id
        
        with dashboard_lock:
            accounts_data[temp_account_id] = {
                "username": "None",
                "status": "Đang kết nối",
                "last_message": "Đang kết nối thiết bị",
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
        
        self._add_response_message("Đang kết nối thiết bị")
        
        try:
            self.device = u2.connect(self.serial)
            self.device.info
            self._add_response_message(" Kết nối thiết bị thành công")
            
            self._add_response_message(" Đang lấy phiên bản TikTok")
            self.tiktok_version = self._get_tiktok_version()
            if self.tiktok_version:
                self._add_response_message(f" Phiên bản TikTok: {self.tiktok_version}")
                self._update_dashboard_with_version()
            else:
                self._add_response_message(" Không lấy được phiên bản TikTok")
                
        except Exception as e:
            self._add_response_message(f" Kết nối thiết bị thất bại: {str(e)}")
            with dashboard_lock:
                if temp_account_id in accounts_data:
                    del accounts_data[temp_account_id]
            return
        
        if self.force_stop_enabled:
            self._add_response_message(" Đang force stop TikTok")
            self._force_stop_tiktok()
            time.sleep(1.2)
        
        self._add_response_message(" Đang mở TikTok")
        self._start_tiktok_and_wait()
        
        final_account_id, auto_username = self.auto_setup_account()
        
        if not final_account_id or not auto_username:
            self._add_response_message(" Không thể thiết lập tài khoản. Dừng luồng.")
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
                accounts_data[final_account_id]["status"] = "Sẵn sàng"
                accounts_data[final_account_id]["last_message"] = f" Đã xác thực @{auto_username}"
                accounts_data[final_account_id]["tiktok_version"] = self.tiktok_version
                accounts_data[final_account_id]["last_update"] = time.time()
            else:
                accounts_data[final_account_id] = {
                    "username": auto_username,
                    "status": "Sẵn sàng",
                    "last_message": f" Đã xác thực @{auto_username}",
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
            self._add_response_message(" Đang nuôi nick ")
            self.nuoi_nick_short(num_videos=num_videos_khoi_dong, share_rate=share_rate)
        
        self._reset_retry_counter()
        
        while not self.stop_flag and not is_stop_all():
            try:
                self._update_dashboard_status(" Đang tìm nhiệm vụ")
                
                delay_time = self._get_random_delay('job')
                share_rate_cao = random.randint(30, 50)
                self._delay_voi_nuoi_nick(delay_time, "Chờ lấy job", share_rate=share_rate_cao)

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

                    link = data.get("link", "")
                    
                    if not link or link == "" or link == "null":
                        object_id = data.get("object_id")
                        if object_id:
                            link = f"https://www.tiktok.com/@user/video/{object_id}"
                            self._add_response_message(f" Build link từ object_id: {object_id} -> {link}")
                        else:
                            self._add_response_message(f" Không có link và không có object_id, bỏ qua job")
                            skip_msg = self._baoloi(data["id"], data["object_id"], data["type"])
                            continue
                    
                    link = link.strip().split('\n')[0].split('\r')[0]
                    self._update_current_link(link)
                    
                    if self._is_link_processed(link):
                        skip_msg = self._baoloi(data["id"], data["object_id"], data["type"])
                        self._add_response_message(f" Đã bỏ qua video đã làm: {skip_msg.get('message', '')}")
                        continue

                    if data["type"] not in self.lam:
                        skip_msg = self._baoloi(data["id"], data["object_id"], data["type"])
                        self._add_response_message(f" Bỏ qua job {data['type']}: {skip_msg.get('message', '')}")
                        time.sleep(0.5)
                        continue

                    status_map = {
                        "follow": " Đang follow",
                        "like": " Đang like",
                        "favorite": " Đang favorite"
                    }
                    self._update_dashboard_status(status_map.get(data["type"], " Đang xử lý"))

                    success, reason, job_ads_id, job_price = self._process_job(data)

                    if success:
                        self.job_count += 1
                        self._update_dashboard_stats(data["type"], job_price, success=True)
                        self._add_response_message(f" {reason} - Giá: {job_price} xu")
                        
                        delay_time_done = self.delay_config.get('delay_done', 9)
                        share_rate_normal = self.delay_config.get('share_rate', 15)
                        
                        if delay_time_done > 0:
                            self._delay_voi_nuoi_nick(delay_time_done, "Delay sau job", share_rate=share_rate_normal)
                        
                        if self.force_stop_after > 0 and self.job_count >= self.force_stop_after:
                            self._add_response_message(f" Đạt {self.job_count} job, force stop TikTok")
                            self._force_stop_tiktok()
                            self.job_count = 0
                            self._start_tiktok_and_wait()
                    else:
                        self._update_dashboard_stats(data["type"], 0, success=False)
                        self._add_response_message(f" {reason}")
                        
                        num_videos_loi = max(1, self.delay_config.get('nuoi_nick', 2) // 2)
                        share_rate_loi = self.delay_config.get('share_rate', 15)
                        if num_videos_loi > 0:
                            self.nuoi_nick_short(num_videos=num_videos_loi, share_rate=share_rate_loi)
                        
                        self._baoloi(data["id"], data["object_id"], data["type"])
                        time.sleep(0.5)
                else:
                    error_msg = nhanjob.get("message", "Lỗi không xác định")
                    retry_wait = self._increment_retry_counter()
                    self._add_response_message(f"{error_msg} - Thử lại sau {retry_wait}s")
                    
                    num_videos = self.delay_config.get('nuoi_nick', 2)
                    share_rate_cao = random.randint(30, 50)
                    self.nuoi_nick_short(num_videos=num_videos, share_rate=share_rate_cao, is_high_trust_mode=True)
                    
                    self._delay_voi_nuoi_nick(retry_wait, "Thử lại sau", share_rate=share_rate_cao)
                    
            except Exception as e:
                if self.stop_flag or is_stop_all():
                    break
                
                retry_wait = self._increment_retry_counter()
                self._add_response_message(f"Lỗi: {str(e)} - Thử lại sau {retry_wait}s")
                self._delay_voi_nuoi_nick(retry_wait, "Lỗi - Thử lại sau")
        
        self._add_response_message(" Bot đã dừng")


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

\033[38;2;255;200;140m[</>] \033[38;2;200;160;255mADMIN: NHƯ ANH ĐÃ THẤY EM   \033[38;2;255;220;160mPhiên Bản: \033[38;2;120;255;220mv3.24
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
    delay_job = [delay_config['job'][0], delay_config['job'][1]]
    delay_fav = [delay_config['favorite'][0], delay_config['favorite'][1]]
    nuoi_nick = delay_config.get('nuoi_nick', 2)
    share_rate = delay_config.get('share_rate', 15)
    loc_follow = delay_config.get('loc_follow', 0)
    delay_done = delay_config.get('delay_done', 9)
    delay_open = delay_config.get('delay_open', 10)
    follow_via_search = delay_config.get('follow_via_search', 0)
    force_stop_enabled = saved_config.get('force_stop_enabled', False) if saved_config else False
    force_stop_after = saved_config.get('force_stop_after', 0) if saved_config else 0
    
    force_stop = "Yes" if force_stop_enabled else "No"
    stop_job = force_stop_after
    follow_search_status = "Bật" if follow_via_search == 1 else "Tắt"
    
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
            u"[#00ff9c]Follow qua tìm kiếm[/]",
            u"[bold #ffffff]{}[/]".format(follow_search_status),
            u"[#00ffff]{}/OFF[/]".format("ON" if follow_via_search == 1 else "OFF")
        )

        table.add_row(
            u"[#ffd54f]Delay Hoàn Thành[/]",
            u"[bold #ffffff]{}[/]".format(delay_done),
            u"[#00ffff]s[/]"
        )
        
        table.add_row(
            u"[#00ff9c]Delay Mở TikTok[/]",
            u"[bold #ffffff]{}[/]".format(delay_open),
            u"[#00ffff]giây[/]"
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
            input_number(f"Delay Like Min ({delay_like[0]}): ", delay_like[0]),
            input_number(f"Delay Like Max ({delay_like[1]}): ", delay_like[1])
        ]

        delay_follow = [
            input_number(f"Delay Follow Min ({delay_follow[0]}): ", delay_follow[0]),
            input_number(f"Delay Follow Max ({delay_follow[1]}): ", delay_follow[1])
        ]

        delay_job = [
            input_number(f"Delay Get Jobs Min ({delay_job[0]}): ", delay_job[0]),
            input_number(f"Delay Get Jobs Max ({delay_job[1]}): ", delay_job[1])
        ]

        delay_fav = [
            input_number(f"Delay Favorite Min ({delay_fav[0]}): ", delay_fav[0]),
            input_number(f"Delay Favorite Max ({delay_fav[1]}): ", delay_fav[1])
        ]

        nuoi_nick = input_number(f"Số video nuôi nick ({nuoi_nick}): ", nuoi_nick)
        share_rate = input_number(f"Tỷ lệ Copy Link (0-100%) ({share_rate}): ", share_rate)
        loc_follow = input_number(f"Lọc Follow (0 = OFF) ({loc_follow}): ", loc_follow)
        delay_done = input_number(f"Delay Hoàn Thành ({delay_done}): ", delay_done)
        delay_open = input_number(f"Delay sau khi mở TikTok ({delay_open}): ", delay_open)
        
        console.print(u"\n[bold #00ff9c]Follow qua tìm kiếm (Bật/Tắt)[/]")
        follow_search_input = input("Bật follow qua tìm kiếm? (y/n): ").strip().lower()
        follow_via_search = 1 if follow_search_input == "y" else 0
        follow_search_status = "Bật" if follow_via_search == 1 else "Tắt"

        force_stop_input = input("Buộc dừng chạy (y/n): ").strip().lower()
        force_stop_enabled = (force_stop_input == "y")
        force_stop = "Yes" if force_stop_enabled else "No"
        stop_job = input_number(f"Số job buộc dừng ({stop_job}): ", stop_job)

    delay_config = {
        'like': delay_like,
        'follow': delay_follow,
        'favorite': delay_fav,
        'job': delay_job,
        'delay_done': delay_done,
        'delay_open': delay_open,
        'loc_follow': loc_follow,
        'nuoi_nick': nuoi_nick,
        'share_rate': share_rate,
        'follow_via_search': follow_via_search
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
            status = "[blink bold #ffff00] Đang chờ[/]"
        else:
            status = "[dim] Chưa chọn[/]"

        table.add_row(
            f"[{color}]{i+1}[/]",
            f"[{color}]{job['name']}[/]",
            status
        )
    return table


def menu_jobs():
    JOBS = [
        {"id": "like", "name": "Like", "color": "#ff9ecb"},
        {"id": "follow", "name": "Follow", "color": "#ffd54f"},
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
            
            ans = console.input(f"\n[#ff9ecb]➤ [#ffffff]Bạn có muốn làm nhiệm vụ [bold]{job['name']}[/] không? (y/n) [y]: ").strip().lower()
            
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
        console.print(f"\n[#ffffff] Nhiệm vụ đã chọn:[/] [bold #00ffff]{', '.join(job['name'] for job in JOBS if job['id'] in selected_jobs)}[/]")
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
                    battery_display = u"[bold green]█[/bold green]" * (b // 10) + f"[green]{b}%[/green]"
                elif b >= 50:
                    battery_display = u"[bold yellow]█[/bold yellow]" * (b // 10) + f"[yellow]{b}%[/yellow]"
                elif b >= 20:
                    battery_display = u"[bold orange1]█[/bold orange1]" * (b // 10) + f"[orange1]{b}%[/orange1]"
                else:
                    battery_display = u"[bold red]█[/bold red]" * (b // 10) + f"[red]{b}%[/red]"
            except:
                battery_display = f"[cyan]{battery}%[/cyan]"
        else:
            battery_display = "[dim]None[/dim]"
        
        version_display = f"[#a78bfa]{tiktok_version}[/]" if tiktok_version != "None" else "[dim]None[/]"

        table.add_row(
            str(i + 1),
            f"[#00ff9c]{d.serial}[/]",
            f"[#ffd54f]{model}[/]",
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
                console.print(f"[green]✓ Đã chọn tất cả {len(selected_serials)} thiết bị[/]")
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
                console.print(f"[green]✓ Đã chọn {len(selected_serials)} thiết bị[/]")
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
            error_msg = response_json.get("message", f"HTTP {response.status_code}")
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
        console.print(u" Chưa có Authorization nào! Vui lòng nhập Authorization.")
        new_auth = console.input(u" Nhập Authorization: ").strip()
        if new_auth:
            save_authorization(new_auth)
            return new_auth
        else:
            console.print(u"Authorization không được để trống!")
            sys.exit(1)
    
    session = requests.Session()
    patch_session_with_custom_dns(session)
    
    for token in auth_tokens:
        result = get_user_me(token, session)
        accounts.append(result)
    
    acc_lines = []
    for i, acc in enumerate(accounts):
        idx = f"{i+1:02d}"
        
        if acc.get("success"):
            username = acc.get("username", "Unknown")
            coin = acc.get("coin", 0)
            line = f"[#00ffff][{idx}][/] [#ff99cc]{username}[/] | [#99ff99]{coin} coin[/]"
        else:
            msg = acc.get('message', 'Lỗi hệ thống')[:30]
            line = f"[#00ffff][{idx}][/] [red]:[/] [#ff4444]{msg}[/]"
        
        acc_lines.append(line)
    
    acc_content = "\n".join(acc_lines)
    
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
        u'[#cccccc]Enter: [#ff9ecb]để tiếp tục [#d7d7a8]với tài khoản đã [#ffd4b8]chọn nhập [#ff9ecb]"t" [#99ff99]thêm tài [#ff9ecb]khoản mới [#00ffff]nhập số [#ff6b6b]để chọn [#99ff99]tài khoản:[/]',
        border_style="#d7d7a8",
        padding=(0, 1),
        width=80
    )
    console.print(panel_input)
    
    choice = console.input(u"[#ff9ecb]➤ [#ffffff]Lựa chọn: [/]").strip().lower()
    
    if choice == '':
        valid_accounts = [acc for acc in accounts if acc.get("success")]
        if valid_accounts:
            selected = valid_accounts[0]
            console.print(f"\n[bold #00ff9c] Đã chọn tài khoản: {selected['username']} | {selected['coin']} coin[/]")
            time.sleep(1.5)
            return selected["auth"]
        else:
            console.print(u" Không có tài khoản hợp lệ nào!")
            sys.exit(1)
    elif choice == 't':
        new_auth = console.input(u"\n[white] Authorization mới: [/]").strip()
        if not new_auth:
            console.print(u" Authorization không được để trống!")
            time.sleep(1.5)
            return display_auth_menu()
        
        console.print(u" Đang kiểm tra Authorization")
        session = requests.Session()
        patch_session_with_custom_dns(session)
        result = get_user_me(new_auth, session)
        
        if result.get("success"):
            console.print(f" Authorization hợp lệ! [{result['username']}] | {result['coin']} coin")
            save_authorization(new_auth)
            time.sleep(1.5)
            return new_auth
        else:
            console.print(f" Authorization không hợp lệ! Lỗi: {result.get('message', 'Unknown error')}")
            confirm = input("Authorization không hợp lệ, bạn vẫn muốn lưu? (y/n): ").strip().lower()
            if confirm == 'y':
                save_authorization(new_auth)
                return new_auth
            return display_auth_menu()
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(accounts):
            acc = accounts[idx]
            if acc.get("success"):
                console.print(f"\n[bold #00ff9c] Đã chọn tài khoản: {acc['username']} | {acc['coin']} coin[/]")
                time.sleep(1.5)
                return acc["auth"]
            else:
                console.print(u" Tài khoản này không hợp lệ!")
                time.sleep(1.5)
                return display_auth_menu()
        else:
            console.print(u" Số không hợp lệ!")
            time.sleep(1)
            return display_auth_menu()
    else:
        console.print(u" Lựa chọn không hợp lệ!")
        time.sleep(1)
        return display_auth_menu()


import time
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich import box
from rich.live import Live
import os
from collections import deque

# Biến global lưu thời gian bắt đầu tool để hiển thị lên UI
if 'APP_START_TIME' not in globals():
    APP_START_TIME = time.time()

# Thêm queue để lưu log cho console
if 'console_logs' not in globals():
    console_logs = deque(maxlen=50)  # Giữ tối đa 50 dòng log

# Thêm queue để đồng bộ tablet
if 'tablet_sync_queue' not in globals():
    tablet_sync_queue = deque(maxlen=100)
    last_sync_time = time.time()
    SYNC_INTERVAL = 0.3  # Sync mỗi 0.3 giây

# THÊM BIẾN SCROLL CHO TABLE
scroll_offset = 0
VISIBLE_ROWS = 20  # Chỉ hiển thị 20 dòng mỗi lần
last_scroll_time = time.time()
SCROLL_INTERVAL = 2.0  # Scroll mỗi 2 giây

# THÊM BIẾN DELAY COUNTDOWN
delay_remaining = 0
last_delay_update = time.time()

def add_console_log(message, level="INFO"):
    """Thêm log vào console với timestamp"""
    timestamp = time.strftime('%H:%M:%S')
    color_map = {
        "INFO": "#00ffff",      # Cyan sáng
        "SUCCESS": "#00ff9c",   # Xanh lá sáng
        "WARNING": "#ffd54f",   # Vàng
        "ERROR": "#ff4d6d",     # Đỏ
        "DEBUG": "#a78bfa"      # Tím nhạt
    }
    color = color_map.get(level, "#ffffff")
    log_entry = f"[{color}][{timestamp}] [{level}][/] {message}"
    console_logs.append(log_entry)

def get_console_content():
    """Lấy nội dung console để hiển thị"""
    if not console_logs:
        return "[dim]Chưa có hoạt động nào[/dim]"
    return "\n".join(console_logs)

def get_status_color(status):
    """Lấy màu dựa trên trạng thái - HÀM MỚI CHỈ ĐỂ ĐỒNG BỘ MÀU, KHÔNG ẢNH HƯỞNG LOGIC CHÍNH"""
    status_lower = status.lower()
    if any(word in status_lower for word in ["error", "lỗi", "fail", "thất bại"]):
        return "#ff4d6d"  # Đỏ
    elif any(word in status_lower for word in ["ok", "thành công", "ready", "xong"]):
        return "#00ff9c"  # Xanh lá
    elif any(word in status_lower for word in ["đang", "running", "processing", "chạy"]):
        return "#ffd54f"  # Vàng
    else:
        return "#ffffff"  # Trắng mặc định

def sync_tablet_data():
    """Đồng bộ dữ liệu màu với tablet - HÀM MỚI, KHÔNG ẢNH HƯỞNG CODE CŨ"""
    global last_sync_time
    
    current_time = time.time()
    if current_time - last_sync_time < SYNC_INTERVAL:
        return
    
    try:
        with dashboard_lock:
            # Chỉ lấy dữ liệu màu sắc cần đồng bộ
            color_data = {}
            for acc_id, data in accounts_data.items():
                status = data.get("status", "đang chờ")
                color_data[acc_id] = {
                    'status': status,
                    'color': get_status_color(status),
                    'device': data.get("device_serial", "?")[-16:],
                    'username': data.get("username", "?")[:10],
                    'timestamp': time.time()
                }
        
        # Thêm vào queue để xử lý bất đồng bộ (non-blocking)
        tablet_sync_queue.append({
            'type': 'color_update',
            'data': color_data,
            'timestamp': current_time
        })
        
        # Có thể gửi dữ liệu qua network/socket ở đây nếu cần
        # Ví dụ: send_to_tablet(color_data)
        
        last_sync_time = current_time
        
    except Exception as e:
        # Log lỗi nhưng không break main flow
        add_console_log(f"Sync tablet warning: {str(e)}", "WARNING")

def update_delay_countdown():
    """Cập nhật delay countdown từ luồng chính"""
    global delay_remaining, last_delay_update
    
    # Lấy delay từ accounts_data nếu có (tìm bất kỳ account nào đang delay)
    current_time = time.time()
    
    with dashboard_lock:
        for acc_id, data in accounts_data.items():
            if 'delay_until' in data and data['delay_until']:
                delay_end = data['delay_until']
                remaining = max(0, int(delay_end - current_time))
                
                if remaining != delay_remaining:
                    delay_remaining = remaining
                    last_delay_update = current_time
                return
        
        # Không có delay, reset
        if delay_remaining != 0:
            delay_remaining = 0
            last_delay_update = current_time

def build_dashboard_table(animator=None):
    global scroll_offset, last_scroll_time, delay_remaining
    
    # Cập nhật delay mỗi khi build table
    update_delay_countdown()
    
    table = Table(
        title="DS",
        title_justify="center",
        show_header=True,
        header_style="#ffffff",
        border_style="#ffffff",
        box=box.ROUNDED,
        show_lines=True
    )

    table.add_column("STT", justify="center", style="#a78bfa")  
    table.add_column("Device", style="#a78bfa")  
    table.add_column("usname", style="#00ffff")  
    table.add_column("Fail", justify="center", style="#ff4d6d")  
    table.add_column("Type", justify="center", style="#38bdf8")  
    table.add_column("Xu", justify="center", style="#facc15")  
    table.add_column("Tổng", justify="center", style="#facc15")  
    table.add_column("Done", style="#ff9ecb")  
    table.add_column("Message", style="#ffffff")  
    
    with dashboard_lock:  
        devices_list = []  
        for acc_id, data in accounts_data.items():  
            last_update = data.get("last_update", 0)  
            devices_list.append((last_update, acc_id, data))  
        
        devices_list.sort(key=lambda x: x[0], reverse=True)
        
        total_devices = len(devices_list)
        
        # KHÔNG GIỚI HẠN - HIỂN THỊ TOÀN BỘ DEVICES
        # Bỏ scroll window, hiển thị tất cả device thật
        devices_to_show = devices_list
        start_idx = 0
        end_idx = total_devices
        
        # Hiển thị tất cả các dòng
        for actual_stt, (_, acc_id, data) in enumerate(devices_to_show, 1):
            status = str(data.get("status", "đang chờ"))  
            job_type = data.get("job_type", "")  
            msg_time = data.get("message_time", "")  
            time_display = f"[dim]{msg_time}[/dim] " if msg_time else ""  
            
            # Check nếu đang trong delay và có hiển thị countdown
            if 'delay_until' in data and data['delay_until']:
                delay_end = data['delay_until']
                remaining = max(0, int(delay_end - time.time()))
                if remaining > 0:
                    status = f"Delay {remaining}s"
                    
                    # GIỮ NGUYÊN LOGIC LOG CHỈ 1 LẦN DUY NHẤT
                    if 'last_delay_log' not in data or data.get('last_delay_log') != remaining:
                        # Chỉ log khi bắt đầu delay hoặc khi remaining thay đổi đáng kể
                        if remaining == 5 or remaining <= 1 or 'last_delay_log' not in data:
                            device_serial = data.get("device_serial", "?")[-16:]
                            add_console_log(
                                f"[#a78bfa]Device [{device_serial}][/] - [#00ffff]{data.get('username', '?')[:10]}[/]: [#ffd54f]Đang delay {remaining}s[/#ffd54f]",
                                "WARNING"
                            )
                            data['last_delay_log'] = remaining
            
            # GIỮ NGUYÊN LOGIC LOG CŨ (chỉ log khi status thay đổi)
            if 'last_status' not in data or data.get('last_status') != status:  
                # Chỉ log nếu không phải là delay (delay đã được log riêng)
                if not (data.get('delay_until') and 'Delay' in status):
                    device_serial = data.get("device_serial", "?")[-16:]
                    add_console_log(
                        f"[#a78bfa]Device [{device_serial}][/] - [#00ffff]{data.get('username', '?')[:10]}[/]: "
                        f"{('[#00ff9c]'+status+'[/]') if any(w in status.lower() for w in ['thành công','xong','ok']) else ('[#ff4d6d]'+status+'[/]') if any(w in status.lower() for w in ['lỗi','fail','error']) else ('[#ffd54f]'+status+'[/]')}",
                        "SUCCESS" if "thành công" in status or "xong" in status else
                        "ERROR" if "lỗi" in status or "fail" in status else "INFO"
                    )
                    data['last_status'] = status
            
            # GIỮ NGUYÊN LOGIC HIỂN THỊ STATUS CŨ
            if any(word in status.lower() for word in ["error", "lỗi", "fail", "thất bại"]):  
                status_display = f"[#ff4d6d]{status}[/#ff4d6d]"  
            elif any(word in status.lower() for word in ["ok", "thành công", "ready", "xong"]):  
                status_display = f"[#00ff9c]{status}[/#00ff9c]"
            elif 'delay' in status.lower():
                # Delay có màu vàng và hiển thị countdown
                status_display = f"[#ffd54f]{status}[/#ffd54f]"
            else:  
                status_display = f"[#ffd54f]{status}[/#ffd54f]"  
            
            table.add_row(  
                str(actual_stt),  
                data.get("device_serial", "?")[-16:],  
                data.get("username", "?")[:10],  
                str(data.get("fail", 0)),  
                job_type.upper()[:12] if job_type else "None",  
                str(data.get("xu", 0)),  
                str(data.get("total_xu", 0)),  
                str(data.get("done", 0)),  
                f"{time_display}{status_display}"  
            )
    
    # GỌI HÀM SYNC MÀU (HÀM MỚI THÊM, KHÔNG ẢNH HƯỞNG GÌ ĐẾN CODE CŨ)
    sync_tablet_data()
    
    return table

def make_dashboard_layout(animator):
    global delay_remaining
    
    layout = Layout()

    run_time = int(time.time() - APP_START_TIME)  
    mins, secs = divmod(run_time, 60)  
    hours, mins = divmod(mins, 60)  
    run_time_str = f"{hours}h {mins}m" if hours else f"{mins} phút"  
    start_time_str = time.strftime('%H:%M', time.localtime(APP_START_TIME))  

    with dashboard_lock:  
        total_xu = sum(d.get("total_xu", 0) for d in accounts_data.values())  
        total_done = sum(d.get("done", 0) for d in accounts_data.values())  
        total_fail = sum(d.get("fail", 0) for d in accounts_data.values())  
        total_devices = len(accounts_data)  

    # Bỏ width cố định để auto co giãn
    # Thêm box delay countdown nếu có
    if delay_remaining > 0:
        box1_content = f"[#00ff9c]⏰ DELAY:[/] [#ffd54f]{delay_remaining}s[/#ffd54f]\n[#00ff9c]Thời gian bắt đầu:[/] {start_time_str}"  
    else:
        box1_content = f"[#00ff9c]Thời gian bắt đầu:[/] {start_time_str}\n[#00ff9c]Đã chạy được:[/] {run_time_str}"
    
    box2_content = f"[#ffd54f]Số jobs đã làm:[/] {total_done} (Fail: {total_fail})\n[#ffd54f]Số xu đã nhận:[/] {total_xu}"  
    
    panel1 = Panel(box1_content, border_style="#ff9ecb", box=box.ROUNDED)
    panel2 = Panel(box2_content, border_style="#ff9ecb", box=box.ROUNDED, padding=(0, 1))
    
    # Thêm panel thứ 3 hiển thị tổng số thiết bị
    box3_content = f"[#a78bfa]Tổng thiết bị:[/] {total_devices}\n[#a78bfa]Đang hoạt động:[/] {sum(1 for d in accounts_data.values() if 'đang' in d.get('status', '').lower())}"
    panel3 = Panel(box3_content, border_style="#ff9ecb", box=box.ROUNDED)
    
    header_grid = Table.grid(expand=True, padding=(0, 2))
    header_grid.add_column(ratio=1)
    header_grid.add_column(ratio=1)
    header_grid.add_column(ratio=1)
    header_grid.add_row(panel1, panel2, panel3)

    # ✅ TÍNH CHIỀU CAO TABLE THEO DATA THẬT
    rows = total_devices
    table_height = rows * 2 + 5  # Mỗi dòng ~2 lines + header + border
    
    # ✅ GIỚI HẠN THEO MÀN HÌNH (KHÔNG GIỚI HẠN DATA)
    try:
        screen_height = console.height
        header_height = 5
        console_min = 6  # Console tối thiểu 6 dòng
        
        max_table = screen_height - header_height - console_min
        table_height = min(table_height, max_table)
        # Đảm bảo table_height không âm và tối thiểu 5
        table_height = max(5, table_height)
    except:
        pass
    
    # ✅ UPDATE LAYOUT - BỎ RATIO, DÙNG SIZE THỰC
    layout.split(
        Layout(name="header", size=5),           # Header cố định 5 dòng
        Layout(name="table", size=table_height), # Table size tính theo số device
        Layout(name="console", ratio=1)          # Console chiếm phần còn lại
    )  

    layout["header"].update(header_grid)  
    layout["table"].update(build_dashboard_table(animator))  
    
    # Chỉ hiển thị 10 dòng log cuối cùng
    console_content = "\n".join(list(console_logs)[-10:])
    
    console_panel = Panel(
        console_content,
        title="Console",
        border_style="#00ffff",
        box=box.ROUNDED,
        padding=(0, 1)
    )

    layout["console"].update(console_panel)

    return layout

def run_dashboard():
    if hasattr(os, 'nice'):
        try:
            os.nice(10)
        except:
            pass

    add_console_log("Dashboard khởi động", "SUCCESS")  
    add_console_log(f"Giám sát {len(accounts_data)} thiết bị", "INFO")  

    animator = BorderAnimator(width=80, height=20)  
    frame_rate = 20  
    frame_duration = 1.0 / frame_rate  

    layout = make_dashboard_layout(animator)  
    last_size = console.size  

    with Live(  
        layout,  
        refresh_per_second=frame_rate,  
        screen=True,  
        auto_refresh=False,  
        transient=False  
    ) as live:  

        last_frame_time = time.time()  
        last_log_time = time.time()  

        while not is_stop_all():  
            try:  
                current_size = console.size  
                if current_size != last_size:  
                    layout = make_dashboard_layout(animator)  
                    live.update(layout)  
                    last_size = current_size  

                current_time = time.time()  
                delta = current_time - last_frame_time  

                if delta >= frame_duration:  
                    animator.update()  
                    new_layout = make_dashboard_layout(animator)  
                    if new_layout is not None:  
                        for child in layout.children:  
                            try:  
                                layout[child.name].update(  
                                    new_layout[child.name].renderable  
                                )  
                            except:  
                                pass  
                    live.refresh()  
                    last_frame_time = current_time  
                else:  
                    time.sleep(0.001)  
                    
                if current_time - last_log_time >= 30:  
                    with dashboard_lock:  
                        total_xu = sum(d.get("total_xu", 0) for d in accounts_data.values())  
                        total_done = sum(d.get("done", 0) for d in accounts_data.values())  
                        active_jobs = sum(1 for d in accounts_data.values()   
                                        if "đang" in d.get("status", "").lower())  
                    add_console_log(f"Thống kê: {total_done} jobs hoàn thành, {total_xu} xu, {active_jobs} jobs đang chạy", "INFO")  
                    last_log_time = current_time  
                    
            except Exception as e:  
                add_console_log(f"Lỗi dashboard: {str(e)}", "ERROR")  
                time.sleep(0.01)


# ==================== MAIN ====================
if __name__ == "__main__":
    clear_stop_all()
    
    stop_event = threading.Event()
    
    def signal_handler(sig, frame):
        print("\n\033[93m Đang dừng tất cả các thiết bị...\033[0m")
        set_stop_all()
        stop_event.set()
        time.sleep(2)
        print("\033[92m Đã dừng toàn bộ tool\033[0m")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except:
        pass
    
    banner()
    
    auth_token = display_auth_menu()
    console.print(" Đã chọn Authorization")
    time.sleep(1)
    
    console.print("[yellow] CẤU HÌNH DELAY VÀ THÔNG SỐ[/]")
    delay_config, min_follow_price, force_stop_enabled, force_stop_after = setup_delay_config()
    
    lam = menu_jobs()
    
    console.print("[yellow] Tiến hành kết nối thiết bị ADB[/]")
    
    selected_serials = select_devices()
    
    if not selected_serials:
        console.print("[red] Không có thiết bị nào được chọn! Thoát tool.[/]")
        sys.exit(1)
    
    console.print(f" Đã chọn {len(selected_serials)} thiết bị để chạy song song")
    time.sleep(2)
    
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()
    time.sleep(2)
    
    console.print(f"[bold green] BẮT ĐẦU CHẠY {len(selected_serials)} THIẾT BỊ SONG SONG[/]")
    
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
            while futures:
                if stop_event.is_set() or is_stop_all():
                    console.print("\n[yellow] Đang hủy các tác vụ còn lại...[/]")
                    for future in futures:
                        future.cancel()
                    break
                
                done = []
                for future in list(futures.keys()):
                    if future.done():
                        done.append(future)
                
                if done:
                    for future in done:
                        try:
                            future.result(timeout=0.1)
                        except KeyboardInterrupt:
                            raise
                        except Exception as e:
                            pass
                        del futures[future]
                else:
                    time.sleep(0.1)

        except KeyboardInterrupt:
            console.print("\n[yellow] Người dùng yêu cầu dừng (CTRL+C)[/]")
            set_stop_all()
            stop_event.set()
            
            for future in futures:
                future.cancel()
            
            console.print("[green] Đã dừng tất cả các luồng[/]")
            sys.exit(0)
