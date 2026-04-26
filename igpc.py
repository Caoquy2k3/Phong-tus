#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import requests
import re
from datetime import datetime, timezone
import random
import urllib3
import threading
from queue import Queue
from collections import defaultdict
import urllib.parse
import subprocess
import tempfile
import shutil

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

# THÊM IMPORT CHO SELENIUM
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, SessionNotCreatedException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Disable warnings SSL (chỉ cho Golike API)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

console = Console()

# ========== CẤU HÌNH HIỆU SUẤT ==========
WINDOW_WIDTH = 50
WINDOW_HEIGHT = 100
ZOOM_LEVEL = 0.25
DISABLE_IMAGES = True

# ========== CẤU HÌNH ANTI-BAN ==========
ENABLE_ANTI_BAN = True
MIN_DELAY_BETWEEN_ACTIONS = 8
MAX_DELAY_BETWEEN_ACTIONS = 15
ENABLE_HUMAN_BEHAVIOR = True
ENABLE_RANDOM_SCROLL = True
ENABLE_KEYSTROKE_DELAY = True

# ========== CẤU HÌNH ANTI-POPUP ==========
BLOCK_POPUPS = True
HANDLE_NOTIFICATIONS = True
HANDLE_SAVE_LOGIN = True

# ========== CẤU HÌNH NUÔI NICK ==========
ENABLE_FEED_BROWSING = True  # Bật chế độ lướt newsfeed khi delay hoặc hết job
FEED_BROWSING_MIN_DURATION = 15  # Thời gian lướt tối thiểu (giây)
FEED_BROWSING_MAX_DURATION = 45  # Thời gian lướt tối đa (giây)
FEED_SCROLL_COUNT = 5  # Số lần scroll tối thiểu
FEED_SCROLL_PAUSE_MIN = 2  # Thời gian dừng giữa các lần scroll tối thiểu
FEED_SCROLL_PAUSE_MAX = 5  # Thời gian dừng giữa các lần scroll tối đa
ENABLE_FEED_LIKE = False  # Có tự động like khi lướt feed không
ENABLE_FEED_STORY_WATCH = True  # Có xem story khi lướt feed không

# ========== KIỂM TRA MÔI TRƯỜNG ==========
def is_termux():
    try:
        if os.path.exists('/data/data/com.termux'):
            return True
        if 'ANDROID_ROOT' in os.environ and 'PREFIX' in os.environ and 'com.termux' in os.environ.get('PREFIX', ''):
            return True
        if os.path.exists('/data/data/com.termux/files/usr/bin'):
            return True
        return False
    except:
        return False

def is_windows():
    return os.name == 'nt'

RUNNING_IN_TERMUX = is_termux()
RUNNING_IN_WINDOWS = is_windows()

# ========== CẤU HÌNH LƯU TRỮ ==========
DATA_FOLDER = "data"
os.makedirs(DATA_FOLDER, exist_ok=True)
ACCOUNTS_SAVE_FILE = os.path.join(DATA_FOLDER, "saved_accounts.json")
AUTH_FILE = os.path.join(DATA_FOLDER, "Authorization.json")
GOLIKE_SELECTION_FILE = os.path.join(DATA_FOLDER, "golike_selection.json")
PROXY_CONFIG_FILE = os.path.join(DATA_FOLDER, "proxy_config.json")
USER_AGENT_CONFIG_FILE = os.path.join(DATA_FOLDER, "user_agent_config.json")

global_lock = threading.RLock()
driver_locks = defaultdict(threading.Lock)

