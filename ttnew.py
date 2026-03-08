#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import requests
from datetime import datetime
import subprocess
import uiautomator2 as u2
import random
import logging
from logging.handlers import RotatingFileHandler
import re
from difflib import SequenceMatcher
import hashlib
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import box
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.style import Style
from rich.align import Align

# Cấu hình UTF-8 cho terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình múi giờ
os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
try:
    time.tzset()
except:
    pass

# Biến toàn cục
device = None
device_serial = None
TIKTOK_PACKAGE = "com.ss.android.ugc.trill"
INSTANCE_ID = None

# Định nghĩa các file
AUTH_FILE = "Authorization.txt"
LINK_JOB_FILE = "link_job.txt"
LOG_FILE = "log_phongtus.txt"
CHECK_CMT_FILE = "check_cmt.txt"

SIMILARITY_THRESHOLD = 0.85
MIN_FOLLOW_PRICE = 0

# Biến cấu hình cho chế độ follow
FOLLOW_MODE = 1  # 1: Mở qua link (package), 2: Mở bằng tìm kiếm username

# ===== CẤU HÌNH FORCE STOP =====
FORCE_STOP_BEFORE_RUN = True   # Bật/tắt buộc dừng trước khi chạy
FORCE_STOP_EVERY_JOB = 20      # Sau bao nhiêu job thì buộc dừng app TikTok

logger = None
console = Console()

# --- CẤU TRÚC accounts_data ---
accounts_data = {}

def get_video_id(link):
    """
    Extract video ID từ link TikTok
    Ưu tiên lấy ID từ pattern /video/ID
    Nếu không có thì dùng MD5 của link để tránh trùng
    """
    try:
        # Pattern cho link dạng: /video/1234567890
        match = re.search(r'/video/(\d+)', link)
        if match:
            return match.group(1)
        
        # Pattern cho link dạng vt.tiktok.com (short link)
        match = re.search(r'tiktok\.com/(?:@[^/]+/video/|video/|)(\d+)', link)
        if match:
            return match.group(1)
        
        # Fallback: dùng MD5 của link nếu không extract được ID
        return hashlib.md5(link.encode()).hexdigest()[:10]
    except Exception as e:
        if logger:
            logger.error(f"Lỗi extract video_id từ {link}: {str(e)}")
        return link

def save_link_job(link, job_type, status, price):
    """Lưu video_id thay vì full link"""
    try:
        video_id = get_video_id(link)
        with open(LINK_JOB_FILE, 'w', encoding='utf-8') as f:
            f.write(f"{video_id}\n")
        if logger:
            logger.info(f"Đã lưu video_id: {video_id} cho job {job_type}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Lỗi lưu video_id: {str(e)}")
        return False

def is_link_processed(link):
    """
    Kiểm tra link đã làm chưa bằng cách so sánh video_id
    Thay vì so sánh full link
    """
    try:
        video_id = get_video_id(link)
        
        if os.path.exists(LINK_JOB_FILE):
            with open(LINK_JOB_FILE, 'r', encoding='utf-8') as f:
                last_video_id = f.read().strip()
            
            if last_video_id and last_video_id == video_id:
                if logger:
                    logger.info(f"Video ID {video_id} đã được xử lý trước đó")
                return True
        
        return False
    except Exception as e:
        if logger:
            logger.error(f"Lỗi kiểm tra link đã xử lý: {str(e)}")
        return False

def get_current_link():
    """Lấy video_id hiện tại đang làm"""
    try:
        if os.path.exists(LINK_JOB_FILE):
            with open(LINK_JOB_FILE, 'r', encoding='utf-8') as f:
                video_id = f.read().strip()
                if video_id:
                    return f"Video ID: {video_id}"
                return "Chưa có job"
    except:
        pass
    return "Chưa có job"

def get_status_color(status):
    """Trả về màu sắc dựa trên trạng thái"""
    status_lower = status.lower()
    if "đợi" in status_lower or "chờ" in status_lower or "đang chờ" in status_lower:
        return "yellow"
    elif "theo dõi" in status_lower:
        return "blue"
    elif "thích" in status_lower:
        return "magenta"
    elif "bình luận" in status_lower:
        return "cyan"
    elif "yêu thích" in status_lower:
        return "pink1"
    elif "hoàn thành" in status_lower or "thành công" in status_lower:
        return "green"
    elif "thất bại" in status_lower or "bỏ qua" in status_lower or "skip" in status_lower:
        return "red"
    elif "tìm nhiệm vụ" in status_lower:
        return "bright_black"
    elif "reset" in status_lower or "force stop" in status_lower:
        return "bright_red"
    else:
        return "white"

def build_table():
    """Xây dựng bảng dashboard với màu sắc theo trạng thái"""
    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    
    table.add_column("STT", style="cyan", width=4)
    table.add_column("Username", style="bright_yellow", width=15)
    table.add_column("Trạng thái", style="white", width=40)
    table.add_column("Đã làm", justify="right", style="green", width=6)
    table.add_column("Bỏ qua", justify="right", style="red", width=6)
    table.add_column("Theo dõi", justify="right", style="blue", width=6)
    table.add_column("Thích", justify="right", style="magenta", width=6)
    table.add_column("Bình luận", justify="right", style="cyan", width=6)
    table.add_column("Yêu thích", justify="right", style="pink1", width=6)
    table.add_column("Xu", justify="right", style="yellow", width=8)
    
    for acc_id, data in accounts_data.items():
        status = str(data.get("status", "Đang chờ..."))
        status_color = get_status_color(status)
        status_text = Text(status, style=status_color)
        
        table.add_row(
            str(data.get("stt", "?")),
            str(data.get("username", "?")),
            status_text,
            str(data.get("done", 0)),
            str(data.get("skip", 0)),
            str(data.get("follow", 0)),
            str(data.get("like", 0)),
            str(data.get("cmt", 0)),
            str(data.get("favorite", 0)),
            f"{data.get('coin', 0)}đ"
        )
    return table

def get_device_count():
    """Lấy số lượng thiết bị đang chạy"""
    return len(accounts_data)

def get_current_link_display():
    """Lấy link hiện tại đang làm để hiển thị"""
    try:
        if os.path.exists(LINK_JOB_FILE):
            with open(LINK_JOB_FILE, 'r', encoding='utf-8') as f:
                video_id = f.read().strip()
                if video_id:
                    if video_id.isdigit() and len(video_id) > 10:
                        return f"https://www.tiktok.com/video/{video_id}"
                    return video_id
    except:
        pass
    return "Chưa có job"

def update_dashboard():
    """Cập nhật dashboard với layout giống ảnh mẫu - KHÔNG EMOJI"""
    layout = Layout()
    
    title_panel = Panel(
        Align.center(Text("TIKTOK DASHBOARD", style="bold red")),
        style="bright_yellow",
        box=box.DOUBLE
    )
    
    total_coin = sum(acc.get('coin', 0) for acc in accounts_data.values())
    current_time = datetime.now().strftime('%H:%M:%S')
    current_date = datetime.now().strftime('%d/%m/%Y')
    
    device_text = f"{device_serial if device_serial else 'Chưa kết nối'}"
    left_panel = Panel(
        Align.center(Text(device_text, style="bold cyan")),
        title="[bold green]THIẾT BỊ[/bold green]",
        border_style="bright_blue",
        box=box.ROUNDED
    )
    
    follow_mode_text = "Mở link" if FOLLOW_MODE == 1 else "Tìm kiếm"
    middle_text = f"{total_coin}đ  |  {current_time}  |  {current_date}  |  Follow: {follow_mode_text}"
    middle_panel = Panel(
        Align.center(Text(middle_text, style="bold yellow")),
        title="[bold green]TỔNG XU & THỜI GIAN & CHẾ ĐỘ[/bold green]",
        border_style="bright_blue",
        box=box.ROUNDED
    )
    
    current_link = get_current_link_display()
    if len(current_link) > 50:
        current_link = current_link[:47] + "..."
    right_panel = Panel(
        Align.center(Text(current_link, style="bold magenta")),
        title="[bold green]LINK JOB[/bold green]",
        border_style="bright_blue",
        box=box.ROUNDED
    )
    
    info_row = Columns([left_panel, middle_panel, right_panel])
    accounts_table = build_table()
    
    layout.split_column(
        Layout(title_panel, size=3),
        Layout(info_row, size=5),
        Layout(accounts_table)
    )
    
    return layout

