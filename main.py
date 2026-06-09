import asyncio
import re
import os
from aiohttp import web
from telethon import TelegramClient
import pycountry

# ================= কনফিগ =================
api_id = 33959126
api_hash = "e6045668a34aecdcd802eca0db3844fa"
GROUP_ID = -1002531902737

# ================= সেশন ফাইল সাপোর্ট =================
# Railway Environment Variable চেক করুন
STRING_SESSION = os.environ.get("STRING_SESSION")
TELETHON_SESSION = os.environ.get("TELETHON_SESSION")

if STRING_SESSION:
    # String Session থেকে লোড করুন
    from telethon.sessions import StringSession
    client = TelegramClient(StringSession(STRING_SESSION), api_id, api_hash)
    print("✅ Using String Session")
elif TELETHON_SESSION:
    # Base64 Session থেকে লোড করুন
    import base64
    import tempfile
    session_bytes = base64.b64decode(TELETHON_SESSION)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.session')
    temp_file.write(session_bytes)
    temp_file.close()
    session_name = temp_file.name.replace('.session', '')
    client = TelegramClient(session_name, api_id, api_hash)
    print("✅ Using Base64 Session")
else:
    # লোকাল সেশন ফাইল ব্যবহার করুন (আপনার আগের মতো)
    client = TelegramClient("user_session", api_id, api_hash)
    print("✅ Using local session file")

all_otps = []

# ================= ফাংশন (আগের মতোই, শুধু match_number_by_pattern ঠিক করা হয়েছে) =================

def get_country_flag_emoji(country_name):
    if not country_name or country_name == "Unknown":
        return "🏳️"
    try:
        country = pycountry.countries.get(name=country_name)
        if not country:
            country = pycountry.countries.get(common_name=country_name)
        if not country:
            return "🏳️"
        iso_code = country.alpha_2.upper()
        flag = ''.join(chr(ord(char) + 127397) for char in iso_code)
        return flag
    except Exception:
        return "🏳️"

def extract_number(text):
    if not text:
        return None
    match = re.search(r'Number:\s*(\d[\d\*]+)', text)
    if match:
        return match.group(1)
    match = re.search(r'(\d{3,4}\*{3}\d{3,4})', text)
    if match:
        return match.group(1)
    numbers = re.findall(r'\b(\d{8,15})\b', text)
    return numbers[0] if numbers else None

def extract_otp(text):
    if not text:
        return None
    match = re.search(r'OTP Code:\s*(\d{4,8})', text)
    if match:
        return match.group(1)
    match = re.search(r'(\d{4,8})\s+is your (Instagram|Facebook|TikTok) code', text, re.I)
    if match:
        return match.group(1)
    match = re.search(r'(\d{4,8})\s+est votre code (Instagram|Facebook|TikTok)', text, re.I)
    if match:
        return match.group(1)
    codes = re.findall(r'\b(\d{4,8})\b', text)
    for code in codes:
        if not re.match(r'^(19|20)\d{2}', code):
            return code
    return None

def detect_platform(text):
    if not text:
        return "Unknown"
    t = text.lower()
    if 'facebook' in t or 'est votre code facebook' in t:
        return "Facebook"
    if 'instagram' in t or '#ig' in t:
        return "Instagram"
    if 'whatsapp' in t:
        return "WhatsApp"
    if 'tiktok' in t:
        return "TikTok"
    return "Other"

def extract_country(text):
    match = re.search(r'Country:\s*[🇦-🇿]+\s*([\w\s]+)', text)
    if match:
        return match.group(1).strip()
    return "Unknown"

def get_first_last_digits(number):
    if not number:
        return None, None
    digits = re.sub(r'[^0-9]', '', number)
    if len(digits) < 6:
        return None, None
    return digits[:3], digits[-3:]

