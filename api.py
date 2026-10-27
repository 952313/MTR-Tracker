import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from data import MTR_NETWORK

# 定义 debug 函数
DEBUG = False  # 设置为 True 以启用调试输出，False 以禁用
debug = lambda x: DEBUG and print(x)

print_lock = Lock()

def fetch_single_station(line: str, sta_code: str, sta_info: list, index: int, total_stations: int, headers: dict) -> tuple:
    """单独获取并清洗某个车站数据的函数（含失败重试机制）"""
    api_url = "https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php"
    params = {
        "line": line,
        "sta": sta_code,
        "lang": "CH"
    }
    
    station_result = None
    status_msg = ""
    max_retries = 3  # 最大重试次数
    
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(api_url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 429:
                status_msg = "❌ 触发限流 [HTTP 429]"
                if attempt < max_retries:
                    continue
                return sta_code, None, status_msg
                
            if response.status_code != 200:
                status_msg = f"⚠️ 状态码异常 [HTTP {response.status_code}]"
                if attempt < max_retries:
                    continue
                return sta_code, None, status_msg
                
            text_content = response.text.strip()
            if not text_content or not text_content.startswith("{"):
                status_msg = "⚠️ 返回内容非JSON"
                if attempt < max_retries:
                    continue
                return sta_code, None, status_msg
                
            res_json = response.json()
            
            # 使用 debug 打印原始返回（如果需要排查的话）
            debug(f"[DEBUG] 车站 {sta_code} 第 {attempt} 次请求返回: {res_json}")
            
            if res_json.get("status") == 1:
                api_key = f"{line}-{sta_code}"
                raw_station_data = res_json.get("data", {}).get(api_key, {})
                
                station_data = {"UP": [], "DOWN": []}
                
                # 清洗 UP（上行）
                for train in raw_station_data.get("UP", []):
                    raw_time = train.get("time", "")
                    clean_time = raw_time.split(" ")[1] if " " in raw_time else raw_time
                    
                    raw_ttnt = train.get("ttnt")
                    ttnt_val = int(raw_ttnt) if raw_ttnt is not None and str(raw_ttnt).isdigit() else 0
                    
                    formatted_train = {
                        "time": clean_time,
                        "dest": train.get("dest"),
                        "plat": train.get("plat"),
                        "ttnt": ttnt_val,
                        "trainArrived": (ttnt_val == 0)
                    }
                    station_data["UP"].append(formatted_train)
                    
                # 清洗 DOWN（下行）
                for train in raw_station_data.get("DOWN", []):
                    raw_time = train.get("time", "")
                    clean_time = raw_time.split(" ")[1] if " " in raw_time else raw_time
                    
                    raw_ttnt = train.get("ttnt")
                    ttnt_val = int(raw_ttnt) if raw_ttnt is not None and str(raw_ttnt).isdigit() else 0
                    
                    formatted_train = {
                        "time": clean_time,
                        "dest": train.get("dest"),
                        "plat": train.get("plat"),
                        "ttnt": ttnt_val,
                        "trainArrived": (ttnt_val == 0)
                    }
                    station_data["DOWN"].append(formatted_train)
                
                status_msg = "✅ 成功"
                station_result = station_data
                break  # 成功则跳出重试循环
            else:
                err_info = res_json.get("error", {})
                err_code = err_info.get("errorCode", "Unknown")
                err_msg = err_info.get("errorMsg", res_json.get("message", "无列车服务"))
                
                station_result = {"UP": [], "DOWN": [], "info": f"[{err_code}] {err_msg}"}
                status_msg = f"ℹ️ 暂无服务 [{err_code}]"
                break  # 业务上的空数据（如NT-204）不需要重试，直接跳出
                
        except requests.Timeout:
            status_msg = f"❌ 超时 (第 {attempt}/{max_retries} 次)"
            if attempt < max_retries:
                continue
        except Exception as e:
            status_msg = f"❌ 异常: {e}"
            break
            
    # 线程安全地打印最终状态
    with print_lock:
        print(f"[{index}/{total_stations}] 车站: {sta_code} ({sta_info[0]}) ... {status_msg}")
        
    return sta_code, station_result, status_msg


def getTrains(line: str) -> dict:
    if line not in MTR_NETWORK:
        return {"status": False, "error": "Invalid line code"}
        
    station_dict = MTR_NETWORK[line]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    output = {
        "status": True,
        "stations": {}
    }
    
    total_stations = len(station_dict)
    print(f"🚀 开始并发获取 [{line}] 线全线数据（含自动重试机制），共计 {total_stations} 个车站...\n")
    
    max_workers = min(8, total_stations)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sta = {
            executor.submit(fetch_single_station, line, sta_code, sta_info, index, total_stations, headers): sta_code
            for index, (sta_code, sta_info) in enumerate(station_dict.items(), 1)
        }
        
        for future in as_completed(future_to_sta):
            debug(f"Processing result for station: {future_to_sta[future]}")
            sta_code, station_data, msg = future.result()
            if station_data is not None:
                output["stations"][sta_code] = station_data
                
    print(f"\n🎉 [{line}] 线所有车站数据获取完毕！")
    return output


if __name__ == "__main__":
    result = getTrains("TWL")
    
    if result["status"]:
        preview_station = "LAK"
        if preview_station in result["stations"]:
            print(f"\n✨ [{preview_station}] 站的格式化实时数据预览：")
            print(json.dumps(result["stations"][preview_station], indent=2, ensure_ascii=False))