import os
import json
import datetime
import sys
import re
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from flask_cors import CORS
from google import genai
from google.genai import types
import PyPDF2

import config

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
client = genai.Client(api_key=config.GEMINI_KEY)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "chat_history.json")
RESULT_FILE = os.path.join(BASE_DIR, "interviews.json")

# --- GLOBAL STORAGE ---
# Store structured candidate data here to pass to the UI
active_candidates = {} 
# Store active chat sessions (Gemini objects) - THIS WAS MISSING BEFORE
active_chats = {} 

print(f"\n📂 LOGGING TO:\n  -> {LOG_FILE}\n  -> {RESULT_FILE}\n")

# --- INITIALIZATION ---
def init_files():
    try:
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", encoding='utf-8') as f: json.dump([], f)
        if not os.path.exists(RESULT_FILE):
            with open(RESULT_FILE, "w", encoding='utf-8') as f: json.dump([], f)
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Cannot write to files.\nError: {e}")

init_files()

# --- HELPER: EXTRACT INFO USING GEMINI ---
def parse_resume_with_ai(text):
    """Sends resume text to Gemini to extract structured JSON data."""
    try:
        prompt = f"""
        Analyze the following resume text and extract the candidate's details.
        Return ONLY a raw JSON object (no markdown formatting).
        
        Keys required:
        - name (String, Title Case)
        - email (String)
        - skills (String, comma separated list of top 5 technical skills)
        - summary (String, a brief 2-sentence professional summary)
        - projects (String, a string where every project starts with the character "•" and is separated by a newline)

        RESUME TEXT:
        {text[:4000]}
        """
        
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp", 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        return json.loads(response.text)
    except Exception as e:
        print(f"AI Extraction Error: {e}")
        # Fallback data if AI fails
        return {
            "name": "Candidate", 
            "email": "Unknown", 
            "skills": "General", 
            "summary": "Could not parse resume.",
            "projects": "N/A"
        }

# --- LOGGING ---
def log_interaction(session_id, user_msg, ai_msg):
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding='utf-8') as f:
                try: logs = json.load(f)
                except: logs = []
        else: logs = []

        session = next((s for s in logs if s.get("sessionId") == session_id), None)
        if not session:
            session = { "sessionId": session_id, "timestamp": datetime.datetime.now().isoformat(), "conversation": [] }
            logs.append(session)
        
        session["conversation"].append({"role": "Candidate", "message": user_msg})
        session["conversation"].append({"role": "Divya", "message": ai_msg})

        with open(LOG_FILE, "w", encoding='utf-8') as f: json.dump(logs, f, indent=2) 
    except Exception as e:
        print(f"❌ LOGGING FAILED: {e}")

def save_result(candidate, score, feedback, cheated=False):
    try:
        results = json.load(open(RESULT_FILE)) if os.path.exists(RESULT_FILE) else []
        results.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "candidate": candidate,
            "score": 0 if cheated else score,
            "feedback": "DISQUALIFIED (Cheating)" if cheated else feedback,
            "cheated": cheated
        })
        with open(RESULT_FILE, "w", encoding='utf-8') as f: json.dump(results, f, indent=2)
        print("🏆 Interview Result Saved!")
    except Exception as e:
        print(f"❌ RESULT SAVE FAILED: {e}")

