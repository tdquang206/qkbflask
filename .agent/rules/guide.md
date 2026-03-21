---
trigger: always_on
---

- remember to use virtual env .venv/scripts/activate.ps1
- ask what is the goal I want, do not guess
- use newest version, download js library for offline use, do not use cdn
- flask, bulma css
- no hard-code white background for text field
- optimize for desktop, offline use
- do not use icon
- do not add long <script> or <style> to html file
- add encoding='utf-8' or similar param when possible
- make sure to comment on non-trivial code
- make sure to not break existing api
- add function to new files, do not add directly to app.py
- for debug files, put them inside debug folder, and use load_dotenv()