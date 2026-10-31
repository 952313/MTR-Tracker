# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
    MTR Tracker - TWL Core Engine
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
# TWLcore.py (完整整合版 - 严格保留路轨检测/区间车/debug日志 + 先 Pop 后 Push 时序修复)
# ==============================================================================
import time
import os
import json
from data import MTR_NETWORK, TWL_PLATFORMS

# 🔴 全局调试开关：设为 True 时累加轮次、输出黄字告警并写入 debug.txt
DEBUG = True

# ANSI 颜色定义
RED = "\033[91m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# 全局内存中的在途列车队列、快照与轮次计数器
segment_queues = {}
last_arrived_snapshot = {}
error_history = []
loop_round = 0  # 全局轮次计数器 n

def get_twl_stations():
    """从 data.py 动态获取荃湾线 (TWL) 的所有车站代码"""
    if "TWL" not in MTR_NETWORK:
        return []
    return list(MTR_NETWORK["TWL"].keys())

def get_next_station(line: str, dir_key: str, current_sta: str) -> str:
    """根据 MTR_NETWORK 中定义的车站顺序获取下一站代码"""
    stations = get_twl_stations()
    if line not in MTR_NETWORK or current_sta not in stations:
        return None
    idx = stations.index(current_sta)
    if dir_key == "UP" and idx - 1 >= 0:
        return stations[idx - 1]
    elif dir_key == "DOWN" and idx + 1 < len(stations):
        return stations[idx + 1]
    return None

def get_twl_direction(current_sta: str, dest: str) -> str:
    """
    核心动态判定函数：根据当前车站和终点站在线路中的索引，
    计算列车实际行驶方向 ('UP' 或 'DOWN')。
    """
    stations = get_twl_stations()
    if current_sta not in stations or dest not in stations:
        return "DOWN"
    
    curr_idx = stations.index(current_sta)
    dest_idx = stations.index(dest)
    
    if curr_idx < dest_idx:
        return "DOWN"
    elif curr_idx > dest_idx:
        return "UP"
    else:
        return "DOWN" if current_sta == "CEN" else "UP" if current_sta == "TSW" else "DOWN"

def get_platforms(sta_code: str, dir_key: str) -> list:
    """获取指定方向和车站的配置月台。"""
    return TWL_PLATFORMS.get(dir_key, {}).get(sta_code, [])

def get_train_platform(sta_code: str, dir_key: str, train: dict) -> list:
    """获取列车实际占用的月台，避免 CEN 缺少月台时占用两边。"""
    configured_plats = get_platforms(sta_code, dir_key)
    actual_plat = str(train.get("plat", ""))
    if sta_code == "CEN":
        if actual_plat in ("1", "2"):
            return [actual_plat]
        return ["1"] if dir_key == "UP" else ["2"]
    return configured_plats

def dump_debug_log(trains_data, conflict_details):
    """
    将冲突现场及未被任何解析污染的源 json 写入 debug.txt (a+ 模式)
    """
    curr_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    try:
        with open("debug.txt", "a", encoding="utf-8") as f:
            f.write("="*80 + "\n")
            f.write(f"[DEBUG LOG] 时间戳: {curr_time_str} | 轮次 n={loop_round} | 时间戳整数: {int(time.time())}\n")
            f.write("--- 发现冲突: 车站与相邻路轨同时占用 ---\n")
            for detail in conflict_details:
                f.write(f"  * {detail}\n")
            f.write("--- 源 JSON (RAW API DATA) ---\n")
            f.write(json.dumps(trains_data, ensure_ascii=False, indent=2) + "\n")
            f.write("="*80 + "\n\n")
    except Exception as e:
        print(f"写入 debug.txt 失败: {e}")

