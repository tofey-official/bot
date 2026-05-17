from flask import Blueprint, render_template_string, request, jsonify, redirect, session
from functools import wraps
from config import ADMIN_PASSWORD, SECRET_KEY
from database import db
import asyncio

admin_bp = Blueprint('admin', __name__)

# ==================== مصادقة ====================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated

# ==================== قوالب HTML ====================
LOGIN_HTML = """
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تسجيل الدخول - لوحة التحكم</title>
    <style>
        body { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex; justify-content: center; align-items: center;
            height: 100vh; margin: 0; font-family: 'Segoe UI', sans-serif;
        }
        .login-box { 
            background: white; padding: 40px; border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2); width: 100%; max-width: 400px;
        }
        h2 { text-align: center; color: #333; margin-bottom: 30px; }
        input { 
            width: 100%; padding: 15px; margin: 10px 0; border: 2px solid #ddd;
            border-radius: 8px; font-size: 16px;
        }
        button { 
            width: 100%; padding: 15px; background: #667eea; color: white;
            border: none; border-radius: 8px; font-size: 16px; cursor: pointer;
        }
        button:hover { background: #764ba2; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🔐 لوحة التحكم</h2>
        <form method="POST">
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit">دخول</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>لوحة التحكم - Xtream Bot</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, sans-serif; 
            background: #f0f2f5;
        }
        .sidebar { 
            position: fixed; right: 0; top: 0; width: 260px; height: 100vh;
            background: #1a1a2e; color: white; padding: 20px;
        }
        .sidebar h2 { margin-bottom: 30px; text-align: center; }
        .nav-item { 
            padding: 15px; margin: 5px 0; border-radius: 8px;
            cursor: pointer; transition: all 0.3s;
        }
        .nav-item:hover, .nav-item.active { background: #667eea; }
        .main { margin-right: 260px; padding: 30px; }
        .stats-grid { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px; margin-bottom: 30px;
        }
        .stat-card { 
            background: white; padding: 25px; border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .stat-card h3 { color: #666; font-size: 14px; margin-bottom: 10px; }
        .stat-card .value { font-size: 32px; font-weight: bold; color: #1a1a2e; }
        .stat-card .icon { font-size: 40px; margin-bottom: 10px; }
        .section { 
            background: white; padding: 25px; border-radius: 15px;
            margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .section h2 { margin-bottom: 20px; color: #1a1a2e; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: right; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; }
        .btn { 
            padding: 8px 16px; border: none; border-radius: 6px;
            cursor: pointer; font-size: 14px; margin: 2px;
        }
        .btn-ban { background: #ef4444; color: white; }
        .btn-unban { background: #22c55e; color: white; }
        .btn-broadcast { background: #667eea; color: white; padding: 12px 24px; }
        .badge { 
            padding: 4px 12px; border-radius: 12px; font-size: 12px;
            font-weight: bold;
        }
        .badge-online { background: #dcfce7; color: #166534; }
        .badge-banned { background: #fee2e2; color: #991b1b; }
        .broadcast-box { 
            display: flex; gap: 10px; margin-top: 15px;
        }
        textarea { 
            flex: 1; padding: 12px; border: 2px solid #ddd;
            border-radius: 8px; resize: vertical; min-height: 100px;
        }
        .chart-container { height: 300px; margin: 20px 0; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>🤖 Xtream Bot</h2>
        <div class="nav-item active" onclick="showSection('dashboard')">📊 الإحصائيات</div>
        <div class="nav-item" onclick="showSection('users')">👥 المستخدمين</div>
        <div class="nav-item" onclick="showSection('banned')">🚷 المحظورين</div>
        <div class="nav-item" onclick="showSection('broadcast')">📢 الإذاعة</div>
        <div class="nav-item" onclick="showSection('history')">📋 السجل</div>
        <div class="nav-item" onclick="location.href='/admin/logout'">🚪 خروج</div>
    </div>

    <div class="main">
        <!-- الإحصائيات -->
        <div id="dashboard" class="section-content">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="icon">👥</div>
                    <h3>إجمالي المستخدمين</h3>
                    <div class="value" id="totalUsers">0</div>
                </div>
                <div class="stat-card">
                    <div class="icon">✅</div>
                    <h3>الحسابات الناجحة</h3>
                    <div class="value" id="totalOk">0</div>
                </div>
                <div class="stat-card">
                    <div class="icon">🔍</div>
                    <h3>إجمالي الفحوصات</h3>
                    <div class="value" id="totalChecks">0</div>
                </div>
                <div class="stat-card">
                    <div class="icon">🚷</div>
                    <h3>المحظورين</h3>
                    <div class="value" id="totalBanned">0</div>
                </div>
            </div>
            <div class="section">
                <h2>📈 رسم بياني للإحصائيات</h2>
                <div class="chart-container">
                    <canvas id="statsChart"></canvas>
                </div>
            </div>
        </div>

        <!-- المستخدمين -->
        <div id="users" class="section-content hidden">
            <div class="section">
                <h2>👥 قائمة المستخدمين</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>الاسم</th>
                            <th>المستخدم</th>
                            <th>الفحوصات</th>
                            <th>الناجحة</th>
                            <th>الحالة</th>
                            <th>الإجراءات</th>
                        </tr>
                    </thead>
                    <tbody id="usersTable"></tbody>
                </table>
            </div>
        </div>

        <!-- المحظورين -->
        <div id="banned" class="section-content hidden">
            <div class="section">
                <h2>🚷 قائمة المحظورين</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>الاسم</th>
                            <th>تاريخ الحظر</th>
                            <th>الإجراءات</th>
                        </tr>
                    </thead>
                    <tbody id="bannedTable"></tbody>
                </table>
            </div>
        </div>

        <!-- الإذاعة -->
        <div id="broadcast" class="section-content hidden">
            <div class="section">
                <h2>📢 إذاعة رسالة للجميع</h2>
                <div class="broadcast-box">
                    <textarea id="broadcastMsg" placeholder="اكتب رسالتك هنا..."></textarea>
                    <button class="btn btn-broadcast" onclick="sendBroadcast()">إرسال الإذاعة</button>
                </div>
                <div id="broadcastResult" style="margin-top: 15px;"></div>
            </div>
        </div>

        <!-- السجل -->
        <div id="history" class="section-content hidden">
            <div class="section">
                <h2>📋 سجل الفحوصات الأخيرة</h2>
                <table>
                    <thead>
                        <tr>
                            <th>المستخدم</th>
                            <th>الدومين</th>
                            <th>اليوزر</th>
                            <th>الحالة</th>
                            <th>التاريخ</th>
                        </tr>
                    </thead>
                    <tbody id="historyTable"></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let botToken = '{{ bot_token }}';
        
        function showSection(id) {
            document.querySelectorAll('.section-content').forEach(el => el.classList.add('hidden'));
            document.getElementById(id).classList.remove('hidden');
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            event.target.classList.add('active');
            if (id === 'users') loadUsers();
            if (id === 'banned') loadBanned();
            if (id === 'history') loadHistory();
        }

        async function loadStats() {
            const res = await fetch('/admin/api/stats');
            const data = await res.json();
            document.getElementById('totalUsers').textContent = data.total_users;
            document.getElementById('totalOk').textContent = data.total_ok;
            document.getElementById('totalChecks').textContent = data.total_checks;
            document.getElementById('totalBanned').textContent = data.total_banned;
            
            updateChart(data.total_ok, data.total_checks - data.total_ok);
        }

        function updateChart(ok, bad) {
            const ctx = document.getElementById('statsChart').getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['ناجح', 'فاشل'],
                    datasets: [{
                        data: [ok, bad],
                        backgroundColor: ['#22c55e', '#ef4444']
                    }]
                }
            });
        }

        async function loadUsers() {
            const res = await fetch('/admin/api/users');
            const users = await res.json();
            const tbody = document.getElementById('usersTable');
            tbody.innerHTML = users.map(u => `
                <tr>
                    <td>${u.user_id}</td>
                    <td>${u.first_name}</td>
                    <td>@${u.username || '—'}</td>
                    <td>${u.checks_count || 0}</td>
                    <td>${u.ok_count || 0}</td>
                    <td><span class="badge ${u.is_banned ? 'badge-banned' : 'badge-online'}">${u.is_banned ? 'محظور' : 'نشط'}</span></td>
                    <td>
                        ${u.is_banned 
                            ? `<button class="btn btn-unban" onclick="unbanUser(${u.user_id})">فك الحظر</button>`
                            : `<button class="btn btn-ban" onclick="banUser(${u.user_id})">حظر</button>`
                        }
                    </td>
                </tr>
            `).join('');
        }

        async function loadBanned() {
            const res = await fetch('/admin/api/banned');
            const users = await res.json();
            document.getElementById('bannedTable').innerHTML = users.map(u => `
                <tr>
                    <td>${u.user_id}</td>
                    <td>${u.first_name}</td>
                    <td>${u.joined_at || '—'}</td>
                    <td><button class="btn btn-unban" onclick="unbanUser(${u.user_id})">فك الحظر</button></td>
                </tr>
            `).join('');
        }

        async function banUser(id) {
            await fetch('/admin/api/ban', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: id})
            });
            loadUsers();
            loadStats();
        }

        async function unbanUser(id) {
            await fetch('/admin/api/unban', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: id})
            });
            loadUsers();
            loadBanned();
            loadStats();
        }

        async function sendBroadcast() {
            const msg = document.getElementById('broadcastMsg').value;
            if (!msg) return alert('الرجاء كتابة رسالة');
            const res = await fetch('/admin/api/broadcast', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: msg})
            });
            const data = await res.json();
            document.getElementById('broadcastResult').innerHTML = 
                `✅ تم الإرسال لـ ${data.sent} مستخدم | ❌ فشل: ${data.failed}`;
        }

        async function loadHistory() {
            const res = await fetch('/admin/api/history');
            const history = await res.json();
            document.getElementById('historyTable').innerHTML = history.map(h => `
                <tr>
                    <td>${h.user_id}</td>
                    <td>${h.domain}</td>
                    <td>${h.username}</td>
                    <td>${h.status}</td>
                    <td>${new Date(h.checked_at).toLocaleString('ar-SA')}</td>
                </tr>
            `).join('');
        }

        loadStats();
    </script>
</body>
</html>
"""