def init_account_data(account_id, username):
    """Khởi tạo dữ liệu account cho dashboard"""
    if account_id not in accounts_data:
        accounts_data[account_id] = {
            "username": username,
            "devices": device_serial if device_serial else "N/A",
            "done": 0,
            "skip": 0,
            "follow": 0,
            "like": 0,
            "cmt": 0,
            "favorite": 0,
            "coin": 0,
            "status": "Đang chờ...",
            "stt": len(accounts_data) + 1
        }

def update_account_stats(account_id, job_type=None, coin=0, success=True):
    """Cập nhật thống kê cho account"""
    if account_id not in accounts_data:
        return
    
    if success:
        accounts_data[account_id]["done"] += 1
        accounts_data[account_id]["coin"] += coin
        
        if job_type == "follow":
            accounts_data[account_id]["follow"] += 1
        elif job_type == "like":
            accounts_data[account_id]["like"] += 1
        elif job_type == "comment":
            accounts_data[account_id]["cmt"] += 1
        elif job_type == "favorite":
            accounts_data[account_id]["favorite"] += 1
    else:
        accounts_data[account_id]["skip"] += 1

def update_account_status(account_id, status):
    """Cập nhật trạng thái account"""
    if account_id in accounts_data:
        accounts_data[account_id]["status"] = status

def get_random_delay():
    """Trả về delay ngẫu nhiên, đảm bảo >= 1 giây"""
    return max(1, base_delay + random.randint(-delay_variation, delay_variation))

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def job(msg):
    global logger
    if logger:
        logger.info(msg)

def get_instance_files(serial):
    safe_serial = re.sub(r'[^\w\-_]', '_', serial)
    return {
        'link_job': f"device_{safe_serial}_link_job.txt",
        'log': f"device_{safe_serial}_log.txt",
        'check_cmt': f"device_{safe_serial}_check_cmt.txt"
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
                with open(file, 'w', encoding='utf-8') as f:
                    if file == LINK_JOB_FILE:
                        f.write("")
                    elif file == LOG_FILE:
                        f.write(f"# Log file - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Thiết bị: {serial}\n")
                    elif file == CHECK_CMT_FILE:
                        f.write("")
            except Exception as e:
                job(f"Lỗi tạo file {file}: {str(e)}")
                return False
    return True

def setup_instance_logging(serial):
    safe_serial = re.sub(r'[^\w\-_]', '_', serial)
    log_filename = f"device_{safe_serial}_log.txt"

    instance_logger = logging.getLogger(f"device_{safe_serial}")
    instance_logger.setLevel(logging.INFO)
    instance_logger.handlers.clear()

    file_handler = RotatingFileHandler(log_filename, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    instance_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    instance_logger.addHandler(console_handler)

    return instance_logger

def init_files():
    if not os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'a', encoding='utf-8') as f:
                f.write("")
            print("\033[1;32mĐã tạo file Authorization.txt\033[0m")
        except Exception as e:
            print(f"\033[1;31mLỗi tạo file Authorization.txt: {str(e)}\033[0m")
            return False
    return True

def read_auth():
    try:
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return content if content else None
        return None
    except Exception as e:
        job(f"Lỗi đọc file auth: {str(e)}")
        return None

def save_auth(auth):
    try:
        with open(AUTH_FILE, 'w', encoding='utf-8') as f:
            f.write(auth)
        job("Đã lưu authorization")
        return True
    except Exception as e:
        job(f"Lỗi lưu auth: {str(e)}")
        return False

def load_last_comment():
    try:
        if os.path.exists(CHECK_CMT_FILE):
            with open(CHECK_CMT_FILE, 'r', encoding='utf-8') as f:
                last_comment = f.read().strip()
            return last_comment if last_comment else None
        return None
    except Exception as e:
        job(f"Lỗi đọc file check_cmt: {str(e)}")
        return None

def save_comment(comment, status="sent"):
    try:
        with open(CHECK_CMT_FILE, 'w', encoding='utf-8') as f:
            f.write(f"{comment}\n")
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

def get_adb_devices():
    try:
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split('\n')[1:]
        devices = []
        for line in lines:
            if line.strip() and 'device' in line and 'offline' not in line:
                serial = line.split()[0]
                devices.append(serial)
        return devices
    except Exception as e:
        print(f"\033[1;31mLỗi quét ADB: {str(e)}\033[0m")
        return []

def select_device():
    global device, device_serial
    print("\033[1;33mĐang quét thiết bị ADB...\033[0m")
    devices = get_adb_devices()
    if not devices:
        print("\033[1;31mKhông tìm thấy thiết bị ADB nào!\033[0m")
        return False

    print("\033[1;36m══════════════════════════════════════════════\033[0m")
    print("\033[1;37mDanh sách thiết bị ADB:\033[0m")
    for i, serial in enumerate(devices):
        try:
            model = run_adb_command(['shell', 'getprop', 'ro.product.model'], serial=serial)
            model = model.stdout.strip() if model else "Không xác định"
        except:
            model = "Không xác định"
        print(f"\033[1;33m[{i+1}]\033[0m \033[1;36mSerial: {serial} | Model: {model}\033[0m")

    while True:
        try:
            choice = input(f"\033[1;37mChọn thiết bị (1-{len(devices)}): \033[0m").strip()
            choice = int(choice)
            if 1 <= choice <= len(devices):
                device_serial = devices[choice-1]
                if not init_instance_files(device_serial):
                    print("\033[1;31mKhông thể khởi tạo file cho instance!\033[0m")
                    return False
                break
            else:
                print("\033[1;31mLựa chọn không hợp lệ!\033[0m")
        except:
            print("\033[1;31mVui lòng nhập số!\033[0m")

    return connect_device(device_serial)

def connect_device(serial):
    global device
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"\033[1;33mĐang kết nối đến thiết bị {serial}... (lần {attempt+1})\033[0m")
            device = u2.connect(serial)
            device.info
            print("\033[1;32mKết nối thành công!\033[0m")
            job(f"Kết nối thành công tới thiết bị {serial}")
            check_tiktok_installed()
            return True
        except Exception as e:
            print(f"\033[1;31mKết nối thất bại: {str(e)}\033[0m")
            job(f"Kết nối thất bại tới {serial}: {str(e)}")
            time.sleep(2)
    return False

def reconnect_device():
    global device
    print("\033[1;33mMất kết nối thiết bị, đang kết nối lại...\033[0m")
    job("Mất kết nối thiết bị, đang kết nối lại...")
    time.sleep(2)
    return connect_device(device_serial) if device_serial else False

def check_tiktok_installed():
    global device
    try:
        packages = device.app_list()
        if TIKTOK_PACKAGE not in packages:
            print("\033[1;33mCảnh báo: TikTok chưa được cài đặt!\033[0m")
            job("Cảnh báo: TikTok chưa được cài đặt trên thiết bị")
            return False
        return True
    except Exception as e:
        job(f"Lỗi kiểm tra TikTok: {str(e)}")
        return False