# ========== QUẢN LÝ PROXY VÀ USER AGENT ==========
def load_proxy_config():
    """Tải cấu hình proxy từ file"""
    try:
        if os.path.exists(PROXY_CONFIG_FILE):
            with open(PROXY_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        console.print(f"[red]Lỗi tải proxy config: {str(e)}[/]")
        return {}

def save_proxy_config(config):
    """Lưu cấu hình proxy vào file"""
    try:
        with open(PROXY_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        console.print(f"[red]Lỗi lưu proxy config: {str(e)}[/]")
        return False

def load_user_agent_config():
    """Tải cấu hình User Agent từ file"""
    try:
        if os.path.exists(USER_AGENT_CONFIG_FILE):
            with open(USER_AGENT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        console.print(f"[red]Lỗi tải user agent config: {str(e)}[/]")
        return {}

def save_user_agent_config(config):
    """Lưu cấu hình User Agent vào file"""
    try:
        with open(USER_AGENT_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        console.print(f"[red]Lỗi lưu user agent config: {str(e)}[/]")
        return False

def get_proxy_for_account(username):
    """Lấy proxy cho một account cụ thể"""
    config = load_proxy_config()
    return config.get(username)

def set_proxy_for_account(username, proxy_url):
    """Thiết lập proxy cho một account"""
    config = load_proxy_config()
    config[username] = proxy_url
    return save_proxy_config(config)

def get_user_agent_for_account(username):
    """Lấy User Agent cho một account cụ thể"""
    config = load_user_agent_config()
    return config.get(username)

def set_user_agent_for_account(username, user_agent):
    """Thiết lập User Agent cho một account"""
    config = load_user_agent_config()
    config[username] = user_agent
    return save_user_agent_config(config)

def input_proxy_for_account(username):
    """Nhập proxy cho account"""
    console.print(f"\n[#6bb8ff]➤ Cấu hình Proxy cho account [cyan]{username}[/cyan][/#6bb8ff]")
    console.print("[dim]Định dạng: http://user:pass@host:port hoặc socks5://user:pass@host:port[/dim]")
    console.print("[dim]Nhập 'skip' để bỏ qua, 'none' để xóa proxy hiện tại[/dim]")
    
    current_proxy = get_proxy_for_account(username)
    if current_proxy:
        console.print(f"[#ffa56b]Proxy hiện tại: {current_proxy}[/#ffa56b]")
    
    proxy_input = console.input("[#ff9ecb]➤ [#ffffff]Nhập Proxy: [/]").strip()
    
    if proxy_input.lower() == 'skip':
        return current_proxy
    elif proxy_input.lower() == 'none':
        config = load_proxy_config()
        if username in config:
            del config[username]
            save_proxy_config(config)
            console.print("[#6bffb8]✓ Đã xóa proxy[/#6bffb8]")
        return None
    elif proxy_input:
        if set_proxy_for_account(username, proxy_input):
            console.print("[#6bffb8]✓ Đã lưu proxy[/#6bffb8]")
            return proxy_input
        else:
            console.print("[#ff6b6b]✗ Lỗi lưu proxy[/#ff6b6b]")
    return None

def input_user_agent_for_account(username):
    """Nhập User Agent cho account"""
    console.print(f"\n[#6bb8ff]➤ Cấu hình User Agent cho account [cyan]{username}[/cyan][/#6bb8ff]")
    console.print("[dim]Nhập 'skip' để bỏ qua, 'random' để dùng ngẫu nhiên, 'none' để xóa[/dim]")
    
    current_ua = get_user_agent_for_account(username)
    if current_ua:
        console.print(f"[#ffa56b]User Agent hiện tại: {current_ua[:50]}...[/#ffa56b]")
    
    ua_input = console.input("[#ff9ecb]➤ [#ffffff]Nhập User Agent: [/]").strip()
    
    if ua_input.lower() == 'skip':
        return current_ua
    elif ua_input.lower() == 'none':
        config = load_user_agent_config()
        if username in config:
            del config[username]
            save_user_agent_config(config)
            console.print("[#6bffb8]✓ Đã xóa User Agent[/#6bffb8]")
        return None
    elif ua_input.lower() == 'random':
        return None  # Sẽ dùng random
    elif ua_input:
        if set_user_agent_for_account(username, ua_input):
            console.print("[#6bffb8]✓ Đã lưu User Agent[/#6bffb8]")
            return ua_input
        else:
            console.print("[#ff6b6b]✗ Lỗi lưu User Agent[/#ff6b6b]")
    return None

def get_profile_path(account_data=None):
    if account_data and account_data.get("username"):
        username = account_data.get("username")
        profiles_dir = os.path.join(os.getcwd(), "chrome_profiles")
        os.makedirs(profiles_dir, exist_ok=True)
        safe_username = re.sub(r'[^a-zA-Z0-9_-]', '_', username)
        profile_path = os.path.join(profiles_dir, safe_username)
        os.makedirs(profile_path, exist_ok=True)
        return profile_path
    temp_dir = tempfile.mkdtemp(prefix="chrome_profile_")
    return temp_dir

def cleanup_profiles():
    profiles_dir = os.path.join(os.getcwd(), "chrome_profiles")
    if os.path.exists(profiles_dir):
        try:
            shutil.rmtree(profiles_dir)
            console.print("[yellow]Đã dọn dẹp profile Chrome[/yellow]")
        except Exception as e:
            console.print(f"[dim]Không thể dọn profile: {e}[/dim]")

# ========== HÀM LẤY THÔNG TIN USER TỪ GOLIKE ==========
def get_user_me(auth_token, session=None):
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
    try:
        with open(GOLIKE_SELECTION_FILE, 'w', encoding='utf-8') as f:
            json.dump({"selected_indices": selected_indices}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        console.print(f"[red]Lỗi lưu lựa chọn Golike: {str(e)}[/]")
        return False

def load_golike_selection():
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
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    while True:
        accounts = load_all_accounts()
        
        console.clear()
        banner()
        
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

# ========== KIỂM TRA SELENIUM ==========
def check_and_install_selenium():
    try:
        import selenium
        return True
    except ImportError:
        print("\033[1;33mSelenium chưa được cài đặt. Đang tiến hành cài đặt...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium"])
            print("\033[1;32mĐã cài đặt selenium thành công!")
            return True
        except:
            print("\033[1;31mKhông thể cài đặt selenium. Vui lòng cài thủ công: pip install selenium")
            return False

# ========== TÌM ĐƯỜNG DẪN CHROME/CHROMIUM VÀ CHROMEDRIVER TRONG TERMUX ==========
def find_chrome_in_termux():
    possible_paths = [
        '/data/data/com.termux/files/usr/bin/chromium',
        '/data/data/com.termux/files/usr/bin/chromium-browser',
        '/data/data/com.termux/files/usr/bin/chrome',
        '/data/data/com.termux/files/usr/bin/brave',
        '/data/data/com.termux/files/usr/bin/chromium-android',
        '/system/bin/chromium',
        '/system/bin/chrome'
    ]
    try:
        result = subprocess.run(['which', 'chromium'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    try:
        result = subprocess.run(['which', 'chromium-browser'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def find_chromedriver_in_termux():
    termux_chromedriver = '/data/data/com.termux/files/usr/bin/chromedriver'
    if os.path.exists(termux_chromedriver):
        return termux_chromedriver
    possible_paths = [
        '/data/data/com.termux/files/usr/bin/chromedriver',
        '/data/data/com.termux/files/usr/bin/chromium-driver',
        '/data/data/com.termux/files/usr/bin/chrome-driver',
        '/system/bin/chromedriver',
        '/system/bin/chrome-driver'
    ]
    try:
        result = subprocess.run(['which', 'chromedriver'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

# ========== KIỂM TRA CHROME ĐÃ CÀI ĐẶT CHƯA ==========
def check_chrome_installed(account_data=None):
    if RUNNING_IN_TERMUX:
        chrome_path = find_chrome_in_termux()
        if chrome_path:
            if account_data:
                update_account_status(account_data, f"Tìm thấy Chromium")
            return True, chrome_path
        else:
            if account_data:
                update_account_status(account_data, "Không tìm thấy Chromium", "error")
            return False, None
    else:
        try:
            import shutil
            chrome_path = shutil.which('chrome') or shutil.which('google-chrome') or shutil.which('chromium')
            if chrome_path:
                return True, chrome_path
            default_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files\Chromium\Application\chrome.exe"
            ]
            for path in default_paths:
                if os.path.exists(path):
                    return True, path
            options = Options()
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            test_driver = webdriver.Chrome(options=options)
            test_driver.quit()
            return True, None
        except:
            return False, None

def check_chromedriver_installed(account_data=None):
    if RUNNING_IN_TERMUX:
        chromedriver_path = find_chromedriver_in_termux()
        if chromedriver_path:
            if account_data:
                update_account_status(account_data, f"Tìm thấy ChromeDriver")
            return chromedriver_path
        else:
            if account_data:
                update_account_status(account_data, "Không tìm thấy ChromeDriver", "error")
            return None
    return None

# Danh sách User-Agent cho Instagram
USER_AGENTS = [
    'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 12; SM-S908E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def get_user_agent_for_driver(username=None):
    """Lấy User Agent cho driver, ưu tiên cấu hình riêng"""
    if username:
        custom_ua = get_user_agent_for_account(username)
        if custom_ua:
            return custom_ua
    return get_random_user_agent()

# ========== HÀM LẤY USERNAME TỪ COOKIE ==========
def get_username_from_cookie(cookie_str):
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
            'User-Agent': get_random_user_agent(),
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

# ========== HÀM LƯU/ TẢI ACCOUNTS ==========
def save_accounts_to_file(ui_accounts):
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
                "saved_at": get_current_time().strftime("%Y-%m-%d %H:%M:%S"),
                "proxy": get_proxy_for_account(acc.get("username")),
                "user_agent": get_user_agent_for_account(acc.get("username"))
            })
        with open(ACCOUNTS_SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        console.print(f"[#ff6b6b]Lỗi lưu accounts: {str(e)}[/#ff6b6b]")
        return False

def load_accounts_from_file():
    try:
        if os.path.exists(ACCOUNTS_SAVE_FILE):
            with open(ACCOUNTS_SAVE_FILE, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            ui_accounts = []
            for acc in save_data:
                username = acc.get("username")
                ui_accounts.append({
                    "username": username,
                    "account_id": acc.get("account_id"),
                    "cookie": acc.get("cookie"),
                    "golike_username": acc.get("golike_username"),
                    "status": acc.get("status", "[#6bffb8]Đã lưu[/#6bffb8]"),
                    "is_valid": acc.get("is_valid", False),
                    "saved_at": acc.get("saved_at", ""),
                    "proxy": acc.get("proxy"),
                    "user_agent": acc.get("user_agent")
                })
            return ui_accounts
        return []
    except Exception as e:
        console.print(f"[#ff6b6b]Lỗi tải accounts: {str(e)}[/#ff6b6b]")
        return []

def init_data_folder():
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        readme_content = """# Thư mục lưu trữ dữ liệu Instagram Tool

## Các file trong thư mục:
- `saved_accounts.json`: Lưu danh sách accounts đã nhập cookie
- `Authorization.json`: Lưu danh sách Authorization Golike
- `golike_selection.json`: Lưu lựa chọn nick Golike
- `proxy_config.json`: Lưu cấu hình proxy cho từng account
- `user_agent_config.json`: Lưu cấu hình User Agent cho từng account
- Các file `cookies_*.txt`: Backup cookie cho từng account

## Lệnh quản lý trong tool:
- `add`: Thêm cookie mới
- `save`: Lưu danh sách accounts hiện tại
- `load`: Tải danh sách accounts đã lưu
- `1,2,3`: Chọn account để chạy
- `-1,2`: Xóa account
- `run`: Bắt đầu chạy
- `proxy`: Cấu hình proxy cho account đã chọn
- `ua`: Cấu hình User Agent cho account đã chọn

© Tool Instagram Auto
"""
        with open(os.path.join(DATA_FOLDER, "README.md"), 'w', encoding='utf-8') as f:
            f.write(readme_content)

init_data_folder()

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

# ========== Hàm kiểm tra an toàn ==========
def safe_get(data, key, default=None):
    if isinstance(data, dict):
        return data.get(key, default)
    return default

def safe_get_nested(data, *keys, default=None):
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current

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

# ========== Cấu hình an toàn ==========
MAX_SESSION_ERRORS = 5
ERROR_RESET_TIME = 1800
MAX_RETRY_COUNT = 2
RATE_LIMIT_BACKOFF = [5, 15, 30]

# ========== Biến toàn cục ==========
all_accounts_data = {}
stop_threads = False
thread_status = {}
account_locks = defaultdict(threading.RLock)
bot_instances = {}
system_status = {"message": "Đang khởi động...", "level": "info"}

api_lock = threading.RLock()

# ========== Hàm cập nhật trạng thái ==========
def update_account_status(account_data, message, level="info"):
    with account_locks.get(account_data.get("id", "unknown"), threading.RLock()):
        if len(message) > 50:
            message = message[:47] + "..."
        account_data["detail_status"] = message
        account_data["status"] = message

def update_system_status(message, level="info"):
    global system_status
    system_status = {"message": message, "level": level}

# ========== HÀM TRÍCH XUẤT USERNAME TỪ JOB DATA ==========
def extract_username_from_job_data(data):
    if not isinstance(data, dict):
        return None
    username = None
    object_data = data.get("object_data")
    if isinstance(object_data, str):
        try:
            object_data = json.loads(object_data)
        except:
            object_data = {}
    if isinstance(object_data, dict):
        for key in ["username", "instagram_username", "target_username", "name"]:
            username = object_data.get(key)
            if username and str(username).strip():
                return str(username).strip().replace("@", "")
    for key in ["username", "target_username"]:
        username = data.get(key)
        if username and str(username).strip():
            return str(username).strip().replace("@", "")
    link = data.get("link")
    if link and isinstance(link, str):
        import re
        match = re.search(r"(?:www\.|m\.)?instagram\.com/([A-Za-z0-9._]+)", link)
        if match:
            username = match.group(1)
            if username and username not in ["p", "reel", "stories", "explore", "tv", "accounts"]:
                return username
    return None

# ========== HÀM LẤY COMMENT TEXT TỪ JOB DATA (CHUẨN GOLIKE) ==========
def extract_comment_from_job_data(data):
    """
    Lấy nội dung comment CHUẨN từ cấu trúc dữ liệu Golike
    Ưu tiên: data.comment_run.message (mới nhất) -> comments[].message -> object_data.comment
    KHÔNG DÙNG DỰ PHÒNG, lấy đúng response từ Golike
    """
    if not isinstance(data, dict):
        return None
    
    # ===== ƯU TIÊN 1: comment_run.message (comment đang chạy hiện tại) =====
    comment_run = data.get("comment_run")
    if isinstance(comment_run, dict):
        message = comment_run.get("message")
        if message and isinstance(message, str) and message.strip():
            return message.strip()
    
    # ===== ƯU TIÊN 2: Lấy từ mảng comments (các comment đã được gán) =====
    comments = data.get("comments")
    if isinstance(comments, list) and len(comments) > 0:
        # Lấy comment mới nhất trong mảng
        for comment in reversed(comments):
            if isinstance(comment, dict):
                message = comment.get("message")
                if message and isinstance(message, str) and message.strip():
                    return message.strip()
    
    # ===== ƯU TIÊN 3: object_data.comment =====
    object_data = data.get("object_data")
    if isinstance(object_data, str):
        try:
            object_data = json.loads(object_data)
        except:
            object_data = {}
    if isinstance(object_data, dict):
        comment = object_data.get("comment")
        if comment and isinstance(comment, str) and comment.strip():
            return comment.strip()
    
    return None

# ========== HÀM LẤY STATUS MESSAGE TỪ JOB DATA (CHUẨN GOLIKE) ==========
def extract_status_message_from_job_data(data):
    """
    Lấy status_message từ Golike response
    Ví dụ: "status_message": "Đang chạy -"
    """
    if not isinstance(data, dict):
        return None
    status_msg = data.get("status_message")
    if status_msg and isinstance(status_msg, str) and status_msg.strip():
        return status_msg.strip()
    return None

# ========== HÀM LẤY GIÁ TIỀN TỪ JOB DATA ==========
def extract_price_from_job_data(data):
    """
    Lấy giá tiền từ job data
    price_per: giá gốc, price_after_cost: giá sau chi phí
    """
    if not isinstance(data, dict):
        return 0
    # Ưu tiên price_after_cost
    price = data.get("price_after_cost")
    if price and isinstance(price, (int, float)):
        return int(price)
    price = data.get("price_per")
    if price and isinstance(price, (int, float)):
        return int(price)
    return 0

# ========== HÀM LẤY PACKAGE NAME TỪ JOB DATA ==========
def extract_package_name_from_job_data(data):
    """
    Lấy package_name từ job data
    Ví dụ: "package_name": "comment"
    """
    if not isinstance(data, dict):
        return None
    pkg_name = data.get("package_name")
    if pkg_name and isinstance(pkg_name, str):
        return pkg_name.strip()
    return None

# ========== HÀM LẤY OBJECT NOT EXIST STATUS ==========
def extract_object_not_exist_from_job_data(data):
    """
    Lấy object_not_exist status từ job data
    """
    if not isinstance(data, dict):
        return 0
    return data.get("object_not_exist", 0)

# ========== HÀM TỰ ĐỘNG ADD GOLIKE ==========
def get_target_uid(link_target, cookie_str):
    headers_ig = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'user-agent': get_random_user_agent(),
        'cookie': cookie_str,
    }
    try:
        res = requests.get(link_target, headers=headers_ig, timeout=15, verify=False)
        lt = re.findall(r'"target_id":"(\d+)"', res.text)
        if lt:
            return lt[0]
        match = re.search(r'"profile_id":"(\d+)"', res.text)
        if match:
            return match.group(1)
        match2 = re.search(r'"id":"(\d+)","is_verified"', res.text)
        if match2:
            return match2.group(1)
        return None
    except:
        return None

def auto_add_golike(username, cookie_str, headers_golike, golike_username):
    console.print(f"[#ffa56b]➤ Account {username} chưa có trên Golike. Đang tiến hành thêm tự động vào nick [cyan]{golike_username}[/cyan]...[/#ffa56b]")
    
    FALLBACK_LINK = "https://www.instagram.com/evansnguyen.0104"
    
    console.print(f"[#6bb8ff]➤ Đang lấy link Verify từ API Golike...[/#6bb8ff]")
    link_target = ""
    
    try:
        res_link = requests.get('https://gateway.golike.net/api/instagram-account', headers=headers_golike, timeout=15, verify=False)
        if res_link.status_code != 200:
            try:
                error_data = res_link.json()
                error_msg = error_data.get('message') or error_data.get('msg') or f"HTTP {res_link.status_code}"
            except:
                error_msg = f"HTTP {res_link.status_code}"
            console.print(f"[#ffa56b]⚠ Lỗi lấy link verify: {error_msg} - Thử link dự phòng[/#ffa56b]")
            link_target = FALLBACK_LINK
        else:
            link_target = res_link.json().get('link_verify_follow', '')
            if link_target:
                console.print(f"[#6bffb8]✓ Lấy thành công link verify: {link_target}[/#6bffb8]")
            else:
                console.print(f"[#ffa56b]⚠ API Golike không trả về link_verify_follow - Thử link dự phòng[/#ffa56b]")
                link_target = FALLBACK_LINK
    except Exception as e:
        console.print(f"[#ffa56b]⚠ Lỗi khi lấy link verify: {str(e)} - Thử link dự phòng[/#ffa56b]")
        link_target = FALLBACK_LINK

    console.print(f"[#6bb8ff]➤ Đang lấy UID của mục tiêu...[/#6bb8ff]")
    target_uid = get_target_uid(link_target, cookie_str)
    
    if not target_uid and link_target != FALLBACK_LINK:
        console.print(f"[#ffa56b]⚠ Không lấy được UID từ link API, thử với link dự phòng...[/#ffa56b]")
        link_target = FALLBACK_LINK
        console.print(f"[#6bb8ff]➤ Sử dụng link dự phòng: {link_target}[/#6bb8ff]")
        target_uid = get_target_uid(link_target, cookie_str)
        
    if not target_uid:
        console.print(f"[#ff6b6b]✗ Lỗi: Không lấy được UID từ link {link_target}![/#ff6b6b]")
        console.print(f"[dim]   → Cookie có thể đã hết hạn hoặc Instagram chặn[/dim]")
        return False, "-"
        
    console.print(f"[#6bb8ff]➤ Đang follow ID {target_uid} bằng API V1...[/#6bb8ff]")
    try:
        csrf = cookie_str.split("csrftoken=")[1].split(';')[0] if "csrftoken=" in cookie_str else ""
        headers_follow = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.instagram.com',
            'referer': 'https://www.instagram.com/',
            'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'user-agent': get_random_user_agent(),
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
            console.print(f"[#6bffb8] Follow thành công![/#6bffb8]")
        else:
            console.print(f"[#ff6b6b] Lỗi: Follow thất bại (Response: {res_follow.status_code})[/#ff6b6b]")
            return False, "-"
    except Exception as e:
        console.print(f"[#ff6b6b] Lỗi thực thi Follow: {str(e)}[/#ff6b6b]")
        return False, "-"
    
    console.print(f"[#6bb8ff]➤ Đợi 3 giây để Instagram ghi nhận Follow...[/#6bb8ff]")
    time.sleep(3)
        
    console.print(f"[#6bb8ff]➤ Đang gửi yêu cầu Verify lên Golike...[/#6bb8ff]")
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
            console.print(f"[bold #6bffb8]✓ Thêm và Match thành công {username} vào Golike![/bold #6bffb8]")
            return True, new_acc_data.get('id', '-')
        else:
            error_msg = resp_json.get('message') or resp_json.get('msg') or f"HTTP {res.status_code}"
            console.print(f"[#ff6b6b]✗ Lỗi từ Golike: {error_msg}[/#ff6b6b]")
            return False, "-"
    except Exception as e:
        console.print(f"[#ff6b6b]✗ Lỗi kết nối API Golike Verify: {str(e)}[/#ff6b6b]")
        return False, "-"

# ========== HÀM HIỂN THỊ DANH SÁCH GOLIKE ĐỂ CHỌN ==========
def display_golike_list_for_selection(golike_accounts):
    console.clear()
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

# ========== MENU CẤU HÌNH NUÔI NICK ==========
def setup_feed_browsing_config():
    """Menu cấu hình chế độ lướt newsfeed nuôi nick"""
    global ENABLE_FEED_BROWSING, FEED_BROWSING_MIN_DURATION, FEED_BROWSING_MAX_DURATION
    global FEED_SCROLL_COUNT, FEED_SCROLL_PAUSE_MIN, FEED_SCROLL_PAUSE_MAX
    global ENABLE_FEED_LIKE, ENABLE_FEED_STORY_WATCH
    
    while True:
        console.clear()
        
        table = Table(
            title="[#ffffff]Cấu Hình [#00ffff]Nuôi Nick (Lướt Newsfeed)[/]",
            box=box.SQUARE,
            border_style="#ff9ecb",
            show_lines=True,
            pad_edge=False
        )
        table.add_column("Thông Số", justify="left", header_style="#ff9ecb", width=25)
        table.add_column("Giá Trị", justify="center", header_style="#00ffff", width=20)
        table.add_column("Mô Tả", justify="left", header_style="#ffffff", width=30)
        
        table.add_row(
            "[bold #6bb8ff]Bật chế độ nuôi nick[/]",
            f"[bold {'#6bffb8' if ENABLE_FEED_BROWSING else '#ff6b6b'}]{'BẬT' if ENABLE_FEED_BROWSING else 'TẮT'}[/]",
            "Tự động lướt newsfeed khi delay hoặc hết job"
        )
        table.add_row(
            "[bold #6bb8ff]Thời gian lướt tối thiểu[/]",
            f"[bold #ffd54f]{FEED_BROWSING_MIN_DURATION}s[/]",
            "Thời gian lướt ít nhất mỗi lần"
        )
        table.add_row(
            "[bold #6bb8ff]Thời gian lướt tối đa[/]",
            f"[bold #ffd54f]{FEED_BROWSING_MAX_DURATION}s[/]",
            "Thời gian lướt nhiều nhất mỗi lần"
        )
        table.add_row(
            "[bold #6bb8ff]Số lần scroll tối thiểu[/]",
            f"[bold #ffd54f]{FEED_SCROLL_COUNT}[/]",
            "Số lần scroll khi lướt feed"
        )
        table.add_row(
            "[bold #6bb8ff]Dừng giữa scroll (min-max)[/]",
            f"[bold #ffd54f]{FEED_SCROLL_PAUSE_MIN}-{FEED_SCROLL_PAUSE_MAX}s[/]",
            "Thời gian dừng xem bài viết"
        )
        table.add_row(
            "[bold #6bb8ff]Tự động like khi lướt[/]",
            f"[bold {'#6bffb8' if ENABLE_FEED_LIKE else '#ff6b6b'}]{'BẬT' if ENABLE_FEED_LIKE else 'TẮT'}[/]",
            "Có tự động like bài viết khi lướt feed không"
        )
        table.add_row(
            "[bold #6bb8ff]Xem story[/]",
            f"[bold {'#6bffb8' if ENABLE_FEED_STORY_WATCH else '#ff6b6b'}]{'BẬT' if ENABLE_FEED_STORY_WATCH else 'TẮT'}[/]",
            "Có xem story khi lướt feed không"
        )
        
        console.print(table)
        
        console.print("\n[#ff9ecb]➤ [#ffffff]Lệnh:[/]")
        console.print("  [#6bb8ff]1[/] - Bật/Tắt chế độ nuôi nick")
        console.print("  [#6bb8ff]2[/] - Sửa thời gian lướt tối thiểu")
        console.print("  [#6bb8ff]3[/] - Sửa thời gian lướt tối đa")
        console.print("  [#6bb8ff]4[/] - Sửa số lần scroll")
        console.print("  [#6bb8ff]5[/] - Sửa thời gian dừng giữa scroll")
        console.print("  [#6bb8ff]6[/] - Bật/Tắt tự động like")
        console.print("  [#6bb8ff]7[/] - Bật/Tắt xem story")
        console.print("  [#6bffb8]Enter[/] - Lưu và tiếp tục")
        
        choice = console.input("\n[#ff9ecb]➤ [#ffffff]Lựa chọn: [/]").strip()
        
        if choice == '':
            console.print("[#6bffb8]✓ Đã lưu cấu hình nuôi nick[/#6bffb8]")
            time.sleep(1)
            return
        elif choice == '1':
            ENABLE_FEED_BROWSING = not ENABLE_FEED_BROWSING
            console.print(f"[#6bffb8]✓ Chế độ nuôi nick: {'BẬT' if ENABLE_FEED_BROWSING else 'TẮT'}[/#6bffb8]")
            time.sleep(0.5)
        elif choice == '2':
            try:
                val = int(console.input("[#ff9ecb]➤ Thời gian lướt tối thiểu (giây): [/]").strip())
                if val > 0 and val <= FEED_BROWSING_MAX_DURATION:
                    FEED_BROWSING_MIN_DURATION = val
                else:
                    console.print("[#ff6b6b]✗ Giá trị không hợp lệ (phải > 0 và <= max)[/#ff6b6b]")
                    time.sleep(1)
            except:
                console.print("[#ff6b6b]✗ Sai định dạng[/#ff6b6b]")
                time.sleep(1)
        elif choice == '3':
            try:
                val = int(console.input("[#ff9ecb]➤ Thời gian lướt tối đa (giây): [/]").strip())
                if val >= FEED_BROWSING_MIN_DURATION:
                    FEED_BROWSING_MAX_DURATION = val
                else:
                    console.print("[#ff6b6b]✗ Giá trị không hợp lệ (phải >= min)[/#ff6b6b]")
                    time.sleep(1)
            except:
                console.print("[#ff6b6b]✗ Sai định dạng[/#ff6b6b]")
                time.sleep(1)
        elif choice == '4':
            try:
                val = int(console.input("[#ff9ecb]➤ Số lần scroll tối thiểu: [/]").strip())
                if val > 0:
                    FEED_SCROLL_COUNT = val
                else:
                    console.print("[#ff6b6b]✗ Phải lớn hơn 0[/#ff6b6b]")
                    time.sleep(1)
            except:
                console.print("[#ff6b6b]✗ Sai định dạng[/#ff6b6b]")
                time.sleep(1)
        elif choice == '5':
            try:
                min_val = int(console.input("[#ff9ecb]➤ Thời gian dừng tối thiểu (giây): [/]").strip())
                max_val = int(console.input("[#ff9ecb]➤ Thời gian dừng tối đa (giây): [/]").strip())
                if min_val > 0 and max_val >= min_val:
                    FEED_SCROLL_PAUSE_MIN = min_val
                    FEED_SCROLL_PAUSE_MAX = max_val
                else:
                    console.print("[#ff6b6b]✗ Giá trị không hợp lệ[/#ff6b6b]")
                    time.sleep(1)
            except:
                console.print("[#ff6b6b]✗ Sai định dạng[/#ff6b6b]")
                time.sleep(1)
        elif choice == '6':
            ENABLE_FEED_LIKE = not ENABLE_FEED_LIKE
            console.print(f"[#6bffb8]✓ Tự động like: {'BẬT' if ENABLE_FEED_LIKE else 'TẮT'}[/#6bffb8]")
            time.sleep(0.5)
        elif choice == '7':
            ENABLE_FEED_STORY_WATCH = not ENABLE_FEED_STORY_WATCH
            console.print(f"[#6bffb8]✓ Xem story: {'BẬT' if ENABLE_FEED_STORY_WATCH else 'TẮT'}[/#6bffb8]")
            time.sleep(0.5)

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
    delay_like = [5, 10]
    delay_follow = [5, 15]
    delay_comment = [10, 20]
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
        table.add_row(*row("Delay Comment", delay_comment, "#6bb8ff", "#b8dcff", "#8ac6ff"))
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
                "comment": delay_comment,
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
        delay_comment = [
            input_number(f"Delay Comment Min ({delay_comment[0]}): ", delay_comment[0]),
            input_number(f"Delay Comment Max ({delay_comment[1]}): ", delay_comment[1])
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
    {"id": "3", "name": "Comment", "value": "comment", "color": "#00ffff"},
]

def render_tablet(selections, current_idx):
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
    ui_accounts = load_accounts_from_file()
    selected = []

    def render():
        table = Table(expand=True, box=box.HEAVY, show_lines=True, border_style="#caffbf")
        table.add_column("[#6bffb8]STT[/]", justify="center", width=4)
        table.add_column("[#ffffb8]USERNAME[/]", justify="center", style="#6bb8ff", width=15)
        table.add_column("[#ffd54f]GOLIKE ID[/]", justify="center", width=8)
        table.add_column("[#ffa56b]NICK GOLIKE[/]", justify="center", width=12)
        table.add_column("[#ffa56b]PROXY[/]", justify="center", width=12)
        table.add_column("[#ffa56b]COOKIE[/]", justify="center", width=20)
        table.add_column("[#6bffb8]STATUS[/]", justify="center", width=15)
        for i, acc in enumerate(ui_accounts, 1):
            style = "bold #ff6b6b #ffd54f #ffffb8 #6bffb8 #6bb8ff" if (i-1) in selected else ""
            cookie_short = (acc.get("cookie", "")[:20] + "...") if len(acc.get("cookie", "")) > 20 else acc.get("cookie", "")
            golike_name = acc.get("golike_username", "-")[:10]
            proxy_status = "[#6bffb8]Có[/]" if acc.get("proxy") else "[#ffa56b]Không[/]"
            table.add_row(
                str(i),
                f"[#6bb8ff]{acc.get('username','Unknown')}[/]",
                f"[#ffd54f]{str(acc.get('account_id','-'))}[/]",
                f"[#ffa56b]{golike_name}[/]",
                proxy_status,
                f"[#ffa56b]{cookie_short if cookie_short else 'Chưa nhập'}[/]",
                f"[#6bffb8]{acc.get('status','')}[/]",
                style=style
            )
        total_accounts = len(ui_accounts)
        valid_accounts = sum(1 for acc in ui_accounts if acc.get("is_valid", False))
        title = Align.center(Text.from_markup("[#6bb8ff]INSTAGRAM[/] [#ff6b6b]ACCOUNT[/]"))
        commands = Text.from_markup("\n [#6bb8ff]Lệnh: add = thêm cookie [/][#ff6b6b]|[/][#ffd54f] save = lưu [/][#6bffb8]|[/][#6bb8ff] load = tải [/][#ffd54f]|[/][#ff9ecb] 1,2,3 = chọn acc [/][#6bb8ff]|[/][#ff6b6b] -1,2 = xóa acc [/][#6bffb8]|[/][#00ffff] proxy = cấu hình proxy [/][#6bffb8]|[/][#ff9ecb] ua = cấu hình User Agent [/][#6bffb8]|[/][#ffd54f] run = Bắt đầu\n[/]")
        return Group(title, table, commands)

    def parse_ids(cmd):
        return [int(x.strip()) - 1 for x in cmd.split(",") if x.strip().isdigit()]

    def add_multi_cookie():
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
            
            # Cấu hình proxy cho account mới
            proxy = input_proxy_for_account(username)
            
            # Cấu hình User Agent cho account mới
            user_agent = input_user_agent_for_account(username)
            
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
                    "saved_at": get_current_time().strftime("%Y-%m-%d %H:%M:%S"),
                    "proxy": proxy,
                    "user_agent": user_agent
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
        if cmd == "proxy":
            if not selected:
                console.print("[#ff6b6b] Bạn chưa chọn account nào! Hãy nhập số thứ tự (VD: 1,2) trước[/#ff6b6b]")
                time.sleep(2)
                continue
            for idx in selected:
                username = ui_accounts[idx].get("username")
                if username:
                    proxy = input_proxy_for_account(username)
                    ui_accounts[idx]["proxy"] = proxy
            save_accounts_to_file(ui_accounts)
            continue
        if cmd == "ua":
            if not selected:
                console.print("[#ff6b6b] Bạn chưa chọn account nào! Hãy nhập số thứ tự (VD: 1,2) trước[/#ff6b6b]")
                time.sleep(2)
                continue
            for idx in selected:
                username = ui_accounts[idx].get("username")
                if username:
                    ua = input_user_agent_for_account(username)
                    ui_accounts[idx]["user_agent"] = ua
            save_accounts_to_file(ui_accounts)
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
            "comment": 0,
            "favorite": 0,
            "coin": 0,
            "status": "Đang chờ...",
            "detail_status": "Đang khởi tạo...",
            "api_message": "",
            "session_errors": 0,
            "last_error_time": 0,
            "error_counts": {
                'follow': 0, 'like': 0, 'comment': 0, 'checkpoint': 0, 'rate_limit': 0, 'other': 0
            },
            "is_running": True,
            "thread_id": None,
            "job_counter": 0,
            "rate_limit_until": 0,
            "proxy": acc_data.get("proxy"),
            "user_agent": acc_data.get("user_agent")
        }
        try:
            with open(f"cookies_{acc_data['username']}.txt", 'w') as f:
                f.write(acc_data['cookie'])
        except:
            pass
    return selected_accounts

# ========== INSTAGRAM Class - Sử dụng Selenium với Anti-Ban ==========
class INSTAGRAM:
    def __init__(self, cookies, account_data=None):
        self.cookies = cookies
        self.driver = None
        self.user_id = None
        self.username = None
        self.last_action_time = 0
        self.min_action_interval = 5
        self.account_data = account_data
        self.error_count = 0
        self.max_errors_before_reset = 999
        self.driver_lock = threading.Lock()
        self.is_logged_in = False
        self._action_count = 0
        self._feed_browsing_count = 0
        
    def _update_status(self, message, level="info"):
        if self.account_data:
            update_account_status(self.account_data, message, level)
            if "thành công" in message.lower() or "success" in message.lower():
                self.error_count = 0
    
    def _human_delay(self):
        if not ENABLE_ANTI_BAN:
            return
        delay = random.uniform(MIN_DELAY_BETWEEN_ACTIONS, MAX_DELAY_BETWEEN_ACTIONS)
        time.sleep(delay)
        self.last_action_time = time.time()

    def _random_mouse_movement(self):
        if not ENABLE_HUMAN_BEHAVIOR or not self.driver:
            return
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            window_size = self.driver.get_window_size()
            width = window_size.get('width', 500)
            height = window_size.get('height', 500)
            actions = ActionChains(self.driver)
            random_x = random.randint(50, max(100, width - 50))
            random_y = random.randint(50, max(100, height - 50))
            actions.move_by_offset(random_x, random_y).perform()
            actions.move_by_offset(-random_x, -random_y).perform()
        except:
            pass

    def _random_scroll(self):
        if not ENABLE_RANDOM_SCROLL or not self.driver:
            return
        try:
            scroll_amount = random.randint(100, 500)
            scroll_direction = random.choice([-1, 1])
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount * scroll_direction});")
            time.sleep(random.uniform(0.3, 1))
            if random.random() < 0.3:
                self.driver.execute_script(f"window.scrollBy(0, {-scroll_amount * scroll_direction // 2});")
        except:
            pass

    def _handle_popups(self):
        if not BLOCK_POPUPS or not self.driver:
            return
        try:
            popup_selectors = [
                "//button[contains(text(), 'Not Now')]",
                "//button[contains(text(), 'Later')]",
                "//button[contains(text(), 'Cancel')]",
                "//button[contains(text(), 'Close')]",
                "//div[@role='button' and contains(text(), 'Not Now')]",
                "//div[@role='button' and contains(text(), 'Later')]",
                "//button[@aria-label='Close']",
                "//div[@aria-label='Close']",
                "//button[contains(@class, 'wpO6b')]",
                "//button[contains(@class, 'aOOlW')]",
                "//div[contains(text(), 'Turn on Notifications')]/following::button",
                "//div[contains(text(), 'Bật thông báo')]/following::button",
                "//button[contains(text(), 'Không phải bây giờ')]",
                "//button[contains(text(), 'Để sau')]",
            ]
            for selector in popup_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            self.driver.execute_script("arguments[0].click();", elem)
                            time.sleep(random.uniform(0.5, 1))
                except:
                    continue
        except:
            pass

    def _handle_notifications(self):
        if not HANDLE_NOTIFICATIONS or not self.driver:
            return
        try:
            self.driver.execute_script("""
                if (Notification && Notification.requestPermission) {
                    Notification.requestPermission = function() {
                        return Promise.resolve('denied');
                    };
                }
            """)
        except:
            pass

    def _handle_save_password(self):
        if not HANDLE_SAVE_LOGIN or not self.driver:
            return
        try:
            save_selectors = [
                "//button[contains(text(), 'Not Now')]",
                "//button[contains(text(), 'Save Info')]/following::button",
                "//button[contains(text(), 'Không phải bây giờ')]",
                "//div[@role='button' and contains(text(), 'Not Now')]",
            ]
            for selector in save_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            self.driver.execute_script("arguments[0].click();", elem)
                            time.sleep(random.uniform(0.3, 0.8))
                except:
                    continue
        except:
            pass

    def _human_keystroke(self, element, text):
        if not ENABLE_KEYSTROKE_DELAY:
            element.send_keys(text)
            return
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.03, 0.15))
        time.sleep(random.uniform(0.1, 0.3))

    def _random_activity_break(self):
        if not ENABLE_ANTI_BAN:
            return
        self._action_count += 1
        if self._action_count >= random.randint(5, 10):
            self._action_count = 0
            break_time = random.randint(30, 90)
            self._update_status(f"Nghỉ giải lao {break_time}s để tránh ban")
            time.sleep(break_time)
        
    def _wait_for_rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self.last_action_time
        if time_since_last < self.min_action_interval:
            time.sleep(self.min_action_interval - time_since_last)
        self.last_action_time = time.time()
    
    # ========== HÀM NUÔI NICK - LƯỚT NEWSFEED ==========
    def browse_newsfeed(self, duration=None):
        """
        Lướt newsfeed Instagram để tăng trust cho tài khoản.
        Sử dụng lại các hàm _random_scroll và _random_mouse_movement có sẵn.
        """
        if not ENABLE_FEED_BROWSING:
            return
            
        if not self.driver or not self.is_logged_in:
            self._update_status("Không thể lướt feed: chưa đăng nhập", "warning")
            return
        
        try:
            # Xác định thời gian lướt
            if duration is None:
                browse_duration = random.randint(FEED_BROWSING_MIN_DURATION, FEED_BROWSING_MAX_DURATION)
            else:
                browse_duration = min(duration, FEED_BROWSING_MAX_DURATION)
            
            self._feed_browsing_count += 1
            self._update_status(f"🌿 Nuôi nick: Lướt newsfeed {browse_duration}s")
            
            # Điều hướng về trang chủ
            current_url = self.driver.current_url
            if "instagram.com" not in current_url or "/p/" in current_url or "/reel/" in current_url:
                self._update_status("🌿 Về trang chủ Instagram...")
                try:
                    self.driver.get("https://www.instagram.com/")
                except TimeoutException:
                    self.driver.execute_script("window.stop();")
                time.sleep(random.uniform(3, 5))
            
            self._handle_popups()
            self._handle_notifications()
            
            start_time = time.time()
            scroll_count = 0
            stories_watched = False
            
            while time.time() - start_time < browse_duration:
                if stop_threads:
                    break
                
                # Xem story nếu có và chưa xem
                if ENABLE_FEED_STORY_WATCH and not stories_watched:
                    try:
                        story_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                            "div[role='button'] canvas, div._aa0g, div._ac7b, div._aarf")
                        if story_elements:
                            for story in story_elements[:2]:  # Xem tối đa 2 story
                                if story.is_displayed():
                                    self.driver.execute_script("arguments[0].click();", story)
                                    self._update_status("🌿 Đang xem story...")
                                    time.sleep(random.uniform(3, 6))
                                    # Thoát story
                                    try:
                                        close_btn = self.driver.find_element(By.CSS_SELECTOR, 
                                            "div[role='button'] svg[aria-label='Đóng'], div[role='button'] svg[aria-label='Close']")
                                        self.driver.execute_script("arguments[0].click();", close_btn.find_element(By.XPATH, ".."))
                                    except:
                                        self.driver.get("https://www.instagram.com/")
                                    time.sleep(random.uniform(1, 2))
                                    break
                        stories_watched = True
                    except:
                        pass
                
                # Scroll ngẫu nhiên
                scroll_amount = random.randint(300, 800)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                scroll_count += 1
                
                # Di chuột ngẫu nhiên
                self._random_mouse_movement()
                
                # Dừng lại để "xem" bài viết
                pause_time = random.uniform(FEED_SCROLL_PAUSE_MIN, FEED_SCROLL_PAUSE_MAX)
                
                # Thỉnh thoảng like bài viết nếu bật
                if ENABLE_FEED_LIKE and random.random() < 0.2:  # 20% cơ hội like
                    try:
                        like_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                            "svg[aria-label='Thích'], svg[aria-label='Like'], span._aamw button")
                        visible_likes = [btn for btn in like_buttons if btn.is_displayed()]
                        if visible_likes:
                            like_btn = random.choice(visible_likes[:3])
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", like_btn)
                            time.sleep(random.uniform(0.5, 1.5))
                            try:
                                self.driver.execute_script("arguments[0].click();", like_btn)
                                self._update_status("🌿 Đã like một bài viết")
                            except:
                                pass
                            pause_time += random.uniform(1, 2)
                    except:
                        pass
                
                # Đếm ngược thời gian còn lại
                remaining = int(browse_duration - (time.time() - start_time))
                if remaining > 0:
                    self._update_status(f"🌿 Lướt feed... còn {remaining}s")
                
                time.sleep(pause_time)
                
                # Thỉnh thoảng scroll lên
                if scroll_count >= 3 and random.random() < 0.3:
                    self.driver.execute_script("window.scrollBy(0, -400);")
                    scroll_count = 0
                    time.sleep(random.uniform(1, 2))
                
                # Xử lý popup nếu có
                self._handle_popups()
            
            self._update_status(f"🌿 Kết thúc lướt feed sau {browse_duration}s")
            
        except Exception as e:
            self._update_status(f"Lỗi khi lướt feed: {str(e)[:30]}", "warning")
        
    def init_driver(self):
        if not self.driver:
            try:
                self._update_status("Khởi tạo driver...")
                with self.driver_lock:
                    self.driver = create_chrome_driver(self.account_data)
                self.driver.set_page_load_timeout(60)
                self.driver.set_script_timeout(30)
                self._update_status("Driver sẵn sàng")
                return True
            except Exception as e:
                self._update_status(f"Lỗi driver: {str(e)[:30]}", "error")
                return False
        return True
    
    def login_with_cookies(self):
        if self.is_logged_in:
            self._update_status("Đã đăng nhập từ trước, bỏ qua...")
            return True
        try:
            if not self.init_driver():
                return False
            self._update_status("Đang truy cập Instagram...")
            try:
                self.driver.set_page_load_timeout(60)
                self.driver.get("https://www.instagram.com/")
            except TimeoutException:
                self._update_status("Timeout tải trang, tiếp tục...")
                self.driver.execute_script("window.stop();")
            time.sleep(random.uniform(4, 7))
            self._update_status("Đang thêm cookie...")
            cookie_dict = {}
            for item in self.cookies.split('; '):
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookie_dict[key] = value
            cookie_count = 0
            for name, value in cookie_dict.items():
                try:
                    if name.lower() in ['expires', 'max-age', 'domain', 'path', 'secure', 'httponly', 'samesite']:
                        continue
                    cookie = {
                        'name': name,
                        'value': value,
                        'domain': '.instagram.com',
                        'path': '/',
                        'secure': True,
                        'httpOnly': False
                    }
                    try:
                        self.driver.add_cookie(cookie)
                        cookie_count += 1
                    except:
                        cookie['domain'] = 'www.instagram.com'
                        try:
                            self.driver.add_cookie(cookie)
                            cookie_count += 1
                        except:
                            pass
                except:
                    pass
            self._update_status(f"Đã thêm {cookie_count} cookie")
            self._update_status("Đang refresh trang...")
            self.driver.refresh()
            self._update_status("Đợi Instagram xử lý...")
            time.sleep(random.uniform(7, 10))
            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()
            login_success = False
            if "instagram.com/accounts/login" not in current_url and "login" not in current_url:
                login_success = True
            if not login_success:
                try:
                    profile_elements = self.driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Trang cá nhân'], img[alt*='profile'], a[href*='accounts/edit']")
                    if profile_elements:
                        login_success = True
                except:
                    pass
            if login_success:
                self.is_logged_in = True
                self._update_status("Đăng nhập thành công!")
                try:
                    for cookie in self.driver.get_cookies():
                        if cookie['name'] == 'ds_user_id':
                            self.user_id = cookie['value']
                        if cookie['name'] == 'sessionid' and 'userid' in cookie.get('value', ''):
                            parts = cookie['value'].split('%')
                            if len(parts) > 0 and parts[0].isdigit():
                                self.user_id = parts[0]
                    self.driver.get("https://www.instagram.com/accounts/edit/")
                    time.sleep(random.uniform(2, 4))
                    username_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[name='username']")
                    if username_inputs:
                        self.username = username_inputs[0].get_attribute('value')
                        self._update_status(f"Username: {self.username}")
                except:
                    pass
                if not self.username:
                    self.username = "account_" + str(self.user_id)[-6:] if self.user_id else "unknown"
                    self._update_status(f"Username: {self.username}")
                self._random_scroll()
                self._random_mouse_movement()
                self._handle_popups()
                self._handle_notifications()
                self._handle_save_password()
                time.sleep(random.uniform(2, 5))
                return True
            else:
                self._update_status("Đăng nhập thất bại - Cookie hết hạn", "error")
                return False
        except Exception as e:
            self._update_status(f"Lỗi đăng nhập: {str(e)[:30]}", "error")
            return False
    
    def FOLLOW(self, username_to_follow):
        self._wait_for_rate_limit()
        try:
            self._update_status(f"Đang follow: {username_to_follow}")
            clean_username = str(username_to_follow).strip().replace('@', '')
            profile_url = f"https://www.instagram.com/{clean_username}/"
            self._handle_popups()
            try:
                self.driver.set_page_load_timeout(60)
                self.driver.get(profile_url)
            except TimeoutException:
                self._update_status("Timeout tải trang, dừng tải...")
                self.driver.execute_script("window.stop();")
                time.sleep(random.uniform(2, 4))
            self._random_scroll()
            self._random_mouse_movement()
            self._handle_popups()
            self._handle_notifications()
            self._handle_save_password()
            time.sleep(random.uniform(4, 7))
            page_source = self.driver.page_source
            if "Sorry, this page isn't available" in page_source or "Trang này không khả dụng" in page_source or "Page not found" in page_source:
                error_msg = f"User không tồn tại: {clean_username}"
                self._update_status(error_msg, "error")
                self.error_count += 1
                self._human_delay()
                return {"status": False, "message": error_msg}
            if "This account is private" in page_source or "Tài khoản này ở chế độ riêng tư" in page_source:
                self._update_status(f"User private: {clean_username}", "warning")
            follow_selectors = [
                "//button[text()='Follow']", "//button[text()='Theo dõi']",
                "//button[contains(text(), 'Follow')]", "//button[contains(text(), 'Theo dõi')]",
                "//div[text()='Follow']", "//div[text()='Theo dõi']",
                "//div[contains(text(), 'Follow')]", "//div[contains(text(), 'Theo dõi')]",
                "button._acan._acap._acas", "button._acan._acap._acat",
                "button[aria-label='Follow']", "button[aria-label='Theo dõi']",
                "//div[@role='button' and contains(., 'Follow')]"
            ]
            follow_button = None
            for selector in follow_selectors:
                try:
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            text = elem.text.lower()
                            if 'follow' in text or 'theo dõi' in text:
                                follow_button = elem
                                break
                    if follow_button:
                        break
                except:
                    continue
            following_selectors = [
                "//button[contains(., 'Following')]", "//button[contains(., 'Đang follow')]",
                "//div[contains(., 'Following') and @role='button']",
                "button[aria-label='Following']"
            ]
            for selector in following_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            self._update_status(f"Đã follow {clean_username} trước đó")
                            self._human_delay()
                            return {"status": False, "message": "Đã follow trước đó"}
                except:
                    continue
            if follow_button:
                self._update_status(f"Tìm thấy nút Follow")
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                actions.move_to_element(follow_button).perform()
                time.sleep(random.uniform(0.5, 1.5))
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", follow_button)
                time.sleep(random.uniform(1.5, 3))
                try:
                    follow_button.click()
                    self._update_status("Đã click nút Follow")
                except:
                    try:
                        self.driver.execute_script("arguments[0].click();", follow_button)
                        self._update_status("Đã click nút Follow (JavaScript)")
                    except:
                        try:
                            actions.click().perform()
                            self._update_status("Đã click nút Follow (ActionChains)")
                        except:
                            pass
                time.sleep(random.uniform(3, 5))
                self._handle_popups()
                for selector in following_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        for elem in elements:
                            if elem.is_displayed():
                                self._update_status(f"Follow thành công: {clean_username}")
                                self.error_count = 0
                                self._random_activity_break()
                                self._human_delay()
                                return {"status": True, "message": "Follow thành công"}
                    except:
                        continue
                self._update_status(f"Đã click Follow nhưng không xác nhận được", "warning")
                self._human_delay()
                return {"status": True, "message": "Đã click Follow"}
            else:
                error_msg = f"Không tìm thấy nút Follow cho {clean_username}"
                self._update_status(error_msg, "error")
                self.error_count += 1
                self._human_delay()
                return {"status": False, "message": error_msg}
        except Exception as e:
            self.error_count += 1
            error_msg = str(e)
            self._update_status(f"Lỗi follow: {error_msg[:30]}", "error")
            self._human_delay()
            return {"status": False, "message": f"Lỗi: {error_msg}"}
    
    def LIKE(self, post_url):
        self._wait_for_rate_limit()
        try:
            self._update_status(f"Đang like bài post...")
            self._handle_popups()
            try:
                self.driver.set_page_load_timeout(60)
                self.driver.get(post_url)
            except TimeoutException:
                self._update_status("Timeout tải trang, dừng tải...")
                self.driver.execute_script("window.stop();")
                time.sleep(random.uniform(2, 4))
            self._random_scroll()
            self._random_mouse_movement()
            self._handle_popups()
            time.sleep(random.uniform(4, 7))
            page_source = self.driver.page_source
            if "Sorry, this page isn't available" in page_source or "Trang này không khả dụng" in page_source:
                error_msg = "Bài post không tồn tại"
                self._update_status(error_msg, "error")
                self.error_count += 1
                self._human_delay()
                return {"status": False, "message": error_msg}
            like_selectors = [
                "svg[aria-label='Thích']", "svg[aria-label='Like']",
                "button._abl- svg", "div[role='button'] svg",
                "svg[style*='fill: rgb(255, 48, 65)']"
            ]
            like_button = None
            for selector in like_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        if "svg" in selector:
                            like_button = elements[0].find_element(By.XPATH, "..")
                        else:
                            like_button = elements[0]
                        break
                except:
                    continue
            unlike_selectors = [
                "svg[aria-label='Bỏ thích']", "svg[aria-label='Unlike']",
                "svg[style*='fill: rgb(237, 73, 86)']"
            ]
            for selector in unlike_selectors:
                try:
                    if self.driver.find_elements(By.CSS_SELECTOR, selector):
                        self._update_status("Đã like bài post trước đó")
                        self._human_delay()
                        return {"status": False, "message": "Đã like trước đó"}
                except:
                    continue
            if like_button and like_button.is_displayed():
                self._update_status(f"Tìm thấy nút Like")
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                actions.move_to_element(like_button).perform()
                time.sleep(random.uniform(0.5, 1))
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", like_button)
                time.sleep(random.uniform(1.5, 3))
                try:
                    self.driver.execute_script("arguments[0].click();", like_button)
                    self._update_status("Đã click nút Like")
                except:
                    try:
                        like_button.click()
                        self._update_status("Đã click nút Like (click thường)")
                    except:
                        error_msg = "Không thể click nút Like"
                        self._update_status(error_msg, "error")
                        self.error_count += 1
                        self._human_delay()
                        return {"status": False, "message": error_msg}
                time.sleep(random.uniform(2, 4))
                for selector in unlike_selectors:
                    try:
                        if self.driver.find_elements(By.CSS_SELECTOR, selector):
                            self._update_status("Like thành công!")
                            self.error_count = 0
                            self._random_activity_break()
                            self._human_delay()
                            return {"status": True, "message": "Like thành công"}
                    except:
                        continue
                self._update_status("Đã click Like nhưng không xác nhận được", "warning")
                self._human_delay()
                return {"status": True, "message": "Đã click Like"}
            else:
                error_msg = "Không tìm thấy nút Like"
                self._update_status(error_msg, "error")
                self.error_count += 1
                self._human_delay()
                return {"status": False, "message": error_msg}
        except Exception as e:
            self.error_count += 1
            error_msg = str(e)
            self._update_status(f"Lỗi like: {error_msg[:30]}", "error")
            self._human_delay()
            return {"status": False, "message": f"Lỗi: {error_msg}"}
    
    def COMMENT(self, post_url, comment_text):
        self._wait_for_rate_limit()
        try:
            self._update_status(f"Đang comment...")
            if not comment_text or comment_text.strip() == '':
                error_msg = "Job comment không có nội dung - bỏ qua"
                self._update_status(error_msg, "warning")
                return {"status": False, "skip": True, "message": error_msg}
            self._handle_popups()
            try:
                self.driver.set_page_load_timeout(60)
                self.driver.get(post_url)
            except TimeoutException:
                self._update_status("Timeout tải trang, dừng tải...")
                self.driver.execute_script("window.stop();")
                time.sleep(random.uniform(2, 4))
            self._random_scroll()
            self._random_mouse_movement()
            self._handle_popups()
            time.sleep(random.uniform(4, 7))
            page_source = self.driver.page_source
            if "Sorry, this page isn't available" in page_source or "Trang này không khả dụng" in page_source:
                error_msg = "Bài post không tồn tại"
                self._update_status(error_msg, "error")
                self.error_count += 1
                self._human_delay()
                return {"status": False, "message": error_msg}
            comment_icon_selectors = [
                "svg[aria-label='Bình luận']", "svg[aria-label='Comment']",
                "//*[@aria-label='Bình luận']", "//*[@aria-label='Comment']",
                "button[aria-label='Bình luận']"
            ]
            comment_icon = None
            for selector in comment_icon_selectors:
                try:
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        comment_icon = elements[0]
                        self._update_status("Tìm thấy icon bình luận")
                        break
                except:
                    continue
            if comment_icon:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", comment_icon)
                    time.sleep(random.uniform(1, 2))
                    self.driver.execute_script("arguments[0].click();", comment_icon)
                    self._update_status("Đã click icon bình luận")
                    time.sleep(random.uniform(1.5, 3))
                except:
                    self._update_status("Không thể click icon bình luận, vẫn thử tìm textarea...")
            comment_selectors = [
                "textarea[aria-label='Thêm bình luận...']", "textarea[aria-label='Add a comment...']",
                "textarea[placeholder='Thêm bình luận...']", "form textarea",
                "textarea._aaoc", "div[role='textbox']"
            ]
            comment_input = None
            for selector in comment_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            comment_input = elem
                            break
                    if comment_input:
                        break
                except:
                    continue
            if comment_input:
                self._update_status(f"Tìm thấy ô comment")
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", comment_input)
                time.sleep(random.uniform(1.5, 3))
                try:
                    comment_input.click()
                except:
                    self.driver.execute_script("arguments[0].click();", comment_input)
                time.sleep(random.uniform(1, 2))
                comment_input.clear()
                time.sleep(random.uniform(0.3, 0.7))
                self._human_keystroke(comment_input, comment_text)
                self._update_status("Đã nhập nội dung comment")
                time.sleep(random.uniform(1.5, 3))
                post_selectors = [
                    "//div[contains(text(), 'Đăng')]", "//div[contains(text(), 'Post')]",
                    "//button[contains(text(), 'Đăng')]", "//button[contains(text(), 'Post')]",
                    "button._acan._acap._acat", "form button"
                ]
                post_button = None
                for selector in post_selectors:
                    try:
                        if selector.startswith("//"):
                            elements = self.driver.find_elements(By.XPATH, selector)
                        else:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            if elem.is_displayed() and elem.is_enabled():
                                post_button = elem
                                break
                        if post_button:
                            break
                    except:
                        continue
                if post_button:
                    self._update_status("Đang đăng comment...")
                    try:
                        post_button.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", post_button)
                    time.sleep(random.uniform(2, 4))
                    self._update_status("Comment thành công!")
                    self.error_count = 0
                    self._random_activity_break()
                    self._human_delay()
                    return {"status": True, "message": "Comment thành công"}
                else:
                    self._update_status("Không tìm thấy nút Post, thử nhấn Enter...")
                    comment_input.send_keys(Keys.RETURN)
                    time.sleep(random.uniform(2, 4))
                    self._update_status("Đã gửi comment bằng Enter")
                    self.error_count = 0
                    self._random_activity_break()
                    self._human_delay()
                    return {"status": True, "message": "Comment thành công"}
            else:
                error_msg = "Không tìm thấy ô comment"
                self._update_status(error_msg, "error")
                self.error_count += 1
                self._human_delay()
                return {"status": False, "message": error_msg}
        except Exception as e:
            self.error_count += 1
            error_msg = str(e)
            self._update_status(f"Lỗi comment: {error_msg[:30]}", "error")
            self._human_delay()
            return {"status": False, "message": f"Lỗi: {error_msg}"}
    
    def close(self):
        if self.driver:
            try:
                with self.driver_lock:
                    self.driver.quit()
            except:
                pass
            self.driver = None
            self.is_logged_in = False

# ========== CẤU HÌNH SELENIUM THEO MÔI TRƯỜNG ==========
def create_chrome_driver(account_data=None):
    if account_data:
        update_account_status(account_data, "Kiểm tra trình duyệt...")
    chrome_installed, chrome_path = check_chrome_installed(account_data)
    if not chrome_installed:
        raise Exception("Chrome/Chromium chưa được cài đặt.")
    chrome_options = Options()
    profile_path = get_profile_path(account_data)
    chrome_options.add_argument(f'--user-data-dir={profile_path}')
    chrome_options.add_argument(f'--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}')
    chrome_options.add_argument('--window-position=0,0')
    zoom_value = random.uniform(0.25, 0.30)
    chrome_options.add_argument(f'--force-device-scale-factor={zoom_value}')
    
    # Sử dụng User Agent từ cấu hình riêng hoặc random
    username = account_data.get("username") if account_data else None
    user_agent = get_user_agent_for_driver(username)
    chrome_options.add_argument(f'--user-agent={user_agent}')
    
    # Sử dụng Proxy từ cấu hình riêng
    proxy_url = account_data.get("proxy") if account_data else None
    if proxy_url:
        chrome_options.add_argument(f'--proxy-server={proxy_url}')
        update_account_status(account_data, f"Dùng proxy: {proxy_url[:30]}...")
    
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--disable-features=VizDisplayCompositor')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-plugins')
    if DISABLE_IMAGES:
        chrome_options.add_argument('--disable-images')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--lang=vi-VN')
    chrome_options.add_argument('--memory-pressure-off')
    chrome_options.add_argument('--max_old_space_size=512')
    chrome_options.add_argument('--js-flags=--max-old-space-size=512')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument('--silent')
    if RUNNING_IN_TERMUX:
        chrome_options.add_argument('--single-process')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.images": 2 if DISABLE_IMAGES else 1,
    })
    if RUNNING_IN_TERMUX:
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-setuid-sandbox')
        chrome_options.add_argument('--disable-session-crashed-bubble')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--hide-scrollbars')
        if chrome_path:
            chrome_options.binary_location = chrome_path
    else:
        chrome_options.add_argument('--disable-logging')
    driver = None
    errors = []
    if RUNNING_IN_TERMUX:
        chromedriver_path = find_chromedriver_in_termux()
        if chromedriver_path:
            try:
                if account_data:
                    update_account_status(account_data, f"Khởi tạo driver (profile: {os.path.basename(profile_path)})")
                service = Service(executable_path=chromedriver_path, service_args=['--verbose', '--log-path=chromedriver.log'])
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.set_page_load_timeout(60)
                driver.set_script_timeout(30)
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                try:
                    driver.execute_script(f"document.body.style.zoom = '{zoom_value}'")
                except:
                    pass
                if account_data:
                    update_account_status(account_data, "Driver sẵn sàng")
                return driver
            except Exception as e:
                errors.append(f"Lỗi driver: {str(e)[:30]}")
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        chromedriver_path = ChromeDriverManager().install()
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        try:
            driver.execute_script(f"document.body.style.zoom = '{zoom_value}'")
        except:
            pass
        if account_data:
            update_account_status(account_data, f"Driver sẵn sàng (profile: {os.path.basename(profile_path)})")
        return driver
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "webdriver-manager"])
            from webdriver_manager.chrome import ChromeDriverManager
            chromedriver_path = ChromeDriverManager().install()
            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(60)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            try:
                driver.execute_script(f"document.body.style.zoom = '{zoom_value}'")
            except:
                pass
            if account_data:
                update_account_status(account_data, "Driver sẵn sàng")
            return driver
        except Exception as e:
            errors.append(f"Lỗi cài webdriver-manager: {str(e)[:30]}")
    except Exception as e:
        errors.append(f"Lỗi webdriver-manager: {str(e)[:30]}")
    try:
        if not RUNNING_IN_TERMUX:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(60)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            try:
                driver.execute_script(f"document.body.style.zoom = '{zoom_value}'")
            except:
                pass
            if account_data:
                update_account_status(account_data, "Driver sẵn sàng (mặc định)")
            return driver
    except Exception as e:
        errors.append(f"Lỗi driver mặc định: {str(e)[:30]}")
    error_message = "\nKHÔNG THỂ KHỞI TẠO CHROME DRIVER!\n"
    for err in errors:
        error_message += f"  - {err}\n"
    raise Exception(error_message)

