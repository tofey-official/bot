from flask import Blueprint, render_template_string, request
import urllib.parse

player_bp = Blueprint('player', __name__)

PLAYER_HTML = """
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مشغل Xtream</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <script src="https://cdn.jsdelivr.net/npm/clappr@latest/dist/clappr.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: #0f0f0f; 
            color: #fff; 
            font-family: 'Segoe UI', Tahoma, sans-serif;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { 
            text-align: center; 
            padding: 30px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            margin-bottom: 30px;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .player-container { 
            background: #1a1a1a; 
            border-radius: 15px; 
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }
        #player { width: 100%; height: 500px; }
        .controls { 
            display: flex; 
            gap: 10px; 
            padding: 20px; 
            background: #222;
            flex-wrap: wrap;
        }
        .input-group { flex: 1; min-width: 200px; }
        .input-group label { display: block; margin-bottom: 5px; color: #aaa; }
        input, select { 
            width: 100%; 
            padding: 12px; 
            border: 1px solid #444; 
            background: #333; 
            color: #fff;
            border-radius: 8px;
            font-size: 14px;
        }
        button { 
            padding: 12px 30px; 
            background: #667eea; 
            color: white; 
            border: none;
            border-radius: 8px; 
            cursor: pointer; 
            font-size: 16px;
            transition: all 0.3s;
        }
        button:hover { background: #764ba2; transform: translateY(-2px); }
        .info-panel { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px; 
            margin-top: 20px;
        }
        .info-card { 
            background: #1a1a1a; 
            padding: 20px; 
            border-radius: 10px;
            border-right: 4px solid #667eea;
        }
        .info-card h3 { color: #667eea; margin-bottom: 10px; }
        .status { 
            display: inline-block; 
            padding: 5px 15px; 
            border-radius: 20px;
            font-size: 12px; 
            font-weight: bold;
        }
        .status.online { background: #22c55e; color: white; }
        .status.offline { background: #ef4444; color: white; }
        @media (max-width: 768px) { #player { height: 250px; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📺 مشغل Xtream Codes</h1>
            <p>مشغل ويب متكامل يدعم HLS و M3U8</p>
        </div>
        
        <div class="player-container">
            <div id="player"></div>
            <div class="controls">
                <div class="input-group">
                    <label>رابط البث (M3U8/MP4):</label>
                    <input type="text" id="streamUrl" placeholder="أدخل رابط البث..." 
                           value="{{ stream_url|default('') }}">
                </div>
                <div class="input-group">
                    <label>نوع البث:</label>
                    <select id="streamType">
                        <option value="hls">HLS (.m3u8)</option>
                        <option value="mp4">MP4 Video</option>
                    </select>
                </div>
                <button onclick="playStream()">▶️ تشغيل</button>
                <button onclick="toggleFullscreen()">⛶ ملء الشاشة</button>
            </div>
        </div>

        <div class="info-panel">
            <div class="info-card">
                <h3>📊 حالة البث</h3>
                <span id="streamStatus" class="status offline">غير متصل</span>
                <p id="streamInfo">في انتظار التشغيل...</p>
            </div>
            <div class="info-card">
                <h3>⚡ الجودة</h3>
                <p id="quality">--</p>
            </div>
            <div class="info-card">
                <h3>📡 البروتوكول</h3>
                <p id="protocol">HLS / HTTP</p>
            </div>
        </div>
    </div>

    <script>
        let player = null;
        let hls = null;

        function playStream() {
            const url = document.getElementById('streamUrl').value.trim();
            const type = document.getElementById('streamType').value;
            
            if (!url) { alert('الرجاء إدخال رابط البث'); return; }
            
            destroyPlayer();
            
            if (type === 'hls' && Hls.isSupported()) {
                hls = new Hls({
                    debug: false,
                    enableWorker: true,
                    lowLatencyMode: true
                });
                
                const video = document.createElement('video');
                video.style.width = '100%';
                video.style.height = '100%';
                video.controls = true;
                video.autoplay = true;
                document.getElementById('player').innerHTML = '';
                document.getElementById('player').appendChild(video);
                
                hls.loadSource(url);
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED, () => {
                    updateStatus(true, 'متصل - جاري البث');
                    video.play();
                });
                hls.on(Hls.Events.ERROR, (event, data) => {
                    if (data.fatal) updateStatus(false, 'خطأ في البث: ' + data.type);
                });
            } else {
                player = new Clappr.Player({
                    source: url,
                    parentId: "#player",
                    autoPlay: true,
                    height: "100%",
                    width: "100%",
                    mediacontrol: { seekbar: "#667eea", buttons: "#fff" }
                });
                updateStatus(true, 'متصل');
            }
        }

        function destroyPlayer() {
            if (hls) { hls.destroy(); hls = null; }
            if (player) { player.destroy(); player = null; }
        }

        function updateStatus(online, info) {
            const status = document.getElementById('streamStatus');
            status.className = 'status ' + (online ? 'online' : 'offline');
            status.textContent = online ? 'متصل' : 'غير متصل';
            document.getElementById('streamInfo').textContent = info;
        }

        function toggleFullscreen() {
            const elem = document.getElementById('player');
            if (elem.requestFullscreen) elem.requestFullscreen();
        }

        // تشغيل تلقائي إذا كان هناك رابط
        window.onload = () => {
            const urlParams = new URLSearchParams(window.location.search);
            const streamUrl = urlParams.get('url');
            if (streamUrl) {
                document.getElementById('streamUrl').value = decodeURIComponent(streamUrl);
                playStream();
            }
        };
    </script>
</body>
</html>
"""

@player_bp.route('/player')
def player():
    stream_url = request.args.get('url', '')
    return render_template_string(PLAYER_HTML, stream_url=stream_url)