# ===== HÀM FORCE STOP TIKTOK (HỖ TRỢ ĐA ROM) =====
def force_stop_tiktok():
    """
    Buộc dừng ứng dụng TikTok
    Hỗ trợ nhiều ROM Android (Samsung, Xiaomi, Oppo, Vivo, Pixel, máy xách tay Việt/Anh)
    """
    global device, device_serial
    
    try:
        print(f"\033[1;33m[{device_serial}] Đang kiểm tra trạng thái TikTok...\033[0m")
        job(f"Đang kiểm tra trạng thái TikTok...")

        # Mở App Info
        device.shell(f"am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:{TIKTOK_PACKAGE}")

        # Đợi Settings load - hỗ trợ đa ngôn ngữ
        if device(textMatches="(?i)(Buộc dừng|Buộc đóng|Force stop|Clear data|Xóa dữ liệu|App info|Storage)").wait(timeout=10):

            time.sleep(1.5)

            # Tìm nút Force Stop (hỗ trợ nhiều ROM)
            btn_stop = None
            
            # Thử tìm theo resourceId
            btn_stop = device(resourceIdMatches=".*force_stop.*|.*stop_button.*|.*forceStop.*")
            
            if not btn_stop or not btn_stop.exists:
                # Thử tìm theo text (đa ngôn ngữ)
                btn_stop = device(textMatches="(?i)(Buộc dừng|Buộc đóng|Force stop|Stop|Dừng)")
            
            if not btn_stop or not btn_stop.exists:
                # Thử tìm theo className và text
                for btn in device(className="android.widget.Button"):
                    try:
                        btn_text = btn.get_text()
                        if btn_text and re.search(r'(?i)(force\s*stop|buộc\s*dừng|stop|dừng)', btn_text):
                            btn_stop = btn
                            break
                    except:
                        continue

            if btn_stop and btn_stop.exists:

                # Nếu nút đang sáng (enabled) → app đang chạy
                if btn_stop.info.get("enabled", False):
                    
                    print(f"\033[1;33m[{device_serial}] TikTok đang chạy → Tiến hành BUỘC DỪNG\033[0m")
                    job("TikTok đang chạy → Tiến hành BUỘC DỪNG")

                    btn_stop.click()
                    time.sleep(1.5)

                    # Tìm nút OK/Xác nhận (đa ngôn ngữ)
                    btn_ok = device(resourceId="android:id/button1")
                    if not btn_ok.exists:
                        btn_ok = device(textMatches="(?i)(OK|Đồng ý|Xác nhận|Có|Yes|Accept)")
                    
                    if btn_ok.wait(timeout=3):
                        btn_ok.click()
                        print(f"\033[1;32m[{device_serial}] Đã buộc dừng TikTok\033[0m")
                        job("Đã buộc dừng TikTok")
                    else:
                        print(f"\033[1;33m[{device_serial}] Không tìm thấy nút xác nhận, nhưng đã click force stop\033[0m")

                else:
                    print(f"\033[1;32m[{device_serial}] TikTok đã dừng sẵn (nút xám)\033[0m")
                    job("TikTok đã dừng sẵn (nút xám)")

            else:
                print(f"\033[1;31m[{device_serial}] Không tìm thấy nút Buộc dừng\033[0m")
                job("Không tìm thấy nút Buộc dừng")

        else:
            print(f"\033[1;31m[{device_serial}] Không thể mở App Info\033[0m")
            job("Không thể mở App Info")

        # Back về màn hình chính
        device.press('home')
        time.sleep(1.5)
        
        return True

    except Exception as e:
        print(f"\033[1;31m[{device_serial}] Lỗi force stop: {str(e)}\033[0m")
        job(f"Lỗi force stop: {str(e)}")
        
        # Thử back về home nếu có lỗi
        try:
            device.press('home')
        except:
            pass
        
        return False

def open_tiktok_after_force_stop():
    """Mở TikTok sau khi force stop"""
    global device, device_serial
    
    try:
        print(f"\033[1;33m[{device_serial}] Mở TikTok...\033[0m")
        job("Mở TikTok...")
        
        device.app_start(TIKTOK_PACKAGE)

        # Đợi TikTok load - kiểm tra bằng nhiều cách
        if device(resourceIdMatches=".*tab_layout.*|.*main_tab.*|.*home_tab.*").wait(timeout=15) or \
           device(descriptionMatches="(?i)(home|trang chủ|feed|for you)").wait(timeout=15):
            print(f"\033[1;32m[{device_serial}] TikTok sẵn sàng\033[0m")
            job("TikTok sẵn sàng")
            time.sleep(2)
            return True
        else:
            print(f"\033[1;31m[{device_serial}] Không phát hiện giao diện TikTok\033[0m")
            job("Không phát hiện giao diện TikTok")
            time.sleep(2)
            return False
            
    except Exception as e:
        print(f"\033[1;31m[{device_serial}] Lỗi mở TikTok: {str(e)}\033[0m")
        job(f"Lỗi mở TikTok: {str(e)}")
        return False

# === HÀM GÕ TEXT TỰ NHIÊN - KHÔNG ÉP DÙNG AXT KEYBOARD ===
def type_text_natural(element, text):
    """
    Gõ text tự nhiên - click vào ô nhập và để bàn phím mặc định của máy tự bật lên
    Sau đó gõ từng ký tự bằng adb shell input text - KHÔNG ÉP DÙNG AXT
    """
    global device, device_serial
    try:
        if not text:
            return True
            
        job(f"Bắt đầu gõ text tự nhiên: {text[:20]}... (dài {len(text)} ký tự)")
        
        # Click vào ô nhập để focus và bật bàn phím mặc định
        element.click()
        time.sleep(1.5)  # Đợi bàn phím mặc định bật lên tự nhiên
        
        # Sử dụng adb shell input text để gõ - phương pháp tự nhiên nhất
        # Không cần set IME, không cần kích hoạt app keyboard
        escaped_text = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
        
        # Gõ từng phần nếu text quá dài (adb input text có giới hạn)
        max_chunk = 100
        for i in range(0, len(escaped_text), max_chunk):
            chunk = escaped_text[i:i+max_chunk]
            cmd = f"input text '{chunk}'"
            device.shell(cmd)
            time.sleep(0.3)  # Delay nhẹ giữa các chunk
        
        job(f"Đã gõ xong {len(text)} ký tự bằng input text tự nhiên")
        return True
        
    except Exception as e:
        job(f"Lỗi khi gõ text tự nhiên: {str(e)}")
        return False

def focus_and_type_natural(element, text):
    """
    Focus vào element và gõ text tự nhiên - KHÔNG ÉP DÙNG AXT
    """
    global device
    try:
        if not element or not element.exists:
            job("Element không tồn tại")
            return False
        
        # Click vào element để focus và bật bàn phím mặc định
        element.click()
        time.sleep(1)  # Đợi bàn phím bật lên
        
        # Xóa nội dung cũ nếu có (tùy chọn)
        try:
            element.clear_text()
            time.sleep(0.5)
        except:
            pass
        
        # Gõ text tự nhiên
        return type_text_natural(element, text)
        
    except Exception as e:
        job(f"Lỗi trong focus_and_type_natural: {str(e)}")
        return False

def open_link(link):
    """Mở link TikTok với tham số -W để đợi intent hoàn thành - tránh bị redirect"""
    global device
    try:
        cmd = f'am start -W -a android.intent.action.VIEW -d "{link}" {TIKTOK_PACKAGE}'
        device.shell(cmd)

        launched = device.app_wait(TIKTOK_PACKAGE, timeout=10)

        if launched:
            job(f"Đã mở link: {link}")
            time.sleep(1.5)  # Đợi thêm để tránh redirect

        return launched
    except Exception as e:
        job(f"Lỗi mở link {link}: {str(e)}")
        return False

def open_tiktok():
    """Mở ứng dụng TikTok"""
    global device
    try:
        device.app_start(TIKTOK_PACKAGE)
        time.sleep(3)
        return True
    except Exception as e:
        job(f"Lỗi mở TikTok: {str(e)}")
        return False

