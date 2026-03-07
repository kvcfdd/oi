import os
import re
import json
import requests
from bs4 import BeautifulSoup

# ================= 配置区 =================
BASE_SAVE_PATH = "E:/zzz/miao-plugin/resources/meta-gs/artifact"
JSON_PATH = os.path.join(BASE_SAVE_PATH, "data.json")
IMGS_PATH = os.path.join(BASE_SAVE_PATH, "imgs")
ALIAS_JS_PATH = os.path.join(BASE_SAVE_PATH, "alias.js")
# ==========================================

# 圣遗物部件映射规则
PIECE_MAP = {
    '4': '1',  
    '2': '2',  
    '5': '3',  
    '1': '4',  
    '3': '5'   
}

# 排除不需要加入 alias.js 的特定套装
EXCLUDE_ALIAS_SETS = ["祭风之人", "祭雷之人", "祭水之人", "祭冰之人", "祭火之人"]

def get_all_set_ids():
    url = "https://gensh.honeyhunterworld.com/fam_art_set/?lang=CHS"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    print("正在从总览页面提取圣遗物套装 ID...")
    res = requests.get(url, headers=headers, timeout=15)
    res.raise_for_status()
    
    set_ids = []
    if "sortable_data.push(" in res.text:
        parts = res.text.split("sortable_data.push(")[1:]
        for part in parts:
            array_str = part.split(");")[0].strip()
            if array_str.startswith("[") and array_str.endswith("]"):
                try:
                    data_array = json.loads(array_str)
                    for row in data_array:
                        first_col_html = row[0]
                        ids = re.findall(r'i_n(\d+)', first_col_html)
                        if ids:
                            max_id = max(int(i) for i in ids)
                            set_ids.append(max_id)
                except Exception as e:
                    print(f"  × 数组解析跳过: {e}")
    
    sorted_ids = sorted(list(set(set_ids)))
    return sorted_ids

def fetch_artifact_set(set_id):
    url = f"https://gensh.honeyhunterworld.com/i_n{set_id}/?lang=CHS"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    print(f"\n[{set_id}] 正在请求页面: {url}")
    res = requests.get(url, headers=headers, timeout=15)
    res.raise_for_status()
    html_text = res.text
    html_text = re.sub(r'<color[^>]*>', '', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'</color[^>]*>', '', html_text, flags=re.IGNORECASE)
    
    soup = BeautifulSoup(html_text, 'html.parser')
    
    data = {
        "id": str(set_id),
        "name": "",
        "idxs": {},
        "skills": {}
    }
    
    # 提取套装名称和效果
    main_table = soup.find('table', class_='main_table')
    if main_table:
        for tr in main_table.find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) < 2:
                continue
            
            key = tds[-2].text.strip()
            val = tds[-1].text.strip()
            
            if key == 'Name':
                data["name"] = val
            elif key == '1-Piece':
                data["skills"]["1"] = val.replace('1-Piece: ', '').strip()
            elif key == '2-Piece':
                data["skills"]["2"] = val.replace('2-Piece: ', '').strip()
            elif key == '4-Piece':
                data["skills"]["4"] = val.replace('4-Piece: ', '').strip()
                
    # 提取具体部件名称和ID
    skill_table = soup.find('table', class_='skill_dmg_table')
    if skill_table:
        first_tr = skill_table.find('tr')
        if first_tr:
            for td in first_tr.find_all('td')[1:]:
                a_tag = td.find('a')
                img_tag = td.find('img')
                
                if a_tag and img_tag:
                    href = a_tag.get('href', '')
                    m = re.search(r'i_n(\d+)', href)
                    if m:
                        piece_id = m.group(1)
                        piece_name = img_tag.get('alt', '').strip()
                        
                        piece_idx = None
                        if len(piece_id) >= 2:
                            digit = piece_id[-2]
                            piece_idx = PIECE_MAP.get(digit)
                        
                        if not piece_idx:
                            piece_idx = str(len(data["idxs"]) + 1)
                            
                        data["idxs"][piece_idx] = {
                            "id": piece_id,
                            "name": piece_name
                        }

    data["idxs"] = {k: data["idxs"][k] for k in sorted(data["idxs"].keys(), key=lambda x: int(x))}
    
    return data

