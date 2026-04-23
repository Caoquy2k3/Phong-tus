import requests
import json
import time
import random
import re
import os
import sys
import uuid
from typing import Dict, Any, Optional, List

# ==================== MÀU SẮC RGB ====================
class Colors:
    """Lớp quản lý màu sắc RGB gradient"""
    @staticmethod
    def rgb(r, g, b):
        return f"\033[38;2;{r};{g};{b}m"
    
    # Màu gradient từ tím -> hồng -> xanh
    PURPLE1 = rgb(153, 51, 255)
    PURPLE2 = rgb(170, 70, 255)
    PURPLE3 = rgb(190, 90, 255)
    PURPLE4 = rgb(210, 110, 240)
    PURPLE5 = rgb(230, 130, 220)
    PINK1 = rgb(240, 150, 200)
    PINK2 = rgb(200, 200, 255)
    BLUE1 = rgb(150, 230, 255)
    BLUE2 = rgb(120, 255, 230)
    
    # Màu chức năng
    YELLOW = rgb(255, 200, 140)
    WHITE = rgb(245, 245, 245)
    LAVENDER = rgb(200, 160, 255)
    GOLD = rgb(255, 235, 180)
    CYAN = rgb(120, 255, 220)
    GREEN = rgb(190, 235, 210)
    RED = rgb(255, 100, 100)
    RESET = "\033[0m"

# ==================== BANNER ====================
def banner():
    """Hiển thị banner với gradient màu"""
    os.system('clear' if os.name == 'posix' else 'cls')
    
    banner_lines = [
        (f"{Colors.PURPLE1}▄▄▄█████▓ █    ██   ██████    ▄▄▄█████▓ ▒█████   ▒█████   ██▓", Colors.PURPLE1),
        (f"{Colors.PURPLE2}▓  ██▒ ▓▒ ██  ▓██▒▒██    ▒    ▓  ██▒ ▓▒▒██▒  ██▒▒██▒  ██▒▓██▒", Colors.PURPLE2),
        (f"{Colors.PURPLE3}▒ ▓██░ ▒░▓██  ▒██░░ ▓██▄      ▒ ▓██░ ▒░▒██░  ██▒▒██░  ██▒▒██░", Colors.PURPLE3),
        (f"{Colors.PURPLE4}░ ▓██▓ ░ ▓▓█  ░██░  ▒   ██▒   ░ ▓██▓ ░ ▒██   ██░▒██   ██░▒██░", Colors.PURPLE4),
        (f"{Colors.PURPLE5}  ▒██▒ ░ ▒▒█████▓ ▒██████▒▒     ▒██▒ ░ ░ ████▓▒░░ ████▓▒░░██████▒", Colors.PURPLE5),
        (f"{Colors.PINK1}  ▒ ░░   ░▒▓▒ ▒ ▒ ▒ ▒▓▒ ▒ ░     ▒ ░░   ░ ▒░▒░▒░ ░ ▒░▒░▒░ ░ ▒░▓  ░", Colors.PINK1),
        (f"{Colors.PINK2}    ░    ░░▒░ ░ ░ ░ ░▒  ░ ░       ░      ░ ▒ ▒░   ░ ▒ ▒░ ░ ░ ▒  ░", Colors.PINK2),
        (f"{Colors.BLUE1}  ░       ░░░ ░ ░ ░  ░  ░       ░      ░ ░ ░ ▒  ░ ░ ░ ▒    ░ ░", Colors.BLUE1),
        (f"{Colors.BLUE2}            ░           ░                  ░ ░      ░ ░      ░  ░", Colors.BLUE2),
    ]
    
    for line, color in banner_lines:
        print(line)
    
    print(f"{Colors.YELLOW}[{Colors.WHITE}</>{Colors.YELLOW}] {Colors.LAVENDER}ADMIN:{Colors.GOLD} NHƯ ANH ĐÃ THẤY EM   {Colors.YELLOW}Phiên Bản: {Colors.CYAN}v4.0.3 (Fixed GraphQL)")
    print(f"{Colors.YELLOW}[{Colors.WHITE}</>{Colors.YELLOW}] {Colors.LAVENDER}Nhóm Telegram: {Colors.CYAN}https://t.me/se_meo_bao_an")
    print(f"{Colors.GREEN}───────────────────────────────────────────────────────────────────────{Colors.RESET}")

