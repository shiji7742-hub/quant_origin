"""Flask 后端 API - 提供股票数据和图表"""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import tempfile
import threading
from datetime import datetime, time as dt_time, timedelta
from hmac import compare_digest
from urllib.parse import quote, urljoin, urlparse

import akshare as ak
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS
from werkzeug.security import check_password_hash

from config import MAINBOARD_PATTERN
from data_fetcher import (
    MarketDataError,
    get_daily_kline,
    get_intraday_data,
    get_stock_history,
    get_stock_info,
)
from new_washout_strategies import check_all_new_strategies
from screener import screen_all_stocks, screen_stocks, analyze_stock
from strategies import check_all_strategies
from trading_calendar import is_trading_day

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

load_dotenv()

DEFAULT_LOGIN_USERNAME = 'admin'
DEFAULT_LOGIN_PASSWORD_HASH = (
    'scrypt:32768:8:1$kpnBd3c7PTtU4rWP$'
    'f9d25ef3b889af055c3d4c1045a7f3d2851fa0282aa45d3331ff34167ffd3f84'
    'f6ec164b6a8b01b176fe04d7ae1b42de776a1f6717a00278ab609d4b24f03a04'
)


def get_session_hours():
    """读取登录会话时长，非法值回退到 12 小时。"""
    try:
        return max(1, int(os.getenv('LOGIN_SESSION_HOURS', '12')))
    except ValueError:
        return 12


def get_market_scan_limit():
    """限制单次全市场扫描的候选数量，避免页面长时间无响应。"""
    try:
        return max(5, int(os.getenv('MARKET_SCAN_MAX_CANDIDATES', '20')))
    except ValueError:
        return 20


def get_market_scan_workers():
    """限制扫描并发数，避免请求过载。"""
    try:
        return max(1, min(12, int(os.getenv('MARKET_SCAN_MAX_WORKERS', '6'))))
    except ValueError:
        return 6


def get_market_scan_cache_max_age_seconds():
    """市场扫描结果缓存秒数，超时后在后台刷新。"""
    try:
        return max(5, int(os.getenv('MARKET_SCAN_CACHE_MAX_AGE_SECONDS', '45')))
    except ValueError:
        return 45


def get_market_scan_retry_delay_seconds():
    """后台扫描失败后的最短重试间隔。"""
    try:
        return max(5, int(os.getenv('MARKET_SCAN_RETRY_DELAY_SECONDS', '15')))
    except ValueError:
        return 15


def get_market_scan_refresh_stale_seconds():
    """后台刷新长时间无回包时，视为僵死任务并允许重新触发。"""
    try:
        return max(60, int(os.getenv('MARKET_SCAN_REFRESH_STALE_SECONDS', '1800')))
    except ValueError:
        return 1800


def get_market_scan_auto_refresh_hour():
    """收盘后自动刷新的触发小时。"""
    try:
        return min(23, max(0, int(os.getenv('MARKET_SCAN_AUTO_REFRESH_HOUR', '15'))))
    except ValueError:
        return 15


def get_market_scan_auto_refresh_minute():
    """收盘后自动刷新的触发分钟。"""
    try:
        return min(59, max(0, int(os.getenv('MARKET_SCAN_AUTO_REFRESH_MINUTE', '5'))))
    except ValueError:
        return 5


def get_market_scan_auto_refresh_poll_seconds():
    """后台调度器的轮询周期。"""
    try:
        return max(5, int(os.getenv('MARKET_SCAN_AUTO_REFRESH_POLL_SECONDS', '30')))
    except ValueError:
        return 30


def is_truthy_arg(value):
    """解析查询参数中的布尔值。"""
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


MARKET_SCAN_CACHE_LOCK = threading.Lock()
market_scan_cache = {}
MARKET_SCAN_AUTO_REFRESH_STRATEGIES = (
    '涨停破位洗盘',
    '缩量横盘整理',
    '深度回调支撑',
    '箱体突破',
    '均线粘合发散',
    '地量见底',
)
MARKET_SCAN_SCHEDULER_LOCK = threading.Lock()
market_scan_scheduler_state = {'started': False}


def get_market_scan_cache_dir() -> str:
    """全市场扫描缓存目录。"""
    configured = os.getenv('MARKET_SCAN_CACHE_DIR', '').strip()
    if configured:
        return configured
    return os.path.join(os.path.dirname(__file__), 'cache', 'market_scan')


def ensure_market_scan_cache_dir() -> str:
    cache_dir = get_market_scan_cache_dir()
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_market_scan_cache_lockfile_path() -> str:
    return os.path.join(ensure_market_scan_cache_dir(), '.market_scan.lock')


def get_market_scan_cache_file_path(cache_key: str) -> str:
    safe_name = quote(cache_key, safe='') or '__default__'
    return os.path.join(ensure_market_scan_cache_dir(), f'{safe_name}.json')


def acquire_market_scan_file_lock(lock_file):
    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        return

    if msvcrt is not None:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b'0')
            lock_file.flush()
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        return

    raise RuntimeError('当前平台不支持全市场扫描缓存锁')


def release_market_scan_file_lock(lock_file):
    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return

    if msvcrt is not None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        return


