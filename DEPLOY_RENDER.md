# Deploy Flask len Render + Gan Ten Mien

## 1) Day code len GitHub
1. Tao repository moi tren GitHub.
2. Push code len nhanh `main`.

## 2) Tao Web Service tren Render
1. Vao Render -> New -> Web Service.
2. Chon repo vua push.
3. Render se doc san `render.yaml`.
4. Build command: `pip install -r requirements.txt`.
5. Start command: `gunicorn wsgi:app`.

## 3) Set bien moi truong tren Render
Can thiet:
- `FLASK_SECRET_KEY` (auto generate neu dung `render.yaml`).

Neu dung OAuth:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `FACEBOOK_CLIENT_ID`
- `FACEBOOK_CLIENT_SECRET`

## 4) OAuth callback URL
Sau khi app co URL Render (vi du `https://mint-travel-app.onrender.com`), set callback:
- Google: `https://mint-travel-app.onrender.com/auth/google/callback`
- Facebook: `https://mint-travel-app.onrender.com/auth/facebook/callback`

## 5) Gan ten mien
1. Mua domain (Cloudflare/Namecheap/...)
2. Trong Render -> Settings -> Custom Domains -> Add domain.
3. Render cung cap ban ghi DNS, them dung o nha cung cap domain:
   - Thuong la CNAME cho `www`
   - Va A/ALIAS cho domain goc `@`
4. Cho DNS cap nhat (thuong vai phut den vai gio).
5. SSL se duoc Render cap tu dong sau khi DNS dung.

## 6) Luu y ve SQLite
Ban dang dung `dulich.db` (SQLite), phu hop MVP/demo.
Tren hosting cloud, filesystem co the ephemereal (khong ben vung qua redeploy/restart).
De chay that, nen chuyen sang Postgres. Neu ban muon, co the lam buoc migrate sau.

## 7) Chay local nhu production (test)
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m gunicorn wsgi:app
```

Neu gunicorn khong ho tro tren may local cua ban, van co the test bang:
```powershell
.\.venv\Scripts\python.exe web_du_lich.py
```
