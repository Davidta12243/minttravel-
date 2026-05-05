from web_du_lich import app, init_db

# Ensure schema exists when app is started by Gunicorn.
init_db()
