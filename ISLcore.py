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
# ISLcore.py (港岛线专属核心逻辑与渲染模块 - CHW 1/2 号月台精准隔离映射版)
# ==============================================================================
import time
import os
import json
from data import MTR_NETWORK, ISL_PLATFORMS

# 🔴 全局调试开关
DEBUG = False

# ANSI 颜色定义
RED = "\033[91m"
BLUE = "\033[94m"
GREEN = "\033[92m"
RESET = "\033[0m"

# 全局内存中的在途列车队列、快照与轮次计数器
segment_queues = {}
last_arrived_snapshot = {}
error_history = []
loop_round = 0  

def get_isl_stations():
    """从 data.py 动态获取港岛线 (ISL) 的所有车站代码"""
    if "ISL" not in MTR_NETWORK:
        return []
    return list(MTR_NETWORK["ISL"].keys())

def get_next_station(line: str, dir_key: str, current_sta: str) -> str:
    """根据 MTR_NETWORK 中定义的车站顺序获取下一站代码"""
    stations = get_isl_stations()
    if line not in MTR_NETWORK or current_sta not in stations:
        return None
    idx = stations.index(current_sta)
    if dir_key == "UP" and idx - 1 >= 0:
        return stations[idx - 1]
    elif dir_key == "DOWN" and idx + 1 < len(stations):
        return stations[idx + 1]
    return None

def get_isl_direction(current_sta: str, dest: str) -> str:
    stations = get_isl_stations()
    if current_sta not in stations or dest not in stations:
        return "DOWN"
    
    curr_idx = stations.index(current_sta)
    dest_idx = stations.index(dest)
    
    if curr_idx < dest_idx:
        return "DOWN"
    elif curr_idx > dest_idx:
        return "UP"
    else:
        return "DOWN" if current_sta == "KET" else "UP" if current_sta == "CHW" else "DOWN"

def get_platforms(sta_code: str, dir_key: str) -> list:
    """从 data.py 的 ISL_PLATFORMS 中获取指定方向和车站的配置月台"""
    return ISL_PLATFORMS.get(dir_key, {}).get(sta_code, [])

def get_train_platform(sta_code: str, dir_key: str, train: dict) -> list:
    actual_plat = str(train.get("plat", ""))
    if actual_plat and actual_plat != "0":
        return [actual_plat]
    return get_platforms(sta_code, dir_key)