# ==================== Routes ====================
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect('/admin/')
        return render_template_string(LOGIN_HTML + '<p style="color:red;text-align:center;">كلمة مرور خاطئة</p>')
    return render_template_string(LOGIN_HTML)

@admin_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin/login')

@admin_bp.route('/')
@login_required
def dashboard():
    from config import BOT_TOKEN
    return render_template_string(DASHBOARD_HTML, bot_token=BOT_TOKEN)

# ==================== API Routes ====================
@admin_bp.route('/api/stats')
@login_required
def api_stats():
    users = db.get_all_users()
    stats = db.get_global_stats()
    return jsonify({
        "total_users": len(users),
        "total_ok": stats.get("total_ok", 0),
        "total_checks": stats.get("total_checks", 0),
        "total_banned": len([u for u in users if u.get("is_banned")])
    })

@admin_bp.route('/api/users')
@login_required
def api_users():
    return jsonify(db.get_all_users())

@admin_bp.route('/api/banned')
@login_required
def api_banned():
    return jsonify(db.get_banned_users())

@admin_bp.route('/api/ban', methods=['POST'])
@login_required
def api_ban():
    data = request.get_json()
    db.ban_user(data['user_id'])
    return jsonify({"status": "banned"})

@admin_bp.route('/api/unban', methods=['POST'])
@login_required
def api_unban():
    data = request.get_json()
    db.unban_user(data['user_id'])
    return jsonify({"status": "unbanned"})

@admin_bp.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    from telegram import Bot
    from config import BOT_TOKEN
    
    data = request.get_json()
    message = data['message']
    bot = Bot(token=BOT_TOKEN)
    
    users = db.get_all_users()
    sent = 0
    failed = 0
    
    for user in users:
        if not user.get("is_banned"):
            try:
                asyncio.run(bot.send_message(
                    chat_id=user['user_id'], 
                    text=f"📢 *إذاعة:*\n\n{message}",
                    parse_mode="Markdown"
                ))
                sent += 1
            except Exception:
                failed += 1
    
    return jsonify({"sent": sent, "failed": failed})

@admin_bp.route('/api/history')
@login_required
def api_history():
    # جلب آخر 50 سجل
    history = []
    if db.db:
        docs = (db.db.collection("history")
                .order_by("checked_at", direction=firestore.Query.DESCENDING)
                .limit(50)
                .stream())
        history = [doc.to_dict() for doc in docs]
    return jsonify(history)