# ========== Các hàm xử lý job ==========
def handle_follow_job(bot, data, account_id, account_data):
    global stop_threads
    if stop_threads:
        return {"status": False, "message": "Thread dừng"}
    username_to_follow = extract_username_from_job_data(data)
    if not username_to_follow:
        error_msg = "Không thể trích xuất username từ job data"
        update_account_status(account_data, error_msg, "error")
        return {"status": False, "skip": True}
    username_to_follow = username_to_follow.lower()
    try:
        result = bot.FOLLOW(username_to_follow)
        if result and result.get('status'):
            update_account_status(account_data, f"Follow thành công {username_to_follow}")
            return {"status": True, "message": result.get('message', 'Follow thành công')}
        else:
            error_msg = result.get('message', 'Lỗi không xác định') if result else "Không có phản hồi từ bot"
            update_account_status(account_data, f"Follow thất bại: {error_msg[:50]}", "warning")
            if kiem_tra_checkpoint(error_msg):
                increment_error(account_data, 'checkpoint')
                update_account_status(account_data, "CHECKPOINT - Dừng tài khoản", "error")
                account_data["is_running"] = False
                return {"status": False, "message": error_msg, "fatal": True, "checkpoint": True}
            if kiem_tra_rate_limit(error_msg):
                increment_error(account_data, 'rate_limit')
                wait_time = random.randint(60, 120)
                account_data["rate_limit_until"] = time.time() + wait_time
                return {"status": False, "message": error_msg, "retry": True, "wait": wait_time}
            increment_error(account_data, 'follow')
            return {"status": False, "message": error_msg}
    except Exception as e:
        increment_error(account_data, 'other')
        error_msg = str(e)
        update_account_status(account_data, f"Lỗi: {error_msg[:20]}", "error")
        return {"status": False, "message": f"exception: {error_msg}"}

