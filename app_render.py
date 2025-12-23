from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timezone, timedelta, date
from werkzeug.security import generate_password_hash, check_password_hash
import os
import calendar  # 追加

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-debug-mode'
# SQLAlchemy接続をコメントアウト（一時的にデータベースなし）
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///study_app.db'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLAlchemyを一時的に無効化
# db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# デバッグモードフラグ
DEBUG_MODE = True

# アバターオプション
AVATAR_OPTIONS = {
    'default_cat': 'https://api.dicebear.com/7.x/avataaars/svg?seed=default',
    'おじいさん(？)': 'https://api.dicebear.com/7.x/avataaars/svg?seed=cat',
    '歯抜けお姉さん': 'https://api.dicebear.com/7.x/avataaars/svg?seed=dog',
    '髪ちょび': 'https://api.dicebear.com/7.x/avataaars/svg?seed=bear',
    '髭おじさん': 'https://api.dicebear.com/7.x/avataaars/svg?seed=fox',
    '坊主': 'https://api.dicebear.com/7.x/avataaars/svg?seed=rabbit',
    '嫌な顔': 'https://api.dicebear.com/7.x/avataaars/svg?seed=panda',
    '睡眠(？)': 'https://api.dicebear.com/7.x/avataaars/svg?seed=lion',
    '白眉': 'https://api.dicebear.com/7.x/avataaars/svg?seed=tiger',
    'チャラ男': 'https://api.dicebear.com/7.x/avataaars/svg?seed=wolf',
    '笑顔': 'https://api.dicebear.com/7.x/avataaars/svg?seed=koala'
}

# ダミーユーザークラス（データベースなし）
class DummyUser(UserMixin):
    def __init__(self, user_id, username, level=1, xp=0, avatar='default_cat'):
        self.id = user_id
        self.username = username
        self.level = level
        self.xp = xp
        self.avatar = avatar
        self.records_count = 0
        self.created_at = datetime.now(timezone.utc)
    
    @property
    def xp_to_next(self):
        return self.level * 100

# ダミーレコードクラス
class DummyRecord:
    def __init__(self, record_id, subject, content, difficulty=3, learning_time=30):
        self.id = record_id
        self.subject = subject
        self.content = content
        self.difficulty = difficulty
        self.learning_time = learning_time
        self.study_date = date.today().strftime('%Y-%m-%d')
        self.timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        self.is_mastered = False
        self.mastered_at = None

# ダミーデータストア
class DummyDataStore:
    def __init__(self):
        self.users = {}
        self.records = {}
        self.next_user_id = 1
        self.next_record_id = 1
        
        # デフォルトテストユーザー
        self.add_user('test', 'test123', level=5, xp=350, avatar='cat')
        self.add_user('admin', 'debug123', level=1, xp=0, avatar='default_cat')
    
    def add_user(self, username, password, level=1, xp=0, avatar='default_cat'):
        user_id = self.next_user_id
        self.next_user_id += 1
        user = DummyUser(user_id, username, level, xp, avatar)
        user.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        self.users[user_id] = user
        self.users[username] = user  # ユーザー名でも検索可能に
        return user
    
    def get_user_by_username(self, username):
        for user in self.users.values():
            if hasattr(user, 'username') and user.username == username:
                return user
        return None
    
    def get_user_by_id(self, user_id):
        return self.users.get(user_id)
    
    def add_record(self, user_id, subject, content, difficulty=3, learning_time=30):
        record_id = self.next_record_id
        self.next_record_id += 1
        record = DummyRecord(record_id, subject, content, difficulty, learning_time)
        
        if user_id not in self.records:
            self.records[user_id] = []
        self.records[user_id].append(record)
        return record
    
    def get_user_records(self, user_id):
        return self.records.get(user_id, [])
    
    def delete_record(self, user_id, record_id):
        if user_id in self.records:
            self.records[user_id] = [r for r in self.records[user_id] if r.id != record_id]
            return True
        return False
    
    def toggle_mastery(self, user_id, record_id):
        if user_id in self.records:
            for record in self.records[user_id]:
                if record.id == record_id:
                    record.is_mastered = not record.is_mastered
                    record.mastered_at = datetime.now(timezone.utc) if record.is_mastered else None
                    return record
        return None

# グローバルデータストア
dummy_store = DummyDataStore()

@login_manager.user_loader
def load_user(user_id):
    """ユーザーローダー（ダミーデータ用）"""
    return dummy_store.get_user_by_id(int(user_id))

