import os
import sys
import time
import json
import requests
import re
from datetime import datetime
import subprocess
import random 
import threading 
import base64 # [ADDED] Thêm base64 để hỗ trợ ADB Keyboard cũ

# [START ADDED] THÊM PROMPT TOOLKIT
try:
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.styles import Style
    PT_AVAILABLE = True
except ImportError:
    PT_AVAILABLE = False

def smart_input(text, choices=None):
    """Hàm nhập liệu thông minh: Dùng Prompt Toolkit nếu có, không thì dùng input thường"""
    if PT_AVAILABLE:
        completer = WordCompleter(choices) if choices else None
        # Sử dụng ANSI để giữ màu sắc của prompt
        return prompt(ANSI(text), completer=completer).strip()
    else:
        # Fallback về input cũ nếu chưa cài prompt_toolkit
        sys.stdout.write(text)
        sys.stdout.flush()
        return input().strip()
# [END ADDED]

try:
    import uiautomator2 as u2
except ImportError:
    pass 
try:
    import adbutils 
except ImportError:
    pass

os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
try:
    time.tzset()
except:
    pass

SELECTED_DEVICE_ID = None
DEVICE_HISTORY = {} 

headers = {
    'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
    'Referer': 'https://app.golike.net/',
    'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': "Android",
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'T': 'VFZSak1FMTZZM3BOZWtFd1RtYzlQUT09',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
    'Content-Type': 'application/json;charset=utf-8'
}

# --- [MOD: HÀM CHẠY LỆNH ADB ẨN (KHÔNG HIỆN LOG RÁC)] ---
def run_silent_adb(cmd):
    try:
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        os.system(cmd + " >nul 2>&1") # Fallback cho Windows cũ
# --- [END MOD] ---

# [START ADDED] HÀM TÁCH USERNAME TỪ LINK ĐỂ CHECK
def get_target_from_link(url):
    """
    Tách username hoặc ID từ link Golike trả về.
    VD: https://www.instagram.com/ngoctrinh89/ -> return "ngoctrinh89"
    """
    try:
        if not url: return None
        # Xử lý link dạng instagram.com/username/
        if "instagram.com" in url:
            parts = url.rstrip('/').split('/')
            # parts thường là ['https:', '', 'www.instagram.com', 'username']
            if len(parts) >= 4:
                obj = parts[3]
                # Nếu là link bài viết (p, reel, tv) thì trả về None (hoặc xử lý sau)
                if obj in ['p', 'reel', 'reels', 'tv', 'stories', 'explore']:
                    return None 
                # Loại bỏ các tham số ?igshid=...
                return obj.split('?')[0]
    except:
        pass
    return None
# [END ADDED]

def get_connected_devices():
    devices = []
    try:
        for dev in adbutils.device_list():
             if dev.state == 'device':
                 try:
                     output = subprocess.check_output(f"adb -s {dev.serial} shell getprop ro.product.model", shell=True, timeout=2).decode('utf-8').strip()
                     model = output.replace("_", " ") if output else "Unknown"
                 except:
                      model = "Unknown" 
                 devices.append({'id': dev.serial, 'name': model})
        if devices:
            return devices
    except NameError:
         pass
    except Exception:
         pass
         
    try:
        output = subprocess.check_output("adb devices -l", shell=True).decode('utf-8').strip().split('\n')
        for line in output[1:]:
            if 'device' in line and 'model:' in line and 'offline' not in line:
                parts = line.split()
                dev_id = parts[0]
                model = "Unknown"
                for part in parts:
                    if part.startswith("model:"):
                        model = part.replace("model:", "").replace("_", " ")
                devices.append({'id': dev_id, 'name': model})
    except:
        pass
        
    return devices

def check_and_set_gboard(device_id):
    # --- [MOD: USER YÊU CẦU BỎ GBOARD - GIỮ CODE NHƯNG RETURN TRUE LUÔN] ---
    return True

# [MOD START] HÀM CÀI ĐẶT VÀ SỬ DỤNG ADB KEYBOARD (BẢN CŨ)
def setup_adb_keyboard_old(d, device_id):
    """Cài đặt và kích hoạt ADB Keyboard cũ (com.android.adbkeyboard)"""
    try:
        # Check xem đã cài chưa
        check_pkg = d.shell("pm list packages com.android.adbkeyboard").output
        
        if "com.android.adbkeyboard" not in check_pkg:
            print(f"\033[1;33m[{device_id}] Chưa cài ADB Keyboard. Đang tải và cài đặt...")
            # Link tải ADB Keyboard bản cũ ổn định (GitHub Mirror)
            url = "https://github.com/senzhk/ADBKeyBoard/raw/master/ADBKeyboard.apk" 
            try:
                # Tải về file tạm nếu chưa có
                if not os.path.exists("ADBKeyboard.apk"):
                    r = requests.get(url, allow_redirects=True, timeout=10)
                    with open("ADBKeyboard.apk", "wb") as f:
                        f.write(r.content)
                
                # Cài đặt qua ADB
                os.system(f"adb -s {device_id} install -r ADBKeyboard.apk")
                time.sleep(3)
                print(f"\033[1;32m[{device_id}] Cài đặt ADB Keyboard thành công!")
            except Exception as e:
                print(f"\033[1;31m[{device_id}] Lỗi tải/cài ADB Keyboard: {e}")

        # Kích hoạt và set mặc định
        d.shell("ime enable com.android.adbkeyboard/.AdbIME")
        d.shell("ime set com.android.adbkeyboard/.AdbIME")
    except Exception as e:
        print(f"\033[1;31m[{device_id}] Lỗi set ADB Keyboard: {e}")

def input_text_adb_keyboard(d, text):
    """Nhập text bằng broadcast intent (B64) - đặc trưng của ADB Keyboard cũ"""
    try:
        # Mã hóa Base64 để hỗ trợ Tiếng Việt và ký tự đặc biệt
        b64_text = base64.b64encode(text.encode('utf-8')).decode('utf-8')
        # Gửi broadcast ADB_INPUT_B64
        d.shell(f"am broadcast -a ADB_INPUT_B64 --es msg {b64_text}")
    except:
        # Fallback input text thường nếu lỗi
        text_safe = text.replace(" ", "%s")
        d.shell(f"input text {text_safe}")
# [MOD END]

def connect_device():
    print("\033[1;97m══════════════════════════════════════════════════════════════")
    ip_address = smart_input("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;36m✈ \033[1;32mNhập IP:PORT (Ví dụ 192.168.1.5:5555): ")
    
    if not ip_address:
        print("\033[1;31m[✖] IP không được để trống!")
        return

    pairing_code = smart_input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhập mã Pin 6 số (bỏ trống nếu đã xác minh): ")

    if pairing_code:
        print(f"\033[1;33m[!] Đang thực hiện Pairing với {ip_address}...")
        try:
            os.system(f"adb pair {ip_address} {pairing_code}")
            time.sleep(3)
        except:
            print("\033[1;31m[✖] Lỗi khi thực hiện lệnh Pair.")

    print(f"\033[1;33m[!] Đang kết nối ADB tới {ip_address}...")
    os.system(f"adb connect {ip_address}")
    time.sleep(2)

