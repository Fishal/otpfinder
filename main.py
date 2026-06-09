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
STRING_SESSION = os.environ.get("STRING_SESSION")
TELETHON_SESSION = os.environ.get("TELETHON_SESSION")

if STRING_SESSION:
    from telethon.sessions import StringSession
    client = TelegramClient(StringSession(STRING_SESSION), api_id, api_hash)
    print("✅ Using String Session")
elif TELETHON_SESSION:
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
    client = TelegramClient("user_session", api_id, api_hash)
    print("✅ Using local session file")

all_otps = []

# ================= উন্নত ফাংশন =================

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
    """সব ধরনের নম্বর এক্সট্রাক্ট করা"""
    if not text:
        return None
    
    # প্যাটার্ন: Number: 9929***3727
    match = re.search(r'Number:\s*(\d[\d\*]+)', text)
    if match:
        return match.group(1)
    
    # প্যাটার্ন: 📞 Number: 9929***3727
    match = re.search(r'📞\s*Number:\s*(\d[\d\*]+)', text)
    if match:
        return match.group(1)
    
    # প্যাটার্ন: *** আংশিক নম্বর
    match = re.search(r'(\d{3,4}\*{3}\d{3,4})', text)
    if match:
        return match.group(1)
    
    # সম্পূর্ণ নম্বর (কোনো স্পেস ছাড়া)
    numbers = re.findall(r'\b(\d{8,15})\b', text)
    if numbers:
        return numbers[0]
    
    return None

def extract_otp(text):
    """সব ধরনের OTP এক্সট্রাক্ট করা"""
    if not text:
        return None
    
    # প্যাটার্ন: OTP Code: 857457
    match = re.search(r'OTP Code:\s*(\d{4,8})', text)
    if match:
        return match.group(1)
    
    # প্যাটার্ন: 🔑 OTP Code: 857457
    match = re.search(r'🔑\s*OTP Code:\s*(\d{4,8})', text)
    if match:
        return match.group(1)
    
    # ইংরেজি: XXXX is your Instagram code
    match = re.search(r'(\d{4,8})\s+is your (Instagram|Facebook|TikTok) code', text, re.I)
    if match:
        return match.group(1)
    
    # ফরাসি: XXXX est votre code
    match = re.search(r'(\d{4,8})\s+est votre code (Instagram|Facebook|TikTok)', text, re.I)
    if match:
        return match.group(1)
    
    # পর্তুগিজ: XXXX é seu código
    match = re.search(r'(\d{4,8})\s+é seu código (Instagram|Facebook|TikTok)', text, re.I)
    if match:
        return match.group(1)
    
    # ইন্দোনেশিয়ান: XXXX adalah kode Facebook Anda
    match = re.search(r'(\d{4,8})\s+adalah kode (Instagram|Facebook|TikTok)', text, re.I)
    if match:
        return match.group(1)
    
    # পোলিশ: XXXX to Twój kod Facebooka
    match = re.search(r'(\d{4,8})\s+to Twój kod (Instagram|Facebook|TikTok)', text, re.I)
    if match:
        return match.group(1)
    
    # সাধারণ নম্বর (শুধু ডিজিট)
    codes = re.findall(r'\b(\d{4,8})\b', text)
    for code in codes:
        if not re.match(r'^(19|20)\d{2}', code) and len(code) >= 4:
            return code
    
    return None

def detect_platform(text):
    """প্ল্যাটফর্ম ডিটেক্ট করা"""
    if not text:
        return "Unknown"
    t = text.lower()
    
    if 'facebook' in t or 'est votre code facebook' in t or 'adalah kode facebook' in t or 'to twój kod facebooka' in t:
        return "Facebook"
    if 'instagram' in t or '#ig' in t or 'é seu código de instagram' in t:
        return "Instagram"
    if 'whatsapp' in t:
        return "WhatsApp"
    if 'tiktok' in t:
        return "TikTok"
    return "Other"