def click_search():
    """Click vào ô tìm kiếm trên TikTok - chỉ dùng selector chính xác"""
    global device
    try:
        # Chỉ dùng các selector chính xác, không dùng ImageView chung chung
        search_selectors = [
            {'description': 'Search'},
            {'description': 'Tìm kiếm'},
            {'text': 'Search'},
            {'text': 'Tìm kiếm'},
            {'resourceId': 'com.ss.android.ugc.trill:id/search'}, 
            {'resourceId': 'com.ss.android.ugc.trill:id/action_search'}
        ]
        
        for selector in search_selectors:
            try:
                element = device(**selector)
                if element.exists:
                    element.click()
                    time.sleep(1)
                    job("Đã click vào ô tìm kiếm")
                    return True
            except:
                continue
        
        job("Không tìm thấy nút tìm kiếm với selector chính xác")
        return False
    except Exception as e:
        job(f"Lỗi click tìm kiếm: {str(e)}")
        return False

def click_users_tab():
    """Click vào tab Users trong kết quả tìm kiếm"""
    global device
    try:
        # Tìm tab Users
        users_tab_selectors = [
            {'text': 'Users'},
            {'text': 'Người dùng'},
            {'text': 'People'},
            {'resourceId': 'com.ss.android.ugc.trill:id/tab_title', 'text': 'Users'},
            {'resourceId': 'com.ss.android.ugc.trill:id/tab_title', 'text': 'Người dùng'}
        ]
        
        for selector in users_tab_selectors:
            try:
                element = device(**selector)
                if element.exists:
                    element.click()
                    time.sleep(2)
                    job("Đã chuyển sang tab Users")
                    return True
            except:
                continue
        
        # Nếu không tìm thấy tab Users, có thể đang ở tab Users mặc định
        job("Không tìm thấy tab Users, có thể đang ở tab Users")
        return True
    except Exception as e:
        job(f"Lỗi click tab Users: {str(e)}")
        return False

def find_exact_username_in_search_results(username):
    """Tìm username chính xác trong kết quả tìm kiếm - KHÔNG VUỐT"""
    global device
    try:
        # Chuẩn hóa username (bỏ @ nếu có)
        target_username = username.replace('@', '').strip().lower()
        
        # Danh sách selectors - đã thêm fallback className TextView
        username_selectors = [
            # ResourceId chính xác
            {'resourceId': 'com.ss.android.ugc.trill:id/username'},
            {'resourceId': 'com.ss.android.ugc.trill:id/user_name'},
            {'resourceId': 'com.ss.android.ugc.trill:id/tv_name'},
            # Fallback cho mọi phiên bản TikTok
            {'className': 'android.widget.TextView'}
        ]
        
        # KHÔNG VUỐT - chỉ tìm trong kết quả hiện tại
        # Thử từng selector một lần duy nhất, không vuốt
        for selector in username_selectors:
            try:
                # Lấy tất cả các element phù hợp với selector
                elements = device(**selector).all()
                
                if elements and len(elements) > 0:
                    job(f"Tìm thấy {len(elements)} element với selector {selector}")
                    
                    # Duyệt qua từng element trong danh sách
                    for elem in elements:
                        try:
                            text = elem.get_text()
                            if text:
                                # Chuẩn hóa text (bỏ @ nếu có)
                                clean_text = text.replace('@', '').strip().lower()
                                
                                # Lọc thêm: tránh các text quá dài hoặc có dấu hiệu không phải username
                                if len(clean_text) > 30:  # Username thường không quá dài
                                    continue
                                
                                # Tránh các text phổ biến không phải username
                                common_texts = ['follow', 'following', 'theo dõi', 'đang theo dõi', 
                                               'message', 'nhắn tin', 'share', 'chia sẻ', 'report',
                                               'block', 'chặn', 'videos', 'video', 'likes', 'thích',
                                               'followers', 'người theo dõi', 'following', 'đang follow']
                                if clean_text in common_texts:
                                    continue
                                
                                # So sánh chính xác
                                if clean_text == target_username:
                                    job(f"Tìm thấy username chính xác: {text}")
                                    elem.click()
                                    time.sleep(2)  # Đợi profile load
                                    return True
                                
                                # Fallback: nếu username chứa target (trong trường hợp có prefix/suffix)
                                if target_username in clean_text and len(clean_text) - len(target_username) <= 3:
                                    job(f"Tìm thấy username gần đúng: {text} (chứa {target_username})")
                                    elem.click()
                                    time.sleep(2)
                                    return True
                                    
                        except Exception as e:
                            job(f"Lỗi xử lý element: {str(e)}")
                            continue
            except Exception as e:
                job(f"Lỗi với selector {selector}: {str(e)}")
                continue
        
        # KHÔNG VUỐT - nếu không tìm thấy thì báo lỗi ngay
        job(f"Không tìm thấy username chính xác '{username}' trong kết quả tìm kiếm (không vuốt)")
        return False
        
    except Exception as e:
        job(f"Lỗi tìm username chính xác: {str(e)}")
        return False

def verify_profile_username(expected_username):
    """Kiểm tra username trên profile có khớp với expected_username không - chỉ dùng selector chính xác"""
    global device
    try:
        # Chỉ dùng các selector chính xác cho username profile
        username_selectors = [
            {'resourceId': 'com.ss.android.ugc.trill:id/profile_title'},
            {'resourceId': 'com.ss.android.ugc.trill:id/title'},
            {'resourceId': 'com.ss.android.ugc.trill:id/user_name'}
        ]
        
        # Đợi profile load tối thiểu 3-4 giây
        time.sleep(4)
        
        target_username = expected_username.replace('@', '').strip().lower()
        
        for selector in username_selectors:
            try:
                element = device(**selector)
                if element.exists:
                    profile_username_text = element.get_text()
                    if profile_username_text:
                        clean_profile = profile_username_text.replace('@', '').strip().lower()
                        
                        if clean_profile == target_username:
                            job(f"Xác minh username thành công: {profile_username_text} == {expected_username}")
                            return True
                        else:
                            job(f"Username không khớp: {profile_username_text} != {expected_username}")
                            return False
            except:
                continue
        
        job("Không tìm thấy username trên profile để xác minh")
        return False
    except Exception as e:
        job(f"Lỗi verify username: {str(e)}")
        return False

def type_search_natural(username):
    """
    Focus vào ô tìm kiếm và gõ username tự nhiên - KHÔNG ÉP DÙNG AXT
    """
    global device
    try:
        # Tìm ô nhập liệu
        input_box = None
        input_selectors = [
            {'className': 'android.widget.EditText'},
            {'resourceId': 'com.ss.android.ugc.trill:id/search_edit_text'},
            {'resourceId': 'com.ss.android.ugc.trill:id/et_search_keyword'}
        ]
        
        for selector in input_selectors:
            try:
                element = device(**selector)
                if element.exists:
                    input_box = element
                    break
            except:
                continue
        
        if not input_box:
            job("Không tìm thấy ô nhập tìm kiếm")
            return False
        
        # Focus và gõ username tự nhiên - KHÔNG ÉP DÙNG AXT
        if not focus_and_type_natural(input_box, username):
            job("Không thể gõ username")
            return False
        
        # Đợi 1 giây sau khi gõ xong
        time.sleep(1)
        
        # Tìm và click nút tìm kiếm
        search_buttons = [
            {'text': 'Search'}, 
            {'text': 'Tìm kiếm'},
            {'resourceId': 'com.ss.android.ugc.trill:id/search_button'},
            {'description': 'Search'},
            {'description': 'Tìm kiếm'},
            {'className': 'android.widget.Button', 'textMatches': '(?i)search|tìm kiếm'}
        ]
        
        search_clicked = False
        for btn_selector in search_buttons:
            try:
                btn = device(**btn_selector)
                if btn.exists and btn.info.get('enabled', False):
                    btn.click()
                    search_clicked = True
                    job(f"Đã click nút tìm kiếm: {btn_selector}")
                    break
            except:
                continue
        
        # Nếu không tìm thấy nút tìm kiếm, thử nhấn Enter
        if not search_clicked:
            job("Không tìm thấy nút tìm kiếm, nhấn Enter")
            device.press('enter')
        
        # Đợi kết quả tìm kiếm load
        time.sleep(3)
        
        job(f"Đã tìm kiếm username: {username} (gõ tự nhiên, không ép dùng AXT)")
        return True
        
    except Exception as e:
        job(f"Lỗi trong type_search_natural: {str(e)}")
        return False