def handle_like_job(bot, link, account_id, account_data):
    global stop_threads
    if stop_threads:
        return {"status": False, "message": "Thread dừng"}
    update_account_status(account_data, "Đang xử lý like...")
    try:
        result = bot.LIKE(link)
        if result['status']:
            update_account_status(account_data, "Like thành công")
            return {"status": True, "message": result.get('message', 'Like thành công')}
        else:
            error_msg = result.get('message', 'Lỗi không xác định')
            update_account_status(account_data, f"Like thất bại: {error_msg}", "warning")
            if kiem_tra_checkpoint(error_msg):
                increment_error(account_data, 'checkpoint')
                update_account_status(account_data, "CHECKPOINT - Dừng tài khoản", "error")
                account_data["is_running"] = False
                return {"status": False, "message": error_msg, "fatal": True, "checkpoint": True}
            if kiem_tra_rate_limit(error_msg):
                increment_error(account_data, 'rate_limit')
                wait_time = random.randint(60, 120)
                account_data["rate_limit_until"] = time.time() + wait_time
                return {"status": False, "message": error_msg, "retry": True, "wait": wait_time}
            increment_error(account_data, 'like')
            return {"status": False, "message": error_msg}
    except Exception as e:
        increment_error(account_data, 'other')
        error_msg = f"exception: {str(e)[:50]}"
        update_account_status(account_data, f"Lỗi: {str(e)[:30]}", "error")
        return {"status": False, "message": error_msg}

