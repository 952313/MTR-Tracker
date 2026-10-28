# ==============================================================================
# KTLcore.py (观塘线专属核心逻辑与渲染模块 - 修复字典推导式 NameError)
# ==============================================================================
import time
import os
import json
from data import MTR_NETWORK, KTL_PLATFORMS

# 🔴 开启调试开关
DEBUG = False

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
loop_round = 0

# HOM 标蓝/盲区状态机
hom_blue_state = 0  
last_ymt_has_red = False

def get_ktl_stations():
    if "KTL" not in MTR_NETWORK:
        return []
    return list(MTR_NETWORK["KTL"].keys())

def get_next_station(line: str, dir_key: str, current_sta: str) -> str:
    stations = get_ktl_stations()
    if line not in MTR_NETWORK or current_sta not in stations:
        return None
    idx = stations.index(current_sta)
    if dir_key == "UP" and idx - 1 >= 0:
        return stations[idx - 1]
    elif dir_key == "DOWN" and idx + 1 < len(stations):
        return stations[idx + 1]
    return None

def get_ktl_direction(current_sta: str, dest: str) -> str:
    stations = get_ktl_stations()
    if current_sta not in stations or dest not in stations:
        return "DOWN"
    curr_idx = stations.index(current_sta)
    dest_idx = stations.index(dest)
    if curr_idx < dest_idx:
        return "DOWN"
    elif curr_idx > dest_idx:
        return "UP"
    else:
        return "DOWN" if current_sta == "WHA" else "UP" if current_sta == "TIK" else "DOWN"

def get_platforms(sta_code: str, dir_key: str) -> list:
    return KTL_PLATFORMS.get(dir_key, {}).get(sta_code, [])

def get_train_platform(sta_code: str, dir_key: str, train: dict) -> list:
    actual_plat = str(train.get("plat", ""))
    if sta_code == "WHA":
        return ["1"]
    if actual_plat and actual_plat != "0":
        return [actual_plat]
    return get_platforms(sta_code, dir_key)