def extract_country(text):
    """কান্ট্রি এক্সট্রাক্ট করা"""
    match = re.search(r'Country:\s*[🇦-🇿]+\s*([\w\s]+)', text)
    if match:
        return match.group(1).strip()
    
    match = re.search(r'🌐\s*Country:\s*[🇦-🇿]+\s*([\w\s]+)', text)
    if match:
        return match.group(1).strip()
    
    return "Unknown"

def extract_country_flag_from_text(text):
    """টেক্সট থেকে ফ্লাগ ইমোজি এক্সট্রাক্ট"""
    match = re.search(r'[🇦-🇿]{2}', text)
    if match:
        return match.group(0)
    return None

def normalize_number(number):
    """নম্বর নরমালাইজ করা (শুধু ডিজিট)"""
    if not number:
        return ""
    return re.sub(r'[^0-9]', '', number)

def get_number_patterns(number):
    """নম্বরের বিভিন্ন প্যাটার্ন তৈরি করা"""
    if not number:
        return []
    
    digits = normalize_number(number)
    if not digits:
        return []
    
    patterns = [digits]
    
    # প্রথম 3-4 ডিজিট + শেষ 3-4 ডিজিট
    if len(digits) >= 7:
        first4 = digits[:4]
        last4 = digits[-4:]
        patterns.append(f"{first4}***{last4}")
        
        first3 = digits[:3]
        last3 = digits[-3:]
        patterns.append(f"{first3}***{last3}")
    
    # আংশিক ম্যাচিং প্যাটার্ন
    if len(digits) >= 8:
        patterns.append(digits[:6])
        patterns.append(digits[-6:])
    
    return patterns

def match_number(sms_number, search_number):
    """উন্নত নম্বর ম্যাচিং সিস্টেম"""
    if not sms_number or not search_number:
        return False
    
    # নরমালাইজড ভার্সন
    sms_digits = normalize_number(sms_number)
    search_digits = normalize_number(search_number)
    
    if not sms_digits or not search_digits:
        return False
    
    # 1. ডাইরেক্ট ম্যাচ
    if sms_digits == search_digits:
        return True
    
    # 2. স্মস নম্বর যদি *** থাকে তাহলে প্যাটার্ন ম্যাচ
    if '*' in sms_number:
        # প্যাটার্ন: "9929***3727" বনাম "99291234567"
        pattern = sms_number.replace('*', '[0-9]')
        if re.fullmatch(pattern, search_number):
            return True
        
        # প্যাটার্ন থেকে prefix + suffix
        parts = sms_number.split('***')
        if len(parts) == 2:
            prefix, suffix = parts
            if search_digits.startswith(prefix) and search_digits.endswith(suffix):
                return True
    
    # 3. শেষ 6 ডিজিট ম্যাচ (বেশিরভাগ OTP নম্বরের জন্য)
    if len(sms_digits) >= 6 and len(search_digits) >= 6:
        if sms_digits[-6:] == search_digits[-6:]:
            return True
    
    # 4. প্রথম 5 এবং শেষ 4 ডিজিট
    if len(sms_digits) >= 9 and len(search_digits) >= 9:
        if sms_digits[:5] == search_digits[:5] and sms_digits[-4:] == search_digits[-4:]:
            return True
    
    # 5. শেষ 4 ডিজিট ম্যাচ
    if len(sms_digits) >= 4 and len(search_digits) >= 4:
        if sms_digits[-4:] == search_digits[-4:]:
            return True
    
    return False

def extract_clean_message(text):
    """ক্লিন মেসেজ এক্সট্রাক্ট"""
    if not text:
        return ""
    
    # OTP লাইন খোঁজা
    lines = text.split('\n')
    for line in lines:
        if re.search(r'(is your|est votre|é seu|adalah kode|to Twój kod)', line, re.I):
            return line.strip()
    
    return text[:150] + "..." if len(text) > 150 else text

# ================= মেসেজ সংগ্রহ =================