def match_number_by_pattern(sms_number, search_number):
    """
    এটাই শুধু ঠিক করা হলো - মাস্ক করা নম্বর এবং সার্চ নম্বর ম্যাচ করবে
    যেমন: sms_number = "9929***3727", search_number = "992970963727" হলে ম্যাচ করবে
    """
    if not sms_number or not search_number:
        return False
    
    # শুধু ডিজিট বের করা
    sms_digits = re.sub(r'[^0-9]', '', sms_number)
    search_digits = re.sub(r'[^0-9]', '', search_number)
    
    # সরাসরি ডিজিট ম্যাচ
    if sms_digits == search_digits:
        return True
    
    # মাস্ক করা নম্বরের জন্য (যেমন: 9929***3727)
    if '***' in sms_number:
        # প্যাটার্ন বানানো: 9929***3727 -> 9929\d{3}3727
        pattern = sms_number.replace('***', r'\d{3}')
        # পুরো স্ট্রিং ম্যাচ
        if re.match(f'^{pattern}$', search_number):
            return True
        
        # শুধু ডিজিট দিয়েও চেক
        pattern_digits = sms_number.replace('*', r'\d')
        if re.match(f'^{pattern_digits}$', search_number):
            return True
    
    # প্রথম 4 ও শেষ 4 ডিজিট চেক
    sms_first, sms_last = get_first_last_digits(sms_number)
    search_first, search_last = get_first_last_digits(search_number)
    
    if sms_first and search_first and sms_last and search_last:
        # প্রথম 3 এবং শেষ 3 ডিজিট ম্যাচ করলে true
        if sms_first == search_first and sms_last == search_last:
            return True
    
    return False

def extract_clean_message(text):
    if not text:
        return ""
    
    match = re.search(r'(#\s*\d{4,8}\s+is your (Instagram|Facebook|TikTok) code[^\n]*)', text, re.I)
    if match:
        return match.group(1).strip()
    
    match = re.search(r'(#\s*\d{4,8}\s+est votre code (Instagram|Facebook|TikTok)[^\n]*)', text, re.I)
    if match:
        return match.group(1).strip()
    
    match = re.search(r'(#\s*[^\n]+)', text)
    if match:
        return match.group(1).strip()
    
    return text[:150] + "..." if len(text) > 150 else text

# ================= মেসেজ সংগ্রহ =================

async def fetch_otps():
    global all_otps
    print("\n📡 গ্রুপ থেকে মেসেজ পড়ছি...")
    
    try:
        messages = []
        seen = set()
        
        async for msg in client.iter_messages(GROUP_ID, limit=300):
            text = msg.message or msg.raw_text or ""
            
            if not text or len(text) < 10:
                continue
            
            number = extract_number(text)
            if not number:
                continue
            
            otp = extract_otp(text)
            platform = detect_platform(text)
            country = extract_country(text)
            flag_emoji = get_country_flag_emoji(country)
            clean_msg = extract_clean_message(text)
            
            key = f"{number}_{otp}"
            if key in seen:
                continue
            
            seen.add(key)
            
            messages.append({
                "number": number,
                "otp": otp if otp else "Not Found",
                "platform": platform,
                "country": country,
                "flag": flag_emoji,
                "message": clean_msg
            })
            
            if len(messages) >= 200:
                break
        
        messages.reverse()
        all_otps = messages
        
        print(f"✅ {len(messages)} টি OTP পাওয়া গেছে!")
        
    except Exception as e:
        print(f"❌ এরর: {e}")

# ================= ওয়েব সার্ভার =================

