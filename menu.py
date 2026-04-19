#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import subprocess

# ===== FIX ENCODING CHO WINDOWS =====
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

# ===== CÀI THƯ VIỆN GIAO DIỆN =====
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich import box
except ImportError:
    print("[*] Đang thiết lập hệ thống...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rich", "-q"])
    from rich.console import Console
    from rich.panel import Panel
    from rich import box

console = Console()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

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
\033[38;2;255;200;140m[\033[38;2;245;245;245m</>\033[38;2;255;200;140m] \033[38;2;200;160;255mADMIN:\033[38;2;255;235;180m NHƯ ANH ĐÃ THẤY EM   \033[38;2;255;220;160mPhiên Bản: \033[38;2;120;255;220mv3.4
\033[38;2;255;200;140m[\033[38;2;245;245;245m</>\033[38;2;255;200;140m] \033[38;2;200;160;255mNhóm Telegram: \033[38;2;120;255;220mhttps://t.me/se_meo_bao_an
\033[38;2;190;235;210m───────────────────────────────────────────────────────────────────────\033[0m
"""
    print(banner_text)
    
    # Khung thông báo khóa cứng
    console.print(Panel(
        f"[#ff4d6d] PHIÊN BẢN ĐÃ CŨ - TOOL BỊ KHÓA![/]\n\n"
        f"[#ffffff]Phiên bản này đã ngừng hoạt động để đảm bảo an toàn.\n"
        f"Bạn bắt buộc phải tải lại bản update mới nhất.\n\n"
        f"[#ff9ecb]👉 Lấy link tải bản mới tại nhóm Telegram:[/]\n"
        f"[bold #00ffff]➤ https://t.me/se_meo_bao_an[/]\n\n"
        f"[#888888](TOOL TÊN tustool3.13.py Vui lòng copy link trên và dán vào trình duyệt hoặc Telegram)[/]",
        border_style="#ff4d6d",
        box=box.DOUBLE,
        title="[bold #ff4d6d]YÊU CẦU CẬP NHẬT BẮT BUỘC[/]",
        title_align="center",
        width=65
    ))
    
    # Chặn dừng ở đây, nhấn Enter thì thoát luôn
    input("\nNhấn Enter để thoát chương trình...")
    sys.exit(0)

if __name__ == "__main__":
    banner() # <-- Đã sửa lại thành gọi hàm banner() thay vì show_lock_screen()