def calc_isl_state(trains_data):
    global last_arrived_snapshot, segment_queues, error_history, loop_round
    
    if DEBUG:
        loop_round += 1  
        
    current_time = time.time()
    isl_stations = get_isl_stations()
    if not isl_stations:
        return {}

    lines = trains_data.get("lines", {})
    isl_info = lines.get("ISL", trains_data)
    stations_data = isl_info.get("stations", {})

    for sta_code, sta_info in stations_data.items():
        if isinstance(sta_info, dict) and sta_info.get("success") is False:
            error = f"{sta_code}: {sta_info.get('message', 'API error')}"
            if error not in error_history:
                error_history.append(error)
    
    current_arrived_snapshot = {}
    valid_stations = {
        sta_code
        for sta_code in isl_stations
        if isinstance(stations_data.get(sta_code), dict)
        and "UP" in stations_data[sta_code]
        and "DOWN" in stations_data[sta_code]
    }
    
    # 静态分配固定方向月台号码：
    # UP 侧（左）：CEN 为 "3"，KET 为 "2"（盲区标蓝），CHW 明确固定为 "2"，其余为 "2"
    # DOWN 侧（右）：CEN 为 "4"，KET 为 "1"，CHW 明确固定为 "1"，其余为 "1"
    arrived_status = {}
    for sta in isl_stations:
        up_p = "3" if sta == "CEN" else ("2" if sta in ("KET", "CHW") else ("/".join(get_platforms(sta, "UP")) or "-"))
        down_p = "4" if sta == "CEN" else ("1" if sta in ("KET", "CHW") else ("/".join(get_platforms(sta, "DOWN")) or "-"))
        
        arrived_status[sta] = {
            "UP": False, 
            "DOWN": False, 
            "plats": set(), 
            "green_plats": set(),
            "blue_plats": ["2"] if sta == "KET" else [],
            "up_plat": up_p,
            "down_plat": down_p,
            "arrived_trains": {"UP": [], "DOWN": []}
        }
    
    # 1. 收集当前停靠状态：两端终点站 KET 和 CHW 采用 ttnt <= 5（n=5）作为开出/停靠判断
    for sta_code in isl_stations:
        sta_info = stations_data.get(sta_code, {})
        plats_arrived = set()
        arrived_trains = {"UP": [], "DOWN": []}
        
        for api_dir_key in ["UP", "DOWN"]:
            train_list = sta_info.get(api_dir_key, [])
            for t in train_list:
                ttnt = t.get("ttnt", 99)
                is_arr = (ttnt <= 5) if sta_code in ("KET", "CHW") else (ttnt == 0)
                
                if is_arr:
                    dest = t.get("dest", "UNKNOWN")
                    real_dir = get_isl_direction(sta_code, dest)
                    
                    configured_plats = get_train_platform(sta_code, real_dir, t)
                    actual_plat = str(t.get("plat", ""))
                    
                    # 💡【核心精确定位规则】：针对 CHW（柴湾）站，严禁月台混淆或错位！
                    # 只有当 API 明确返回 plat="2" 时，才允许点亮 UP(左侧)；
                    # 只有当 API 明确返回 plat="1" 时，才允许点亮 DOWN(右侧)。
                    if sta_code == "CHW":
                        if actual_plat == "2":
                            arrived_status[sta_code]["UP"] = True
                            plats_arrived.add("2")
                        elif actual_plat == "1":
                            arrived_status[sta_code]["DOWN"] = True
                            plats_arrived.add("1")
                        elif "2" in configured_plats and real_dir == "UP":
                            arrived_status[sta_code]["UP"] = True
                            plats_arrived.add("2")
                        elif "1" in configured_plats and real_dir == "DOWN":
                            arrived_status[sta_code]["DOWN"] = True
                            plats_arrived.add("1")
                    else:
                        arrived_status[sta_code][real_dir] = True
                        plats_arrived.update(configured_plats)

                    if dest not in ("KET", "CHW"):
                        arrived_status[sta_code]["green_plats"].update(configured_plats)
                        
                    arrived_trains[real_dir].append(dest)
                    
                    snapshot_key = (
                        "ISL", real_dir, sta_code, dest,
                        str(t.get("plat", ""))
                    )
                    current_arrived_snapshot[snapshot_key] = current_time
                    
        arrived_status[sta_code]["plats"] = plats_arrived
        arrived_status[sta_code]["arrived_trains"] = arrived_trains

    # 2. 离站检测
    for old_key, _ in last_arrived_snapshot.items():
        if old_key[2] not in valid_stations:
            current_arrived_snapshot[old_key] = _
            continue
        if old_key not in current_arrived_snapshot:
            line_code, _, sta_code, dest = old_key[:4]
            
            departure_dir = get_isl_direction(sta_code, dest)
            next_sta = get_next_station(line_code, departure_dir, sta_code)
            
            if next_sta:
                seg_key = f"{line_code}-{departure_dir}-{sta_code}->{next_sta}"
                
                if sta_code == "KET" and next_sta == "HKU" and departure_dir == "DOWN":
                    continue
                
                if seg_key not in segment_queues:
                    segment_queues[seg_key] = []
                
                segment_queues[seg_key].append({
                    "depart_time": current_time,
                    "depart_time_str": time.strftime('%H:%M:%S', time.localtime(current_time)),
                    "depart_round": loop_round,
                    "dest": dest,
                    "plat": old_key[4]
                })

    # 3. 进站匹配
    for sta_code in isl_stations:
        for dir_key in ["UP", "DOWN"]:
            for dest in arrived_status[sta_code]["arrived_trains"][dir_key]:
                train_dir = get_isl_direction(sta_code, dest)
                stations_list = isl_stations
                idx = stations_list.index(sta_code)
                prev_sta = None
                
                if train_dir == "DOWN" and idx - 1 >= 0:
                    prev_sta = stations_list[idx - 1]
                elif train_dir == "UP" and idx + 1 < len(stations_list):
                    prev_sta = stations_list[idx + 1]
                
                if prev_sta:
                    seg_key = f"ISL-{train_dir}-{prev_sta}->{sta_code}"
                    if seg_key in segment_queues and segment_queues[seg_key]:
                        matching_index = next(
                            (index for index, train in enumerate(segment_queues[seg_key])
                             if train["dest"] == dest),
                            None
                        )
                        if matching_index is None:
                            matching_index = 0
                        segment_queues[seg_key].pop(matching_index)

    # 4. 队列垃圾清理 (10分钟超时)
    for seg_key in list(segment_queues.keys()):
        segment_queues[seg_key] = [t for t in segment_queues[seg_key] if current_time - t["depart_time"] < 600]
        if not segment_queues[seg_key]:
            del segment_queues[seg_key]

    last_arrived_snapshot = current_arrived_snapshot

    return {
        "line": "ISL",
        "stations": isl_stations,
        "arrived_status": arrived_status,
        "segment_queues": segment_queues,
        "errors": error_history,
        "current_round": loop_round
    }