def update_alias_js(set_name):
    if set_name in EXCLUDE_ALIAS_SETS:
        return
        
    if not os.path.exists(ALIAS_JS_PATH):
        print(f"  ! 未找到 alias.js: {ALIAS_JS_PATH}")
        return
        
    with open(ALIAS_JS_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    def insert_into_block(lines_list, block_marker, name):
        start_idx = -1
        for i, line in enumerate(lines_list):
            if block_marker in line:
                start_idx = i
                break
        if start_idx == -1: 
            return lines_list, False
            
        end_idx = -1
        for i in range(start_idx + 1, len(lines_list)):
            if lines_list[i].strip() == "}":
                end_idx = i
                break
        if end_idx == -1: 
            return lines_list, False
            
        # 查重检测
        for i in range(start_idx, end_idx):
            if re.search(rf'^\s*"?{re.escape(name)}"?\s*:', lines_list[i]):
                return lines_list, False
                
        # 处理上一行缺少逗号的情况
        prev_line_idx = end_idx - 1
        if lines_list[prev_line_idx].strip() != "" and not lines_list[prev_line_idx].strip().endswith(","):
            lines_list[prev_line_idx] = lines_list[prev_line_idx].rstrip() + ",\n"
            
        # 生成名称的前两个字
        abbr_val = name[:2]
        new_line = f'  {name}: "{abbr_val}",\n'
        lines_list.insert(end_idx, new_line)
        return lines_list, True

    lines, updated_abbr = insert_into_block(lines, "export const setAbbr =", set_name)
    lines, updated_alias = insert_into_block(lines, "export const setAlias =", set_name)
    
    if updated_abbr or updated_alias:
        with open(ALIAS_JS_PATH, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"  + 成功将 '{set_name}' 追加到 alias.js 中。")

def process_and_save(data):
    set_id = data["id"]
    set_name = data["name"]
    
    if not set_name:
        print(f"  × 未能解析到名称，跳过 ID: {set_id}")
        return
        
    os.makedirs(BASE_SAVE_PATH, exist_ok=True)
    
    # 更新 data.json
    local_data = {}
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            try:
                local_data = json.load(f)
            except json.JSONDecodeError:
                local_data = {}
            
    local_data[set_id] = data
    
    # 依照字典键(id)升序排序
    sorted_data = {k: local_data[k] for k in sorted(local_data.keys(), key=lambda x: int(x))}
    
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)
    print(f"  + 成功更新本地数据字典: {set_name}")
    
    # 更新 alias.js
    update_alias_js(set_name)
    
    # 下载图像
    img_dir = os.path.join(IMGS_PATH, set_name)
    os.makedirs(img_dir, exist_ok=True)
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for idx_str, piece_info in data["idxs"].items():
        piece_id = piece_info["id"]
        img_url = f"https://gensh.honeyhunterworld.com/img/i_n{piece_id}.webp"
        save_path = os.path.join(img_dir, f"{idx_str}.webp")
        
        # 本地如果已存在该文件则跳过请求
        if os.path.exists(save_path):
            # print(f"  - 跳过下载 (已存在): {idx_str}.webp")
            continue
            
        try:
            res = requests.get(img_url, headers=headers, stream=True, timeout=10)
            if res.status_code == 200:
                with open(save_path, 'wb') as f:
                    for chunk in res.iter_content(1024):
                        f.write(chunk)
                print(f"  √ 成功下载: {idx_str}.webp ({piece_info['name']})")
            else:
                print(f"  × 下载失败: {idx_str}.webp (HTTP {res.status_code})")
        except Exception as e:
            print(f"  × 下载报错: {idx_str}.webp ({e})")

if __name__ == "__main__":
    try:
        target_ids = get_all_set_ids()
        print(f"=== 成功提取 {len(target_ids)} 个圣遗物套装ID，开始处理 ===")
        
        for w_id in target_ids:
            try:
                set_data = fetch_artifact_set(w_id)
                process_and_save(set_data)
            except Exception as e:
                print(f"  × 处理 {w_id} 时发生错误: {e}")
                
        print("\n=== 所有圣遗物处理完毕 ===")
        
    except Exception as e:
        print(f"发生致命错误: {e}")