# ==============================================================================
# 第一部分：纯计算与状态更新逻辑
# ==============================================================================
def calc_ktl_state(trains_data):
    global last_arrived_snapshot, segment_queues, error_history, loop_round, hom_blue_state, last_ymt_has_red
    
    if DEBUG:
        loop_round += 1  
        
    current_time = time.time()
    ktl_stations = get_ktl_stations()
    if not ktl_stations:
        return {}

    lines = trains_data.get("lines", {})
    ktl_info = lines.get("KTL", trains_data)
    stations_data = ktl_info.get("stations", {})

    for sta_code, sta_info in stations_data.items():
        if isinstance(sta_info, dict) and sta_info.get("success") is False:
            error = f"{sta_code}: {sta_info.get('message', 'API error')}"
            if error not in error_history:
                error_history.append(error)
    
    current_arrived_snapshot = {}
    valid_stations = {
        sta_code for sta_code in ktl_stations
        if isinstance(stations_data.get(sta_code), dict)
        and "UP" in stations_data[sta_code] and "DOWN" in stations_data[sta_code]
    }
    
    # 💡 修复处：将键名从未定义的 sta 改为 sta_code
    arrived_status = {
        sta_code: {"UP": False, "DOWN": False, "plats": set(), "green_plats": set(), "arrived_trains": {"UP": [], "DOWN": []}}
        for sta_code in ktl_stations
    }
    
    # 1. 收集当前停靠状态
    for sta_code in ktl_stations:
        sta_info = stations_data.get(sta_code, {})
        plats_arrived = set()
        
        for api_dir_key in ["UP", "DOWN"]:
            train_list = sta_info.get(api_dir_key, [])
            for t in train_list:
                ttnt = t.get("ttnt", 99)
                
                if sta_code == "WHA":
                    is_arr = (ttnt < 3)
                else:
                    is_arr = (ttnt == 0)
                
                if is_arr:
                    dest = t.get("dest", "UNKNOWN")
                    real_dir = get_ktl_direction(sta_code, dest)
                    
                    arrived_status[sta_code][real_dir] = True
                    configured_plats = get_train_platform(sta_code, real_dir, t)
                    plats_arrived.update(configured_plats)
                    
                    if dest not in ("TIK", "WHA"):
                        arrived_status[sta_code]["green_plats"].update(configured_plats)
                        
                    arrived_status[sta_code]["arrived_trains"][real_dir].append(dest)
                    
                    snapshot_key = ("KTL", real_dir, sta_code, dest, str(t.get("plat", "")))
                    current_arrived_snapshot[snapshot_key] = current_time
                    
        arrived_status[sta_code]["plats"] = plats_arrived

    # -------------------------------------------------------------------------
    # 核心精准状态机：HOM 折返盲区与标蓝时序
    # -------------------------------------------------------------------------
    ymt_up_trains = arrived_status["YMT"]["arrived_trains"].get("UP", [])
    ymt_has_hom_train = ("HOM" in ymt_up_trains)
    ymt_has_red_train = any(d in ("WHA", "UNKNOWN") for d in ymt_up_trains)

    if ymt_has_hom_train and hom_blue_state == 0:
        hom_blue_state = 1

    if hom_blue_state == 1 and ymt_has_red_train and not last_ymt_has_red:
        hom_blue_state = 2

    last_ymt_has_red = ymt_has_red_train

    # 2. 离站检测与入队
    for old_key, _ in last_arrived_snapshot.items():
        if old_key[2] not in valid_stations:
            current_arrived_snapshot[old_key] = _
            continue
        if old_key not in current_arrived_snapshot:
            line_code, _, sta_code, dest = old_key[:4]
            departure_dir = get_ktl_direction(sta_code, dest)
            next_sta = get_next_station(line_code, departure_dir, sta_code)

            if sta_code == "YMT" and departure_dir == "UP" and dest in ("WHA", "UNKNOWN"):
                if hom_blue_state == 2:
                    hom_blue_state = 0

            if sta_code == dest or (sta_code == "YAT" and dest == "TIK") or (sta_code == "YMT" and dest == "HOM") or (sta_code == "WHA"):
                continue

            if next_sta:
                seg_key = f"{line_code}-{departure_dir}-{sta_code}->{next_sta}"
                if seg_key not in segment_queues:
                    segment_queues[seg_key] = []
                segment_queues[seg_key].append({
                    "depart_time": current_time,
                    "depart_time_str": time.strftime('%H:%M:%S', time.localtime(current_time)),
                    "depart_round": loop_round,
                    "dest": dest,
                    "plat": old_key[4]
                })

    # 3. 进站匹配与出队
    for sta_code in ktl_stations:
        for dir_key in ["UP", "DOWN"]:
            for dest in arrived_status[sta_code]["arrived_trains"][dir_key]:
                train_dir = get_ktl_direction(sta_code, dest)
                stations_list = ktl_stations
                idx = stations_list.index(sta_code) if sta_code in stations_list else 0
                prev_sta = None
                if train_dir == "DOWN" and idx - 1 >= 0:
                    prev_sta = stations_list[idx - 1]
                elif train_dir == "UP" and idx + 1 < len(stations_list):
                    prev_sta = stations_list[idx + 1]
                if prev_sta:
                    seg_key = f"KTL-{train_dir}-{prev_sta}->{sta_code}"
                    if seg_key in segment_queues and segment_queues[seg_key]:
                        matching_index = next(
                            (index for index, train in enumerate(segment_queues[seg_key]) if train["dest"] == dest),
                            None
                        )
                        if matching_index is None:
                            matching_index = 0
                        segment_queues[seg_key].pop(matching_index)

    # 4. 队列清理
    for seg_key in list(segment_queues.keys()):
        segment_queues[seg_key] = [t for t in segment_queues[seg_key] if current_time - t["depart_time"] < 600]
        if not segment_queues[seg_key]:
            del segment_queues[seg_key]

    last_arrived_snapshot = current_arrived_snapshot

    return {
        "line": "KTL",
        "stations": ktl_stations,
        "arrived_status": arrived_status,
        "segment_queues": segment_queues,
        "errors": error_history,
        "current_round": loop_round,
        "hom_blue_state": hom_blue_state
    }