@contextmanager
def market_scan_cache_file_lock():
    lock_path = get_market_scan_cache_lockfile_path()
    with open(lock_path, 'a+b') as lock_file:
        acquire_market_scan_file_lock(lock_file)
        try:
            yield
        finally:
            release_market_scan_file_lock(lock_file)


def load_market_scan_entry_from_disk(cache_key: str):
    path = get_market_scan_cache_file_path(cache_key)
    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r', encoding='utf-8') as fh:
            payload = json.load(fh)
            return dict(payload) if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def store_market_scan_entry(cache_key: str, entry):
    snapshot = dict(entry or {})
    path = get_market_scan_cache_file_path(cache_key)

    with tempfile.NamedTemporaryFile(
        mode='w',
        encoding='utf-8',
        dir=ensure_market_scan_cache_dir(),
        delete=False,
        suffix='.tmp',
    ) as tmp_file:
        json.dump(snapshot, tmp_file, ensure_ascii=False)
        temp_path = tmp_file.name

    os.replace(temp_path, path)

    with MARKET_SCAN_CACHE_LOCK:
        market_scan_cache[cache_key] = dict(snapshot)


def get_market_scan_auto_refresh_time() -> dt_time:
    return dt_time(
        hour=get_market_scan_auto_refresh_hour(),
        minute=get_market_scan_auto_refresh_minute(),
    )


def get_market_scan_cache_key(strategy: str) -> str:
    return strategy.strip() or '__default__'


def filter_market_scan_rows_for_strategy(rows, strategy: str):
    """只保留与当前策略匹配的扫描结果，避免串用旧缓存。"""
    if not isinstance(rows, list):
        return []

    expected_strategy = (strategy or '').strip()
    filtered_rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        row_strategy = str(row.get('策略', '') or '').strip()
        if expected_strategy and row_strategy and row_strategy != expected_strategy:
            continue

        filtered_rows.append(row)

    return filtered_rows


def get_market_scan_entry(cache_key: str):
    """读取缓存快照，避免锁泄漏到业务逻辑。"""
    disk_entry = load_market_scan_entry_from_disk(cache_key)
    if disk_entry is not None:
        with MARKET_SCAN_CACHE_LOCK:
            market_scan_cache[cache_key] = dict(disk_entry)
        return disk_entry

    with MARKET_SCAN_CACHE_LOCK:
        entry = market_scan_cache.get(cache_key)
        return dict(entry) if entry else None


def is_market_scan_entry_refreshing(entry, now: datetime | None = None) -> bool:
    """识别后台扫描是否仍然活跃，避免僵死任务长期阻塞刷新。"""
    if not entry or not entry.get('refreshing'):
        return False

    last_started_at = entry.get('last_started_at')
    if not last_started_at:
        return True

    try:
        started_at = datetime.fromisoformat(last_started_at)
    except (TypeError, ValueError):
        return False

    age_seconds = ((now or datetime.now()) - started_at).total_seconds()
    return age_seconds < get_market_scan_refresh_stale_seconds()


def is_market_scan_entry_stale(entry) -> bool:
    """判断缓存是否过期。"""
    if not entry or not entry.get('timestamp'):
        return True

    try:
        timestamp = datetime.fromisoformat(entry['timestamp'])
    except (TypeError, ValueError):
        return True

    age_seconds = (datetime.now() - timestamp).total_seconds()
    return age_seconds > get_market_scan_cache_max_age_seconds()


def can_retry_failed_market_scan(entry) -> bool:
    """失败后的后台重试节流。"""
    if not entry or not entry.get('error') or is_market_scan_entry_refreshing(entry):
        return False

    last_completed_at = entry.get('last_completed_at')
    if not last_completed_at:
        return True

    try:
        completed_at = datetime.fromisoformat(last_completed_at)
    except (TypeError, ValueError):
        return True

    age_seconds = (datetime.now() - completed_at).total_seconds()
    return age_seconds >= get_market_scan_retry_delay_seconds()


def was_market_scan_entry_updated_after_close(entry, now: datetime) -> bool:
    """判断某策略当天是否已经拿到收盘后的结果。"""
    timestamp = entry.get('timestamp') if entry else None
    if not timestamp or entry.get('error'):
        return False

    try:
        updated_at = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return False

    return (
        updated_at.date() == now.date()
        and updated_at.time() >= get_market_scan_auto_refresh_time()
    )


def should_auto_refresh_market_scan_strategy(strategy: str, now: datetime | None = None) -> bool:
    """判断某个全市场策略是否需要参与收盘后的自动刷新。"""
    current_time = now or datetime.now()
    if not is_trading_day(current_time.date()):
        return False

    if current_time.time() < get_market_scan_auto_refresh_time():
        return False

    entry = get_market_scan_entry(get_market_scan_cache_key(strategy))
    if not entry:
        return True

    if is_market_scan_entry_refreshing(entry, now=current_time):
        return False

    if was_market_scan_entry_updated_after_close(entry, current_time):
        return False

    if entry.get('last_auto_refresh_date') == current_time.date().isoformat():
        return bool(entry.get('error')) and can_retry_failed_market_scan(entry)

    return True