def do_follow_via_search_natural(username):
    """Thực hiện follow bằng cách tìm kiếm username - KHÔNG ÉP DÙNG AXT"""
    global device
    
    if not username:
        job("Không có username để tìm kiếm")
        return False
    
    job(f"Bắt đầu follow bằng tìm kiếm cho username: {username} (không ép dùng AXT)")
    
    # Bước 1: Mở TikTok
    if not open_tiktok():
        job("Không thể mở TikTok")
        return False
    
    # Bước 2: Click nút tìm kiếm
    if not click_search():
        job("Không thể click vào ô tìm kiếm")
        return False
    
    # Bước 3: Gõ username tự nhiên và search - KHÔNG ÉP DÙNG AXT
    if not type_search_natural(username):
        job("Không thể thực hiện tìm kiếm")
        return False
    
    # Bước 4: Vào tab Users
    if not click_users_tab():
        job("Không thể chuyển sang tab Users")
        return False
    
    # Bước 5: Click đúng username
    if not find_exact_username_in_search_results(username):
        job(f"Không tìm thấy username chính xác '{username}' - Skip job")
        device.press('back')
        time.sleep(1)
        device.press('back')
        time.sleep(1)
        return False
    
    # Bước 6: Đợi profile load và kiểm tra username
    if not verify_profile_username(username):
        job(f"Username trên profile không khớp với {username} - Skip job")
        device.press('back')
        time.sleep(1)
        device.press('back')
        time.sleep(1)
        return False
    
    # Bước 7: Thực hiện follow
    if not do_follow(device):
        job("Follow thất bại")
        device.press('back')
        time.sleep(1)
        device.press('back')
        time.sleep(1)
        return False
    
    # Bước 8: Back về màn hình chính
    job("Back về màn hình chính")
    device.press('back')
    time.sleep(1)
    device.press('back')
    time.sleep(1)
    
    job(f"Follow thành công cho username: {username} (không ép dùng AXT)")
    return True

def do_follow_via_link(link):
    """Thực hiện follow bằng cách mở link profile (cách cũ)"""
    global device
    
    if not link:
        job("Không có link để mở")
        return False
    
    job(f"Bắt đầu follow bằng link: {link}")
    
    # Mở link với tham số -W
    if not open_link(link):
        job("Không thể mở link")
        return False
    
    time.sleep(3)  # Đợi profile load
    
    # Thực hiện follow
    if not do_follow(device):
        job("Follow thất bại")
        return False
    
    # Quay lại
    device.press('back')
    time.sleep(1)
    
    job("Follow thành công qua link")
    return True

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

def do_like(d):
    if not d:
        return False

    candidates = [
        {'resourceId': "com.ss.android.ugc.trill:id/like_button"},
        {'resourceId': "com.ss.android.ugc.trill:id/a_f"},
        {'descriptionContains': "like"},
        {'descriptionContains': "thích"},
        {'textContains': "Thích"},
    ]
    btn, sel = find_first_selector(d, candidates, timeout_per=2)
    if not btn:
        job("Không tìm thấy nút thích")
        return False

    try:
        btn.click()
        time.sleep(1.2)
        return True
    except Exception as e:
        job(f"Lỗi click thích: {str(e)}")
        return False

def do_follow(d):
    if not d:
        return False

    # Chỉ dùng selector chính xác, tránh click nhầm Following/Follow back
    candidates = [
        {'resourceId': "com.ss.android.ugc.trill:id/follow_btn"},
        {'resourceId': "com.ss.android.ugc.trill:id/a_x"},
        {'textMatches': "(?i)^follow$|^theo dõi$"},  # Chỉ match chính xác từ "follow" hoặc "theo dõi"
    ]
    btn, sel = find_first_selector(d, candidates, timeout_per=2)
    if not btn:
        job("Không tìm thấy nút theo dõi")
        return False

    try:
        btn.click()
        time.sleep(1.2)
        return True
    except Exception as e:
        job(f"Lỗi click theo dõi: {str(e)}")
        return False

def do_favorite(d):
    if not d:
        return False

    try:
        selectors = [
            {"descriptionContains": "Favorite"},
            {"descriptionContains": "Favourite"},
            {"descriptionContains": "Add to favorites"},
            {"descriptionContains": "Save to favorites"},
            {"textContains": "Favorite"},
            {"textContains": "Favourite"},
            {"descriptionContains": "Yêu thích"},
            {"descriptionContains": "Thêm vào yêu thích"},
            {"descriptionContains": "Lưu vào yêu thích"},
            {"textContains": "Yêu thích"},
            {"descriptionContains": "收藏"},
            {"descriptionContains": "お気に入り"},
            {"descriptionContains": "즐겨찾기"},
        ]

        for sel in selectors:
            obj = d(**sel)
            if obj.exists(timeout=2):
                job(f"Tìm thấy nút yêu thích qua: {sel}")
                obj.click()
                time.sleep(1)
                return True

        job("Không tìm thấy qua text/description, thử tìm theo class...")
        for obj in d(className="android.widget.ImageView", clickable=True):
            try:
                bounds = obj.info.get('bounds', {})
                content_desc = obj.info.get('contentDescription', '').lower()

                if bounds and 'right' in bounds:
                    if bounds.get('right', 0) > 800:
                        if any(keyword in content_desc for keyword in ['favorite', 'thích', 'yêu', '收藏']):
                            job(f"Tìm thấy nút yêu thích qua bounds + content-desc: {content_desc}")
                            obj.click()
                            time.sleep(1)
                            return True
            except:
                continue

        try:
            for obj in d(className="android.widget.ImageView"):
                res_id = obj.info.get('resourceName', '')
                if res_id and ('favorite' in res_id.lower() or 'fav' in res_id.lower()):
                    if obj.clickable:
                        job(f"Tìm thấy nút yêu thích qua resourceId: {res_id}")
                        obj.click()
                        time.sleep(1)
                        return True
        except:
            pass

        return False
    except Exception as e:
        job(f"Lỗi trong do_favorite: {str(e)}")
        return False

def do_comment_natural(d, text, link):
    """Thực hiện comment - KHÔNG ÉP DÙNG AXT"""
    if not d:
        return False

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

    # Tìm nút bình luận
    comment_candidates = [
        {'resourceId': "com.ss.android.ugc.trill:id/comment_button"},
        {'resourceId': "com.ss.android.ugc.trill:id/a_y"},
        {'descriptionContains': "comment"},
        {'descriptionContains': "bình luận"},
    ]
    comment_btn, sel_c = find_first_selector(d, comment_candidates, timeout_per=3)
    if not comment_btn:
        job("Không tìm thấy nút bình luận")
        return False

    try:
        comment_btn.click()
        time.sleep(1.5)
    except Exception as e:
        job(f"Lỗi click bình luận: {str(e)}")
        return False

    # Tìm ô nhập bình luận
    input_box = None
    try:
        input_box = d(className="android.widget.EditText")
        if not input_box.wait(timeout=5):
            input_box, _ = find_first_selector(d, [{'className': "android.widget.EditText"}, {'resourceId': "com.ss.android.ugc.trill:id/comment_edit_text"}], timeout_per=1)
    except Exception:
        input_box = None

    if not input_box:
        job("Không tìm thấy ô nhập bình luận")
        return False

    # Focus và gõ comment tự nhiên - KHÔNG ÉP DÙNG AXT
    if not focus_and_type_natural(input_box, filtered_text):
        job("Không thể gõ nội dung bình luận")
        return False

    # Tìm nút gửi
    send_candidates = [
        {'resourceId': "com.ss.android.ugc.trill:id/send_btn"},
        {'resourceId': "com.ss.android.ugc.trill:id/send_button"},
        {'textMatches': "(?i)send|post|gửi|đăng"},
        {'descriptionContains': "gửi"},
    ]
    send_btn, send_sel = find_first_selector(d, send_candidates, timeout_per=2)
    if send_btn and send_btn.info.get('enabled'):
        try:
            send_btn.click()
            time.sleep(0.5)
        except Exception:
            d.press("enter")
    else:
        d.press("enter")

    save_comment(filtered_text, "sent")
    previous_job_link = link
    job(f"Đã bình luận: {filtered_text[:30]}... (gõ tự nhiên, không ép dùng AXT)")
    return True

