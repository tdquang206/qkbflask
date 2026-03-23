cd /d D:\QuangPyApp\QKBFlask
call .venv\Scripts\activate
pythonw -m waitress --listen=0.0.0.0:5000 app:app