async def index(request):
    html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes, viewport-fit=cover">
        <title>GetPaid OTP Finder</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
                color: #e2e8f0;
                min-height: 100vh;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                transition: all 0.3s ease;
                padding: 0;
                margin: 0;
            }

            body.light {
                background: linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 100%);
                color: #1e293b;
            }

            .container {
                max-width: 600px;
                margin: 0 auto;
                padding: 20px 16px;
            }

            /* Header */
            .header {
                text-align: center;
                margin-bottom: 20px;
                background: linear-gradient(135deg, #1e293b, #0f172a);
                padding: 20px 16px;
                border-radius: 28px;
                border: 1px solid #334155;
                transition: all 0.3s ease;
            }

            body.light .header {
                background: linear-gradient(135deg, #ffffff, #f8fafc);
                border: 1px solid #e2e8f0;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }

            .logo {
                width: 70px;
                height: 70px;
                margin: 0 auto 10px;
            }

            .logo img {
                width: 100%;
                height: 100%;
                border-radius: 50%;
                object-fit: cover;
                box-shadow: 0 8px 20px rgba(56,189,248,0.3);
            }

            h1 {
                font-size: 22px;
                background: linear-gradient(135deg, #38bdf8, #818cf8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                margin-bottom: 4px;
            }

            .full-title {
                font-size: 9px;
                opacity: 0.5;
                letter-spacing: 1px;
                margin-top: 4px;
            }

            /* Controls */
            .controls {
                display: flex;
                justify-content: flex-end;
                gap: 10px;
                margin-bottom: 16px;
            }

            .theme-btn, .info-btn {
                border: none;
                padding: 8px 18px;
                border-radius: 40px;
                cursor: pointer;
                background: #1e293b;
                color: white;
                font-weight: 500;
                transition: all 0.2s;
                font-size: 13px;
            }

            body.light .theme-btn, body.light .info-btn {
                background: #e2e8f0;
                color: #1e293b;
            }

            .theme-btn:hover, .info-btn:hover {
                background: #0ea5e9;
                color: white;
                transform: scale(0.96);
            }

            /* Modal */
            .modal {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.85);
                z-index: 1000;
                justify-content: center;
                align-items: center;
            }

            .modal-content {
                background: #1e293b;
                border-radius: 24px;
                padding: 25px;
                max-width: 300px;
                width: 85%;
                text-align: center;
                border: 1px solid #38bdf8;
            }

            body.light .modal-content {
                background: white;
            }

            .modal-content h3 {
                margin-bottom: 15px;
                color: #38bdf8;
                font-size: 18px;
            }

            .modal-content p {
                margin-bottom: 10px;
                font-size: 13px;
                line-height: 1.5;
            }

            .modal-content .close-modal {
                margin-top: 15px;
                padding: 8px 25px;
                background: #22c55e;
                border: none;
                border-radius: 40px;
                color: white;
                cursor: pointer;
                font-weight: bold;
            }

            /* Search Card */
            .search-card {
                background: #1e293b;
                border-radius: 24px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                transition: all 0.3s ease;
            }

            body.light .search-card {
                background: white;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }

            .search-box {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }

            .search-box input {
                width: 100%;
                padding: 16px 18px;
                border: none;
                border-radius: 60px;
                background: #0f172a;
                color: white;
                font-size: 16px;
                outline: none;
                transition: all 0.3s ease;
                text-align: center;
                letter-spacing: 1px;
            }

            body.light .search-box input {
                background: #f1f5f9;
                color: #1e293b;
                border: 1px solid #cbd5e1;
            }

            .search-box input:focus {
                outline: 2px solid #38bdf8;
                transform: scale(1.01);
            }

            .search-btn {
                width: 100%;
                padding: 16px 20px;
                border: none;
                border-radius: 60px;
                background: linear-gradient(135deg, #38bdf8, #818cf8);
                color: white;
                font-weight: bold;
                font-size: 18px;
                cursor: pointer;
                transition: 0.2s;
                box-shadow: 0 4px 15px rgba(56,189,248,0.3);
            }

            .search-btn:hover {
                transform: scale(0.98);
                background: linear-gradient(135deg, #0ea5e9, #6366f1);
            }

            .search-btn:active {
                transform: scale(0.96);
            }

            /* Loading */
            .loading {
                text-align: center;
                padding: 40px;
                display: none;
            }

            .spinner {
                width: 45px;
                height: 45px;
                border: 3px solid #334155;
                border-top: 3px solid #38bdf8;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 15px;
            }

            @keyframes spin {
                100% { transform: rotate(360deg); }
            }

            /* Result Card */
            .result-card {
                background: #1e293b;
                border-radius: 24px;
                padding: 20px;
                display: none;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                animation: fadeIn 0.3s ease;
                transition: all 0.3s ease;
            }

            body.light .result-card {
                background: white;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .info-item {
                margin-bottom: 14px;
                padding: 14px 16px;
                background: #0f172a;
                border-radius: 18px;
                transition: all 0.3s ease;
            }

            body.light .info-item {
                background: #f8fafc;
            }

            .number-value {
                font-size: 18px;
                font-weight: 700;
                word-break: break-all;
                color: #38bdf8;
                text-align: center;
                letter-spacing: 0.5px;
            }

            .platform-row {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 12px;
            }

            .platform-icon {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                overflow: hidden;
                background: white;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .platform-icon img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }

            .platform-name {
                font-size: 18px;
                font-weight: 700;
            }

            .country-row {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
            }
            
            .country-flag {
                font-size: 28px;
            }
            
            .country-name {
                font-size: 17px;
                font-weight: 600;
            }

            .otp-box {
                background: linear-gradient(135deg, #1a2a3a, #0f172a);
                border-radius: 20px;
                padding: 22px;
                text-align: center;
                cursor: pointer;
                transition: all 0.2s ease;
                border: 2px solid #334155;
                margin-bottom: 14px;
            }

            body.light .otp-box {
                background: linear-gradient(135deg, #e8f0fe, #ffffff);
                border: 2px solid #cbd5e1;
            }

            .otp-box:hover {
                transform: scale(0.98);
                background: linear-gradient(135deg, #22c55e, #16a34a);
                border-color: #22c55e;
            }

            .otp-box:active {
                transform: scale(0.96);
            }

            .otp-box.copied {
                background: linear-gradient(135deg, #22c55e, #16a34a);
                animation: pulse 0.3s ease;
            }

            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(0.96); }
                100% { transform: scale(1); }
            }

            .otp-value {
                font-size: 42px;
                font-weight: 800;
                letter-spacing: 5px;
                color: #38bdf8;
                font-family: 'Courier New', monospace;
            }

            .otp-box:hover .otp-value {
                color: white;
            }

            .message-value {
                font-size: 12px;
                font-weight: 500;
                word-break: break-all;
                color: #38bdf8;
                line-height: 1.5;
                font-family: monospace;
                text-align: center;
            }

            body.light .message-value {
                color: #0ea5e9;
            }

            .not-found {
                text-align: center;
                padding: 35px;
                background: #7f1a1a60;
                border-radius: 24px;
                color: #f87171;
                display: none;
                font-size: 16px;
                font-weight: 500;
            }

            body.light .not-found {
                background: #fee2e2;
            }

            /* Telegram Button */
            .telegram-btn {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 12px;
                margin-top: 20px;
                padding: 14px 20px;
                background: linear-gradient(135deg, #1e3a8a, #2563eb);
                border-radius: 60px;
                text-decoration: none;
                color: white;
                font-weight: 700;
                transition: 0.2s;
                font-size: 15px;
            }

            .telegram-btn:hover {
                transform: scale(0.98);
                background: linear-gradient(135deg, #2563eb, #1e40af);
            }

            .telegram-icon {
                width: 28px;
                height: 28px;
            }

            .telegram-icon svg {
                width: 100%;
                height: 100%;
                fill: white;
            }

            .toast {
                position: fixed;
                bottom: 30px;
                left: 50%;
                transform: translateX(-50%);
                background: #22c55e;
                color: white;
                padding: 12px 24px;
                border-radius: 50px;
                font-size: 14px;
                display: none;
                z-index: 9999;
                font-weight: bold;
                white-space: nowrap;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }

            .toast.error {
                background: #ef4444;
            }

            @media (max-width: 550px) {
                .container { padding: 16px 12px; }
                .otp-value { font-size: 32px; letter-spacing: 4px; }
                .search-btn { font-size: 16px; padding: 14px 20px; }
                .search-box input { font-size: 15px; padding: 14px 16px; }
                .info-item { padding: 12px 14px; }
                .number-value { font-size: 16px; }
                .platform-name { font-size: 16px; }
                .message-value { font-size: 11px; }
            }

            @media (max-width: 380px) {
                .otp-value { font-size: 26px; letter-spacing: 3px; }
                .container { padding: 12px 10px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">
                    <img src="https://i.ibb.co/RpzTyt1v/bot.jpg" alt="bot" border="0">
                </div>
                <h1>GetPaid OTP Finder</h1>
                <div class="full-title">🔐 Full Connected GetPaid OTP 2.0</div>
            </div>

            <div class="controls">
                <button class="theme-btn" onclick="toggleTheme()">🌓 Light/Dark</button>
                <button class="info-btn" onclick="openModal()">ℹ️ Info</button>
            </div>

            <!-- Modal -->
            <div id="infoModal" class="modal">
                <div class="modal-content">
                    <h3>ℹ️ Information</h3>
                    <p>📌 Click on OTP box to copy code instantly</p>
                    <p>🔒 100% Safe & Secured Server</p>
                    <p>📱 Enter number → Click Search</p>
                    <button class="close-modal" onclick="closeModal()">Got it</button>
                </div>
            </div>

            <div class="search-card">
                <div class="search-box">
                    <input type="text" id="numberInput" placeholder="📞 Enter phone number" autocomplete="off">
                    <button class="search-btn" onclick="searchOTP()">🔍 SEARCH OTP</button>
                </div>
            </div>

            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Searching OTP...</p>
            </div>

            <div class="not-found" id="notFound">
                ❌ OTP not found for this number
            </div>

            <div class="result-card" id="resultCard">
                <div class="info-item">
                    <div class="number-value" id="resultNumber">—</div>
                </div>

                <div class="info-item">
                    <div class="platform-row" id="resultPlatform">
                        <div class="platform-icon" id="platformIcon"></div>
                        <div class="platform-name" id="platformName">—</div>
                    </div>
                </div>

                <div class="info-item">
                    <div class="country-row" id="resultCountry">
                        <span class="country-flag" id="countryFlag">🏳️</span>
                        <span class="country-name" id="countryName">—</span>
                    </div>
                </div>

                <div class="otp-box" onclick="copyOTPFromBox()" id="otpBox">
                    <div class="otp-value" id="resultOTP">—</div>
                </div>

                <div class="info-item">
                    <div class="message-value" id="resultMessage">—</div>
                </div>
            </div>

            <!-- Telegram Button -->
            <a class="telegram-btn" href="https://t.me/otpincomereal2_bot" target="_blank">
                <div class="telegram-icon">
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.51-.99-.66-.35-1.02.22-1.61.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.03-2.01 1.28-2.83 1.8-.27.18-.51.27-.73.27-.24 0-.63-.12-.92-.23-.44-.16-.83-.25-.8-.53.02-.15.11-.3.28-.45.59-.51 2.6-1.68 4.38-2.78 1.58-.98 2.14-1.15 2.46-1.15.12 0 .28.03.41.12.12.09.19.21.21.35.02.08.02.17-.01.28z"/>
                    </svg>
                </div>
                <span>Join Telegram Bot</span>
            </a>
        </div>

        <div id="toast" class="toast">✅ Copied!</div>

        <script>
            let currentOTP = '';

            function toggleTheme() {
                document.body.classList.toggle('light');
            }

            function openModal() {
                document.getElementById('infoModal').style.display = 'flex';
            }

            function closeModal() {
                document.getElementById('infoModal').style.display = 'none';
            }

            function showToast(msg, isError = false) {
                let toast = document.getElementById('toast');
                toast.textContent = msg || (isError ? '❌ Failed to copy' : '✅ Copied!');
                toast.className = 'toast' + (isError ? ' error' : '');
                toast.style.display = 'block';
                setTimeout(() => {
                    toast.style.display = 'none';
                    toast.className = 'toast';
                }, 1500);
            }

            function getPlatformIcon(platform) {
                const icons = {
                    'Facebook': 'https://i.ibb.co/Rk4wk8d5/facebook.jpg',
                    'Instagram': 'https://i.ibb.co/bgcdmD3P/instagram.jpg',
                    'WhatsApp': 'https://i.ibb.co/QvvDqSRs/whatsapp.jpg',
                    'TikTok': 'https://i.ibb.co/ymBVDLyF/png-transparent-tiktok-tiktok-logo-tiktok-icon-thumbnail.png'
                };
                let url = icons[platform];
                if (url) {
                    return `<img src="${url}" alt="${platform}" onerror="this.src='https://placehold.co/40x40/1e293b/white?text=${platform[0]}'">`;
                }
                return `<div style="width:40px;height:40px;background:#334155;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;">?</div>`;
            }

            async function searchOTP() {
                let number = document.getElementById('numberInput').value.trim();
                
                if (!number) {
                    showToast('⚠️ Please enter a number', true);
                    return;
                }

                document.getElementById('loading').style.display = 'block';
                document.getElementById('resultCard').style.display = 'none';
                document.getElementById('notFound').style.display = 'none';

                try {
                    let response = await fetch(`/search?number=${encodeURIComponent(number)}`);
                    let data = await response.json();

                    document.getElementById('loading').style.display = 'none';

                    if (data.found) {
                        currentOTP = data.data.otp;
                        document.getElementById('resultNumber').innerText = data.data.number;
                        document.getElementById('platformName').innerHTML = data.data.platform;
                        document.getElementById('platformIcon').innerHTML = getPlatformIcon(data.data.platform);
                        document.getElementById('countryFlag').innerHTML = data.data.flag || '🏳️';
                        document.getElementById('countryName').innerHTML = data.data.country || 'Unknown';
                        document.getElementById('resultOTP').innerHTML = data.data.otp;
                        document.getElementById('resultMessage').innerHTML = data.data.message || '-';
                        document.getElementById('resultCard').style.display = 'block';
                        document.getElementById('otpBox').classList.remove('copied');
                    } else {
                        document.getElementById('notFound').style.display = 'block';
                        setTimeout(() => {
                            document.getElementById('notFound').style.display = 'none';
                        }, 3000);
                    }
                } catch (error) {
                    document.getElementById('loading').style.display = 'none';
                    showToast('❌ Server error', true);
                }
            }

            function copyOTPFromBox() {
                if (currentOTP && currentOTP !== 'Not Found' && currentOTP !== '—') {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        navigator.clipboard.writeText(currentOTP).then(() => {
                            let otpBox = document.getElementById('otpBox');
                            otpBox.classList.add('copied');
                            showToast(`✅ ${currentOTP} copied!`);
                            setTimeout(() => {
                                otpBox.classList.remove('copied');
                            }, 500);
                        }).catch(err => {
                            fallbackCopy(currentOTP);
                        });
                    } else {
                        fallbackCopy(currentOTP);
                    }
                } else {
                    showToast('❌ No OTP to copy', true);
                }
            }
            
            function fallbackCopy(text) {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                try {
                    document.execCommand('copy');
                    let otpBox = document.getElementById('otpBox');
                    otpBox.classList.add('copied');
                    showToast(`✅ ${text} copied!`);
                    setTimeout(() => {
                        otpBox.classList.remove('copied');
                    }, 500);
                } catch (err) {
                    showToast('❌ Failed to copy', true);
                }
                document.body.removeChild(textarea);
            }

            document.getElementById('numberInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') searchOTP();
            });

            window.onclick = function(event) {
                let modal = document.getElementById('infoModal');
                if (event.target == modal) {
                    modal.style.display = 'none';
                }
            }
        </script>
    </body>
    </html>
    '''
    return web.Response(text=html, content_type='text/html')

async def search_api(request):
    number = request.query.get('number', '').strip()
    if not number:
        return web.json_response({'found': False})
    
    print(f"\n🔍 Searching: {number}")
    
    for item in all_otps:
        if match_number_by_pattern(item['number'], number):
            print(f"   ✅ Found: {item['number']} → {item['otp']}")
            return web.json_response({'found': True, 'data': item})
    
    print(f"   ❌ Not found: {number}")
    return web.json_response({'found': False})

async def background_updater():
    while True:
        await fetch_otps()
        await asyncio.sleep(5)

async def main():
    print("=" * 50)
    print("🔰 GetPaid OTP Finder v2.0")
    print("=" * 50)
    
    try:
        await client.start()
        
        me = await client.get_me()
        print(f"✅ Logged in: {me.first_name}")
        
        await fetch_otps()
        
        app = web.Application()
        app.router.add_get('/', index)
        app.router.add_get('/search', search_api)
        
        # Railway এর জন্য PORT ব্যবহার করুন
        port = int(os.environ.get("PORT", 20300))
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        print("=" * 50)
        print(f"✅ Server running at: http://0.0.0.0:{port}")
        print("=" * 50)
        
        asyncio.create_task(background_updater())
        
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
