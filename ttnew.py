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
        job("[STOP_FLAG] Đã set cờ dừng khẩn cấp")

def clear_stop_flag():
    global STOP_FLAG
    with STOP_LOCK:
        STOP_FLAG = False

def check_stop():
    with STOP_LOCK:
        if STOP_FLAG:
            raise Exception("STOP_FLAG triggered - Dừng khẩn cấp")

def wait_for_ui_stable(d, wait_time=2.5, extra_wait=0.5):
    check_stop()
    job(f"Đợi UI ổn định trong {wait_time}s...")
    time.sleep(wait_time)
    if extra_wait > 0:
        time.sleep(extra_wait)
    check_stop()
    return True

def wait_for_element(d, selector, timeout=10, check_interval=0.5):
    start = time.time()
    while time.time() - start < timeout:
        check_stop()
        try:
            elem = d(**selector) if isinstance(selector, dict) else selector
            if elem.exists(timeout=0.5):
                return elem
        except Exception as e:
            job(f"wait_for_element exception: {str(e)}")
        time.sleep(check_interval)
    return None

# ==================== HÀM HỖ TRỢ TIKTOK ====================
def restart_tiktok(d):
    try:
        d.app_stop(TIKTOK_PACKAGE)
        time.sleep(1)
        d.app_start(TIKTOK_PACKAGE)
        time.sleep(3)
    except Exception as e:
        job(f"restart_tiktok error: {str(e)}")

def check_app_status(d):
    try:
        current = d.app_current()
        if current.get("package") != TIKTOK_PACKAGE:
            d.app_start(TIKTOK_PACKAGE)
            time.sleep(3)
            return False
        return True
    except Exception as e:
        job(f"check_app_status error: {str(e)}")
        restart_tiktok(d)
        return False

# ==================== HÀM LẤY USERNAME MỚI CHÍNH XÁC ====================
def click_username_by_dump(d):
    """Click vào username và lấy tên username chính xác từ TikTok"""
    try:
        if not check_app_status(d):
            return None

        # Vào profile (nút ở góc phải dưới)
        w, h = d.window_size()
        d.click(int(w * 0.9), int(h * 0.95))
        time.sleep(1.5)

        # Dump UI để tìm username
        xml = d.dump_hierarchy()

        # Tìm username trong XML
        match = re.search(
            r'text="(@[^"]+)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            xml
        )

        if match:
            username_clean = match.group(1).replace("@", "").strip().lower()
            
            # Lấy tọa độ để click
            left, top, right, bottom = map(int, match.groups()[1:])
            x = (left + right) // 2
            y = (top + bottom) // 2

            job(f"Click username: {username_clean}")
            d.click(x, y)
            time.sleep(1)
            
            return username_clean

        else:
            job("Chưa tìm thấy username trong UI")

    except Exception as e:
        job(f"Lỗi click_username_by_dump: {str(e)}")

    return None

def get_tiktok_username_v2(d, max_retry=5):
    """
    Lấy username TikTok từ thiết bị bằng cách click vào username thật
    Đây là phiên bản mới thay thế hoàn toàn code cũ
    """
    check_stop()
    job("Đang tự động lấy Username TikTok (phiên bản mới)...")
    
    for attempt in range(max_retry):
        check_stop()
        job(f"Lần thử {attempt+1}/{max_retry}")
        
        # Đảm bảo TikTok đang mở
        if not check_app_status(d):
            job("TikTok không hoạt động, đang khởi động lại...")
            restart_tiktok(d)
            time.sleep(2)
            continue
        
        # Thử lấy username bằng cách click vào profile
        username = click_username_by_dump(d)
        
        if username and len(username) > 1:
            job(f"✅ Đã lấy được Username: {username}")
            return username
        
        job(f"Chưa tìm thấy, thử lại sau 2 giây...")
        time.sleep(2)
    
    job("❌ Không thể lấy Username sau nhiều lần thử")
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
    'loc_follow': 0
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

# ==================== HÀM LẤY MESSAGE CHUẨN TỪ RESPONSE ====================
def extract_message_from_response(response_json):
    """
    Lấy message chuẩn từ response JSON
    Ưu tiên: message -> msg -> error -> error_message -> description
    """
    if not isinstance(response_json, dict):
        return str(response_json) if response_json else ""
    
    # Các key có thể chứa message
    message_keys = ['message', 'msg', 'error', 'error_message', 'error_msg', 'description', 'detail']
    
    for key in message_keys:
        if key in response_json:
            val = response_json[key]
            if val and isinstance(val, str):
                return val
            elif val and isinstance(val, (int, float)):
                return str(val)
    
    # Nếu không có key message, trả về toàn bộ response dạng string
    return json.dumps(response_json, ensure_ascii=False) if response_json else ""

def get_full_error_message(response, func_name="unknown"):
    """
    Lấy toàn bộ thông tin lỗi từ response, không cắt bớt
    """
    try:
        status_code = response.status_code if hasattr(response, 'status_code') else "N/A"
        
        try:
            resp_json = response.json()
            message = extract_message_from_response(resp_json)
        except:
            message = response.text if hasattr(response, 'text') else str(response)
        
        # Log đầy đủ message
        job(f"[{func_name}] HTTP {status_code} - Message: {message}")
        
        return {
            'status_code': status_code,
            'message': message,
            'full_response': response.text if hasattr(response, 'text') else str(response)
        }
    except Exception as e:
        job(f"[{func_name}] Lỗi khi parse response: {str(e)}")
        return {
            'status_code': "N/A",
            'message': f"Parse error: {str(e)}",
            'full_response': str(response) if response else "No response"
        }

# ==================== HÀM XỬ LÝ RESPONSE VỚI STATUS CODE ĐẦY ĐỦ ====================
def parse_api_response(response, func_name="api_call"):
    """
    Parse API response, trả về dict với đầy đủ status, message, data
    Không cắt, không nuốt lỗi
    """
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
            
            # Lấy message chuẩn
            result['message'] = extract_message_from_response(resp_json)
            
            # Kiểm tra status trong JSON
            json_status = resp_json.get('status')
            if json_status == 200:
                result['success'] = True
            
            # Detect limit/checkpoint
            msg_lower = result['message'].lower()
            if any(kw in msg_lower for kw in ['limit', 'giới hạn', 'quá nhiều', 'too many', 'rate limit']):
                result['is_limit'] = True
            if any(kw in msg_lower for kw in ['checkpoint', 'verify', 'xác minh', 'captcha']):
                result['is_checkpoint'] = True
                
        except json.JSONDecodeError:
            result['message'] = response.text if response.text else f"HTTP {response.status_code}"
            
    except Exception as e:
        result['message'] = f"Exception: {str(e)}"
        job(f"[{func_name}] Exception: {str(e)}")
    
    # Log đầy đủ message
    limit_flag = " [LIMIT]" if result['is_limit'] else ""
    cp_flag = " [CHECKPOINT]" if result['is_checkpoint'] else ""
    job(f"[{func_name}] HTTP {result['status_code']} - {result['message']}{limit_flag}{cp_flag}")
    
    return result

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