def draw_isl_trains(state_data):
    """第二部分：纯渲染逻辑（终端终端终端适配）"""
    if not state_data:
        return
        
    isl_stations = state_data["stations"]
    arrived_status = state_data["arrived_status"]
    segment_queues = state_data["segment_queues"]
    current_round = state_data.get("current_round", 0)

    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"=== ISL Track Monitor [{time.strftime('%H:%M:%S')}] | 当前轮次 n={current_round} ===")
    print("\n" + "="*50 + "\n")

    for i, sta_code in enumerate(isl_stations):
        plats = arrived_status[sta_code]["plats"]
        green_plats = arrived_status[sta_code]["green_plats"]
        
        if sta_code == "KET":
            down_arr = arrived_status[sta_code]["DOWN"]
            u_color = BLUE  # KET2 标蓝
            d_color = GREEN if "1" in green_plats else RED if down_arr else ""
            u_str = f"{u_color}KET2{RESET}"
            d_str = f"{d_color}KET1{RESET}" if d_color else "KET1"
        elif sta_code == "CHW":
            up_arr = arrived_status[sta_code]["UP"]
            down_arr = arrived_status[sta_code]["DOWN"]
            u_color = GREEN if "2" in green_plats else RED if (up_arr or "2" in plats) else ""
            d_color = GREEN if "1" in green_plats else RED if (down_arr or "1" in plats) else ""
            u_str = f"{u_color}CHW2{RESET}" if u_color else "CHW2"
            d_str = f"{d_color}CHW1{RESET}" if d_color else "CHW1"
        else:
            up_plats = get_platforms(sta_code, "UP")
            down_plats = get_platforms(sta_code, "DOWN")
            up_label = "/".join(up_plats)
            down_label = "/".join(down_plats)
            
            up_arr = arrived_status[sta_code]["UP"]
            down_arr = arrived_status[sta_code]["DOWN"]
            
            u_color = GREEN if any(p in green_plats for p in up_plats) else RED if up_arr else ""
            d_color = GREEN if any(p in green_plats for p in down_plats) else RED if down_arr else ""
            
            u_str = f"{u_color}{sta_code}{up_label}{RESET}" if u_color else f"{sta_code}{up_label}"
            d_str = f"{d_color}{sta_code}{down_label}{RESET}" if d_color else f"{sta_code}{down_label}"
        
        print(f"{u_str}\t\t{d_str}")
        
        if i < len(isl_stations) - 1:
            next_code = isl_stations[i+1]
            down_seg = f"ISL-DOWN-{sta_code}->{next_code}"
            up_seg = f"ISL-UP-{next_code}->{sta_code}"
            
            down_has_train = bool(segment_queues.get(down_seg))
            up_has_train = bool(segment_queues.get(up_seg))
            
            u_rail_color = RED if up_has_train else ""
            d_rail_color = RED if down_has_train else ""
            
            if next_code == "HKU" and sta_code == "KET":
                u_rail_color = BLUE

            u_reset = RESET if u_rail_color else ""
            d_reset = RESET if d_rail_color else ""

            print(f"{u_rail_color}^{u_reset}\t\t{d_rail_color}v{d_reset}")

    print("\n===============================")
    for error in state_data.get("errors", []):
        print(error)

def mainloop(trains):
    state = calc_isl_state(trains)
    draw_isl_trains(state)