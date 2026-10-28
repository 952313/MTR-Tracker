# ==============================================================================
# app.py (支持 TWL, KTL, ISL 的 Flask 后端)
# ==============================================================================
from flask import Flask, render_template, jsonify, request
import time
import threading
from api import getTrains
from data import MTR_NETWORK
from TWLcore import calc_twl_state
from KTLcore import calc_ktl_state
from ISLcore import calc_isl_state  # 👈 1. 导入港岛线核心计算模块

app = Flask(__name__)
DEBUG = False
debug = lambda x: DEBUG and print(x)

# 线程安全锁与独立状态缓存
lock = threading.Lock()

# 动态获取 MTR_NETWORK 中的所有线路代码作为支持列表
SUPPORTED_LINES = list(MTR_NETWORK.keys())

# 初始化各线路独立缓存与最后访问时间戳（心跳）
latest_state_cache = {line: {} for line in SUPPORTED_LINES}         
active_lines_status = {line: 0.0 for line in SUPPORTED_LINES}

INACTIVE_TIMEOUT = 10           

def calc_line_state(line: str, raw_data: dict):
    """根据线路代码分发到对应的计算核心模块"""
    if line == "TWL":
        return calc_twl_state(raw_data)
    elif line == "KTL":
        return calc_ktl_state(raw_data)
    elif line == "ISL":
        return calc_isl_state(raw_data)  # 👈 2. 增加 ISL 分发逻辑
    else:
        # 针对暂未写专属核心的线路，先返回原始清洗数据或空字典
        lines_data = raw_data.get("lines", {}).get(line, raw_data)
        return {"line": line, "stations": lines_data.get("stations", {})}

def background_api_worker():
    """后台独立线程：轮询被激活且近期有用户访问的线路，防止 429 且多线程并发安全"""
    while True:
        current_time = time.time()
        
        # 遍历所有支持的线路进行状态检查与按需抓取
        for line in SUPPORTED_LINES:
            with lock:
                last_access = active_lines_status.get(line, 0)
            
            # 如果超过 10 秒无人访问该线路，则暂停该线路的 API 请求（防止触发 429）
            if current_time - last_access > INACTIVE_TIMEOUT:
                continue
                
            try:
                debug(f"🚀 [API请求] 正在抓取线路: {line}")
                raw_data = getTrains(line)
                
                with lock:
                    state = calc_line_state(line, raw_data)
                        
                    # 统一处理 Python set 转 list，防止 jsonify 报错
                    if isinstance(state, dict) and "arrived_status" in state:
                        for sta_code, info in state["arrived_status"].items():
                            if isinstance(info.get("plats"), set):
                                info["plats"] = list(info["plats"])
                            if isinstance(info.get("green_plats"), set):
                                info["green_plats"] = list(info["green_plats"])
                                
                    latest_state_cache[line] = state
            except Exception as e:
                debug(f"❌ 后端调用 {line} 报错: {e}")
                
        time.sleep(10) # 💡 严格设定轮询间隔为 10 秒

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/switch_line', methods=['POST'])
def switch_line():
    data = request.get_json()
    line = data.get("line", "").upper()
    if line in SUPPORTED_LINES:
        with lock:
            active_lines_status[line] = time.time() # 激活该线路心跳
        return jsonify({"status": True, "active_line": line})
    return jsonify({"status": False, "message": "Invalid line"})

@app.route('/api/status')
def get_status():
    line = request.args.get("line", "TWL").upper()
    if line not in SUPPORTED_LINES:
        line = "TWL"
        
    with lock:
        active_lines_status[line] = time.time() # 刷新对应线路的心跳
        state_data = latest_state_cache.get(line, {})
        
    if not state_data:
        return jsonify({
            "status": True,
            "fresh": False,
            "line": line,
            "message": "正在获取最新数据..."
        })
        
    return jsonify({
        "status": True,
        "fresh": True,
        "line": line,
        "data": state_data
    })

print("🚀 港铁实时监控后台多线路轮询线程初始化...")
t = threading.Thread(target=background_api_worker, daemon=True)
t.start()

if __name__ == '__main__':
    app.run(debug=False, port=5000)