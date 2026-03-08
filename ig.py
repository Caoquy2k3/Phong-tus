#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
import random
import socket
import urllib3
import threading
from queue import Queue
from collections import defaultdict

# THÊM IMPORT CHO RICH
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import box
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

# Disable warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== Xử lý Timezone an toàn ==========
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
    except ZoneInfoNotFoundError:
        try:
            import tzdata
            VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
        except (ImportError, Exception):
            VIETNAM_TZ = timezone.utc
except ImportError:
    VIETNAM_TZ = timezone.utc

def get_current_time():
    """Lấy thời gian hiện tại theo múi giờ Việt Nam (hoặc UTC nếu không có)"""
    return datetime.now(VIETNAM_TZ)

# ========== Lấy IP thật từ API ==========
def get_public_ip():
    """
    Lấy địa chỉ IP public thật từ API ipify.org
    Nếu lỗi trả về "Không xác định"
    """
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=10, verify=False)
        if response.status_code == 200:
            data = response.json()
            return data.get("ip", "Không xác định")
        return "Không xác định"
    except:
        return "Không xác định"

# ========== Cấu hình an toàn ==========
MAX_SESSION_ERRORS = 5
ERROR_RESET_TIME = 1800
MAX_RETRY_COUNT = 2
RATE_LIMIT_BACKOFF = [5, 15, 30]

# ========== Biến toàn cục ==========
accounts_data = {}  # Lưu thông tin tất cả accounts
stop_threads = False  # Biến dừng các thread
thread_status = {}  # Theo dõi trạng thái các thread
account_locks = defaultdict(threading.Lock)  # Lock cho mỗi account

# ========== InstagramBot Class - Sử dụng API GraphQL đơn giản hóa ==========
class InstagramBot:
    BASE_URL = "https://www.instagram.com"
    GRAPHQL_URL = f"{BASE_URL}/graphql/query/"

    ACTION_CONFIG = {
        "follow": {
            "doc_id": "9740159112729312",
            "friendly_name": "usePolarisFollowMutation",
            "variable_key": "target_user_id",
            "response_field": "xdt_create_friendship"
        },
        "like": {
            "doc_id": "23951234354462179",
            "friendly_name": "usePolarisLikeMediaLikeMutation",
            "variable_key": "media_id",
            "response_field": "xdt_mark_media_like"
        }
    }

    def __init__(self, cookies_str, user_agent=None):
        self.session = requests.Session()
        self.fb_dtsg = None
        self.lsd = None
        self._set_cookies(cookies_str)
        self._set_default_headers(user_agent)
        self._extract_csrf()
        self._fetch_lsd()

    def _set_cookies(self, cookies_str):
        cookies = {}
        for item in cookies_str.split(';'):
            item = item.strip()
            if not item:
                continue
            if '=' in item:
                key, val = item.split('=', 1)
                cookies[key] = val
        self.session.cookies.update(cookies)

    def _set_default_headers(self, user_agent):
        self.session.headers.update({
            'authority': 'www.instagram.com',
            'accept': '*/*',
            'accept-language': 'vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.BASE_URL,
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user_agent or 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
            'x-ig-app-id': '1217981644879628',
        })

    def _extract_csrf(self):
        csrf = self.session.cookies.get('csrftoken')
        if csrf:
            self.session.headers.update({'x-csrftoken': csrf})
        else:
            raise ValueError("Không tìm thấy csrftoken trong cookies")

    def _fetch_lsd(self):
        """Lấy lsd từ cookies hoặc trang chủ"""
        self.lsd = self.session.cookies.get('lsd')
        if self.lsd:
            return

        try:
            response = self.session.get(self.BASE_URL, timeout=15, verify=False)
            if response.status_code == 200:
                # Pattern 1: ["LSD",[],{"token":"..."}]
                match = re.search(r'\["LSD",\[\],\{"token":"([^"]+)"', response.text)
                if match:
                    self.lsd = match.group(1)
                    return
                
                # Pattern 2: "LSD","token":"..."
                match = re.search(r'"LSD","token":"([^"]+)"', response.text)
                if match:
                    self.lsd = match.group(1)
                    return
                
                # Pattern 3: "LSD" : [ [ { "token" : "..."
                match = re.search(r'"LSD"\s*:\s*\[\s*\[\s*\{\s*"token"\s*:\s*"([^"]+)"', response.text)
                if match:
                    self.lsd = match.group(1)
                    return

            raise ValueError("Không thể tìm thấy lsd trong response từ trang chủ")

        except Exception as e:
            error_msg = f"Cookie thiếu thông số bảo mật LSD và không thể tự động lấy được. Lỗi: {str(e)[:100]}"
            print(f"\033[1;31m{error_msg}")
            print("Vui lòng cập nhật cookies mới có chứa 'lsd' hoặc đảm bảo cookie còn sống.")
            sys.exit(1)

    def _get_simple_payload(self, action, target_id):
        """Tạo payload đơn giản, chỉ với các tham số cần thiết"""
        
        variables = {}
        if action == "follow":
            variables = {
                "target_user_id": str(target_id),
                "container_module": "profile",
                "nav_chain": "PolarisFeedRoot:feedPage:4:topnav-link,PolarisProfilePostsTabRoot:profilePage:6:unexpected"
            }
        elif action == "like":
            variables = {
                "media_id": str(target_id),
                "container_module": "single_post"
            }

        payload = {
            'lsd': self.lsd,
            'doc_id': self.ACTION_CONFIG[action]["doc_id"],
            'variables': json.dumps(variables)
        }
        
        return payload

    def follow(self, user_id):
        return self._action("follow", user_id)

    def like(self, media_id):
        return self._action("like", media_id)

    def _action(self, action, target_id):
        try:
            time.sleep(random.uniform(1.5, 3.5))
            
            headers = {
                'referer': f'{self.BASE_URL}/',
                'x-fb-friendly-name': self.ACTION_CONFIG[action]["friendly_name"],
            }
            self.session.headers.update(headers)
            
            payload = self._get_simple_payload(action, target_id)
            
            response = self.session.post(self.GRAPHQL_URL, data=payload, timeout=20, verify=False)

            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    if resp_json.get('data') and (
                        resp_json['data'].get('xdt_create_friendship') or 
                        resp_json['data'].get('xdt_mark_media_like')
                    ):
                        return {'status': True, 'message': 'Thành công', 'response': response}
                    elif resp_json.get('errors'):
                        return {'status': False, 'message': resp_json['errors'][0]['message'], 'response': response}
                    else:
                        return {'status': False, 'message': 'Unknown response', 'response': response}
                except:
                    return {'status': False, 'message': 'Invalid JSON response', 'response': response}
            else:
                return {'status': False, 'message': f'HTTP {response.status_code}', 'response': response}
                
        except requests.exceptions.Timeout:
            return {'status': False, 'message': 'Timeout', 'response': None}
        except requests.exceptions.ConnectionError:
            return {'status': False, 'message': 'Connection Error', 'response': None}
        except Exception as e:
            return {'status': False, 'message': f'Exception: {str(e)}', 'response': None}