def handle_comment_job(bot, link, comment_text, account_id, account_data):
    global stop_threads
    if stop_threads:
        return {"status": False, "message": "Thread dừng"}
    if not comment_text or comment_text == '' or comment_text.strip() == '':
        error_msg = "Job comment không có nội dung - bỏ qua"
        update_account_status(account_data, error_msg, "warning")
        return {"status": False, "skip": True, "message": error_msg}
    update_account_status(account_data, "Đang xử lý comment...")
    try:
        result = bot.COMMENT(link, comment_text)
        if result['status']:
            update_account_status(account_data, "Comment thành công")
            return {"status": True, "message": result.get('message', 'Comment thành công')}
        else:
            error_msg = result.get('message', 'Lỗi không xác định')
            update_account_status(account_data, f"Comment thất bại: {error_msg}", "warning")
            if kiem_tra_checkpoint(error_msg):
                increment_error(account_data, 'checkpoint')
                update_account_status(account_data, "CHECKPOINT - Dừng tài khoản", "error")
                account_data["is_running"] = False
                return {"status": False, "message": error_msg, "fatal": True, "checkpoint": True}
            if kiem_tra_rate_limit(error_msg):
                increment_error(account_data, 'rate_limit')
                wait_time = random.randint(60, 120)
                account_data["rate_limit_until"] = time.time() + wait_time
                return {"status": False, "message": error_msg, "retry": True, "wait": wait_time}
            increment_error(account_data, 'comment')
            return {"status": False, "message": error_msg}
    except Exception as e:
        increment_error(account_data, 'other')
        error_msg = f"exception: {str(e)[:50]}"
        update_account_status(account_data, f"Lỗi: {str(e)[:30]}", "error")
        return {"status": False, "message": error_msg}

