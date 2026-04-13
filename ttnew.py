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

# ==================== CẤU HÌNH MÚI GIỜ VIỆT NAM CHUẨN ====================
os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
if hasattr(time, 'tzset'):
    time.tzset()

VN_TZ = timezone(timedelta(hours=7))

def get_vn_time():
    return datetime.now(VN_TZ)

# ==================== THÊM STOP_FLAG CHO DỪNG KHẨN CẤP ====================
STOP_FLAG = False
STOP_LOCK = threading.Lock()

def set_stop_flag():
    global STOP_FLAG
    with STOP_LOCK:
        STOP_FLAG = True

def clear_stop_flag():
    global STOP_FLAG
    with STOP_LOCK:
        STOP_FLAG = False

def check_stop():
    with STOP_LOCK:
        if STOP_FLAG:
            raise Exception("STOP_FLAG triggered - Dừng khẩn cấp")

def check_stop_safe():
    with STOP_LOCK:
        return STOP_FLAG

# ==================== TỐI ƯU HIỆU NĂNG & CHỐNG TREO ====================
_ui_dump_cache = {"xml": "", "timestamp": 0, "nodes": []}
_UI_DUMP_CACHE_TTL = 0.5
_UI_DUMP_LAST_CALL = 0
_UI_DUMP_CALL_COUNT = 0

_MAX_RESPONSE_MESSAGES = 100
_MAX_TEMP_MESSAGES = 50
_LAST_GC_TIME = 0
_GC_INTERVAL = 300

_job_counter_since_restart = 0
_error_counter_since_restart = 0
_MAX_JOBS_BEFORE_RESTART = 100
_MAX_ERRORS_BEFORE_RESTART = 10
_LAST_RESTART_TIME = 0
_RESTART_COOLDOWN = 60

_REQUESTS_TIMEOUT = 30
_REQUESTS_RETRY_COUNT = 3
_REQUESTS_RETRY_BACKOFF = [2, 5, 10]

# ==================== KIỂM TRA VÀ RECONNECT ADB ĐỊNH KỲ ====================
_last_adb_check_time = 0
_ADB_CHECK_INTERVAL = 30

def check_and_reconnect_adb():
    """Kiểm tra và reconnect ADB nếu mất kết nối"""
    global device, device_serial, _last_adb_check_time
    
    now = time.time()
    if now - _last_adb_check_time < _ADB_CHECK_INTERVAL:
        return True
    
    _last_adb_check_time = now
    
    try:
        if device:
            device.info
            return True
    except Exception as e:
        add_response_message(u"[WARN] Mất kết nối ADB: {}".format(str(e)[:50]))
    
    try:
        add_response_message(u"[INFO] Đang reconnect ADB...")
        device = u2.connect(device_serial)
        device.info
        add_response_message(u"[OK] Reconnect ADB thành công")
        try:
            device.app_start(TIKTOK_PACKAGE)
            time.sleep(2)
        except:
            pass
        return True
    except Exception as e:
        add_response_message(u"[ERROR] Reconnect ADB thất bại: {}".format(str(e)[:50]))
        return False

def gc_if_needed():
    global _LAST_GC_TIME
    now = time.time()
    if now - _LAST_GC_TIME > _GC_INTERVAL:
        gc.collect()
        _LAST_GC_TIME = now
        if logger:
            logger.info("Auto GC performed")