# ========== Các hàm xử lý job ==========
def handle_follow_job(cookies, object_id, account_id, account_data):
    global stop_threads

    if stop_threads:
        return {"status": False, "message": "Thread stopped"}

    with account_locks[account_id]:
        account_data["status"] = "Đang thực hiện follow..."
    
    retry_count = 0
    max_retries = MAX_RETRY_COUNT

    while retry_count < max_retries and not stop_threads:
        try:
            bot = InstagramBot(cookies)
            result = bot.follow(object_id)

            if result['status']:
                with account_locks[account_id]:
                    account_data["status"] = result.get('message', 'Follow thành công')
                return {"status": True, "message": result.get('message', 'Follow thành công')}
            else:
                error_msg = result.get('message', 'Lỗi không xác định')
                with account_locks[account_id]:
                    account_data["status"] = error_msg[:50]
                ghi_log_follow(object_id, error_msg)

                if kiem_tra_checkpoint(error_msg):
                    increment_error(account_data, 'checkpoint')
                    with account_locks[account_id]:
                        account_data["status"] = error_msg
                    return {"status": False, "message": error_msg, "fatal": True}

                if kiem_tra_rate_limit(error_msg, 429 if 'rate' in error_msg.lower() else 200):
                    increment_error(account_data, 'rate_limit')
                    wait_time = RATE_LIMIT_BACKOFF[min(retry_count, len(RATE_LIMIT_BACKOFF)-1)]
                    # Countdown rate limit
                    for i in range(wait_time, 0, -1):
                        if stop_threads:
                            return {"status": False, "message": "Thread stopped"}
                        with account_locks[account_id]:
                            account_data["status"] = f"Rate limit - Nghỉ {i} giây..."
                        time.sleep(1)
                    retry_count += 1
                    continue

                if kiem_tra_cookie_die(error_msg, 403 if 'forbidden' in error_msg.lower() else 200):
                    increment_error(account_data, 'other')
                    with account_locks[account_id]:
                        account_data["status"] = error_msg
                    return {"status": False, "message": error_msg, "fatal": True}

                increment_error(account_data, 'follow')
                return {"status": False, "message": error_msg}

        except Exception as e:
            increment_error(account_data, 'other')
            retry_count += 1
            if retry_count < max_retries and not stop_threads:
                wait_time = random.randint(5, 10)
                for i in range(wait_time, 0, -1):
                    if stop_threads:
                        return {"status": False, "message": "Thread stopped"}
                    with account_locks[account_id]:
                        account_data["status"] = f"Lỗi: {str(e)[:20]} - Thử lại sau {i} giây..."
                    time.sleep(1)
            else:
                error_msg = f"exception: {str(e)[:50]}"
                with account_locks[account_id]:
                    account_data["status"] = error_msg
                ghi_log_follow(object_id, error_msg)
                return {"status": False, "message": error_msg}

    increment_error(account_data, 'follow')
    with account_locks[account_id]:
        account_data["status"] = "Follow thất bại sau nhiều lần thử"
    return {"status": False, "message": "Follow thất bại sau nhiều lần thử"}

