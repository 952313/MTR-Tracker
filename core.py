import json
import time
from data import MTR_NETWORK

# 内部调试开关
DEBUG_CORE = True
debug = lambda x: print(x) if DEBUG_CORE else None

transit_records = {}
tracked_trains = []
last_arrived_snapshot = {}


def get_station_name(line: str, sta_code: str) -> str:
    """获取车站的繁体中文名称，找不到则返回代码本身"""
    try:
        return MTR_NETWORK[line][sta_code][1]
    except KeyError:
        return sta_code


def get_next_station(line: str, dir_key: str, current_sta: str) -> str:
    """根据 MTR_NETWORK 中定义的车站顺序获取下一站代码"""
    if line not in MTR_NETWORK:
        return None
    
    stations = list(MTR_NETWORK[line].keys())
    if current_sta not in stations:
        return None
        
    idx = stations.index(current_sta)
    
    if dir_key == "UP":
        if idx + 1 < len(stations):
            return stations[idx + 1]
    elif dir_key == "DOWN":
        if idx - 1 >= 0:
            return stations[idx - 1]
            
    return None


def save_results_to_txt():
    """计算已记录的所有样本平均耗时，并将 JSON 结构写入 result.txt"""
    formatted_output = {}
    
    for line, dirs in transit_records.items():
        formatted_output[line] = {"UP": {}, "DOWN": {}}
        for dir_key, segments in dirs.items():
            for seg_key, times in segments.items():
                if times:
                    avg_seconds = round(sum(times) / len(times))
                    formatted_output[line][dir_key][seg_key] = {
                        "avg_seconds": avg_seconds,
                        "samples": len(times),
                        "raw_history": times
                    }
                    
    try:
        with open("result.txt", "w", encoding="utf-8") as f:
            json.dump(formatted_output, f, indent=2, ensure_ascii=False)
        debug("💾 [测绘保存] 数据已成功更新并写入 result.txt")
    except Exception as e:
        debug(f"❌ [测绘保存] 写入 result.txt 失败: {e}")


def mainloop(trains):
    global last_arrived_snapshot, tracked_trains
    
    current_time = time.time()
    current_arrived_snapshot = {}
    
    lines_data = trains.get("lines", {}) if "lines" in trains else {}
    if not lines_data and "stations" in trains:
        lines_data = {"TWL": trains}

    for line_code, line_info in lines_data.items():
        if not line_info.get("status"):
            continue
            
        stations = line_info.get("stations", {})
        
        for sta_code, sta_data in stations.items():
            if not isinstance(sta_data, dict) or "UP" not in sta_data:
                continue
                
            sta_name = get_station_name(line_code, sta_code)
            
            for dir_key in ["UP", "DOWN"]:
                train_list = sta_data.get(dir_key, [])
                
                for train in train_list:
                    dest = train.get("dest")
                    dest_name = get_station_name(line_code, dest) if dest else "未知"
                    is_arrived = train.get("trainArrived", False) or (train.get("ttnt") == 0)
                    
                    if not dest:
                        continue
                        
                    train_key = f"{line_code}-{dir_key}-{sta_code}-{dest}"
                    
                    if is_arrived:
                        # 🌟 进站提示
                        if train_key not in last_arrived_snapshot:
                            debug(f"🟢 【进站】{line_code}线 {sta_name}({sta_code})站 [{dir_key}行] 往 {dest_name}方向 的列车已进站停靠")
                            
                        current_arrived_snapshot[train_key] = current_time
                        
                        match_idx = None
                        for idx, tracked in enumerate(tracked_trains):
                            next_sta = get_next_station(tracked["line"], tracked["dir"], tracked["from_sta"])
                            
                            if (tracked["line"] == line_code and 
                                tracked["dir"] == dir_key and 
                                next_sta == sta_code and 
                                tracked["dest"] == dest):
                                
                                duration = int(current_time - tracked["depart_time"])
                                from_name = get_station_name(line_code, tracked["from_sta"])
                                segment_name = f"{tracked['from_sta']}->{sta_code}"
                                
                                debug(f"🎯 [区段测绘] {line_code}线 [{dir_key}行] {from_name} -> {sta_name} 实际耗时: {duration} 秒 (往 {dest_name})")
                                
                                if line_code not in transit_records:
                                    transit_records[line_code] = {"UP": {}, "DOWN": {}}
                                if segment_name not in transit_records[line_code][dir_key]:
                                    transit_records[line_code][dir_key][segment_name] = []
                                    
                                transit_records[line_code][dir_key][segment_name].append(duration)
                                save_results_to_txt()
                                match_idx = idx
                                break
                                
                        if match_idx is not None:
                            tracked_trains.pop(match_idx)

    # 离站检测
    for old_key, arrived_time in last_arrived_snapshot.items():
        if old_key not in current_arrived_snapshot:
            parts = old_key.split("-")
            line_code, dir_key, sta_code, dest = parts[0], parts[1], parts[2], parts[3]
            
            sta_name = get_station_name(line_code, sta_code)
            dest_name = get_station_name(line_code, dest)
            next_sta_code = get_next_station(line_code, dir_key, sta_code)
            next_sta_name = get_station_name(line_code, next_sta_code) if next_sta_code else "终点"
            
            tracked_trains.append({
                "line": line_code,
                "dir": dir_key,
                "from_sta": sta_code,
                "dest": dest,
                "depart_time": current_time
            })
            
            # 🌟 离站提示
            debug(f"🚀 【离站】{line_code}线 {sta_name}({sta_code})站 [{dir_key}行] 往 {dest_name}方向 的列车已离站，正开往 {next_sta_name}")

    tracked_trains = [t for t in tracked_trains if current_time - t["depart_time"] < 600]
    last_arrived_snapshot = current_arrived_snapshot