# ==============================================================================
# 第二部分：纯渲染逻辑
# ==============================================================================
def draw_ktl_trains(state_data):
    if not state_data:
        return
        
    ktl_stations = state_data["stations"]
    arrived_status = state_data["arrived_status"]
    segment_queues = state_data["segment_queues"]
    current_round = state_data.get("current_round", 0)
    blue_state = state_data.get("hom_blue_state", 0)

    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"=== KTL Track Monitor [{time.strftime('%H:%M:%S')}] | 轮次 n={current_round} ===")
    print("\n" + "="*60 + "\n")

    for i, sta_code in enumerate(ktl_stations):
        plats = arrived_status[sta_code]["plats"]
        green_plats = arrived_status[sta_code]["green_plats"]
        
        up_arr = arrived_status[sta_code]["UP"]
        down_arr = arrived_status[sta_code]["DOWN"]
        
        # 1. 车站显示逻辑
        if sta_code == "CHH":
            p1_active = "1" in plats
            p2_3_active = "2" in plats or "3" in plats
            p4_active = "4" in plats
            p1_color = GREEN if "1" in green_plats else RED if p1_active else ""
            p2_3_color = GREEN if ("2" in green_plats or "3" in green_plats) else RED if p2_3_active else ""
            p4_color = GREEN if "4" in green_plats else RED if p4_active else ""
            ch1_str = f"{p1_color}CHH1{RESET}" if p1_color else "CHH1"
            ch23_str = f"{p2_3_color}CHH2/3{RESET}" if p2_3_color else "CHH2/3"
            ch4_str = f"{p4_color}CHH4{RESET}" if p4_color else "CHH4"
            print(f"{ch4_str}\t\t{ch23_str}\t\t{ch1_str}")
        elif sta_code == "WHA":
            wha_active = up_arr or down_arr
            wha_color = RED if wha_active else ""
            wha_str = f"{wha_color}WHA1{RESET}" if wha_color else "WHA1"
            print(f"{wha_str}\t\t\t\t{wha_str}")
        elif sta_code == "TIK":
            up_plats = get_platforms("TIK", "UP")
            up_p = up_plats[0] if up_plats else "2"
            u_color = GREEN if up_p in green_plats else RED if up_arr else ""
            tik2_str = f"{u_color}TIK{up_p}{RESET}" if u_color else f"TIK{up_p}"
            tik1_str = f"{BLUE}TIK1{RESET}"
            print(f"{tik2_str}\t\t\t\t{tik1_str}")
        else:
            up_plats = get_platforms(sta_code, "UP")
            down_plats = get_platforms(sta_code, "DOWN")
            up_p = up_plats[0] if up_plats else "2"
            down_p = down_plats[0] if down_plats else "1"
            
            u_color = GREEN if up_p in green_plats else RED if up_arr else ""
            d_color = GREEN if down_p in green_plats else RED if down_arr else ""
            
            if sta_code == "HOM":
                if not u_color and blue_state in (1, 2):
                    u_color = BLUE
            
            u_str = f"{u_color}{sta_code}{up_p}{RESET}" if u_color else f"{sta_code}{up_p}"
            d_str = f"{d_color}{sta_code}{down_p}{RESET}" if d_color else f"{sta_code}{down_p}"
            print(f"{u_str}\t\t\t\t{d_str}")
        
        # 2. 轨道显示逻辑
        if i < len(ktl_stations) - 1:
            next_code = ktl_stations[i+1]
            down_seg = f"KTL-DOWN-{sta_code}->{next_code}"
            up_seg = f"KTL-UP-{next_code}->{sta_code}"
            
            up_trains = segment_queues.get(up_seg, [])
            down_trains = segment_queues.get(down_seg, [])
            
            up_has_train = bool(up_trains)
            down_has_train = bool(down_trains)
            
            up_is_green = any(t["dest"] not in ("WHA", "TIK") for t in up_trains)
            down_is_green = any(t["dest"] not in ("WHA", "TIK") for t in down_trains)
            
            if up_has_train:
                u_rail_color = GREEN if up_is_green else RED
            else:
                u_rail_color = ""

            if down_has_train:
                d_rail_color = GREEN if down_is_green else RED
            else:
                d_rail_color = ""

            if sta_code == "HOM" and next_code == "YMT":
                if not up_has_train and blue_state == 1:
                    u_rail_color = BLUE

            if next_code == "TIK":
                d_rail_color = BLUE
            elif sta_code == "TIK":
                u_rail_color = BLUE

            u_reset = RESET if u_rail_color else ""
            d_reset = RESET if d_rail_color else ""

            print(f"{u_rail_color}^{u_reset}\t\t\t\t{d_rail_color}v{d_reset}")

    print("\n==================================================")
    for error in state_data.get("errors", []):
        print(error)

def mainloop(trains):
    state = calc_ktl_state(trains)
    draw_ktl_trains(state)