def handle_like_job(cookies, idlike, link, account_id, account_data):
    global stop_threads

    if stop_threads:
        return {"status": False, "message": "Thread stopped"}

    with account_locks[account_id]:
        account_data["status"] = "Đang thực hiện like..."
    
    retry_count = 0
    max_retries = MAX_RETRY_COUNT

    while retry_count < max_retries and not stop_threads:
        try:
            bot = InstagramBot(cookies)
            result = bot.like(idlike)

            if result['status']:
                with account_locks[account_id]:
                    account_data["status"] = result.get('message', 'Like thành công')
                return {"status": True, "message": result.get('message', 'Like thành công')}
            else:
                error_msg = result.get('message', 'Lỗi không xác định')
                with account_locks[account_id]:
                    account_data["status"] = error_msg[:50]
                ghi_log_like(link, error_msg)

                if kiem_tra_checkpoint(error_msg):
                    increment_error(account_data, 'checkpoint')
                    with account_locks[account_id]:
                        account_data["status"] = error_msg
                    return {"status": False, "message": error_msg, "fatal": True}

                if kiem_tra_rate_limit(error_msg, 429 if 'rate' in error_msg.lower() else 200):
                    increment_error(account_data, 'rate_limit')
                    wait_time = RATE_LIMIT_BACKOFF[min(retry_count, len(RATE_LIMIT_BACKOFF)-1)]
                    for i in range(wait_time, 0, -1):
                        if stop_threads:
                            return {"status": False, "message": "Thread stopped"}
                        with account_locks[account_id]:
                            account_data["status"] = f"Rate limit - Nghỉ {i} giây..."
                        time.sleep(1)
                    retry_count += 1
                    continue

                if kiem_tra_cookie_die(error_msg, 403 if 'forbidden' in error_msg.lower() else 200):
                    increment_error(account_data, 'other')
                    with account_locks[account_id]:
                        account_data["status"] = error_msg
                    return {"status": False, "message": error_msg, "fatal": True}

                increment_error(account_data, 'like')
                return {"status": False, "message": error_msg}

        except Exception as e:
            increment_error(account_data, 'other')
            retry_count += 1
            if retry_count < max_retries and not stop_threads:
                wait_time = random.randint(5, 10)
                for i in range(wait_time, 0, -1):
                    if stop_threads:
                        return {"status": False, "message": "Thread stopped"}
                    with account_locks[account_id]:
                        account_data["status"] = f"Lỗi: {str(e)[:20]} - Thử lại sau {i} giây..."
                    time.sleep(1)
            else:
                error_msg = f"exception: {str(e)[:50]}"
                with account_locks[account_id]:
                    account_data["status"] = error_msg
                ghi_log_like(link, error_msg)
                return {"status": False, "message": error_msg}

    increment_error(account_data, 'like')
    with account_locks[account_id]:
        account_data["status"] = "Like thất bại sau nhiều lần thử"
    return {"status": False, "message": "Like thất bại sau nhiều lần thử"}

# ========== Các hàm kiểm tra lỗi ==========
def increment_error(account_data, error_type='other'):
    if "error_counts" not in account_data:
        account_data["error_counts"] = {'follow': 0, 'like': 0, 'checkpoint': 0, 'rate_limit': 0, 'other': 0}
    account_data["error_counts"][error_type] = account_data["error_counts"].get(error_type, 0) + 1
    account_data["session_errors"] = account_data.get("session_errors", 0) + 1
    account_data["last_error_time"] = time.time()

def ghi_log_like(link, error_message):
    try:
        with open('link_job.txt', 'a', encoding='utf-8') as f:
            current_time = get_current_time().strftime("%H:%M:%S")
            f.write(f"[{current_time}] | {link} | {error_message}\n")
    except:
        pass

def ghi_log_follow(object_id, error_message):
    try:
        with open('link_job.txt', 'a', encoding='utf-8') as f:
            current_time = get_current_time().strftime("%H:%M:%S")
            link = f"https://instagram.com/{object_id}"
            f.write(f"[{current_time}] | {link} | {error_message}\n")
    except:
        pass

def kiem_tra_cookie_die(error_msg, status_code):
    cookie_die_messages = [
        'login_required', 'checkpoint_required', 'forbidden',
        'not_authorized', 'unauthorized', 'invalid_token',
        'The access token is invalid'
    ]
    
    if status_code in [401, 403]:
        return True
    if any(msg in str(error_msg).lower() for msg in cookie_die_messages):
        return True
    return False

def kiem_tra_checkpoint(error_msg):
    checkpoint_messages = ['checkpoint_required', 'checkpoint', 'challenge_required']
    if any(msg in str(error_msg).lower() for msg in checkpoint_messages):
        return True
    return False

def kiem_tra_rate_limit(error_msg, status_code):
    if status_code == 429:
        return True
    rate_messages = ['rate_limit', 'too many requests', 'please wait']
    if any(msg in str(error_msg).lower() for msg in rate_messages):
        return True
    return False

# ========== Hàm gọi API Golike ==========
def chonacc(headers):
    url = 'https://gateway.golike.net/api/instagram-account'
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": False, "message": response.text}
    except requests.exceptions.Timeout:
        return {"status": False, "message": "Timeout khi kết nối Golike"}
    except requests.exceptions.ConnectionError:
        return {"status": False, "message": "Lỗi kết nối Golike"}
    except Exception as e:
        return {"status": False, "message": str(e)}