# 基本科目
DEFAULT_SUBJECTS = ['数学', '英語', '国語', '理科', '社会', 'プログラミング']

def get_user_custom_subjects(user_id):
    """ユーザーのカスタム科目リスト（ダミー）"""
    return DEFAULT_SUBJECTS

def add_xp_and_check_level_up(user, xp_to_add, reason=""):
    """XP追加とレベルアップチェック（ダミー）"""
    old_level = user.level
    user.xp += xp_to_add
    
    # レベルアップチェック
    xp_needed_for_next = user.xp_to_next
    while user.xp >= xp_needed_for_next:
        user.level += 1
        user.xp -= xp_needed_for_next
        xp_needed_for_next = user.xp_to_next
    
    new_level = user.level
    
    if new_level > old_level:
        flash(f"レベルアップ！ レベル{old_level} → レベル{new_level}", "success")
    
    return new_level > old_level

# 🔧 修正ポイント1: カレンダー生成関数を追加
def generate_calendar_days(year, month):
    """カレンダー日付を生成する関数（HTMLテンプレート用）"""
    # 当月の最初の日と最後の日
    first_day = date(year, month, 1)
    last_day = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year + 1, 1, 1) - timedelta(days=1)
    
    # カレンダーオブジェクト（日曜日始まり）
    cal = calendar.Calendar(firstweekday=6)
    
    calendar_days = []
    today = date.today()
    
    # ユーザーの学習記録がある日付を抽出
    user_records = dummy_store.get_user_records(current_user.id) if current_user.is_authenticated else []
    record_dates = {r.study_date for r in user_records}
    
    # 月の日付を取得（前月・次月の日付も含む）
    month_days = cal.monthdatescalendar(year, month)
    
    for week in month_days:
        for day_date in week:
            # 当月かどうか
            is_current_month = day_date.month == month
            
            # 学習記録があるか
            has_record = day_date.strftime('%Y-%m-%d') in record_dates
            
            # 今日かどうか
            is_today = day_date == today
            
            # 曜日名を日本語に変換（オプション）
            day_name = day_date.strftime('%a')
            
            calendar_days.append({
                'day': day_date.day,
                'is_padding': not is_current_month,  # 前月/次月の日付
                'full_date': day_date.strftime('%Y-%m-%d'),
                'day_name': day_name,
                'is_today': is_today,
                'has_record': has_record
            })
    
    return calendar_days

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        print(f"🔍 ログイン試行: username={username}")
        
        # ダミーデータストアからユーザーを取得
        user = dummy_store.get_user_by_username(username)
        
        if user:
            # パスワード検証
            try:
                if hasattr(user, 'password_hash') and check_password_hash(user.password_hash, password):
                    login_user(user)
                    flash('ログイン成功！', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('パスワードが正しくありません', 'error')
            except Exception as e:
                print(f"⚠️ パスワード検証エラー: {e}")
                flash('認証エラーが発生しました', 'error')
        else:
            # デバッグモード: 任意のユーザーでログイン
            if DEBUG_MODE:
                print(f"✅ デバッグモード: 新規ユーザー '{username}' を作成")
                user = dummy_store.add_user(username, password)
                login_user(user)
                flash('デバッグモード: 新規ユーザーでログインしました', 'warning')
                return redirect(url_for('dashboard'))
            else:
                flash('ユーザー名またはパスワードが正しくありません', 'error')
        
        return render_template('login.html', error='ログインに失敗しました')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        print(f"🔍 新規登録試行: username={username}")
        
        # バリデーション
        if len(username) < 3:
            flash('ユーザー名は3文字以上必要です', 'error')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('パスワードは6文字以上必要です', 'error')
            return render_template('signup.html')
        
        # 既存ユーザーチェック
        existing_user = dummy_store.get_user_by_username(username)
        if existing_user:
            flash('このユーザー名は既に使用されています', 'error')
            return render_template('signup.html')
        
        # 新規ユーザー作成
        new_user = dummy_store.add_user(username, password)
        login_user(new_user)
        
        print(f"✅ ユーザー登録成功: {username}")
        flash('アカウント登録が完了しました！', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('signup.html')

# 🔧 修正ポイント2: dashboard()関数を更新
@app.route('/dashboard')
@login_required
def dashboard():
    # カレンダー用のデータ準備
    today = datetime.now()
    year = today.year
    month = today.month
    
    # 🔧 修正: 新しいカレンダー生成関数を使用
    calendar_days = generate_calendar_days(year, month)
    
    # ユーザーのカスタム科目リスト
    custom_subjects = get_user_custom_subjects(current_user.id)
    
    # ユーザーのアバター画像URL
    avatar_path = AVATAR_OPTIONS.get(current_user.avatar, AVATAR_OPTIONS['default_cat'])
    
    # デバッグ用: カレンダーデータをコンソールに表示
    print(f"📊 カレンダーデータ生成: {len(calendar_days)}日")
    print(f"📅 {year}年{month}月")
    for i, day in enumerate(calendar_days[:10]):  # 最初の10日だけ表示
        padding = "（前/次月）" if day['is_padding'] else ""
        today_mark = "【今日】" if day['is_today'] else ""
        record_mark = "✓" if day['has_record'] else ""
        print(f"  {i:2d}: {day['full_date']} ({day['day_name']}) {day['day']:2d}日{padding}{today_mark}{record_mark}")
    
    return render_template('dashboard.html',
                         user=current_user,
                         custom_subjects=custom_subjects,
                         calendar={'year': year, 'month': month},
                         calendar_days=calendar_days,
                         avatar_path=avatar_path)

@app.route('/add_record', methods=['POST'])
@login_required
def add_record():
    subject = request.form.get('study_subject', '').strip()
    content = request.form.get('study_content', '').strip()
    difficulty = int(request.form.get('study_difficulty', 3))
    learning_time = int(request.form.get('study_time_minutes', 30))
    study_date_str = request.form.get('study_date', '')
    
    print(f"🔍 学習記録追加: subject={subject}, content={content}, time={learning_time}分")
    
    if not subject or not content:
        flash('科目と学習内容は必須です', 'error')
        return redirect(url_for('dashboard'))
    
    # 日付の処理
    if study_date_str:
        try:
            study_date = datetime.strptime(study_date_str, '%Y-%m-%d').date()
        except ValueError:
            study_date = datetime.utcnow().date()
    else:
        study_date = datetime.utcnow().date()
    
    # 学習記録を作成
    new_record = dummy_store.add_record(
        current_user.id,
        subject,
        content,
        difficulty,
        learning_time
    )
    new_record.study_date = study_date.strftime('%Y-%m-%d')
    
    # XP計算とレベルアップチェック
    base_xp = learning_time * 0.5
    difficulty_bonus = difficulty * 5
    total_xp = int(base_xp + difficulty_bonus)
    
    level_up_occurred = add_xp_and_check_level_up(current_user, total_xp, f"{subject}の学習")
    
    # ユーザーの記録数を更新
    current_user.records_count = len(dummy_store.get_user_records(current_user.id))
    
    flash(f'学習記録を追加しました！ (+{total_xp}XP)', 'success')
    return redirect(url_for('dashboard'))

@app.route('/records')
@login_required
def records():
    # ユーザーの全ての学習記録を取得
    user_records = dummy_store.get_user_records(current_user.id)
    
    # 日付でソート（新しい順）
    user_records.sort(key=lambda x: x.study_date, reverse=True)
    
    # 未復習のポイントを抽出
    unmastered_points = [record for record in user_records if not record.is_mastered]
    
    # ユーザーのカスタム科目リスト
    custom_subjects = get_user_custom_subjects(current_user.id)
    
    return render_template('records.html',
                         records=user_records,
                         unmastered_points=unmastered_points,
                         custom_subjects=custom_subjects)

@app.route('/toggle_mastery/<int:record_id>')
@login_required
def toggle_mastery(record_id):
    record = dummy_store.toggle_mastery(current_user.id, record_id)
    
    if not record:
        flash('記録が見つかりません', 'error')
        return redirect(url_for('records'))
    
    # 復習完了でXPボーナス
    if record.is_mastered:
        review_xp = record.learning_time * 0.2
        add_xp_and_check_level_up(current_user, int(review_xp), "復習完了")
        flash('復習完了！ XPボーナスを獲得しました', 'success')
    else:
        flash('未復習に戻しました', 'info')
    
    return redirect(url_for('records'))

@app.route('/delete_record/<int:record_id>')
@login_required
def delete_record(record_id):
    success = dummy_store.delete_record(current_user.id, record_id)
    
    if success:
        flash('学習記録を削除しました', 'info')
    else:
        flash('記録が見つかりません', 'error')
    
    return redirect(url_for('records'))

@app.route('/settings')
@login_required
def settings():
    # ユーザーのカスタム科目リスト
    custom_subjects = get_user_custom_subjects(current_user.id)
    
    # ユーザーの現在のアバター
    current_avatar = current_user.avatar
    
    return render_template('settings.html',
                         user=current_user,
                         custom_subjects=custom_subjects,
                         current_avatar=current_avatar,
                         avatar_options=AVATAR_OPTIONS)

@app.route('/update_avatar', methods=['POST'])
@login_required
def update_avatar():
    avatar_id = request.form.get('avatar_id', 'default_cat')
    
    if avatar_id not in AVATAR_OPTIONS:
        flash('無効なアバターIDです', 'error')
    else:
        current_user.avatar = avatar_id
        flash('アバターを更新しました！', 'success')
    
    return redirect(url_for('settings'))

@app.route('/update_username', methods=['POST'])
@login_required
def update_username():
    new_username = request.form.get('username', '').strip()
    
    if not new_username or len(new_username) < 3:
        flash('ユーザー名は3文字以上必要です', 'error')
        return redirect(url_for('settings'))
    
    # 既存ユーザーチェック（自分自身を除く）
    existing_user = dummy_store.get_user_by_username(new_username)
    if existing_user and existing_user.id != current_user.id:
        flash('このユーザー名は既に使用されています', 'error')
    else:
        current_user.username = new_username
        flash('ユーザー名を更新しました！', 'success')
    
    return redirect(url_for('settings'))

@app.route('/level_history')
@login_required
def level_history():
    # ダミーレベルアップ履歴
    dummy_history = [
        {
            'old_level': 1,
            'new_level': 2,
            'xp_earned': 150,
            'message': '数学の学習によりレベルアップ！',
            'timestamp': '2025-12-20 14:30:00'
        },
        {
            'old_level': 2,
            'new_level': 3,
            'xp_earned': 200,
            'message': '英語の復習によりレベルアップ！',
            'timestamp': '2025-12-19 10:15:00'
        }
    ]
    
    # 統計情報
    total_level_ups = len(dummy_history)
    total_xp_earned = sum([h['xp_earned'] for h in dummy_history])
    
    return render_template('level_history.html',
                         level_history=dummy_history,
                         current_level=current_user.level,
                         total_level_ups=total_level_ups,
                         total_xp_earned=total_xp_earned)

@app.route('/friends')
@login_required
def friends():
    # ダミーのフレンドデータ
    dummy_friends = [
        {'username': '山田さん', 'level': 15, 'xp_to_next': 75, 'last_activity': '2時間前', 'avatar_id': 'cat'},
        {'username': '鈴木さん', 'level': 12, 'xp_to_next': 40, 'last_activity': '1日前', 'avatar_id': 'dog'},
        {'username': '佐藤さん', 'level': 18, 'xp_to_next': 90, 'last_activity': '30分前', 'avatar_id': 'bear'},
        {'username': '田中さん', 'level': 8, 'xp_to_next': 20, 'last_activity': '3日前', 'avatar_id': 'fox'},
        {'username': '伊藤さん', 'level': 22, 'xp_to_next': 55, 'last_activity': '今日', 'avatar_id': 'rabbit'},
    ]
    
    return render_template('friends.html',
                         friends=dummy_friends,
                         avatar_options=AVATAR_OPTIONS)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ログアウトしました', 'info')
    return redirect(url_for('login'))

# ========================
# 共有機能エンドポイント（ダミー版）
# ========================

@app.route('/share/<int:record_id>')
@login_required
def share_single(record_id):
    """単一の学習記録を共有するページ（ダミー）"""
    user_records = dummy_store.get_user_records(current_user.id)
    record = next((r for r in user_records if r.id == record_id), None)
    
    if not record:
        flash("記録が見つかりません", "error")
        return redirect(url_for('records'))
    
    # 共有URLの生成
    share_url = f"{request.url_root}shared/{record_id}"
    
    return render_template('share_single.html',
                         user=current_user,
                         record=record,
                         share_url=share_url,
                         AVATAR_OPTIONS=AVATAR_OPTIONS)

@app.route('/shared/<int:record_id>')
def shared_record(record_id):
    """公開用の学習記録表示ページ（ログイン不要、ダミー）"""
    # ダミーデータから適当な記録を取得
    dummy_user = dummy_store.get_user_by_id(1)  # testユーザー
    user_records = dummy_store.get_user_records(1)
    record = user_records[0] if user_records else None
    
    if not record:
        return "記録が見つかりません", 404
    
    return render_template('share_single.html',
                         user=dummy_user,
                         record=record,
                         share_url=request.url,
                         AVATAR_OPTIONS=AVATAR_OPTIONS,
                         is_public=True)

@app.route('/share/<int:record_id>/image')
@login_required
def share_single_image(record_id):
    """学習記録を画像として共有するページ（ダミー）"""
    user_records = dummy_store.get_user_records(current_user.id)
    record = next((r for r in user_records if r.id == record_id), None)
    
    if not record:
        flash("記録が見つかりません", "error")
        return redirect(url_for('records'))
    
    # 現在の日付を取得
    current_date = datetime.now().strftime("%Y年%m月%d日")
    
    return render_template('share_single_image.html',
                         user=current_user,
                         record=record,
                         current_date=current_date,
                         AVATAR_OPTIONS=AVATAR_OPTIONS)

@app.route('/share/<int:record_id>/qr')
@login_required
def share_single_qr(record_id):
    """学習記録のQRコードを生成（ダミー）"""
    flash("QRコード機能は近日実装予定です", "info")
    return redirect(url_for('share_single', record_id=record_id))

@app.route('/debug/create_test_data')
def create_test_data():
    """デバッグ用: テストデータを作成"""
    if not current_user.is_authenticated:
        return "ログインが必要です"
    
    # テスト学習記録を追加
    subjects = ['数学', '英語', 'プログラミング', '物理', '化学']
    
    for i in range(5):
        dummy_store.add_record(
            current_user.id,
            subjects[i % len(subjects)],
            f"テスト学習内容 {i+1}",
            difficulty=(i % 5) + 1,
            learning_time=30 * (i + 1)
        )
    
    flash('テストデータを作成しました', 'success')
    return redirect(url_for('dashboard'))

@app.route('/debug/reset_user')
def debug_reset_user():
    """デバッグ用: ユーザーデータをリセット"""
    if not DEBUG_MODE:
        return "デバッグモードが無効です"
    
    logout_user()
    flash('ユーザーデータをリセットしました', 'info')
    return redirect(url_for('login'))

@app.route('/debug/calendar_data')
@login_required
def debug_calendar_data():
    """デバッグ用: カレンダーデータを表示"""
    today = datetime.now()
    year = today.year
    month = today.month
    
    calendar_days = generate_calendar_days(year, month)
    
    output = f"📅 {year}年 {month}月 カレンダーデータ（{len(calendar_days)}日）\n"
    output += "=" * 60 + "\n"
    
    for i, day in enumerate(calendar_days):
        if i % 7 == 0:
            output += f"\n週 {i//7 + 1}: "
        
        padding = "○" if day['is_padding'] else " "
        today_mark = "★" if day['is_today'] else " "
        record_mark = "✓" if day['has_record'] else " "
        
        output += f"{day['day']:2d}{padding}{today_mark}{record_mark} "
    
    output += "\n" + "=" * 60 + "\n"
    output += "凡例: ○=前/次月, ★=今日, ✓=記録あり\n"
    
    return f"<pre>{output}</pre>"

# ========================
# メイン実行部分
# ========================

def init_debug_mode():
    """デバッグモードの初期化"""
    print("=" * 50)
    print("🎮 デバッグモードで起動")
    print("📝 特徴:")
    print("  • データベース接続なし")
    print("  • メモリ内で動作")
    print("  • 再起動でデータはリセット")
    print("  • 任意のユーザー名でログイン可能")
    print("=" * 50)
    
    # デフォルトユーザーを作成
    dummy_store.add_user('test', 'test123', level=5, xp=350, avatar='cat')
    dummy_store.add_user('admin', 'debug123', level=1, xp=0, avatar='default_cat')
    
    print("✅ デフォルトユーザーを作成:")
    print(f"  1. test / test123 (レベル5, 350XP)")
    print(f"  2. admin / debug123 (レベル1, 0XP)")
    print("=" * 50)

if __name__ == '__main__':
    # デバッグモードを初期化
    init_debug_mode()
    
    # 開発サーバー起動
    print("🚀 Flaskサーバーを起動中...")
    print(f"🌐 アクセス先: http://127.0.0.1:5000")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)