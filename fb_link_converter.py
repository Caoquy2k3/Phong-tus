from urllib.parse import unquote
from bs4 import BeautifulSoup
from curl_cffi import requests


def get_and_decode_video_link(url):
  url = url.strip()
  if not url: 
    return None

  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
          ' like Gecko) Chrome/139.0.0.0 Safari/537.36'
      ),
      'Accept': (
          'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
      ),
      'Accept-Language': 'en-US,en;q=0.5',
  }

  try:
    response = requests.get(
        url, headers=headers, impersonate='chrome110', allow_redirects=True
    )
    
    if response.status_code in [404, 410] or "This content isn't available" in response.text:
      return f"[DIE LINK] {unquote(url)}"

    # Trả về thẳng Request URL đích sau khi đã redirect (Chính là dòng Request URL trong ảnh)
    if response.status_code == 200:
      return unquote(response.url)
      
  except Exception:
    pass

  return unquote(url)


if __name__ == '__main__':
  user_url = input('Nhập link vào đây: ')
  print(get_and_decode_video_link(user_url))