def chon_thiet_bi():
    while True:
        clear_screen()
        banner()
        data = requests.get("https://ipwho.is/").json()
        ip = data.get("ip", "N/A")
        city = data.get("city", "N/A")
        region = data.get("region", "N/A")
        country = data.get("country", "N/A")
        if region == city:
            hometown = "Không có dữ liệu huyện/quận"
        else:
            hometown = region
        print(f"\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37mĐịa chỉ IP  : \033[1;32m\033[1;31m\033[1;32m{ip}\033[1;31m\033[1;97m")
        print(f"\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37mThành phố   : \033[1;32m\033[1;31m\033[1;32m{city}\033[1;31m\033[1;97m")
        print(f"\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37mQuê quán    : \033[1;32m\033[1;31m\033[1;32m{hometown}\033[1;31m\033[1;97m")
        print(f"\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37mQuốc gia    : \033[1;32m\033[1;31m\033[1;32m{country}\033[1;31m\033[1;97m")
        
        devs = get_connected_devices()
        
        print("\033[1;97m══════════════════════════════════════════════════════════════")
        print(f"\033[1;97m \033[1;33mSTT \033[1;97m║ \033[1;32m{'NAME DEVICES'.ljust(15)} \033[1;97m║ \033[1;36m{'ID DEVICES'.ljust(20)} \033[1;97m║ \033[1;35mLAST ACCOUNT")
        print("\033[1;97m══════════════════════════════════════════════════════════════")
        
        if not devs:
            print(f"\033[1;31m{'[!] Không tìm thấy thiết bị nào!'.center(60)}")
        
        for i, dev in enumerate(devs):
            last_acc = DEVICE_HISTORY.get(dev['id'], "Chưa có")
            print(f" \033[1;33m[{i+1}] \033[1;97m║ \033[1;32m{dev['name'][:15].ljust(15)} \033[1;97m║ \033[1;36m{dev['id'][:20].ljust(20)} \033[1;97m║ \033[1;35m{last_acc}")
            
        print("\033[1;97m══════════════════════════════════════════════════════════════")
        print("\033[1;31m[\033[1;37madd\033[1;31m] \033[1;36m✈ \033[1;32mNhập \033[1;33madd \033[1;32mđể \033[1;36mthêm thiết bị (ADB)")
        print("\033[1;97m══════════════════════════════════════════════════════════════")
        
        choice = smart_input("\033[1;97m[\033[1;91m❣\033[1;97m] \033[1;36m✈ \033[1;32mNhập \033[1;33mSTT thiết bị cần chạy (cách nhau bằng dấu phẩy: 1,3,4) \033[1;32mhoặc \033[1;33mall \033[1;32mđể chọn tất cả: ", choices=['all', 'add'])
        
        if choice.lower() == 'add':
            connect_device()
            smart_input("\033[1;33mẤn Enter để tiếp tục...")
            continue
            
        selected_indices = []
        if choice.lower() == 'all':
            selected_indices = list(range(len(devs)))
        else:
            try:
                indices_str = [x.strip() for x in choice.split(',') if x.strip().isdigit()]
                for s in indices_str:
                    idx = int(s) - 1
                    if 0 <= idx < len(devs) and idx not in selected_indices:
                        selected_indices.append(idx)
            except:
                pass

        if selected_indices:
            selected_devices = [devs[i] for i in selected_indices]
            print(f"\033[1;32m[✔] Đã chọn {len(selected_devices)} thiết bị để chạy Multi-thread.")
            time.sleep(1)
            return selected_devices
        
        print("\033[1;31m[✖] Lựa chọn không hợp lệ hoặc không có thiết bị nào được chọn!")
        time.sleep(1)

def check_network_latency(device_id):
    try:
        cmd = f"adb -s {device_id} shell ping -c 1 -W 2 8.8.8.8"
        output = subprocess.check_output(cmd, shell=True).decode('utf-8')
        
        if "1 packets transmitted, 1 received" in output:
            time_ms = re.search(r'time=(\d+\.?\d*)', output)
            if time_ms:
                ms = float(time_ms.group(1))
                return True, ms
        return False, 999
    except:
        return False, 999

def wait_for_ui_stability(d, timeout=10, check_interval=1, device_id=""):
    start_time = time.time()
    last_ui = None
    stable_count = 0
    
    sys.stdout.write(f"\033[1;33m[{device_id}] Đang chờ UI ổn định... \r")
    sys.stdout.flush()

    try:
        while time.time() - start_time < timeout:
            current_ui = d.dump_hierarchy()
            
            if last_ui and current_ui == last_ui:
                stable_count += 1
                if stable_count >= 2:
                    sys.stdout.write(f"\033[1;32m[{device_id}] UI đã ổn định. ({round(time.time() - start_time, 2)}s)  \r")
                    sys.stdout.flush()
                    return True
            else:
                stable_count = 0
                
            last_ui = current_ui
            time.sleep(check_interval)
            
        sys.stdout.write(f"\033[1;31m[{device_id}] Timeout chờ UI ổn định! \r")
        sys.stdout.flush()
        return False
    except Exception as e:
        sys.stdout.write(f"\033[1;31m[{device_id}] Lỗi khi chờ UI: {str(e)[:30]} \r")
        sys.stdout.flush()
        return False