def call_api_complete(ads_id, account_id):
    """Gọi API complete và trả về (success, message)"""
    try:
        json_data = {
            'ads_id': ads_id,
            'account_id': account_id,
            'async': True,
            'data': None
        }

        response = session.post(
            'https://gateway.golike.net/api/advertising/publishers/tiktok/complete-jobs',
            headers=headers, json=json_data, timeout=30)

        # Parse response JSON
        try:
            resp_json = response.json()
        except:
            # Không parse được JSON
            return False, f"HTTP {response.status_code} - Không parse được JSON"

        # Luôn lấy message từ response
        api_message = resp_json.get("message", "Không có message")

        if response.status_code != 200:
            return False, f"HTTP {response.status_code} - {api_message}"

        if resp_json.get("status") != 200:
            return False, api_message

        return True, "success"

    except requests.exceptions.Timeout:
        return False, "Timeout - API không phản hồi"
    except requests.exceptions.ConnectionError:
        return False, "Lỗi kết nối - Kiểm tra mạng"
    except Exception as e:
        return False, f"Lỗi: {str(e)}"

def call_api_skip(ads_id, object_id, account_id, job_type):
    """Gọi API skip và trả về (success, message)"""
    try:
        json_data = {
            'ads_id': ads_id, 
            'object_id': object_id, 
            'account_id': account_id, 
            'type': job_type
        }
        
        response = session.post(
            'https://gateway.golike.net/api/advertising/publishers/tiktok/skip-jobs',
            headers=headers, json=json_data, timeout=30)

        # Parse response JSON
        try:
            resp_json = response.json()
        except:
            return False, f"HTTP {response.status_code} - Không parse được JSON"

        # Luôn lấy message từ response
        api_message = resp_json.get("message", "Không có message")

        if response.status_code != 200:
            return False, f"HTTP {response.status_code} - {api_message}"

        if resp_json.get("status") != 200:
            return False, api_message

        return True, "success"

    except requests.exceptions.Timeout:
        return False, "Timeout - API không phản hồi"
    except requests.exceptions.ConnectionError:
        return False, "Lỗi kết nối - Kiểm tra mạng"
    except Exception as e:
        return False, f"Lỗi: {str(e)}"

def call_api_get_jobs(account_id):
    """Gọi API lấy job và trả về (success, data, message)"""
    try:
        params = {'account_id': account_id, 'data': 'null'}
        response = session.get(
            'https://gateway.golike.net/api/advertising/publishers/tiktok/jobs',
            headers=headers, params=params, timeout=30)

        # Parse response JSON
        try:
            resp_json = response.json()
        except:
            return False, None, f"HTTP {response.status_code} - Không parse được JSON"

        # Luôn lấy message từ response
        api_message = resp_json.get("message", "Không có message")

        if response.status_code != 200:
            return False, None, f"HTTP {response.status_code} - {api_message}"

        if resp_json.get("status") != 200:
            return False, None, api_message

        return True, resp_json.get("data"), "success"

    except requests.exceptions.Timeout:
        return False, None, "Timeout - API không phản hồi"
    except requests.exceptions.ConnectionError:
        return False, None, "Lỗi kết nối - Kiểm tra mạng"
    except Exception as e:
        return False, None, f"Lỗi: {str(e)}"

def call_api_get_accounts():
    """Gọi API lấy danh sách tài khoản và trả về (success, data, message)"""
    try:
        response = session.get(
            'https://gateway.golike.net/api/tiktok-account', 
            headers=headers, timeout=30)

        # Parse response JSON
        try:
            resp_json = response.json()
        except:
            return False, None, f"HTTP {response.status_code} - Không parse được JSON"

        # Luôn lấy message từ response
        api_message = resp_json.get("message", "Không có message")

        if response.status_code != 200:
            return False, None, f"HTTP {response.status_code} - {api_message}"

        if resp_json.get("status") != 200:
            return False, None, api_message

        return True, resp_json.get("data", []), "success"

    except requests.exceptions.Timeout:
        return False, None, "Timeout - API không phản hồi"
    except requests.exceptions.ConnectionError:
        return False, None, "Lỗi kết nối - Kiểm tra mạng"
    except Exception as e:
        return False, None, f"Lỗi: {str(e)}"

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
        link = job_data["link"]
        action_type = job_data["type"]
        ads_id = job_data["id"]
        job_price = get_job_price(job_data)

        if action_type == "follow":
            if job_price < MIN_FOLLOW_PRICE:
                return False, f"Giá thấp ({job_price}đ < {MIN_FOLLOW_PRICE}đ)", ads_id, job_price

        if action_type not in ["like", "follow", "comment", "favorite"]:
            return False, f"Loại không hỗ trợ: {action_type}", None, 0

        success = False
        reason = ""

        # Xử lý đặc biệt cho follow với 2 chế độ
        if action_type == "follow" and FOLLOW_MODE == 2:
            # Chế độ 2: Tìm kiếm username - KHÔNG ÉP DÙNG AXT
            username = None
            
            # Thử lấy username từ link
            if link:
                match = re.search(r'@([^/?]+)', link)
                if match:
                    username = match.group(1)
            
            # Nếu không lấy được từ link, thử lấy từ job_data
            if not username:
                username = job_data.get("unique_username") or job_data.get("username") or job_data.get("object_name")
            
            if not username:
                job("Không thể lấy username từ job data")
                return False, "Không tìm thấy username", ads_id, job_price
            
            # Sử dụng hàm follow mới - KHÔNG ÉP DÙNG AXT
            success = do_follow_via_search_natural(username)
            reason = "Không tìm thấy username" if not success else "thành công"
        else:
            # Chế độ 1: Mở link
            if not open_link(link):
                return False, "Không thể mở link", ads_id, job_price

            if action_type == "like":
                success = do_like(device)
                reason = "Không tìm thấy nút thích" if not success else "thành công"
            elif action_type == "follow":
                success = do_follow(device)
                reason = "Không tìm thấy nút theo dõi" if not success else "thành công"
            elif action_type == "favorite":
                success = do_favorite(device)
                reason = "Không tìm thấy nút yêu thích" if not success else "thành công"
            elif action_type == "comment":
                comment_text = (
                    job_data.get("text") or
                    job_data.get("description") or
                    job_data.get("comment") or
                    job_data.get("noidung")
                )
                if not comment_text:
                    return False, "Thiếu nội dung bình luận", ads_id, job_price
                # Sử dụng hàm comment mới - KHÔNG ÉP DÙNG AXT
                success = do_comment_natural(device, comment_text, link)
                reason = "Bình luận thất bại" if not success else "thành công"

        if not success:
            return False, reason, ads_id, job_price

        # Gọi API complete
        complete_success, api_message = call_api_complete(ads_id, account_id)
        
        if complete_success:
            save_link_job(link, action_type, "thành công", job_price)
            return True, "success", ads_id, job_price
        else:
            save_link_job(link, action_type, f"thất bại: {api_message}", job_price)
            return False, api_message, ads_id, job_price

    except Exception as e:
        job(f"Exception trong process_tiktok_job: {str(e)}")
        return False, f"Lỗi: {str(e)}", None, 0

# Khởi tạo session
session = requests.Session()
headers = {}