def get_auth_settings():
    """读取登录账号配置，优先使用环境变量。"""
    username = os.getenv('QUANT_APP_USERNAME', DEFAULT_LOGIN_USERNAME)
    password = os.getenv('QUANT_APP_PASSWORD')
    password_hash = os.getenv('QUANT_APP_PASSWORD_HASH')

    if password_hash:
        return {
            'username': username,
            'password': None,
            'password_hash': password_hash,
            'uses_default_password': False
        }

    if password:
        return {
            'username': username,
            'password': password,
            'password_hash': None,
            'uses_default_password': False
        }

    return {
        'username': username,
        'password': None,
        'password_hash': DEFAULT_LOGIN_PASSWORD_HASH,
        'uses_default_password': True
    }


AUTH_SETTINGS = get_auth_settings()

def convert_to_serializable(obj):
    """转换 numpy 类型为 Python 原生类型"""
    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(i) for i in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    return obj


def is_authenticated():
    """当前请求是否已经登录。"""
    return session.get('authenticated') is True


def is_safe_redirect_url(target):
    """限制登录后的跳转目标只能回到本站。"""
    if not target:
        return False

    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def get_next_target():
    """获取登录后应该跳转回的页面。"""
    next_target = request.args.get('next') or request.form.get('next')
    if next_target and is_safe_redirect_url(next_target):
        return next_target
    return url_for('workspace')


def get_current_target():
    """获取当前请求地址，用于未登录时回跳。"""
    if request.query_string:
        return request.full_path.rstrip('?')
    return request.path


def get_current_git_commit():
    """返回当前仓库 HEAD commit，失败时降级为 unknown。"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='ignore',
        )
        return result.stdout.strip()
    except Exception:
        return 'unknown'


def validate_login(username, password):
    """校验用户名和密码。"""
    if not compare_digest(username or '', AUTH_SETTINGS['username']):
        return False

    if AUTH_SETTINGS['password_hash']:
        try:
            return check_password_hash(AUTH_SETTINGS['password_hash'], password or '')
        except ValueError:
            return False

    return compare_digest(password or '', AUTH_SETTINGS['password'] or '')

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.getenv(
    'FLASK_SECRET_KEY',
    'quant-ai-local-secret-change-this'
)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=get_session_hours())
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = (
    os.getenv('SESSION_COOKIE_SECURE', 'false').lower() in {'1', 'true', 'yes'}
)
CORS(app, supports_credentials=True)

if AUTH_SETTINGS['uses_default_password']:
    print(
        'Warning: QUANT_APP_PASSWORD / QUANT_APP_PASSWORD_HASH 未设置，'
        '当前使用默认开发账号 admin 和默认口令。'
    )


@app.context_processor
def inject_auth_state():
    """向模板注入当前登录状态。"""
    return {
        'is_authenticated': is_authenticated(),
        'current_user': session.get('username')
    }


@app.before_request
def enforce_login():
    """未登录时拦截受保护页面和 API。"""
    public_endpoints = {'static', 'landing', 'login', 'logout', 'healthz'}

    if request.endpoint is None or request.endpoint in public_endpoints:
        return None

    if is_authenticated():
        return None

    next_target = get_current_target()

    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': '请先登录',
            'login_required': True,
            'login_url': url_for('login', next=next_target)
        }), 401

    return redirect(url_for('login', next=next_target))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页和登录提交。"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        next_target = get_next_target()

        if validate_login(username, password):
            session.clear()
            session.permanent = True
            session['authenticated'] = True
            session['username'] = username
            return redirect(next_target)

        return render_template(
            'login.html',
            error='用户名或密码错误',
            next_target=next_target,
            username=username
        ), 401

    if is_authenticated():
        return redirect(get_next_target())

    return render_template(
        'login.html',
        error=None,
        next_target=get_next_target(),
        username=''
    )


@app.route('/logout')
def logout():
    """退出登录并清理会话。"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/healthz')
def healthz():
    """对部署脚本暴露的轻量健康检查。"""
    return jsonify({
        'status': 'ok',
        'service': 'quant-ai',
        'version': get_current_git_commit(),
        'time': datetime.now().isoformat()
    })

@app.route('/')
def landing():
    """落地页 - 策略介绍"""
    return render_template('landing.html')

@app.route('/workspace')
def workspace():
    """工作台 - 双门选择"""
    return render_template('home.html')

@app.route('/market')
def market_page():
    """全市场扫描页面"""
    return render_template('market.html')

@app.route('/sector')
def sector_page():
    """强势板块扫描页面"""
    return render_template('sector.html')

@app.route('/dashboard')
def dashboard():
    """数据大屏（旧版）"""
    return render_template('dashboard.html')

@app.route('/simple')
def simple_select():
    """简洁版选股页面"""
    return render_template('simple_select.html')

