# 🤖 AI Technical Interviewer - Canary Digitals.AI


## 📋 Overview

The **AI Technical Interviewer** is a sophisticated web application designed to automate the initial screening process for software engineering candidates. Built for **Canary Digitals.AI**, this tool utilizes **Google's Gemini 2.0 Flash model** to conduct real-time, context-aware voice interviews.

The system analyzes a candidate's uploaded resume (PDF), generates dynamic technical questions based on their specific skills and projects, and enforces strict proctoring rules to ensure assessment integrity.

## ✨ Key Features

* **📄 Intelligent Resume Parsing:** Automatically extracts candidate details, skills, and project history from PDF resumes using Generative AI.
* **🗣️ Voice-First Interaction:** Features seamless Speech-to-Text (STT) and Text-to-Speech (TTS) for a natural, conversational interview experience.
* **🧠 Dynamic Questioning Engine:** "Divya" (the AI Recruiter) adapts questions in real-time based on the candidate's responses and resume content.
* **⚡ Quick Reply Suggestions:** Candidates can use smart suggestion chips (e.g., "Yes, I'm ready", "Next Question") for faster interaction.
* **🛡️ Automated Proctoring:**
    * **Fullscreen Enforcement:** Detects if the candidate exits fullscreen mode.
    * **Focus Tracking:** Monitors tab switching and window blurring.
    * **Auto-Disqualification:** Implements a "3-Strike" rule for violations.
* **📱 Fully Responsive UI:** Optimized interface that works seamlessly on both desktop and mobile devices.

## 🛠️ Tech Stack

* **Backend:** Python 3.x, Flask
* **AI Core:** Google Gemini 2.0 Flash (via `google-genai` SDK)
* **Frontend:** HTML5, JavaScript (Web Speech API), Tailwind CSS
* **Data Processing:** PyPDF2
* **Styling:** FontAwesome, Custom CSS Animations

## 🚀 Installation & Setup

Follow these steps to run the project locally.

### 1. Clone the Repository
```bash
git clone [https://github.com/yourusername/ai-interviewer.git](https://github.com/yourusername/ai-interviewer.git)
cd ai-interviewer
```

### 2. Create a Virtual Environment
It is recommended to use a virtual environment to manage dependencies.

Windows:
```
python -m venv venv
venv\Scripts\activate
```
Mac/Linux:
```
python3 -m venv venv
source venv/bin/activate
```
### 3. Install Dependencies
```
pip install -r requirements.txt
```
### 4. Configure API Key
1. Get your API key from Google AI Studio.
2. Create a file named config.py in the root directory.
3. Add your key to the file:

Python
```
# config.py
GEMINI_KEY = "YOUR_ACTUAL_API_KEY_HERE"
```
(Note: config.py is ignored by Git for security)

### 5. Run the Application
```Bash

python app.py
```
Open your web browser and navigate to: http://127.0.0.1:5001

### 🛡️ Usage Guide
**Landing Page**: Open the app. The sidebar displays the Canary Digitals.AI branding.

**Resume Upload**: Click the upload area to select a PDF resume.

**Resume Analysis**: The system extracts your name, skills, and projects instantly.

**The Interview**:

- Click "Enter Interview Room".
  
- Accept permissions for Microphone usage.
  
- Enter Fullscreen Mode when prompted (Mandatory).
  
- Divya (the AI) will start the interview. Answer verbally or use the Quick Reply buttons.
  
**Completion**:
After 4–5 technical questions, the AI generates:

- A score (1–10)
- Technical feedback

  These are stored in the backend.

## 🤝 Contributing
Contributions are welcome! Please fork the repository and create a pull request for any feature enhancements or bug fixes.

## 📄 License
This project is created for educational and portfolio purposes.