def run_nuoi_nick(d, device_id, so_lan_luot_home, so_lan_luot_reels):
    try:
        width, height = d.window_size()
        x_mid = width // 2
        y_start = int(height * 0.8)
        y_end = int(height * 0.2)
        y_small_scroll_start = int(height * 0.5)
        y_small_scroll_end = int(height * 0.3)
        
        sys.stdout.write(f"\033[1;97m[{device_id}] \033[1;36m✈ \033[1;33mĐang nuôi nick (Lướt Home)...      \r")
        sys.stdout.flush()

        # --- [MOD: LOGIC BANK RA HOME - SỬ DỤNG BACK - UI2 CHECKER] ---
        sys.stdout.write(f"\033[1;97m[{device_id}] \033[1;36m✈ \033[1;33mĐang Bank về Trang Chủ Instagram...      \r")
        sys.stdout.flush()
        
        retry_bank = 0
        max_retry_bank = 6
        is_at_home = False

        while retry_bank < max_retry_bank:
            # Dùng UI2 Selector để check xem có icon Home không
            # Description thường là "Home" hoặc "Trang chủ"
            # ResourceID thường là "com.instagram.android:id/tab_bar_button_home" hoặc ".../feed_tab"
            if d(descriptionMatches="^(Home|Trang chủ)$").exists or d(resourceIdMatches=".*tab_bar_button_home").exists:
                is_at_home = True
                break
            
            d.press("back")
            time.sleep(1.5)
            retry_bank += 1
        
        if not is_at_home:
             # Nếu Back hoài không được thì mới dùng lệnh ADB Start để force về activity chính
             cmd_open = f"adb -s {device_id} shell am start -n com.instagram.android/com.instagram.mainactivity.MainActivity"
             run_silent_adb(cmd_open)
             time.sleep(3)
        
        # Click vào Home Tab bằng UI Selector (Không dùng tọa độ)
        home_tab = d(descriptionMatches="^(Home|Trang chủ)$")
        if home_tab.exists:
             home_tab.click()
        else:
             home_tab_id = d(resourceIdMatches=".*tab_bar_button_home")
             if home_tab_id.exists:
                 home_tab_id.click()
        
        # --- [END MOD] ---

        real_swipe_home = random.randint(so_lan_luot_home, so_lan_luot_home + 2)
        
        for i in range(real_swipe_home):
            # Swipe vẫn phải dùng tọa độ tương đối (x, y) vì đây là hành động vuốt
            # Nhưng tọa độ này tính theo % màn hình, không fix cứng
            d.swipe(x_mid, y_start, x_mid, y_end, duration=random.uniform(0.3, 0.6))
            
            if random.random() < 0.3:
                d.swipe(x_mid, y_small_scroll_start, x_mid, y_small_scroll_end, duration=random.uniform(0.2, 0.4))
                time.sleep(random.uniform(1, 2))
                
            sleep_time = random.uniform(2, 6)
            sys.stdout.write(f"\033[1;97m[{device_id}] \033[1;36m✈ \033[1;33mĐang xem Home ({i+1}/{real_swipe_home})...      \r")
            sys.stdout.flush()
            time.sleep(sleep_time)

        if so_lan_luot_reels > 0:
            sys.stdout.write(f"\033[1;97m[{device_id}] \033[1;36m✈ \033[1;33mĐang chuẩn bị lướt Reels...      \r")
            sys.stdout.flush()
            
            reels_clicked = False
            # --- [MOD: PURE UI2 REELS SELECTOR] ---
            # Tìm nút Reels bằng Text/Description/ID
            reels_tab = d(descriptionMatches="^(Reels|Video)$")
            if reels_tab.exists:
                 reels_tab.click()
                 reels_clicked = True
            else:
                 reels_tab_id = d(resourceIdMatches=".*tab_clips")
                 if reels_tab_id.exists:
                     reels_tab_id.click()
                     reels_clicked = True

            if not reels_clicked:
                 sys.stdout.write(f"\033[1;31m[{device_id}] Không tìm thấy nút Reels (UI2)! Bỏ qua. \r")
                 # Không dùng fallback tọa độ nữa
            else:
                time.sleep(3)
                sys.stdout.write(f"\033[1;97m[{device_id}] \033[1;36m✈ \033[1;33m[Reels] Đã vào Reels. Bắt đầu lướt...      \r")
                sys.stdout.flush()
                time.sleep(1) 

                real_swipe_reels = random.randint(so_lan_luot_reels, so_lan_luot_reels + 2)
                
                for i in range(real_swipe_reels):
                     if random.random() < 0.4: 
                         sys.stdout.write(f"\033[1;97m[{device_id}] \033[1;36m✈ \033[1;33m[Reels] Check comment...      \r")
                         sys.stdout.flush()

                         # --- [MOD: UI2 SELECTOR FOR COMMENT] ---
                         cmt_reels = d(descriptionMatches="^(Bình luận|Comment)$")
                         if cmt_reels.exists:
                             cmt_reels.click()
                             time.sleep(random.uniform(1.5, 3)) 
                             # Scroll comment (Swipe tương đối)
                             d.swipe(x_mid, int(height * 0.7), x_mid, int(height * 0.4), duration=random.uniform(0.3, 0.5))
                             time.sleep(random.uniform(2, 4))
                             d.press("back")
                             time.sleep(1.5)
                         # --- [END MOD] ---

                     d.swipe(x_mid, y_start, x_mid, y_end, duration=random.uniform(0.3, 0.6))
                     
                     sleep_time = random.uniform(3, 8)
                     sys.stdout.write(f"\033[1;97m[{device_id}] \033[1;36m✈ \033[1;33mĐang xem Reels ({i+1}/{real_swipe_reels})...      \r")
                     sys.stdout.flush()
                     time.sleep(sleep_time)
                
                # Quay về home bằng UI2 Selector
                home_back = d(descriptionMatches="^(Home|Trang chủ)$")
                if home_back.exists:
                    home_back.click()
                time.sleep(2)

        d.app_stop("com.instagram.android")
        time.sleep(2) 
        
        sys.stdout.write(f"\033[1;97m[{device_id}] \033[1;36m✈ \033[1;32mNuôi nick xong! Đã đóng Instagram. Sẵn sàng job mới.      \r")
        sys.stdout.flush()
        
    except Exception as e:
        pass

