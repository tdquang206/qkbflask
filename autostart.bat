cd /d D:\QuangPyApp\QKBFlask
call .venv\Scripts\activate
waitress-serve --listen=0.0.0.0:5000 app:app