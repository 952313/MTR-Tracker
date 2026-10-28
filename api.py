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

import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, local
from requests.adapters import HTTPAdapter
from data import MTR_NETWORK

# 调试开关
DEBUG = False
debug = lambda x: DEBUG and print(x)
print_lock = Lock()
thread_state = local()

API_URL = "https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php"
ALL_MAX_WORKERS = 8
MAX_RETRIES = 3


def get_session(headers: dict) -> requests.Session:
    """为每个工作线程复用 HTTP 连接，避免每个车站重复建立连接。"""
    session = getattr(thread_state, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(headers)
        adapter = HTTPAdapter(
            pool_connections=ALL_MAX_WORKERS,
            pool_maxsize=ALL_MAX_WORKERS,
        )
        session.mount("https://", adapter)
        thread_state.session = session
    return session


def wait_before_retry(response: requests.Response | None, attempt: int) -> None:
    """尊重服务端的 Retry-After，并对临时错误采用指数退避。"""
    retry_after = response.headers.get("Retry-After") if response is not None else None
    try:
        delay = float(retry_after) if retry_after else 0.4 * (2 ** (attempt - 1))
    except ValueError:
        delay = 0.4 * (2 ** (attempt - 1))
    time.sleep(min(delay, 4.0))


def fetch_single_station(line: str, sta_code: str, sta_info: list, index: int, total_stations: int, headers: dict) -> tuple:
    """单独获取并清洗某个车站数据的函数（供全局线程池调用）"""
    params = {
        "line": line,
        "sta": sta_code,
        "lang": "CH"
    }
    
    station_result = None
    status_msg = ""
    session = get_session(headers)
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(API_URL, params=params, timeout=5)
            
            if response.status_code == 429:
                status_msg = "❌ 触发限流 [HTTP 429]"
                if attempt < MAX_RETRIES:
                    wait_before_retry(response, attempt)
                    continue
                return line, sta_code, {"success": False, "originalJson": None, "message": "API Rate Limited (429)"}, status_msg
                
            if response.status_code != 200:
                status_msg = f"⚠️ 状态码异常 [HTTP {response.status_code}]"
                if response.status_code in {500, 502, 503, 504} and attempt < MAX_RETRIES:
                    wait_before_retry(response, attempt)
                    continue
                return line, sta_code, {"success": False, "originalJson": response.text, "message": f"HTTP {response.status_code}"}, status_msg
                
            text_content = response.text.strip()
            if not text_content or not text_content.startswith("{"):
                status_msg = "⚠️ 返回内容非JSON"
                if attempt < MAX_RETRIES:
                    wait_before_retry(None, attempt)
                    continue
                return line, sta_code, {"success": False, "originalJson": text_content, "message": "Invalid JSON response"}, status_msg
                
            try:
                res_json = response.json()
            except ValueError:
                status_msg = "⚠️ 返回内容JSON解析失败"
                if attempt < MAX_RETRIES:
                    wait_before_retry(response, attempt)
                    continue
                return line, sta_code, {"success": False, "originalJson": response.text, "message": "Invalid JSON response"}, status_msg
                
            debug(f"[DEBUG] 线路 {line} 车站 {sta_code} 返回: {res_json}")
            
            # 检查 NT-204 或 status == 0
            err_info = res_json.get("error", {})
            err_code = err_info.get("errorCode", "")
            
            if err_code == "NT-204" or res_json.get("status") == 0:
                station_result = {
                    "success": False,
                    "originalJson": res_json,
                    "message": "Wrong station code or no service"
                }
                status_msg = f"ℹ️ 暂无服务/代码不匹配 [NT-204]"
                break
            
            if res_json.get("status") == 1:
                api_key = f"{line}-{sta_code}"
                raw_station_data = res_json.get("data", {}).get(api_key, {})
                
                station_data = {"UP": [], "DOWN": []}
                
                # 清洗 UP（上行）
                for train in raw_station_data.get("UP", []):
                    raw_time = train.get("time", "")
                    clean_time = raw_time.split(" ")[1] if " " in raw_time else raw_time
                    
                    raw_ttnt = train.get("ttnt")
                    ttnt_val = int(raw_ttnt) if raw_ttnt is not None and str(raw_ttnt).isdigit() else 99
                    
                    plat_val = train.get("plat")
                    # 针对部分车站若API缺省月台的兜底适配（可根据需要微调）
                    if not plat_val and sta_code == "CEN":
                        plat_val = "1"
                        
                    formatted_train = {
                        "time": clean_time,
                        "dest": train.get("dest"),
                        "plat": plat_val,
                        "ttnt": ttnt_val,
                        "trainArrived": (ttnt_val == 0)
                    }
                    station_data["UP"].append(formatted_train)
                    
                # 清洗 DOWN（下行）
                for train in raw_station_data.get("DOWN", []):
                    raw_time = train.get("time", "")
                    clean_time = raw_time.split(" ")[1] if " " in raw_time else raw_time
                    
                    raw_ttnt = train.get("ttnt")
                    ttnt_val = int(raw_ttnt) if raw_ttnt is not None and str(raw_ttnt).isdigit() else 99
                    
                    plat_val = train.get("plat")
                    if not plat_val and sta_code == "CEN":
                        plat_val = "2"
                        
                    formatted_train = {
                        "time": clean_time,
                        "dest": train.get("dest"),
                        "plat": plat_val,
                        "ttnt": ttnt_val,
                        "trainArrived": (ttnt_val == 0)
                    }
                    station_data["DOWN"].append(formatted_train)
                
                status_msg = "✅ 成功"
                station_result = station_data
                break
            else:
                err_msg = err_info.get("errorMsg", res_json.get("message", "未知错误"))
                station_result = {
                    "success": False,
                    "originalJson": res_json,
                    "message": err_msg
                }
                status_msg = f"ℹ️ 状态异常 [{err_msg}]"
                break
                
        except requests.Timeout:
            status_msg = f"❌ 超时 (第 {attempt}/{MAX_RETRIES} 次)"
            if attempt < MAX_RETRIES:
                wait_before_retry(None, attempt)
                continue
            station_result = {"success": False, "originalJson": None, "message": "Request Timeout"}
        except requests.ConnectionError as e:
            status_msg = f"❌ 连接异常 (第 {attempt}/{MAX_RETRIES} 次)"
            if attempt < MAX_RETRIES:
                wait_before_retry(None, attempt)
                continue
            station_result = {"success": False, "originalJson": None, "message": str(e)}
        except Exception as e:
            status_msg = f"❌ 异常: {e}"
            station_result = {"success": False, "originalJson": None, "message": str(e)}
            break
            
    with print_lock:
        debug(f"[{index}/{total_stations}] 线路: {line} | 车站: {sta_code} ({sta_info[0] if sta_info else ''}) ... {status_msg}")
        
    return line, sta_code, station_result, status_msg

# 在 api.py 的 getTrains 函数中增加对复合线路（如 "TWL&KTL"）的支持
def getTrains(line: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 支持传入如 "TWL&KTL" 或 "ALL"
    if "&" in line or line.upper() == "ALL":
        target_lines = list(MTR_NETWORK.keys()) if line.upper() == "ALL" else [l.strip().upper() for l in line.split("&")]
        all_tasks = []
        for l_code in target_lines:
            if l_code in MTR_NETWORK:
                for sta_code, sta_info in MTR_NETWORK[l_code].items():
                    all_tasks.append((l_code, sta_code, sta_info))
                
        total_tasks = len(all_tasks)
        debug(f"🚀 开始【多线路并发】获取目标线路数据，总计 {total_tasks} 个车站...\n")
        
        output = {
            "status": True,
            "lines": {l_code: {"status": True, "stations": {}} for l_code in target_lines}
        }
        
        with ThreadPoolExecutor(max_workers=ALL_MAX_WORKERS) as executor:
            future_to_info = {
                executor.submit(fetch_single_station, l_code, sta_code, sta_info, i, total_tasks, headers): (l_code, sta_code)
                for i, (l_code, sta_code, sta_info) in enumerate(all_tasks, 1)
            }
            
            for future in as_completed(future_to_info):
                l_code, sta_code, station_result, msg = future.result()
                if station_result is not None and l_code in output["lines"]:
                    output["lines"][l_code]["stations"][sta_code] = station_result
                    
        return output

    # 单条线路查询保持不变
    if line not in MTR_NETWORK:
        debug(f"❌ 无效的线路代码: {line}")
        return {"status": False, "error": "Invalid line code"}
        
    station_dict = MTR_NETWORK[line]
    output = {"status": True, "stations": {}}
    total_stations = len(station_dict)
    
    max_workers = min(10, total_stations)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sta = {
            executor.submit(fetch_single_station, line, sta_code, sta_info, index, total_stations, headers): sta_code
            for index, (sta_code, sta_info) in enumerate(station_dict.items(), 1)
        }
        
        for future in as_completed(future_to_sta):
            _, sta_code, station_result, _ = future.result()
            if station_result is not None:
                output["stations"][sta_code] = station_result
                
    return output

if __name__ == "__main__":
    all_data = getTrains("ALL")
    for line_code, line_res in all_data["lines"].items():
        debug(f"\n==================== [{line_code}] 线路数据 ====================")
        if line_res["status"]:
            for sta_code, sta_data in line_res["stations"].items():
                if isinstance(sta_data, dict) and "UP" in sta_data and "DOWN" in sta_data:
                    debug(f"✨ [{sta_code}] 站实时数据：上行 {len(sta_data['UP'])} 班次 | 下行 {len(sta_data['DOWN'])} 班次")