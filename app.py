from flask import Flask, render_template, jsonify
from api import getTrains
from core import calc_twl_state

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/twl_status')
def twl_status():
    """提供给前端的 API 接口，返回当前荃湾线的实时计算状态"""
    try:
        raw_trains = getTrains("TWL")
        state = calc_twl_state(raw_trains)
        
        # 💡 核心修复：由于 state 中的 arrived_status 含有 Python 的 set 类型，
        # 需要在转 JSON 前将其转换为 list，否则 jsonify 会报错。
        if "arrived_status" in state:
            for sta_code, info in state["arrived_status"].items():
                if isinstance(info.get("plats"), set):
                    info["plats"] = list(info["plats"])
                if isinstance(info.get("green_plats"), set):
                    info["green_plats"] = list(info["green_plats"])

        return jsonify({
            "status": True,
            "data": state
        })
    except Exception as e:
        print(f"❌ 后端接口报错: {e}")  # 可以在终端看到具体错误
        return jsonify({
            "status": False,
            "error": str(e)
        })

if __name__ == '__main__':
    print("🚀 港铁实时监控网页端已启动: http://127.0.0.1:5000")
    app.run(debug=True, port=5000)