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
from concurrent.futures import ThreadPoolExecutor, as_completed

# THÊM IMPORT CHO RICH
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import box
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.align import Align
from rich.console import Group

# Disable warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

console = Console()

# ========== CẤU HÌNH LƯU TRỮ ==========
DATA_FOLDER = "data"
os.makedirs(DATA_FOLDER, exist_ok=True)
ACCOUNTS_SAVE_FILE = os.path.join(DATA_FOLDER, "saved_accounts.json")
AUTH_FILE = os.path.join(DATA_FOLDER, "Authorization.json")
GOLIKE_SELECTION_FILE = os.path.join(DATA_FOLDER, "golike_selection.json")

# Lock toàn cục cho đa luồng ổn định
global_lock = threading.RLock()
account_locks = defaultdict(threading.Lock)

# ========== DANH SÁCH LINK DỰ PHÒNG CHO AUTO-ADD ==========
FALLBACK_LINKS = [
    "https://www.instagram.com/evansnguyen.0104",
]

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
    return datetime.now(VIETNAM_TZ)

# ========== Lấy IP thật từ API ==========
def get_public_ip():
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=10, verify=False)
        if response.status_code == 200:
            data = response.json()
            return data.get("ip", "Không xác định")
        return "Không xác định"
    except:
        return "Không xác định"

# ========== HÀM LẤY THÔNG TIN USER TỪ GOLIKE ==========
def get_user_me(auth_token, session=None):
    """Gọi API /users/me để lấy thông tin user từ Golike"""
    if session is None:
        session = requests.Session()
    
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
        response = session.get('https://gateway.golike.net/api/users/me', headers=headers, timeout=30, verify=False)
        
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
    except Exception as e:
        return {
            "success": False,
            "auth": auth_token,
            "message": str(e)
        }

def read_authorizations():
    """Đọc danh sách Authorization từ file"""
    try:
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('tokens', [])
        return []
    except Exception as e:
        console.print(f"[red]Lỗi đọc file auth: {str(e)}[/]")
        return []

def save_authorization(auth):
    """Lưu Authorization mới vào file"""
    try:
        current_auths = read_authorizations()
        if auth not in current_auths:
            current_auths.append(auth)
            with open(AUTH_FILE, 'w', encoding='utf-8') as f:
                json.dump({"tokens": current_auths}, f, ensure_ascii=False, indent=2)
            return True
        return False
    except Exception as e:
        console.print(f"[red]Lỗi lưu auth: {str(e)}[/]")
        return False

def delete_authorization(index):
    """Xóa Authorization theo index"""
    try:
        current_auths = read_authorizations()
        if 0 <= index < len(current_auths):
            removed = current_auths.pop(index)
            with open(AUTH_FILE, 'w', encoding='utf-8') as f:
                json.dump({"tokens": current_auths}, f, ensure_ascii=False, indent=2)
            return True, removed
        return False, None
    except Exception as e:
        console.print(f"[red]Lỗi xóa auth: {str(e)}[/]")
        return False, None

def load_all_accounts():
    """Load tất cả accounts và lấy thông tin từ API /users/me"""
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
    
    return results