def calc_twl_state(trains_data):
    """
    第一部分：计算核心逻辑
    处理在途队列、到站/离站匹配、过海校验，并返回整理好的状态数据
    """
    global last_arrived_snapshot, segment_queues, error_history, loop_round
    
    if DEBUG:
        loop_round += 1  
        
    current_time = time.time()
    twl_stations = get_twl_stations()
    if not twl_stations:
        return {}

    lines = trains_data.get("lines", {})
    twl_info = lines.get("TWL", trains_data)
    stations_data = twl_info.get("stations", {})

    for sta_code, sta_info in stations_data.items():
        if isinstance(sta_info, dict) and sta_info.get("success") is False:
            error = f"{sta_code}: {sta_info.get('message', 'API error')}"
            if error not in error_history:
                error_history.append(error)
    
    current_arrived_snapshot = {}
    valid_stations = {
        sta_code
        for sta_code in twl_stations
        if isinstance(stations_data.get(sta_code), dict)
        and "UP" in stations_data[sta_code]
        and "DOWN" in stations_data[sta_code]
    }
    
    arrived_status = {
        sta: {
            "UP": False, 
            "DOWN": False, 
            "plats": set(), 
            "green_plats": set(),
            "up_plat": "1" if sta == "CEN" else ("/".join(get_platforms(sta, "UP")) if get_platforms(sta, "UP") else "-"),
            "down_plat": "2" if sta == "CEN" else ("/".join(get_platforms(sta, "DOWN")) if get_platforms(sta, "DOWN") else "-")
        }
        for sta in twl_stations
    }
    
    # ----------------------------------------------------
    # 1. 全量收集当前各站到站停靠状态
    # ----------------------------------------------------
    for sta_code in twl_stations:
        sta_info = stations_data.get(sta_code, {})
        plats_arrived = set()
        arrived_trains = {"UP": [], "DOWN": []}
        
        for api_dir_key in ["UP", "DOWN"]:
            train_list = sta_info.get(api_dir_key, [])
            for t in train_list:
                ttnt = t.get("ttnt", 99)
                is_arr = (ttnt <= 5) if sta_code == "CEN" else (ttnt == 0)
                
                if is_arr:
                    dest = t.get("dest", "UNKNOWN")
                    real_dir = get_twl_direction(sta_code, dest)
                    if sta_code == "CEN":
                        real_dir = "UP"
                    elif sta_code == "TSW":
                        real_dir = "DOWN"
                    
                    arrived_status[sta_code][real_dir] = True
                    configured_plats = get_train_platform(sta_code, real_dir, t)
                    plats_arrived.update(configured_plats)
                    
                    if dest not in ("CEN", "TSW"):
                        arrived_status[sta_code]["green_plats"].update(configured_plats)
                        
                    arrived_trains[real_dir].append(dest)
                    
                    snapshot_key = (
                        "TWL", real_dir, sta_code, dest,
                        str(t.get("plat", ""))
                    )
                    current_arrived_snapshot[snapshot_key] = current_time
                    
        arrived_status[sta_code]["plats"] = plats_arrived
        arrived_status[sta_code]["arrived_trains"] = arrived_trains

    # ----------------------------------------------------
    # 2. 统一先处理进站匹配 (Pop)
    # 彻底解决出站即被误消的问题；结合 FIFO 与 dest 后备匹配
    # ----------------------------------------------------
    for sta_code in twl_stations:
        for dir_key in ["UP", "DOWN"]:
            for dest in arrived_status[sta_code]["arrived_trains"][dir_key]:
                train_dir = get_twl_direction(sta_code, dest)
                if sta_code == "CEN":
                    train_dir = "UP"
                elif sta_code == "TSW":
                    train_dir = "DOWN"
                
                stations_list = twl_stations
                idx = stations_list.index(sta_code)
                prev_sta = None
                
                if train_dir == "DOWN" and idx - 1 >= 0:
                    prev_sta = stations_list[idx - 1]
                elif train_dir == "UP" and idx + 1 < len(stations_list):
                    prev_sta = stations_list[idx + 1]
                
                if prev_sta:
                    seg_key = f"TWL-{train_dir}-{prev_sta}->{sta_code}"
                    if seg_key in segment_queues and segment_queues[seg_key]:
                        is_cross_harbor = seg_key.endswith("TST->ADM") or seg_key.endswith("ADM->TST")
                        
                        # CEN 站特权免校验，或匹配同 dest 的列车（后备匹配首辆）
                        if sta_code == "CEN":
                            matching_index = 0
                        else:
                            matching_index = next(
                                (index for index, train in enumerate(segment_queues[seg_key])
                                 if train["dest"] == dest),
                                0
                            )
                        
                        matching_train = segment_queues[seg_key][matching_index]
                        elapsed = current_time - matching_train["depart_time"]
                        round_diff = loop_round - matching_train["depart_round"]

                        # DEBUG 告警检测
                        if DEBUG:
                            if round_diff < 1:
                                print(f"\n{YELLOW}[WARNING] 极短轮次差冲突告警！{RESET}")
                                print(f"区段: {seg_key} | 终点: {dest} | 轮次差: {round_diff} (小于1) | 耗时: {elapsed:.2f}s")
                                print(f"触发轮次: #{loop_round} | 离站轮次: #{matching_train['depart_round']}\n")
                            elif elapsed < 20.0:
                                print(f"\n{YELLOW}[WARNING] 异常偏短区间耗时告警！{RESET}")
                                print(f"区段: {seg_key} | 终点: {dest} | 耗时: {elapsed:.2f} 秒 (小于20秒阈值)")
                                print(f"触发轮次: #{loop_round} | 离站时间: {matching_train['depart_time_str']}\n")

                        # 过海段 >120 秒防卡死检验
                        if not (is_cross_harbor and elapsed < 120):
                            segment_queues[seg_key].pop(matching_index)

    # ----------------------------------------------------
    # 3. 统一后处理离站检测与入队 (Push)
    # ----------------------------------------------------
    for old_key, _ in last_arrived_snapshot.items():
        if old_key[2] not in valid_stations:
            current_arrived_snapshot[old_key] = _
            continue
        if old_key not in current_arrived_snapshot:
            line_code, _, sta_code, dest = old_key[:4]
            
            departure_dir = get_twl_direction(sta_code, dest)
            next_sta = get_next_station(line_code, departure_dir, sta_code)
            
            if next_sta:
                seg_key = f"{line_code}-{departure_dir}-{sta_code}->{next_sta}"
                
                if sta_code == "TWH" and next_sta == "TSW":
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

    # ----------------------------------------------------
    # 4. 队列垃圾清理 (10分钟超时)
    # ----------------------------------------------------
    for seg_key in list(segment_queues.keys()):
        segment_queues[seg_key] = [t for t in segment_queues[seg_key] if current_time - t["depart_time"] < 600]
        if not segment_queues[seg_key]:
            del segment_queues[seg_key]

    # ----------------------------------------------------
    # 5. 【保留诊断检测】仅当 DEBUG=True 时检测并写入 debug.txt
    # ----------------------------------------------------
    conflict_details = []
    if DEBUG:
        for i, sta_code in enumerate(twl_stations):
            if i < len(twl_stations) - 1:
                next_code = twl_stations[i+1]
                up_seg = f"TWL-UP-{next_code}->{sta_code}"
                if arrived_status[sta_code]["UP"] and segment_queues.get(up_seg):
                    for q_train in segment_queues[up_seg]:
                        conflict_details.append(
                            f"车站 [{sta_code}] UP 停靠着，但其入站轨道 [{up_seg}] 仍有残留车 (终点={q_train['dest']}, "
                            f"压入轮次={q_train['depart_round']}, 压入时间={q_train['depart_time_str']})"
                        )

            if i > 0:
                prev_code = twl_stations[i-1]
                down_seg = f"TWL-DOWN-{prev_code}->{sta_code}"
                if arrived_status[sta_code]["DOWN"] and segment_queues.get(down_seg):
                    for q_train in segment_queues[down_seg]:
                        conflict_details.append(
                            f"车站 [{sta_code}] DOWN 停靠着，但其入站轨道 [{down_seg}] 仍有残留车 (终点={q_train['dest']}, "
                            f"压入轮次={q_train['depart_round']}, 压入时间={q_train['depart_time_str']})"
                        )

        if conflict_details:
            dump_debug_log(trains_data, conflict_details)

    last_arrived_snapshot = current_arrived_snapshot

    return {
        "stations": twl_stations,
        "arrived_status": arrived_status,
        "segment_queues": segment_queues,
        "errors": error_history,
        "current_round": loop_round
    }