def do_like(d, max_retry=10):
    if not d:
        return False
    
    check_stop()
    job("Scan tìm nút Like...")
    clicked = False
    
    for i in range(max_retry):
        check_stop()
        
        wait_for_ui_stable(d, wait_time=0.5)
        
        nodes = dump_ui_nodes(d)
        btn = find_like_btn(nodes)
        
        if not btn:
            job(f"Retry {i+1}/{max_retry} - chưa thấy nút")
            time.sleep(1.5)
            continue
        
        if is_liked(btn):
            job("Đã Like rồi")
            return True
        
        if not clicked:
            job(f"Click Like (lần {i+1})")
            if not click_node_by_bounds(d, btn):
                job("Không thể click nút like")
                continue
            clicked = True
        else:
            job("Đã click → chờ verify")
        
        for check in range(3):
            check_stop()
            time.sleep(2)
            
            nodes_after = dump_ui_nodes(d)
            btn_after = find_like_btn(nodes_after)
            
            if not btn_after:
                job("UI lag → chưa thấy lại")
                continue
            
            if is_liked(btn_after):
                job("Like thành công (verified)")
                return True
            
            job(f"Verify {check+1} chưa ăn")
        
        job("Click chưa ăn → cho click lại")
        clicked = False
        time.sleep(2)
    
    job("Fail Like")
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
            job(f"Đang quét UI tìm nút Follow (Lần {i+1})...")
            
            wait_for_ui_stable(d, wait_time=1.0)
            
            nodes = dump_ui_nodes(d)
            
            for node in nodes:
                text = node.get("text", "").strip().lower()
                res_id = node.get("resource-id", "")
                
                if any(t == text for t in target_texts) or any(idx in res_id for idx in target_ids):
                    if "đang theo dõi" in text or "following" in text:
                        job("Đã follow từ trước")
                        return True
                    
                    if click_node_by_bounds(d, node):
                        job("Đã click nút follow, đang verify...")
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
                            job("Follow thành công (real)")
                            return True
                        elif is_reverted:
                            job("Bị nhả follow (Shadowban hoặc mạng lỗi)")
                            return False
                        else:
                            job("Nút follow đã mất, nhưng UI khác lạ (KHÔNG phải fail)")
                            return True
            
            time.sleep(2)
            
        job("Không tìm thấy nút Follow sau khi đã chờ load")
        return False
            
    except Exception as e:
        job(f"Lỗi trong do_follow: {str(e)}")
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
            job(f"Đang quét UI tìm đúng nút Lưu (Lần {i+1})...")
            
            wait_for_ui_stable(d, wait_time=1.0)
            
            nodes = dump_ui_nodes(d)
            
            for node in nodes:
                res_id = node.get("resource-id", "")
                desc = node.get("content-desc", "").lower()
                
                is_fav = any(tid in res_id for tid in fav_identifiers["ids"]) or \
                         any(td in desc for td in fav_identifiers["descs"])

                if is_fav:
                    if node.get("selected") == "true" or "đã lưu" in desc or "added" in desc:
                        job("Video này đã được lưu vào Favorites từ trước.")
                        return True
                    
                    bounds = node.get("bounds", "")
                    if bounds:
                        job(f"Đã tìm thấy nút Favorites! (ID: {res_id})")
                        if click_node_by_bounds(d, node):
                            job("Đã Lưu video thành công!")
                            wait_for_ui_stable(d, wait_time=1.5)
                            return True
                            
            time.sleep(2)

        job("Không tìm thấy nút Favorites. Kiểm tra lại giao diện TikTok.")
        return False
        
    except Exception as e:
        job(f"Lỗi trong do_favorite: {str(e)}")
        return False

# ==================== CÁC HÀM XỬ LÝ COMMENT ====================
def do_comment(d, text, link):
    if not d:
        return False

    check_stop()
    global previous_job_link
    if previous_job_link == link:
        job(f"Bỏ qua bình luận - link trùng: {link}")
        return False

    filtered_text = filter_comment_content(text)
    if not filtered_text:
        return False

    last_comment = load_last_comment()
    if is_duplicate_comment(filtered_text, last_comment):
        job(f"Bình luận trùng/tương đồng với bình luận cuối cùng")
        return False

    job("Đợi video load để tìm nút comment...")
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
        
        job(f"Chưa thấy nút comment, chờ load (lần {attempt+1}/5)...")
        time.sleep(2)
        
    if not comment_opened:
        job("Không tìm thấy nút comment sau khi chờ")
        return False

    job("Tìm ô nhập comment...")
    check_stop()
    wait_for_ui_stable(d, wait_time=1.0)
    
    input_box = d(className="android.widget.EditText")
    if not input_box.exists:
        job("Không thấy ô nhập")
        return False

    input_box.click()
    wait_for_ui_stable(d, wait_time=0.5)
    
    try:
        input_box.clear_text()
    except Exception as e:
        job(f"Lỗi clear text: {str(e)}")
        
    d.clipboard.set(filtered_text)
    d.press("paste")
    wait_for_ui_stable(d, wait_time=1)
    job("Đã nhập nội dung comment")

    job("Tìm nút gửi bằng ảnh (cv2)...")
    check_stop()
    try:
        screenshot = d.screenshot(format="opencv")
        
        template_path = check_and_download_gui()
        
        if not os.path.exists(template_path):
            job("Cảnh báo: Không tìm thấy file ảnh, dùng phím Enter thay thế")
            d.press("enter")
        else:
            template = cv2.imread(template_path)
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            job(f"Độ khớp ảnh nút Gửi: {max_val:.2f}")
            threshold = 0.7

            if max_val >= threshold:
                h, w = template.shape[:2]
                x = max_loc[0] + w // 2
                y = max_loc[1] + h // 2
                d.click(x, y)
                job(f"Đã click nút Gửi qua CV2 tại ({x},{y})")
            else:
                job("Độ khớp thấp, dùng phím Enter thay thế")
                d.press("enter")
    except Exception as e:
        job(f"Lỗi xử lý CV2: {str(e)}, dùng phím Enter thay thế")
        d.press("enter")

    check_stop()
    if verify_comment_success(d, filtered_text):
        save_comment(filtered_text, "sent")
        previous_job_link = link
        return True
    else:
        job("Comment thất bại trong verify")
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
                        job(f"Tìm thấy comment với độ tương đồng {similarity:.2f}")
                        found = True
                        break
            except Exception as e:
                job(f"Lỗi khi đọc text element: {str(e)}")
                continue
        
        if found:
            return True
            
        error_msg = d(textMatches="(?i)(lỗi|thất bại|không thể đăng|spam)")
        if error_msg.exists(timeout=2):
            job("Phát hiện thông báo lỗi khi đăng comment")
            return False
            
        job("Không tìm thấy comment nhưng không có lỗi, tạm chấp nhận")
        return True
    except Exception as e:
        job(f"Lỗi verify comment: {str(e)}")
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
            headers=headers, json=json_data)

        # Parse response đầy đủ
        parsed = parse_api_response(response, "complete_jobs")
        
        if parsed['success']:
            save_link_job(link, job_type, "thành công", 0)
            return True, parsed['message']
        else:
            # Detect nếu là lỗi duplicate/limit
            msg_lower = parsed['message'].lower()
            if job_type == "comment" and any(kw in msg_lower for kw in ["vi phạm", "spam", "trùng", "không hợp lệ", "duplicate"]):
                previous_job_link = link
            return False, parsed['message']

    except Exception as e:
        error_msg = f"Exception: {str(e)}"
        job(f"Exception khi hoàn thành nhiệm vụ: {error_msg}")
        return False, error_msg

