import asyncio
import re
import os
import base64
import tempfile
from aiohttp import web
from telethon import TelegramClient
import pycountry

# ================= কনফিগ =================
api_id = 33959126
api_hash = "e6045668a34aecdcd802eca0db3844fa"
GROUP_ID = -1002531902737

# ================= সেশন হ্যান্ডলিং =================
def get_session_client():
    """সেশন ফাইল বা Environment Variable থেকে ক্লায়েন্ট তৈরি করে"""
    
    # 1. Environment Variable থেকে সেশন লোড করুন (Railway এর জন্য)
    session_base64 = os.environ.get("TELETHON_SESSION")
    
    if session_base64:
        print("📦 Loading session from environment variable...")
        try:
            session_bytes = base64.b64decode(session_base64)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.session')
            temp_file.write(session_bytes)
            temp_file.close()
            session_name = temp_file.name.replace('.session', '')
            print("✅ Session loaded from base64")
            return TelegramClient(session_name, api_id, api_hash)
        except Exception as e:
            print(f"⚠️ Failed to load from base64: {e}")
    
    # 2. সরাসরি সেশন ফাইল ব্যবহার করুন
    if os.path.exists("user_session.session"):
        print("📁 Loading session from file...")
        return TelegramClient("user_session", api_id, api_hash)
    
    # 3. Railway String Session (বিকল্প)
    string_session = os.environ.get("STRING_SESSION")
    if string_session:
        print("📦 Loading from string session...")
        from telethon.sessions import StringSession
        return TelegramClient(StringSession(string_session), api_id, api_hash)
    
    print("❌ No session found! Please set TELETHON_SESSION environment variable.")
    raise Exception("No valid session available")

# ক্লায়েন্ট তৈরি করুন
client = get_session_client()
all_otps = []

# ================= ফাংশন =================

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
    match = re.search(r'(\d{4,8})\s+is your (Instagram|Facebook) code', text, re.I)
    if match:
        return match.group(1)
    match = re.search(r'(\d{4,8})\s+est votre code (Instagram|Facebook)', text, re.I)
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
    if not sms_number or not search_number:
        return False
    
    sms_first, sms_last = get_first_last_digits(sms_number)
    search_first, search_last = get_first_last_digits(search_number)
    
    if sms_first is None or search_first is None:
        return False
    
    if sms_first == search_first and sms_last == search_last:
        return True
    
    if re.sub(r'[^0-9]', '', sms_number) == re.sub(r'[^0-9]', '', search_number):
        return True
    
    return False