async def fetch_otps():
    global all_otps
    print("\n📡 গ্রুপ থেকে মেসেজ পড়ছি...")
    
    try:
        messages = []
        seen = set()
        
        async for msg in client.iter_messages(GROUP_ID, limit=500):
            text = msg.message or msg.raw_text or ""
            
            if not text or len(text) < 20:
                continue
            
            number = extract_number(text)
            if not number:
                continue
            
            otp = extract_otp(text)
            platform = detect_platform(text)
            country = extract_country(text)
            flag_from_text = extract_country_flag_from_text(text)
            flag_emoji = flag_from_text if flag_from_text else get_country_flag_emoji(country)
            
            # ডুপ্লিকেট চেক
            key = f"{normalize_number(number)}_{otp}"
            if key in seen:
                continue
            
            seen.add(key)
            
            clean_msg = extract_clean_message(text)
            
            messages.append({
                "number": number,
                "number_normalized": normalize_number(number),
                "otp": otp if otp else "Not Found",
                "platform": platform,
                "country": country if country != "Unknown" else "Unknown",
                "flag": flag_emoji,
                "message": clean_msg,
                "full_text": text[:500]
            })
            
            if len(messages) >= 300:
                break
        
        # নতুন মেসেজ আগে দেখাবে
        messages.reverse()
        all_otps = messages
        
        print(f"✅ {len(messages)} টি OTP পাওয়া গেছে!")
        
        # ডিবাগ: প্রথম 5 টা দেখাও
        for i, m in enumerate(messages[:5]):
            print(f"   {i+1}. {m['number']} → {m['otp']} ({m['platform']})")
        
    except Exception as e:
        print(f"❌ এরর: {e}")

# ================= ওয়েব সার্ভার =================

async def index(request):
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes, viewport-fit=cover">
    <title>GetPaid OTP Finder Pro</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: #e2e8f0;
            min-height: 100vh;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            padding: 0;
            margin: 0;
        }
        body.light {
            background: linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 100%);
            color: #1e293b;
        }
        .container { max-width: 600px; margin: 0 auto; padding: 20px 16px; }
        .header {
            text-align: center;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #1e293b, #0f172a);
            padding: 20px 16px;
            border-radius: 28px;
            border: 1px solid #334155;
        }
        body.light .header {
            background: linear-gradient(135deg, #ffffff, #f8fafc);
            border: 1px solid #e2e8f0;
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
            background-clip: text;
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
        }
        body.light .theme-btn, body.light .info-btn {
            background: #e2e8f0;
            color: #1e293b;
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
            outline: none;
            text-align: center;
        }
        body.light .search-box input {
            background: #f1f5f9;
            color: #1e293b;
            border: 1px solid #cbd5e1;
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
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .result-card {
            background: #1e293b;
            border-radius: 24px;
            padding: 20px;
            display: none;
            animation: fadeIn 0.3s ease;
        }
        body.light .result-card {
            background: white;
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
            overflow: hidden;
            background: white;
        }
        .platform-icon img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .platform-name { font-size: 18px; font-weight: 700; }
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
            border: 2px solid #cbd5e1;
        }
        .otp-box:hover {
            transform: scale(0.98);
            background: linear-gradient(135deg, #22c55e, #16a34a);
        }
        .otp-value {
            font-size: 42px;
            font-weight: 800;
            letter-spacing: 5px;
            color: #38bdf8;
            font-family: 'Courier New', monospace;
        }
        .otp-box:hover .otp-value { color: white; }
        .message-value {
            font-size: 12px;
            font-weight: 500;
            word-break: break-all;
            color: #38bdf8;
            text-align: center;
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
                <img src="https://i.ibb.co/RpzTyt1v/bot.jpg" alt="bot">
            </div>
            <h1>GetPaid OTP Finder Pro</h1>
            <div class="full-title" style="font-size:9px;opacity:0.5;">🔐 Advanced OTP Search v3.0</div>
        </div>
        <div class="controls">
            <button class="theme-btn" onclick="toggleTheme()">🌓 Theme</button>
            <button class="info-btn" onclick="openModal()">ℹ️ Info</button>
        </div>
        <div id="infoModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:1000;justify-content:center;align-items:center;">
            <div style="background:#1e293b;border-radius:24px;padding:25px;max-width:300px;text-align:center;">
                <h3 style="color:#38bdf8;">ℹ️ Information</h3>
                <p>📌 Enter full phone number</p>
                <p>🔒 Advanced matching system</p>
                <p>📱 Click OTP to copy</p>
                <button onclick="closeModal()" style="margin-top:15px;padding:8px 25px;background:#22c55e;border:none;border-radius:40px;color:white;cursor:pointer;">Got it</button>
            </div>
        </div>
        <div class="search-card">
            <div class="search-box">
                <input type="text" id="numberInput" placeholder="📞 Enter full phone number" autocomplete="off">
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
            <span>📱 Join Telegram Bot</span>
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
            toast.textContent = msg || (isError ? '❌ Failed' : '✅ Copied!');
            toast.className = 'toast' + (isError ? ' error' : '');
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, 1500);
        }
        function getPlatformIcon(platform) {
            const icons = {
                'Facebook': 'https://i.ibb.co/Rk4wk8d5/facebook.jpg',
                'Instagram': 'https://i.ibb.co/bgcdmD3P/instagram.jpg',
                'WhatsApp': 'https://i.ibb.co/QvvDqSRs/whatsapp.jpg',
                'TikTok': 'https://i.ibb.co/ymBVDLyF/png-transparent-tiktok-tiktok-logo-tiktok-icon-thumbnail.png'
            };
            let url = icons[platform];
            if(url) return `<img src="${url}" alt="${platform}">`;
            return `<div style="width:40px;height:40px;background:#334155;border-radius:50%;display:flex;align-items:center;justify-content:center;">?</div>`;
        }
        async function searchOTP() {
            let number = document.getElementById('numberInput').value.trim();
            if(!number) { showToast('⚠️ Enter number', true); return; }
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
                showToast('❌ Server error', true);
            }
        }
        function copyOTPFromBox() {
            if(currentOTP && currentOTP !== 'Not Found' && currentOTP !== '—') {
                navigator.clipboard.writeText(currentOTP).then(() => {
                    showToast(`✅ ${currentOTP} copied!`);
                    document.getElementById('otpBox').style.background = 'linear-gradient(135deg, #22c55e, #16a34a)';
                    setTimeout(() => { document.getElementById('otpBox').style.background = ''; }, 300);
                }).catch(() => { showToast('❌ Failed', true); });
            } else { showToast('❌ No OTP', true); }
        }
        document.getElementById('numberInput').addEventListener('keypress', function(e) { if(e.key === 'Enter') searchOTP(); });
        window.onclick = function(event) { let modal = document.getElementById('infoModal'); if(event.target == modal) modal.style.display = 'none'; }
    </script>