# ========== Các hàm kiểm tra lỗi ==========
def increment_error(account_data, error_type='other'):
    if "error_counts" not in account_data:
        account_data["error_counts"] = {'follow': 0, 'like': 0, 'comment': 0, 'checkpoint': 0, 'rate_limit': 0, 'other': 0}
    account_data["error_counts"][error_type] = account_data["error_counts"].get(error_type, 0) + 1
    account_data["session_errors"] = account_data.get("session_errors", 0) + 1
    account_data["last_error_time"] = time.time()

def kiem_tra_cookie_die(error_msg, status_code):
    cookie_die_messages = [
        'login_required', 'checkpoint_required', 'forbidden',
        'not_authorized', 'unauthorized', 'invalid_token',
        'The access token is invalid', 'cookie invalid'
    ]
    if status_code in [401, 403]:
        return True
    if any(msg in str(error_msg).lower() for msg in cookie_die_messages):
        return True
    return False

def kiem_tra_checkpoint(error_msg):
    checkpoint_messages = ['checkpoint_required', 'checkpoint', 'challenge_required', 'challenge']
    if any(msg in str(error_msg).lower() for msg in checkpoint_messages):
        return True
    return False

def kiem_tra_rate_limit(error_msg):
    if "429" in str(error_msg):
        return True
    rate_messages = ['rate_limit', 'too many requests', 'please wait', 'rate limit', '429']
    if any(msg in str(error_msg).lower() for msg in rate_messages):
        return True
    return False

