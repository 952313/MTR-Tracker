from flask import Flask, render_template, jsonify
import time
import threading
from api import getTrains
from core import calc_twl_state

app = Flask(__name__)
DEBUG = False  # 调试开关
debug = lambda x: DEBUG and print(x)
# 全局状态变量
last_active_time = time.time()  
latest_state_cache = {}         
lock = threading.Lock()         

INACTIVE_TIMEOUT = 10           # 💡 修改为 10 秒无访问即暂停 API
data_fresh_flag = False         # 标记当前缓存是否是刚刚拉取的新鲜数据

def background_api_worker():
    """后台独立线程：负责按需调用港铁 NextTrainAPI"""
    global last_active_time, latest_state_cache, data_fresh_flag
    
    while True:
        current_time = time.time()
        idle_duration = current_time - last_active_time
        
        debug(f"Idle duration: {idle_duration}")
        # 超过 10 秒无网页访问，暂停 API
        if idle_duration > INACTIVE_TIMEOUT:
            debug(f"💤 [休眠中] 已经超过 10 秒无用户访问网页 (闲置 {int(idle_duration)}秒)，已停止访问 NextTrainAPI。")
            with lock:
                data_fresh_flag = False  # 标记数据失效/过时
            time.sleep(3)
            continue
            
        # 用户在线，开始请求 API
        try:
            debug("🚀 [API请求] 用户在线，正在请求港铁 NextTrainAPI...")
            raw_trains = getTrains("TWL")
            state = calc_twl_state(raw_trains)
            
            # 处理 Python set 转 list，防止 jsonify 报错
            if "arrived_status" in state:
                for sta_code, info in state["arrived_status"].items():
                    if isinstance(info.get("plats"), set):
                        info["plats"] = list(info["plats"])
                    if isinstance(info.get("green_plats"), set):
                        info["green_plats"] = list(info["green_plats"])
            
            with lock:
                latest_state_cache = state
                data_fresh_flag = True  # 标记已有新鲜数据
                
        except Exception as e:
            debug(f"❌ 后端调用 NextTrainAPI 报错: {e}")
            
        time.sleep(5)

@app.route('/')
def index():
    global last_active_time, data_fresh_flag
    last_active_time = time.time()  
    with lock:
        data_fresh_flag = False  # 每次用户重新打开网页时，强制初始化为“未获取新数据”
    return render_template('index.html')

@app.route('/api/twl_status')
def twl_status():
    global last_active_time
    last_active_time = time.time()  # 刷新心跳
    
    with lock:
        is_fresh = data_fresh_flag
        state_data = latest_state_cache
        
    # 如果数据不是最新拉取的（比如刚开网页、或者刚从 10 秒休眠中唤醒），告诉前端正在加载
    if not is_fresh or not state_data:
        return jsonify({
            "status": True,
            "fresh": False,
            "message": "正在获取最新数据..."
        })
        
    return jsonify({
        "status": True,
        "fresh": True,
        "data": state_data
    })

if __name__ == '__main__':
    DEBUG = True  # 调试开关
    print("🚀 港铁实时监控网页端已启动: http://127.0.0.1:5000")
    print("💡 智能防 429 机制已生效：阈值 10 秒，未访问网页时自动停止访问 NextTrainAPI。")
    
    t = threading.Thread(target=background_api_worker, daemon=True)
    t.start()
    
    app.run(debug=False, port=5000)