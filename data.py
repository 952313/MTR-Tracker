# ==============================================================================
# 港铁 (MTR) 官方线路与车站数据字典 (data.py)
# 依据 Next Train API Specification v1.6 官方文档重新整理
# 数据结构: {"车站代码": ["英文名", "繁体中文", "简体中文"]}
# ==============================================================================

# 1. 机场快线 Airport Express Line
AEL = {
    "HOK": ["Hong Kong", "香港", "香港"],
    "KOW": ["Kowloon", "九龍", "九龙"],
    "TSY": ["Tsing Yi", "青衣", "青衣"],
    "AIR": ["Airport", "機場", "机场"],
    "AWE": ["AsiaWorld Expo", "博覽館", "博览馆"]
}

# 2. 东涌线 Tung Chung Line
TCL = {
    "HOK": ["Hong Kong", "香港", "香港"],
    "KOW": ["Kowloon", "九龍", "九龙"],
    "OLY": ["Olympic", "奧運", "奥运"],
    "NAC": ["Nam Cheong", "南昌", "南昌"],
    "LAK": ["Lai King", "荔景", "荔景"],
    "TSY": ["Tsing Yi", "青衣", "青衣"],
    "SUN": ["Sunny Bay", "欣澳", "欣澳"],
    "TUC": ["Tung Chung", "東涌", "东涌"]
}

# 3. 屯马线 Tuen Ma Line
TML = {
    "WKS": ["Wu Kai Sha", "烏溪沙", "乌溪沙"],
    "MOS": ["Ma On Shan", "馬鞍山", "马鞍山"],
    "HEO": ["Heng On", "恆安", "恒安"],
    "TSH": ["Tai Shui Hang", "大水坑", "大水坑"],
    "SHM": ["Shek Mun", "石門", "石门"],
    "CIO": ["City One", "第一城", "第一城"],
    "STW": ["Sha Tin Wai", "沙田圍", "沙田围"],
    "CKT": ["Che Kung Temple", "車公廟", "车公庙"],
    "TAW": ["Tai Wai", "大圍", "大围"],
    "HIK": ["Hin Keng", "顯徑", "显径"],
    "DIH": ["Diamond Hill", "鑽石山", "钻石山"],
    "KAT": ["Kai Tak", "啟德", "启德"],
    "SUW": ["Sung Wong Toi", "宋皇臺", "宋皇台"],
    "TKW": ["To Kwa Wan", "土瓜灣", "土瓜湾"],
    "HOM": ["Ho Man Tin", "何文田", "何文田"],
    "HUH": ["Hung Hom", "紅磡", "红磡"],
    "ETS": ["East Tsim Sha Tsui", "尖東", "尖东"],
    "AUS": ["Austin", "柯士甸", "柯士甸"],
    "NAC": ["Nam Cheong", "南昌", "南昌"],
    "MEF": ["Mei Foo", "美孚", "美孚"],
    "TWW": ["Tsuen Wan West", "荃灣西", "荃湾西"],
    "KSR": ["Kam Sheung Road", "錦上路", "锦上路"],
    "YUL": ["Yuen Long", "元朗", "元朗"],
    "LOP": ["Long Ping", "朗屏", "朗屏"],
    "TIS": ["Tin Shui Wai", "天水圍", "天水围"],
    "SIH": ["Siu Hong", "兆康", "兆康"],
    "TUM": ["Tuen Mun", "屯門", "屯门"]
}

# 4. 将军澳线 Tseung Kwan O Line
TKL = {
    "NOP": ["North Point", "北角", "北角"],
    "QUB": ["Quarry Bay", "鰂魚涌", "鲗鱼涌"],
    "YAT": ["Yau Tong", "油塘", "油塘"],
    "TIK": ["Tiu Keng Leng", "調景嶺", "调景岭"],
    "TKO": ["Tseung Kwan O", "將軍澳", "将军澳"],
    "LHP": ["LOHAS Park", "康城", "康城"],
    "HAH": ["Hang Hau", "坑口", "坑口"],
    "POA": ["Po Lam", "寶琳", "宝琳"]
}

# 5. 东铁线 East Rail Line
EAL = {
    "ADM": ["Admiralty", "金鐘", "金钟"],
    "EXC": ["Exhibition Centre", "會展", "会展"],
    "HUH": ["Hung Hom", "紅磡", "红磡"],
    "MKK": ["Mong Kok East", "旺角東", "旺角东"],
    "KOT": ["Kowloon Tong", "九龍塘", "九龙塘"],
    "TAW": ["Tai Wai", "大圍", "大围"],
    "SHT": ["Sha Tin", "沙田", "沙田"],
    "FOT": ["Fo Tan", "火炭", "火炭"],
    "RAC": ["Racecourse", "馬場", "马场"],
    "UNI": ["University", "大學", "大学"],
    "TAP": ["Tai Po Market", "大埔墟", "大埔墟"],
    "TWO": ["Tai Wo", "太和", "太和"],
    "FAN": ["Fanling", "粉嶺", "粉岭"],
    "SHS": ["Sheung Shui", "上水", "上水"],
    "LOW": ["Lo Wu", "羅湖", "罗湖"],
    "LMC": ["Lok Ma Chau", "落馬洲", "落马洲"]
}

# 6. 南港岛线 South Island Line
SIL = {
    "ADM": ["Admiralty", "金鐘", "金钟"],
    "OCP": ["Ocean Park", "海洋公園", "海洋公园"],
    "WCH": ["Wong Chuk Hang", "黃竹坑", "黄竹坑"],
    "LET": ["Lei Tung", "利東", "利东"],
    "SOH": ["South Horizons", "海怡半島", "海怡半岛"]
}

