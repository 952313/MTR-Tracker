# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
    MTR Tracker
    Copyright (C) 2026 Yang Jincheng

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

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
from ISLcore import calc_isl_state

app = Flask(__name__)
DEBUG = True
debug = lambda x: DEBUG and print(x)

lock = threading.Lock()
SUPPORTED_LINES = list(MTR_NETWORK.keys())

# 各线路的最新渲染状态缓存
latest_state_cache = {line: {} for line in SUPPORTED_LINES}
# 各线路最后一次真正请求 API 的时间戳
last_fetch_time = {line: 0.0 for line in SUPPORTED_LINES}

# 🛡️ 核心防线：硬性冷却时间（单位：秒）。
# 意味着：不管有多少人、前端改得有多快，该线路的 API 在 8 秒内最多被调用一次！
COOLDOWN_SECONDS = 8.0

def calc_line_state(line: str, raw_data: dict):
    if line == "TWL":
        return calc_twl_state(raw_data)
    elif line == "KTL":
        return calc_ktl_state(raw_data)
    elif line == "ISL":
        return calc_isl_state(raw_data)
    else:
        lines_data = raw_data.get("lines", {}).get(line, raw_data)
        return {"line": line, "stations": lines_data.get("stations", {})}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    line = request.args.get("line", "TWL").upper()
    if line not in SUPPORTED_LINES:
        line = "TWL"
        
    current_time = time.time()
    
    # 使用线程锁确保高并发下的安全
    with lock:
        elapsed = current_time - last_fetch_time.get(line, 0.0)
        cached_state = latest_state_cache.get(line, {})
        
        # 💡 核心逻辑：只有当距离上次真正请求超过了冷却时间，或者缓存为空时，才允许碰 API
        if elapsed > COOLDOWN_SECONDS or not cached_state:
            debug(f"🚀 [后端防线] 允许触发 API 抓取线路: {line} (距上次请求 {elapsed:.1f}s)")
            try:
                # 真正去抓 API
                raw_data = getTrains(line)
                state = calc_line_state(line, raw_data)
                    
                # 转换 Python set 为 list
                if isinstance(state, dict) and "arrived_status" in state:
                    for sta_code, info in state["arrived_status"].items():
                        if isinstance(info.get("plats"), set):
                            info["plats"] = list(info["plats"])
                        if isinstance(info.get("green_plats"), set):
                            info["green_plats"] = list(info["green_plats"])
                            
                latest_state_cache[line] = state
                last_fetch_time[line] = current_time
                cached_state = state
            except Exception as e:
                debug(f"❌ 后端调用 {line} 报错: {e}")
        else:
            debug(f"🛡️ [后端拦截] 冷却中，直接返回内存缓存 (距上次请求 {elapsed:.1f}s)")

    return jsonify({
        "status": True,
        "fresh": True,
        "line": line,
        "data": cached_state
    })

if __name__ == '__main__':
    app.run(debug=False, port=5000)