def banner():
    clear_screen()
    banner_text = """
██      ██╗      ████████╗ █████╗  █████╗ ██╗
██╗    ╔██║      ╚══██╔══╝██╔══██╗██╔══██╗██║
██║████║██║ █████╗  ██║   ██║  ██║██║  ██║██║
██║    ╚██║ ╚════╝  ██║   ██║  ██║██║  ██║██║
██║     ██║         ██║   ╚█████╔╝╚█████╔╝██████╗
╚═╝     ╚═╝         ╚═╝    ╚════╝  ╚════╝ ╚════╝
"""
    for char in banner_text:
        print(char, end='', flush=True)
        time.sleep(0.00125)

# --- MAIN CODE ---
if __name__ == "__main__":
    if not init_files():
        print("\033[1;31mKhông thể khởi tạo files chung! Thoát tool.\033[0m")
        sys.exit(1)

    banner()
    print("\033[1;36mĐịa chỉ IP: 83.86.8888\033[0m")
    print("\033[1;35m════════════════════════════════════════════════\033[0m")
    print("\033[1;32mNhập 1 để vào Tool Tiktok\033[0m")
    print("\033[1;31mNhập 2 để xóa Authorization hiện tại\033[0m")

    while True:
        try:
            choose = input("\033[1;33mNhập lựa chọn (1 hoặc 2): \033[0m").strip()
            choose = int(choose)
            if choose not in [1, 2]:
                print("\033[1;31mLựa chọn không hợp lệ! Hãy nhập lại.\033[0m")
                continue
            break
        except (ValueError, EOFError):
            print("\033[1;31mSai định dạng! Vui lòng nhập số.\033[0m")

    if choose == 2:
        if os.path.exists(AUTH_FILE):
            try:
                os.remove(AUTH_FILE)
                print("\033[1;32mĐã xóa Authorization.txt!\033[0m")
            except Exception as e:
                print(f"\033[1;31mKhông thể xóa {AUTH_FILE}: {e}\033[0m")
        else:
            print("\033[1;33mFile Authorization.txt không tồn tại!\033[0m")
        print("\033[1;33mVui lòng nhập lại thông tin!\033[0m")
        choose = 1

    author = read_auth()

    while not author:
        print("\033[1;35m════════════════════════════════════════════════\033[0m")
        author = input("\033[1;33mNhập Authorization: \033[0m").strip()
        if author:
            save_auth(author)
        else:
            print("\033[1;31mAuthorization không được để trống!\033[0m")

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

    print("\033[1;35m════════════════════════════════════════════════\033[0m")
    print("\033[1;32mĐăng nhập thành công! Đang vào Tool Tiktok...\033[0m")
    time.sleep(1)

    # Lấy danh sách tài khoản
    accounts_success, accounts_data_list, accounts_message = call_api_get_accounts()
    
    if not accounts_success:
        print(f"\033[1;31mLỗi lấy danh sách tài khoản: {accounts_message}\033[0m")
        if logger:
            logger.error(f"Lỗi lấy danh sách tài khoản: {accounts_message}")
        sys.exit(1)

    if not accounts_data_list:
        print("\033[1;31mKhông có tài khoản nào trong danh sách!\033[0m")
        sys.exit(1)

    def dsacc():
        banner()
        print("\033[1;36mĐịa chỉ IP: 83.86.8888\033[0m")
        print(f"\033[1;33mThiết bị: {device_serial if device_serial else 'Chưa kết nối'}\033[0m")
        print("\033[1;35m════════════════════════════════════════════════\033[0m")
        print("\033[1;32mDanh sách tài khoản Tik Tok:\033[0m")
        print("\033[1;35m════════════════════════════════════════════════\033[0m")
        for i, acc in enumerate(accounts_data_list):
            print(f"\033[1;34m[{i+1}]\033[0m ID: {acc['unique_username']} | \033[1;32mHoạt động\033[0m")
        print("\033[1;35m════════════════════════════════════════════════\033[0m")

    dsacc()

    d = 0
    while True:
        idacc = input("\033[1;32mNhập ID tài khoản Tiktok làm việc: \033[0m").strip()
        for acc in accounts_data_list:
            if acc["unique_username"] == idacc:
                d = 1
                account_id = acc["id"]
                username = acc["unique_username"]
                init_account_data(account_id, username)
                if logger:
                    logger.info(f"Chọn account ID: {account_id}")
                break
        if d == 0:
            print("\033[1;31mTài khoản này chưa được thêm vào golike hoặc ID sai\033[0m")
            continue
        break

    while True:
        try:
            print("\033[1;35m════════════════════════════════════════════════\033[0m")
            print("\033[1;32mLọc nhiệm vụ theo dõi theo tiền:\033[0m")
            min_follow = input("\033[1;33mNhập giá theo dõi tối thiểu (vd: 12, nhập 0 để tắt lọc): \033[0m").strip()
            MIN_FOLLOW_PRICE = float(min_follow) if '.' in min_follow else int(min_follow)
            if logger:
                logger.info(f"Giá theo dõi tối thiểu: {MIN_FOLLOW_PRICE}")
            break
        except ValueError:
            print("\033[1;31mSai định dạng! Vui lòng nhập số.\033[0m")

    while True:
        try:
            print("\033[1;35m════════════════════════════════════════════════\033[0m")
            print("\033[1;32mChọn chế độ mở job FOLLOW:\033[0m")
            print("\033[1;36m1: Mở qua link (package/deeplink) - giữ nguyên cách cũ\033[0m")
            print("\033[1;36m2: Mở bằng tìm kiếm username (chỉ áp dụng cho job FOLLOW)\033[0m")
            follow_mode_choice = input("\033[1;33mChọn chế độ (1 hoặc 2): \033[0m").strip()
            follow_mode_choice = int(follow_mode_choice)
            if follow_mode_choice in [1, 2]:
                FOLLOW_MODE = follow_mode_choice
                if logger:
                    logger.info(f"Chế độ follow: {'Mở link' if FOLLOW_MODE == 1 else 'Tìm kiếm username'}")
                break
            else:
                print("\033[1;31mVui lòng chọn 1 hoặc 2!\033[0m")
        except ValueError:
            print("\033[1;31mSai định dạng! Vui lòng nhập số.\033[0m")

    while True:
        try:
            print("\033[1;35m════════════════════════════════════════════════\033[0m")
            print("\033[1;32mCấu hình FORCE STOP:\033[0m")
            force_stop_choice = input("\033[1;33mBật force stop trước khi chạy? (1: Có / 0: Không): \033[0m").strip()
            FORCE_STOP_BEFORE_RUN = (force_stop_choice == '1')
            
            force_stop_every = input("\033[1;33mSau bao nhiêu job thì force stop TikTok? (nhập số, 0 để tắt): \033[0m").strip()
            FORCE_STOP_EVERY_JOB = int(force_stop_every) if force_stop_every.isdigit() else 20
            
            if logger:
                logger.info(f"Force stop trước khi chạy: {FORCE_STOP_BEFORE_RUN}, reset sau {FORCE_STOP_EVERY_JOB} job")
            break
        except ValueError:
            print("\033[1;31mSai định dạng! Vui lòng nhập số.\033[0m")

    while True:
        try:
            base_delay = int(input("\033[1;33mNhập thời gian cơ bản (giây): \033[0m").strip())
            delay_variation = int(input("\033[1;33mBiến thiên +- (giây): \033[0m").strip())
            if logger:
                logger.info(f"Cấu hình đợi: cơ bản={base_delay}, biến thiên={delay_variation}")
            break
        except ValueError:
            print("\033[1;31mSai định dạng!!!\033[0m")

    print("\033[1;35m════════════════════════════════════════════════\033[0m")
    print("\033[1;32mChọn chế độ nhận nhiệm vụ:\033[0m")
    print("\033[1;36m1: Chỉ theo dõi\033[0m")
    print("\033[1;36m2: Chỉ thích\033[0m")
    print("\033[1;36m3: Chỉ bình luận\033[0m")
    print("\033[1;36m4: Chỉ yêu thích\033[0m")
    print("\033[1;36m5: Thích + theo dõi\033[0m")
    print("\033[1;36m6: Thích + bình luận\033[0m")
    print("\033[1;36m7: Thích + yêu thích\033[0m")
    print("\033[1;36m8: Theo dõi + bình luận\033[0m")
    print("\033[1;36m9: Theo dõi + yêu thích\033[0m")
    print("\033[1;36m10: Bình luận + yêu thích\033[0m")
    print("\033[1;36m11: Thích + theo dõi + bình luận\033[0m")
    print("\033[1;36m12: Thích + theo dõi + yêu thích\033[0m")
    print("\033[1;36m13: Thích + bình luận + yêu thích\033[0m")
    print("\033[1;36m14: Theo dõi + bình luận + yêu thích\033[0m")
    print("\033[1;36m15: Thích + theo dõi + bình luận + yêu thích\033[0m")

    valid_choices = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

    while True:
        try:
            chedo = int(input("\033[1;33mChọn chế độ (1-15): \033[0m").strip())
            if chedo in valid_choices:
                if logger:
                    logger.info(f"Chọn chế độ: {chedo}")
                break
            else:
                print("\033[1;31mVui lòng chọn từ 1 đến 15!\033[0m")
        except ValueError:
            print("\033[1;31mNhập số hợp lệ!\033[0m")

    if chedo == 1:
        lam = ["follow"]
    elif chedo == 2:
        lam = ["like"]
    elif chedo == 3:
        lam = ["comment"]
    elif chedo == 4:
        lam = ["favorite"]
    elif chedo == 5:
        lam = ["like", "follow"]
    elif chedo == 6:
        lam = ["like", "comment"]
    elif chedo == 7:
        lam = ["like", "favorite"]
    elif chedo == 8:
        lam = ["follow", "comment"]
    elif chedo == 9:
        lam = ["follow", "favorite"]
    elif chedo == 10:
        lam = ["comment", "favorite"]
    elif chedo == 11:
        lam = ["like", "follow", "comment"]
    elif chedo == 12:
        lam = ["like", "follow", "favorite"]
    elif chedo == 13:
        lam = ["like", "comment", "favorite"]
    elif chedo == 14:
        lam = ["follow", "comment", "favorite"]
    else:
        lam = ["like", "follow", "comment", "favorite"]

    print("\033[1;35m════════════════════════════════════════════════\033[0m")
    print("\033[1;32mHoàn tất cấu hình nhiệm vụ!\033[0m")
    print(f"\033[1;36mCác loại nhiệm vụ sẽ làm: {', '.join(lam)}\033[0m")
    print(f"\033[1;36mChế độ follow: {'Mở link' if FOLLOW_MODE == 1 else 'Tìm kiếm username'}\033[0m")
    print(f"\033[1;36mForce stop trước khi chạy: {'CÓ' if FORCE_STOP_BEFORE_RUN else 'KHÔNG'}\033[0m")
    print(f"\033[1;36mReset TikTok sau mỗi {FORCE_STOP_EVERY_JOB} job\033[0m")
    print("\033[1;33mTiến hành kết nối thiết bị ADB...\033[0m")

    time.sleep(1)

    if not select_device():
        print("\033[1;31mKhông thể kết nối thiết bị. Thoát tool!\033[0m")
        if logger:
            logger.error("Không thể kết nối thiết bị, thoát tool")
        sys.exit(1)

    accounts_data[account_id]["devices"] = device_serial

    # ===== BIẾN ĐẾM JOB TOÀN CỤC =====
    job_count = 0

    # ===== FORCE STOP TRƯỚC KHI CHẠY (NẾU BẬT) =====
    if FORCE_STOP_BEFORE_RUN:
        update_account_status(account_id, "Đang force stop TikTok...")
        with Live(update_dashboard(), console=console, refresh_per_second=2, screen=True) as live:
            live.update(update_dashboard())
        
        force_stop_tiktok()
        open_tiktok_after_force_stop()
        
        time.sleep(1)

    # ===== VÒNG LẶP CHÍNH =====
    with Live(update_dashboard(), console=console, refresh_per_second=2, screen=True) as live:
        while True:
            update_account_status(account_id, "Đang tìm nhiệm vụ...")
            live.update(update_dashboard())

            # Gọi API lấy job
            job_success, job_data, job_message = call_api_get_jobs(account_id)

            if job_success:
                if not job_data or not job_data.get("link"):
                    update_account_status(account_id, f"Không có job - {job_message}")
                    live.update(update_dashboard())
                    time.sleep(2)
                    continue

                current_link = job_data.get("link")
                with open(LINK_JOB_FILE, 'w', encoding='utf-8') as f:
                    f.write(current_link)

                if is_link_processed(current_link):
                    skip_success, skip_message = call_api_skip(
                        job_data["id"], job_data["object_id"], account_id, job_data["type"]
                    )
                    if not skip_success:
                        job(f"Báo lỗi thất bại: {skip_message}")
                    
                    update_account_status(account_id, f"Job đã làm rồi - {skip_message if not skip_success else 'Đã báo lỗi'}")
                    live.update(update_dashboard())
                    time.sleep(1)
                    continue

                if job_data["type"] not in lam:
                    skip_success, skip_message = call_api_skip(
                        job_data["id"], job_data["object_id"], account_id, job_data["type"]
                    )
                    if not skip_success:
                        job(f"Báo lỗi thất bại: {skip_message}")
                    
                    update_account_status(account_id, f"Bỏ qua job {job_data['type']} - {skip_message if not skip_success else 'Đã báo lỗi'}")
                    live.update(update_dashboard())
                    time.sleep(1)
                    continue

                status_map = {
                    "follow": "Đang theo dõi...",
                    "like": "Đang thích...",
                    "comment": "Đang bình luận...",
                    "favorite": "Đang thêm yêu thích..."
                }
                update_account_status(account_id, status_map.get(job_data["type"], f"Đang xử lý {job_data['type']}..."))
                live.update(update_dashboard())

                success, reason, job_ads_id, job_price = process_tiktok_job(job_data)

                if success:
                    update_account_stats(account_id, job_data["type"], job_price, success=True)
                    update_account_status(account_id, f"Hoàn thành - +{job_price}đ")
                    live.update(update_dashboard())

                    delay = get_random_delay()
                    for remaining_time in range(delay, 0, -1):
                        update_account_status(account_id, f"Đợi {remaining_time}s...")
                        live.update(update_dashboard())
                        time.sleep(1)
                    
                    # Tăng biến đếm job
                    job_count += 1
                    
                else:
                    update_account_stats(account_id, job_data["type"], 0, success=False)
                    # Hiển thị message thật từ API hoặc lỗi thực tế
                    update_account_status(account_id, f"Thất bại - {reason}")
                    live.update(update_dashboard())

                    # Gọi API báo lỗi
                    skip_success, skip_message = call_api_skip(
                        job_data["id"], job_data["object_id"], account_id, job_data["type"]
                    )
                    if not skip_success:
                        job(f"Báo lỗi thất bại: {skip_message}")
                    
                    time.sleep(1)

                # ===== KIỂM TRA VÀ FORCE STOP SAU X JOB =====
                if FORCE_STOP_EVERY_JOB > 0 and job_count >= FORCE_STOP_EVERY_JOB:
                    update_account_status(account_id, f"Reset TikTok sau {job_count} job...")
                    live.update(update_dashboard())
                    
                    # Force stop và mở lại TikTok
                    force_stop_tiktok()
                    open_tiktok_after_force_stop()
                    
                    # Reset biến đếm
                    job_count = 0
                    
                    # Đợi một chút sau khi reset
                    time.sleep(2)

            else:
                # Hiển thị message từ API khi lỗi
                update_account_status(account_id, f"Lỗi API: {job_message}")
                live.update(update_dashboard())
                time.sleep(5)