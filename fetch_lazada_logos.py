import requests
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

url = "https://www.lazada.vn"
try:
    r = requests.get(url, headers=headers, timeout=10)
    html = r.text
    images = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)
    print("Found images:")
    for img in images:
        if any(x in img.lower() for x in ["bct", "congthuong", "thongbao", "dangky", "gov.vn", "alicdn"]):
            print(img)
except Exception as e:
    print("Error:", e)