def extract_clean_message(text):
    if not text:
        return ""
    
    match = re.search(r'(#\s*\d{4,8}\s+is your (Instagram|Facebook) code[^\n]*)', text, re.I)
    if match:
        return match.group(1).strip()
    
    match = re.search(r'(#\s*\d{4,8}\s+est votre code (Instagram|Facebook)[^\n]*)', text, re.I)
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
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>GetPaid OTP Finder</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: #e2e8f0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
            padding: 20px;
        }
        body.light {
            background: linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 100%);
            color: #1e293b;
        }
        .container { max-width: 600px; margin: 0 auto; }
        .header {
            text-align: center;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #1e293b, #0f172a);
            padding: 20px;
            border-radius: 28px;
        }
        body.light .header {
            background: linear-gradient(135deg, #ffffff, #f8fafc);
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
        }
        h1 {
            font-size: 22px;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .full-title {
            font-size: 9px;
            opacity: 0.5;
            margin-top: 4px;
        }
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
            font-size: 13px;
        }
        body.light .theme-btn, body.light .info-btn {
            background: #e2e8f0;
            color: #1e293b;
        }
        .theme-btn:hover, .info-btn:hover {
            background: #0ea5e9;
            color: white;
        }
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
        }
        body.light .modal-content {
            background: white;
        }
        .modal-content h3 {
            margin-bottom: 15px;
            color: #38bdf8;
        }
        .modal-content p {
            margin-bottom: 10px;
            font-size: 13px;
        }
        .close-modal {
            margin-top: 15px;
            padding: 8px 25px;
            background: #22c55e;
            border: none;
            border-radius: 40px;
            color: white;
            cursor: pointer;
            font-weight: bold;
        }
        .search-card {
            background: #1e293b;
            border-radius: 24px;
            padding: 20px;
            margin-bottom: 20px;
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
            text-align: center;
        }
        body.light .search-box input {
            background: #f1f5f9;
            color: #1e293b;
        }
        .search-box input:focus {
            outline: 2px solid #38bdf8;
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
        }
        .search-btn:hover {
            transform: scale(0.98);
        }
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
        .result-card {
            background: #1e293b;
            border-radius: 24px;
            padding: 20px;
            display: none;
        }
        body.light .result-card {
            background: white;
        }
        .info-item {
            margin-bottom: 14px;
            padding: 14px 16px;
            background: #0f172a;
            border-radius: 18px;
        }
        body.light .info-item {
            background: #f8fafc;
        }
        .number-value {
            font-size: 18px;
            font-weight: 700;
            text-align: center;
            color: #38bdf8;
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
            background: white;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .platform-icon img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
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
        .country-flag { font-size: 28px; }
        .country-name { font-size: 17px; font-weight: 600; }
        .otp-box {
            background: linear-gradient(135deg, #1a2a3a, #0f172a);
            border-radius: 20px;
            padding: 22px;
            text-align: center;
            cursor: pointer;
            border: 2px solid #334155;
            margin-bottom: 14px;
        }
        body.light .otp-box {
            background: linear-gradient(135deg, #e8f0fe, #ffffff);
        }
        .otp-box:hover {
            background: linear-gradient(135deg, #22c55e, #16a34a);
        }
        .otp-value {
            font-size: 42px;
            font-weight: 800;
            letter-spacing: 5px;
            color: #38bdf8;
            font-family: monospace;
        }
        .otp-box:hover .otp-value { color: white; }
        .message-value {
            font-size: 12px;
            text-align: center;
            color: #38bdf8;
        }
        .not-found {
            text-align: center;
            padding: 35px;
            background: #7f1a1a60;
            border-radius: 24px;
            color: #f87171;
            display: none;
        }
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
        }
        .telegram-icon { width: 28px; height: 28px; }
        .telegram-icon svg { fill: white; }
        .toast {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            background: #22c55e;
            color: white;
            padding: 12px 24px;
            border-radius: 50px;
            display: none;
            z-index: 9999;
        }
        .toast.error { background: #ef4444; }
        @media (max-width: 550px) {
            .otp-value { font-size: 32px; letter-spacing: 4px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">
                <img src="https://i.ibb.co/4KMyrVp/logo.png" alt="Logo" onerror="this.src='https://placehold.co/70x70/38bdf8/white?text=G'">
            </div>
            <h1>GetPaid OTP Finder</h1>
            <div class="full-title">🔐 Full Connected GetPaid OTP 2.0</div>
        </div>
        <div class="controls">
            <button class="theme-btn" onclick="toggleTheme()">🌓 Light/Dark</button>
            <button class="info-btn" onclick="openModal()">ℹ️ Info</button>
        </div>
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
        <div class="not-found" id="notFound">❌ OTP not found for this number</div>
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
        <a class="telegram-btn" href="https://t.me/otpincomereal2_bot" target="_blank">
            <div class="telegram-icon"><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.51-.99-.66-.35-1.02.22-1.61.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.03-2.01 1.28-2.83 1.8-.27.18-.51.27-.73.27-.24 0-.63-.12-.92-.23-.44-.16-.83-.25-.8-.53.02-.15.11-.3.28-.45.59-.51 2.6-1.68 4.38-2.78 1.58-.98 2.14-1.15 2.46-1.15.12 0 .28.03.41.12.12.09.19.21.21.35.02.08.02.17-.01.28z"/></svg></div>
            <span>Join Telegram Bot</span>
        </a>
    </div>
    <div id="toast" class="toast">✅ Copied!</div>
    <script>
        let currentOTP = '';
        function toggleTheme() { document.body.classList.toggle('light'); }
        function openModal() { document.getElementById('infoModal').style.display = 'flex'; }
        function closeModal() { document.getElementById('infoModal').style.display = 'none'; }
        function showToast(msg, isError) {
            let toast = document.getElementById('toast');
            toast.textContent = msg || (isError ? 'Failed' : 'Copied!');
            toast.className = 'toast' + (isError ? ' error' : '');
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, 1500);
        }
        function getPlatformIcon(platform) {
            const icons = {'Facebook':'https://i.ibb.co/4T2Yq5M/facebook.png','Instagram':'https://i.ibb.co/s9Q2QjM/instagram.png','WhatsApp':'https://i.ibb.co/6y9Wr0K/whatsapp.png'};
            if(icons[platform]) return `<img src="${icons[platform]}" alt="${platform}">`;
            return `<div style="width:40px;height:40px;background:#334155;border-radius:50%;display:flex;align-items:center;justify-content:center;">?</div>`;
        }
        async function searchOTP() {
            let number = document.getElementById('numberInput').value.trim();
            if(!number) { showToast('Enter number', true); return; }
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultCard').style.display = 'none';
            document.getElementById('notFound').style.display = 'none';
            try {
                let response = await fetch(`/search?number=${encodeURIComponent(number)}`);
                let data = await response.json();
                document.getElementById('loading').style.display = 'none';
                if(data.found) {
                    currentOTP = data.data.otp;
                    document.getElementById('resultNumber').innerText = data.data.number;
                    document.getElementById('platformName').innerHTML = data.data.platform;
                    document.getElementById('platformIcon').innerHTML = getPlatformIcon(data.data.platform);
                    document.getElementById('countryFlag').innerHTML = data.data.flag || '🏳️';
                    document.getElementById('countryName').innerHTML = data.data.country || 'Unknown';
                    document.getElementById('resultOTP').innerHTML = data.data.otp;
                    document.getElementById('resultMessage').innerHTML = data.data.message || '-';
                    document.getElementById('resultCard').style.display = 'block';
                } else {
                    document.getElementById('notFound').style.display = 'block';
                    setTimeout(() => { document.getElementById('notFound').style.display = 'none'; }, 3000);
                }
            } catch(e) {
                document.getElementById('loading').style.display = 'none';
                showToast('Server error', true);
            }
        }
        function copyOTPFromBox() {
            if(currentOTP && currentOTP !== 'Not Found' && currentOTP !== '—') {
                navigator.clipboard.writeText(currentOTP).then(() => {
                    showToast(`${currentOTP} copied!`);
                }).catch(() => {
                    let ta = document.createElement('textarea');
                    ta.value = currentOTP;
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                    showToast(`${currentOTP} copied!`);
                });
            } else { showToast('No OTP', true); }
        }
        document.getElementById('numberInput').addEventListener('keypress', e => { if(e.key === 'Enter') searchOTP(); });
        window.onclick = e => { if(e.target == document.getElementById('infoModal')) closeModal(); };
    </script>
</body>
</html>'''
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
    print("🔰 GetPaid OTP Finder v2.0 - Railway Edition")
    print("=" * 50)
    
    try:
        await client.start()
        me = await client.get_me()
        print(f"✅ Logged in as: {me.first_name} (@{me.username})")
        
        await fetch_otps()
        
        app = web.Application()
        app.router.add_get('/', index)
        app.router.add_get('/search', search_api)
        
        port = int(os.environ.get("PORT", 8080))
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        print("=" * 50)
        print(f"✅ Server running on port {port}")
        print(f"🌐 Open your Railway URL to use the app")
        print("=" * 50)
        
        asyncio.create_task(background_updater())
        
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