def draw_twl_trains(state_data):
    """
    第二部分：纯渲染逻辑（保留区间车绿轨判定与站轨冲突报警）
    """
    if not state_data:
        return
        
    twl_stations = state_data["stations"]
    arrived_status = state_data["arrived_status"]
    segment_queues = state_data["segment_queues"]
    current_round = state_data.get("current_round", 0)

    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"=== TWL Track Monitor [{time.strftime('%H:%M:%S')}] | 当前轮次 n={current_round} ===")

    # 实时检测真实的“车站与相邻轨道同时占用”冲突
    active_conflicts = []
    for i, sta_code in enumerate(twl_stations):
        if i < len(twl_stations) - 1:
            next_code = twl_stations[i+1]
            up_seg = f"TWL-UP-{next_code}->{sta_code}"
            if arrived_status[sta_code]["UP"] and segment_queues.get(up_seg):
                for q_train in segment_queues[up_seg]:
                    active_conflicts.append(
                        f"车站 [{sta_code}] UP 停靠着，但其入站轨道 [{up_seg}] 仍有残留车 (终点={q_train['dest']}, 压入轮次={q_train['depart_round']})"
                    )

        if i > 0:
            prev_code = twl_stations[i-1]
            down_seg = f"TWL-DOWN-{prev_code}->{sta_code}"
            if arrived_status[sta_code]["DOWN"] and segment_queues.get(down_seg):
                for q_train in segment_queues[down_seg]:
                    active_conflicts.append(
                        f"车站 [{sta_code}] DOWN 停靠着，但其入站轨道 [{down_seg}] 仍有残留车 (终点={q_train['dest']}, 压入轮次={q_train['depart_round']})"
                    )

    # 仅当真正发生“站轨同时占用”时才在顶部报警，否则显示状态正常
    if active_conflicts:
        print("\033[91m[检测到 Bug] 发现车站与相邻路轨同时占用冲突：\033[0m")
        for conflict in active_conflicts:
            print(f"\033[91m  * {conflict}\033[0m")
    else:
        print("\033[92m[状态正常] 轨道追踪正常，无站轨冲突。\033[0m")

    print("\n" + "="*50 + "\n")

    for i, sta_code in enumerate(twl_stations):
        plats = arrived_status[sta_code]["plats"]
        green_plats = arrived_status[sta_code]["green_plats"]
        
        if sta_code == "CEN":
            u_color = GREEN if "1" in green_plats else RED if "1" in plats else ""
            d_color = GREEN if "2" in green_plats else RED if "2" in plats else ""
            u_str = f"{u_color}CEN1{RESET}" if u_color else "CEN1"
            d_str = f"{d_color}CEN2{RESET}" if d_color else "CEN2"
        elif sta_code == "TSW":
            up_arr = arrived_status[sta_code]["UP"]
            u_color = GREEN if "2" in green_plats else RED if up_arr else ""
            d_color = BLUE  # 💡 强制 TSW1 为蓝色
            u_str = f"{u_color}TSW2{RESET}" if u_color else "TSW2"
            d_str = f"{BLUE}TSW1{RESET}"
        else:
            up_arr = arrived_status[sta_code]["UP"]
            down_arr = arrived_status[sta_code]["DOWN"]
            up_plats = get_platforms(sta_code, "UP")
            down_plats = get_platforms(sta_code, "DOWN")
            up_label = "/".join(up_plats)
            down_label = "/".join(down_plats)
            u_color = GREEN if any(plat in green_plats for plat in up_plats) else RED if up_arr else ""
            d_color = GREEN if any(plat in green_plats for plat in down_plats) else RED if down_arr else ""
            u_str = f"{u_color}{sta_code}{up_label}{RESET}" if u_color else f"{sta_code}{up_label}"
            d_str = f"{d_color}{sta_code}{down_label}{RESET}" if d_color else f"{sta_code}{down_label}"
        
        print(f"{u_str}\t\t{d_str}")
        
        if i < len(twl_stations) - 1:
            next_code = twl_stations[i+1]
            down_seg = f"TWL-DOWN-{sta_code}->{next_code}"
            up_seg = f"TWL-UP-{next_code}->{sta_code}"
            
            down_has_train = bool(segment_queues.get(down_seg))
            up_has_train = bool(segment_queues.get(up_seg))
            down_has_non_terminal = any(
                train["dest"] not in ("CEN", "TSW")
                for train in segment_queues.get(down_seg, [])
            )
            up_has_non_terminal = any(
                train["dest"] not in ("CEN", "TSW")
                for train in segment_queues.get(up_seg, [])
            )
            
            u_rail_color = GREEN if (up_has_train and up_has_non_terminal) else RED if up_has_train else ""
            d_rail_color = GREEN if (down_has_train and down_has_non_terminal) else RED if down_has_train else ""
            
            if next_code == "TSW":
                d_rail_color = BLUE

            u_reset = RESET if u_rail_color else ""
            d_reset = RESET if d_rail_color else ""

            print(f"{u_rail_color}^{u_reset}\t\t{d_rail_color}v{d_reset}")

    print("\n===============================")
    for error in state_data.get("errors", []):
        print(error)

def mainloop(trains):
    """主循环入口"""
    state = calc_twl_state(trains)
    draw_twl_trains(state)