</body>
</html>'''
    return web.Response(text=html, content_type='text/html')

async def search_api(request):
    number = request.query.get('number', '').strip()
    if not number:
        return web.json_response({'found': False})
    
    print(f"\n🔍 Searching: {number}")
    
    # উন্নত সার্চ অ্যালগরিদম
    found_items = []
    
    for item in all_otps:
        if match_number(item['number'], number):
            found_items.append(item)
            print(f"   ✅ Matched: {item['number']} → {item['otp']}")
    
    # যদি একাধিক ম্যাচ পায় তাহলে সবচেয়ে ভালোটা নিবে
    if found_items:
        # প্রাধান্য: যার OTP আছে এবং সম্পূর্ণ নম্বর ম্যাচ বেশি
        best_item = found_items[0]
        for item in found_items:
            if item['otp'] != 'Not Found' and best_item['otp'] == 'Not Found':
                best_item = item
            elif normalize_number(item['number']) == normalize_number(number):
                best_item = item
                break
        return web.json_response({'found': True, 'data': best_item})
    
    print(f"   ❌ Not found: {number}")
    return web.json_response({'found': False})

async def background_updater():
    while True:
        await fetch_otps()
        await asyncio.sleep(10)

async def main():
    print("=" * 50)
    print("🔰 GetPaid OTP Finder Pro v3.0")
    print("=" * 50)
    
    try:
        await client.start()
        me = await client.get_me()
        print(f"✅ Logged in: {me.first_name}")
        
        await fetch_otps()
        
        app = web.Application()
        app.router.add_get('/', index)
        app.router.add_get('/search', search_api)
        
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
