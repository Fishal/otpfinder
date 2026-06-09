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

# সেশন ফাইল - Railway এ আপলোড করা ফাইল
SESSION_NAME = "user_session"

client = TelegramClient(SESSION_NAME, api_id, api_hash)
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 30px;
            background: rgba(30, 41, 59, 0.5);
            border-radius: 20px;
        }
        h1 {
            font-size: 28px;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .search-card {
            background: #1e293b;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 20px;
        }
        .search-box input {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 10px;
            background: #0f172a;
            color: white;
            font-size: 16px;
            margin-bottom: 15px;
        }
        .search-btn {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 10px;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            color: white;
            font-weight: bold;
            font-size: 18px;
            cursor: pointer;
        }
        .result-card {
            background: #1e293b;
            border-radius: 20px;
            padding: 30px;
            display: none;
        }
        .otp-box {
            background: linear-gradient(135deg, #1a2a3a, #0f172a);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            margin: 20px 0;
        }
        .otp-value {
            font-size: 48px;
            font-weight: bold;
            color: #38bdf8;
            letter-spacing: 5px;
        }
        .info-item {
            background: #0f172a;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            display: none;
        }
        .spinner {
            border: 3px solid #334155;
            border-top: 3px solid #38bdf8;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
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
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 GetPaid OTP Finder</h1>
            <p>Find OTP codes from Telegram group</p>
        </div>
        
        <div class="search-card">
            <div class="search-box">
                <input type="text" id="numberInput" placeholder="📞 Enter phone number">
                <button class="search-btn" onclick="searchOTP()">🔍 Search OTP</button>
            </div>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Searching for OTP...</p>
        </div>
        
        <div class="result-card" id="resultCard">
            <div class="info-item">
                <div id="resultNumber" style="font-size: 20px; font-weight: bold; text-align: center;"></div>
            </div>
            <div class="info-item">
                <div id="resultPlatform" style="text-align: center;"></div>
            </div>
            <div class="info-item">
                <div id="resultCountry" style="text-align: center;"></div>
            </div>
            <div class="otp-box" onclick="copyOTP()">
                <div class="otp-value" id="resultOTP"></div>
                <div style="font-size: 12px; margin-top: 10px;">👇 Click to copy</div>
            </div>
            <div class="info-item">
                <div id="resultMessage" style="font-size: 12px;"></div>
            </div>
        </div>
    </div>
    
    <div id="toast" class="toast">✅ Copied!</div>
    
    <script>
        let currentOTP = '';
        
        async function searchOTP() {
            let number = document.getElementById('numberInput').value.trim();
            if (!number) {
                alert('Please enter a number');
                return;
            }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultCard').style.display = 'none';
            
            try {
                let response = await fetch(`/search?number=${encodeURIComponent(number)}`);
                let data = await response.json();
                
                document.getElementById('loading').style.display = 'none';
                
                if (data.found) {
                    currentOTP = data.data.otp;
                    document.getElementById('resultNumber').innerHTML = `📞 ${data.data.number}`;
                    document.getElementById('resultPlatform').innerHTML = `🔹 Platform: ${data.data.platform}`;
                    document.getElementById('resultCountry').innerHTML = `${data.data.flag} Country: ${data.data.country}`;
                    document.getElementById('resultOTP').innerHTML = data.data.otp;
                    document.getElementById('resultMessage').innerHTML = data.data.message || 'No message';
                    document.getElementById('resultCard').style.display = 'block';
                } else {
                    alert('❌ OTP not found for this number');
                }
            } catch (error) {
                document.getElementById('loading').style.display = 'none';
                alert('Server error. Please try again.');
            }
        }
        
        function copyOTP() {
            if (currentOTP && currentOTP !== 'Not Found') {
                navigator.clipboard.writeText(currentOTP).then(() => {
                    let toast = document.getElementById('toast');
                    toast.style.display = 'block';
                    setTimeout(() => {
                        toast.style.display = 'none';
                    }, 2000);
                });
            }
        }
        
        document.getElementById('numberInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') searchOTP();
        });
    </script>
</body>
</html>'''
    return web.Response(text=html, content_type='text/html')

async def search_api(request):
    number = request.query.get('number', '').strip()
    if not number:
        return web.json_response({'found': False})
    
    for item in all_otps:
        if match_number_by_pattern(item['number'], number):
            return web.json_response({'found': True, 'data': item})
    
    return web.json_response({'found': False})

async def background_updater():
    while True:
        await fetch_otps()
        await asyncio.sleep(5)

async def main():
    print("=" * 50)
    print("🔰 GetPaid OTP Finder v2.0")
    print("=" * 50)
    
    # Start client
    await client.start()
    me = await client.get_me()
    print(f"✅ Logged in as: {me.first_name}")
    
    await fetch_otps()
    
    app = web.Application()
    app.router.add_get('/', index)
    app.router.add_get('/search', search_api)
    
    port = int(os.environ.get("PORT", 8080))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"✅ Server running on port {port}")
    
    asyncio.create_task(background_updater())
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