@app.route('/api/scan_by_style', methods=['GET'])
def scan_by_style():
    """根据投资风格扫描股票"""
    try:
        style = request.args.get('style', 'short')
        
        # 定义不同风格对应的策略
        style_strategies = {
            'short': {
                'name': '短线交易',
                'strategies': ['涨停破位洗盘', '箱体突破', '均线粘合发散'],
                'desc': '快进快出，追求短期收益'
            },
            'medium': {
                'name': '波段操作',
                'strategies': ['深度回调支撑', '缩量横盘整理', '均线金叉', '缩量回踩'],
                'desc': '把握中期趋势'
            },
            'long': {
                'name': '中长线投资',
                'strategies': ['地量见底', '底部放量', '突破平台'],
                'desc': '价值投资理念'
            }
        }
        
        if style not in style_strategies:
            return jsonify({'success': False, 'error': '无效的投资风格'}), 400
        
        style_info = style_strategies[style]
        all_results = []
        candidates = screen_all_stocks()
        
        # 扫描每个策略
        for strategy in style_info['strategies']:
            try:
                results = scan_by_strategy(strategy, candidates=candidates)
                for stock in results:
                    stock['策略'] = strategy
                    all_results.append(stock)
            except:
                continue
        
        # 去重（同一只股票可能符合多个策略）
        seen = set()
        unique_results = []
        for stock in all_results:
            code = stock.get('代码', '')
            if code and code not in seen:
                seen.add(code)
                unique_results.append(stock)
        
        # 转换为前端需要的格式
        formatted_results = []
        for stock in unique_results[:30]:  # 限制返回30只
            formatted_results.append({
                'code': stock.get('代码', ''),
                'name': stock.get('名称', ''),
                'price': float(stock.get('最新价', 0)),
                'change': float(stock.get('涨跌幅', 0)),
                'strategy': stock.get('策略', '')
            })
        
        return jsonify({
            'success': True,
            'style': style,
            'style_name': style_info['name'],
            'data': formatted_results,
            'count': len(formatted_results),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/daily_recommendations', methods=['GET'])
def get_daily_recommendations():
    """获取每日推荐股票（从JSON文件读取）"""
    import os
    
    try:
        json_path = os.path.join(os.path.dirname(__file__), 'daily_recommendations.json')
        
        if not os.path.exists(json_path):
            return jsonify({
                'success': False,
                'error': '数据文件不存在，请联系管理员更新'
            }), 404
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify({
            'success': True,
            'data': {
                'short': data.get('short', []),
                'medium': data.get('medium', []),
                'long': data.get('long', [])
            },
            'update_time': data.get('update_time', '未知'),
            'date': data.get('date', ''),
            'note': data.get('note', '')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scan', methods=['GET'])
def scan_stocks():
    """扫描筛选股票，支持同步扫描或后台刷新模式。"""
    strategy = request.args.get('strategy', '').strip()
    async_mode = is_truthy_arg(request.args.get('async'))
    force_refresh = is_truthy_arg(request.args.get('force'))

    if async_mode:
        return get_market_scan_async_response(strategy, force_refresh=force_refresh)

    try:
        return jsonify(perform_market_scan(strategy))
    except MarketDataError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 503
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def perform_market_scan(strategy: str):
    """执行一次完整的市场扫描。"""
    if not strategy:
        candidates = screen_stocks()
        results = []
        for symbol in candidates:
            data = analyze_stock(symbol)
            if data:
                results.append(data)
        return {
            'success': True,
            'data': convert_to_serializable(results),
            'count': len(results),
            'scanned_count': len(candidates),
            'timestamp': datetime.now().isoformat()
        }

    scanned_count = None

    if strategy not in {'潜力板块+涨停洗盘', '潜力板块'}:
        candidates = screen_stocks(limit=get_market_scan_limit())
        scanned_count = len(candidates)
        results = scan_by_strategy(strategy, candidates=candidates)
    else:
        results = scan_by_strategy(strategy)
        scanned_count = len(results)

    return {
        'success': True,
        'strategy': strategy,
        'data': convert_to_serializable(results),
        'count': len(results),
        'scanned_count': scanned_count,
        'timestamp': datetime.now().isoformat()
    }


def set_market_scan_error(cache_key: str, strategy: str, error_message: str):
    """记录后台扫描失败，但尽量保留上一版结果。"""
    completed_at = datetime.now().isoformat()

    with market_scan_cache_file_lock():
        current = get_market_scan_entry(cache_key) or {}
        store_market_scan_entry(cache_key, {
            'strategy': strategy,
            'data': current.get('data', []),
            'count': current.get('count', len(current.get('data', []))),
            'scanned_count': current.get('scanned_count', 0),
            'timestamp': current.get('timestamp'),
            'refreshing': False,
            'error': error_message,
            'last_started_at': current.get('last_started_at'),
            'last_completed_at': completed_at,
            'last_auto_refresh_date': current.get('last_auto_refresh_date'),
        })


def run_market_scan_refresh(cache_key: str, strategy: str):
    """后台刷新市场扫描缓存。"""
    try:
        payload = perform_market_scan(strategy)
        with market_scan_cache_file_lock():
            current = get_market_scan_entry(cache_key) or {}
            store_market_scan_entry(cache_key, {
                'strategy': strategy,
                'data': payload.get('data', []),
                'count': payload.get('count', len(payload.get('data', []))),
                'scanned_count': payload.get('scanned_count', 0),
                'timestamp': payload.get('timestamp'),
                'refreshing': False,
                'error': None,
                'last_started_at': current.get('last_started_at'),
                'last_completed_at': payload.get('timestamp'),
                'last_auto_refresh_date': current.get('last_auto_refresh_date'),
            })
    except Exception as exc:
        set_market_scan_error(cache_key, strategy, str(exc))


def start_market_scan_refresh(
    strategy: str,
    force_refresh: bool = False,
    trigger_source: str = 'manual',
    current_time: datetime | None = None,
) -> bool:
    """如有必要则启动后台扫描线程。"""
    cache_key = get_market_scan_cache_key(strategy)
    started_at = current_time or datetime.now()

    with market_scan_cache_file_lock():
        current = get_market_scan_entry(cache_key)
        if current and is_market_scan_entry_refreshing(current, now=started_at):
            return False

        entry = dict(current or {})
        entry['strategy'] = strategy
        entry['refreshing'] = True
        entry['last_started_at'] = started_at.isoformat()
        entry['data'] = filter_market_scan_rows_for_strategy(entry.get('data', []), strategy)
        entry['count'] = len(entry['data'])
        entry['scanned_count'] = entry.get('scanned_count', 0)

        if force_refresh or not entry['data']:
            entry['error'] = None

        if trigger_source == 'scheduled':
            entry['last_auto_refresh_date'] = started_at.date().isoformat()

        store_market_scan_entry(cache_key, entry)

    threading.Thread(
        target=run_market_scan_refresh,
        args=(cache_key, strategy),
        daemon=True,
    ).start()
    return True


def trigger_market_scan_auto_refresh(now: datetime | None = None) -> int:
    """收盘后按策略触发自动刷新；每个策略只在需要时启动一次。"""
    current_time = now or datetime.now()
    started = 0

    for strategy in MARKET_SCAN_AUTO_REFRESH_STRATEGIES:
        if not should_auto_refresh_market_scan_strategy(strategy, now=current_time):
            continue

        if start_market_scan_refresh(
            strategy,
            force_refresh=True,
            trigger_source='scheduled',
            current_time=current_time,
        ):
            started += 1

    return started


def run_market_scan_auto_refresh_scheduler(stop_event: threading.Event | None = None):
    """后台轮询收盘时点，自动触发一次全市场策略刷新。"""
    scheduler_stop_event = stop_event or threading.Event()

    while not scheduler_stop_event.wait(get_market_scan_auto_refresh_poll_seconds()):
        try:
            trigger_market_scan_auto_refresh()
        except Exception as exc:
            print(f"市场扫描自动刷新失败: {exc}")


def ensure_market_scan_auto_refresh_scheduler_started() -> bool:
    """确保后台调度器只在当前进程中启动一次。"""
    with MARKET_SCAN_SCHEDULER_LOCK:
        if market_scan_scheduler_state['started']:
            return False

        market_scan_scheduler_state['started'] = True

    threading.Thread(
        target=run_market_scan_auto_refresh_scheduler,
        daemon=True,
        name='market-scan-auto-refresh',
    ).start()
    return True


def get_market_scan_async_response(strategy: str, force_refresh: bool = False):
    """返回后台扫描模式下的结果。"""
    cache_key = get_market_scan_cache_key(strategy)
    entry = get_market_scan_entry(cache_key)
    has_cached_result = bool(entry and entry.get('timestamp'))
    should_refresh = (
        force_refresh
        or entry is None
        or (has_cached_result and is_market_scan_entry_stale(entry))
        or can_retry_failed_market_scan(entry)
    )

    if should_refresh:
        start_market_scan_refresh(strategy, force_refresh=force_refresh)
        entry = get_market_scan_entry(cache_key)

    if entry:
        cached_data = filter_market_scan_rows_for_strategy(entry.get('data', []), strategy)
        cached_count = len(cached_data)

        if cached_data:
            message = None
            if is_market_scan_entry_refreshing(entry):
                message = '正在后台刷新，当前展示上次扫描结果'
            elif entry.get('error'):
                message = f"最近一次刷新失败，当前展示上次结果：{entry['error']}"

            return jsonify({
                'success': True,
                'strategy': strategy,
                'data': cached_data,
                'count': cached_count,
                'scanned_count': entry.get('scanned_count', 0),
                'timestamp': entry.get('timestamp'),
                'cached': True,
                'processing': is_market_scan_entry_refreshing(entry),
                'message': message,
                'last_started_at': entry.get('last_started_at'),
                'last_completed_at': entry.get('last_completed_at')
            })

    if entry and entry.get('data'):
        message = None
        if is_market_scan_entry_refreshing(entry):
            message = '正在后台刷新，请稍候几秒后自动刷新'
        elif entry.get('error'):
            message = f"最近一次刷新结果与当前策略不一致：{entry['error']}"

        return jsonify({
            'success': True,
            'strategy': strategy,
            'data': [],
            'count': 0,
            'scanned_count': entry.get('scanned_count', 0),
            'timestamp': entry.get('timestamp'),
            'cached': True,
            'processing': is_market_scan_entry_refreshing(entry),
            'message': message,
            'last_started_at': entry.get('last_started_at'),
            'last_completed_at': entry.get('last_completed_at')
        })

    if entry and entry.get('error') and not is_market_scan_entry_refreshing(entry):
        return jsonify({
            'success': False,
            'strategy': strategy,
            'error': entry['error'],
            'cached': False,
            'processing': False,
            'last_started_at': entry.get('last_started_at'),
            'last_completed_at': entry.get('last_completed_at')
        }), 503

    return jsonify({
        'success': True,
        'strategy': strategy,
        'data': [],
        'count': 0,
        'scanned_count': entry.get('scanned_count', 0) if entry else 0,
        'timestamp': entry.get('timestamp') if entry else None,
        'cached': False,
        'processing': True,
        'message': '正在后台扫描，请稍候几秒后自动刷新',
        'last_started_at': entry.get('last_started_at') if entry else None,
        'last_completed_at': entry.get('last_completed_at') if entry else None
    })

def scan_by_strategy(strategy_name, candidates=None):
    """按策略扫描股票"""
    from strategies import (
        strategy_volume_breakout, strategy_ma_golden_cross, strategy_macd_divergence,
        strategy_pullback_support, strategy_platform_breakout, strategy_bottom_volume,
        strategy_three_red, strategy_limit_up_washout
    )
    from new_washout_strategies import (
        strategy_shrink_consolidation, strategy_deep_pullback_support,
        strategy_box_breakout, strategy_ma_convergence_divergence, strategy_volume_bottom
    )
    
    # 组合策略特殊处理
    if strategy_name == '潜力板块+涨停洗盘':
        return scan_combined_strategy()
    
    # 潜力板块扫描
    if strategy_name == '潜力板块':
        return scan_potential_sectors_api()
    
    # 策略映射
    strategy_map = {
        # 基础策略
        '放量突破': strategy_volume_breakout,
        '均线金叉': strategy_ma_golden_cross,
        'MACD底背离': strategy_macd_divergence,
        '缩量回踩': strategy_pullback_support,
        '突破平台': strategy_platform_breakout,
        '底部放量': strategy_bottom_volume,
        '三连阳': strategy_three_red,
        '涨停破位洗盘': strategy_limit_up_washout,
        # 新洗盘策略
        '缩量横盘整理': strategy_shrink_consolidation,
        '深度回调支撑': strategy_deep_pullback_support,
        '箱体突破': strategy_box_breakout,
        '均线粘合发散': strategy_ma_convergence_divergence,
        '地量见底': strategy_volume_bottom,
    }
    
    if strategy_name not in strategy_map:
        return []
    
    strategy_func = strategy_map[strategy_name]
    
    # 获取候选股票
    if candidates is None:
        candidates = screen_stocks()

    def scan_one(index, symbol):
        try:
            df = get_stock_history(symbol, days=70)
            if df is None or len(df) < 30:
                return index, None

            # 检测策略
            try:
                if strategy_name == '涨停破位洗盘':
                    result = strategy_func(df, relaxed=True)
                else:
                    result = strategy_func(df)
            except Exception as e:
                print(f"策略检测失败 {symbol}: {e}")
                return index, None
            
            if result.get('触发'):
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                return index, {
                    '代码': symbol,
                    '最新价': float(latest['收盘']),
                    '涨跌幅': round((latest['收盘'] - prev['收盘']) / prev['收盘'] * 100, 2),
                    '策略': strategy_name,
                    '说明': result.get('说明', ''),
                    '条件': result.get('条件', '')
                }
        except Exception as e:
            print(f"获取数据失败 {symbol}: {e}")
        return index, None

    results = []
    max_workers = min(get_market_scan_workers(), len(candidates)) if candidates else 1

    if max_workers <= 1:
        for index, symbol in enumerate(candidates):
            _, matched = scan_one(index, symbol)
            if matched:
                results.append((index, matched))
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(scan_one, index, symbol)
                for index, symbol in enumerate(candidates)
            ]
            for future in futures:
                index, matched = future.result()
                if matched:
                    results.append((index, matched))

    results.sort(key=lambda item: item[0])
    return [item[1] for item in results]

def scan_combined_strategy():
    """扫描组合策略：潜力板块+涨停洗盘"""
    from combined_strategy import get_potential_sectors, get_sector_stocks, check_limit_up_washout
    
    results = []
    sectors = get_potential_sectors()
    
    for sector in sectors:
        stocks = get_sector_stocks(sector)
        if not stocks:
            continue
        
        for stock in stocks:
            code = stock['代码']
            name = stock['名称']
            
            match, _ = check_limit_up_washout(code, name, relaxed=True)
            
            if match:
                results.append({
                    '代码': code,
                    '名称': name,
                    '最新价': float(stock.get('涨跌幅', 0)),
                    '涨跌幅': float(stock.get('涨跌幅', 0)),
                    '策略': '潜力板块+涨停洗盘',
                    '板块': sector,
                    '说明': match.get('说明', ''),
                    '条件': match.get('条件', '')
                })
    
    return results

def scan_potential_sectors_api():
    """扫描潜力板块"""
    from scan_potential_sectors import scan_potential_sectors, get_all_sectors
    
    try:
        results = scan_potential_sectors(num_sectors=50)
        
        # 转换为前端需要的格式
        formatted = []
        for r in results:
            formatted.append({
                '代码': r.get('板块代码', ''),
                '名称': r.get('板块名称', ''),
                '最新价': r.get('当日涨幅', 0),
                '涨跌幅': r.get('当日涨幅', 0),
                '策略': '潜力板块',
                '说明': f"爆发日:{r.get('surge_date', '')} 回撤:{r.get('drawdown', 0)}%",
                '条件': f"近15日:{r.get('recent_15d', 0)}% 近5日:{r.get('recent_5d', 0)}%"
            })
        return formatted
    except Exception as e:
        print(f"潜力板块扫描失败: {e}")
        return []

@app.route('/api/stock/<symbol>/intraday', methods=['GET'])
def get_intraday(symbol):
    """获取分时数据"""
    try:
        df = get_intraday_data(symbol)
        if df is None or len(df) == 0:
            return jsonify({'success': False, 'error': '无分时数据'}), 404
        
        # 转换为列表格式
        data = []
        for _, row in df.iterrows():
            data.append({
                'time': str(row.get('时间', ''))[-8:],  # 只取时间部分
                'price': float(row.get('收盘', 0)),
                'volume': int(row.get('成交量', 0)),
                'amount': float(row.get('成交额', 0))
            })
        
        return jsonify({
            'success': True,
            'symbol': symbol,
            'data': data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stock/<symbol>/kline', methods=['GET'])
def get_kline(symbol):
    """获取日K线数据"""
    try:
        df = get_daily_kline(symbol, days=30)
        if df is None or len(df) == 0:
            return jsonify({'success': False, 'error': '无K线数据'}), 404
        
        # 转换为列表格式
        data = []
        for _, row in df.iterrows():
            data.append({
                'date': str(row.get('日期', '')),
                'open': float(row.get('开盘', 0)),
                'high': float(row.get('最高', 0)),
                'low': float(row.get('最低', 0)),
                'close': float(row.get('收盘', 0)),
                'volume': int(row.get('成交量', 0))
            })
        
        return jsonify({
            'success': True,
            'symbol': symbol,
            'data': data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stock/<symbol>/info', methods=['GET'])
def get_info(symbol):
    """获取股票基本信息"""
    try:
        info = get_stock_info(symbol)
        return jsonify({
            'success': True,
            'symbol': symbol,
            'data': info
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    """获取所有策略列表"""
    try:
        strategies = {
            "洗盘策略": [
                {"name": "涨停破位洗盘", "desc": "涨停后跌破最低价再大阳反包（核心策略）", "type": "核心"},
                {"name": "缩量横盘整理", "desc": "上涨后缩量横盘，主力洗盘", "type": "洗盘"},
                {"name": "深度回调支撑", "desc": "回调到MA20/MA30支撑位企稳", "type": "回调"},
                {"name": "箱体突破", "desc": "震荡后放量突破箱体上沿", "type": "突破"},
                {"name": "均线粘合发散", "desc": "MA5/10/20粘合后放量向上发散", "type": "趋势"},
                {"name": "地量见底", "desc": "地量后放量阳线，抛压枯竭", "type": "抄底"}
            ],
            "板块策略": [
                {"name": "潜力板块", "desc": "早期爆发→回撤洗盘→企稳的板块", "type": "板块"},
                {"name": "潜力板块+涨停洗盘", "desc": "在潜力板块中找涨停破位洗盘的个股", "type": "组合"}
            ]
        }
        return jsonify({
            'success': True,
            'data': strategies,
            'total': sum(len(v) for v in strategies.values())
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/potential-sectors', methods=['GET'])
def get_potential_sectors_api():
    """获取潜力板块列表（使用缓存）"""
    global sector_cache
    
    try:
        # 如果有缓存直接返回
        if sector_cache.get('sectors'):
            return jsonify({
                'success': True,
                'data': sector_cache['sectors'],
                'count': len(sector_cache['sectors']),
                'cached': True
            })
        
        from scan_potential_sectors import scan_potential_sectors
        
        results = scan_potential_sectors(num_sectors=30)
        
        formatted = []
        for r in results[:10]:
            formatted.append({
                'name': r.get('板块名称', ''),
                'code': r.get('板块代码', ''),
                'change': r.get('当日涨幅', 0),
                'drawdown': r.get('drawdown', 0),
                'surge_date': r.get('surge_date', ''),
                'recent_15d': r.get('recent_15d', 0),
                'recent_5d': r.get('recent_5d', 0)
            })
        
        # 缓存结果
        sector_cache['sectors'] = formatted
        
        return jsonify({
            'success': True,
            'data': formatted,
            'count': len(formatted)
        })
    except Exception as e:
        print(f"潜力板块扫描失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 全局缓存
sector_cache = {
    'sectors': [],
    'stocks': {}  # 按板块名缓存个股
}


def get_sector_strategy_map():
    """返回板块个股扫描使用的策略映射。"""
    from strategies import strategy_limit_up_washout
    from new_washout_strategies import (
        strategy_shrink_consolidation, strategy_deep_pullback_support,
        strategy_box_breakout, strategy_ma_convergence_divergence, strategy_volume_bottom
    )

    return {
        '涨停破位洗盘': strategy_limit_up_washout,
        '缩量横盘整理': strategy_shrink_consolidation,
        '深度回调支撑': strategy_deep_pullback_support,
        '箱体突破': strategy_box_breakout,
        '均线粘合发散': strategy_ma_convergence_divergence,
        '地量见底': strategy_volume_bottom,
    }


def get_sector_candidate_stocks(sector_name: str, sector_code: str = ''):
    """获取板块候选个股，统一走带回退的成分股接口。"""
    from scan_potential_sectors import get_sector_constituents

    df = get_sector_constituents(sector_name, sector_code=sector_code)
    if df is None or df.empty:
        return []

    normalized = df.copy()
    normalized['代码'] = (
        normalized['代码']
        .astype(str)
        .str.extract(r'(\d{6})', expand=False)
        .fillna('')
    )
    normalized['名称'] = normalized['名称'].astype(str).str.strip()
    normalized = normalized[normalized['代码'].str.match(MAINBOARD_PATTERN, na=False)]
    normalized = normalized[~normalized['名称'].str.contains('ST', na=False)]
    return normalized[['代码', '名称']].drop_duplicates('代码').to_dict('records')


def scan_sector_candidate_stocks(stocks, strategy_name: str, sector_name: str, max_candidates: int | None = None):
    """对板块成分股执行策略扫描。"""
    strategy_map = get_sector_strategy_map()
    strategy_func = strategy_map.get(strategy_name, strategy_map['涨停破位洗盘'])

    results = []
    candidates = stocks[:max_candidates] if max_candidates else stocks
    for stock in candidates:
        try:
            symbol = str(stock.get('代码', '')).zfill(6)
            name = stock.get('名称', '')
            if not symbol or not name:
                continue

            hist = get_stock_history(symbol, days=70)
            if hist is None or len(hist) < 30:
                continue

            hist = hist.tail(70)
            if strategy_name == '涨停破位洗盘':
                result = strategy_func(hist, relaxed=True)
            else:
                result = strategy_func(hist)

            if result.get('触发'):
                latest = hist.iloc[-1]
                prev = hist.iloc[-2]
                results.append({
                    '代码': symbol,
                    '名称': name,
                    '最新价': float(latest['收盘']),
                    '涨跌幅': round((latest['收盘'] - prev['收盘']) / prev['收盘'] * 100, 2),
                    '策略': strategy_name,
                    '板块': sector_name,
                    '说明': result.get('说明', ''),
                    '条件': result.get('条件', '')
                })
        except Exception:
            continue

    return convert_to_serializable(results)

@app.route('/api/scan-sector', methods=['GET'])
def scan_sector_stocks():
    """扫描指定板块的个股（使用缓存）"""
    global sector_cache
    
    try:
        sector_name = request.args.get('sector', '')
        strategy_name = request.args.get('strategy', '涨停破位洗盘')
        
        if not sector_name:
            return jsonify({'success': False, 'error': '请指定板块'}), 400
        
        cache_key = f"{sector_name}_{strategy_name}"
        
        # 如果有缓存直接返回
        if cache_key in sector_cache['stocks']:
            return jsonify({
                'success': True,
                'data': sector_cache['stocks'][cache_key],
                'sector': sector_name,
                'strategy': strategy_name,
                'count': len(sector_cache['stocks'][cache_key]),
                'cached': True
            })
        
        stocks = get_sector_candidate_stocks(sector_name)
        if not stocks:
            return jsonify({'success': False, 'error': '获取板块成分股失败'}), 404
        results = scan_sector_candidate_stocks(stocks, strategy_name, sector_name, max_candidates=30)
        sector_cache['stocks'][cache_key] = results
        
        return jsonify({
            'success': True,
            'data': results,
            'sector': sector_name,
            'strategy': strategy_name,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/prescan', methods=['POST'])
def prescan_all():
    """预扫描所有潜力板块的个股"""
    global sector_cache
    
    try:
        from scan_potential_sectors import scan_potential_sectors
        
        # 先扫描潜力板块
        results = scan_potential_sectors(num_sectors=30)
        
        formatted = []
        for r in results[:8]:
            formatted.append({
                'name': r.get('板块名称', ''),
                'code': r.get('板块代码', ''),
                'change': r.get('当日涨幅', 0),
                'drawdown': r.get('drawdown', 0),
                'surge_date': r.get('surge_date', ''),
                'recent_15d': r.get('recent_15d', 0),
                'recent_5d': r.get('recent_5d', 0)
            })
        
        sector_cache['sectors'] = formatted
        
        # 预扫描每个板块的个股
        for sector in formatted:
            sector_name = sector['name']
            try:
                stocks = get_sector_candidate_stocks(sector_name, sector.get('code', ''))
                if not stocks:
                    continue
                cache_key = f"{sector_name}_涨停破位洗盘"
                sector_cache['stocks'][cache_key] = scan_sector_candidate_stocks(
                    stocks,
                    '涨停破位洗盘',
                    sector_name,
                    max_candidates=20
                )
                
            except Exception as e:
                print(f"预扫描板块 {sector_name} 失败: {e}")
                continue
        
        return jsonify({
            'success': True,
            'sectors': len(formatted),
            'message': '预扫描完成'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stock/<symbol>/strategies', methods=['GET'])
def check_stock_strategies(symbol):
    """检测单只股票的所有策略"""
    try:
        # 获取股票数据
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        if df is None or len(df) < 30:
            return jsonify({'success': False, 'error': '数据不足'}), 404
        
        df = df.tail(70)
        
        # 检测基础策略
        basic_results = check_all_strategies(df)
        
        # 检测新策略
        new_results = check_all_new_strategies(df)
        
        # 合并结果
        all_results = {}
        triggered = []
        
        for name, result in basic_results.items():
            all_results[name] = convert_to_serializable(result)
            if result.get('触发'):
                triggered.append(name)
        
        for name, result in new_results.items():
            all_results[name] = convert_to_serializable(result)
            if result.get('触发'):
                triggered.append(name)
        
        return jsonify({
            'success': True,
            'symbol': symbol,
            'data': all_results,
            'triggered': triggered,
            'triggered_count': len(triggered)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ != '__main__' or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    ensure_market_scan_auto_refresh_scheduler_started()

if __name__ == '__main__':
    ensure_market_scan_auto_refresh_scheduler_started()
    app.run(debug=True, port=5000)