def save_golike_selection(selected_indices):
    """Lưu lựa chọn nick Golike vào file"""
    try:
        with open(GOLIKE_SELECTION_FILE, 'w', encoding='utf-8') as f:
            json.dump({"selected_indices": selected_indices}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        console.print(f"[red]Lỗi lưu lựa chọn Golike: {str(e)}[/]")
        return False

def load_golike_selection():
    """Đọc lựa chọn nick Golike từ file"""
    try:
        if os.path.exists(GOLIKE_SELECTION_FILE):
            with open(GOLIKE_SELECTION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("selected_indices", [])
        return []
    except Exception as e:
        return []

# ========== MENU QUẢN LÝ AUTHORIZATION VÀ CHỌN NHIỀU NICK GOLIKE ==========
def display_auth_and_select_accounts():
    """Hiển thị menu quản lý Authorization và cho phép chọn nhiều nick Golike"""
    
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
\033[38;2;255;200;140m[\033[38;2;245;245;245m</>\033[38;2;255;200;140m] \033[38;2;200;160;255mADMIN:\033[38;2;255;235;180m NHƯ ANH ĐÃ THẤY EM   \033[38;2;255;220;160mPhiên Bản: \033[38;2;120;255;220mv3.5
\033[38;2;255;200;140m[\033[38;2;245;245;245m</>\033[38;2;255;200;140m] \033[38;2;200;160;255mNhóm Telegram: \033[38;2;120;255;220mhttps://t.me/se_meo_bao_an
\033[38;2;190;235;210m───────────────────────────────────────────────────────────────────────\033[0m
"""
        print(banner_text)
    
    while True:
        accounts = load_all_accounts()
        
        banner()
        current_ip = get_public_ip()
        print(f"\033[1;97m Địa chỉ IP: \033[1;32m{current_ip}")
        print("\033[1;97m═══════════════════════════════════════════════════════════════════")
        
        if accounts:
            acc_lines = []
            for i, acc in enumerate(accounts):
                idx = f"{i+1:02d}"
                
                if acc.get("success"):
                    username = acc.get("username", "Unknown")
                    coin = acc.get("coin", 0)
                    line = f"[#00ffff][{idx}][/] [#ff99cc]{username}[/] | [#99ff99]{coin} coin[/]"
                else:
                    msg = acc.get('message', 'Lỗi hệ thống')[:30]
                    line = f"[#00ffff][{idx}][/] [red]ERROR:[/] [#ff4444]{msg}[/]"
                
                acc_lines.append(line)
            
            acc_content = "\n".join(acc_lines)
        else:
            acc_content = "[#ffa56b]⚠ Chưa có Authorization nào! Vui lòng nhập token.[/#ffa56b]"
        
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
            '[#cccccc]Lệnh: [#ff9ecb]"t" [#d7d7a8]thêm Authorization, [#ffd4b8]"d 1,2,3" xóa Authorization, [#ff9ecb]"r" [#99ff99]load lại [#ff9ecb]"1,2,3" [#00ffff]chọn nick Golike cách nhau bằng dấu phẩy [#ff6b6b]Enter [#99ff99]để tiếp tục với nick đã chọn[/]',
            border_style="#d7d7a8",
            padding=(0, 1),
            width=80
        )
        console.print(panel_input)
        
        console.print("[#ff9ecb]➤ [#ffffff]Lựa chọn: [/]", end="")
        choice = input().strip().lower()
        
        if choice == '':
            valid_accounts = [acc for acc in accounts if acc.get("success")]
            if valid_accounts:
                saved_selection = load_golike_selection()
                selected_accounts = []
                for idx in saved_selection:
                    if 0 <= idx < len(accounts) and accounts[idx].get("success"):
                        selected_accounts.append(accounts[idx])
                
                if selected_accounts:
                    console.print(f"[green] Đã chọn {len(selected_accounts)} nick Golike từ lưu trữ[/]")
                    time.sleep(1)
                    return selected_accounts
                else:
                    console.print("[red] Chưa chọn nick Golike nào! Vui lòng chọn.[/]")
                    time.sleep(2)
                    continue
            else:
                console.print("[red] Không có tài khoản hợp lệ nào! Vui lòng thêm token mới.[/]")
                time.sleep(2)
                continue
                
        elif choice == 't':
            console.print("\n[#6bb8ff]✈ Nhập Authorization mới: [/]", end="")
            new_auth = input().strip()
            if not new_auth:
                console.print("[red]Authorization không được để trống![/]")
                time.sleep(1.5)
                continue
            
            console.print("[yellow]Đang kiểm tra token...[/]")
            session = requests.Session()
            result = get_user_me(new_auth, session)
            
            if result.get("success"):
                console.print(f"[green]✓ Token hợp lệ! Xin chào: [bold]{result['username']}[/bold] | {result['coin']} coin[/]")
                save_authorization(new_auth)
                console.print("[green]✓ Đã lưu token thành công![/]")
            else:
                console.print(f"[red]✗ Token không hợp lệ! Lỗi: {result.get('message', 'Unknown error')}[/]")
                confirm = input("Token không hợp lệ, bạn vẫn muốn lưu? (y/n): ").strip().lower()
                if confirm == 'y':
                    save_authorization(new_auth)
                    console.print("[yellow]✓ Đã lưu token (dù không hợp lệ)[/]")
            
            time.sleep(2)
            continue
            
        elif choice.startswith('d'):
            parts = choice.split()
            if len(parts) >= 2:
                try:
                    indices = [int(x.strip()) - 1 for x in parts[1].split(',') if x.strip().isdigit()]
                    for idx in sorted(indices, reverse=True):
                        success, removed = delete_authorization(idx)
                        if success:
                            console.print(f"[green]✓ Đã xóa token[/]")
                        else:
                            console.print(f"[red]✗ Không tìm thấy token thứ {idx+1}[/]")
                except Exception as e:
                    console.print(f"[red]Lỗi: {str(e)}[/]")
            else:
                console.print("[yellow]Cú pháp: d 1,2,3 để xóa token theo số thứ tự[/]")
            time.sleep(2)
            continue
            
        elif choice == 'r':
            continue
            
        elif ',' in choice or choice.isdigit():
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(',') if x.strip().isdigit()]
                selected_accounts = []
                for idx in indices:
                    if 0 <= idx < len(accounts):
                        acc = accounts[idx]
                        if acc.get("success"):
                            selected_accounts.append(acc)
                        else:
                            console.print(f"[red]✗ Tài khoản thứ {idx+1} không hợp lệ![/]")
                    else:
                        console.print(f"[red]✗ Số {idx+1} không hợp lệ! (1-{len(accounts)})[/]")
                
                if selected_accounts:
                    console.print(f"[green]✓ Đã chọn {len(selected_accounts)} nick Golike:[/]")
                    for acc in selected_accounts:
                        console.print(f"   - [cyan]{acc['username']}[/] | [yellow]{acc['coin']} coin[/]")
                    
                    save_golike_selection(indices)
                    time.sleep(2)
                    return selected_accounts
                else:
                    console.print("[red]✗ Không có tài khoản hợp lệ nào được chọn![/]")
                    time.sleep(2)
                    continue
            except Exception as e:
                console.print(f"[red]Lỗi: {str(e)}[/]")
                time.sleep(2)
                continue
            
        else:
            console.print(f"[red]Lựa chọn không hợp lệ![/]")
            time.sleep(1.5)
            continue

# ========== HÀM LẤY USERNAME TỪ COOKIE ==========
def get_username_from_cookie(cookie_str):
    """Lấy username từ cookie Instagram bằng requests"""
    try:
        cookies = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if not item:
                continue
            if '=' in item:
                key, val = item.split('=', 1)
                cookies[key] = val
        
        session = requests.Session()
        session.cookies.update(cookies)
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        
        response = session.get('https://www.instagram.com/', timeout=15, verify=False)
        
        match = re.search(r'"username":"([^"]+)"', response.text)
        if match:
            return match.group(1)
        
        match = re.search(r'"logged_in_user"\s*:\s*\{[^}]*"username"\s*:\s*"([^"]+)"', response.text)
        if match:
            return match.group(1)
        
        match = re.search(r'https://www\.instagram\.com/([^/"]+)/', response.text)
        if match:
            return match.group(1)
        
        return None
    except Exception:
        return None

# ========== HÀM TỰ ĐỘNG ADD GOLIKE ==========
def get_target_uid(link_target, cookie_str):
    """Hàm lấy UID từ một link cụ thể"""
    headers_ig = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'cookie': cookie_str,
    }
    try:
        res = requests.get(link_target, headers=headers_ig, timeout=15, verify=False)
        if res.status_code != 200:
            return None
        
        patterns = [
            r'"target_id":"(\d+)"',
            r'"profile_id":"(\d+)"',
            r'"id":"(\d+)","is_verified"',
            r'"pk":"(\d+)"',
            r'"user_id":"(\d+)"',
            r'"owner":{"id":"(\d+)"}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, res.text)
            if match:
                return match.group(1)
        return None
    except:
        return None

def perform_follow(target_uid, cookie_str, username):
    """Thực hiện follow một UID"""
    try:
        csrf = cookie_str.split("csrftoken=")[1].split(';')[0] if "csrftoken=" in cookie_str else ""
        
        headers_follow = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.instagram.com',
            'referer': 'https://www.instagram.com/',
            'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'x-csrftoken': csrf,
            'x-ig-app-id': '936619743392459',
            'x-requested-with': 'XMLHttpRequest',
            'cookie': cookie_str,
        }
        data_follow = {
            'container_module': 'single_post',
            'nav_chain': 'PolarisExploreRoot:exploreLandingPage:3:topnav-link,PolarisPostModal:postPage:4:modalLink',
            'user_id': target_uid,
            'jazoest': '22588',
        }
        res_follow = requests.post(
            f'https://www.instagram.com/api/v1/friendships/create/{target_uid}/', 
            headers=headers_follow, 
            data=data_follow, 
            timeout=15, 
            verify=False
        )
        
        if res_follow.status_code == 200 and 'friendship_status' in res_follow.text:
            return True, "Follow thành công"
        else:
            return False, f"Follow thất bại (Response: {res_follow.status_code})"
    except Exception as e:
        return False, f"Lỗi follow: {str(e)}"

def call_verify_api(username, headers_golike, link_used=None):
    """Gọi API verify-account lên Golike"""
    json_data = {'object_id': username}
    try:
        res = requests.post('https://gateway.golike.net/api/instagram-account/verify-account', 
                        headers=headers_golike, json=json_data, timeout=15, verify=False)
        
        try:
            resp_json = res.json()
        except:
            resp_json = {}
        
        if res.status_code == 200 and (resp_json.get('status') == 200 or resp_json.get('success') == True):
            new_acc_data = resp_json.get('data', {})
            return True, new_acc_data.get('id', '-'), resp_json
        else:
            error_msg = resp_json.get('message') or resp_json.get('msg') or f"HTTP {res.status_code}"
            return False, None, {"message": error_msg}
    except Exception as e:
        return False, None, {"message": str(e)}

def auto_add_golike(username, cookie_str, headers_golike, golike_username):
    """Hàm tự động thêm Golike sử dụng API V1 Follow"""
    console.print(f"[#ffa56b]➤ Account {username} chưa có trên Golike. Đang tiến hành thêm tự động vào nick [cyan]{golike_username}[/cyan]...[/#ffa56b]")
    
    # Lấy link verify từ API Golike
    console.print(f"[#6bb8ff]➤ Đang lấy link Verify từ API Golike...[/#6bb8ff]")
    api_link = None
    try:
        res_link = requests.get('https://gateway.golike.net/api/instagram-account', headers=headers_golike, timeout=15, verify=False)
        
        if res_link.status_code == 200:
            api_link = res_link.json().get('link_verify_follow', '')
            if api_link:
                console.print(f"[#6bffb8]✓ Lấy thành công link verify: {api_link}[/#6bffb8]")
            else:
                console.print(f"[#ffa56b]⚠ API Golike không trả về link_verify_follow[/#ffa56b]")
        else:
            console.print(f"[#ffa56b]⚠ API trả về status {res_link.status_code}[/#ffa56b]")
    except Exception as e:
        console.print(f"[#ffa56b]⚠ Lỗi lấy link verify: {str(e)}[/#ffa56b]")
    
    links_to_try = []
    if api_link:
        links_to_try.append(api_link)
    links_to_try.extend(FALLBACK_LINKS)
    links_to_try = list(dict.fromkeys(links_to_try))
    
    console.print(f"[#6bb8ff]➤ Sẽ thử {len(links_to_try)} link (API + dự phòng)[/#6bb8ff]")
    
    for idx, link_target in enumerate(links_to_try, 1):
        console.print(f"\n[#ffa56b]--- Thử link {idx}/{len(links_to_try)}: {link_target[:50]}... ---[/#ffa56b]")
        
        target_uid = get_target_uid(link_target, cookie_str)
        
        if not target_uid:
            console.print(f"[#ff6b6b]✗ Không lấy được UID từ link này![/#ff6b6b]")
            continue
        
        console.print(f"[#6bffb8]✓ Lấy UID thành công: {target_uid}[/#6bffb8]")
        
        console.print(f"[#6bb8ff]➤ Đang follow ID {target_uid}...[/#6bb8ff]")
        follow_success, follow_msg = perform_follow(target_uid, cookie_str, username)
        
        if not follow_success:
            console.print(f"[#ff6b6b]✗ {follow_msg}[/#ff6b6b]")
            continue
        
        console.print(f"[#6bffb8]✓ {follow_msg}[/#6bffb8]")
        console.print(f"[#6bb8ff]➤ Đợi 3 giây để Instagram ghi nhận Follow...[/#6bb8ff]")
        time.sleep(3)
        
        console.print(f"[#6bb8ff]➤ Đang gửi yêu cầu Verify lên Golike...[/#6bb8ff]")
        verify_success, acc_id, resp_data = call_verify_api(username, headers_golike, link_target)
        
        if verify_success:
            console.print(f"[bold #6bffb8]✓ Thêm và Match thành công {username} vào Golike! (ID: {acc_id})[/bold #6bffb8]")
            return True, acc_id
        else:
            error_msg = resp_data.get('message', 'Lỗi không xác định')
            console.print(f"[#ff6b6b]✗ Verify thất bại: {error_msg}[/#ff6b6b]")
            
            if "chưa follow" in error_msg.lower() or "not follow" in error_msg.lower():
                console.print(f"[#ffa56b]⚠ Link này không hợp lệ, thử link tiếp theo...[/#ffa56b]")
                continue
            else:
                console.print(f"[#ff6b6b]✗ Lỗi verify không thể retry, dừng lại.[/#ff6b6b]")
                return False, "-"
    
    console.print(f"[#ff6b6b]✗ Đã thử {len(links_to_try)} link nhưng đều thất bại![/#ff6b6b]")
    return False, "-"

# ========== HÀM HIỂN THỊ DANH SÁCH GOLIKE ĐỂ CHỌN ==========
def display_golike_list_for_selection(golike_accounts):
    """Hiển thị danh sách Golike để người dùng chọn"""
    os.system('clear' if os.name == 'posix' else 'cls')
    
    acc_lines = []
    for i, acc in enumerate(golike_accounts):
        idx = f"{i+1:02d}"
        if acc.get("success"):
            username = acc.get("username", "Unknown")
            coin = acc.get("coin", 0)
            line = f"[#00ffff][{idx}][/] [#ff99cc]{username}[/] | [#99ff99]{coin} coin[/]"
        else:
            msg = acc.get('message', 'Lỗi hệ thống')[:30]
            line = f"[#00ffff][{idx}][/] [red]ERROR:[/] [#ff4444]{msg}[/]"
        acc_lines.append(line)
    
    acc_content = "\n".join(acc_lines)
    
    panel_acc = Panel(
        acc_content,
        title="[bold #d7d7a8]CHỌN NICK GOLIKE ĐỂ LIÊN KẾT[/]",
        title_align="center",
        border_style="#d7d7a8",
        padding=(0, 1),
        width=60
    )
    console.print(panel_acc)
    
    console.print("\n[#ff9ecb]➤ [#ffffff]Nhập số thứ tự nick Golike muốn liên kết: [/]", end="")
    choice = input().strip()
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(golike_accounts) and golike_accounts[idx].get("success"):
            return golike_accounts[idx]
        else:
            console.print("[red]✗ Lựa chọn không hợp lệ![/]")
            return None
    except:
        console.print("[red]✗ Vui lòng nhập số![/]")
        return None

# ========== HÀM LƯU/ TẢI ACCOUNTS ==========
def save_accounts_to_file(ui_accounts):
    """Lưu danh sách accounts đã nhập cookie vào file JSON"""
    try:
        save_data = []
        for acc in ui_accounts:
            save_data.append({
                "username": acc.get("username"),
                "account_id": acc.get("account_id"),
                "cookie": acc.get("cookie"),
                "golike_username": acc.get("golike_username"),
                "status": acc.get("status"),
                "is_valid": acc.get("is_valid", False),
                "saved_at": get_current_time().strftime("%Y-%m-%d %H:%M:%S")
            })
        
        with open(ACCOUNTS_SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        console.print(f"[#ff6b6b]Lỗi lưu accounts: {str(e)}[/#ff6b6b]")
        return False

def load_accounts_from_file():
    """Tải danh sách accounts từ file JSON"""
    try:
        if os.path.exists(ACCOUNTS_SAVE_FILE):
            with open(ACCOUNTS_SAVE_FILE, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            ui_accounts = []
            for acc in save_data:
                ui_accounts.append({
                    "username": acc.get("username"),
                    "account_id": acc.get("account_id"),
                    "cookie": acc.get("cookie"),
                    "golike_username": acc.get("golike_username"),
                    "status": acc.get("status", "[#6bffb8]Đã lưu[/#6bffb8]"),
                    "is_valid": acc.get("is_valid", False),
                    "saved_at": acc.get("saved_at", "")
                })
            return ui_accounts
        return []
    except Exception as e:
        console.print(f"[#ff6b6b]Lỗi tải accounts: {str(e)}[/#ff6b6b]")
        return []

# ========== MENU CẤU HÌNH DELAY VỚI RICH ==========
def input_number(text, default):
    while True:
        try:
            value = input(text).strip()
            if value == "":
                return default
            return int(value)
        except:
            console.print("[bold #ff6b6b]Sai định dạng! Nhập số.[/]")

def setup_delay_config():
    """Cấu hình delay với giao diện Rich"""
    delay_like = [5, 10]
    delay_follow = [5, 15]
    delay_job = [3, 7]
    delay_job_error = 10
    delay_done = 5

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

        table.add_row(*row("Delay Like", delay_like, "#ff6b6b", "#ffb8b8", "#ff8a8a"))
        table.add_row(*row("Delay Follow", delay_follow, "#6bff6b", "#b8ffb8", "#8aff8a"))
        table.add_row(*row("Delay Get Jobs", delay_job, "#ffa56b", "#ffd4b8", "#ffbc8a"))

        table.add_row(
            "[bold #ff6b6b]Delay Job Lỗi[/]", 
            f"[bold #ffffff]{delay_job_error}[/]", 
            "[#00ffff]s[/]"
        )

        table.add_row(
            "[#ffd54f]Delay Hoàn Thành[/]",
            f"[bold #ffffff]{delay_done}[/]",
            "[#00ffff]s[/]"
        ) 

        console.clear()
        console.print(table)

        console.print("\n[#ff9ecb]➤ [#ffffff]Dùng lại config?[/] [#00ffff](Y/N)[/] [#ffffff]: ", end="")
        choice = input().strip().lower()

        if choice != "n":
            console.print("[#6bffb8] Giữ config hiện tại[/]")
            return {
                "like": delay_like,
                "follow": delay_follow,
                "job": delay_job,
                "error": delay_job_error,
                "done": delay_done
            }

        console.print("\n[bold #ffd54f] Nhập lại cấu hình (Nhấn Enter để giữ giá trị cũ)[/]\n")

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

        delay_job_error = input_number(f"Delay Job Lỗi ({delay_job_error}): ", delay_job_error)
        delay_done = input_number(f"Delay Hoàn Thành ({delay_done}): ", delay_done)

# ========== MENU CHỌN JOB VỚI UI TABLET ==========
JOBS = [
    {"id": "1", "name": "Follow", "value": "follow", "color": "#ffd54f"},
    {"id": "2", "name": "Like", "value": "like", "color": "#ff9ecb"},
]

def render_tablet(selections, current_idx):
    """Vẽ khung Tablet (Bảng bo tròn góc)"""
    table = Table(
        box=box.ROUNDED, 
        border_style="#d7b8ff", 
        header_style="bold #ffffff",
        width=45
    )
    
    table.add_column("ID", justify="center", style="bold")
    table.add_column("Nhiệm Vụ")
    table.add_column("Trạng Thái", justify="center")

    for i, job in enumerate(JOBS):
        color = job["color"]
        
        if selections[i] == 'y':
            status = "[bold #6bffb8] ✓ BẬT[/]"
        elif selections[i] == 'n':
            status = "[bold #ff6b6b] ✗ TẮT[/]"
        elif i == current_idx:
            status = "[blink bold #ffff00] ? Đang chọn...[/]"
        else:
            status = "[dim]...[/]"

        table.add_row(
            f"[{color}]{job['id']}[/]",
            f"[{color}]{job['name']}[/]",
            status
        )
        
    return table

def menu_jobs():
    """Menu chọn nhiệm vụ với giao diện Tablet"""
    while True:
        selections = [None] * len(JOBS)
        
        for i, job in enumerate(JOBS):
            while True:
                console.clear()
                console.print(render_tablet(selections, i))
                
                ans = console.input(f"\n[#ff9ecb]➤ [#ffffff]Bật nhiệm vụ {job['name']}? (y/n) (Mặc định: y)[/]: ").strip().lower()
                
                if ans in ['y', 'yes', '']:
                    selections[i] = 'y'
                    break
                elif ans in ['n', 'no']:
                    selections[i] = 'n'
                    break

        console.clear()
        console.print(render_tablet(selections, -1))
        
        lam = [JOBS[i]["value"] for i in range(len(JOBS)) if selections[i] == 'y']
        
        if lam:
            selected_names = [JOBS[i]["name"] for i in range(len(JOBS)) if selections[i] == 'y']
            console.print(f"[#ffffff]Đã cấu hình chạy:[/] [bold #00ffff]{', '.join(selected_names)}[/]")
            return lam
        else:
            console.print("[bold #ff6b6b]➤ Lỗi: Bạn phải chọn ít nhất 1 nhiệm vụ để chạy![/]")
            console.input("[#00ffff]Nhấn Enter để chọn lại...[/]")

# ========== CHỌN ACCOUNT VỚI GIAO DIỆN RICH ==========
def chon_accounts_de_chay(selected_golike_accounts):
    """Giao diện Rich quản lý và tự động map/add cookie với account Golike"""
    ui_accounts = load_accounts_from_file()
    selected = []

    def render():
        table = Table(expand=True, box=box.HEAVY, show_lines=True, border_style="#caffbf")
        table.add_column("[#6bffb8]STT[/]", justify="center", width=4)
        table.add_column("[#ffffb8]USERNAME[/]", justify="center", style="#6bb8ff", width=20)
        table.add_column("[#ffd54f]GOLIKE ID[/]", justify="center", width=10)
        table.add_column("[#ffa56b]NICK GOLIKE[/]", justify="center", width=15)
        table.add_column("[#ffa56b]COOKIE[/]", justify="center", width=25)
        table.add_column("[#6bffb8]STATUS[/]", justify="center", width=20)
    
        for i, acc in enumerate(ui_accounts, 1):
            style = "bold #ff6b6b #ffd54f #ffffb8 #6bffb8 #6bb8ff" if (i-1) in selected else ""
            cookie_short = (acc.get("cookie", "")[:25] + "...") if len(acc.get("cookie", "")) > 25 else acc.get("cookie", "")
            golike_name = acc.get("golike_username", "-")
        
            table.add_row(
                str(i),
                f"[#6bb8ff]{acc.get('username','Unknown')}[/]",
                f"[#ffd54f]{str(acc.get('account_id','-'))}[/]",
                f"[#ffa56b]{golike_name}[/]",
                f"[#ffa56b]{cookie_short if cookie_short else 'Chưa nhập'}[/]",
                f"[#6bffb8]{acc.get('status','')}[/]",
                style=style
            )

        total_accounts = len(ui_accounts)
        valid_accounts = sum(1 for acc in ui_accounts if acc.get("is_valid", False))
        title = Align.center(Text.from_markup("[#6bb8ff]INSTAGRAM[/] [#ff6b6b]ACCOUNT[/]"))
        commands = Text.from_markup("\n [#6bb8ff]Lệnh: add = thêm cookie [/][#ff6b6b]|[/][#ffd54f] save = lưu [/][#6bffb8]|[/][#6bb8ff] load = tải [/][#ffd54f]|[/][#ff9ecb] 1,2,3 = chọn acc [/][#6bb8ff]|[/][#ff6b6b] -1,2 = xóa acc [/][#6bffb8]|[/][#ffd54f] run = Bắt đầu\n[/]")

        return Group(title, table, commands)

    def parse_ids(cmd):
        return [int(x.strip()) - 1 for x in cmd.split(",") if x.strip().isdigit()]

    def add_multi_cookie():
        """THÊM COOKIE - LUỒNG MỚI: THÊM XONG QUAY LẠI NGAY ĐỂ THÊM COOKIE MỚI"""
        console.print("\n[#6bffb8] Dán cookie từng dòng (gõ 'done' để dừng):[/]")
        console.print("[#6bb8ff] Mỗi cookie sẽ được kiểm tra và hiển thị tên username ngay sau khi nhập[/]\n")
        
        while True:
            cookie_input = input(" Nhập Cookie: ").strip()
            if cookie_input.lower() == "done":
                break
            if not cookie_input:
                continue

            with console.status("[bold #ffa56b] Đang kiểm tra cookie...[/bold #ffa56b]", spinner="dots"):
                time.sleep(0.5)
                username = get_username_from_cookie(cookie_input)

            if not username:
                console.print(f"[#ff6b6b] THẤT BẠI![/#ff6b6b] Cookie không hợp lệ hoặc đã chết!")
                console.print(f"[dim]   → Không thể lấy được username từ cookie này[/dim]")
                console.print(f"[dim]   → Đã bỏ qua, không lưu vào danh sách[/dim]\n")
                continue
                
            console.print(f"[#6bffb8] THÀNH CÔNG![/#6bffb8] Đã lấy được username: [bold #6bb8ff]{username}[/bold #6bb8ff]")
            
            if any(a.get("username") == username for a in ui_accounts):
                console.print(f"[#ff6b6b]  Cookie cho {username} đã tồn tại trong danh sách![/#ff6b6b]")
                console.print(f"[dim]   → Không thêm trùng lặp[/dim]\n")
                continue
            
            console.print(f"\n[#ffa56b] Chọn nick Golike để liên kết với account [cyan]{username}[/cyan][/#ffa56b]")
            
            valid_golike = [acc for acc in selected_golike_accounts if acc.get("success")]
            if not valid_golike:
                console.print("[#ff6b6b] Không có nick Golike hợp lệ nào để chọn![/#ff6b6b]")
                console.print("[dim]   → Vui lòng thêm Authorization Golike trước[/dim]\n")
                continue
            
            selected_golike = display_golike_list_for_selection(valid_golike)
            if not selected_golike:
                console.print("[#ff6b6b] Lựa chọn không hợp lệ! Bỏ qua cookie này.[/#ff6b6b]\n")
                continue
            
            headers_golike = {
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
                "Authorization": selected_golike['auth'],
                'Content-Type': 'application/json;charset=utf-8'
            }
            
            console.print("[#6bb8ff] Đang kiểm tra account trên Golike...[/#6bb8ff]")
            chontk_result = chonacc(headers_golike)
            
            account_map = {}
            if chontk_result.get('status') == True:
                accounts_list = chontk_result.get('data', [])
                account_map = {acc['instagram_username'].lower(): acc for acc in accounts_list}
            
            is_valid = False
            account_id = "-"
            status = ""
            golike_username = selected_golike['username']
            
            if username.lower() not in account_map:
                console.print(f"[#ffa56b]  Account {username} chưa có trên Golike![/#ffa56b]")
                with console.status(f"[bold #ffa56b] Đang tự động thêm {username} vào Golike...[/bold #ffa56b]", spinner="dots"):
                    success, acc_id = auto_add_golike(username, cookie_input, headers_golike, golike_username)
                
                if success:
                    console.print(f"[#6bffb8] Đã thêm thành công {username} vào Golike! (ID: {acc_id})[/#6bffb8]")
                    status = "[#6bffb8] Hợp lệ (Sẵn sàng)[/#6bffb8]"
                    account_id = acc_id
                    is_valid = True
                else:
                    console.print(f"[#ff6b6b] Thêm {username} vào Golike thất bại![/#ff6b6b]")
                    console.print(f"[dim]   → Cookie không được thêm vào danh sách[/dim]\n")
                    continue
            else:
                console.print(f"[#6bffb8] Account {username} đã tồn tại trên Golike![/#6bffb8]")
                status = "[#6bffb8] Hợp lệ (Sẵn sàng)[/#6bffb8]"
                account_id = account_map[username.lower()]['id']
                is_valid = True
            
            if is_valid:
                ui_accounts.append({
                    "username": username,
                    "account_id": account_id,
                    "cookie": cookie_input,
                    "golike_username": golike_username,
                    "status": status,
                    "is_valid": True,
                    "saved_at": get_current_time().strftime("%Y-%m-%d %H:%M:%S")
                })
                
                console.print(f"[bold #6bffb8] Đã thêm {username} vào danh sách thành công! (Liên kết với Golike: {golike_username})[/bold #6bffb8]")
                
                save_accounts_to_file(ui_accounts)
                console.print(f"[dim]   → Đã tự động lưu vào file[/dim]")
            else:
                console.print(f"[bold #ff6b6b] Thêm thất bại, không lưu vào danh sách[/bold #ff6b6b]")
            
            console.print(f"[#6bb8ff]{'─' * 60}[/#6bb8ff]\n")

    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        console.print(render())
        cmd = input("\033[38;2;107;255;184mNhập lệnh (): \033[0m").strip().lower()

        if cmd == "run":
            if not selected:
                console.print("[#ff6b6b] Bạn chưa chọn account nào để chạy! Hãy nhập số thứ tự (VD: 1,2)[/#ff6b6b]")
                time.sleep(2)
                continue
            
            invalid_selected = [ui_accounts[i]["username"] for i in selected if not ui_accounts[i].get("is_valid", False)]
            if invalid_selected:
                console.print(f"[#ff6b6b] Các account sau không hợp lệ (lỗi cookie/không có trên Golike): {', '.join(invalid_selected)}[/#ff6b6b]")
                console.print("[#ffa56b] Vui lòng bỏ chọn hoặc nhập lại cookie![/#ffa56b]")
                time.sleep(3)
                continue
            break

        if cmd == "add":
            add_multi_cookie()
            continue

        if cmd == "save":
            if save_accounts_to_file(ui_accounts):
                console.print("[#6bffb8] Đã lưu danh sách accounts thành công![/#6bffb8]")
            else:
                console.print("[#ff6b6b] Lưu thất bại![/#ff6b6b]")
            time.sleep(1.5)
            continue

        if cmd == "load":
            loaded_accounts = load_accounts_from_file()
            if loaded_accounts:
                ui_accounts = loaded_accounts
                selected = []
                console.print("[#6bffb8] Đã tải danh sách accounts từ file![/#6bffb8]")
            else:
                console.print("[#ffa56b] Không có file lưu trữ hoặc file rỗng![/#ffa56b]")
            time.sleep(1.5)
            continue

        if cmd.startswith("-"):
            ids = parse_ids(cmd[1:])
            ids = sorted(set(ids), reverse=True)
            for idx in ids:
                if 0 <= idx < len(ui_accounts):
                    removed_username = ui_accounts[idx].get("username", "Unknown")
                    ui_accounts.pop(idx)
                    console.print(f"[#ffa56b]️ Đã xóa account: {removed_username}[/#ffa56b]")
            selected = []
            save_accounts_to_file(ui_accounts)
            time.sleep(1)
            continue

        try:
            ids = parse_ids(cmd)
            if ids:
                selected = [i for i in ids if 0 <= i < len(ui_accounts)]
                if selected:
                    selected_names = [ui_accounts[i].get("username", "Unknown") for i in selected]
                    console.print(f"[#6bffb8] Đã chọn {len(selected)} account: {', '.join(selected_names)}[/#6bffb8]")
                    time.sleep(1)
        except:
            pass

    selected_accounts = {}
    for idx in selected:
        acc_data = ui_accounts[idx]
        acc_id = acc_data['account_id']
        
        golike_auth = None
        golike_username = acc_data.get('golike_username')
        for golike_acc in selected_golike_accounts:
            if golike_acc.get('username') == golike_username:
                golike_auth = golike_acc.get('auth')
                break
        
        selected_accounts[acc_id] = {
            "id": acc_id,
            "username": acc_data['username'],
            "cookie": acc_data['cookie'],
            "golike_username": golike_username,
            "golike_auth": golike_auth,
            "selected": True,
            "done": 0,
            "skip": 0,
            "follow": 0,
            "like": 0,
            "coin": 0,
            "status": "Đang chờ...",
            "api_message": "",
            "session_errors": 0,
            "last_error_time": 0,
            "error_counts": {
                'follow': 0, 'like': 0, 'checkpoint': 0, 'rate_limit': 0, 'other': 0
            },
            "is_running": True,
            "thread_id": None,
            "job_counter": 0,
            "rate_limit_until": 0
        }

    return selected_accounts

# ========== HÀM GỌI API GOLIKE ==========
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

# ========== InstagramBot Class - Giữ nguyên GraphQL ==========
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
                match = re.search(r'\["LSD",\[\],\{"token":"([^"]+)"', response.text)
                if match:
                    self.lsd = match.group(1)
                    return
                
                match = re.search(r'"LSD","token":"([^"]+)"', response.text)
                if match:
                    self.lsd = match.group(1)
                    return
                
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

# ========== Các hàm kiểm tra lỗi ==========
MAX_SESSION_ERRORS = 5
ERROR_RESET_TIME = 1800
MAX_RETRY_COUNT = 2
RATE_LIMIT_BACKOFF = [5, 15, 30]

def increment_error(account_data, error_type='other'):
    if "error_counts" not in account_data:
        account_data["error_counts"] = {'follow': 0, 'like': 0, 'checkpoint': 0, 'rate_limit': 0, 'other': 0}
    account_data["error_counts"][error_type] = account_data["error_counts"].get(error_type, 0) + 1
    account_data["session_errors"] = account_data.get("session_errors", 0) + 1
    account_data["last_error_time"] = time.time()

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

def update_account_status(account_data, message, level="info"):
    with account_locks.get(account_data.get("id", "unknown"), threading.RLock()):
        if len(message) > 50:
            message = message[:47] + "..."
        account_data["status"] = message
        account_data["api_message"] = message[:45]

# ========== Các hàm xử lý job ==========
def handle_follow_job(cookies, object_id, account_id, account_data):
    global stop_threads

    if stop_threads:
        return {"status": False, "message": "Thread stopped"}

    update_account_status(account_data, f"Đang follow ID: {object_id}")
    
    retry_count = 0
    max_retries = MAX_RETRY_COUNT

    while retry_count < max_retries and not stop_threads:
        try:
            bot = InstagramBot(cookies)
            result = bot.follow(object_id)

            if result['status']:
                update_account_status(account_data, f"Follow thành công")
                return {"status": True, "message": result.get('message', 'Follow thành công')}
            else:
                error_msg = result.get('message', 'Lỗi không xác định')
                update_account_status(account_data, f"Follow thất bại: {error_msg[:30]}", "warning")

                if kiem_tra_checkpoint(error_msg):
                    increment_error(account_data, 'checkpoint')
                    return {"status": False, "message": error_msg, "fatal": True}

                if kiem_tra_rate_limit(error_msg, 429 if 'rate' in error_msg.lower() else 200):
                    increment_error(account_data, 'rate_limit')
                    wait_time = RATE_LIMIT_BACKOFF[min(retry_count, len(RATE_LIMIT_BACKOFF)-1)]
                    for i in range(wait_time, 0, -1):
                        if stop_threads:
                            return {"status": False, "message": "Thread stopped"}
                        update_account_status(account_data, f"Rate limit - Nghỉ {i}s")
                        time.sleep(1)
                    retry_count += 1
                    continue

                if kiem_tra_cookie_die(error_msg, 403 if 'forbidden' in error_msg.lower() else 200):
                    increment_error(account_data, 'other')
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
                    update_account_status(account_data, f"Lỗi: {str(e)[:20]} - Thử lại sau {i}s")
                    time.sleep(1)
            else:
                error_msg = f"exception: {str(e)[:50]}"
                update_account_status(account_data, error_msg, "error")
                return {"status": False, "message": error_msg}

    increment_error(account_data, 'follow')
    update_account_status(account_data, "Follow thất bại sau nhiều lần thử", "error")
    return {"status": False, "message": "Follow thất bại sau nhiều lần thử"}

def handle_like_job(cookies, idlike, link, account_id, account_data):
    global stop_threads

    if stop_threads:
        return {"status": False, "message": "Thread stopped"}

    update_account_status(account_data, f"Đang like bài post...")
    
    retry_count = 0
    max_retries = MAX_RETRY_COUNT

    while retry_count < max_retries and not stop_threads:
        try:
            bot = InstagramBot(cookies)
            result = bot.like(idlike)

            if result['status']:
                update_account_status(account_data, f"Like thành công")
                return {"status": True, "message": result.get('message', 'Like thành công')}
            else:
                error_msg = result.get('message', 'Lỗi không xác định')
                update_account_status(account_data, f"Like thất bại: {error_msg[:30]}", "warning")

                if kiem_tra_checkpoint(error_msg):
                    increment_error(account_data, 'checkpoint')
                    return {"status": False, "message": error_msg, "fatal": True}

                if kiem_tra_rate_limit(error_msg, 429 if 'rate' in error_msg.lower() else 200):
                    increment_error(account_data, 'rate_limit')
                    wait_time = RATE_LIMIT_BACKOFF[min(retry_count, len(RATE_LIMIT_BACKOFF)-1)]
                    for i in range(wait_time, 0, -1):
                        if stop_threads:
                            return {"status": False, "message": "Thread stopped"}
                        update_account_status(account_data, f"Rate limit - Nghỉ {i}s")
                        time.sleep(1)
                    retry_count += 1
                    continue

                if kiem_tra_cookie_die(error_msg, 403 if 'forbidden' in error_msg.lower() else 200):
                    increment_error(account_data, 'other')
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
                    update_account_status(account_data, f"Lỗi: {str(e)[:20]} - Thử lại sau {i}s")
                    time.sleep(1)
            else:
                error_msg = f"exception: {str(e)[:50]}"
                update_account_status(account_data, error_msg, "error")
                return {"status": False, "message": error_msg}

    increment_error(account_data, 'like')
    update_account_status(account_data, "Like thất bại sau nhiều lần thử", "error")
    return {"status": False, "message": "Like thất bại sau nhiều lần thử"}

def countdown_delay(account_id, account_data, total_seconds, message="Đợi"):
    global stop_threads
    
    if total_seconds > 10:
        variation = random.uniform(-2, 2)
        total_seconds = max(3, total_seconds + variation)
    
    account_data["api_message"] = f" {message} {int(total_seconds)}s"
    
    for i in range(int(total_seconds), 0, -1):
        if stop_threads:
            return
        account_data["api_message"] = f" {message} {i}s"
        update_account_status(account_data, f"{message} {i}s")
        time.sleep(1)
    
    account_data["api_message"] = ""

# ========== Biến toàn cục ==========
accounts_data = {}
stop_threads = False

# ========== Hàm chạy cho mỗi account trong thread riêng ==========
def run_account(account_id, account_data, headers, lam, delay_config, lannhan, doiacc, job_nghi, thoi_gian_nghi):
    global stop_threads
    
    account_data["thread_id"] = threading.current_thread().ident
    cookies = account_data["cookie"]
    username = account_data["username"]
    checkdoiacc = 0
    job_counter = 0
    
    update_account_status(account_data, "Bắt đầu chạy...")
    account_data["is_running"] = True
    
    delay_job_range = delay_config.get("job", [3, 7])
    delay_done = delay_config.get("done", 5)
    delay_error = delay_config.get("error", 10)
    
    print(f"\033[1;32m[Thread {username}] Đã khởi động")
    
    while not stop_threads and account_data.get("is_running", True):
        try:
            if account_data.get("rate_limit_until", 0) > time.time():
                remaining = int(account_data["rate_limit_until"] - time.time())
                if remaining > 0:
                    account_data["api_message"] = f" Rate limit 429, nghỉ {remaining}s"
                    time.sleep(min(remaining, 5))
                    continue
            
            account_data["api_message"] = " Đang tìm job..."
            
            if checkdoiacc >= doiacc and doiacc > 0:
                update_account_status(account_data, f"Đạt giới hạn lỗi ({doiacc})", "error")
                account_data["is_running"] = False
                break

            update_account_status(account_data, "Đang lấy job...")
            nhanjob = nhannv(account_id, headers)
            
            if isinstance(nhanjob, dict):
                if nhanjob.get('status') == 200:
                    data = nhanjob.get('data', {})
                    
                    if not isinstance(data, dict):
                        update_account_status(account_data, "Dữ liệu job không hợp lệ", "warning")
                        account_data["api_message"] = " Dữ liệu job lỗi"
                        time.sleep(random.uniform(4, 7))
                        continue
                        
                    ads_id = data.get('id')
                    link = data.get('link')
                    object_id = data.get('object_id')
                    loai = data.get('type')
                    object_data = data.get('object_data', {})
                    
                    update_account_status(account_data, f"Nhận job: {loai}")
                    
                    if not isinstance(object_data, dict):
                        object_data = {}
                        
                    if not object_id or not loai:
                        update_account_status(account_data, "Thiếu thông tin job", "warning")
                        account_data["api_message"] = " Thiếu thông tin job"
                        time.sleep(random.uniform(1.5, 3))
                        continue
                else:
                    msg = nhanjob.get('message', 'Không có job')
                    update_account_status(account_data, f"API: {msg}")
                    account_data["api_message"] = f" {msg[:45]}"
                    wait_time = random.randint(delay_job_range[0], delay_job_range[1])
                    countdown_delay(account_id, account_data, wait_time, "Chờ job")
                    continue
            else:
                time.sleep(random.uniform(4, 7))
                continue

            if loai not in lam:
                update_account_status(account_data, f"Bỏ qua {loai} (không trong cấu hình)")
                account_data["api_message"] = f" Bỏ qua {loai}"
                try:
                    baoloi(ads_id, object_id, account_id, loai, headers)
                    with account_locks[account_id]:
                        account_data["skip"] += 1
                    time.sleep(random.uniform(0.8, 1.5))
                    continue
                except:
                    time.sleep(random.uniform(0.8, 1.5))
                    continue

            success = {"status": False, "message": "Không xác định"}
            
            if loai == "follow":
                update_account_status(account_data, f"Xử lý follow...")
                account_data["api_message"] = f" Đang xử lý follow job"
                success = handle_follow_job(cookies, object_id, account_id, account_data)
                
            elif loai == "like":
                media_id = data.get('object_data', {}).get('pk')
                if not media_id:
                    update_account_status(account_data, "Lỗi: media_id rỗng", "error")
                    time.sleep(2)
                    continue
                success = handle_like_job(cookies, media_id, link, account_id, account_data)

            if success.get('retry') and success.get('wait'):
                wait_time = success['wait']
                update_account_status(account_data, f"Rate limit - nghỉ {wait_time}s", "warning")
                account_data["api_message"] = f" Rate limit 429, nghỉ {wait_time}s"
                countdown_delay(account_id, account_data, wait_time, "Nghỉ rate limit")
                continue

            if success.get('fatal'):
                if success.get('checkpoint'):
                    update_account_status(account_data, "Dừng: CHECKPOINT", "error")
                    account_data["is_running"] = False
                else:
                    update_account_status(account_data, "Dừng: COOKIE HẾT HẠN", "error")
                    account_data["is_running"] = False
                break

            if success.get('skip'):
                with account_locks[account_id]:
                    account_data["skip"] += 1
                time.sleep(random.uniform(0.8, 1.5))
                continue

            if success.get('retry'):
                continue

            if success.get('status'):
                account_data["job_counter"] += 1
            
            if job_nghi > 0 and account_data["job_counter"] > 0 and account_data["job_counter"] % job_nghi == 0:
                update_account_status(account_data, f"Đã làm {account_data['job_counter']} job, nghỉ {thoi_gian_nghi}s")
                countdown_delay(account_id, account_data, thoi_gian_nghi, "Nghỉ")

            if success.get('status'):
                update_account_status(account_data, "Đang nhận tiền...")
                account_data["api_message"] = " Đang nhận tiền..."
                try:
                    nhantien = hoanthanh(ads_id, account_id, headers)
                except Exception as e:
                    update_account_status(account_data, "Lỗi nhận tiền", "warning")
                    account_data["api_message"] = f"⚠ Lỗi nhận tiền: {str(e)[:20]}"
                    time.sleep(random.uniform(1.5, 3))
                    continue

                if lannhan == 'y':
                    checklan = 1
                else:
                    checklan = 2

                ok = 0
                while checklan <= 2 and not stop_threads:
                    if isinstance(nhantien, dict) and nhantien.get('status') == 200:
                        ok = 1
                        tien = 0
                        if nhantien.get('data') and isinstance(nhantien.get('data'), dict):
                            tien = nhantien.get('data', {}).get('prices', 0)
                        
                        with account_locks[account_id]:
                            account_data["done"] += 1
                            account_data["coin"] += tien
                            
                            if loai == "follow":
                                account_data["follow"] += 1
                            elif loai == "like":
                                account_data["like"] += 1
                            
                            update_account_status(account_data, f"Thành công +{tien} coin")
                            account_data["api_message"] = f" +{tien} coin"
                        
                        checkdoiacc = 0
                        break
                    
                    checklan += 1
                    if checklan == 3:
                        break
                    
                    time.sleep(random.uniform(2, 4))
                    account_data["api_message"] = " Đang nhận tiền lần 2..."
                    
                    try:
                        nhantien = hoanthanh(ads_id, account_id, headers)
                        if not isinstance(nhantien, dict):
                            nhantien = {"status": False, "message": "Phản hồi không hợp lệ"}
                    except:
                        nhantien = {"status": False, "message": "Exception"}

                if ok != 1:
                    error_msg = nhantien.get('message', 'Không nhận được tiền') if isinstance(nhantien, dict) else 'Không nhận được tiền'
                    update_account_status(account_data, f"Lỗi nhận tiền: {error_msg[:30]}", "warning")
                    account_data["api_message"] = f"⚠ {error_msg[:40]}"
                    try:
                        baoloi(ads_id, object_id, account_id, loai, headers)
                        with account_locks[account_id]:
                            account_data["skip"] += 1
                        checkdoiacc += 1
                        time.sleep(random.uniform(0.8, 1.5))
                    except:
                        time.sleep(random.uniform(0.8, 1.5))
            else:
                try:
                    baoloi(ads_id, object_id, account_id, loai, headers)
                    with account_locks[account_id]:
                        account_data["skip"] += 1
                    checkdoiacc += 1
                    time.sleep(random.uniform(0.8, 1.5))
                except:
                    time.sleep(random.uniform(0.8, 1.5))
            
            if loai in delay_config:
                delay_range = delay_config[loai]
                delay_time = random.randint(delay_range[0], delay_range[1])
            else:
                delay_time = delay_done
            
            if delay_time > 0:
                countdown_delay(account_id, account_data, delay_time, f"Delay {loai}")
                    
        except Exception as e:
            update_account_status(account_data, f"Lỗi: {str(e)[:20]}", "error")
            account_data["api_message"] = f"⚠ {str(e)[:20]}"
            time.sleep(random.uniform(delay_error * 0.8, delay_error * 1.2))
            continue
    
    with account_locks[account_id]:
        account_data["is_running"] = False
        if not account_data["status"].startswith("Dừng"):
            update_account_status(account_data, "Đã dừng")
    
    print(f"\033[1;33m[Thread {username}] Đã kết thúc")

# ========== HÀM XÂY DỰNG BẢNG DASHBOARD ==========
def build_table():
    table = Table(show_header=True, header_style="#ffffff", border_style="#ff9ecb", box=box.ROUNDED, show_lines=True)

    table.add_column("STT", justify="center", style="dim", width=4)
    table.add_column("Username", style="cyan", width=14)
    table.add_column("Nick Golike", style="yellow", width=14)
    table.add_column("Trạng thái", style="bold", justify="center", width=12)
    table.add_column("Đã làm", justify="center", style="green", width=6)
    table.add_column("Bỏ qua", justify="center", style="red", width=6)
    table.add_column("Type", justify="center", width=12)
    table.add_column("Coin", justify="center", style="yellow", width=5)
    table.add_column("Message", style="magenta", width=30)

    for i, (acc_id, data) in enumerate(accounts_data.items(), 1):
        if not data.get("is_running", True):
            status = "Đã dừng"
            status_color = "red"
        elif "checkpoint" in data.get("status", "").lower():
            status = "CHECKPOINT"
            status_color = "red"
        elif "die" in data.get("status", "").lower():
            status = "DIE"
            status_color = "red"
        elif data.get("rate_limit_until", 0) > time.time():
            status = "RATE LIMIT"
            status_color = "yellow"
        elif "rate limit" in data.get("status", "").lower():
            status = "GIỚI HẠN"
            status_color = "yellow"
        elif "nghỉ" in data.get("status", "").lower():
            status = "NGHỈ"
            status_color = "yellow"
        else:
            status = "ĐANG CHẠY"
            status_color = "green"

        if data.get("api_message"):
            detail = data["api_message"]
        else:
            detail = data.get("status", "")

        if len(detail) > 30:
            detail = detail[:27] + "..."

        golike_name = data.get("golike_username", "-")[:12]

        type_parts = []
        if data.get('follow', 0) > 0:
            type_parts.append(f"F:{data['follow']}")
        if data.get('like', 0) > 0:
            type_parts.append(f"L:{data['like']}")
        type_display = " | ".join(type_parts) if type_parts else "None"

        table.add_row(
            str(i),
            data.get("username", "")[:12],
            golike_name,
            f"[{status_color}]{status}[/{status_color}]",
            str(data.get("done", 0)),
            str(data.get("skip", 0)),
            type_display,
            str(data.get("coin", 0)),
            detail
        )
        
    return table

# ========== Phần chính ==========
if __name__ == '__main__':
    console = Console()
    
    selected_golike_accounts = display_auth_and_select_accounts()
    
    if not selected_golike_accounts:
        print("\033[1;31mKhông có nick Golike nào được chọn!")
        sys.exit(1)
    
    print(f"\033[1;32m✓ Đã chọn {len(selected_golike_accounts)} nick Golike:")
    for acc in selected_golike_accounts:
        print(f"   - [cyan]{acc['username']}[/] | [yellow]{acc['coin']} coin[/]")
    
    all_selected_accounts = chon_accounts_de_chay(selected_golike_accounts)
    
    if not all_selected_accounts:
        print("\033[1;31mKhông có tài khoản Instagram nào được chọn!")
        sys.exit(1)
    
    console.print(f"\n[bold #6bffb8]✓ Tổng cộng {len(all_selected_accounts)} Instagram account sẽ chạy[/bold #6bffb8]")
    time.sleep(2)
    
    delay_config = setup_delay_config()
    
    lam = menu_jobs()
    
    while True:
        try:
            job_nghi = int(input("\033[1;32mSau bao nhiêu job thành công thì nghỉ (0 = không nghỉ): ").strip())
            if job_nghi >= 0:
                break
            else:
                print("\033[1;31mNhập số >= 0!")
        except:
            print("\033[1;31mSai định dạng!")
    
    if job_nghi > 0:
        while True:
            try:
                thoi_gian_nghi = int(input("\033[1;32mThời gian nghỉ (giây): ").strip())
                if thoi_gian_nghi > 0:
                    break
                else:
                    print("\033[1;31mNhập số > 0!")
            except:
                print("\033[1;31mSai định dạng!")
    else:
        thoi_gian_nghi = 0
    
    while True:
        lannhan = input("\033[1;32mNhận tiền lần 2 nếu lần 1 fail? (y/n): ").strip().lower()
        if lannhan in ('y', 'n'):
            break
        print("\033[1;31mNhập y hoặc n!")
    
    while True:
        try:
            doiacc = int(input("\033[1;32mSố job fail để dừng tài khoản (0 = không dừng): ").strip())
            break
        except:
            print("\033[1;31mNhập số!")
    
    # Hiển thị banner cuối cùng
    os.system('clear' if os.name == 'posix' else 'cls')
    current_ip = get_public_ip()
    print(f"\033[1;97m IP: \033[1;32m{current_ip}")
    print(f"\033[1;32m Số nick Golike: {len(selected_golike_accounts)} | Số Instagram account: {len(all_selected_accounts)}")
    print(f"\033[1;32m Chế độ job: {lam}")
    print(f"\033[1;32m Delay Follow: {delay_config['follow'][0]}-{delay_config['follow'][1]}s")
    print(f"\033[1;32m Delay Like: {delay_config['like'][0]}-{delay_config['like'][1]}s")
    if job_nghi > 0:
        print(f"\033[1;32m Nghỉ {thoi_gian_nghi}s sau {job_nghi} job thành công")
    print(f"\033[1;32m Giới hạn lỗi: {doiacc}")
    print("\033[1;97m═══════════════════════════════════════════════════════════════════")
    print("\033[1;33mĐang khởi động tool đa luồng...")
    time.sleep(2)
    
    stop_threads = False
    threads = []
    
    # Cập nhật accounts_data global
    accounts_data.clear()
    accounts_data.update(all_selected_accounts)
    
    for account_id, account_data in all_selected_accounts.items():
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
            "Authorization": account_data.get('golike_auth'),
            'Content-Type': 'application/json;charset=utf-8'
        }
        
        t = threading.Thread(target=run_account, args=(account_id, account_data, headers, lam, delay_config, lannhan, doiacc, job_nghi, thoi_gian_nghi))
        t.daemon = True
        t.start()
        threads.append(t)
        time.sleep(0.3)
    
    os.system('clear' if os.name == 'posix' else 'cls')
    
    try:
        with Live(build_table(), console=console, refresh_per_second=2, screen=True) as live:
            while any(t.is_alive() for t in threads):
                live.update(build_table())
                time.sleep(0.5)
                
                if not any(t.is_alive() for t in threads):
                    break
    except KeyboardInterrupt:
        print("\n\033[1;33mĐang dừng các thread...")
        stop_threads = True
        
        for t in threads:
            t.join(timeout=5)
        
        print("\033[1;32m═══════════════════════════════════════════════════════════════════")
        print("\033[1;33mKẾT QUẢ:")
        total_done = sum(acc.get("done", 0) for acc in all_selected_accounts.values())
        total_coin = sum(acc.get("coin", 0) for acc in all_selected_accounts.values())
        
        golike_stats = {}
        for acc_id, acc in all_selected_accounts.items():
            golike_user = acc.get("golike_username", "Unknown")
            if golike_user not in golike_stats:
                golike_stats[golike_user] = {"done": 0, "coin": 0, "accounts": []}
            golike_stats[golike_user]["done"] += acc.get("done", 0)
            golike_stats[golike_user]["coin"] += acc.get("coin", 0)
            golike_stats[golike_user]["accounts"].append(acc.get("username", "?"))
        
        for golike_user, stats in golike_stats.items():
            print(f"\033[1;36m Nick Golike: {golike_user}")
            print(f"   Instagram accounts: {', '.join(stats['accounts'])}")
            print(f"   Jobs done: \033[1;32m{stats['done']}\033[0m | Coin: \033[1;33m{stats['coin']}\033[0m")
        
        print(f"\n\033[1;33mTỔNG: \033[1;32m{total_done} jobs \033[1;33m{total_coin} coin")
        print("\033[1;32m═══════════════════════════════════════════════════════════════════")
        print("\033[1;32mTạm biệt!")
        sys.exit(0)
