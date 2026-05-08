# J.A.R.V.I.S — AI Desktop Assistant

<div align="center">

<img src="jarvis1.jpg" alt="JARVIS Banner" width="700"/>

### Your Personal AI-Powered Desktop Assistant

Voice-controlled automation, face recognition, OCR, WhatsApp messaging, media control, system management, and AI conversation — all in one assistant.

</div>

---

# Features

* 🎙️ Voice Assistant with speech recognition
* 🧠 AI-powered conversation system
* 👤 Face Recognition Authentication
* 📷 OCR (Optical Character Recognition)
* 🌐 Browser Automation
* 📩 Email Sending
* 💬 WhatsApp Automation
* 🎵 Media Controls
* 🖥️ System Controls
* 📰 Latest News Fetching
* 📍 Location Detection
* 😂 Joke Generator
* ☁️ Weather Information
* 📺 YouTube Downloader
* 🧠 Memory Management System

---

# Project Structure

```bash id="7x2qv7"
├── ai/
├── core/
├── modules/
├── security/
├── memory/
├── Face Recognition/
├── images/
├── samples/
├── registered_faces/
├── jarvis.py
├── OCR.py
├── requirements.txt
└── README.md
```

---

# Technologies Used

* Python 3.8+
* OpenCV
* SpeechRecognition
* pyttsx3
* Groq API
* OCR
* Face Recognition
* Automation Modules

---

# Requirements

## Python Modules

```txt id="17j7hq"
datetime
os
pyttsx3
wikipedia
speech_recognition
webbrowser
sys
smtplib
requests
json
difflib
geocoder
pyjokes
psutil
pyautogui
opencv-python
```

---

# Installation

## 1. Clone the Repository

```bash id="t3h4hm"
git clone https://github.com/Manikanta1216/ai-daemon.git
cd ai-daemon
```

---

## 2. Create Virtual Environment

### Windows

```bash id="d1mq5q"
python -m venv venv
venv\Scripts\activate
```

### Linux / macOS

```bash id="9hwtb0"
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash id="6t3m65"
pip install -r requirements.txt
```

---

# PyAudio Installation (Windows)

PyAudio sometimes fails to install directly on Windows.

### Option 1 — Recommended

Download the compatible `.whl` file from:

[PyAudio Windows Wheels](https://www.lfd.uci.edu/~gohlke/pythonlibs/?utm_source=chatgpt.com#pyaudio)

Then install it:

```bash id="agj2d7"
pip install PyAudio-0.2.11-cp38-cp38-win_amd64.whl
```

After that:

```bash id="2wt8vn"
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file in the root directory.

Example:

```env id="3w0f38"
GROQ_API_KEY=your_groq_api_key
EMAIL=your_email
EMAIL_PASSWORD=your_password
```

---

# Running J.A.R.V.I.S

```bash id="yvq2o7"
python jarvis.py
```

---

# Face Recognition Setup

## Generate Face Samples

```bash id="lnq0hl"
python "Face Recognition/Sample generator.py"
```

## Train the Model

```bash id="q6l7to"
python "Face Recognition/Model Trainer.py"
```

---

# OCR Usage

Run OCR module:

```bash id="4j4o8u"
python OCR.py
```

---

# Modules Included

| Module                   | Description        |
| ------------------------ | ------------------ |
| `automation_module.py`   | Desktop automation |
| `browser.py`             | Browser controls   |
| `email_module.py`        | Send emails        |
| `whatsapp_module.py`     | WhatsApp messaging |
| `media_module.py`        | Media controls     |
| `system_module.py`       | System operations  |
| `face_monitor_module.py` | Face monitoring    |

---

# Screenshots

## Interface

<img src="images/jarvis.jpg" width="700"/>

## Face Recognition

<img src="images/face-600x900.png" width="500"/>

---

# Security Notes

* Never upload real API keys
* Keep `.env` in `.gitignore`
* Do not commit virtual environments
* Remove personal images/data before publishing

Recommended `.gitignore`:

```gitignore id="x2v8k0"
venv/
venv_new/
.env
__pycache__/
*.pyc
```

---

# Future Improvements

* GUI Dashboard
* Multi-language support
* Better AI memory
* Mobile integration
* Smart home controls
* Plugin architecture

---

# Contributing

Contributions are welcome.

1. Fork the repository
2. Create a new branch
3. Commit changes
4. Open a Pull Request

---

# License

This project is licensed under the MIT License.

---

# Author

## 👨‍💻 ZENTIH 

* AI Enthusiast
* Python Developer
* Automation Engineer

GitHub:

[Manikanta1216 GitHub](https://github.com/Manikanta1216?utm_source=chatgpt.com)

---

# Support

If you like this project:

⭐ Star the repository
🍴 Fork the project
🐛 Report issues
🚀 Contribute improvements
