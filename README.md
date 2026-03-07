# Album Cover Generator — Setup Guide

## Folder Structure

```
album_cover_generator/
├── app.py
├── requirements.txt
├── README.md
└── assets/
    ├── epp_logo.jpg        ← Ekonomic Propaganda logo JPEG
    ├── rc_logo.jpg         ← redCola logo JPEG
    └── ssc_logo.png        ← Short Story Collective logo PNG
```

---

## Step 1 — Prepare the assets folder

Create a folder called `assets` inside `album_cover_generator`.

Copy your logo files into it, renamed exactly as shown:
- `epp_logo.jpg` — the Ekonomic Propaganda logo JPEG
- `rc_logo.jpg` — the redCola logo JPEG
- `ssc_logo.png` — the Short Story Collective PNG (use the transparent-bg version)

---

## Step 2 — Run locally on your Mac (for testing)

Open Terminal and run:

```bash
cd ~/album_cover_generator
pip3 install -r requirements.txt
streamlit run app.py
```

The app will open automatically in your browser at http://localhost:8501

---

## Step 3 — Deploy to Streamlit Cloud (for your team)

### 3a. Create accounts (free)
1. Go to https://github.com and create an account (or log in)
2. Go to https://share.streamlit.io and sign in with your GitHub account

### 3b. Upload to GitHub
1. On GitHub, click **New repository**
2. Name it `album-cover-generator`, set it to **Private**
3. Click **Create repository**
4. Upload all files: `app.py`, `requirements.txt`, and the entire `assets/` folder
   - Click **Add file → Upload files**
   - Drag everything in
   - Click **Commit changes**

### 3c. Deploy on Streamlit Cloud
1. Go to https://share.streamlit.io
2. Click **New app**
3. Select your GitHub repository: `album-cover-generator`
4. Main file path: `app.py`
5. Click **Deploy**

Streamlit will give you a URL like:
`https://your-name-album-cover-generator.streamlit.app`

Share this URL with your team in Budapest and Malta.

### 3d. Add a password (optional but recommended)
Add this to the top of `app.py` before any other code:

```python
import streamlit as st

PASSWORD = "your_password_here"   # change this

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        pwd = st.text_input("Enter password:", type="password")
        if st.button("Login"):
            if pwd == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
        st.stop()

check_password()
```

### 3e. Set your Anthropic API key in Streamlit Cloud
1. In Streamlit Cloud, go to your app → **Settings → Secrets**
2. Add:
```toml
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```
3. In `app.py`, the Anthropic client will automatically pick this up.

---

## How to use the app

1. **Select catalog** — click EPP, redCola, or SSC
2. The catalog logo appears confirming your selection
3. **Enter album title** and series name
4. **Write a short mood description** (helps AI choose the right typography)
5. **Upload the hero image** from MidJourney
6. Click **Generate Design Suggestions** — Claude analyses the image
7. Review the AI suggestions and reasoning
8. Optionally fine-tune fonts, colors, sizes using the adjustments panel
9. Click **Render Preview** — see the 1000×1000 preview
10. If happy, click **Download ZIP** — get 8 files (4 sizes × JPEG + PNG)

---

## Troubleshooting

**Fonts not rendering correctly:** The app uses system fonts available on the server.
On Mac you have many fonts. On Streamlit Cloud (Linux), fonts are limited.
To guarantee specific fonts, add `.ttf` font files to an `assets/fonts/` subfolder
and update the `get_system_font()` function to point to them.

**Logo background not removed correctly:** The app uses colour-keying to remove
black or white backgrounds. If your logo has a different background colour,
export a proper PNG with transparency from Pixelmator (checkered = transparent)
and place that in the assets folder.

**API errors:** Make sure your `ANTHROPIC_API_KEY` environment variable is set.
The app falls back to sensible defaults if the API is unavailable.