def log_success(msg):
    print(f"{Colors.GREEN}[✓] {msg}{Colors.RESET}")

def log_error(msg):
    print(f"{Colors.RED}[✗] {msg}{Colors.RESET}")

def log_info(msg):
    print(f"{Colors.CYAN}[i] {msg}{Colors.RESET}")

def log_warning(msg):
    print(f"{Colors.YELLOW}[!] {msg}{Colors.RESET}")

# ==================== CÁC LỚP CHÍNH ====================
class CookieHandler:
    @staticmethod
    def to_dict(cookie_str: str) -> Dict[str, str]:
        return {k.strip(): v.strip() for item in cookie_str.split(";") 
                if "=" in item for k, v in [item.split("=", 1)]}

class NumberEncoder:
    @staticmethod
    def to_base36(num: int) -> str:
        chars = "0123456789abcdefghijklmnopqrstuvwxyz"
        if num == 0:
            return "0"
        result = ""
        while num:
            num, remainder = divmod(num, 36)
            result = chars[remainder] + result
        return result

class HTMLExtractor:
    @staticmethod
    def find_pattern(html: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, html)
        return match.group(1) if match else None
    
    @staticmethod
    def extract_token(html: str) -> Optional[str]:
        patterns = [
            r'name="fb_dtsg" value="([^"]+)"',
            r'DTSGInitialData",\[\],{"token":"([^"]+)"}',
            r'DTSGInitialData".*?"token":"([^"]+)"', 
            r'"fb_dtsg":"([^"]+)"',
            r'"token":"([^"]+)"'
        ]
        for pattern in patterns:
            result = HTMLExtractor.find_pattern(html, pattern)
            if result:
                return result
        return None
    
    @staticmethod
    def extract_lsd(html: str) -> Optional[str]:
        patterns = [
            r'name="lsd" value="([^"]+)"',
            r'LSD",\[\],{"token":"([^"]+)"}',
            r'LSD".*?"token":"([^"]+)"'
        ]
        for pattern in patterns:
            result = HTMLExtractor.find_pattern(html, pattern)
            if result:
                return result
        return None
    
    @staticmethod
    def extract_user_id(html: str, cookie: str) -> Optional[str]:
        cookie_match = re.search(r'c_user=(\d+)', cookie)
        if cookie_match:
            return cookie_match.group(1)
            
        patterns = [r'"actorID":"(\d+)"', r'"USER_ID":"(\d+)"']
        for pattern in patterns:
            result = HTMLExtractor.find_pattern(html, pattern)
            if result:
                return result
        return None
    
    @staticmethod
    def extract_revision(html: str) -> Optional[str]:
        patterns = [r'client_revision["\s:]+(\d+)', r'"client_revision":(\d+)']
        for pattern in patterns:
            result = HTMLExtractor.find_pattern(html, pattern)
            if result:
                return result
        return None
    
    @staticmethod
    def extract_jazoest(html: str) -> Optional[str]:
        patterns = [r'name="jazoest" value="([^"]+)"', r'jazoest=(\d+)']
        for pattern in patterns:
            result = HTMLExtractor.find_pattern(html, pattern)
            if result:
                return result
        return None

class FacebookSession:
    def __init__(self, cookie: str):
        self.cookie = cookie
        self.token = None
        self.user_id = None
        self.revision = None
        self.jazoest = None
        self.lsd = None

    def authenticate(self) -> Dict[str, Any]:
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "accept-language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "cache-control": "max-age=0",
            "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        }
        try:
            headers["cookie"] = self.cookie
            
            response = requests.get("https://www.facebook.com/", headers=headers, timeout=30)
            html = response.text
            
            self.user_id = HTMLExtractor.extract_user_id(html, self.cookie)
            self.token = HTMLExtractor.extract_token(html)
            self.revision = HTMLExtractor.extract_revision(html)
            self.jazoest = HTMLExtractor.extract_jazoest(html)
            self.lsd = HTMLExtractor.extract_lsd(html)
            
            if not self.token or not self.user_id:
                if not self.token:
                    with open("debug_error.html", "w", encoding="utf-8") as f:
                        f.write(html)
                return {"success": False, "error": "Failed to extract token (fb_dtsg). Cookie có thể bị checkpoint/hết hạn."}
            
            return {"success": True, "token": self.token, "user_id": self.user_id,
                    "revision": self.revision or "", "jazoest": self.jazoest or "", "lsd": self.lsd or ""}
        except Exception as e:
            return {"success": False, "error": str(e)}