def get_job_price(job_data):
    try:
        price_fields = ['reward', 'price', 'money', 'coin', 'amount', 'value', 'point']
        for field in price_fields:
            if field in job_data:
                price = job_data[field]
                if isinstance(price, dict):
                    for subfield in ["amount", "value", "money", "coin"]:
                        if subfield in price:
                            price = price[subfield]
                            break
                if isinstance(price, str):
                    price = re.sub(r'[^\d.]', '', price)
                    if price:
                        price = float(price) if '.' in price else int(price)
                    else:
                        continue
                if isinstance(price, (int, float)) and price > 0:
                    return price

        default_prices = {
            'like': 5,
            'follow': 10,
            'comment': 8,
            'favorite': 6
        }
        return default_prices.get(job_data.get('type', ''), 5)
    except Exception as e:
        job(f"Lỗi lấy tiền nhiệm vụ: {str(e)}")
        return 5

def process_tiktok_job(job_data):
    try:
        check_stop()
        link = job_data["link"]
        action_type = job_data["type"]
        ads_id = job_data["id"]
        job_price = get_job_price(job_data)

        if action_type == "follow":
            if job_price < MIN_FOLLOW_PRICE:
                return False, f"giá thấp hơn {MIN_FOLLOW_PRICE}", ads_id, job_price

        if action_type not in ["like", "follow", "comment", "favorite"]:
            return False, "loại không hỗ trợ", None, 0

        if not open_link(link):
            return False, "mở link thất bại", ads_id, job_price

        success = False
        reason = ""

        wait_for_ui_stable(device, wait_time=2)

        if action_type == "like":
            success = do_like(device)
            reason = "thích thất bại" if not success else "thành công"
        elif action_type == "follow":
            success = do_follow(device)
            reason = "theo dõi thất bại" if not success else "thành công"
        elif action_type == "favorite":
            success = do_favorite(device)
            reason = "yêu thích thất bại" if not success else "thành công"
        elif action_type == "comment":
            comment_text = (
                job_data.get("text") or
                job_data.get("description") or
                job_data.get("comment") or
                job_data.get("noidung")
            )
            if not comment_text:
                return False, "thiếu nội dung bình luận", ads_id, job_price
            success = do_comment(device, comment_text, link)
            reason = "bình luận thất bại" if not success else "thành công"

        if not success:
            return False, reason, ads_id, job_price

        success, complete_reason = complete_and_check_response(ads_id, account_id, action_type, link)
        if success:
            save_link_job(link, action_type, "thành công", job_price)
        else:
            save_link_job(link, action_type, f"thất bại: {complete_reason}", job_price)

        return success, complete_reason, ads_id, job_price
    except Exception as e:
        if "STOP_FLAG" in str(e):
            raise
        error_msg = f"Exception: {str(e)}"
        job(f"Exception trong process_tiktok_job: {error_msg}")
        return False, error_msg, None, 0

