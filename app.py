from web_du_lich import app, init_db

# Render fallback: supports gunicorn app:app
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
