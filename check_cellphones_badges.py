import requests

candidates = [
    "https://cdn2.cellphones.com.vn/80x,webp/media/logo/logoSaleNoti.png",
    "https://cdn2.cellphones.com.vn/80x,webp/media/logo/logoRegister.png",
    "https://cdn2.cellphones.com.vn/80x,webp/media/logo/logoRegisterNoti.png",
    "https://cdn2.cellphones.com.vn/80x,webp/media/logo/logoSaleNoti2.png"
]

for url in candidates:
    try:
        r = requests.get(url, timeout=5)
        print(f"{url}: Status {r.status_code}")
    except Exception as e:
        print(f"{url}: Error {e}")