# ========== Hàm gọi API Golike ==========
def chonacc(headers):
    url = 'https://gateway.golike.net/api/instagram-account'
    with api_lock:
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            try:
                result = response.json()
            except:
                result = {}
            if response.status_code == 200:
                if isinstance(result, dict) and (result.get('status') == 200 or result.get('success') == True):
                    return {"status": True, "data": result.get('data', [])}
                else:
                    error_msg = result.get('message') or result.get('msg') or f"HTTP {response.status_code}"
                    return {"status": False, "message": error_msg}
            else:
                error_msg = result.get('message') or result.get('msg') or f"HTTP {response.status_code}"
                return {"status": False, "message": error_msg}
        except requests.exceptions.Timeout:
            return {"status": False, "message": "Timeout khi kết nối Golike"}
        except requests.exceptions.ConnectionError:
            return {"status": False, "message": "Lỗi kết nối Golike"}
        except Exception as e:
            return {"status": False, "message": str(e)}

def nhannv(account_id, headers):
    params = {'instagram_account_id': account_id, 'data': 'null'}
    url = 'https://gateway.golike.net/api/advertising/publishers/instagram/jobs'
    with api_lock:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=20, verify=False)
            try:
                result = response.json()
            except:
                result = {}
            if response.status_code == 200:
                if isinstance(result, dict) and (result.get('status') == 200 or result.get('success') == True):
                    return {"status": True, "data": result.get('data')}
                else:
                    error_msg = result.get('message') or result.get('msg') or f"HTTP {response.status_code}"
                    return {"status": False, "message": error_msg}
            else:
                error_msg = result.get('message') or result.get('msg') or f"HTTP {response.status_code}"
                return {"status": False, "message": error_msg}
        except requests.exceptions.Timeout:
            return {"status": False, "message": "Timeout khi kết nối Golike"}
        except requests.exceptions.ConnectionError:
            return {"status": False, "message": "Lỗi kết nối Golike"}
        except Exception as e:
            return {"status": False, "message": str(e)}

def hoanthanh(ads_id, account_id, headers):
    json_data = {
        'instagram_users_advertising_id': ads_id,
        'instagram_account_id': account_id,
        'async': True,
        'data': None
    }
    with api_lock:
        try:
            response = requests.post('https://gateway.golike.net/api/advertising/publishers/instagram/complete-jobs',
                                     headers=headers, json=json_data, timeout=15, verify=False)
            try:
                result = response.json()
            except:
                result = {}
            if response.status_code == 200:
                if isinstance(result, dict) and (result.get('status') == 200 or result.get('success') == True):
                    return {"status": True, "data": result.get('data'), "message": result.get('message', 'Success')}
                else:
                    error_msg = result.get('message') or result.get('msg') or f"HTTP {response.status_code}"
                    return {"status": False, "message": error_msg}
            else:
                error_msg = result.get('message') or result.get('msg') or f"HTTP {response.status_code}"
                return {"status": False, "message": error_msg}
        except requests.exceptions.Timeout:
            return {"status": False, "message": "Timeout khi hoàn thành"}
        except requests.exceptions.ConnectionError:
            return {"status": False, "message": "Lỗi kết nối khi hoàn thành"}
        except Exception as e:
            return {"status": False, "message": str(e)}

