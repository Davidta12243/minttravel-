import requests

# Let's search GitHub for common repositories that have logo-bct or dathongbao or dadangky in their path
# We can check a few public repos we know or search
candidates = [
    "https://raw.githubusercontent.com/hieunguyen31/react-ecommerce/master/public/img/logo-sale.png",
    "https://raw.githubusercontent.com/phuongnam1995/ShopMulti/master/ShopMulti/Content/images/da-thong-bao-bo-cong-thuong.png",
    "https://raw.githubusercontent.com/nguyenthanhnam1/OnlineShop/master/OnlineShop/assets/client/images/da-thong-bao-bo-cong-thuong.png",
    "https://raw.githubusercontent.com/tanphat1/laravel-ecommerce/master/public/images/da-thong-bao-bo-cong-thuong.png",
    "https://raw.githubusercontent.com/duyphuong/ecommerce/master/public/img/dathongbao.png"
]

for url in candidates:
    try:
        r = requests.get(url, timeout=5)
        print(f"{url}: Status {r.status_code}")
    except Exception as e:
        print(f"{url}: Error {e}")