def requests_with_retry(method, url, **kwargs):
    timeout = kwargs.pop('timeout', _REQUESTS_TIMEOUT)
    
    for attempt in range(_REQUESTS_RETRY_COUNT):
        try:
            if method.upper() == 'GET':
                return requests.get(url, timeout=timeout, **kwargs)
            elif method.upper() == 'POST':
                return requests.post(url, timeout=timeout, **kwargs)
            else:
                return requests.request(method, url, timeout=timeout, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < _REQUESTS_RETRY_COUNT - 1:
                wait = _REQUESTS_RETRY_BACKOFF[attempt]
                add_response_message(u"[RETRY] Request thất bại, thử lại sau {}s: {}".format(wait, str(e)[:50]))
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            raise

def soft_reset_if_needed():
    global _job_counter_since_restart, _error_counter_since_restart, _LAST_RESTART_TIME
    
    now = time.time()
    if now - _LAST_RESTART_TIME < _RESTART_COOLDOWN:
        return False
    
    should_reset = False
    reason = ""
    
    if _job_counter_since_restart >= _MAX_JOBS_BEFORE_RESTART:
        should_reset = True
        reason = u"đã chạy {} job".format(_job_counter_since_restart)
    elif _error_counter_since_restart >= _MAX_ERRORS_BEFORE_RESTART:
        should_reset = True
        reason = u"quá nhiều lỗi ({})".format(_error_counter_since_restart)
    
    if should_reset:
        add_response_message(u"[RESET] Soft reset do {} - Đang khởi động lại kết nối...".format(reason))
        
        _job_counter_since_restart = 0
        _error_counter_since_restart = 0
        _LAST_RESTART_TIME = now
        
        global _ui_dump_cache
        _ui_dump_cache = {"xml": "", "timestamp": 0, "nodes": []}
        
        try:
            restart_tiktok(device)
        except:
            pass
        
        return True
    
    return False

def increment_job_counter():
    global _job_counter_since_restart
    _job_counter_since_restart += 1
    soft_reset_if_needed()

def increment_error_counter():
    global _error_counter_since_restart
    _error_counter_since_restart += 1
    soft_reset_if_needed()

def wait_for_ui_stable(d, wait_time=2.5, extra_wait=0.5):
    check_stop()
    
    wait_time = min(wait_time, 10)
    extra_wait = min(extra_wait, 3)
    
    remaining = wait_time
    while remaining > 0 and not check_stop_safe():
        sleep_chunk = min(0.1, remaining)
        time.sleep(sleep_chunk)
        remaining -= sleep_chunk
    
    if extra_wait > 0:
        remaining_extra = extra_wait
        while remaining_extra > 0 and not check_stop_safe():
            sleep_chunk = min(0.1, remaining_extra)
            time.sleep(sleep_chunk)
            remaining_extra -= sleep_chunk
    
    check_stop()
    return True

def wait_for_element(d, selector, timeout=10, check_interval=0.5):
    start = time.time()
    timeout = min(timeout, 30)
    
    while time.time() - start < timeout:
        check_stop()
        try:
            elem = d(**selector) if isinstance(selector, dict) else selector
            if elem.exists(timeout=0.3):
                return elem
        except Exception:
            pass
        time.sleep(check_interval)
    return None

def wait_for_any_element(d, selectors, timeout=10, check_interval=0.3):
    start = time.time()
    timeout = min(timeout, 30)
    
    while time.time() - start < timeout:
        check_stop()
        for selector in selectors:
            try:
                elem = d(**selector)
                if elem.exists(timeout=0.2):
                    return elem, selector
            except Exception:
                continue
        time.sleep(check_interval)
    return None, None

def wait_and_click(d, selectors, timeout=5, check_interval=0.3):
    start_time = time.time()
    timeout = min(timeout, 15)
    
    while time.time() - start_time < timeout:
        if check_stop_safe():
            return False
        for selector in selectors:
            try:
                obj = d(**selector)
                if obj.exists(timeout=0.3):
                    obj.click()
                    return True
            except Exception:
                continue
        time.sleep(check_interval)
    return False

def wait_for_click_verify(d, selector, timeout=10, verify_selector=None, verify_timeout=3):
    timeout = min(timeout, 30)
    
    elem = wait_for_element(d, selector, timeout)
    if not elem:
        add_response_message(u"[ERROR] Không tìm thấy element để click trong {}s".format(timeout))
        return False
    
    try:
        elem.click()
        add_response_message(u"[OK] Đã click element")
    except Exception as e:
        add_response_message(u"[ERROR] Click thất bại: {}".format(str(e)))
        return False
    
    if verify_selector:
        wait_for_ui_stable(d, wait_time=1.0)
        verify_elem = wait_for_element(d, verify_selector, verify_timeout)
        if verify_elem:
            add_response_message(u"[OK] Xác nhận thành công")
            return True
        else:
            add_response_message(u"[WARN] Xác nhận thất bại - không thấy element")
            return False
    
    return True

# ==================== HÀM SHARE VÀ COPY LINK ====================
def do_share_and_copy_link(d, max_retry=2):
    try:
        d.implicitly_wait(0)
        add_response_message(u"[INFO] Đang tìm nút Share...")

        share_selectors = [
            {"descriptionContains": "share"},
            {"descriptionContains": "gửi"},
            {"descriptionContains": "chia sẻ"},
            {"textContains": "Share"},
            {"textContains": "Gửi"}
        ]

        start_time = time.time()
        clicked_share = False
        while time.time() - start_time < 15:
            if check_stop_safe(): 
                return False
            for s in share_selectors:
                if d(**s).exists:
                    d(**s).click()
                    clicked_share = True
                    break
            if clicked_share: 
                break
            time.sleep(0.2)

        if not clicked_share:
            add_response_message(u"[ERROR] Không tìm thấy nút Share sau 15s")
            return False

        add_response_message(u"[OK] Đã mở menu Share")

        copy_selectors = [
            {"text": "Sao chép liên kết"},
            {"textContains": "Sao chép"},
            {"textContains": "liên kết"},
            {"text": "Copy link"},
            {"textContains": "Copy"},
            {"textContains": "link"},
            {"descriptionContains": "copy"},
            {"descriptionContains": "link"}
        ]

        start_time = time.time()
        clicked_copy = False
        while time.time() - start_time < 10:
            if check_stop_safe(): 
                return False
            for s in copy_selectors:
                if d(**s).exists:
                    d(**s).click()
                    clicked_copy = True
                    break
            if clicked_copy: 
                break
            time.sleep(0.2)

        if clicked_copy:
            add_response_message(u"[OK] Đã sao chép liên kết")
            time.sleep(0.5)
            if d(textMatches="(?i)(Sao chép liên kết|Copy link)").exists:
                d.press("back")
            return True
        else:
            add_response_message(u"[ERROR] Không tìm thấy nút Sao chép liên kết")
            d.press("back")
            return False

    except Exception as e:
        add_response_message(u"[ERROR] Lỗi Share/Copy: {}".format(str(e)))
        return False

# ==================== HÀM NUÔI NICK NÂNG CAO ====================
def nuoi_nick_short(d, num_videos=2, share_rate=15, is_high_trust_mode=False):
    try:
        if is_high_trust_mode:
            share_rate = random.randint(30, 50)
            add_response_message(u"[HIGH TRUST] Đang lượt nuôi nick ({} video)...".format(num_videos))
        else:
            add_response_message(u"[INFO] Đang lượt trang chủ nuôi nick ({} video, tỷ lệ copy link {}%)...".format(num_videos, share_rate))
        
        for _ in range(1):
            d.press("back")
            time.sleep(0.2)
        
        time.sleep(0.8)
        
        try:
            home_tab = d(text="Home", resourceIdMatches=".*tab.*")
            if home_tab.exists:
                home_tab.click()
                time.sleep(0.5)
        except:
            pass
        
        success_share_count = 0
        min_watch, max_watch = 5, 12
        
        for i in range(num_videos):
            if check_stop_safe():
                break
            
            watch_time = random.uniform(min_watch, max_watch)
            add_response_message(u"[VIDEO] Xem video {}/{} ({:.0f}s)".format(i+1, num_videos, watch_time))
            
            remaining = watch_time
            while remaining > 0 and not check_stop_safe():
                sleep_time = min(0.5, remaining)
                time.sleep(sleep_time)
                remaining -= sleep_time
            
            if check_stop_safe():
                break
            
            should_share = random.randint(1, 100) <= share_rate
            
            if should_share:
                add_response_message(u"[SHARE] Video {}: Thử Share và Copy Link...".format(i+1))
                if do_share_and_copy_link(d):
                    success_share_count += 1
                time.sleep(random.uniform(0.8, 1.5))
            
            w, h = d.window_size()
            x_mid = int(w * 0.5)
            start_y = int(h * 0.85)
            end_y = int(h * 0.2)
            d.swipe(x_mid, start_y, x_mid, end_y, duration=random.uniform(0.15, 0.3))
            
            time.sleep(random.uniform(0.5, 1.0))
        
        if success_share_count > 0:
            add_response_message(u"[OK] Đã hoàn thành lượt video nuôi nick (Đã Share/Copy {} link)".format(success_share_count))
        else:
            add_response_message(u"[OK] Đã hoàn thành lượt video nuôi nick")
        
        return success_share_count
        
    except Exception as e:
        if "STOP_FLAG" not in str(e):
            add_response_message(u"[ERROR] Lỗi nuôi nick: {}".format(str(e)))
        return 0

def nuoi_nick_thong_minh(d, delay_seconds, share_rate=15):
    if delay_seconds <= 0:
        return 0
    
    delay_seconds = min(delay_seconds, 300)
    
    time_per_video = 10
    max_videos = max(1, delay_seconds // time_per_video)
    max_videos = min(max_videos, 5)
    
    if max_videos > 0:
        add_response_message(u"[NUÔI] Nuôi nick thông minh: {}s -> lượt {} video".format(delay_seconds, max_videos))
        start_time = time.time()
        nuoi_nick_short(d, num_videos=max_videos, share_rate=share_rate)
        elapsed = time.time() - start_time
        
        remaining = delay_seconds - elapsed
        if remaining > 0:
            add_response_message(u"[WAIT] Còn {:.0f}s, đợi thêm...".format(remaining))
            for remaining_sec in range(int(remaining), 0, -1):
                if check_stop_safe():
                    break
                if remaining_sec % 5 == 0 or remaining_sec <= 3:
                    update_account_status(account_id, u"[WAIT] Đợi thêm {}s...".format(remaining_sec))
                time.sleep(1)
        
        return elapsed
    else:
        for remaining_sec in range(delay_seconds, 0, -1):
            if check_stop_safe():
                break
            if remaining_sec % 5 == 0 or remaining_sec <= 3:
                update_account_status(account_id, u"[WAIT] Đợi {}s...".format(remaining_sec))
            time.sleep(1)
        return delay_seconds

# ==================== HÀM HỖ TRỢ TIKTOK ====================
def restart_tiktok(d):
    try:
        d.app_stop(TIKTOK_PACKAGE)
        time.sleep(1)
        d.app_start(TIKTOK_PACKAGE)
        time.sleep(2.5)
    except Exception as e:
        add_response_message(u"restart_tiktok error: {}".format(str(e)))

def check_app_status(d):
    try:
        current = d.app_current()
        if current.get("package") != TIKTOK_PACKAGE:
            d.app_start(TIKTOK_PACKAGE)
            time.sleep(2.5)
            return False
        return True
    except Exception as e:
        add_response_message(u"check_app_status error: {}".format(str(e)))
        restart_tiktok(d)
        return False

# ==================== HÀM THÊM MESSAGE VÀO DASHBOARD ====================
response_messages = []
response_lock = threading.Lock()
temp_messages = []

def add_response_message(msg, job_type=None):
    global account_id, logger, response_messages
    
    timestamp = get_vn_time().strftime('%H:%M:%S')
    full_msg = u"[{}] {}".format(timestamp, msg)
    
    if logger:
        logger.info(msg)
    
    with response_lock:
        response_messages.append(full_msg)
        while len(response_messages) > _MAX_RESPONSE_MESSAGES:
            response_messages.pop(0)
    
    if account_id:
        with dashboard_lock:
            if account_id in accounts_data:
                current_status = accounts_data[account_id].get("status", "")
                new_status = msg[:80] if len(msg) > 80 else msg
                accounts_data[account_id]["status"] = new_status
                accounts_data[account_id]["last_message"] = msg
                accounts_data[account_id]["message_time"] = timestamp
                if job_type:
                    accounts_data[account_id]["job_type"] = job_type
    else:
        with response_lock:
            temp_messages.append(full_msg)
            while len(temp_messages) > _MAX_TEMP_MESSAGES:
                temp_messages.pop(0)

def get_all_response_messages():
    with response_lock:
        return response_messages.copy()

# ==================== HÀM LẤY MESSAGE CHUẨN TỪ RESPONSE ====================
def extract_message_from_response(response_json):
    if not isinstance(response_json, dict):
        return str(response_json) if response_json else ""
    
    message_keys = ['message', 'msg', 'error', 'error_message', 'error_msg', 'description', 'detail']
    
    for key in message_keys:
        if key in response_json:
            val = response_json[key]
            if val and isinstance(val, str):
                return val
            elif val and isinstance(val, (int, float)):
                return str(val)
            elif val and isinstance(val, dict):
                sub_msg = extract_message_from_response(val)
                if sub_msg:
                    return sub_msg
    
    return json.dumps(response_json, ensure_ascii=False) if response_json else ""

def parse_api_response(response, func_name="api_call"):
    result = {
        'success': False,
        'status_code': None,
        'message': '',
        'data': None,
        'raw_response': None,
        'is_limit': False,
        'is_checkpoint': False
    }
    
    try:
        result['status_code'] = response.status_code
        result['raw_response'] = response.text
        
        try:
            resp_json = response.json()
            result['data'] = resp_json
            result['message'] = extract_message_from_response(resp_json)
            
            if not result['message']:
                result['message'] = u"HTTP {}".format(response.status_code)
            
            json_status = resp_json.get('status')
            if json_status == 200:
                result['success'] = True
            
            msg_lower = result['message'].lower()
            if any(kw in msg_lower for kw in ['limit', 'giới hạn', 'quá nhiều', 'too many', 'rate limit']):
                result['is_limit'] = True
            if any(kw in msg_lower for kw in ['checkpoint', 'verify', 'xác minh', 'captcha']):
                result['is_checkpoint'] = True
                
        except json.JSONDecodeError:
            result['message'] = response.text if response.text else u"HTTP {}".format(response.status_code)
            
    except Exception as e:
        result['message'] = u"Exception: {}".format(str(e))
    
    limit_flag = u" [LIMIT]" if result['is_limit'] else ""
    cp_flag = u" [CHECKPOINT]" if result['is_checkpoint'] else ""
    full_message = u"{}{}{}".format(result['message'], limit_flag, cp_flag)
    
    add_response_message(u"[{}] {}".format(func_name, full_message))
    
    return result

# ==================== HÀM LẤY USERNAME MỚI CHÍNH XÁC ====================
def click_username_by_dump(d):
    try:
        if not check_app_status(d):
            return None

        w, h = d.window_size()
        d.click(int(w * 0.9), int(h * 0.95))
        time.sleep(1.0)

        xml = d.dump_hierarchy()

        match = re.search(
            r'text="(@[^"]+)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            xml
        )

        if match:
            username_clean = match.group(1).replace("@", "").strip().lower()
            
            left, top, right, bottom = map(int, match.groups()[1:])
            x = (left + right) // 2
            y = (top + bottom) // 2

            add_response_message(u"Click username: {}".format(username_clean))
            d.click(x, y)
            
            return username_clean
        else:
            add_response_message(u"Chưa tìm thấy username trong UI")

    except Exception as e:
        add_response_message(u"Lỗi click_username_by_dump: {}".format(str(e)))

    return None

def get_tiktok_username_v2(d, max_retry=3):
    check_stop()
    add_response_message(u"[INFO] Đang tự động lấy Username TikTok...")
    
    for attempt in range(max_retry):
        check_stop()
        
        if not check_app_status(d):
            add_response_message(u"[WARN] TikTok không hoạt động, đang khởi động lại...")
            restart_tiktok(d)
            time.sleep(1.5)
            continue
        
        username = click_username_by_dump(d)
        
        if username and len(username) > 1:
            add_response_message(u"[OK] Đã lấy được Username: {}".format(username))
            return username
        
        if attempt < max_retry - 1:
            add_response_message(u"[RETRY] Chưa tìm thấy, thử lại sau 1 giây...")
            time.sleep(1)
    
    add_response_message(u"[ERROR] Không thể lấy Username sau nhiều lần thử")
    return None

# ======================================================================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

device = None
device_serial = None
TIKTOK_PACKAGE = "com.ss.android.ugc.trill"
INSTANCE_ID = None
account_id = None
base_delay = 5
delay_variation = 2

AUTH_FILE = os.path.join(DATA_DIR, "Authorization.json")
LINK_JOB_FILE = None
LOG_FILE = None
CHECK_CMT_FILE = None
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

SIMILARITY_THRESHOLD = 0.85
MIN_FOLLOW_PRICE = 0
FORCE_STOP_ENABLED = False
FORCE_STOP_AFTER = 0
job_count = 0

delay_config = {
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

logger = None
console = Console()
accounts_data = {}
dashboard_lock = threading.Lock()
auth_accounts = []

JOBS = [
    {"id": "like", "name": "Like", "color": "#ff9ecb"},
    {"id": "follow", "name": "Follow", "color": "#ffd54f"},
    {"id": "comment", "name": "Comment", "color": "#00ffff"},
    {"id": "favorite", "name": "Favorite", "color": "#a78bfa"}
]

def get_job_color(job_type):
    if not job_type:
        return "#ffffff"
    for job in JOBS:
        if job["id"] == job_type:
            return job["color"]
    return "#ffffff"

def get_job_name(job_type):
    for job in JOBS:
        if job["id"] == job_type:
            return job["name"]
    return job_type.capitalize() if job_type else ""

# ==================== CÁC HÀM XỬ LÝ LIKE ====================
def is_like_node(node):
    res_id = node.get("resource-id", "")
    desc = node.get("content-desc", "").lower()
    
    if "like" in desc or "thích" in desc:
        return True
    
    if any(k in res_id for k in ["like", "digg", "heart"]):
        return True
    
    return False

def is_liked(node):
    desc = node.get("content-desc", "").lower()
    return (
        node.get("selected") == "true"
        or "unlike" in desc
        or "bỏ thích" in desc
    )

def find_like_btn(nodes):
    candidates = []
    
    for node in nodes:
        if is_like_node(node):
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

def dump_ui_nodes(device_obj):
    global _ui_dump_cache, _UI_DUMP_LAST_CALL, _UI_DUMP_CALL_COUNT
    
    now = time.time()
    
    _UI_DUMP_CALL_COUNT += 1
    if _UI_DUMP_CALL_COUNT > 10:
        _UI_DUMP_LAST_CALL = now
        _UI_DUMP_CALL_COUNT = 0
    
    if (_ui_dump_cache["nodes"] and 
        (now - _ui_dump_cache["timestamp"]) < _UI_DUMP_CACHE_TTL):
        return _ui_dump_cache["nodes"]
    
    try:
        xml_content = device_obj.dump_hierarchy()
        
        nodes = []
        pattern = re.compile(r'<node\s+([^>]+)>')
        attr_pattern = re.compile(r'([\w\-]+)="([^"]*)"')
        
        for match in pattern.finditer(xml_content):
            attrs = dict(attr_pattern.findall(match.group(1)))
            nodes.append(attrs)
        
        _ui_dump_cache["xml"] = xml_content
        _ui_dump_cache["timestamp"] = now
        _ui_dump_cache["nodes"] = nodes
        
        return nodes
    except Exception as e:
        add_response_message(u"Lỗi dump UI nodes: {}".format(str(e)))
        return []

def click_node_by_bounds(device_obj, node):
    bounds = node.get("bounds")
    if not bounds:
        return False
    
    pts = list(map(int, re.findall(r'\d+', bounds)))
    if len(pts) >= 4:
        x = (pts[0] + pts[2]) // 2
        y = (pts[1] + pts[3]) // 2
        
        add_response_message(u"Click tại {},{}".format(x, y))
        device_obj.click(x, y)
        return True
    
    return False

def do_like(d, max_retry=10):
    if not d:
        return False
    
    check_stop()
    add_response_message(u"[SCAN] Tìm nút Like...", "like")
    clicked = False
    
    for i in range(max_retry):
        check_stop()
        
        wait_for_ui_stable(d, wait_time=0.5)
        
        nodes = dump_ui_nodes(d)
        btn = find_like_btn(nodes)
        
        if not btn:
            add_response_message(u"[RETRY] {}/{} - chưa thấy nút".format(i+1, max_retry), "like")
            time.sleep(1.5)
            continue
        
        if is_liked(btn):
            add_response_message(u"[OK] Đã Like rồi", "like")
            return True
        
        if not clicked:
            add_response_message(u"[CLICK] Click Like (lần {})".format(i+1), "like")
            if not click_node_by_bounds(d, btn):
                add_response_message(u"[ERROR] Không thể click nút like", "like")
                continue
            clicked = True
        else:
            add_response_message(u"[VERIFY] Đã click → chờ xác nhận", "like")
        
        for check in range(3):
            check_stop()
            time.sleep(2)
            
            nodes_after = dump_ui_nodes(d)
            btn_after = find_like_btn(nodes_after)
            
            if not btn_after:
                add_response_message(u"[WARN] UI chưa cập nhật", "like")
                continue
            
            if is_liked(btn_after):
                add_response_message(u"[OK] Like thành công", "like")
                return True
            
            add_response_message(u"[VERIFY] Xác nhận {} chưa thấy".format(check+1), "like")
        
        add_response_message(u"[WARN] Click chưa thành công → thử lại", "like")
        clicked = False
        time.sleep(2)
    
    add_response_message(u"[ERROR] Like thất bại", "like")
    increment_error_counter()
    return False

# ==================== CÁC HÀM XỬ LÝ FOLLOW ====================
def do_follow(d, max_retry=3):
    if not d:
        return False

    check_stop()
    try:
        target_texts = ["theo dõi", "follow", "follow back", "follow lại"]
        target_ids = ["follow_or_edit_profile_btn", "follow_btn"]
        
        for i in range(max_retry):
            check_stop()
            add_response_message(u"[SCAN] Đang quét UI tìm nút Follow (Lần {})...".format(i+1), "follow")
            
            wait_for_ui_stable(d, wait_time=1.0)
            
            nodes = dump_ui_nodes(d)
            
            for node in nodes:
                text = node.get("text", "").strip().lower()
                res_id = node.get("resource-id", "")
                
                if any(t == text for t in target_texts) or any(idx in res_id for idx in target_ids):
                    if "đang theo dõi" in text or "following" in text:
                        add_response_message(u"[OK] Đã follow từ trước", "follow")
                        return True
                    
                    if click_node_by_bounds(d, node):
                        add_response_message(u"[CLICK] Đã click nút follow, đang xác nhận...", "follow")
                        wait_for_ui_stable(d, wait_time=3.5)
                        
                        nodes_after = dump_ui_nodes(d)
                        verified = False
                        is_reverted = False
                        success_texts = ["đang theo dõi", "following", "nhắn tin", "message"]
                        
                        for n in nodes_after:
                            t = n.get("text", "").lower()
                            desc = n.get("content-desc", "").lower()
                            
                            if any(s in t for s in success_texts) or any(s in desc for s in success_texts):
                                verified = True
                                break
                            if any(tf == t for tf in target_texts):
                                is_reverted = True
                        
                        if verified:
                            add_response_message(u"[OK] Follow thành công", "follow")
                            return True
                        elif is_reverted:
                            add_response_message(u"[WARN] Follow bị hoàn tác (Shadowban hoặc mạng lỗi)", "follow")
                            increment_error_counter()
                            return False
                        else:
                            add_response_message(u"[OK] Nút follow đã biến mất, follow thành công", "follow")
                            return True
            
            time.sleep(2)
            
        add_response_message(u"[ERROR] Không tìm thấy nút Follow", "follow")
        increment_error_counter()
        return False
            
    except Exception as e:
        add_response_message(u"[ERROR] Lỗi trong do_follow: {}".format(str(e)), "follow")
        increment_error_counter()
        return False

# ==================== CÁC HÀM XỬ LÝ FAVORITE ====================
def do_favorite(d, max_retry=6):
    if not d:
        return False

    check_stop()
    try:
        fav_identifiers = {
            "ids": ["favorite_icon", "h2m", "iv_favorite", "com.ss.android.ugc.trill:id/favorite_icon"],
            "descs": ["favorite", "yêu thích", "lưu", "favorites"]
        }

        for i in range(max_retry):
            check_stop()
            add_response_message(u"[SCAN] Đang quét UI tìm nút Lưu (Lần {})...".format(i+1), "favorite")
            
            wait_for_ui_stable(d, wait_time=1.0)
            
            nodes = dump_ui_nodes(d)
            
            for node in nodes:
                res_id = node.get("resource-id", "")
                desc = node.get("content-desc", "").lower()
                
                is_fav = any(tid in res_id for tid in fav_identifiers["ids"]) or \
                         any(td in desc for td in fav_identifiers["descs"])

                if is_fav:
                    if node.get("selected") == "true" or "đã lưu" in desc or "added" in desc:
                        add_response_message(u"[OK] Video này đã được lưu vào Favorites từ trước", "favorite")
                        return True
                    
                    bounds = node.get("bounds", "")
                    if bounds:
                        add_response_message(u"[OK] Đã tìm thấy nút Favorites! (ID: {})".format(res_id), "favorite")
                        if click_node_by_bounds(d, node):
                            add_response_message(u"[OK] Đã lưu video thành công", "favorite")
                            wait_for_ui_stable(d, wait_time=1.5)
                            return True
                            
            time.sleep(2)

        add_response_message(u"[ERROR] Không tìm thấy nút Favorites", "favorite")
        increment_error_counter()
        return False
        
    except Exception as e:
        add_response_message(u"[ERROR] Lỗi trong do_favorite: {}".format(str(e)), "favorite")
        increment_error_counter()
        return False

# ==================== CÁC HÀM XỬ LÝ COMMENT ====================
def do_comment(d, text, link):
    if not d:
        return False

    check_stop()
    global previous_job_link
    if previous_job_link == link:
        add_response_message(u"[WARN] Bỏ qua bình luận - link trùng: {}".format(link), "comment")
        return False

    filtered_text = filter_comment_content(text)
    if not filtered_text:
        return False

    last_comment = load_last_comment()
    if is_duplicate_comment(filtered_text, last_comment):
        add_response_message(u"[WARN] Bình luận trùng với bình luận cuối cùng", "comment")
        return False

    add_response_message(u"[WAIT] Đợi video load để tìm nút comment...", "comment")
    comment_opened = False
    for attempt in range(5):
        check_stop()
        wait_for_ui_stable(d, wait_time=1.0)
        
        comment_btn = d(descriptionContains="comment")
        if not comment_btn.exists:
            comment_btn = d(descriptionContains="bình luận")
            
        if comment_btn.exists:
            comment_btn.click()
            wait_for_ui_stable(d, wait_time=2)
            comment_opened = True
            break
        
        add_response_message(u"[WAIT] Chưa thấy nút comment, chờ load (lần {}/5)...".format(attempt+1), "comment")
        time.sleep(2)
        
    if not comment_opened:
        add_response_message(u"[ERROR] Không tìm thấy nút comment", "comment")
        increment_error_counter()
        return False

    add_response_message(u"[SCAN] Tìm ô nhập comment...", "comment")
    check_stop()
    wait_for_ui_stable(d, wait_time=1.0)
    
    input_box = d(className="android.widget.EditText")
    if not input_box.exists:
        add_response_message(u"[ERROR] Không thấy ô nhập comment", "comment")
        increment_error_counter()
        return False

    input_box.click()
    wait_for_ui_stable(d, wait_time=0.5)
    
    try:
        input_box.clear_text()
    except Exception as e:
        add_response_message(u"[WARN] Lỗi clear text: {}".format(str(e)), "comment")
        
    d.clipboard.set(filtered_text)
    d.press("paste")
    wait_for_ui_stable(d, wait_time=1)
    add_response_message(u"[OK] Đã nhập nội dung comment", "comment")

    add_response_message(u"[SCAN] Tìm nút gửi...", "comment")
    check_stop()
    
    use_cv2 = True
    try:
        if use_cv2:
            screenshot = d.screenshot(format="opencv")
            template_path = check_and_download_gui()
            
            if not os.path.exists(template_path):
                add_response_message(u"[WARN] Không tìm thấy file ảnh, dùng phím Enter", "comment")
                d.press("enter")
            else:
                template = cv2.imread(template_path)
                result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                add_response_message(u"[MATCH] Độ khớp ảnh nút Gửi: {:.2f}".format(max_val), "comment")
                threshold = 0.7

                if max_val >= threshold:
                    h, w = template.shape[:2]
                    x = max_loc[0] + w // 2
                    y = max_loc[1] + h // 2
                    d.click(x, y)
                    add_response_message(u"[OK] Đã click nút Gửi", "comment")
                else:
                    add_response_message(u"[WARN] Độ khớp thấp, dùng phím Enter", "comment")
                    d.press("enter")
        else:
            d.press("enter")
    except Exception as e:
        add_response_message(u"[WARN] Lỗi xử lý ảnh: {}, dùng phím Enter".format(str(e)), "comment")
        d.press("enter")

    check_stop()
    if verify_comment_success(d, filtered_text):
        save_comment(filtered_text, "sent")
        previous_job_link = link
        return True
    else:
        add_response_message(u"[ERROR] Comment thất bại", "comment")
        increment_error_counter()
        return False

def verify_comment_success(d, comment_text):
    try:
        wait_for_ui_stable(d, wait_time=2)
        
        comment_elements = d(className="android.widget.TextView")
        found = False
        
        for elem in comment_elements:
            try:
                text = elem.get_text()
                if text and comment_text and len(text) > 5 and len(comment_text) > 5:
                    similarity = SequenceMatcher(None, text.lower(), comment_text.lower()).ratio()
                    if similarity > 0.7:
                        add_response_message(u"[VERIFY] Tìm thấy comment với độ tương đồng {:.2f}".format(similarity), "comment")
                        found = True
                        break
            except Exception:
                continue
        
        if found:
            return True
            
        error_msg = d(textMatches="(?i)(lỗi|thất bại|không thể đăng|spam)")
        if error_msg.exists(timeout=2):
            add_response_message(u"[WARN] Phát hiện thông báo lỗi khi đăng comment", "comment")
            return False
            
        add_response_message(u"[WARN] Không tìm thấy comment nhưng không có lỗi, tạm chấp nhận", "comment")
        return True
    except Exception as e:
        add_response_message(u"[ERROR] Lỗi xác nhận comment: {}".format(str(e)), "comment")
        return False

def complete_and_check_response(ads_id, account_id_val, job_type, link):
    global previous_job_link
    try:
        json_data = {
            'ads_id': ads_id,
            'account_id': account_id_val,
            'async': True,
            'data': None
        }

        response = session.post(
            'https://gateway.golike.net/api/advertising/publishers/tiktok/complete-jobs',
            headers=headers, json=json_data, timeout=30)

        parsed = parse_api_response(response, "complete_jobs")
        
        if parsed['success']:
            save_link_job(link, job_type, "thành công", 0)
            increment_job_counter()
            return True, parsed['message']
        else:
            msg_lower = parsed['message'].lower()
            if job_type == "comment" and any(kw in msg_lower for kw in ["vi phạm", "spam", "trùng", "không hợp lệ", "duplicate"]):
                previous_job_link = link
            return False, parsed['message']

    except Exception as e:
        error_msg = u"Exception: {}".format(str(e))
        add_response_message(u"Exception khi hoàn thành nhiệm vụ: {}".format(error_msg))
        return False, error_msg

def get_job_price(job_data):
    try:
        for key in ['price_after_cost', 'price_per_after_cost', 'amount', 'reward', 'price', 'money', 'coin', 'value', 'point']:
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
    except Exception:
        return 0

def process_tiktok_job(job_data):
    try:
        check_stop()
        link = job_data["link"]
        action_type = job_data["type"]
        ads_id = job_data["id"]
        job_price = get_job_price(job_data)

        if action_type == "follow":
            if job_price < MIN_FOLLOW_PRICE:
                return False, u"Job Follow giá {}đ < {}đ -> Bỏ qua".format(job_price, MIN_FOLLOW_PRICE), ads_id, job_price

        if action_type not in ["like", "follow", "comment", "favorite"]:
            return False, u"Loại nhiệm vụ không hỗ trợ", None, 0

        if not open_link(link):
            return False, u"Mở link thất bại", ads_id, job_price

        success = False
        reason = ""

        wait_for_ui_stable(device, wait_time=2)

        if action_type == "like":
            success = do_like(device)
            reason = u"Like thất bại" if not success else u"Like thành công"
        elif action_type == "follow":
            success = do_follow(device)
            reason = u"Follow thất bại" if not success else u"Follow thành công"
        elif action_type == "favorite":
            success = do_favorite(device)
            reason = u"Favorite thất bại" if not success else u"Favorite thành công"
        elif action_type == "comment":
            comment_text = (
                job_data.get("text") or
                job_data.get("description") or
                job_data.get("comment") or
                job_data.get("noidung")
            )
            if not comment_text:
                return False, u"Thiếu nội dung bình luận", ads_id, job_price
            success = do_comment(device, comment_text, link)
            reason = u"Comment thất bại" if not success else u"Comment thành công"

        if not success:
            return False, reason, ads_id, job_price

        success, complete_reason = complete_and_check_response(ads_id, account_id, action_type, link)
        if success:
            save_link_job(link, action_type, "thành công", job_price)
        else:
            save_link_job(link, action_type, u"thất bại: {}".format(complete_reason), job_price)

        return success, complete_reason, ads_id, job_price
    except Exception as e:
        if "STOP_FLAG" in str(e):
            raise
        error_msg = u"Exception: {}".format(str(e))
        add_response_message(u"Exception trong process_tiktok_job: {}".format(error_msg))
        increment_error_counter()
        return False, error_msg, None, 0

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
\033[38;2;255;200;140m[</>] \033[38;2;200;160;255mADMIN: \033[38;2;255;235;180mNHƯ ANH ĐÃ THẤY EM   \033[38;2;255;220;160mPhiên Bản: \033[38;2;120;255;220mv3.12
\033[38;2;255;200;140m[</>] \033[38;2;200;160;255mNhóm Telegram: \033[38;2;120;255;220mhttps://t.me/se_meo_bao_an
\033[38;2;190;235;210m───────────────────────────────────────────────────────────────────────\033[0m
"""
    print(banner_text)

def check_and_download_gui():
    """Kiểm tra file gui.png, nếu chưa có thì tải về từ GitHub"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    gui_path = os.path.join(current_dir, "gui.png")
    
    if os.path.exists(gui_path):
        return gui_path
    
    add_response_message(u"[INFO] Chưa có file gui.png, đang tự động tải về...")
    url = "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/refs/heads/main/gui.png"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            urllib.request.urlretrieve(url, gui_path)
            if os.path.exists(gui_path) and os.path.getsize(gui_path) > 0:
                add_response_message(u"[OK] Đã tải gui.png thành công ({} bytes)".format(os.path.getsize(gui_path)))
                return gui_path
            else:
                add_response_message(u"[WARN] File tải về bị lỗi, thử lại...")
        except Exception as e:
            add_response_message(u"[WARN] Lỗi tải ảnh lần {}: {}".format(attempt + 1, str(e)))
            if attempt < max_retries - 1:
                time.sleep(2)
    
    add_response_message(u"[ERROR] Không thể tải gui.png sau {} lần thử".format(max_retries))
    return gui_path

def load_config():
    global delay_config, MIN_FOLLOW_PRICE, FORCE_STOP_ENABLED, FORCE_STOP_AFTER
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            delay_config = config.get('delay_config', delay_config)
            MIN_FOLLOW_PRICE = config.get('min_follow_price', MIN_FOLLOW_PRICE)
            FORCE_STOP_ENABLED = config.get('force_stop_enabled', FORCE_STOP_ENABLED)
            FORCE_STOP_AFTER = config.get('force_stop_after', FORCE_STOP_AFTER)
            
            console.print(u"[green]✓ Đã tải cấu hình từ file[/]")
            return True
        except Exception as e:
            console.print(u"[yellow]⚠ Không thể tải cấu hình: {}[/]".format(e))
            return False
    return False

def save_config():
    try:
        config = {
            'delay_config': delay_config,
            'min_follow_price': MIN_FOLLOW_PRICE,
            'force_stop_enabled': FORCE_STOP_ENABLED,
            'force_stop_after': FORCE_STOP_AFTER
        }
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        console.print(u"[red]Lỗi lưu cấu hình: {}[/]".format(e))
        return False

def input_number(text, default):
    while True:
        try:
            value = input(text).strip()
            if value == "":
                return default
            return int(value)
        except Exception as e:
            console.print(u"[bold #ff4d6d]Sai định dạng! Nhập số. ({})[/]".format(e))

def setup_delay_config():
    global delay_config, MIN_FOLLOW_PRICE, FORCE_STOP_ENABLED, FORCE_STOP_AFTER
    
    delay_like = [delay_config['like'][0], delay_config['like'][1]]
    delay_follow = [delay_config['follow'][0], delay_config['follow'][1]]
    delay_comment = [delay_config['comment'][0], delay_config['comment'][1]]
    delay_job = [delay_config['job'][0], delay_config['job'][1]]
    delay_fav = [delay_config['favorite'][0], delay_config['favorite'][1]]
    nuoi_nick = delay_config.get('nuoi_nick', 2)
    share_rate = delay_config.get('share_rate', 15)

    loc_follow = delay_config['loc_follow']
    delay_done = delay_config['delay_done']
    force_stop = "Yes" if FORCE_STOP_ENABLED else "No"
    stop_job = FORCE_STOP_AFTER
    
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
            console.print(u"[#00ff9c] Giữ config hiện tại[/]")
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
        force_stop = "Yes" if force_stop_input == "y" else "No"
        stop_job = input_number(u"Số job buộc dừng ({}): ".format(stop_job), stop_job)

    delay_config['like'] = delay_like
    delay_config['follow'] = delay_follow
    delay_config['comment'] = delay_comment
    delay_config['job'] = delay_job
    delay_config['favorite'] = delay_fav
    delay_config['nuoi_nick'] = nuoi_nick
    delay_config['share_rate'] = share_rate
    delay_config['loc_follow'] = loc_follow
    delay_config['delay_done'] = delay_done
    
    MIN_FOLLOW_PRICE = loc_follow
    FORCE_STOP_ENABLED = (force_stop == "Yes")
    FORCE_STOP_AFTER = stop_job
    
    save_config()
    return True

def get_random_delay_job(job_type):
    if job_type in delay_config:
        min_delay, max_delay = delay_config[job_type]
        return random.randint(min_delay, max_delay)
    return random.randint(3, 7)

def get_random_delay():
    return get_random_delay_job('job')

def render_tablet(selections, current_idx):
    table = Table(
        box=box.ROUNDED, 
        border_style="#d7b8ff", 
        header_style="bold #ffffff",
        width=45,
        title="[bold #ff9ecb]📋 CHỌN NHIỆM VỤ[/]"
    )
    
    table.add_column("STT", justify="center", style="bold", width=5)
    table.add_column(u"Nhiệm Vụ", width=15)
    table.add_column(u"Trạng Thái", justify="center", width=12)

    for i, job in enumerate(JOBS):
        color = job["color"]
        
        if selections[i] == 'y':
            status = "[bold #00ff9c]✓ Đã chọn[/]"
        elif selections[i] == 'n':
            status = "[bold #ff4d6d]✗ Bỏ qua[/]"
        elif i == current_idx:
            status = "[blink bold #ffff00]⏳ Đang chờ...[/]"
        else:
            status = "[dim]⏳ Chưa chọn[/]"

        table.add_row(
            u"[{}]{}[/]".format(color, i+1),
            u"[{}]{}[/]".format(color, job['name']),
            status
        )
    return table

def menu_jobs():
    selections = [None] * len(JOBS)
    
    console.clear()
    console.print(Panel(u"[bold cyan]🔧 CẤU HÌNH NHIỆM VỤ[/]", border_style="#ff9ecb", width=50))
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
                console.print(u"[red]✗ Vui lòng nhập y hoặc n![/]", style="red")
                time.sleep(1)

    console.clear()
    console.print(render_tablet(selections, -1))
    
    selected_jobs = [JOBS[i]["id"] for i in range(len(JOBS)) if selections[i] == 'y']
    
    if selected_jobs:
        console.print(u"\n[#ffffff] Nhiệm vụ đã chọn:[/] [bold #00ffff]{}[/]".format(u', '.join(job['name'] for job in JOBS if job['id'] in selected_jobs)))
        console.print(u"[#00ff9c]➤ Sẽ thực hiện {} nhiệm vụ[/]\n".format(len(selected_jobs)))
    else:
        console.print(u"\n[#ff4d6d]⚠ Không có nhiệm vụ nào được chọn! Tool sẽ thoát.[/]")
        sys.exit(1)
    
    return selected_jobs

def get_device_model_from_adb(device_obj):
    try:
        return device_obj.shell("getprop ro.product.model").strip()
    except Exception as e:
        add_response_message(u"get_device_model error: {}".format(str(e)))
        return "Unknown"

def get_battery_from_adb(device_obj):
    try:
        info = device_obj.shell("dumpsys battery")
        for line in info.splitlines():
            if "level" in line:
                return line.split(":")[1].strip()
    except Exception:
        pass
    return ""

def show_devices_with_rich():
    console.clear()
    banner()
    table = Table(
        title="[bold #ffffff] DANH SÁCH THIẾT BỊ ADB[/]",
        border_style="#d7d7a8",
        show_lines=True,
        expand=False,
        title_justify="center"
    )

    table.add_column("STT", justify="center", style="#e0e0e0", width=5)
    table.add_column("Device ID", style="#00ff9c", width=25)
    table.add_column("Product Model", style="#ffd54f", width=20)
    table.add_column(u"🔋 Battery", justify="center", width=12)
    table.add_column("Status", style="#00ff99", width=10)

    devices = adb.device_list()

    if not devices:
        console.print(Panel(u"[red]Không tìm thấy thiết bị ADB nào![/]", border_style="red"))
        return []

    for i, d in enumerate(devices):
        model = get_device_model_from_adb(d)
        battery = get_battery_from_adb(d)
        
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
            except Exception:
                battery_display = u"[cyan]{}%[/cyan]".format(battery)
        else:
            battery_display = "[dim]N/A[/dim]"

        table.add_row(
            str(i + 1),
            u"[#00ff9c]{}[/]".format(d.serial),
            u"[#ffd54f]{}[/]".format(model),
            battery_display,
            u"[#00ff99]● Online[/]"
        )

    console.print(table)
    console.print()
    return devices

def get_adb_devices_new():
    devices = show_devices_with_rich()
    if not devices:
        return []
    return [d.serial for d in devices]

def get_status_color(status, job_type=None):
    status_lower = status.lower()
    
    if job_type:
        return get_job_color(job_type)
    
    if u"đợi" in status_lower or u"chờ" in status_lower or u"đang chờ" in status_lower:
        return "yellow"
    elif u"hoàn thành" in status_lower or u"thành công" in status_lower:
        return "green"
    elif u"thất bại" in status_lower or u"bỏ qua" in status_lower or "skip" in status_lower:
        return "red"
    elif u"tìm nhiệm vụ" in status_lower:
        return "bright_black"
    elif u"force stop" in status_lower or u"buộc dừng" in status_lower:
        return "orange1"
    elif "limit" in status_lower:
        return "red"
    elif "checkpoint" in status_lower:
        return "orange1"
    elif "token" in status_lower or "authorization" in status_lower:
        return "red"
    else:
        return "white"

def build_table():
    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    
    table.add_column("Device ID", style="bright_yellow", width=20)
    table.add_column("ID TikTok", style="bright_yellow", width=15)
    table.add_column("Status", style="white", width=50)
    table.add_column("Type Job", style="cyan", width=10)
    table.add_column(u"Xu", style="yellow", width=8)
    table.add_column(u"TỔNG Xu", style="yellow", width=10)
    table.add_column("Done", style="green", width=8)
    table.add_column("Fail", style="red", width=8)
    
    with dashboard_lock:
        for acc_id, data in accounts_data.items():
            status = str(data.get("status", u"đang chờ..."))
            job_type = data.get("job_type", "")
            if job_type:
                status_color = get_job_color(job_type)
            else:
                status_color = get_status_color(status, job_type)
            msg_time = data.get("message_time", "")
            time_display = u"[dim]{}{}[/dim] ".format(msg_time, u" " if msg_time else u"")
            
            job_display = u"[{}]{}[/]".format(get_job_color(job_type), job_type.upper() if job_type else '-') if job_type else "-"
            
            table.add_row(
                str(device_serial if device_serial else "N/A"),
                str(data.get("username", "?")),
                u"{}{}[{}]{}[/{}]".format(time_display, u"", status_color, status, status_color),
                job_display,
                str(data.get("xu", 0)),
                u"[yellow]{}[/yellow]".format(data.get('total_xu', 0)),
                u"[green]{}[/green]".format(data.get('done', 0)),
                u"[red]{}[/red]".format(data.get('fail', 0))
            )
    return table

def make_stats():
    with dashboard_lock:
        total_xu = sum(d.get("total_xu", 0) for d in accounts_data.values())
        total_done = sum(d.get("done", 0) for d in accounts_data.values())
        total_fail = sum(d.get("fail", 0) for d in accounts_data.values())
        total_devices = len(accounts_data)
    
    stats = Table.grid(expand=False, pad_edge=True)
    stats.add_row(
        Panel(u"[yellow]TỔNG Xu : {}/yellow]".format(total_xu), width=15, style="bright_blue", box=box.ROUNDED),
        Panel(u"[cyan]Thiết bị : {}/cyan]".format(total_devices), width=15, style="bright_blue", box=box.ROUNDED),
        Panel(u"[green]Job Done : {}/green]".format(total_done), width=15, style="bright_blue", box=box.ROUNDED),
        Panel(u"[red]Job Fail : {}/red]".format(total_fail), width=15, style="bright_blue", box=box.ROUNDED),
    )
    return stats

def make_link_panel():
    with dashboard_lock:
        if accounts_data:
            first_device = list(accounts_data.values())[0]
            link = first_device.get("link", u"Chưa có job")
            job_type = first_device.get("job_type", "")
            border_color = get_job_color(job_type) if job_type else "bright_yellow"
        else:
            link = u"Chưa có job"
            border_color = "bright_yellow"
    
    link_display = link
    if len(link) > 65:
        parts = []
        for i in range(0, len(link), 65):
            parts.append(link[i:i+65])
        link_display = u"\n".join(parts)
    
    return Panel(
        Align.left(Text(link_display, style="bold cyan")),
        title=u"[bold {}]🔗 LINK JOB HIỆN TẠI[/bold {}]".format(border_color, border_color),
        border_style=border_color,
        box=box.ROUNDED,
        width=72,
        expand=False
    )

def make_layout():
    layout = Layout()
    
    layout.split(
        Layout(name="title", size=3),
        Layout(name="stats", size=5),
        Layout(name="link", size=5),
        Layout(name="table")
    )
    
    layout["title"].update(
        Align.center(
            Panel(
                u"[bold cyan]TOOL GOLIKE TIKTOK BOXPHONE - BY: PHONG Tus | VER 3.12[/bold cyan]",
                style="bright_yellow",
                box=box.DOUBLE
            )
        )
    )
    
    layout["stats"].update(Align.center(make_stats()))
    layout["link"].update(Align.center(make_link_panel()))
    layout["table"].update(build_table())
    
    return layout

def run_dashboard():
    refresh_rate = 1.0
    
    with Live(
        make_layout(),
        refresh_per_second=refresh_rate,
        screen=True,
        auto_refresh=True
    ) as live:
        while True:
            try:
                time.sleep(0.5)
                live.update(make_layout())
            except Exception:
                time.sleep(1)

def init_account_data(account_id_val, username):
    with dashboard_lock:
        if account_id_val not in accounts_data:
            accounts_data[account_id_val] = {
                "username": username,
                "status": u"đang chờ...",
                "last_message": "",
                "message_time": "",
                "job_type": "",
                "xu": 0,
                "total_xu": 0,
                "done": 0,
                "fail": 0,
                "link": ""
            }

def update_account_stats(account_id_val, job_type=None, coin=0, success=True):
    with dashboard_lock:
        if account_id_val not in accounts_data:
            return
        
        if success:
            accounts_data[account_id_val]["done"] += 1
            accounts_data[account_id_val]["total_xu"] += coin
            accounts_data[account_id_val]["xu"] = coin
            if job_type:
                accounts_data[account_id_val]["job_type"] = job_type
        else:
            accounts_data[account_id_val]["fail"] += 1
            if job_type:
                accounts_data[account_id_val]["job_type"] = job_type

def update_account_status(account_id_val, status):
    with dashboard_lock:
        if account_id_val in accounts_data:
            accounts_data[account_id_val]["status"] = status
            accounts_data[account_id_val]["last_message"] = status
            accounts_data[account_id_val]["message_time"] = get_vn_time().strftime('%H:%M:%S')

def update_current_link(account_id_val, link):
    with dashboard_lock:
        if account_id_val in accounts_data:
            accounts_data[account_id_val]["link"] = link

def get_video_id(link):
    try:
        match = re.search(r'/video/(\d+)', link)
        if match:
            return match.group(1)
        
        match = re.search(r'tiktok\.com/(?:@[^/]+/video/|video/|)(\d+)', link)
        if match:
            return match.group(1)
        
        return hashlib.md5(link.encode()).hexdigest()[:10]
    except Exception as e:
        if logger:
            logger.error(u"Lỗi extract video_id từ {}: {}".format(link, str(e)))
        return link

def save_link_job(link, job_type, status, price):
    try:
        video_id = get_video_id(link)
        
        if status != u"thành công":
            return False
        
        data = {}
        if os.path.exists(LINK_JOB_FILE):
            with open(LINK_JOB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        if "processed_videos" not in data:
            data["processed_videos"] = []
        
        if video_id not in data["processed_videos"]:
            data["processed_videos"].append(video_id)
        
        with open(LINK_JOB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        if logger:
            logger.error(u"Lỗi lưu video_id: {}".format(str(e)))
        return False

def is_link_processed(link):
    try:
        video_id = get_video_id(link)
        
        if os.path.exists(LINK_JOB_FILE):
            with open(LINK_JOB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            processed_videos = data.get("processed_videos", [])
            if video_id in processed_videos:
                return True
        
        return False
    except Exception:
        return False

def get_instance_files(serial):
    safe_serial = re.sub(r'[^\w\-_]', '_', serial)
    return {
        'link_job': os.path.join(DATA_DIR, u"device_{}_link_job.json".format(safe_serial)),
        'log': os.path.join(DATA_DIR, u"device_{}_log.txt".format(safe_serial)),
        'check_cmt': os.path.join(DATA_DIR, u"device_{}_check_cmt.json".format(safe_serial))
    }

def init_instance_files(serial):
    global INSTANCE_FILES, LINK_JOB_FILE, LOG_FILE, CHECK_CMT_FILE, logger, INSTANCE_ID
    INSTANCE_ID = serial
    INSTANCE_FILES = get_instance_files(serial)
    LINK_JOB_FILE = INSTANCE_FILES['link_job']
    LOG_FILE = INSTANCE_FILES['log']
    CHECK_CMT_FILE = INSTANCE_FILES['check_cmt']

    logger = setup_instance_logging(serial)

    files = [LINK_JOB_FILE, LOG_FILE, CHECK_CMT_FILE]
    for file in files:
        if not os.path.exists(file):
            try:
                if file == LINK_JOB_FILE:
                    with open(file, 'w', encoding='utf-8') as f:
                        json.dump({"processed_videos": []}, f)
                elif file == LOG_FILE:
                    with open(file, 'w', encoding='utf-8') as f:
                        current_time = get_vn_time().strftime('%Y-%m-%d %H:%M:%S')
                        f.write(u"# Log file - {} - Thiết bị: {}\n".format(current_time, serial))
                elif file == CHECK_CMT_FILE:
                    with open(file, 'w', encoding='utf-8') as f:
                        json.dump({"last_comment": "", "history": []}, f)
            except Exception as e:
                add_response_message(u"Lỗi tạo file {}: {}".format(file, str(e)))
                return False
    return True

def setup_instance_logging(serial):
    safe_serial = re.sub(r'[^\w\-_]', '_', serial)
    log_filename = os.path.join(DATA_DIR, u"device_{}_log.txt".format(safe_serial))

    instance_logger = logging.getLogger(u"device_{}".format(safe_serial))
    instance_logger.setLevel(logging.INFO)
    instance_logger.handlers.clear()

    file_handler = RotatingFileHandler(log_filename, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    instance_logger.addHandler(file_handler)

    return instance_logger

def init_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    if not os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'w', encoding='utf-8') as f:
                json.dump({"tokens": []}, f, ensure_ascii=False, indent=2)
            print(u"Đã tạo file {}".format(AUTH_FILE))
        except Exception as e:
            print(u"Lỗi tạo file {}: {}".format(AUTH_FILE, str(e)))
            return False
    
    load_config()
    return True

def read_authorizations():
    try:
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('tokens', [])
        return []
    except Exception as e:
        print(u"Lỗi đọc file auth: {}".format(str(e)))
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
    except Exception as e:
        print(u"Lỗi lưu auth: {}".format(str(e)))
        return False

def get_user_me(auth_token, session):
    try:
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
        
        response = session.get('https://gateway.golike.net/api/users/me', headers=headers, timeout=30)
        parsed = parse_api_response(response, "get_user_me")
        
        if parsed['success']:
            data = parsed['data'].get("data", {})
            return {
                "success": True,
                "auth": auth_token,
                "username": data.get("username", "Unknown"),
                "coin": data.get("coin", 0)
            }
        else:
            msg = parsed['message'].lower()
            if "unauthorized" in msg or "invalid" in msg or "token" in msg:
                msg = u"Token không hợp lệ hoặc đã hết hạn"
            return {
                "success": False,
                "auth": auth_token,
                "message": msg
            }
    except Exception as e:
        error_msg = u"Exception: {}".format(str(e))
        add_response_message(u"get_user_me error: {}".format(error_msg))
        return {
            "success": False,
            "auth": auth_token,
            "message": error_msg
        }

def load_all_accounts():
    global auth_accounts
    
    auth_tokens = read_authorizations()
    
    if not auth_tokens:
        return []
    
    session = requests.Session()
    results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(get_user_me, token, session): token for token in auth_tokens}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    auth_accounts = results
    return results

def display_auth_menu():
    console.clear()
    banner()
    
    accounts = load_all_accounts()
    
    if not accounts:
        console.print(u"[yellow]⚠ Chưa có Authorization nào! Vui lòng nhập token.[/]")
        new_auth = console.input(u"[cyan]✈ Nhập Authorization: [/]").strip()
        if new_auth:
            save_authorization(new_auth)
            return display_auth_menu()
        else:
            console.print(u"[red] Authorization không được để trống![/]")
            sys.exit(1)
    
    acc_lines = []
    for i, acc in enumerate(accounts):
        idx = u"{:02d}".format(i+1)
        
        if acc.get("success"):
            username = acc.get("username", "Unknown")
            coin = acc.get("coin", 0)
            line = u"[#00ffff][{}][/] [#ff99cc]{}[/] | [#99ff99]{} coin[/]".format(idx, username, coin)
        else:
            msg = acc.get('message', u'Lỗi hệ thống')
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
            console.print(u"[red]✗ Không có tài khoản hợp lệ nào![/]")
            sys.exit(1)
    elif choice == 't':
        new_auth = console.input(u"\n[white]Authorization: [/]").strip()
        if not new_auth:
            console.print(u"[red]Authorization không được để trống![/]")
            time.sleep(1.5)
            return display_auth_menu()
        
        console.print(u"[yellow]Đang kiểm tra token...[/]")
        session = requests.Session()
        result = get_user_me(new_auth, session)
        
        if result.get("success"):
            console.print(u"[green]✓ Token hợp lệ! Xin chào: {} | {} coin[/]".format(result['username'], result['coin']))
            save_authorization(new_auth)
            time.sleep(1)
            return display_auth_menu()
        else:
            console.print(u"[red]✗ Token không hợp lệ! Lỗi: {}[/]".format(result.get('message', 'Unknown error')))
            time.sleep(2)
            return display_auth_menu()
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(accounts):
            acc = accounts[idx]
            if acc.get("success"):
                return acc["auth"]
            else:
                console.print(u"[red]✗ Tài khoản này không hợp lệ![/]")
                time.sleep(1.5)
                return display_auth_menu()
        else:
            console.print(u"[red]Số không hợp lệ! (1-{})[/]".format(len(accounts)))
            time.sleep(1)
            return display_auth_menu()
    else:
        console.print(u"[red]Lựa chọn không hợp lệ![/]")
        time.sleep(1)
        return display_auth_menu()

def load_last_comment():
    try:
        if os.path.exists(CHECK_CMT_FILE):
            with open(CHECK_CMT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('last_comment', None)
        return None
    except Exception as e:
        add_response_message(u"Lỗi đọc file check_cmt: {}".format(str(e)))
        return None

def save_comment(comment, status="sent"):
    try:
        data = {}
        if os.path.exists(CHECK_CMT_FILE):
            with open(CHECK_CMT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        data['last_comment'] = comment
        data['last_status'] = status
        data['last_time'] = get_vn_time().isoformat()
        
        if 'history' not in data:
            data['history'] = []
        
        data['history'].append({
            'comment': comment,
            'status': status,
            'timestamp': get_vn_time().isoformat()
        })
        
        if len(data['history']) > 100:
            data['history'] = data['history'][-100:]
        
        with open(CHECK_CMT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        add_response_message(u"Lỗi lưu bình luận: {}".format(str(e)))
        return False

def normalize_comment(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = ' '.join(text.split())
    return text

def is_duplicate_comment(new_comment, last_comment):
    if not last_comment:
        return False

    new_norm = normalize_comment(new_comment)
    last_norm = normalize_comment(last_comment)

    if new_norm == last_norm:
        return True

    similarity = SequenceMatcher(None, new_norm, last_norm).ratio()
    if similarity >= SIMILARITY_THRESHOLD:
        return True
    return False

def filter_comment_content(text):
    if not text:
        return None
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    text = re.sub(r'(.)\1{4,}', r'\1', text)
    text = ' '.join(text.split())
    if len(text) < 5:
        return None
    if len(text) > 500:
        text = text[:500]
    return text

def run_adb_command(args, serial=None):
    global device_serial
    use_serial = serial if serial else device_serial
    if not use_serial:
        add_response_message(u"Lỗi: Không có serial thiết bị")
        return None

    cmd = ['adb', '-s', use_serial] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result
    except Exception as e:
        add_response_message(u"Lỗi chạy ADB command {}: {}".format(cmd, str(e)))
        return None

def select_device():
    global device, device_serial
    
    devices_list = get_adb_devices_new()
    
    if not devices_list:
        console.print(u"[red]Không tìm thấy thiết bị ADB nào![/]")
        return False

    if len(sys.argv) > 1:
        arg_serial = sys.argv[1]
        if arg_serial in devices_list:
            device_serial = arg_serial
            console.print(u"[green]✓ Tự động khóa thiết bị từ lệnh khởi chạy: {}[/green]".format(device_serial))
            if not init_instance_files(device_serial):
                console.print(u"[red]Không thể khởi tạo file cho instance![/]")
                return False
            return connect_device(device_serial)
        else:
            console.print(u"[yellow]⚠ Device ID '{}' truyền vào không online, chuyển về chọn thủ công...[/yellow]".format(arg_serial))

    while True:
        try:
            choice = console.input(u"[cyan]✈ Nhập STT (1-{}) HOẶC copy dán thẳng Device ID: [/]".format(len(devices_list))).strip()
            
            if choice in devices_list:
                device_serial = choice
                if not init_instance_files(device_serial):
                    console.print(u"[red]Không thể khởi tạo file cho instance![/]")
                    return False
                break
                
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(devices_list):
                    device_serial = devices_list[idx-1]
                    if not init_instance_files(device_serial):
                        console.print(u"[red]Không thể khởi tạo file cho instance![/]")
                        return False
                    break
                else:
                    console.print(u"[red]STT không hợp lệ![/]")
            else:
                console.print(u"[red]Vui lòng nhập số STT hợp lệ hoặc Device ID chính xác đang hiện trên màn hình![/]")
                
        except Exception as e:
            console.print(u"[red]Lỗi nhập liệu: {}[/]".format(e))

    return connect_device(device_serial)

def connect_device(serial):
    global device
    
    os.environ["ANDROID_SERIAL"] = str(serial)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            console.print(u"[yellow]Đang kết nối đến thiết bị {}... (lần {})[/]".format(serial, attempt+1))
            device = u2.connect(serial)
            device.info
            console.print(u"[green]✓ Kết nối thành công![/]")
            add_response_message(u"Kết nối thành công tới thiết bị {}".format(serial))
            
            check_tiktok_installed()
            return True
        except Exception as e:
            console.print(u"[red]Kết nối thất bại: {}[/]".format(str(e)))
            add_response_message(u"Kết nối thất bại tới {}: {}".format(serial, str(e)))
            time.sleep(2)
    return False

def check_tiktok_installed():
    global device
    try:
        packages = device.app_list()
        if TIKTOK_PACKAGE not in packages:
            console.print(u"[yellow] Cảnh báo: TikTok chưa được cài đặt![/]")
            add_response_message(u"Cảnh báo: TikTok chưa được cài đặt trên thiết bị")
            return False
        return True
    except Exception as e:
        add_response_message(u"Lỗi kiểm tra TikTok: {}".format(str(e)))
        return False

def force_stop_tiktok():
    global device, device_serial
    
    check_stop()
    msg = u"[{}] Chuẩn bị buộc dừng TikTok...".format(device_serial)
    add_response_message(msg)
    
    pkg = TIKTOK_PACKAGE
    device.shell(u"am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:{}".format(pkg))
    
    if device(textMatches="(?i)(Buộc dừng|Buộc đóng|Force stop)").wait(timeout=10):
        for attempt in range(3):
            check_stop()
            btn_stop = device(resourceIdMatches=".*(?i)(force_stop|stop_button).*")
            if not btn_stop.exists:
                btn_stop = device(textMatches="(?i)(Buộc dừng|Buộc đóng|Force stop)")
            
            if btn_stop.exists:
                if btn_stop.info.get('enabled', False):
                    add_response_message(u"[{}] Đang bấm Buộc dừng (Lần {})...".format(device_serial, attempt+1))
                    btn_stop.click()
                    
                    btn_ok = device(resourceId="android:id/button1")
                    if not btn_ok.exists:
                        btn_ok = device(textMatches="(?i)(ok|đồng ý|xác nhận)")
                        
                    if btn_ok.wait(timeout=3):
                        btn_ok.click()
                        add_response_message(u"[{}] Đã Force Stop TikTok thành công!".format(device_serial))
                        return
                    else:
                        add_response_message(u"[{}] Chưa thấy nút OK, thử lại...".format(device_serial))
                else:
                    add_response_message(u"[{}] App đã dừng từ trước".format(device_serial))
                    return
            time.sleep(0.5)
        
        add_response_message(u"[{}] ⚠ Đã thử 3 lần nhưng không thể Force Stop hoàn toàn.".format(device_serial))
    else:
        add_response_message(u"[{}] ⚠ Không tìm thấy nút Buộc dừng trong cài đặt.".format(device_serial))

def start_tiktok_and_wait():
    global device, device_serial
    
    check_stop()
    msg = u"[{}] Đang mở TikTok...".format(device_serial)
    add_response_message(msg)
    
    device.app_start(TIKTOK_PACKAGE)
    
    if device(resourceIdMatches=".*tab_layout.*").wait(timeout=5):
        add_response_message(u"[{}] TikTok đã sẵn sàng".format(device_serial))
        return True
    else:
        add_response_message(u"[{}] Không thể đợi TikTok load".format(device_serial))
        return False

def open_link(link):
    global device
    try:
        if not check_and_reconnect_adb():
            return False
            
        cmd = u'am start -a android.intent.action.VIEW -d "{}" {}'.format(link, TIKTOK_PACKAGE)
        device.shell(cmd)
        launched = device.app_wait(TIKTOK_PACKAGE, timeout=7)
        if launched:
            wait_for_ui_stable(device, wait_time=1.5)
            add_response_message(u"[OK] Đã mở link: {}".format(link))
        else:
            add_response_message(u"[ERROR] Không thể mở link: {}".format(link))
        return launched
    except Exception as e:
        add_response_message(u"[ERROR] Lỗi mở link {}: {}".format(link, str(e)))
        if check_and_reconnect_adb():
            try:
                cmd = u'am start -a android.intent.action.VIEW -d "{}" {}'.format(link, TIKTOK_PACKAGE)
                device.shell(cmd)
                launched = device.app_wait(TIKTOK_PACKAGE, timeout=7)
                return launched
            except:
                pass
        return False

def delay_countdown(account_id_val, delay_seconds, msg_prefix=u"Đang chờ"):
    delay_seconds = min(delay_seconds, 300)
    for i in range(int(delay_seconds), 0, -1):
        check_stop()
        update_account_status(account_id_val, u"[WAIT] {} {}s...".format(msg_prefix, i))
        time.sleep(1)

previous_job_link = None

def find_first_selector(d, candidates, timeout_per=1):
    for sel in candidates:
        try:
            obj = d(**sel)
            if obj.wait(timeout=timeout_per):
                return obj, sel
        except Exception:
            continue
    return None, None

session = requests.Session()
headers = {}

# ==================== MAIN CODE V3.12 ====================
if __name__ == "__main__":
    clear_stop_flag()
    
    def signal_handler(sig, frame):
        print(u"\n[yellow] Nhận tín hiệu dừng, đang thoát an toàn...[/]")
        set_stop_flag()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if not init_files():
        console.print(u"[red] Không thể khởi tạo files chung! Thoát tool.[/]")
        sys.exit(1)

    banner()
    console.print(u"[cyan]═══════════════════════════════════════════════════════════════════[/]")
    
    author = display_auth_menu()

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
        'Authorization': author,
        'Content-Type': 'application/json;charset=utf-8'
    }

    console.print(u"[green]✓ ĐĂNG NHẬP THÀNH CÔNG![/]")
    time.sleep(1)

    def chonacc():
        try:
            response = session.get('https://gateway.golike.net/api/tiktok-account', headers=headers, timeout=30)
            parsed = parse_api_response(response, "chonacc")
            
            if not parsed['success']:
                if logger:
                    logger.error(u"Lấy danh sách tài khoản thất bại: {}".format(parsed['message']))
                return {"status": parsed['status_code'], "message": parsed['message'], "data": []}
            
            data = parsed['data'].get("data", []) if parsed['data'] else []
            return {"status": 200, "message": parsed['message'], "data": data}
        except Exception as e:
            error_msg = u"Exception: {}".format(str(e))
            if logger:
                logger.error(u"Lỗi chonacc: {}".format(error_msg))
            return {"status": 500, "message": error_msg, "data": []}

    def nhannv(account_id_val):
        try:
            params = {'account_id': account_id_val, 'data': 'null'}
            response = session.get('https://gateway.golike.net/api/advertising/publishers/tiktok/jobs',
                                   headers=headers, params=params, timeout=30)
            parsed = parse_api_response(response, "nhannv")
            
            if not parsed['success']:
                if logger:
                    logger.warning(u"Nhận nhiệm vụ thất bại: {}".format(parsed['message']))
                return {"status": parsed['status_code'], "message": parsed['message']}
            
            return {"status": 200, "message": parsed['message'], "data": parsed['data'].get("data") if parsed['data'] else None}
        except Exception as e:
            error_msg = u"Exception: {}".format(str(e))
            if logger:
                logger.error(u"Lỗi nhannv: {}".format(error_msg))
            return {"status": 500, "message": error_msg}

    def baoloi(ads_id, object_id, account_id_val, loai):
        try:
            json_data = {'ads_id': ads_id, 'object_id': object_id, 'account_id': account_id_val, 'type': loai}
            response = session.post('https://gateway.golike.net/api/advertising/publishers/tiktok/skip-jobs',
                                    headers=headers, json=json_data, timeout=30)
            parsed = parse_api_response(response, "baoloi")
            
            if not parsed['success']:
                if logger:
                    logger.warning(u"Báo lỗi thất bại: {}".format(parsed['message']))
                return {"status": parsed['status_code'], "message": parsed['message']}
            
            return {"status": 200, "message": parsed['message']}
        except Exception as e:
            error_msg = u"Exception: {}".format(str(e))
            if logger:
                logger.error(u"Lỗi baoloi: {}".format(error_msg))
            return {"status": 500, "message": error_msg}

    chontiktktok = chonacc()

    if chontiktktok.get("status") != 200:
        msg = chontiktktok.get("message", "")
        console.print(u"[red]Lỗi lấy danh sách tài khoản TikTok từ Golike: {}[/]".format(msg))
        if logger:
            logger.error(u"Authorization sai hoặc lỗi API: {}".format(msg))
        sys.exit(1)

    console.print(u"[cyan]═══════════════════════════════════════════════════════════════════[/]")
    console.print(u"[yellow] CẤU HÌNH DELAY VÀ THÔNG SỐ[/]")
    setup_delay_config()

    console.print(u"[cyan]═══════════════════════════════════════════════════════════════════[/]")
    lam = menu_jobs()

    console.print(u"[cyan]═══════════════════════════════════════════════════════════════════[/]")
    console.print(u"[yellow]Tiến hành kết nối thiết bị ADB...[/]")

    if not select_device():
        console.print(u"[red] Không thể kết nối thiết bị. Thoát tool![/]")
        if logger:
            logger.error(u"Không thể kết nối thiết bị, thoát tool")
        sys.exit(1)

    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()
    time.sleep(1)

    temp_account_id = "temp_loading"
    init_account_data(temp_account_id, u"Đang tải...")
    update_account_status(temp_account_id, u"Đang lấy username...")
    update_current_link(temp_account_id, u"Chưa có job")

    if FORCE_STOP_ENABLED:
        update_account_status(temp_account_id, u"Đang Force Stop TikTok...")
        console.print(u"[yellow] Đang thực hiện Force Stop TikTok theo cấu hình...[/]")
        force_stop_tiktok()
        time.sleep(1.5)
        update_account_status(temp_account_id, u"Force Stop xong, đang mở lại TikTok...")
        console.print(u"[green]✓ Force Stop hoàn tất, đang mở lại TikTok...[/]")
    
    device.app_start(TIKTOK_PACKAGE)
    update_account_status(temp_account_id, u"Đang mở TikTok...")
    console.print(u"[dim]Đợi TikTok load (3 giây)...[/dim]")
    time.sleep(3)
    
    update_account_status(temp_account_id, u"Đang lấy username...")
    console.print(u"[yellow] Đang lấy username TikTok...[/yellow]")
    
    auto_username = get_tiktok_username_v2(device, max_retry=3)
    
    is_matched = False
    if auto_username:
        console.print(u"[green]✓ Đã lấy được username: {}[/green]".format(auto_username))
        update_account_status(temp_account_id, u"Đã lấy username: {}".format(auto_username))
        
        for acc in chontiktktok["data"]:
            golike_username = acc["unique_username"].strip().lower()
            if golike_username == auto_username:
                is_matched = True
                account_id = acc["id"]
                username = acc["unique_username"]
                
                with dashboard_lock:
                    if temp_account_id in accounts_data:
                        del accounts_data[temp_account_id]
                
                init_account_data(account_id, username)
                update_account_status(account_id, u"Đã kết nối thành công!")
                update_current_link(account_id, u"Chưa có job")
                console.print(u"[green]✓ Đã map thành công với tài khoản Golike: {}[/green]".format(username))
                if logger:
                    logger.info(u"Auto-mapped account ID: {} - Username: {}".format(account_id, username))
                break
                
    if not is_matched:
        error_msg = u"Username lấy được ({}) không có trong danh sách Golike!".format(auto_username if auto_username else "None")
        console.print(u"[red] {}[/red]".format(error_msg))
        console.print(u"[yellow]Vui lòng thêm tài khoản TikTok này vào Golike hoặc kiểm tra lại.[/yellow]")
        update_account_status(temp_account_id, error_msg)
        time.sleep(5)
        sys.exit(1)

    # ==================== MAIN LOOP VỚI TRY/CATCH TOÀN CỤC ====================
    _consecutive_errors = 0
    _max_consecutive_errors = 10
    
    while True:
        try:
            gc_if_needed()
            
            if not check_and_reconnect_adb():
                add_response_message(u"[ERROR] Mất kết nối ADB, chờ 5s để thử lại...")
                time.sleep(5)
                continue
            
            _consecutive_errors = 0
            
            if not FORCE_STOP_ENABLED:
                if FORCE_STOP_ENABLED:
                    force_stop_tiktok()
            
            start_tiktok_and_wait()
            
            num_videos_khoi_dong = delay_config.get('nuoi_nick', 2)
            share_rate = delay_config.get('share_rate', 15)
            if num_videos_khoi_dong > 0:
                update_account_status(account_id, u"[INFO] Đang nuôi nick khởi động ({} video, tỷ lệ copy link {}%)...".format(num_videos_khoi_dong, share_rate))
                nuoi_nick_short(device, num_videos=num_videos_khoi_dong, share_rate=share_rate)
                update_account_status(account_id, u"[OK] Nuôi nick xong, bắt đầu tìm job...")
            
            while True:
                check_stop()
                update_account_status(account_id, u"[SCAN] Đang tìm nhiệm vụ...")
                
                delay_time = get_random_delay_job('job')
                delay_countdown(account_id, delay_time, u"Đang tìm nhiệm vụ tiếp theo trong")

                nhanjob = {}
                while True:
                    try:
                        check_stop()
                        nhanjob = nhannv(account_id)
                        break
                    except Exception as e:
                        if "STOP_FLAG" in str(e):
                            raise
                        add_response_message(u"Lỗi khi gọi nhannv: {}".format(str(e)))
                        time.sleep(1)

                if nhanjob.get("status") == 200:
                    data = nhanjob.get("data")
                    
                    if not data or not data.get("link"):
                        msg = nhanjob.get("message", u" Không có nhiệm vụ")
                        update_account_status(account_id, msg)
                        
                        num_videos_het_job = max(2, delay_config.get('nuoi_nick', 2) * 2)
                        share_rate_het_job = random.randint(30, 50)
                        update_account_status(account_id, u"[HIGH TRUST] Hết job - Nuôi nick tăng trust ({} video, copy link {}%)...".format(num_videos_het_job, share_rate_het_job))
                        nuoi_nick_short(device, num_videos=num_videos_het_job, share_rate=share_rate_het_job, is_high_trust_mode=True)
                        
                        time.sleep(2)
                        continue

                    current_link = data.get("link")
                    update_current_link(account_id, current_link)

                    if is_link_processed(current_link):
                        try:
                            result = baoloi(data["id"], data["object_id"], account_id, data["type"])
                            if result.get("status") != 200:
                                msg = result.get("message", "")
                                update_account_status(account_id, msg)
                            else:
                                update_account_status(account_id, u"[SKIP] Bỏ qua job đã làm: {}".format(result.get('message', 'OK')))
                        except Exception as e:
                            add_response_message(u"Lỗi khi báo lỗi: {}".format(str(e)))
                        continue

                    if data["type"] not in lam:
                        try:
                            result = baoloi(data["id"], data["object_id"], account_id, data["type"])
                            if result.get("status") != 200:
                                msg = result.get("message", "")
                                update_account_status(account_id, msg)
                            else:
                                update_account_status(account_id, u"[SKIP] Bỏ qua job loại {}".format(data['type']))
                            time.sleep(1)
                            continue
                        except Exception as e:
                            add_response_message(u"Lỗi khi báo lỗi: {}".format(str(e)))
                            continue

                    status_map = {
                        "follow": u"[FOLLOW] Đang follow...",
                        "like": u"[LIKE] Đang like...",
                        "comment": u"[COMMENT] Đang comment...",
                        "favorite": u"[FAVORITE] Đang favorite..."
                    }
                    update_account_status(account_id, status_map.get(data["type"], u"[JOB] Đang xử lý {}...".format(data["type"])))

                    success, reason, job_ads_id, job_price = process_tiktok_job(data)

                    if success:
                        job_count += 1
                        update_account_stats(account_id, data["type"], job_price, success=True)
                        
                        delay_time = delay_config['delay_done']
                        share_rate_normal = delay_config.get('share_rate', 15)
                        
                        if delay_time > 0:
                            update_account_status(account_id, u"[OK] Hoàn thành job +{}đ - Nuôi nick {}s...".format(job_price, delay_time))
                            nuoi_nick_thong_minh(device, delay_time, share_rate_normal)
                        
                        update_account_status(account_id, u"[OK] Hoàn thành - +{}đ".format(job_price))

                        if FORCE_STOP_AFTER > 0 and job_count >= FORCE_STOP_AFTER:
                            add_response_message(u"[{}] Đã hoàn thành {} job -> Force Stop".format(device_serial, job_count))
                            update_account_status(account_id, u"[STOP] Đã làm {} job -> Force Stop...".format(job_count))
                            force_stop_tiktok()
                            job_count = 0
                            start_tiktok_and_wait()
                    else:
                        update_account_stats(account_id, data["type"], 0, success=False)
                        
                        num_videos_loi = max(1, delay_config.get('nuoi_nick', 2) // 2)
                        share_rate_loi = delay_config.get('share_rate', 15)
                        if num_videos_loi > 0:
                            update_account_status(account_id, u"[ERROR] Job lỗi - Nuôi nhẹ ({} video)...".format(num_videos_loi))
                            nuoi_nick_short(device, num_videos=num_videos_loi, share_rate=share_rate_loi)
                        
                        update_account_status(account_id, u"[FAIL] {}".format(reason))

                        try:
                            result = baoloi(data["id"], data["object_id"], account_id, data["type"])
                            if result.get("status") != 200:
                                msg = result.get("message", "")
                                add_response_message(u"Báo lỗi thất bại: {}".format(msg))
                        except Exception as e:
                            add_response_message(u"Lỗi khi báo lỗi: {}".format(str(e)))
                        time.sleep(1)
                else:
                    error_msg = nhanjob.get("message", "")
                    
                    num_videos = delay_config.get('nuoi_nick', 2) * 2
                    share_rate_cao = random.randint(30, 50)
                    update_account_status(account_id, u"[ERROR] Lỗi API - Nuôi gắt ({} video, copy link {}%)...".format(num_videos, share_rate_cao))
                    nuoi_nick_short(device, num_videos=num_videos, share_rate=share_rate_cao, is_high_trust_mode=True)
                    
                    delay_countdown(account_id, 5, u"{} - Thử lại sau".format(error_msg))
                    
        except KeyboardInterrupt:
            console.print(u"\n[yellow] Đã dừng tool bởi người dùng![/]")
            if logger:
                logger.info(u"Tool đã dừng bởi người dùng")
            break
        except Exception as e:
            _consecutive_errors += 1
            error_msg = u"Lỗi toàn cục: {}".format(str(e))
            console.print(u"\n[red] {}[/red]".format(error_msg))
            add_response_message(u"[ERROR] {}".format(error_msg))
            if logger:
                logger.error(error_msg)
            
            if _consecutive_errors >= _max_consecutive_errors:
                console.print(u"\n[red] Quá nhiều lỗi liên tiếp ({}), thoát tool![/]".format(_consecutive_errors))
                if logger:
                    logger.error(u"Quá nhiều lỗi liên tiếp, thoát tool")
                break
            
            wait_time = min(30, 5 * _consecutive_errors)
            console.print(u"[yellow] Chờ {}s trước khi thử lại...[/]".format(wait_time))
            time.sleep(wait_time)