def baoloi(ads_id, object_id, account_id, loai, headers):
    json_data1 = {
        'description': 'Đã làm Job này rồi',
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
    with api_lock:
        try:
            response = requests.post('https://gateway.golike.net/api/advertising/publishers/instagram/skip-jobs',
                                    headers=headers, json=json_data, timeout=8, verify=False)
            try:
                result = response.json()
            except:
                result = {}
            if response.status_code == 200:
                if isinstance(result, dict) and (result.get('status') == 200 or result.get('success') == True):
                    return {"status": True, "message": result.get('message', 'Success')}
                else:
                    error_msg = result.get('message') or result.get('msg') or f"HTTP {response.status_code}"
                    return {"status": False, "message": error_msg}
            else:
                error_msg = result.get('message') or result.get('msg') or f"HTTP {response.status_code}"
                return {"status": False, "message": error_msg}
        except Exception as e:
            return {"status": False, "message": str(e)}

# ========== Hàm banner ==========
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

\033[38;2;255;200;140m[</>]\033[38;2;245;245;245m ADMIN: \033[38;2;200;160;255mNHƯ ANH ĐÃ THẤY EM   \033[38;2;255;220;160mPhiên Bản: \033[38;2;120;255;220mv3.7 (Nuôi Nick)
\033[38;2;255;200;140m[</>]\033[38;2;245;245;245m Nhóm Telegram: \033[38;2;120;255;220mhttps://t.me/se_meo_bao_an
\033[38;2;190;235;210m───────────────────────────────────────────────────────────────────────\033[0m
"""
    print(banner_text)

# ========== HÀM XÂY DỰNG BẢNG DASHBOARD ==========
def build_table():
    table = Table(
    title="[bold #ffffff]DASHBOARD INSTAGRAM TOOL[/]",
    box=box.SQUARE,
    border_style="#ff9ecb",
    show_header=True,
    header_style="#ffffff",
    show_lines=True
)
    table.add_column("STT", justify="center", style="#8b8b8b", width=4)
    table.add_column("Username", style="#4dd6ff", width=12)
    table.add_column("Nick Golike", style="#ff9ecb", width=12)
    table.add_column("Trạng thái", justify="center", style="#ff5c7a", width=12)
    table.add_column("Đã làm", justify="center", style="#39ff88", width=6)
    table.add_column("Bỏ qua", justify="center", style="#ff9f43", width=6)
    table.add_column("Follow", justify="center", style="#6c7bff", width=5)
    table.add_column("Like", justify="center", style="#ffd166", width=5)
    table.add_column("Comment", justify="center", style="#00e5ff", width=6)
    table.add_column("Coin", justify="center", style="#f7b731", width=5)
    table.add_column("Chi tiết", style="#ffffff", width=25)
    for i, (acc_id, data) in enumerate(all_accounts_data.items(), 1):
        if not data.get("is_running", True):
            status = "Đã dừng"
            status_color = "red"
        elif "checkpoint" in data.get("status", "").lower():
            status = "CHECKPOINT"
            status_color = "red"
        elif data.get("rate_limit_until", 0) > time.time():
            status = "RATE LIMIT"
            status_color = "yellow"
        elif "nuôi" in data.get("detail_status", "").lower() or "lướt" in data.get("detail_status", "").lower():
            status = "NUÔI NICK"
            status_color = "#00ffff"
        else:
            status = "ĐANG CHẠY"
            status_color = "green"
        detail = data.get("detail_status", data.get("status", ""))
        if len(detail) > 25:
            detail = detail[:22] + "..."
        golike_name = data.get("golike_username", "-")[:10]
        table.add_row(
            str(i),
            data.get("username", "")[:10],
            golike_name,
            f"[{status_color}]{status}[/{status_color}]",
            str(data.get("done", 0)),
            str(data.get("skip", 0)),
            str(data.get("follow", 0)),
            str(data.get("like", 0)),
            str(data.get("comment", 0)),
            str(data.get("coin", 0)),
            detail
        )
    return table

def countdown_delay(account_id, account_data, total_seconds, message="Đợi"):
    global stop_threads
    if total_seconds > 10:
        variation = random.uniform(-2, 2)
        total_seconds = max(3, total_seconds + variation)
    
    # Nếu delay dài (>15s) và có bot, thì lướt newsfeed thay vì đứng im
    if total_seconds > 15 and account_id in bot_instances and ENABLE_FEED_BROWSING:
        bot = bot_instances.get(account_id)
        if bot and bot.is_logged_in:
            # Lướt feed thay vì đếm ngược đứng im
            update_account_status(account_data, f" Nuôi nick: lướt feed {int(total_seconds)}s")
            bot.browse_newsfeed(duration=total_seconds)
            return
    
    for i in range(int(total_seconds), 0, -1):
        if stop_threads:
            return
        update_account_status(account_data, f"{message} {i}s")
        time.sleep(1)

# ========== Hàm chạy cho mỗi account ==========
def run_account(account_id, account_data, headers, lam, delay_config, lannhan, doiacc, job_nghi, thoi_gian_nghi):
    global stop_threads, bot_instances
    
    account_data["thread_id"] = threading.current_thread().ident
    cookies = account_data["cookie"]
    username = account_data["username"]
    checkdoiacc = 0
    last_feed_browse_time = time.time()
    feed_browse_interval = random.randint(300, 600)  # 5-10 phút lướt feed 1 lần
    
    try:
        bot = INSTAGRAM(cookies, account_data)
        update_account_status(account_data, "Đang đăng nhập...")
        login_success = bot.login_with_cookies()
        if not login_success:
            update_account_status(account_data, "Đăng nhập thất bại", "error")
            account_data["is_running"] = False
            return
        bot_instances[account_id] = bot
        update_account_status(account_data, "Đăng nhập thành công")
        
        # Lướt feed lần đầu sau khi đăng nhập để tăng trust
        if ENABLE_FEED_BROWSING:
            update_account_status(account_data, " Lướt feed khởi động...")
            bot.browse_newsfeed(duration=random.randint(10, 20))
            last_feed_browse_time = time.time()
            
    except Exception as e:
        update_account_status(account_data, f"Lỗi: {str(e)[:30]}", "error")
        account_data["is_running"] = False
        return
    
    update_account_status(account_data, "Bắt đầu chạy...")
    account_data["is_running"] = True
    
    delay_job_range = delay_config.get("job", [3, 7])
    delay_done = delay_config.get("done", 5)
    delay_error = delay_config.get("error", 10)
    
    while not stop_threads and account_data.get("is_running", True):
        try:
            if account_data.get("rate_limit_until", 0) > time.time():
                remaining = int(account_data["rate_limit_until"] - time.time())
                if remaining > 0:
                    # Nếu bị rate limit, lướt feed nhẹ nhàng
                    if ENABLE_FEED_BROWSING and remaining > 30:
                        bot.browse_newsfeed(duration=min(remaining, 60))
                    else:
                        time.sleep(min(remaining, 5))
                    continue
            
            # Kiểm tra nếu đã lâu chưa lướt feed
            if ENABLE_FEED_BROWSING and (time.time() - last_feed_browse_time) > feed_browse_interval:
                bot.browse_newsfeed(duration=random.randint(15, 30))
                last_feed_browse_time = time.time()
                feed_browse_interval = random.randint(300, 600)
            
            if checkdoiacc >= doiacc and doiacc > 0:
                update_account_status(account_data, f"Đạt giới hạn lỗi ({doiacc})", "error")
                account_data["is_running"] = False
                break

            update_account_status(account_data, "Đang lấy job...")
            nhanjob = nhannv(account_id, headers)
            
            if isinstance(nhanjob, dict):
                if nhanjob.get('status') == True:
                    data = nhanjob.get('data')
                    if not isinstance(data, dict):
                        update_account_status(account_data, "Dữ liệu job không hợp lệ", "warning")
                        time.sleep(random.uniform(4, 7))
                        continue
                        
                    ads_id = data.get('id')
                    link = data.get('link')
                    object_id = data.get('object_id')
                    loai = data.get('type')
                    object_data = data.get('object_data', {})
                    
                    # Lấy status_message thực từ Golike
                    status_msg = extract_status_message_from_job_data(data)
                    if status_msg:
                        update_account_status(account_data, f"Nhận job: {loai} - {status_msg}")
                    else:
                        update_account_status(account_data, f"Nhận job: {loai}")
                    
                    if not isinstance(object_data, dict):
                        object_data = {}
                        
                    if not object_id or not loai:
                        update_account_status(account_data, "Thiếu thông tin job", "warning")
                        time.sleep(random.uniform(1.5, 3))
                        continue
                else:
                    msg = nhanjob.get('message', 'Không có job')
                    update_account_status(account_data, f"API: {msg}")
                    wait_time = random.randint(delay_job_range[0], delay_job_range[1])
                    
                    # Khi hết job, lướt newsfeed thay vì đứng im
                    if ENABLE_FEED_BROWSING and wait_time > 10:
                        update_account_status(account_data, f" Hết job, lướt feed {wait_time}s")
                        bot.browse_newsfeed(duration=wait_time)
                        last_feed_browse_time = time.time()
                    else:
                        countdown_delay(account_id, account_data, wait_time, "Chờ job")
                    continue
            else:
                time.sleep(random.uniform(4, 7))
                continue

            if loai not in lam:
                update_account_status(account_data, f"Bỏ qua {loai} (không trong cấu hình)")
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
                success = handle_follow_job(bot, data, account_id, account_data)
                
            elif loai == "like":
                success = handle_like_job(bot, link, account_id, account_data)
                
            elif loai == "comment":
                # SỬ DỤNG HÀM LẤY COMMENT CHUẨN TỪ GOLIKE
                comment_text = extract_comment_from_job_data(data)
                if not comment_text or comment_text.strip() == '':
                    update_account_status(account_data, "Job comment không có nội dung - bỏ qua", "warning")
                    with account_locks[account_id]:
                        account_data["skip"] += 1
                    try:
                        baoloi(ads_id, object_id, account_id, loai, headers)
                    except:
                        pass
                    time.sleep(random.uniform(1, 2))
                    continue
                update_account_status(account_data, f"Nội dung comment: {comment_text[:30]}...")
                success = handle_comment_job(bot, link, comment_text, account_id, account_data)

            if success.get('retry') and success.get('wait'):
                wait_time = success['wait']
                update_account_status(account_data, f"Rate limit - nghỉ {wait_time}s", "warning")
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
                
                # Khi nghỉ dài, lướt newsfeed
                if ENABLE_FEED_BROWSING and thoi_gian_nghi > 20:
                    bot.browse_newsfeed(duration=thoi_gian_nghi)
                    last_feed_browse_time = time.time()
                else:
                    countdown_delay(account_id, account_data, thoi_gian_nghi, "Nghỉ")

            if success.get('status'):
                update_account_status(account_data, "Đang nhận tiền...")
                try:
                    nhantien = hoanthanh(ads_id, account_id, headers)
                except Exception as e:
                    update_account_status(account_data, "Lỗi nhận tiền", "warning")
                    time.sleep(random.uniform(1.5, 3))
                    continue

                if lannhan == 'y':
                    checklan = 1
                else:
                    checklan = 2

                ok = 0
                while checklan <= 2 and not stop_threads:
                    if isinstance(nhantien, dict) and nhantien.get('status') == True:
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
                            elif loai == "comment":
                                account_data["comment"] += 1
                            update_account_status(account_data, f"Thành công +{tien} coin")
                        checkdoiacc = 0
                        break
                    checklan += 1
                    if checklan == 3:
                        break
                    time.sleep(random.uniform(2, 4))
                    try:
                        nhantien = hoanthanh(ads_id, account_id, headers)
                        if not isinstance(nhantien, dict):
                            nhantien = {"status": False, "message": "Phản hồi không hợp lệ"}
                    except:
                        nhantien = {"status": False, "message": "Exception"}

                if ok != 1:
                    error_msg = nhantien.get('message', 'Không nhận được tiền') if isinstance(nhantien, dict) else 'Không nhận được tiền'
                    update_account_status(account_data, f"Lỗi nhận tiền: {error_msg[:30]}", "warning")
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
            time.sleep(random.uniform(delay_error * 0.8, delay_error * 1.2))
            continue
    
    try:
        bot.close()
    except:
        pass
    
    with account_locks[account_id]:
        account_data["is_running"] = False
        if not account_data["status"].startswith("Dừng"):
            update_account_status(account_data, "Đã dừng")

# ========== Hàm khởi tạo và chạy tool ==========
def start_tool():
    global all_accounts_data, stop_threads, console, system_status
    
    console = Console()
    
    if not check_and_install_selenium():
        print("\033[1;31mThiếu selenium. Tool không thể chạy!")
        sys.exit(1)
    
    banner()
    current_ip = get_public_ip()
    print(f"\033[1;97m Địa chỉ IP: \033[1;32m{current_ip}")
    print("\033[1;97m═══════════════════════════════════════════════════════════════════")
    
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
    
    # Cấu hình nuôi nick
    console.print("\n[bold #00ffff]═══════════ CẤU HÌNH NUÔI NICK ═══════════[/bold #00ffff]")
    setup_feed_browsing_config()
    
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
    
    banner()
    current_ip = get_public_ip()
    print(f"\033[1;97m IP: \033[1;32m{current_ip}")
    print(f"\033[1;32m Số nick Golike: {len(selected_golike_accounts)} | Số Instagram account: {len(all_selected_accounts)}")
    print(f"\033[1;32m Chế độ job: {lam}")
    print(f"\033[1;32m Delay Follow: {delay_config['follow'][0]}-{delay_config['follow'][1]}s")
    print(f"\033[1;32m Delay Like: {delay_config['like'][0]}-{delay_config['like'][1]}s")
    print(f"\033[1;32m Delay Comment: {delay_config['comment'][0]}-{delay_config['comment'][1]}s")
    print(f"\033[1;32m Nuôi nick (lướt feed): {'BẬT' if ENABLE_FEED_BROWSING else 'TẮT'}")
    if ENABLE_FEED_BROWSING:
        print(f"\033[1;32m  Thời gian lướt: {FEED_BROWSING_MIN_DURATION}-{FEED_BROWSING_MAX_DURATION}s")
        print(f"\033[1;32m  Tự động like: {'Có' if ENABLE_FEED_LIKE else 'Không'}")
        print(f"\033[1;32m  Xem story: {'Có' if ENABLE_FEED_STORY_WATCH else 'Không'}")
    if job_nghi > 0:
        print(f"\033[1;32m Nghỉ {thoi_gian_nghi}s sau {job_nghi} job thành công")
    print(f"\033[1;32m Giới hạn lỗi: {doiacc}")
    print(f"\033[1;32m Anti-Ban: {'BẬT' if ENABLE_ANTI_BAN else 'TẮT'} | Human Behavior: {'BẬT' if ENABLE_HUMAN_BEHAVIOR else 'TẮT'}")
    print("\033[1;97m═══════════════════════════════════════════════════════════════════")
    print("\033[1;33mĐang khởi động tool đa luồng...")
    time.sleep(2)
    
    stop_threads = False
    threads = []
    
    global all_accounts_data
    all_accounts_data = all_selected_accounts
    
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
        thread_status[account_id] = "running"
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
        for bot in bot_instances.values():
            try:
                bot.close()
            except:
                pass
        cleanup_profiles()
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

# ========== Điểm vào chính ==========
if __name__ == '__main__':
    from concurrent.futures import ThreadPoolExecutor, as_completed
    start_tool()