# [MOD: HÀM AUTO VỚI LOGIC VERIFY CỰC MẠNH - KHÔNG BỎ SÓT TRƯỜNG HỢP]
def auto_via_adb(d, device_id, link, job_type, content=None):
    try:
        sys.stdout.write(f"\033[1;33m[{device_id}] Đang check mạng & mở Job... \r")
        sys.stdout.flush()
        
        # 1. CHECK MẠNG
        retry_net = 0
        while retry_net < 3:
            is_connected, ping_ms = check_network_latency(device_id)
            if is_connected and ping_ms < 450:
                break
            else:
                sys.stdout.write(f"\033[1;31m[{device_id}] Mạng lag ({ping_ms}ms), chờ ổn định... \r")
                sys.stdout.flush()
                time.sleep(2)
                retry_net += 1
        
        if not is_connected or ping_ms >= 450:
             return False, "Mạng không ổn định"
             
        # 2. MỞ LINK (DEEP LINK)
        cmd = f'adb -s {device_id} shell am start -a android.intent.action.VIEW -d "{link}" com.instagram.android'
        run_silent_adb(cmd)
        
        if not d.app_wait("com.instagram.android", timeout=15):
             return False, "Không mở được App Instagram"
        
        wait_for_ui_stability(d, timeout=8, check_interval=1, device_id=device_id)

        # ========================================================================
        # [START ADDED] LOGIC VERIFY TYPE & CONTENT (CHỐNG CLICK NHẦM Ở HOME)
        # ========================================================================
        
        # A. CHECK CHỐNG TRÔI VỀ HOME
        # Nếu mở link bài viết/profile mà giao diện hiện tại lại có Logo "Instagram" (đặc trưng của Home Feed)
        # Thì nghĩa là mở link thất bại hoặc bị văng ra Home -> STOP NGAY
        is_at_home = False
        # Check text "Instagram" ở ActionBar (chỉ có ở Home Feed)
        if d(description="Instagram").exists or d(text="Instagram").exists:
            # Check thêm xem có nút "Message" hay "Notification" không để chắc chắn là Home
            if d(resourceIdMatches=".*action_bar.*").exists:
                is_at_home = True
        
        if is_at_home:
            sys.stdout.write(f"\033[1;31m[{device_id}] CRITICAL: Đang ở Home Feed (Mở link fail)! Hủy Job để tránh like nhầm. \r")
            d.press("back") # Back thử phát cho chắc
            return False, "Lỗi: Trôi về Home"

        # B. CHECK ĐÚNG ĐỐI TƯỢNG (CHO JOB FOLLOW)
        if job_type == 'follow':
            target_user = get_target_from_link(link)
            if target_user:
                # Kiểm tra xem User ID trong link có xuất hiện trên màn hình không
                # Thường tên user sẽ nằm ở Title Bar hoặc Bio
                # Dùng textContains để tìm không phân biệt hoa thường check cho kỹ
                has_user_text = d(textContains=target_user).exists or \
                                d(descriptionContains=target_user).exists or \
                                d(resourceIdMatches=".*action_bar_title", textContains=target_user).exists
                
                if not has_user_text:
                    # Double check: Đôi khi User đổi tên hiển thị, check thử nút Follow xem
                    if not d(textMatches="^(Theo dõi|Follow|Follow Back)$").exists:
                        sys.stdout.write(f"\033[1;31m[{device_id}] CẢNH BÁO: Không thấy User '{target_user}' trên màn hình! \r")
                        return False, f"Sai Profile ({target_user})"

        # C. CHECK MÀN HÌNH POST (CHO JOB LIKE/COMMENT)
        if job_type in ['like', 'comment']:
            # Màn hình Post chuẩn phải có nút Back (mũi tên) ở góc trái trên
            # Hoặc Title là "Posts", "Reels", "Video", "Ảnh"
            # Nếu không có nút Back -> Có thể đang lạc ở đâu đó không phải bài post cụ thể
            has_back_btn = d(descriptionMatches="^(Back|Quay lại|Navigate up)$").exists or \
                           d(resourceIdMatches=".*action_bar_button_back").exists
            
            if not has_back_btn:
                # Trừ trường hợp Reels vuốt (Reels UI khác)
                if not d(resourceIdMatches=".*reel_viewer_.*").exists:
                    sys.stdout.write(f"\033[1;31m[{device_id}] CẢNH BÁO: Không phải giao diện xem bài viết (Thiếu nút Back)! \r")
                    return False, "Sai giao diện Post"

        # ========================================================================
        # [END ADDED] KẾT THÚC LOGIC VERIFY
        # ========================================================================

        # ---------------------------------------------------------
        # BỘ TỪ KHÓA NHẬN DIỆN TRẠNG THÁI & CHẶN (REGEX)
        # ---------------------------------------------------------
        
        # Regex phát hiện lỗi/chặn (Block/Verify/Limit/Spam)
        # Bao gồm: Try Again Later, Confirm, Verify, Suspicious, Action Blocked, Temporarily Blocked
        block_regex = "(?i).*(thử lại|try again|restrict|hạn chế|cộng đồng|community|blocked|chặn|verify|xác minh|suspicious|nghi ngờ|confirm|action blocked|temporarily).*"
        
        # Regex trạng thái Follow
        follow_btn_regex = "^(Theo dõi|Follow|Follow Back)$"
        following_regex = "^(Đang theo dõi|Following|Đã yêu cầu|Requested|Tin nhắn|Message|Unfollow)$"
        
        # Regex trạng thái Like
        like_btn_regex = "^(Thích|Like)$"
        liked_regex = "^(Đã thích|Unlike|Bỏ thích|Liked)$"

        # Regex trạng thái Comment
        comment_btn_regex = "^(Bình luận|Comment)$"
        post_btn_regex = "^(Đăng|Post)$"
        
        # ---------------------------------------------------------
        # BẮT ĐẦU XỬ LÝ THEO LOẠI JOB
        # ---------------------------------------------------------

        # [KIỂM TRA SƠ BỘ] Nếu vừa vào mà gặp Popup chặn ngay -> Báo lỗi luôn
        if d(textMatches=block_regex).exists:
            sys.stdout.write(f"\033[1;31m[{device_id}] Phát hiện Popup Chặn/Verify ngay khi vào! \r")
            d.press("back") # Thử tắt popup
            return False, "Acc bị dính Verify/Block"

        action_done = False

        if job_type == 'follow':
            # >> BƯỚC 1: CHECK ĐÃ LÀM CHƯA
            if d(textMatches=following_regex).exists:
                sys.stdout.write(f"\033[1;32m[{device_id}] Đã Follow từ trước (Check text)! \r")
                return True, "Đã làm từ trước"

            # Check Private (Riêng tư)
            # [MOD UPDATED] NẾU LÀ RIÊNG TƯ -> TRẢ VỀ FALSE ĐỂ SKIP JOB
            if d(textMatches="(?i).*(riêng tư|private).*").exists:
                sys.stdout.write(f"\033[1;33m[{device_id}] Acc Private (Riêng tư) -> Skip job. \r")
                return False, "Job Private - Bỏ qua"

            # >> BƯỚC 2: TÌM NÚT FOLLOW VÀ CLICK
            follow_btn = d(textMatches=follow_btn_regex)
            if follow_btn.exists:
                follow_btn.click()
                sys.stdout.write(f"\033[1;33m[{device_id}] Action: Click Follow... \r")
                time.sleep(random.uniform(3, 5)) # Chờ server phản hồi
                
                # >> BƯỚC 3: CHECK POPUP CHẶN SAU KHI CLICK
                if d(textMatches=block_regex).exists:
                     sys.stdout.write(f"\033[1;31m[{device_id}] LỖI: Bị chặn hành động Follow! \r")
                     d.press("back")
                     return False, "Bị chặn tính năng"

                # >> BƯỚC 4: VERIFY TRẠNG THÁI CUỐI CÙNG (QUAN TRỌNG)
                # Phải chuyển sang: Following, Requested, hoặc Message
                if d(textMatches=following_regex).exists:
                    action_done = True
                    # Double check chống nhả (đợi thêm 1 chút check lại)
                    time.sleep(1)
                    if not d(textMatches=following_regex).exists:
                         sys.stdout.write(f"\033[1;31m[{device_id}] LỖI: Instagram tự nhả Follow! \r")
                         action_done = False
                else:
                    sys.stdout.write(f"\033[1;31m[{device_id}] LỖI: Click rồi nhưng không đổi trạng thái! \r")
                    action_done = False
            else:
                sys.stdout.write(f"\033[1;31m[{device_id}] Không tìm thấy nút Follow! \r")
                return False, "Không tìm thấy nút Follow"

        elif job_type == 'like':
            # >> BƯỚC 1: CHECK ĐÃ LIKE CHƯA
            # Dùng Description (Unlike/Đã thích)
            if d(descriptionMatches=liked_regex).exists:
                 sys.stdout.write(f"\033[1;32m[{device_id}] Đã Like từ trước! \r")
                 return True, "Đã làm từ trước"
            
            # Swipe nhẹ 1 cái để đảm bảo nút Like lọt vào khung hình
            w, h = d.window_size()
            d.swipe(w//2, int(h * 0.7), w//2, int(h * 0.5), duration=0.2)
            time.sleep(1)

            # >> BƯỚC 2: TÌM NÚT LIKE
            like_btn = d(descriptionMatches=like_btn_regex)
            if not like_btn.exists:
                 # Fallback tìm theo ID
                 like_btn = d(resourceIdMatches=".*row_feed_button_like")
            
            if like_btn.exists:
                like_btn.click()
                sys.stdout.write(f"\033[1;33m[{device_id}] Action: Click Like... \r")
                time.sleep(random.uniform(2, 4))
                
                # >> BƯỚC 3: CHECK POPUP CHẶN
                if d(textMatches=block_regex).exists:
                     sys.stdout.write(f"\033[1;31m[{device_id}] LỖI: Bị chặn hành động Like! \r")
                     d.press("back")
                     return False, "Bị chặn Like"

                # >> BƯỚC 4: VERIFY TRẠNG THÁI (Description phải đổi thành Unlike/Đã thích/Liked)
                if d(descriptionMatches=liked_regex).exists:
                     action_done = True
                else:
                     # Thử check lại lần nữa phòng khi mạng lag
                     time.sleep(1)
                     if d(descriptionMatches=liked_regex).exists:
                         action_done = True
                     else:
                         sys.stdout.write(f"\033[1;31m[{device_id}] Thất bại: Like không ăn (Block ngầm)! \r")
                         action_done = False
            else:
                sys.stdout.write(f"\033[1;31m[{device_id}] Không tìm thấy nút Like (Check UI)! \r")
                return False, "Lỗi UI - Ko thấy nút Like"

        elif job_type == 'comment':
            if not content:
                return False, "Thiếu nội dung comment"
            
            # >> BƯỚC 1: TÌM NÚT ICON COMMENT
            cmt_btn = d(descriptionMatches=comment_btn_regex)
            if not cmt_btn.exists:
                 cmt_btn = d(resourceIdMatches=".*row_feed_button_comment")
            
            if cmt_btn.exists:
                cmt_btn.click()
                time.sleep(2) 
                
                # >> BƯỚC 2: CLICK VÀO VÙNG NHẬP LIỆU (FOOTER) ĐỂ HIỆN BÀN PHÍM
                
                found_input_area = False
                
                # Cách 1: Tìm theo ResourceID của layout footer
                input_placeholder = d(resourceIdMatches=".*layout_comment_thread_edittext")
                if input_placeholder.exists:
                    input_placeholder.click()
                    found_input_area = True
                else:
                    # Cách 2: Tìm theo text gợi ý (Thêm bình luận / Add a comment)
                    input_text_hint = d(textMatches="(?i)^(Thêm bình luận|Add a comment|Viết bình luận).*")
                    if input_text_hint.exists:
                        input_text_hint.click()
                        found_input_area = True
                
                time.sleep(1.5) # Chờ bàn phím nảy lên
                
                # >> BƯỚC 3: NHẬP LIỆU VỚI ADB KEYBOARD (OLD STYLE)
                # Tìm ô nhập liệu thực sự (thường là EditText)
                input_field = d(className="android.widget.EditText")
                
                if input_field.exists:
                    if not found_input_area: # Nếu chưa click footer thì click thẳng vào edittext
                        input_field.click()
                    
                    # [MOD: SỬ DỤNG ADB KEYBOARD CŨ ĐỂ NHẬP]
                    input_text_adb_keyboard(d, content)
                    
                    time.sleep(1.5)
                    
                    # >> BƯỚC 4: CLICK POST
                    post_btn = d(textMatches=post_btn_regex)
                    if post_btn.exists:
                        post_btn.click()
                        sys.stdout.write(f"\033[1;33m[{device_id}] Action: Posting Comment... \r")
                        time.sleep(5) # Comment cần chờ lâu hơn chút
                        
                        # >> BƯỚC 5: CHECK POPUP CHẶN COMMENT
                        if d(textMatches=block_regex).exists:
                             sys.stdout.write(f"\033[1;31m[{device_id}] LỖI: Bị chặn Comment (Action Blocked)! \r")
                             d.press("back") 
                             d.press("back") # Thoát khỏi màn hình comment
                             return False, "Bị chặn Comment"
                        
                        # >> BƯỚC 6: VERIFY THÀNH CÔNG
                        # Logic: Nếu nút "Post" biến mất VÀ không có popup lỗi -> Thành công
                        if d(textMatches=post_btn_regex).exists:
                             sys.stdout.write(f"\033[1;31m[{device_id}] Lỗi: Nút Post vẫn còn (Chưa gửi được)! \r")
                             d.press("back")
                             action_done = False
                        else:
                             action_done = True
                             # Back ra ngoài newsfeed
                             d.press("back") 
                    else:
                        sys.stdout.write(f"\033[1;31m[{device_id}] Không thấy nút Post/Đăng! \r")
                else:
                    sys.stdout.write(f"\033[1;31m[{device_id}] Không mở được ô nhập liệu (Không thấy EditText)! \r")
                    d.press("back")
            else:
                 sys.stdout.write(f"\033[1;31m[{device_id}] Không tìm thấy nút Icon Comment! \r")

        # KẾT LUẬN CUỐI CÙNG
        if action_done:
            return True, "Thành công"
        else:
            return False, "Verify thất bại"

    except Exception as e:
        # sys.stdout.write(f"\033[1;31m[{device_id}] Exception: {str(e)} \r")
        return False, "Lỗi Crash/Exception"

def bes4(url):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            content = response.text
            version_match = re.search(r'<span id="version_keyADB">(.*?)</span>', content)
            maintenance_match = re.search(r'<span id="maintenance_keyADB">(.*?)</span>', content)
            
            version = version_match.group(1).strip() if version_match else None
            maintenance = maintenance_match.group(1).strip() if maintenance_match else None
            
            return version, maintenance
    except:
        return None, None
    return None, None

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

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
\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m\033[1;32mADMIN:\033[38;2;255;190;0m NHƯ ANH ĐÃ THẤY EM   \033[1;32mPhiên Bản: \033[38;2;255;190;0mV5 (Fix Comment Real API)
\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m\033[1;32mNHóm Telegram: \033[38;2;255;190;0mhttps://t.me/se_meo_bao_an
\033[97m═══════════════════════════════════════════════════════════════════════ 
\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37mADB instagram\033[1;31m    : \033[1;97m\033[1;32mTool Sử Dụng golike Instagram\033[1;31m\033[1;97m
\033[97m════════════════════════════════════════════════
"""
    for char in banner_text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.00125)

if __name__ == "__main__":
    banner()
    import requests

def get_ip_info():
    try:
        r = requests.get("http://ip-api.com/json", timeout=5)
        data = r.json()

        if data.get("status") != "success":
            return None, None

        ip = data.get("query", "")
        region = data.get("regionName", "")

        if not ip:
            return None, None

        hometown = region if region else "Không xác định"
        return ip, hometown

    except Exception:
        return None, None


ip, hometown = get_ip_info()

if not ip:
    print("❌ Không lấy được IP (mạng lỗi hoặc API bị chặn)")
else:
    print(f"\033[1;31m[</>] \033[1;37mĐịa chỉ IP  : \033[1;32m{ip}")
    print(f"\033[1;31m[</>] \033[1;37mQuê quán    : \033[1;32m{hometown}")
    print("\033[1;97m════════════════════════════════════════════════")
    print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37mNhập 1 \033[1;32mđể vào Tool Instagram") 
    print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37mNhập 2 \033[38;2;255;190;0mĐể Xóa Authorization Hiện Tại")
    print("\033[1;97m════════════════════════════════════════════════")
    
    while True:
        try:
            choose = smart_input("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m\033[1;36m✈ \033[1;37mNhập Lựa Chọn (1 hoặc 2): ", choices=['1', '2'])
            
            if not choose.isdigit():
                 raise ValueError
            choose = int(choose)
            if choose != 1 and choose != 2:
                print("\033[1;31m\n❌ Lựa chọn không hợp lệ! Hãy nhập lại.")
                continue
            break
        except ValueError:
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;36m✈ \033[1;31mSai định dạng! Vui lòng nhập số.")

    file_path = "Authorization.txt"
    if choose == 2:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"\033[1;32m[✔] Đã xóa {file_path}!")
            except:
                print(f"\033[1;31m[✖] Không thể xóa {file_path}!")
        else:
            print(f"\033[1;33m[!] File {file_path} không tồn tại!")
        print("\033[1;33m👉 Vui lòng nhập lại thông tin!")

    if not os.path.exists(file_path):
        try:
            with open(file_path, "w") as f:
                pass
        except:
            print(f"\033[1;31m[✖] Không thể tạo file {file_path}!")
            sys.exit(1)

    author = ""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                author = f.read().strip()
        except:
            print(f"\033[1;31m[✖] Không thể đọc file {file_path}!")
            sys.exit(1)

    while not author:
        print("\033[1;97m════════════════════════════════════════════════")
        author = smart_input("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;36m✈ \033[1;32mNhập Authorization: ")

        try:
            with open(file_path, "w") as f:
                f.write(author)
        except:
            print(f"\033[1;31m[✖] Không thể ghi vào file {file_path}!")
            sys.exit(1)

    headers["Authorization"] = author

    print("\033[1;97m════════════════════════════════════════════════")
    print("\033[1;32m🚀 Đăng nhập thành công! Đang vào Tool Instagram...")
    time.sleep(1)

    selected_devices = chon_thiet_bi()
    
    if not selected_devices:
        print("\033[1;31m[✖] Không có thiết bị nào được chọn. Kết thúc chương trình.")
        sys.exit(0)

    def chonacc():
        try:
            url = 'https://gateway.golike.net/api/instagram-account'
            response = requests.get(url, headers=headers)
            return response.json()
        except:
            return None

    def nhannv(account_id):
        try:
            params = {
                'instagram_account_id': account_id,
                'data': 'null'
            }
            url = 'https://gateway.golike.net/api/advertising/publishers/instagram/jobs'
            response = requests.get(url, headers=headers, params=params)
            return response.json()
        except:
            return None

    def hoanthanh(ads_id, account_id):
        try:
            json_data = {
                'instagram_users_advertising_id': ads_id,
                'instagram_account_id': account_id,
                'async': True,
                'data': None
            }
            url = 'https://gateway.golike.net/api/advertising/publishers/instagram/complete-jobs'
            response = requests.post(url, headers=headers, json=json_data)
            
            if response.status_code != 200:
                 return {'error': f"Lỗi HTTP {response.status_code}"}
            
            return response.json()
        except:
            return {'error': 'Không thể kết nối đến server!'}

    def baoloi(ads_id, object_id, account_id, loai):
        try:
            json_data1 = {
                'description': 'Tôi đã làm Job này rồi',
                'users_advertising_id': ads_id,
                'type': 'ads',
                'provider': 'instagram',
                'fb_id': account_id,
                'error_type': 6 
            }
            requests.post('https://gateway.golike.net/api/report/send', headers=headers, json=json_data1)
            
            json_data = {
                'ads_id': ads_id,
                'object_id': object_id,
                'account_id': account_id,
                'type': loai
            }
            response = requests.post('https://gateway.golike.net/api/advertising/publishers/instagram/skip-jobs', headers=headers, json=json_data)
            return response.json()
        except:
            return None

    chontk_Instagram = chonacc()

    def dsacc(selected_device=None):
        global chontk_Instagram
        return chontk_Instagram["data"]

    def select_account_for_device_manual(dev, acc_list):
        while True:
            print("\033[1;97m════════════════════════════════════════════════")
            input_user = smart_input(f"\033[1;31m[{dev['id']}] \033[1;36m✈ \033[1;32mNhập \033[1;33mUsername Instagram \033[1;32mcho thiết bị \033[1;33m{dev['name']}\033[1;32m: ")
            
            if not input_user:
                print(f"\033[1;31m[!] Không được để trống!")
                continue

            found = False
            account_id = 0
            username_chon = ""
            
            for item in acc_list:
                if item["instagram_username"] == input_user:
                    found = True
                    account_id = item["id"]
                    username_chon = item["instagram_username"]
                    break
            
            if found:
                DEVICE_HISTORY[dev['id']] = username_chon
                print(f"\033[1;32m[{dev['id']}] Xác thực thành công: {username_chon} (ID: {account_id})")
                time.sleep(1)
                return account_id, username_chon
            else:
                print(f"\033[1;31m[{dev['id']}] User '{input_user}' chưa thêm vào Golike hoặc sai tên! Vui lòng nhập lại.")

    all_accs = chontk_Instagram.get("data", [])
    if not all_accs:
        print("Lỗi: Không lấy được danh sách tài khoản từ Golike. Kiểm tra lại Auth!")
        sys.exit()

    device_account_map = {}
    
    print("\033[1;97m════════════════════════════════════════════════")
    print("\033[1;33m[LƯU Ý] Nhập chính xác Username Instagram đã thêm vào Golike.")
    
    for dev in selected_devices:
        account_id, username = select_account_for_device_manual(dev, all_accs)
        device_account_map[dev['id']] = {
            'account_id': account_id,
            'username': username,
            'device_info': dev
        }
        
    clear_screen()
    banner()
    while True:
        try:      	
            delay_input = smart_input("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;36m✈ \033[1;32mNhập thời gian chờ (delay job): ")
            delay = int(delay_input)
            break
        except ValueError:
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;31mSai định dạng!!!")

    while True:
        try:
            freq_input = smart_input("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;32mLàm bao nhiêu Job thì nuôi nick 1 lần? (VD: 5): ")
            JOB_NUOI_FREQ = int(freq_input)
            if JOB_NUOI_FREQ <= 0:
                 print("\033[1;31m[!] Phải lớn hơn 0")
                 continue
            break
        except ValueError:
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;31mNhập số!")

    while True:
        try:
            swipes_input = smart_input("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;32mMỗi lần nuôi nick lướt Home bao nhiêu cái? (VD: 4): ")
            NUM_SWIPES = int(swipes_input)
            break
        except ValueError:
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;31mNhập số!")
            
    while True:
        try:
            reels_input = smart_input("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;32mMỗi lần nuôi nick lướt Reels bao nhiêu cái? (VD: 3): ")
            NUM_REELS_SWIPES = int(reels_input)
            break
        except ValueError:
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;31mNhập số!")

    while True:
        lannhan = smart_input("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;32mNhận tiền lần 2 nếu lần 1 fail? (y/n): ", choices=['y', 'n'])
        if lannhan != "y" and lannhan != "n":
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;31mNhập sai hãy nhập lại!!!")
            continue
        break

    while True:
        try:
            doiacc_input = smart_input("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;36m✈ \033[1;32mSố job fail để đổi acc Instagram (nhập 1 nếu k muốn dừng) : ")
            doiacc = int(doiacc_input)
            break
        except ValueError:
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;31mNhập vào 1 số!!!")

    while True:
        try:
            print("\033[1;97m════════════════════════════════════════════════")
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;32mNhập 1 : \033[1;33mChỉ nhận nhiệm vụ Follow")
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;32mNhập 2 : \033[1;33mChỉ nhận nhiệm vụ Like")
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;32mNhập 3 : \033[1;33mChỉ nhận nhiệm vụ Comment")
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;32mNhập 12 : \033[1;33mKết hợp Like + Follow")
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;32mNhập 23 : \033[1;33mKết hợp Like + Comment")
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;32mNhập 123: \033[1;33mKết hợp Like + Follow + Comment")
            print("\033[1;97m════════════════════════════════════════════════")
            chedo_input = smart_input("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;34mChọn lựa chọn: ", choices=['1','2','3','12','23','123'])
            chedo = int(chedo_input)
            
            s_chedo = str(chedo)
            if all(c in '123' for c in s_chedo):
                break
            else:
                print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;31mLựa chọn không hợp lệ!")
        except ValueError:
            print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m \033[1;36m✈ \033[1;31mNhập vào 1 số!!!")

    lam = []
    s_chedo = str(chedo)
    if '1' in s_chedo: lam.append("follow")
    if '2' in s_chedo: lam.append("like")
    if '3' in s_chedo: lam.append("comment")

    def run_device_worker(device_info, initial_account_id, initial_username, delay, job_nuoi_freq, num_swipes, num_reels_swipes, lannhan, doiacc, job_types):
        device_id = device_info['id']
        thread_name = device_id
        
        try:
            d = u2.connect(device_id)
            
            # [MOD START] SETUP ADB KEYBOARD OLD STYLE (TỰ TẢI VÀ CÀI ĐẶT)
            try:
                 # Tắt fast input của uiautomator2 để tránh xung đột
                 d.set_input_ime(False) 
                 # Cài đặt ADB Keyboard (bản cũ)
                 setup_adb_keyboard_old(d, device_id)
            except Exception as ime_error:
                 pass
            # [MOD END]
            
            # Setting timeout mặc định
            d.settings['operation_delay'] = (0, 0)
            d.settings['wait_timeout'] = 10
            
        except Exception as e:
            print(f"\033[1;31m[{thread_name}] Lỗi kết nối Uiautomator2: {e}. Thread dừng.")
            return

        current_account_id = initial_account_id
        current_username = initial_username
        
        dem = 0 
        tong = 0 
        checkdoiacc = 0 
        previous_job = None
        
        print(f"\033[1;36m[{thread_name}] \033[1;32mBắt đầu chạy. Acc: \033[1;33m{current_username}\033[1;32m. Tốc độ: {delay}s.")

        while True:
            try:
                if checkdoiacc >= doiacc and doiacc > 0: 
                    print(f"\033[1;31m[{thread_name}] Job fail quá nhiều! Nhập User mới.")
                    
                    new_acc_list = chonacc().get("data", [])
                    
                    while True:
                        idacc = smart_input(f"\033[1;31m[{thread_name}] Nhập Username Instagram mới: ")
                        
                        d_found = 0
                        new_account_id = 0
                        new_username_chon = ""
                        
                        for item in new_acc_list:
                            if item["instagram_username"] == idacc:
                                d_found = 1
                                new_account_id = item["id"]
                                new_username_chon = item["instagram_username"]
                                break
                        
                        if d_found == 1:
                            current_account_id = new_account_id
                            current_username = new_username_chon
                            DEVICE_HISTORY[device_id] = current_username
                            checkdoiacc = 0
                            print(f"\033[1;32m[{thread_name}] Đã đổi sang Acc: {current_username}")
                            break
                        else:
                            print(f"\033[1;31m[{thread_name}] Username không tồn tại trong Golike! Thử lại.")

                sys.stdout.write(f"\033[1;35m[{thread_name}] Đang Tìm Nhiệm vụ:>        \r")
                sys.stdout.flush()
                
                nhanjob = None
                for _ in range(3): 
                    try:
                        nhanjob = nhannv(current_account_id)
                        if nhanjob:
                            break
                    except:
                        time.sleep(1)
                
                if not nhanjob or nhanjob.get("status") != 200 or "data" not in nhanjob or not isinstance(nhanjob["data"], dict) or not nhanjob["data"].get("link"):
                    sys.stdout.write(f"\033[1;31m[{thread_name}] Hết Job - Không có link!        \r")
                    sys.stdout.flush()
                    time.sleep(2)
                    continue

                ads_id = nhanjob["data"]["id"]
                link = nhanjob["data"]["link"]
                object_id = nhanjob["data"]["object_id"]
                loai = nhanjob["data"]["type"]
                
                # [MOD: FIX LẤY ĐÚNG NỘI DUNG COMMENT]
                # Ưu tiên object_content trước, sau đó là comment_content
                comment_content = nhanjob["data"].get("object_content") or nhanjob["data"].get("comment_content") or nhanjob["data"].get("content") or nhanjob["data"].get("comment")

                if previous_job and \
                   previous_job["data"]["link"] == nhanjob["data"]["link"] and \
                   previous_job["data"]["type"] == nhanjob["data"]["type"]:
                    sys.stdout.write(f"\033[1;31m[{thread_name}] Job trùng - Bỏ qua!        \r")
                    sys.stdout.flush()
                    time.sleep(2)
                    try:
                        baoloi(ads_id, object_id, current_account_id, loai)
                        checkdoiacc += 1 
                    except:
                        pass
                    continue
                    
                previous_job = nhanjob

                if loai not in job_types:
                    try:
                        baoloi(ads_id, object_id, current_account_id, loai)
                        sys.stdout.write(f"\033[1;31m[{thread_name}] Đã bỏ qua job {loai}!        \r")
                        sys.stdout.flush()
                        time.sleep(1)
                        continue
                    except:
                        pass
                
                sys.stdout.write(f"\033[1;33m[{thread_name}] Đang Auto {loai}...         \r")
                sys.stdout.flush()
                
                adb_success, adb_message = auto_via_adb(d, device_id, link, loai, comment_content)
                
                if not adb_success:
                     sys.stdout.write(f"\033[1;31m[{thread_name}] Fail: {adb_message} \r")
                     try:
                         baoloi(ads_id, object_id, current_account_id, loai)
                         checkdoiacc += 1
                     except:
                         pass
                     continue

                for remaining_time in range(delay, -1, -1):
                    colors = [
                        "\033[1;37mT\033[1;36mu\033[1;35ms \033[1;32mT\033[1;31mO\033[1;34mO\033[1;33mL\033[1;36m - Phong\033[1;36m Tus \033[1;31m\033[1;32m",
                        "\033[1;34mT\033[1;31mu\033[1;37ms \033[1;36mT\033[1;32mO\033[1;35mO\033[1;37mL\033[1;32m - Phong\033[1;34m Tus \033[1;31m\033[1;32m",
                        "\033[1;31mT\033[1;37mu\033[1;36ms \033[1;33mT\033[1;35mO\033[1;32mO\033[1;34mL\033[1;37m - Phong\033[1;33m Tus \033[1;31m\033[1;32m",
                        "\033[1;32mT\033[1;33mu\033[1;34ms \033[1;35mT\033[1;36mO\033[1;37mO\033[1;36mL\033[1;34m - Phong\033[1;31m Tus \033[1;31m\033[1;32m",
                        "\033[1;37mT\033[1;36mu\033[1;35ms \033[1;32mT\033[1;31mO\033[1;34mO\033[1;33mL\033[1;36m - Phong\033[1;36m Tus \033[1;31m\033[1;32m",
                        "\033[1;34mT\033[1;31mu\033[1;37ms \033[1;36mT\033[1;32mO\033[1;35mO\033[1;37mL\033[1;32m - Phong\033[1;34m Tus \033[1;31m\033[1;32m",
                        "\033[1;31mT\033[1;37mu\033[1;36ms \033[1;33mT\033[1;35mO\033[1;32mO\033[1;34mL\033[1;37m - Phong\033[1;33m Tus \033[1;31m\033[1;32m",
                        "\033[1;32mT\033[1;33mu\033[1;34ms \033[1;35mT\033[1;36mO\033[1;37mO\033[1;36mL\033[1;34m - Phong\033[1;31m Tus \033[1;31m\033[1;32m",
                    ]
                    sys.stdout.write(f"\r[{thread_name}] {colors[remaining_time % 8]}|{remaining_time}| \033[1;31m")
                    sys.stdout.flush()
                    # [MOD: FIX DELAY CHẠY NHANH X2 - CHỈNH VỀ 1S]
                    time.sleep(1.0)
                
                sys.stdout.write(f"\r[{thread_name}] Đang Nhận Tiền Lần 1:>        \r")
                sys.stdout.flush()
                
                nhantien = hoanthanh(ads_id, current_account_id)

                ok = 0
                max_loop = 2 if lannhan == "y" else 1 
                current_loop = 1
                
                while current_loop <= max_loop:
                    if nhantien and nhantien.get("status") == 200:
                        ok = 1
                        dem += 1
                        tien = nhantien["data"]["prices"]
                        tong += tien
                        now = datetime.now()
                        time_str = now.strftime("%H:%M:%S")
                        
                        sys.stdout.write("                                                    \r")
                        msg = (f"\033[1;31m| \033[1;36m{dem}\033[1;31m\033[1;97m | "
                               f"\033[1;33m{time_str}\033[1;31m\033[1;97m | "
                               f"\033[1;32msuccess\033[1;31m\033[1;97m | "
                               f"\033[1;31m{nhantien['data']['type']}\033[1;31m\033[1;32m\033[1;97m |"
                               f"\033[1;35m {ads_id} \033[1;97m|\033[1;32m{device_id[:6]}\033[1;97m|"
                               f"\033[1;97m \033[1;32m+{tien} \033[1;97m| "
                               f"\033[1;33m{tong}")
                        print(f"\033[1;36m[{thread_name}] \033[0m{msg}")
                        
                        if dem % job_nuoi_freq == 0:
                            run_nuoi_nick(d, device_id, num_swipes, num_reels_swipes)
                        
                        checkdoiacc = 0
                        break
                    else:
                        current_loop += 1
                        if current_loop > max_loop:
                            break
                        sys.stdout.write(f"\033[1;97m[{thread_name}] Đang Nhận Tiền Lần 2:>        \r")
                        sys.stdout.flush()
                        nhantien = hoanthanh(ads_id, current_account_id)

                if ok != 1:
                    while True:
                        try:
                            baoloi(ads_id, object_id, current_account_id, loai)
                            sys.stdout.write(f"\033[1;31m[{thread_name}] Đã bỏ qua job:>        \r")
                            sys.stdout.flush()
                            time.sleep(1)
                            checkdoiacc += 1
                            break
                        except:
                            pass
            
            except Exception as e:
                print(f"\033[1;31m[{thread_name}] Lỗi không xác định: {e}")
                time.sleep(5)

    banner()
    print("\033[1;31m[\033[1;37m</>\033[1;31m] \033[1;37m\033[1;97m STARTING MULTI-THREADING...")
    print("\033[1;97m════════════════════════════════════════════════")
    print("\033[1;36m|STT\033[1;97m| \033[1;33mThời gian ┊ \033[1;32mStatus | \033[1;31mType Job | \033[1;35mJob ID    |\033[1;32mDev ID| \033[1;32mXu |\033[1;33m Tổng")
    print("\033[1;97m════════════════════════════════════════════════")

    threads = []
    
    for dev_id, acc_data in device_account_map.items():
        dev_info = acc_data['device_info']
        t = threading.Thread(
            target=run_device_worker,
            args=(dev_info, acc_data['account_id'], acc_data['username'], delay, JOB_NUOI_FREQ, NUM_SWIPES, NUM_REELS_SWIPES, lannhan, doiacc, lam),
            name=f"Worker-{dev_id}"
        )
        threads.append(t)
        t.start()

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\n\033[1;31m[!] Chương trình bị dừng bởi người dùng (Ctrl+C).")
        sys.exit(0)