def nhannv(account_id, headers):
    params = {
        'instagram_account_id': account_id,
        'data': 'null'
    }
    url = 'https://gateway.golike.net/api/advertising/publishers/instagram/jobs'
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": False, "message": response.text}
    except requests.exceptions.Timeout:
        return {"status": False, "message": "Timeout khi nhận job"}
    except requests.exceptions.ConnectionError:
        return {"status": False, "message": "Lỗi kết nối khi nhận job"}
    except Exception as e:
        return {"status": False, "message": str(e)}

def hoanthanh(ads_id, account_id, headers):
    json_data = {
        'instagram_users_advertising_id': ads_id,
        'instagram_account_id': account_id,
        'async': True,
        'data': None
    }
    try:
        response = requests.post('https://gateway.golike.net/api/advertising/publishers/instagram/complete-jobs',
                                 headers=headers, json=json_data, timeout=15, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": False, "message": response.text}
    except requests.exceptions.Timeout:
        return {"status": False, "message": "Timeout khi hoàn thành"}
    except requests.exceptions.ConnectionError:
        return {"status": False, "message": "Lỗi kết nối khi hoàn thành"}
    except Exception as e:
        return {"status": False, "message": str(e)}

def baoloi(ads_id, object_id, account_id, loai, headers):
    json_data1 = {
        'description': 'Tôi đã làm Job này rồi',
        'users_advertising_id': ads_id,
        'type': 'ads',
        'provider': 'instagram',
        'fb_id': account_id,
        'error_type': 6
    }
    try:
        requests.post('https://gateway.golike.net/api/report/send', headers=headers, json=json_data1, timeout=8, verify=False)
    except:
        pass
    
    json_data = {
        'ads_id': ads_id,
        'object_id': object_id,
        'account_id': account_id,
        'type': loai
    }
    try:
        response = requests.post('https://gateway.golike.net/api/advertising/publishers/instagram/skip-jobs',
                                headers=headers, json=json_data, timeout=8, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": False, "message": response.text}
    except Exception as e:
        return {"status": False, "message": str(e)}

# ========== Hàm banner ==========
def banner():
    os.system('clear' if os.name == 'posix' else 'cls')
    banner_str = """
                 
        """
    print(banner_str)

def hien_thi_danh_sach_acc(accounts_list):
    """Hiển thị danh sách account để chọn"""
    print("\033[1;97m═══════════════════════════════════════════════════════════════════")
    print("\033[1;33m Danh sách acc Instagram trên Golike: ")
    print("\033[1;97m═══════════════════════════════════════════════════════════════════")
    
    # Hiển thị từng account
    for i, acc in enumerate(accounts_list):
        status_color = "\033[1;32m" if acc.get('active', True) else "\033[1;31m"
        status_text = "Hoạt động" if acc.get('active', True) else "Không hoạt động"
        print(f"\033[1;36m[{i+1}] \033[1;97mUsername: \033[1;93m{acc['instagram_username']} \033[1;97m| ID: \033[1;93m{acc['id']} \033[1;97m| Trạng thái: {status_color}{status_text}")
    
    # Thêm một dòng trống để phân cách
    print("\033[1;97m═══════════════════════════════════════════════════════════════════")
    
    # Hiển thị thông báo về số lượng account
    print(f"\033[1;36mTổng số: {len(accounts_list)} account")

def chon_accounts_de_chay(accounts_list):
    """Cho phép người dùng chọn nhiều account để chạy"""
    global accounts_data
    
    # Hiển thị danh sách account
    hien_thi_danh_sach_acc(accounts_list)
    
    print("\033[1;33mNhập số thứ tự các account muốn chạy (cách nhau bằng dấu cách)")
    print("\033[1;33mVí dụ: 1 3 5 7 (chạy account 1, 3, 5, 7)")
    print("\033[1;33mHoặc nhập 'all' để chạy tất cả")
    print("\033[1;33m----------------------------------------")
    # Thêm một khoảng trống để tách biệt phần nhập với danh sách
    print("" * 2)
    
    # Bây giờ mới gọi input()
    choice = input("\033[1;32mNhập lựa chọn: ").strip()
    
    selected_indices = []
    if choice.lower() == 'all':
        selected_indices = list(range(len(accounts_list)))
    else:
        try:
            parts = choice.split()
            for part in parts:
                idx = int(part) - 1
                if 0 <= idx < len(accounts_list):
                    selected_indices.append(idx)
                else:
                    print(f"\033[1;31mBỏ qua số {part} không hợp lệ")
        except:
            print("\033[1;31mLựa chọn không hợp lệ, chạy tất cả account")
            selected_indices = list(range(len(accounts_list)))
    
    # Khởi tạo accounts_data với các account được chọn
    accounts_data = {}
    for idx in selected_indices:
        acc = accounts_list[idx]
        account_id = acc['id']
        username = acc['instagram_username']
        
        # Kiểm tra file cookie riêng cho từng account
        cookie_file = f"cookies_{username}.txt"
        cookie = ""
        
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, 'r') as f:
                    cookie = f.read().strip()
            except:
                pass
        
        # Nếu chưa có cookie, yêu cầu nhập
        if not cookie:
            print(f"\n\033[1;33mNhập cookie cho account {username}:")
            cookie = input(f"\033[1;32mCookie: ").strip()
            if cookie.lower() == 'exit':
                sys.exit(0)
            try:
                with open(cookie_file, 'w') as f:
                    f.write(cookie)
                print(f"\033[1;32mĐã lưu cookie cho {username}")
            except Exception as e:
                print(f"\033[1;31mLỗi lưu cookie: {e}")
        
        accounts_data[account_id] = {
            "username": username,
            "cookie": cookie,
            "selected": True,
            "done": 0,
            "skip": 0,
            "follow": 0,
            "like": 0,
            "cmt": 0,
            "favorite": 0,
            "coin": 0,
            "status": "Đang chờ...",
            "session_errors": 0,
            "last_error_time": 0,
            "error_counts": {
                'follow': 0, 'like': 0, 'checkpoint': 0, 'rate_limit': 0, 'other': 0
            },
            "is_running": True,  # Trạng thái chạy của account
            "thread_id": None
        }
    
    print(f"\033[1;32mĐã chọn {len(accounts_data)} account để chạy")
    return accounts_data

# ========== HÀM XÂY DỰNG BẢNG DASHBOARD - HIỂN THỊ TẤT CẢ ACCOUNT ==========
def build_table():
    table = Table(box=box.SQUARE)

    table.add_column("STT", justify="center")
    table.add_column("Username", style="cyan")
    table.add_column("Trạng thái", style="bold", justify="center")
    table.add_column("Jobs Done", justify="center", style="green")
    table.add_column("Jobs Skip", justify="center", style="red")
    table.add_column("Follow", justify="center")
    table.add_column("Like", justify="center")
    table.add_column("Coin", justify="center", style="yellow")
    table.add_column("Chi tiết", style="magenta")

    for i, (acc_id, data) in enumerate(accounts_data.items(), 1):
        # Xác định trạng thái và màu sắc
        if not data.get("is_running", True):
            status = " Đã dừng"
            status_color = "red"
        elif "checkpoint" in data.get("status", "").lower() or "die" in data.get("status", "").lower():
            status = " Lỗi"
            status_color = "red"
        elif "thành công" in data.get("status", "").lower() or "hoàn thành" in data.get("status", "").lower():
            status = " Đang chạy"
            status_color = "green"
        else:
            status = " Đang chạy"
            status_color = "yellow"
        
        # Lấy chi tiết lỗi nếu có
        detail = data.get("status", "")
        if len(detail) > 30:
            detail = detail[:27] + "..."
            
        table.add_row(
            str(i),
            data.get("username", ""),
            f"[{status_color}]{status}[/{status_color}]",
            str(data.get("done", 0)),
            str(data.get("skip", 0)),
            str(data.get("follow", 0)),
            str(data.get("like", 0)),
            str(data.get("coin", 0)),
            detail
        )

    return table

def safe_str(value):
    """Chuyển đổi an toàn mọi giá trị sang string, None -> "0" """
    if value is None:
        return "0"
    return str(value)

def countdown_delay(account_id, account_data, total_seconds):
    """Hiển thị đếm ngược thời gian delay"""
    global stop_threads
    for i in range(total_seconds, 0, -1):
        if stop_threads:
            return
        with account_locks[account_id]:
            account_data["status"] = f"Delay {i} giây..."
        time.sleep(1)

# ========== Hàm chạy cho mỗi account trong thread riêng ==========
def run_account(account_id, account_data, headers, lam, base_delay, lannhan, doiacc):
    global stop_threads
    
    # Lưu thread ID
    account_data["thread_id"] = threading.current_thread().ident
    cookies = account_data["cookie"]
    username = account_data["username"]
    checkdoiacc = 0
    job_counter = 0
    
    with account_locks[account_id]:
        account_data["status"] = "Bắt đầu chạy..."
        account_data["is_running"] = True
    
    print(f"\033[1;32m[Thread {username}] Đã khởi động")
    
    while not stop_threads and account_data.get("is_running", True):
        try:
            # Kiểm tra đổi acc nếu fail quá nhiều
            if checkdoiacc >= doiacc and doiacc > 1:
                with account_locks[account_id]:
                    account_data["status"] = f"Đã đạt giới hạn fail ({doiacc}), dừng account"
                    account_data["is_running"] = False
                print(f"\033[1;31m[Thread {username}] Dừng do đạt giới hạn lỗi")
                break

            # Gọi API nhận job
            with account_locks[account_id]:
                account_data["status"] = "Đang gọi API nhận job..."
            
            nhanjob = nhannv(account_id, headers)
            
            # Kiểm tra nếu nhannv trả về lỗi timeout
            if isinstance(nhanjob, dict) and nhanjob.get('status') == False and 'Timeout' in nhanjob.get('message', ''):
                with account_locks[account_id]:
                    account_data["status"] = f"Timeout API - Thử lại..."
                # Đếm ngược 5 giây
                for i in range(5, 0, -1):
                    if stop_threads:
                        return
                    with account_locks[account_id]:
                        account_data["status"] = f"Timeout - Thử lại sau {i}s"
                    time.sleep(1)
                continue

            # Xử lý response
            if not isinstance(nhanjob, dict) or nhanjob.get('status') != 200:
                msg = nhanjob.get('message', '') if isinstance(nhanjob, dict) else 'Lỗi không xác định'
                with account_locks[account_id]:
                    account_data["status"] = f"Không có job - {msg[:30]}"
                wait_time = random.randint(5, 15)
                for i in range(wait_time, 0, -1):
                    if stop_threads:
                        return
                    with account_locks[account_id]:
                        account_data["status"] = f"Chờ {i} giây trước khi thử lại..."
                    time.sleep(1)
                continue

            # Đã nhận được job
            with account_locks[account_id]:
                account_data["status"] = "Đã nhận job, đang xử lý..."
            
            data = nhanjob.get('data', {})
            ads_id = data.get('id')
            link = data.get('link')
            object_id = data.get('object_id')
            loai = data.get('type')

            # Kiểm tra dữ liệu
            if not object_id:
                with account_locks[account_id]:
                    account_data["status"] = f"Lỗi: object_id rỗng"
                time.sleep(2)
                continue

            if loai not in lam:
                try:
                    baoloi(ads_id, object_id, account_id, loai, headers)
                    with account_locks[account_id]:
                        account_data["status"] = f"Đã bỏ qua job {loai} (không trong chế độ đã chọn)"
                        account_data["skip"] += 1
                    time.sleep(1)
                    continue
                except Exception as e:
                    with account_locks[account_id]:
                        account_data["status"] = f"Lỗi bỏ qua job: {str(e)[:30]}"
                    time.sleep(1)
                    continue

            # Xử lý job theo loại
            success = {"status": False, "message": "Không xác định"}
            if loai == "follow":
                success = handle_follow_job(cookies, object_id, account_id, account_data)
            elif loai == "like":
                media_id = data.get('object_data', {}).get('pk')
                if not media_id:
                    with account_locks[account_id]:
                        account_data["status"] = f"Lỗi: media_id rỗng"
                    time.sleep(2)
                    continue
                success = handle_like_job(cookies, media_id, link, account_id, account_data)

            # Kiểm tra lỗi fatal
            if success.get('fatal'):
                with account_locks[account_id]:
                    account_data["status"] = f"Lỗi nghiêm trọng: {success.get('message', '')}"
                # Countdown trước khi tiếp tục
                for i in range(10, 0, -1):
                    if stop_threads:
                        return
                    with account_locks[account_id]:
                        account_data["status"] = f"Lỗi nghiêm trọng - Chờ {i} giây..."
                    time.sleep(1)
                
                # Nếu lỗi fatal (cookie die, checkpoint), dừng account này
                if kiem_tra_cookie_die(success.get('message', ''), 403) or kiem_tra_checkpoint(success.get('message', '')):
                    with account_locks[account_id]:
                        account_data["is_running"] = False
                        account_data["status"] = f"Dừng: {success.get('message', '')}"
                    print(f"\033[1;31m[Thread {username}] Dừng do lỗi fatal: {success.get('message', '')}")
                    break
                continue

            # Delay job
            actual_delay = random.randint(int(base_delay * 0.8), int(base_delay * 1.2))
            countdown_delay(account_id, account_data, actual_delay)

            # Nhận tiền
            with account_locks[account_id]:
                account_data["status"] = "Đang nhận tiền lần 1..."
            
            now = get_current_time()
            h = now.strftime("%H")
            m = now.strftime("%M")
            s = now.strftime("%S")
            
            if success.get('status'):
                try:
                    nhantien = hoanthanh(ads_id, account_id, headers)
                except Exception as e:
                    with account_locks[account_id]:
                        account_data["status"] = f"Lỗi nhận tiền: {str(e)[:30]}"
                    time.sleep(2)
                    continue

                if lannhan == 'y':
                    checklan = 1
                else:
                    checklan = 2

                ok = 0
                while checklan <= 2 and not stop_threads:
                    if nhantien and nhantien.get('status') == 200:
                        ok = 1
                        tien = nhantien.get('data', {}).get('prices', 0)
                        
                        # Cập nhật dashboard
                        with account_locks[account_id]:
                            account_data["done"] += 1
                            account_data["coin"] += tien
                            
                            if loai == "follow":
                                account_data["follow"] += 1
                            elif loai == "like":
                                account_data["like"] += 1
                            
                            api_message = nhantien.get('message', 'Hoàn thành nhiệm vụ')
                            account_data["status"] = f"[{h}:{m}:{s}] {api_message} +{tien}"
                        
                        checkdoiacc = 0
                        break
                    else:
                        checklan += 1
                        if checklan == 3:
                            break
                        with account_locks[account_id]:
                            account_data["status"] = "Đang nhận tiền lần 2..."
                        try:
                            nhantien = hoanthanh(ads_id, account_id, headers)
                        except:
                            pass

                if ok != 1:
                    try:
                        baoloi_response = baoloi(ads_id, object_id, account_id, loai, headers)
                        with account_locks[account_id]:
                            account_data["skip"] += 1
                            account_data["status"] = f"[{h}:{m}:{s}] Đã bỏ qua job"
                        checkdoiacc += 1
                        time.sleep(1)
                    except Exception as e:
                        with account_locks[account_id]:
                            account_data["status"] = f"Lỗi bỏ qua: {str(e)[:30]}"
                        time.sleep(1)
            else:
                try:
                    baoloi_response = baoloi(ads_id, object_id, account_id, loai, headers)
                    with account_locks[account_id]:
                        account_data["skip"] += 1
                        account_data["status"] = f"[{h}:{m}:{s}] Đã bỏ qua job ({success.get('message', '')[:30]})"
                    checkdoiacc += 1
                    time.sleep(1)
                except Exception as e:
                    with account_locks[account_id]:
                        account_data["status"] = f"Lỗi bỏ qua: {str(e)[:30]}"
                    time.sleep(1)
            
            job_counter += 1
            if job_counter % 10 == 0 and not stop_threads:
                rest_time = random.randint(10, 20)
                for i in range(rest_time, 0, -1):
                    if stop_threads:
                        return
                    with account_locks[account_id]:
                        account_data["status"] = f"Đã làm {job_counter} job. Nghỉ {i} giây..."
                    time.sleep(1)
                    
        except Exception as e:
            # BẮT MỌI LỖI để không bị đơ
            with account_locks[account_id]:
                account_data["status"] = f"Lỗi vòng lặp: {str(e)[:30]}"
            time.sleep(3)
            continue
    
    # Kết thúc thread
    with account_locks[account_id]:
        account_data["is_running"] = False
        if not account_data["status"].startswith("Dừng"):
            account_data["status"] = "Đã dừng"
    print(f"\033[1;33m[Thread {username}] Đã kết thúc")

# ========== Phần chính ==========
if __name__ == '__main__':
    console = Console()
    
    banner()
    # Lấy IP thật và hiển thị
    current_ip = get_public_ip()
    print(f"\033[1;97m Địa chỉ IP\033[1;32m  : \033[1;32m \033[1;31m \033[1;32m{current_ip}\033[1;31m \033[1;97m")
    print("\033[1;97m═══════════════════════════════════════════════════════════════════")
    print("\033[1;97m \033[1;36m \033[1;32mNhập \033[1;31m1 \033[1;33mđể vào \033[1;34mTool Instagram\033[1;33m")
    print("\033[1;31m\033[1;97m \033[1;36m \033[1;31mNhập 2 Để Xóa Authorization Hiện Tại'")

    while True:
        try:
            choose = input("\033[1;97m \033[1;36m \033[1;32mNhập Lựa Chọn (1 hoặc 2): ")
            choose = int(choose)
            if choose not in (1, 2):
                print("\033[1;31m\nLựa chọn không hợp lệ! Hãy nhập lại.")
                continue
            break
        except:
            print("\033[1;97m \033[1;36m \033[1;31mSai định dạng! Vui lòng nhập số.")

    if choose == 2:
        file_auth = "Authorization.txt"
        if os.path.exists(file_auth):
            try:
                os.remove(file_auth)
                print(f"\033[1;32mĐã xóa {file_auth}!")
            except:
                print(f"\033[1;31mKhông thể xóa {file_auth}!")
        else:
            print(f"\033[1;33mFile {file_auth} không tồn tại!")
        print("\033[1;33mVui lòng nhập lại thông tin!")

    auth_file = "Authorization.txt"
    if not os.path.exists(auth_file):
        try:
            with open(auth_file, 'w') as f:
                f.write('')
        except:
            print(f"\033[1;31mKhông thể tạo file {auth_file}!")
            sys.exit(1)

    author = ""
    try:
        with open(auth_file, 'r') as f:
            author = f.read().strip()
    except:
        print(f"\033[1;31mKhông thể đọc file {auth_file}!")
        sys.exit(1)

    while not author:
        print("\033[1;97m═══════════════════════════════════════════════════════════════════")
        author = input("\033[1;97m \033[1;36m \033[1;32mNhập Authorization: ").strip()
        try:
            with open(auth_file, 'w') as f:
                f.write(author)
        except:
            print(f"\033[1;31mKhông thể ghi vào file {auth_file}!")
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
        'T': 'VFZSak1FMTZZM3BOZWtFd1RtYzlQUT09',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
        "Authorization": author,
        'Content-Type': 'application/json;charset=utf-8'
    }

    print("\033[1;97m═══════════════════════════════════════════════════════════════════")
    print("\033[1;32mĐăng nhập thành công! Đang lấy danh sách account...")
    time.sleep(1)

    chontk_Instagram = chonacc(headers)
    if isinstance(chontk_Instagram, dict) and chontk_Instagram.get('status') == False:
        print(f"\033[1;31m{chontk_Instagram.get('message')}")
        sys.exit(1)
    
    accounts_list = chontk_Instagram.get('data', [])
    if not accounts_list:
        print("\033[1;31mKhông có account nào trên Golike!")
        sys.exit(1)
    
    # Chọn account để chạy và nhập cookie riêng
    accounts_data = chon_accounts_de_chay(accounts_list)
    
    if not accounts_data:
        print("\033[1;31mKhông có account nào được chọn!")
        sys.exit(1)

    # Nhập cấu hình chung
    while True:
        try:
            base_delay = int(input("\033[1;97m \033[1;36m \033[1;32mNhập thời gian làm job (giây): ").strip())
            break
        except:
            print("\033[1;97m \033[1;36m \033[1;31mSai định dạng!!!")

    while True:
        lannhan = input("\033[1;97m \033[1;36m \033[1;32mNhận tiền lần 2 nếu lần 1 fail? (y/n): ").strip().lower()
        if lannhan not in ('y', 'n'):
            print("\033[1;97m \033[1;36m \033[1;31mNhập sai hãy nhập lại!!!")
            continue
        break

    while True:
        try:
            doiacc = int(input("\033[1;97m \033[1;36m \033[1;32mSố job fail để dừng account (nhập 0 để không dừng): ").strip())
            break
        except:
            print("\033[1;97m \033[1;36m \033[1;31mNhập vào 1 số!!!")

    while True:
        print("\033[1;97m═══════════════════════════════════════════════════════════════════")
        print("\033[1;97m \033[1;36m \033[1;32mNhập 1 : \033[1;33mChỉ nhận nhiệm vụ Follow")
        print("\033[1;97m \033[1;36m \033[1;32mNhập 2 : \033[1;33mChỉ nhận nhiệm vụ like")
        print("\033[1;97m \033[1;36m \033[1;32mNhập 12 : \033[1;33mKết hợp cả Like và Follow")
        print("\033[1;97m═══════════════════════════════════════════════════════════════════")
        try:
            chedo = int(input("\033[1;97m \033[1;36m \033[1;34mChọn lựa chọn: ").strip())
            if chedo in (1, 2, 12):
                break
            else:
                print("\033[1;97m \033[1;36m \033[1;31mChỉ được nhập 1, 2 hoặc 12!")
        except:
            print("\033[1;97m \033[1;36m \033[1;31mNhập vào 1 số!!!")

    lam = []
    if chedo == 1:
        lam = ["follow"]
    elif chedo == 2:
        lam = ["like"]
    elif chedo == 12:
        lam = ["follow", "like"]

    # Hiển thị banner cuối cùng trước khi chạy
    banner()
    current_ip = get_public_ip()
    print(f"\033[1;97m Địa chỉ IP\033[1;32m  : \033[1;32m \033[1;31m \033[1;32m{current_ip}\033[1;31m \033[1;97m")
    print(f"\033[1;32m Đã chọn {len(accounts_data)} account để chạy")
    print(f"\033[1;32m Chế độ: {lam}")
    print(f"\033[1;32m Delay: {base_delay} giây")
    print(f"\033[1;32m Giới hạn lỗi: {doiacc} lần")
    print("\033[1;97m═══════════════════════════════════════════════════════════════════")
    
    input("\033[1;33mNhấn Enter để bắt đầu chạy đa luồng...")

    # ========== BẮT ĐẦU CHẠY ĐA LUỒNG VỚI LIVE DASHBOARD ==========
    stop_threads = False
    threads = []
    
    # Khởi tạo và start các thread
    print(f"\033[1;32mĐang khởi động {len(accounts_data)} thread...")
    for account_id, account_data in accounts_data.items():
        t = threading.Thread(target=run_account, args=(account_id, account_data, headers, lam, base_delay, lannhan, doiacc))
        t.daemon = True
        t.start()
        threads.append(t)
        thread_status[account_id] = "running"
        print(f"\033[1;32m  - Đã khởi động thread cho {account_data['username']}")
        time.sleep(0.5)  # Delay nhẹ giữa các lần start thread
    
    print(f"\033[1;32mĐã khởi động xong {len(threads)} thread")
    print("\033[1;97m═══════════════════════════════════════════════════════════════════")
    
    # Hiển thị dashboard live
    try:
        with Live(build_table(), console=console, refresh_per_second=4) as live:
            while any(t.is_alive() for t in threads):
                live.update(build_table())
                time.sleep(0.5)
                
                # Kiểm tra nếu tất cả thread đã dừng
                if not any(t.is_alive() for t in threads):
                    break
    except KeyboardInterrupt:
        print("\n\033[1;33mĐang dừng các thread...")
        stop_threads = True
        
        # Chờ các thread kết thúc
        for t in threads:
            t.join(timeout=5)
        
        # Hiển thị tổng kết
        print("\033[1;32m═══════════════════════════════════════════════════════════════════")
        print("\033[1;33mKẾT QUẢ CHẠY:")
        total_done = sum(acc.get("done", 0) for acc in accounts_data.values())
        total_coin = sum(acc.get("coin", 0) for acc in accounts_data.values())
        for acc_id, acc in accounts_data.items():
            print(f"\033[1;36m{acc['username']}: \033[1;32mDone: {acc.get('done', 0)} \033[1;33mCoin: {acc.get('coin', 0)}")
        print(f"\033[1;33mTổng kết: \033[1;32m{total_done} jobs \033[1;33m{total_coin} coin")
        print("\033[1;32m═══════════════════════════════════════════════════════════════════")
        print("\033[1;32mĐã dừng tất cả thread. Tạm biệt!")
        sys.exit(0)