# ==================== CÁC HÀM CŨ ĐƯỢC GIỮ LẠI ====================
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
\033[38;2;255;200;140m[\033[38;2;245;245;245m</>\033[38;2;255;200;140m] \033[38;2;200;160;255mADMIN:\033[38;2;255;235;180m NHƯ ANH ĐÃ THẤY EM   \033[38;2;255;220;160mPhiên Bản: \033[38;2;120;255;220mv3.3
\033[38;2;255;200;140m[\033[38;2;245;245;245m</>\033[38;2;255;200;140m] \033[38;2;200;160;255mNhóm Telegram: \033[38;2;120;255;220mhttps://t.me/se_meo_bao_an
\033[38;2;190;235;210m───────────────────────────────────────────────────────────────────────\033[0m
"""
    print(banner_text)

def check_and_download_gui():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    gui_path = os.path.join(current_dir, "gui.png")
    
    if not os.path.exists(gui_path):
        job("Chưa có file gui.png, đang tự động tải về thư mục tool...")
        url = "https://raw.githubusercontent.com/Caoquy2k3/Phong-tus/refs/heads/main/gui.png" 
        try:
            urllib.request.urlretrieve(url, gui_path)
            job(f"✓ Đã tải gui.png thành công tại: {gui_path}")
        except Exception as e:
            job(f"✗ Lỗi tải ảnh: {str(e)}")
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
            
            console.print("[green]✓ Đã tải cấu hình từ file[/]")
            return True
        except Exception as e:
            console.print(f"[yellow]⚠ Không thể tải cấu hình: {e}[/]")
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
        console.print(f"[red]Lỗi lưu cấu hình: {e}[/]")
        return False

def input_number(text, default):
    while True:
        try:
            value = input(text).strip()
            if value == "":
                return default
            return int(value)
        except Exception as e:
            console.print(f"[bold #ff4d6d]Sai định dạng! Nhập số. ({e})[/]")

def setup_delay_config():
    global delay_config, MIN_FOLLOW_PRICE, FORCE_STOP_ENABLED, FORCE_STOP_AFTER
    
    delay_like = [delay_config['like'][0], delay_config['like'][1]]
    delay_follow = [delay_config['follow'][0], delay_config['follow'][1]]
    delay_comment = [delay_config['comment'][0], delay_config['comment'][1]]
    delay_job = [delay_config['job'][0], delay_config['job'][1]]
    delay_fav = [delay_config['favorite'][0], delay_config['favorite'][1]]

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
                f"[bold {c1}]{name}[/]",
                f"[bold {c2}]{val[0]}[/][#aaaaaa]s[/]",
                f"[bold {c3}]{val[1]}[/][#aaaaaa]s[/]"
            ]

        table.add_row(*row("Delay Like", delay_like, "#ff4d6d", "#ffd1dc", "#ff8fa3"))
        table.add_row(*row("Delay Follow", delay_follow, "#00c853", "#b9f6ca", "#69f0ae"))
        table.add_row(*row("Delay Comment", delay_comment, "#00b0ff", "#80d8ff", "#40c4ff"))
        table.add_row(*row("Delay Get Jobs", delay_job, "#ff9100", "#ffd180", "#ffab40"))
        table.add_row(*row("Delay Favorite", delay_fav, "#a78bfa", "#c4b5fd", "#b388ff"))

        table.add_row(
            "[#ff9ecb]Lọc Follow[/]",
            f"[#ffffff]{loc_follow}[/]",
            "[#00ffff]ON/OFF[/]"
        )

        table.add_row(
            "[#ffd54f]Delay Hoàn Thành[/]",
            f"[bold #ffffff]{delay_done}[/]",
            "[#00ffff]s[/]"
        )

        table.add_row(
            "[#ff4d6d]Buộc Dừng chạy[/]",
            f"[#ffffff]{force_stop}[/]",
            "[#aaaaaa]-[/]"
        )

        table.add_row(
            "[#00b0ff]Số Job Buộc dừng[/]",
            f"[bold #ffffff]{stop_job}[/]",
            "[#aaaaaa]-[/]"
        )

        console.clear()
        console.print(table)

        console.print(
            "\n[#ff9ecb]➤ [#ffffff]Dùng lại config?[/] [#00ffff](Y/N)[/] ()[#ffffff]:",
            end=""
        )
        choice = input().strip().lower()

        if choice != "n":
            console.print("[#00ff9c] Giữ config hiện tại[/]")
            break

        console.print("\n[bold #ffd54f] Nhập lại cấu hình[/]\n")

        delay_like = [
            input_number("Delay Like Min: ", delay_like[0]),
            input_number("Delay Like Max: ", delay_like[1])
        ]

        delay_follow = [
            input_number("Delay Follow Min: ", delay_follow[0]),
            input_number("Delay Follow Max: ", delay_follow[1])
        ]

        delay_comment = [
            input_number("Delay Comment Min: ", delay_comment[0]),
            input_number("Delay Comment Max: ", delay_comment[1])
        ]

        delay_job = [
            input_number("Delay Get Jobs Min: ", delay_job[0]),
            input_number("Delay Get Jobs Max: ", delay_job[1])
        ]

        delay_fav = [
            input_number("Delay Favorite Min: ", delay_fav[0]),
            input_number("Delay Favorite Max: ", delay_fav[1])
        ]

        loc_follow = input_number("Lọc Follow (0 = OFF): ", loc_follow)
        delay_done = input_number("Delay Hoàn Thành: ", delay_done)

        force_stop_input = input("Buộc dừng chạy (y/n): ").strip().lower()
        force_stop = "Yes" if force_stop_input == "y" else "No"
        stop_job = input_number("Số job buộc dừng: ", stop_job)

    delay_config['like'] = delay_like
    delay_config['follow'] = delay_follow
    delay_config['comment'] = delay_comment
    delay_config['job'] = delay_job
    delay_config['favorite'] = delay_fav
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
    table.add_column("Nhiệm Vụ", width=15)
    table.add_column("Trạng Thái", justify="center", width=12)

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
            f"[{color}]{i+1}[/]",
            f"[{color}]{job['name']}[/]",
            status
        )
    return table

def menu_jobs():
    selections = [None] * len(JOBS)
    
    console.clear()
    console.print(Panel("[bold cyan]🔧 CẤU HÌNH NHIỆM VỤ[/]", border_style="#ff9ecb", width=50))
    console.print()
    
    for i, job in enumerate(JOBS):
        while True:
            console.clear()
            console.print(render_tablet(selections, i))
            
            ans = console.input(f"\n[#ff9ecb]➤ [#ffffff]Bạn có muốn làm nhiệm vụ [bold]{job['name']}[/] không? (y/n) [y]: [/]").strip().lower()
            
            if ans in ['y', 'yes', '']:
                selections[i] = 'y'
                break
            elif ans in ['n', 'no']:
                selections[i] = 'n'
                break
            else:
                console.print("[red]✗ Vui lòng nhập y hoặc n![/]", style="red")
                time.sleep(1)

    console.clear()
    console.print(render_tablet(selections, -1))
    
    selected_jobs = [JOBS[i]["id"] for i in range(len(JOBS)) if selections[i] == 'y']
    
    if selected_jobs:
        console.print(f"\n[#ffffff]📌 Nhiệm vụ đã chọn:[/] [bold #00ffff]{', '.join(job['name'] for job in JOBS if job['id'] in selected_jobs)}[/]")
        console.print(f"[#00ff9c]➤ Sẽ thực hiện {len(selected_jobs)} nhiệm vụ[/]\n")
    else:
        console.print("\n[#ff4d6d]⚠ Không có nhiệm vụ nào được chọn! Tool sẽ thoát.[/]")
        sys.exit(1)
    
    return selected_jobs

def get_device_model_from_adb(device_obj):
    try:
        return device_obj.shell("getprop ro.product.model").strip()
    except Exception as e:
        job(f"get_device_model error: {str(e)}")
        return "Unknown"

def get_battery_from_adb(device_obj):
    try:
        info = device_obj.shell("dumpsys battery")
        for line in info.splitlines():
            if "level" in line:
                return line.split(":")[1].strip()
    except Exception as e:
        job(f"get_battery error: {str(e)}")
    return ""

def show_devices_with_rich():
    console.clear()
    
    table = Table(
        title="[bold #ffffff]📱 DANH SÁCH THIẾT BỊ ADB[/]",
        border_style="#d7d7a8",
        show_lines=True,
        expand=False,
        title_justify="center"
    )

    table.add_column("STT", justify="center", style="#e0e0e0", width=5)
    table.add_column("Device ID", style="#00ff9c", width=25)
    table.add_column("Product Model", style="#ffd54f", width=20)
    table.add_column("🔋 Battery", justify="center", width=12)
    table.add_column("Status", style="#00ff99", width=10)

    devices = adb.device_list()

    if not devices:
        console.print(Panel("[red]Không tìm thấy thiết bị ADB nào![/]", border_style="red"))
        return []

    for i, d in enumerate(devices):
        model = get_device_model_from_adb(d)
        battery = get_battery_from_adb(d)
        
        if battery:
            try:
                b = int(battery)
                if b >= 80:
                    battery_display = f"[bold green]█[/bold green]" * (b // 10) + f"[green]{b}%[/green]"
                elif b >= 50:
                    battery_display = f"[bold yellow]█[/bold yellow]" * (b // 10) + f"[yellow]{b}%[/yellow]"
                elif b >= 20:
                    battery_display = f"[bold orange1]█[/bold orange1]" * (b // 10) + f"[orange1]{b}%[/orange1]"
                else:
                    battery_display = f"[bold red]█[/bold red]" * (b // 10) + f"[red]{b}%[/red]"
            except Exception as e:
                battery_display = f"[cyan]{battery}%[/cyan]"
        else:
            battery_display = "[dim]N/A[/dim]"

        table.add_row(
            str(i + 1),
            f"[#00ff9c]{d.serial}[/]",
            f"[#ffd54f]{model}[/]",
            battery_display,
            "[#00ff99]● Online[/]"
        )

    console.print(table)
    console.print()
    return devices

def get_adb_devices_new():
    devices = show_devices_with_rich()
    if not devices:
        return []
    return [d.serial for d in devices]

def get_status_color(status):
    status_lower = status.lower()
    if "đợi" in status_lower or "chờ" in status_lower or "đang chờ" in status_lower:
        return "yellow"
    elif "follow" in status_lower or "theo dõi" in status_lower:
        return "blue"
    elif "like" in status_lower or "thích" in status_lower:
        return "magenta"
    elif "comment" in status_lower or "bình luận" in status_lower:
        return "cyan"
    elif "favorite" in status_lower or "yêu thích" in status_lower:
        return "pink1"
    elif "hoàn thành" in status_lower or "thành công" in status_lower:
        return "green"
    elif "thất bại" in status_lower or "bỏ qua" in status_lower or "skip" in status_lower:
        return "red"
    elif "tìm nhiệm vụ" in status_lower:
        return "bright_black"
    elif "force stop" in status_lower or "buộc dừng" in status_lower:
        return "orange1"
    elif "bạn đã làm" in status_lower or "hết hạn" in status_lower or "hạn chế" in status_lower:
        return "red"
    elif "limit" in status_lower:
        return "red"
    elif "checkpoint" in status_lower:
        return "orange1"
    else:
        return "white"

def build_table():
    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    
    table.add_column("Device ID", style="bright_yellow", width=20)
    table.add_column("ID TikTok", style="bright_yellow", width=15)
    table.add_column("Status", style="white", width=22)
    table.add_column("Type Job", style="cyan", width=10)
    table.add_column("Xu", style="yellow", width=8)
    table.add_column("Tổng Xu", style="yellow", width=10)
    table.add_column("Done", style="green", width=8)
    table.add_column("Fail", style="red", width=8)
    
    with dashboard_lock:
        for acc_id, data in accounts_data.items():
            status = str(data.get("status", "Đang chờ..."))
            status_color = get_status_color(status)
            
            table.add_row(
                str(device_serial if device_serial else "N/A"),
                str(data.get("username", "?")),
                f"[{status_color}]{status}[/{status_color}]",
                str(data.get("job_type", "-")),
                str(data.get("xu", 0)),
                f"[yellow]{data.get('total_xu', 0)}[/yellow]",
                f"[green]{data.get('done', 0)}[/green]",
                f"[red]{data.get('fail', 0)}[/red]"
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
        Panel(f"[yellow]Tổng Xu : {total_xu}[/yellow]", width=15, style="bright_blue", box=box.ROUNDED),
        Panel(f"[cyan]Thiết bị : {total_devices}[/cyan]", width=15, style="bright_blue", box=box.ROUNDED),
        Panel(f"[green]Job Done : {total_done}[/green]", width=15, style="bright_blue", box=box.ROUNDED),
        Panel(f"[red]Job Fail : {total_fail}[/red]", width=15, style="bright_blue", box=box.ROUNDED),
    )
    return stats

def make_link_panel():
    with dashboard_lock:
        if accounts_data:
            first_device = list(accounts_data.values())[0]
            link = first_device.get("link", "Chưa có job")
        else:
            link = "Chưa có job"
    
    link_display = link
    if len(link) > 65:
        parts = []
        for i in range(0, len(link), 65):
            parts.append(link[i:i+65])
        link_display = "\n".join(parts)
    
    return Panel(
        Align.left(Text(link_display, style="bold cyan")),
        title="[bold green]🔗 LINK JOB HIỆN TẠI[/bold green]",
        border_style="bright_yellow",
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
                "[bold cyan]TOOL GOLIKE TIKTOK BOXPHONE - BY: PHONG Tus[/bold cyan]",
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
    with Live(
        make_layout(),
        refresh_per_second=2,
        screen=True,
        auto_refresh=True
    ) as live:
        while True:
            try:
                time.sleep(0.5)
                live.update(make_layout())
            except Exception as e:
                if logger:
                    logger.error(f"Dashboard refresh error: {e}")
                time.sleep(1)

def init_account_data(account_id_val, username):
    with dashboard_lock:
        if account_id_val not in accounts_data:
            accounts_data[account_id_val] = {
                "username": username,
                "status": "Đang chờ...",
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
            logger.error(f"Lỗi extract video_id từ {link}: {str(e)}")
        return link

def save_link_job(link, job_type, status, price):
    try:
        video_id = get_video_id(link)
        
        if status != "thành công":
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
        
        if logger:
            logger.info(f"Đã lưu video_id: {video_id} vào danh sách đã xử lý")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Lỗi lưu video_id: {str(e)}")
        return False

def is_link_processed(link):
    try:
        video_id = get_video_id(link)
        
        if os.path.exists(LINK_JOB_FILE):
            with open(LINK_JOB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            processed_videos = data.get("processed_videos", [])
            if video_id in processed_videos:
                if logger:
                    logger.info(f"Video ID {video_id} đã được xử lý thành công trước đó")
                return True
        
        return False
    except Exception as e:
        if logger:
            logger.error(f"Lỗi kiểm tra link đã xử lý: {str(e)}")
        return False

def job(msg):
    global logger
    if logger:
        logger.info(msg)
    
    # Cập nhật status lên dashboard nếu có account_id
    global account_id
    if account_id:
        # Chỉ cập nhật status ngắn gọn cho dashboard
        short_msg = msg[:50] if len(msg) > 50 else msg
        update_account_status(account_id, short_msg)

def get_instance_files(serial):
    safe_serial = re.sub(r'[^\w\-_]', '_', serial)
    return {
        'link_job': os.path.join(DATA_DIR, f"device_{safe_serial}_link_job.json"),
        'log': os.path.join(DATA_DIR, f"device_{safe_serial}_log.txt"),
        'check_cmt': os.path.join(DATA_DIR, f"device_{safe_serial}_check_cmt.json")
    }

def init_instance_files(serial):
    global INSTANCE_FILES, LINK_JOB_FILE, LOG_FILE, CHECK_CMT_FILE, logger, INSTANCE_ID
    INSTANCE_ID = serial
    INSTANCE_FILES = get_instance_files(serial)
    LINK_JOB_FILE = INSTANCE_FILES['link_job']
    LOG_FILE = INSTANCE_FILES['log']
    CHECK_CMT_FILE = INSTANCE_FILES['check_cmt']

    logger = setup_instance_logging(serial)
    job(f"Khởi tạo instance cho thiết bị: {serial}")

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
                        f.write(f"# Log file - {current_time} - Thiết bị: {serial}\n")
                elif file == CHECK_CMT_FILE:
                    with open(file, 'w', encoding='utf-8') as f:
                        json.dump({"last_comment": "", "history": []}, f)
            except Exception as e:
                job(f"Lỗi tạo file {file}: {str(e)}")
                return False
    return True

def setup_instance_logging(serial):
    safe_serial = re.sub(r'[^\w\-_]', '_', serial)
    log_filename = os.path.join(DATA_DIR, f"device_{safe_serial}_log.txt")

    instance_logger = logging.getLogger(f"device_{safe_serial}")
    instance_logger.setLevel(logging.INFO)
    instance_logger.handlers.clear()

    file_handler = RotatingFileHandler(log_filename, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    instance_logger.addHandler(file_handler)

    # Không thêm console handler để tránh print lung tung
    # console_handler = logging.StreamHandler(sys.stdout)
    # console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    # instance_logger.addHandler(console_handler)

    return instance_logger

def init_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    if not os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'w', encoding='utf-8') as f:
                json.dump({"tokens": []}, f, ensure_ascii=False, indent=2)
            print(f"Đã tạo file {AUTH_FILE}")
        except Exception as e:
            print(f"Lỗi tạo file {AUTH_FILE}: {str(e)}")
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
        print(f"Lỗi đọc file auth: {str(e)}")
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
        print(f"Lỗi lưu auth: {str(e)}")
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
        
        # Parse response đầy đủ
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
            return {
                "success": False,
                "auth": auth_token,
                "message": parsed['message']
            }
    except Exception as e:
        error_msg = f"Exception: {str(e)}"
        job(f"get_user_me error: {error_msg}")
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
        console.print("[yellow]⚠ Chưa có Authorization nào! Vui lòng nhập token.[/]")
        new_auth = console.input("[cyan]✈ Nhập Authorization: [/]").strip()
        if new_auth:
            save_authorization(new_auth)
            return display_auth_menu()
        else:
            console.print("[red]✖ Authorization không được để trống![/]")
            sys.exit(1)
    
    acc_lines = []
    for i, acc in enumerate(accounts):
        idx = f"{i+1:02d}"
        
        if acc.get("success"):
            username = acc.get("username", "Unknown")
            coin = acc.get("coin", 0)
            line = f"[#00ffff][{idx}][/] [#ff99cc]{username}[/] | [#99ff99]{coin} coin[/]"
        else:
            msg = acc.get('message', 'Lỗi hệ thống')
            line = f"[#00ffff][{idx}][/] [red]ERROR:[/] [#ff4444]{msg}[/]"
        
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
        '[#cccccc]Enter để tiếp tục, nhập "t" để thêm tài khoản golike:[/]',
        border_style="#d7d7a8",
        padding=(0, 1),
        width=80
    )
    console.print(panel_input)
    
    choice = console.input("[#ff9ecb]➤ [#ffffff]Lựa chọn: [/]").strip().lower()
    
    if choice == '':
        valid_accounts = [acc for acc in accounts if acc.get("success")]
        if valid_accounts:
            return valid_accounts[0]["auth"]
        else:
            console.print("[red]✖ Không có tài khoản hợp lệ nào![/]")
            sys.exit(1)
    elif choice == 't':
        new_auth = console.input("\n[white]Authorization: [/]").strip()
        if not new_auth:
            console.print("[red]Authorization không được để trống![/]")
            time.sleep(1.5)
            return display_auth_menu()
        
        console.print("[yellow]Đang kiểm tra token...[/]")
        session = requests.Session()
        result = get_user_me(new_auth, session)
        
        if result.get("success"):
            console.print(f"[green]✓ Token hợp lệ! Xin chào: {result['username']} | {result['coin']} coin[/]")
            save_authorization(new_auth)
            time.sleep(1)
            return display_auth_menu()
        else:
            console.print(f"[red]✗ Token không hợp lệ! Lỗi: {result.get('message', 'Unknown error')}[/]")
            time.sleep(2)
            return display_auth_menu()
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(accounts):
            acc = accounts[idx]
            if acc.get("success"):
                return acc["auth"]
            else:
                console.print(f"[red]✗ Tài khoản này không hợp lệ![/]")
                time.sleep(1.5)
                return display_auth_menu()
        else:
            console.print(f"[red]Số không hợp lệ! (1-{len(accounts)})[/]")
            time.sleep(1)
            return display_auth_menu()
    else:
        console.print(f"[red]Lựa chọn không hợp lệ![/]")
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
        job(f"Lỗi đọc file check_cmt: {str(e)}")
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
        job(f"Lỗi lưu bình luận: {str(e)}")
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
        job("Lỗi: Không có serial thiết bị")
        return None

    cmd = ['adb', '-s', use_serial] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result
    except Exception as e:
        job(f"Lỗi chạy ADB command {cmd}: {str(e)}")
        return None

def select_device():
    global device, device_serial
    
    devices_list = get_adb_devices_new()
    
    if not devices_list:
        console.print("[red]Không tìm thấy thiết bị ADB nào![/]")
        return False

    while True:
        try:
            choice = console.input(f"[cyan]✈ Chọn thiết bị (1-{len(devices_list)}): [/]").strip()
            choice = int(choice)
            if 1 <= choice <= len(devices_list):
                device_serial = devices_list[choice-1]
                if not init_instance_files(device_serial):
                    console.print("[red]Không thể khởi tạo file cho instance![/]")
                    return False
                break
            else:
                console.print("[red]Lựa chọn không hợp lệ![/]")
        except Exception as e:
            console.print(f"[red]Vui lòng nhập số! ({e})[/]")

    return connect_device(device_serial)

def connect_device(serial):
    global device
    max_retries = 3
    for attempt in range(max_retries):
        try:
            console.print(f"[yellow]Đang kết nối đến thiết bị {serial}... (lần {attempt+1})[/]")
            device = u2.connect(serial)
            device.info
            console.print(f"[green]✓ Kết nối thành công![/]")
            job(f"Kết nối thành công tới thiết bị {serial}")
            check_tiktok_installed()
            return True
        except Exception as e:
            console.print(f"[red]Kết nối thất bại: {str(e)}[/]")
            job(f"Kết nối thất bại tới {serial}: {str(e)}")
            time.sleep(2)
    return False

def check_tiktok_installed():
    global device
    try:
        packages = device.app_list()
        if TIKTOK_PACKAGE not in packages:
            console.print("[yellow]⚠ Cảnh báo: TikTok chưa được cài đặt![/]")
            job("Cảnh báo: TikTok chưa được cài đặt trên thiết bị")
            return False
        return True
    except Exception as e:
        job(f"Lỗi kiểm tra TikTok: {str(e)}")
        return False

def force_stop_tiktok():
    global device, device_serial
    
    check_stop()
    msg = f"[{device_serial}] Chuẩn bị buộc dừng TikTok..."
    job(msg)
    if account_id:
        update_account_status(account_id, f"Force Stop TikTok...")
    
    pkg = TIKTOK_PACKAGE
    device.shell(f"am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:{pkg}")
    
    wait_for_ui_stable(device, wait_time=2.5)
    
    if device(textMatches="(?i)(Buộc dừng|Buộc đóng|Force stop)").wait(timeout=10):
        for attempt in range(3):
            check_stop()
            btn_stop = device(resourceIdMatches=".*(?i)(force_stop|stop_button).*")
            if not btn_stop.exists:
                btn_stop = device(textMatches="(?i)(Buộc dừng|Buộc đóng|Force stop)")
            
            if btn_stop.exists and btn_stop.info.get('enabled', False):
                job(f"[{device_serial}] Đang bấm Buộc dừng (Lần {attempt+1})...")
                btn_stop.click()
                
                wait_for_ui_stable(device, wait_time=1.5)
                
                btn_ok = device(resourceId="android:id/button1")
                if not btn_ok.exists:
                    btn_ok = device(textMatches="(?i)(ok|đồng ý|xác nhận)")
                    
                if btn_ok.wait(timeout=3):
                    btn_ok.click()
                    job(f"[{device_serial}] Đã Force Stop TikTok thành công!")
                    wait_for_ui_stable(device, wait_time=1.5)
                    return
                else:
                    job(f"[{device_serial}] Chưa thấy nút OK, thử lại...")
                    time.sleep(1)
            else:
                job(f"[{device_serial}] App đã dừng từ trước (Nút bị mờ)")
                time.sleep(1)
                return
        
        job(f"[{device_serial}] ⚠ Đã thử 3 lần nhưng không thể Force Stop hoàn toàn.")
    else:
        job(f"[{device_serial}] ⚠ Không tìm thấy nút Buộc dừng trong cài đặt.")
    
    time.sleep(1)

def start_tiktok_and_wait():
    global device, device_serial
    
    check_stop()
    msg = f"[{device_serial}] Đang mở TikTok..."
    job(msg)
    if account_id:
        update_account_status(account_id, f"Đang mở TikTok...")
    
    device.app_start(TIKTOK_PACKAGE)
    
    if device(resourceIdMatches=".*tab_layout.*").wait(timeout=15):
        wait_for_ui_stable(device, wait_time=2)
        job(f"[{device_serial}] TikTok đã sẵn sàng")
        if account_id:
            update_account_status(account_id, f"TikTok sẵn sàng")
        return True
    else:
        job(f"[{device_serial}] Không thể đợi TikTok load")
        return False

def open_link(link):
    global device
    try:
        cmd = f'am start -a android.intent.action.VIEW -d "{link}" {TIKTOK_PACKAGE}'
        device.shell(cmd)
        launched = device.app_wait(TIKTOK_PACKAGE, timeout=10)
        if launched:
            wait_for_ui_stable(device, wait_time=2.5)
            job(f"Đã mở link: {link}")
        else:
            job(f"Không thể mở link: {link}")
        return launched
    except Exception as e:
        job(f"Lỗi mở link {link}: {str(e)}")
        return False

previous_job_link = None

def find_first_selector(d, candidates, timeout_per=1):
    for sel in candidates:
        try:
            obj = d(**sel)
            if obj.wait(timeout=timeout_per):
                return obj, sel
        except Exception as e:
            job(f"find_first_selector error: {str(e)}")
            continue
    return None, None

def dump_ui_nodes(device_obj):
    try:
        xml_content = device_obj.dump_hierarchy()
        
        nodes = []
        for match in re.finditer(r'<node (.*?)>', xml_content):
            attrs = dict(re.findall(r'([\w\-]+)="([^"]*)"', match.group(1)))
            nodes.append(attrs)
        
        return nodes
    except Exception as e:
        job(f"Lỗi dump UI nodes: {str(e)}")
        return []

def click_node_by_bounds(device_obj, node):
    bounds = node.get("bounds")
    if not bounds:
        return False
    
    pts = list(map(int, re.findall(r'\d+', bounds)))
    if len(pts) >= 4:
        x = (pts[0] + pts[2]) // 2
        y = (pts[1] + pts[3]) // 2
        
        job(f"Click tại {x},{y}")
        device_obj.click(x, y)
        return True
    
    return False

session = requests.Session()
headers = {}

# ==================== MAIN CODE ====================
if __name__ == "__main__":
    clear_stop_flag()
    
    if not init_files():
        console.print("[red]✖ Không thể khởi tạo files chung! Thoát tool.[/]")
        sys.exit(1)

    banner()
    console.print("[cyan]════════════════════════════════════════════════[/]")
    
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

    console.print("[green]✓ Đăng nhập thành công![/]")
    time.sleep(1)

    def chonacc():
        try:
            response = session.get('https://gateway.golike.net/api/tiktok-account', headers=headers)
            parsed = parse_api_response(response, "chonacc")
            
            if not parsed['success']:
                if logger:
                    logger.error(f"Lấy danh sách tài khoản thất bại: {parsed['message']}")
                return {"status": parsed['status_code'], "message": parsed['message'], "data": []}
            
            data = parsed['data'].get("data", []) if parsed['data'] else []
            return {"status": 200, "message": parsed['message'], "data": data}
        except Exception as e:
            error_msg = f"Exception: {str(e)}"
            if logger:
                logger.error(f"Lỗi chonacc: {error_msg}")
            return {"status": 500, "message": error_msg, "data": []}

    def nhannv(account_id_val):
        try:
            params = {'account_id': account_id_val, 'data': 'null'}
            response = session.get('https://gateway.golike.net/api/advertising/publishers/tiktok/jobs',
                                   headers=headers, params=params)
            parsed = parse_api_response(response, "nhannv")
            
            if not parsed['success']:
                if logger:
                    logger.warning(f"Nhận nhiệm vụ thất bại: {parsed['message']}")
                return {"status": parsed['status_code'], "message": parsed['message']}
            
            return {"status": 200, "message": parsed['message'], "data": parsed['data'].get("data") if parsed['data'] else None}
        except Exception as e:
            error_msg = f"Exception: {str(e)}"
            if logger:
                logger.error(f"Lỗi nhannv: {error_msg}")
            return {"status": 500, "message": error_msg}

    def baoloi(ads_id, object_id, account_id_val, loai):
        try:
            json_data = {'ads_id': ads_id, 'object_id': object_id, 'account_id': account_id_val, 'type': loai}
            response = session.post('https://gateway.golike.net/api/advertising/publishers/tiktok/skip-jobs',
                                    headers=headers, json=json_data)
            parsed = parse_api_response(response, "baoloi")
            
            if not parsed['success']:
                if logger:
                    logger.warning(f"Báo lỗi thất bại: {parsed['message']}")
                return {"status": parsed['status_code'], "message": parsed['message']}
            
            return {"status": 200, "message": parsed['message']}
        except Exception as e:
            error_msg = f"Exception: {str(e)}"
            if logger:
                logger.error(f"Lỗi baoloi: {error_msg}")
            return {"status": 500, "message": error_msg}

    chontktiktok = chonacc()

    if chontktiktok.get("status") != 200:
        msg = chontktiktok.get("message", "")
        console.print(f"[red]Lỗi lấy danh sách tài khoản TikTok từ Golike: {msg}[/]")
        if logger:
            logger.error(f"Authorization sai hoặc lỗi API: {msg}")
        sys.exit(1)

    console.print("[cyan]════════════════════════════════════════════════[/]")
    console.print("[yellow]⚙️ CẤU HÌNH DELAY VÀ THÔNG SỐ[/]")
    setup_delay_config()

    console.print("[cyan]════════════════════════════════════════════════[/]")
    lam = menu_jobs()

    console.print("[cyan]════════════════════════════════════════════════[/]")
    console.print("[yellow]Tiến hành kết nối thiết bị ADB...[/]")

    if not select_device():
        console.print("[red]✖ Không thể kết nối thiết bị. Thoát tool![/]")
        if logger:
            logger.error("Không thể kết nối thiết bị, thoát tool")
        sys.exit(1)

    # ============ KHỞI ĐỘNG DASHBOARD NGAY SAU KHI KẾT NỐI ============
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()
    time.sleep(1)

    # ============ TẠO ACCOUNT TẠM ĐỂ HIỂN THỊ DASHBOARD ============
    temp_account_id = "temp_loading"
    init_account_data(temp_account_id, "Đang tải...")
    update_account_status(temp_account_id, "Đang lấy username...")
    update_current_link(temp_account_id, "Chưa có job")

    # ============ XỬ LÝ FORCE STOP TRƯỚC KHI LẤY USERNAME (NẾU BẬT) ============
    if FORCE_STOP_ENABLED:
        update_account_status(temp_account_id, "Đang Force Stop TikTok...")
        console.print("[yellow]🔄 Đang thực hiện Force Stop TikTok theo cấu hình...[/]")
        force_stop_tiktok()
        time.sleep(2)
        update_account_status(temp_account_id, "Force Stop xong, đang mở lại TikTok...")
        console.print("[green]✓ Force Stop hoàn tất, đang mở lại TikTok...[/]")
    
    # ============ MỞ TIKTOK ============
    device.app_start(TIKTOK_PACKAGE)
    update_account_status(temp_account_id, "Đang mở TikTok...")
    console.print("[dim]Đợi TikTok load (5 giây)...[/dim]")
    time.sleep(5)
    
    # ============ LẤY USERNAME BẰNG CODE MỚI ============
    update_account_status(temp_account_id, "Đang lấy username (click vào profile)...")
    console.print("[yellow]📱 Đang lấy username TikTok (click vào profile)...[/yellow]")
    
    auto_username = get_tiktok_username_v2(device, max_retry=5)
    
    is_matched = False
    if auto_username:
        console.print(f"[green]✓ Đã lấy được username: {auto_username}[/green]")
        update_account_status(temp_account_id, f"Đã lấy username: {auto_username}")
        
        for acc in chontktiktok["data"]:
            golike_username = acc["unique_username"].strip().lower()
            if golike_username == auto_username:
                is_matched = True
                account_id = acc["id"]
                username = acc["unique_username"]
                
                # Xóa account tạm và thêm account thật
                with dashboard_lock:
                    if temp_account_id in accounts_data:
                        del accounts_data[temp_account_id]
                
                init_account_data(account_id, username)
                update_account_status(account_id, "Đã kết nối thành công!")
                update_current_link(account_id, "Chưa có job")
                console.print(f"[green]✓ Đã map thành công với tài khoản Golike: {username}[/green]")
                if logger:
                    logger.info(f"Auto-mapped account ID: {account_id} - Username: {username}")
                break
            else:
                job(f"So sánh: {golike_username} vs {auto_username}")
                
    if not is_matched:
        error_msg = f"Username lấy được ({auto_username}) không có trong danh sách Golike!"
        console.print(f"[red]✖ {error_msg}[/red]")
        console.print("[yellow]Vui lòng thêm tài khoản TikTok này vào Golike hoặc kiểm tra lại.[/yellow]")
        update_account_status(temp_account_id, error_msg)
        time.sleep(5)
        sys.exit(1)

    # ============ VÒNG LẶP CHÍNH ============
    try:
        # Nếu đã force stop ở trên thì không cần force stop lại
        if not FORCE_STOP_ENABLED:
            if FORCE_STOP_ENABLED:
                force_stop_tiktok()
        
        start_tiktok_and_wait()
        
        while True:
            check_stop()
            update_account_status(account_id, "Đang tìm nhiệm vụ...")
            
            time.sleep(get_random_delay_job('job'))

            nhanjob = {}
            while True:
                try:
                    check_stop()
                    nhanjob = nhannv(account_id)
                    break
                except Exception as e:
                    if "STOP_FLAG" in str(e):
                        raise
                    job(f"Lỗi khi gọi nhannv: {str(e)}")
                    time.sleep(1)

            if nhanjob.get("status") == 200:
                data = nhanjob.get("data")
                if not data or not data.get("link"):
                    msg = nhanjob.get("message", "Không có nhiệm vụ")
                    update_account_status(account_id, msg)
                    time.sleep(1)
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
                            update_account_status(account_id, f"Bỏ qua job đã làm: {result.get('message', 'OK')}")
                    except Exception as e:
                        job(f"Lỗi khi báo lỗi: {str(e)}")
                    continue

                if data["type"] not in lam:
                    try:
                        result = baoloi(data["id"], data["object_id"], account_id, data["type"])
                        if result.get("status") != 200:
                            msg = result.get("message", "")
                            update_account_status(account_id, msg)
                        else:
                            update_account_status(account_id, f"Bỏ qua job loại {data['type']}")
                        time.sleep(1)
                        continue
                    except Exception as e:
                        job(f"Lỗi khi báo lỗi: {str(e)}")
                        continue

                status_map = {
                    "follow": "Đang follow...",
                    "like": "Đang like...",
                    "comment": "Đang comment...",
                    "favorite": "Đang favorite..."
                }
                update_account_status(account_id, status_map.get(data["type"], f"Đang xử lý {data['type']}..."))

                success, reason, job_ads_id, job_price = process_tiktok_job(data)

                if success:
                    job_count += 1
                    update_account_stats(account_id, data["type"], job_price, success=True)
                    update_account_status(account_id, f"Hoàn thành - +{job_price}đ - {reason[:50] if len(reason) > 50 else reason}")

                    if FORCE_STOP_AFTER > 0 and job_count >= FORCE_STOP_AFTER:
                        job(f"[{device_serial}] Đã hoàn thành {job_count} job -> Force Stop")
                        update_account_status(account_id, f"Đã làm {job_count} job -> Force Stop...")
                        force_stop_tiktok()
                        job_count = 0
                        start_tiktok_and_wait()
                    
                    delay = delay_config['delay_done']
                    for remaining_time in range(delay, 0, -1):
                        check_stop()
                        update_account_status(account_id, f"Đợi {remaining_time}s...")
                        time.sleep(1)
                else:
                    update_account_stats(account_id, data["type"], 0, success=False)
                    # Hiển thị message đầy đủ, không cắt
                    update_account_status(account_id, reason)

                    try:
                        result = baoloi(data["id"], data["object_id"], account_id, data["type"])
                        if result.get("status") != 200:
                            msg = result.get("message", "")
                            job(f"Báo lỗi thất bại: {msg}")
                    except Exception as e:
                        job(f"Lỗi khi báo lỗi: {str(e)}")
                    time.sleep(1)
            else:
                error_msg = nhanjob.get("message", "")
                # Hiển thị message đầy đủ, không cắt
                update_account_status(account_id, error_msg)
                time.sleep(10)
                
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Đã dừng tool bởi người dùng![/]")
        if logger:
            logger.info("Tool đã dừng bởi người dùng")
    except Exception as e:
        if "STOP_FLAG" in str(e):
            console.print("\n[yellow]⚠ Tool đã được yêu cầu dừng khẩn cấp![/]")
        else:
            console.print(f"\n[red]✖ Lỗi không xác định: {e}[/]")
        if logger:
            logger.error(f"Lỗi không xác định: {e}")