# 7. 荃湾线 Tsuen Wan Line
TWL = {
    "CEN": ["Central", "中環", "中环"],
    "ADM": ["Admiralty", "金鐘", "金钟"],
    "TST": ["Tsim Sha Tsui", "尖沙咀", "尖沙咀"],
    "JOR": ["Jordan", "佐敦", "佐敦"],
    "YMT": ["Yau Ma Tei", "油麻地", "油麻地"],
    "MOK": ["Mong Kok", "旺角", "旺角"],
    "PRE": ["Prince Edward", "太子", "太子"],
    "SSP": ["Sham Shui Po", "深水埗", "深水埗"],
    "CSW": ["Cheung Sha Wan", "長沙灣", "长沙湾"],
    "LCK": ["Lai Chi Kok", "荔枝角", "荔枝角"],
    "MEF": ["Mei Foo", "美孚", "美孚"],
    "LAK": ["Lai King", "荔景", "荔景"],
    "KWF": ["Kwai Fong", "葵芳", "葵芳"],
    "KWH": ["Kwai Hing", "葵興", "葵兴"],
    "TWH": ["Tai Wo Hau", "大窩口", "大窝口"],
    "TSW": ["Tsuen Wan", "荃灣", "荃湾"]
}

# 荃湾线各方向使用的月台；UP 为 TSW -> CEN，DOWN 为 CEN -> TSW
TWL_PLATFORMS = {
    "UP": {
        "CEN": ["1", "2"],
        "ADM": ["4"],
        "TST": ["2"],
        "JOR": ["2"],
        "YMT": ["2"],
        "MOK": ["2"],
        "PRE": ["4"],
        "SSP": ["2"],
        "CSW": ["2"],
        "LCK": ["2"],
        "MEF": ["2"],
        "LAK": ["2"],
        "KWF": ["2"],
        "KWH": ["2"],
        "TWH": ["2"],
        "TSW": ["2"]
    },
    "DOWN": {
        "CEN": ["1", "2"],
        "ADM": ["1"],
        "TST": ["1"],
        "JOR": ["1"],
        "YMT": ["1"],
        "MOK": ["1"],
        "PRE": ["1"],
        "SSP": ["1"],
        "CSW": ["1"],
        "LCK": ["1"],
        "MEF": ["1"],
        "LAK": ["1"],
        "KWF": ["1"],
        "KWH": ["1"],
        "TWH": ["1"],
        "TSW": ["1"]
    }
}

# 8. 港岛线 Island Line
ISL = {
    "KET": ["Kennedy Town", "堅尼地城", "坚尼地城"],
    "HKU": ["HKU", "香港大學", "香港大学"],
    "SYP": ["Sai Ying Pun", "西營盤", "西营盘"],
    "SHW": ["Sheung Wan", "上環", "上环"],
    "CEN": ["Central", "中環", "中环"],
    "ADM": ["Admiralty", "金鐘", "金钟"],
    "WAC": ["Wan Chai", "灣仔", "湾仔"],
    "CAB": ["Causeway Bay", "銅鑼灣", "铜锣湾"],
    "TIH": ["Tin Hau", "天后", "天后"],
    "FOH": ["Fortress Hill", "炮台山", "炮台山"],
    "NOP": ["North Point", "北角", "北角"],
    "QUB": ["Quarry Bay", "鰂魚涌", "鲗鱼涌"],
    "TAK": ["Tai Koo", "太古", "太古"],
    "SWH": ["Sai Wan Ho", "西灣河", "西湾河"],
    "SKW": ["Shau Kei Wan", "筲箕灣", "筲箕湾"],
    "HFC": ["Heng Fa Chuen", "杏花邨", "杏花邨"],
    "CHW": ["Chai Wan", "柴灣", "柴湾"]
}

# 9. 观塘线 Kwun Tong Line
KTL = {
    "WHA": ["Whampoa", "黃埔", "黄埔"],
    "HOM": ["Ho Man Tin", "何文田", "何文田"],
    "YMT": ["Yau Ma Tei", "油麻地", "油麻地"],
    "MOK": ["Mong Kok", "旺角", "旺角"],
    "PRE": ["Prince Edward", "太子", "太子"],
    "SKM": ["Shek Kip Mei", "石硤尾", "石硖尾"],
    "KOT": ["Kowloon Tong", "九龍塘", "九龙塘"],
    "LOF": ["Lok Fu", "樂富", "乐富"],
    "WTS": ["Wong Tai Sin", "黃大仙", "黄大仙"],
    "DIH": ["Diamond Hill", "鑽石山", "钻石山"],
    "CHH": ["Choi Hung", "彩虹", "彩虹"],
    "KOB": ["Kowloon Bay", "九龍灣", "九龙湾"],
    "NTK": ["Ngau Tau Kok", "牛頭角", "牛头角"],
    "KWT": ["Kwun Tong", "觀塘", "观塘"],
    "LAT": ["Lam Tin", "藍田", "蓝田"],
    "YAT": ["Yau Tong", "油塘", "油塘"],
    "TIK": ["Tiu Keng Leng", "調景嶺", "调景岭"]
}

# ==============================================================================
# 总网络列表
# ==============================================================================
MTR_NETWORK = {
    "AEL": AEL,
    "TCL": TCL,
    "TML": TML,
    "TKL": TKL,
    "EAL": EAL,
    "SIL": SIL,
    "TWL": TWL,
    "ISL": ISL,
    "KTL": KTL
}