class GenData:
    def __init__(self, session: FacebookSession):
        self.session = session
        self.request_counter = 0
    
    def build(self, bio: str, name: str) -> Dict[str, Any]:
        self.request_counter += 1   
        category_ids = [169421023103905, 2347428775505624, 192614304101075, 
                       145118935550090, 1350536325044173, 471120789926333, 
                       180410821995109, 357645644269220, 2705]
        category = random.choice(category_ids)
        
        payload = {
            'fb_api_caller_class': 'RelayModern',
            'fb_api_req_friendly_name': 'AdditionalProfilePlusCreationMutation',
            'server_timestamps': 'true',
            "fb_dtsg": self.session.token,
            "jazoest": self.session.jazoest,
            "__a": "1",
            "__user": str(self.session.user_id),
            "__req": NumberEncoder.to_base36(self.request_counter),
            "__rev": self.session.revision,
            "av": str(self.session.user_id),
            "lsd": self.session.lsd,
            'variables': json.dumps({
                "input": {
                    "bio": bio,
                    "categories": [str(category)],
                    "creation_source": "comet",
                    "name": name,
                    "off_platform_creator_reachout_id": None,
                    "page_referrer": "launch_point",
                    "actor_id": str(self.session.user_id),
                    "client_mutation_id": str(uuid.uuid4())
                }
            }),
            # TODO: Cập nhật doc_id mới lấy từ F12 vào đây nếu doc_id này đã tịt
            'doc_id': '23863457623296585'
        }
        return payload