# --- UI TEMPLATE (Includes canary.png Logo Support) ---
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Canary Digital.ai | Interview</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        /* Dynamic Viewport Height for Mobile Browsers */
        .h-dvh { height: 100vh; height: 100dvh; }
        
        .chat-bubble { max-width: 85%; padding: 10px 14px; border-radius: 12px; margin-bottom: 8px; font-size: 14px; line-height: 1.4; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .user-bubble { background-color: #4F46E5; color: white; border-bottom-right-radius: 2px; align-self: flex-end; }
        .bot-bubble { background-color: white; border: 1px solid #E2E8F0; color: #1E293B; border-top-left-radius: 2px; align-self: flex-start; }
        .fade-in { animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .modal-fade { animation: fadeIn 0.4s ease-out; }
        .warning-flash { animation: flashRed 0.5s ease-in-out; }
        @keyframes flashRed { 0%, 100% { background-color: white; } 50% { background-color: #fee2e2; } }
        
        /* Hide scrollbar but keep functionality */
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    </style>
</head>
<body class="bg-gray-100 h-dvh flex items-center justify-center font-sans overflow-hidden" id="bodyBg">
    
    <div class="w-full max-w-7xl h-full md:h-[90vh] bg-white md:rounded-2xl shadow-xl flex flex-col md:flex-row overflow-hidden md:border border-gray-200 blur-sm transition-all duration-500" id="mainContainer">
        
        <div id="resumeSidebar" class="transition-all duration-700 bg-slate-50 border-gray-200 flex flex-col items-center justify-start relative overflow-hidden w-full md:w-0 h-0 md:h-full opacity-0">
            
            <div class="w-full bg-white md:bg-transparent p-4 md:p-6 border-b border-gray-200 flex flex-col items-center text-center">
                <div class="mb-3 w-full flex justify-center">
                    <img src="{{ url_for('static', filename='canary.png') }}" alt="Canary Digital Logo" class="h-10 md:h-12 object-contain hover:scale-105 transition-transform">
                </div>
                <div class="bg-indigo-100 px-3 py-1 rounded-full">
                    <p class="text-[10px] md:text-xs text-indigo-700 font-bold uppercase tracking-wider">Role: AI Engineer</p>
                </div>
            </div>

            <div class="p-4 md:p-6 w-full text-center flex flex-row md:flex-col items-center justify-between md:justify-center gap-4 flex-grow">
                
                <div class="w-12 h-12 md:w-20 md:h-20 rounded-full bg-white border-2 border-indigo-100 flex items-center justify-center text-indigo-400 text-xl md:text-3xl font-bold shadow-sm shrink-0">
                    <i class="fas fa-user"></i>
                </div>
                
                <div class="text-left md:text-center flex-grow">
                    <h2 id="sbName" class="text-lg md:text-xl font-bold text-gray-800 leading-tight">Candidate Name</h2>
                    <p id="sbEmail" class="text-xs text-gray-500 mt-0 md:mt-1 truncate max-w-[150px] md:max-w-none">email@example.com</p>
                    
                    <div class="hidden md:block mt-6">
                        <div class="mt-2 inline-flex items-center px-3 py-1 rounded-full bg-green-50 text-green-700 text-xs font-bold border border-green-100">
                            <span class="w-2 h-2 rounded-full bg-green-500 mr-2 animate-pulse"></span> Live Session
                        </div>
                    </div>
                </div>
                
                <div class="md:hidden">
                    <span class="flex h-3 w-3 relative">
                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                    </span>
                </div>
            </div>
            
            <div class="hidden md:block w-full p-4 text-center border-t border-gray-200">
                <p class="text-[10px] text-gray-400">Powered by Canary Digital.ai</p>
            </div>
        </div>

        <div class="flex-grow flex flex-col h-full bg-white relative w-full md:w-auto">
            
            <div class="px-4 py-3 md:p-6 border-b flex justify-between items-center bg-white sticky top-0 z-10 shadow-sm md:shadow-none" id="headerSection">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 md:w-10 md:h-10 rounded-lg bg-indigo-600 flex items-center justify-center text-white text-sm md:text-lg"><i class="fas fa-robot"></i></div>
                    <div>
                        <h1 class="text-sm md:text-lg font-bold text-gray-900 leading-tight">Divya (AI Recruiter)</h1>
                        <p class="text-[10px] text-gray-500 font-bold tracking-widest uppercase">Canary Digital.ai</p>
                    </div>
                </div>
                
                <div class="flex items-center gap-2" id="cheatIndicator" style="display:none;">
                    <span class="hidden md:inline text-xs font-bold text-red-500 uppercase tracking-wider">Warnings:</span>
                    <div class="flex gap-1">
                        <div id="w1" class="w-2 h-2 md:w-3 md:h-3 rounded-full bg-gray-200"></div>
                        <div id="w2" class="w-2 h-2 md:w-3 md:h-3 rounded-full bg-gray-200"></div>
                        <div id="w3" class="w-2 h-2 md:w-3 md:h-3 rounded-full bg-gray-200"></div>
                    </div>
                </div>
            </div>
            
            <div id="chatBox" class="flex-grow p-4 md:p-6 overflow-y-auto flex flex-col gap-3 bg-slate-50 no-scrollbar touch-pan-y"></div>

            <div class="p-4 md:p-6 border-t bg-white flex flex-col items-center pb-8 md:pb-6">
                <div id="statusText" class="text-[10px] md:text-xs font-bold text-gray-400 uppercase mb-3 tracking-widest">Ready</div>
                
                <button id="mainBtn" onclick="toggleInterview()" class="w-16 h-16 md:w-20 md:h-20 rounded-full bg-indigo-600 text-white shadow-lg hover:scale-105 active:scale-95 transition-all flex items-center justify-center">
                    <i id="mainIcon" class="fas fa-microphone text-2xl md:text-3xl"></i>
                </button>
                
                <p id="liveTranscript" class="h-5 text-gray-400 text-xs mt-3 italic overflow-hidden text-center max-w-xs md:max-w-lg">Tap mic to start...</p>
            </div>
        </div>
    </div>

    <div id="instructionModal" class="fixed inset-0 bg-black bg-opacity-70 z-50 flex items-center justify-center modal-fade p-4">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90dvh]">
            
            <div class="p-6 border-b bg-gray-50">
                <div class="flex justify-between items-center">
                    <div>
                        <h2 class="text-2xl font-bold text-gray-900">Welcome, Candidate</h2>
                        <p class="text-indigo-600 text-sm font-bold mt-1">Role: AI Engineer</p>
                    </div>
                    <div class="hidden md:block">
                         <img src="{{ url_for('static', filename='canary.png') }}" class="h-8 object-contain">
                    </div>
                </div>
            </div>
            
            <div class="p-6 overflow-y-auto flex-grow no-scrollbar">
                
                <div class="bg-indigo-50 border border-indigo-200 rounded-lg p-4 mb-6 flex items-start gap-3">
                    <div class="mt-1"><i class="fas fa-robot text-indigo-600 text-xl"></i></div>
                    <div>
                        <h3 class="font-bold text-indigo-900 text-sm">AI-Conducted Assessment</h3>
                        <p class="text-xs text-indigo-700 mt-1 leading-relaxed">
                            This interview is conducted entirely by <strong>Divya (AI)</strong> on behalf of <strong>Canary Digital.ai</strong>. 
                            Your responses will be analyzed in real-time and scored automatically.
                        </p>
                    </div>
                </div>

                <div id="uploadSection" class="mb-6">
                    <div id="dropZone" onclick="document.getElementById('resumeFile').click()" class="p-6 border-2 border-dashed border-indigo-300 rounded-xl bg-indigo-50 text-center hover:bg-indigo-100 transition-colors cursor-pointer relative group">
                        <input type="file" id="resumeFile" accept=".pdf" class="hidden" onchange="handleFileSelect(this)">
                        <div class="group-hover:scale-105 transition-transform pointer-events-none">
                            <i class="fas fa-cloud-upload-alt text-4xl text-indigo-500 mb-2"></i>
                            <p id="fileName" class="text-lg font-bold text-indigo-700">Click to Upload Resume</p>
                            <p class="text-xs text-indigo-400 mt-1">PDF Only • Max 5MB</p>
                        </div>
                        <p id="errorMsg" class="text-xs text-red-500 font-bold mt-2 hidden"></p>
                    </div>
                </div>

                <div id="parsedData" class="hidden mb-6 bg-green-50 border border-green-200 rounded-xl p-4">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center text-green-600"><i class="fas fa-check"></i></div>
                        <div>
                            <h3 class="font-bold text-gray-900">Profile Generated!</h3>
                            <p class="text-xs text-gray-500">Your resume details have been extracted.</p>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <h3 class="text-sm font-bold text-red-600 uppercase tracking-wider mb-4 border-b border-red-100 pb-2">
                            <i class="fas fa-shield-alt mr-1"></i> Proctoring Rules
                        </h3>
                        <ul class="space-y-4">
                            <li class="flex items-start gap-3">
                                <div class="mt-1"><i class="fas fa-expand text-red-500"></i></div>
                                <div>
                                    <strong class="text-gray-900 text-sm block">Fullscreen Mandatory</strong>
                                    <p class="text-xs text-gray-500 leading-relaxed mt-1">
                                        The interview requires fullscreen mode to ensure focus. Pressing 'Esc' or minimizing the window is recorded as a violation.
                                    </p>
                                </div>
                            </li>
                            <li class="flex items-start gap-3">
                                <div class="mt-1"><i class="fas fa-window-restore text-red-500"></i></div>
                                <div>
                                    <strong class="text-gray-900 text-sm block">No Tab Switching</strong>
                                    <p class="text-xs text-gray-500 leading-relaxed mt-1">
                                        Focus tracking is active. Switching tabs to search for answers or opening other applications will trigger an immediate alert.
                                    </p>
                                </div>
                            </li>
                            <li class="flex items-start gap-3">
                                <div class="mt-1"><i class="fas fa-ban text-red-500"></i></div>
                                <div>
                                    <strong class="text-gray-900 text-sm block">Automatic Disqualification</strong>
                                    <p class="text-xs text-gray-500 leading-relaxed mt-1">
                                        This system uses a strict "3-Strike" policy. If you trigger 3 warnings, the session terminates immediately with a score of 0.
                                    </p>
                                </div>
                            </li>
                        </ul>
                    </div>
                    
                    <div>
                        <h3 class="text-sm font-bold text-green-600 uppercase tracking-wider mb-4 border-b border-green-100 pb-2">
                            <i class="fas fa-chart-line mr-1"></i> Scoring Criteria
                        </h3>
                        <ul class="space-y-4">
                            <li class="flex items-start gap-3">
                                <div class="mt-1"><i class="fas fa-check-circle text-green-500"></i></div>
                                <div>
                                    <strong class="text-gray-900 text-sm block">Technical Accuracy</strong>
                                    <p class="text-xs text-gray-500 leading-relaxed mt-1">
                                        Your answers are cross-referenced with the resume skills and standard technical documentation.
                                    </p>
                                </div>
                            </li>
                            <li class="flex items-start gap-3">
                                <div class="mt-1"><i class="fas fa-microphone-alt text-green-500"></i></div>
                                <div>
                                    <strong class="text-gray-900 text-sm block">Clarity & Confidence</strong>
                                    <p class="text-xs text-gray-500 leading-relaxed mt-1">
                                        Speak clearly and at a moderate pace. The AI evaluates communication style and confidence levels.
                                    </p>
                                </div>
                            </li>
                            <li class="flex items-start gap-3">
                                <div class="mt-1"><i class="fas fa-clock text-green-500"></i></div>
                                <div>
                                    <strong class="text-gray-900 text-sm block">Conciseness</strong>
                                    <p class="text-xs text-gray-500 leading-relaxed mt-1">
                                        Keep answers direct. Avoid "fluff" or stalling strategies, as the AI is trained to detect them.
                                    </p>
                                </div>
                            </li>
                        </ul>
                    </div>
                </div>

            </div>

            <div class="p-6 border-t bg-gray-50">
                <button onclick="startUploadAndInterview()" id="startBtn" class="w-full py-4 bg-gray-400 text-white font-bold rounded-xl shadow-lg transition-all flex items-center justify-center gap-2 text-lg cursor-not-allowed" disabled>
                    Upload Resume to Unlock
                </button>
            </div>
        </div>
    </div>

    <script>
        let sessionId = Date.now().toString(), isSessionActive = false, isProcessing = false;
        let silenceTimer, silenceWarningCount = 0;
        const SILENCE_LIMIT = 10000;
        let tabSwitchCount = 0;
        let isDisqualified = false;
        
        const chatBox=document.getElementById('chatBox'), statusText=document.getElementById('statusText'), liveTranscript=document.getElementById('liveTranscript'), mainBtn=document.getElementById('mainBtn'), mainIcon=document.getElementById('mainIcon');
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition(); recognition.continuous = false; recognition.lang = 'en-IN'; recognition.interimResults = true;

        let availableVoices = [];
        window.speechSynthesis.onvoiceschanged = () => { availableVoices = window.speechSynthesis.getVoices(); };
        window.speechSynthesis.getVoices(); 

        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('resumeFile');

        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('border-indigo-600', 'bg-indigo-200'); });
        dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('border-indigo-600', 'bg-indigo-200'); });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-indigo-600', 'bg-indigo-200');
            if (e.dataTransfer.files.length > 0) { fileInput.files = e.dataTransfer.files; handleFileSelect(fileInput); }
        });

        function handleFileSelect(input) {
            const errorMsg = document.getElementById('errorMsg');
            errorMsg.classList.add('hidden'); 
            
            if(input.files && input.files[0]) {
                const file = input.files[0];
                if (file.type !== "application/pdf") {
                    errorMsg.innerText = "❌ Only PDF files are allowed.";
                    errorMsg.classList.remove('hidden');
                    input.value = ""; return;
                }
                document.getElementById('fileName').innerHTML = `<span class="text-green-600"><i class="fas fa-check-circle"></i> ${file.name}</span>`;
                const btn = document.getElementById('startBtn');
                btn.classList.remove('bg-gray-400', 'cursor-not-allowed');
                btn.classList.add('bg-indigo-600', 'hover:bg-indigo-700');
                btn.innerText = "Extract Info & Start";
                btn.disabled = false;
            }
        }

        async function startUploadAndInterview() {
            const fileInput = document.getElementById('resumeFile');
            const btn = document.getElementById('startBtn');
            const errorMsg = document.getElementById('errorMsg');
            
            if (!fileInput.files[0]) return;

            btn.innerText = "Analyzing Resume (AI)...";
            btn.disabled = true;

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('session_id', sessionId);

            try {
                const res = await fetch('/upload_resume', { method: 'POST', body: formData });
                const data = await res.json();
                
                if (data.status === "success") {
                    const c = data.candidate;
                    document.getElementById('sbName').innerText = c.name;
                    document.getElementById('sbEmail').innerText = c.email;
                    
                    document.getElementById('uploadSection').classList.add('hidden');
                    document.getElementById('parsedData').classList.remove('hidden');
                    
                    btn.innerText = "Enter Interview Room";
                    btn.onclick = () => startRealInterview();
                    btn.disabled = false;
                } else {
                    errorMsg.innerText = "❌ " + data.message;
                    errorMsg.classList.remove('hidden');
                    btn.innerText = "Try Again";
                    btn.disabled = false;
                }
            } catch (e) {
                console.error(e);
                alert("Server Error.");
            }
        }

        function startRealInterview() {
            const elem = document.documentElement;
            // Attempt Fullscreen (May require user gesture on mobile)
            if (elem.requestFullscreen) { elem.requestFullscreen().catch(() => {}); } 
            else if (elem.webkitRequestFullscreen) { elem.webkitRequestFullscreen(); }
            
            closeModal();
            
            // RESPONSIVE SIDEBAR ANIMATION
            const sb = document.getElementById('resumeSidebar');
            
            // Remove "hidden" state
            sb.classList.remove('w-0', 'md:w-0', 'h-0', 'opacity-0');
            
            // Add "active" state
            // Desktop: 25% width, Full Height, Right Border
            // Mobile: Full width, Auto Height, Bottom Border
            sb.classList.add('w-full', 'md:w-1/4', 'h-auto', 'md:h-full', 'opacity-100', 'border-b', 'md:border-b-0', 'md:border-r');
        }

        document.addEventListener("visibilitychange", () => {
            if (document.hidden && isSessionActive && !isDisqualified) handleTabSwitch();
        });

        function handleTabSwitch() {
            tabSwitchCount++;
            document.getElementById('mainContainer').classList.add('warning-flash');
            setTimeout(() => document.getElementById('mainContainer').classList.remove('warning-flash'), 500);
            
            document.getElementById('cheatIndicator').style.display = 'flex';
            if (tabSwitchCount >= 1) document.getElementById('w1').className = "w-2 h-2 md:w-3 md:h-3 rounded-full bg-red-500";
            if (tabSwitchCount >= 2) document.getElementById('w2').className = "w-2 h-2 md:w-3 md:h-3 rounded-full bg-red-500";
            if (tabSwitchCount >= 3) document.getElementById('w3').className = "w-2 h-2 md:w-3 md:h-3 rounded-full bg-red-500";

            if (tabSwitchCount < 3) {
                speak(`Warning ${tabSwitchCount}. Please focus.`, false);
                addMessage("SYSTEM", `<span class="text-red-500 font-bold">⚠️ PROCTORING WARNING (${tabSwitchCount}/3)</span>`);
            } else {
                isDisqualified = true;
                stopInterviewHard();
                speak("Disqualified.", true);
                addMessage("SYSTEM", `<span class="text-red-600 font-black text-lg">⛔ DISQUALIFIED.</span>`);
                fetch('/disqualify', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:sessionId}) });
            }
        }

        function stopInterviewHard() {
            isSessionActive = false;
            recognition.stop();
            stopSilenceTimer();
            mainIcon.className = "fas fa-ban";
            mainBtn.className = "w-16 h-16 md:w-20 md:h-20 rounded-full bg-red-600 text-white shadow-lg flex items-center justify-center cursor-not-allowed";
            statusText.innerText = "Terminated";
        }

        function closeModal() {
            chatBox.innerHTML = ''; 
            document.getElementById('instructionModal').style.display = 'none';
            document.getElementById('mainContainer').classList.remove('blur-sm');
            toggleInterview();
        }

        function resetToPopup() {
            if (isDisqualified) return;
            isSessionActive = false;
            stopSilenceTimer();
            recognition.stop();
            window.speechSynthesis.cancel();
            
            mainIcon.className = "fas fa-microphone";
            mainBtn.classList.remove("animate-pulse");
            statusText.innerText = "Ready";
            
            // Hide Sidebar logic reversed
            const sb = document.getElementById('resumeSidebar');
            sb.classList.add('w-0', 'md:w-0', 'h-0', 'opacity-0');
            sb.classList.remove('w-full', 'md:w-1/4', 'h-auto', 'md:h-full', 'opacity-100', 'border-b', 'md:border-b-0', 'md:border-r');

            document.getElementById('mainContainer').classList.add('blur-sm');
            document.getElementById('instructionModal').style.display = 'flex';
            tabSwitchCount = 0; 
            document.getElementById('cheatIndicator').style.display = 'none';
            
            document.getElementById('uploadSection').classList.remove('hidden');
            document.getElementById('parsedData').classList.add('hidden');
            document.getElementById('startBtn').onclick = startUploadAndInterview;
            document.getElementById('startBtn').innerText = "Upload Resume to Unlock";
            document.getElementById('fileName').innerText = "Click to Upload Resume";
            document.getElementById('startBtn').classList.add('bg-gray-400', 'cursor-not-allowed');
            document.getElementById('startBtn').classList.remove('bg-indigo-600', 'hover:bg-indigo-700');
        }

        function startSilenceTimer() {
            clearTimeout(silenceTimer);
            if (!isSessionActive || isDisqualified) return;
            silenceTimer = setTimeout(() => {
                if (isSessionActive && !isProcessing) {
                    silenceWarningCount++; 
                    if (silenceWarningCount === 1) speak("Take your time.", false);
                    else if (silenceWarningCount === 2) speak("If stuck, say 'Pass'.", false);
                    else handleUserMessage("Next Question");
                }
            }, SILENCE_LIMIT);
        }

        function stopSilenceTimer() { clearTimeout(silenceTimer); }
        function addMessage(role, text) { const div=document.createElement('div'); div.className=`chat-bubble fade-in ${role==='Candidate'?'user-bubble':'bot-bubble'}`; div.innerHTML=`<strong>${role}:</strong> ${text}`; chatBox.appendChild(div); chatBox.scrollTop=chatBox.scrollHeight; }
        
        function toggleInterview() {
            if(!isSessionActive && !isDisqualified) { 
                isSessionActive=true; mainIcon.className="fas fa-stop"; mainBtn.classList.add("animate-pulse"); statusText.innerText="Connecting..."; 
                silenceWarningCount = 0; 
                const name = document.getElementById('sbName').innerText;
                const g = name !== "Candidate Name" ? `Hello ${name}. I have reviewed your resume. Shall we begin?` : "Hello! What is your name?";
                addMessage('Divya',g); speak(g); 
            }
            else if (!isDisqualified) { resetToPopup(); }
        }
        
        recognition.onstart=()=>{ if(isSessionActive) statusText.innerText="Listening..."; };
        recognition.onend=()=>{ if(isSessionActive && !isProcessing && !isDisqualified) try{recognition.start();}catch(e){} };
        recognition.onresult=(e)=>{ const t=e.results[0][0].transcript; liveTranscript.innerText=t; stopSilenceTimer(); if(e.results[0].isFinal) handleUserMessage(t); };
        
        async function handleUserMessage(text) {
            stopSilenceTimer();
            silenceWarningCount = 0; 
            recognition.stop(); isProcessing=true; statusText.innerText="Thinking..."; addMessage('Candidate',text);
            try {
                const res = await fetch('/process_chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:sessionId, message:text}) });
                const data = await res.json(); addMessage('Divya', data.reply);
                if(data.finished) { 
                    statusText.innerText="Finished"; mainIcon.className="fas fa-check"; mainBtn.classList.remove("animate-pulse"); speak(data.reply, true); 
                } else { speak(data.reply, false); }
            } catch(e) { console.error(e); statusText.innerText="Error"; } finally { isProcessing=false; }
        }
        
        function speak(text, isFinal = false) {
            window.speechSynthesis.cancel(); 
            const u = new SpeechSynthesisUtterance(text);
            if (availableVoices.length === 0) availableVoices = window.speechSynthesis.getVoices();
            const femaleVoice = availableVoices.find(v => v.name.includes('Zira') || v.name.includes('Samantha') || v.name.includes('Female'));
            if (femaleVoice) u.voice = femaleVoice;
            u.onend = () => {
                if (isFinal) setTimeout(resetToPopup, 1000); 
                else if (isSessionActive && !isDisqualified) { try { recognition.start(); } catch(e) {} startSilenceTimer(); }
            };
            window.speechSynthesis.speak(u);
        }
    </script>
</body>
</html>
"""

# --- BACKEND LOGIC ---
submit_tool = types.Tool(function_declarations=[types.FunctionDeclaration(name="submit_interview", description="Submit score", parameters=types.Schema(type="OBJECT", properties={"candidate_name": types.Schema(type="STRING"), "score": types.Schema(type="NUMBER"), "feedback": types.Schema(type="STRING")}, required=["candidate_name", "score", "feedback"]))])

def get_chat_session(session_id):
    if session_id not in active_chats:
        # Default values
        cand_name = "Candidate"
        resume_text = "No resume provided."
        
        # Load Resume Data if available
        if session_id in active_candidates:
            c = active_candidates[session_id]
            cand_name = c.get('name', 'Candidate')
            resume_text = c.get('text', '')[:2000] # Limit text to avoid token limits

        # --- UPDATED STRICT INSTRUCTIONS (Fixes Double Greeting) ---
        sys_prompt = f"""
        SYSTEM: You are Divya, a professional Tech Recruiter at Canary Digital.ai.
        You are interviewing {cand_name} for the AI Engineer role.
        Resume: "{resume_text}..."

        *** STRICT INTERVIEW FLOW (FOLLOW EXACTLY) ***
        1. Ask ONLY ONE question at a time.
        2. Wait for the candidate's answer before moving on.
        3. If the answer is unclear, ask for clarification.
        4. NEVER deviate from the question flow below.

        INTERVIEW QUESTION FLOW:
        Step 1: The candidate has already been greeted. Do NOT say "Hello" again.
                IMMEDIATELY ask 1 specific question about a PROJECT listed in their resume.
        Step 2: (After they answer) Ask a TECHNICAL question about a core SKILL listed in their resume.
        Step 3: (After they answer) Ask a second, slightly harder TECHNICAL question relevant to the role.
        Step 4: (After they answer) Ask a third and final TECHNICAL question (scenario-based or problem-solving).
        Step 5: (After they answer) Do NOT ask any more questions. IMMEDIATELY call the function 'submit_interview' to save their score (0-10) and feedback.
        
        CRITERIA FOR SCORING:
        - Did they answer clearly?
        - Was the technical detail correct?
        - Assign a score from 1 to 10 based on these answers.
        """
        
        active_chats[session_id] = client.chats.create(
            model="gemini-2.0-flash-exp", 
            config=types.GenerateContentConfig(
                tools=[submit_tool], 
                system_instruction=sys_prompt
            ), 
            history=[types.Content(role="model", parts=[types.Part(text="Ready.")])]
        )
    return active_chats[session_id]

# --- ROUTES ---
@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/index.html')
def index_redirect(): return redirect('/')

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    try:
        if 'file' not in request.files: return jsonify({"status": "error", "message": "No file"})
        file = request.files['file']
        session_id = request.form.get("session_id")
        
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
            
        if len(text) < 50:
            return jsonify({"status": "error", "message": "File is empty or unreadable."})

        # EXTRACT INFO WITH AI
        parsed_data = parse_resume_with_ai(text)
        
        # Store structured data + full text
        active_candidates[session_id] = {
            "name": parsed_data.get("name", "Candidate"),
            "email": parsed_data.get("email", "N/A"),
            "skills": parsed_data.get("skills", "N/A"),
            "summary": parsed_data.get("summary", "N/A"),
            "projects": parsed_data.get("projects", "N/A"),
            "text": text
        }
        
        print(f"✅ Parsed Resume for: {active_candidates[session_id]['name']}")
        
        return jsonify({
            "status": "success", 
            "candidate": active_candidates[session_id]
        })
        
    except Exception as e:
        print(f"Upload Error: {e}")
        return jsonify({"status": "error", "message": "Could not process file."})

@app.route('/disqualify', methods=['POST'])
def disqualify_candidate():
    save_result("Candidate (Disqualified)", 0, "Terminated for cheating", cheated=True)
    return jsonify({"status": "disqualified"})

@app.route('/process_chat', methods=['POST'])
def process_chat():
    data = request.json
    chat = get_chat_session(data.get("session_id"))
    response = chat.send_message(data.get("message"))
    ai_text, is_finished = "", False
    
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.function_call:
                args = part.function_call.args
                score = args.get('score'); feedback = args.get('feedback'); candidate = args.get('candidate_name')
                save_result(candidate, score, feedback)
                ai_text = f"Interview Complete. Score: {score}/10. {feedback}"; is_finished = True
                if data.get("session_id") in active_chats: del active_chats[data.get("session_id")]
            elif part.text: ai_text += part.text
            
    log_interaction(data.get("session_id"), data.get("message"), ai_text.replace("**", "").strip())
    return jsonify({"reply": ai_text.replace("**", "").strip(), "finished": is_finished})

if __name__ == '__main__':
    app.run(debug=True, port=5001)