class REGPRO5:
    def __init__(self, cookie: str, delay: float = 2.0):
        self.cookie = cookie
        self.delay = delay
        self.session = FacebookSession(cookie)
        self.payload_builder = None
        self.ready = False
        self.info = None

    def login(self) -> bool:
        self.info = self.session.authenticate()
        if self.info.get("success"):
            self.payload_builder = GenData(self.session)
            self.ready = True
            log_success(f"Login thành công - User ID: {self.info['user_id']}")
            return True
        log_error(f"Login thất bại: {self.info.get('error', 'Unknown error')}")
        return False

    def REG(self, bio: str, name: str) -> Dict[str, Any]:
        if not self.ready:
            return {"success": False, "error": "Not logged in"}
        
        payload = self.payload_builder.build(bio, name)
        
        headers = {
            "accept": "*/*",
            "accept-language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://www.facebook.com",
            "referer": "https://www.facebook.com/",
            "sec-ch-prefers-color-scheme": "dark",
            "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "x-asbd-id": "129477",
            "x-fb-lsd": self.session.lsd or "",
            "cookie": self.cookie,
            'x-fb-friendly-name': 'AdditionalProfilePlusCreationMutation',
        }
        
        try:
            response = requests.post('https://www.facebook.com/api/graphql/', 
                                    headers=headers, data=payload, timeout=30)
            
            raw_text = response.text
            
            # Xóa prefix "for (;;);" của FB trước khi parse
            if raw_text.startswith("for (;;);"):
                raw_text = raw_text.replace("for (;;);", "", 1)
                
            try:
                resp_json = json.loads(raw_text)
            except json.decoder.JSONDecodeError:
                error_preview = raw_text[:100].replace('\n', ' ')
                return {"success": False, "error": f"Parse JSON thất bại. Status: {response.status_code}. Preview: {error_preview}..."}
            
            if 'errors' in resp_json:
                error_msg = resp_json['errors'][0].get('message', 'Unknown error')
                return {"success": False, "error": f"API Error: {error_msg}"}
            
            if 'data' not in resp_json:
                return {"success": False, "error": "Response missing 'data' field"}
            
            mutation_data = resp_json['data'].get('additional_profile_plus_create')
            if not mutation_data:
                return {"success": False, "error": "Missing mutation response"}
            
            if mutation_data.get('error_message'):
                return {"success": False, "error": mutation_data['error_message']}
            
            profile_id = mutation_data.get('additional_profile', {}).get('id')
            if profile_id:
                return {"success": True, "profile_id": profile_id}
            return {"success": False, "error": "No profile ID returned"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

def create_multiple_profiles(cookie: str, profiles_data: List[tuple], delay: float):
    """Tạo nhiều profile với delay giữa các lần"""
    banner()
    log_info(f"Bắt đầu tạo {len(profiles_data)} profile")
    log_info(f"Delay giữa các lần: {delay} giây")
    print()
    
    creator = REGPRO5(cookie, delay)
    if not creator.login():
        log_error("Không thể đăng nhập. Kiểm tra cookie!")
        return
    
    results = []
    for i, (bio, name) in enumerate(profiles_data, 1):
        log_info(f"[{i}/{len(profiles_data)}] Đang tạo: {name}")
        result = creator.REG(bio, name)
        
        if result.get("success"):
            log_success(f"✓ Tạo thành công! Profile ID: {result['profile_id']}")
            results.append({"index": i, "name": name, "success": True, "profile_id": result['profile_id']})
        else:
            log_error(f"✗ Tạo thất bại: {result.get('error', 'Unknown error')}")
            results.append({"index": i, "name": name, "success": False, "error": result.get('error')})
        
        if i < len(profiles_data):
            log_info(f"Chờ {delay} giây trước lần tiếp theo...")
            time.sleep(delay)
        print()
    
    # Tổng kết
    print(f"{Colors.GREEN}═══════════════════════════════════════════════════════{Colors.RESET}")
    log_info("KẾT QUẢ TỔNG HỢP:")
    success_count = sum(1 for r in results if r["success"])
    for r in results:
        if r["success"]:
            log_success(f"  {r['index']}. {r['name']} → ID: {r['profile_id']}")
        else:
            log_error(f"  {r['index']}. {r['name']} → {r.get('error', 'Failed')}")
    print(f"{Colors.CYAN}───────────────────────────────────────────────────────{Colors.RESET}")
    log_info(f"Thành công: {success_count}/{len(profiles_data)}")
    print(f"{Colors.GREEN}═══════════════════════════════════════════════════════{Colors.RESET}")

def main():
    banner()
    
    # Nhập cookie
    print()
    cookie = input(f"{Colors.YELLOW}[?] {Colors.WHITE}Nhập cookie Facebook: {Colors.RESET}").strip()
    
    if not cookie:
        log_error("Cookie không được để trống!")
        return
    
    # Nhập delay
    try:
        delay = float(input(f"{Colors.YELLOW}[?] {Colors.WHITE}Nhập delay giữa các lần tạo (giây, mặc định 2.0): {Colors.RESET}").strip() or "2.0")
        if delay < 1:
            log_warning("Delay quá nhỏ, đề xuất >= 2 giây để tránh rate limit")
    except ValueError:
        delay = 2.0
        log_warning("Giá trị không hợp lệ, dùng delay mặc định 2 giây")
    
    # Nhập số lượng profile
    try:
        num_profiles = int(input(f"{Colors.YELLOW}[?] {Colors.WHITE}Số lượng profile cần tạo: {Colors.RESET}").strip())
        if num_profiles <= 0:
            log_error("Số lượng phải > 0")
            return
    except ValueError:
        log_error("Vui lòng nhập số hợp lệ")
        return
    
    # Nhập thông tin từng profile
    profiles = []
    print()
    for i in range(1, num_profiles + 1):
        log_info(f"Profile thứ {i}:")
        name = input(f"  {Colors.LAVENDER}Tên page: {Colors.RESET}").strip()
        bio = input(f"  {Colors.LAVENDER}BIO: {Colors.RESET}").strip()
        profiles.append((bio, name))
        print()
    
    # Xác nhận
    print(f"{Colors.YELLOW}───────────────────────────────────────────────────────{Colors.RESET}")
    log_info(f"Sẽ tạo {num_profiles} profile với delay {delay} giây")
    confirm = input(f"{Colors.YELLOW}[?] {Colors.WHITE}Bắt đầu? (y/N): {Colors.RESET}").strip().lower()
    
    if confirm == 'y':
        create_multiple_profiles(cookie, profiles, delay)
    else:
        log_info("Đã hủy")

if __name__ == "__main__":
    main()
