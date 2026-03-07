import os
import re
import json
import requests
from bs4 import BeautifulSoup

# ================= 配置区 =================
# 支持配置单个ID(整数)、多个ID(列表)、或 "all" (抓取全部3星及以上武器)
WEAPON_IDS = 15516  
BASE_SAVE_PATH = "E:/zzz/miao-plugin/resources/meta-gs/weapon"  # 基础保存路径
ALIAS_JS_PATH = "E:/zzz/miao-plugin/resources/meta-gs/weapon/alias.js"  # 别名文件路径
# ==========================================

# 副属性映射字典
SUBSTAT_MAP = {
    "Critical Damage %": "cdmg",
    "Critical Rate %": "cpct",
    "Attack %": "atkPct",
    "Health %": "hpPct",
    "Defense %": "defPct",
    "Energy Recharge %": "recharge",
    "Elemental Mastery": "mastery",
    "Physical Damage %": "phy"
}

# 预定义的属性等级严格顺序
ORDERED_LEVELS = [
    "1", "20", "40", "50", "60", "70", "80", "90",
    "20+", "40+", "50+", "60+", "70+", "80+"
]

# 英文分类名与 alias.js 中中文注释的映射关系
FAMILY_ALIAS_MAP = {
    'sword': '// 剑',
    'claymore': '// 大剑',
    'polearm': '// 枪',
    'catalyst': '// 法器',
    'bow': '// 弓'
}

def get_all_weapon_ids():
    urls = [
        "https://gensh.honeyhunterworld.com/fam_sword/?lang=CHS",
        "https://gensh.honeyhunterworld.com/fam_claymore/?lang=CHS",
        "https://gensh.honeyhunterworld.com/fam_polearm/?lang=CHS",
        "https://gensh.honeyhunterworld.com/fam_bow/?lang=CHS",
        "https://gensh.honeyhunterworld.com/fam_catalyst/?lang=CHS"
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    valid_ids = set()
    print("正在从全部分类页面提取所有武器 ID...")
    
    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=15)
            res.raise_for_status()
            
            # 使用正则抓取页面中所有的 i_n + 5位数字格式（适用于链接与图标）
            matches = re.findall(r'i_n(\d{5})', res.text)
            
            for wid_str in matches:
                # 过滤 ID 第三位是 0, 1, 2 的，保留剩下的
                if len(wid_str) >= 3 and wid_str[2] not in ['0', '1', '2']:
                    valid_ids.add(int(wid_str))
                    
        except Exception as e:
            print(f"获取 {url} 的数据时发生错误: {e}")

    sorted_ids = sorted(list(valid_ids))
    return sorted_ids

def fetch_weapon_data(weapon_id):
    url = f"https://gensh.honeyhunterworld.com/i_n{weapon_id}/?lang=CHS"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"正在请求页面: {url}")
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    html_text = response.text
    html_text = re.sub(r'<color[^>]*>', '<span class="affix-color">', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'</color[^>]*>', '</span>', html_text, flags=re.IGNORECASE)
    
    soup = BeautifulSoup(html_text, 'html.parser')

    data = {
        "id": weapon_id,
        "name": "",
        "affixTitle": "",
        "star": 0,
        "desc": "",
        "attr": {
            "atk": {},
            "bonusKey": "",
            "bonusData": {}
        },
        "materials": {},
        "affixData": {
            "text": "",
            "datas": {}
        }
    }

    # 提取基础信息
    main_table = soup.find('table', class_='main_table')
    for tr in main_table.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) < 2:
            continue
        
        key = tds[-2].text.strip()
        val_td = tds[-1]
        
        if key == 'Name':
            data["name"] = val_td.text.strip()
        elif key == 'Family':
            data["family"] = val_td.find_all('a')[1].text.strip().lower()
        elif key == 'Rarity':
            data["star"] = len(val_td.find_all('img', src=re.compile(r'star_35')))
        elif key == 'Weapon Affix':
            data["affixTitle"] = val_td.text.strip()
        elif key == 'Description':
            data["desc"] = val_td.text.strip()
        elif key == 'Substat Type':
            sub_type = val_td.text.strip()
            data["attr"]["bonusKey"] = SUBSTAT_MAP.get(sub_type, "")

    # 提取武器属性
    stat_table = soup.find('section', id='weapon_stats').find('table')
    temp_atk, temp_bonus = {}, {}
    for tr in stat_table.find_all('tr')[1:]:
        tds = tr.find_all('td')
        if len(tds) >= 3:
            lv = tds[0].text.strip()
            atk_val = tds[1].text.strip()
            bonus_val = tds[2].text.strip().replace('%', '')
            
            if atk_val: temp_atk[lv] = float(atk_val)
            if bonus_val: temp_bonus[lv] = float(bonus_val)

    for lv in ORDERED_LEVELS:
        if lv in temp_atk: data["attr"]["atk"][lv] = temp_atk[lv]
        if lv in temp_bonus: data["attr"]["bonusData"][lv] = temp_bonus[lv]

    # 提取突破材料 
    mat_td = None
    for tr in reversed(stat_table.find_all('tr')):
        tds = tr.find_all('td', rowspan='2')
        if tds:
            mat_td = tds[0]
            break
            
    if mat_td:
        mats = []
        for div in mat_td.find_all('div', class_='itempic_cont'):
            img = div.find('img')
            if not img: continue
            mat_name = img.get('alt', '').strip()
            if mat_name and mat_name != '摩拉':
                mats.append(mat_name)
        
        if len(mats) >= 3:
            data["materials"]["weapon"] = mats[0]
            data["materials"]["monster"] = mats[1]
            data["materials"]["normal"] = mats[2]

    # 提取武器特效 (affixData)
    affix_table_section = soup.find('section', id='weapon_affix')
    if affix_table_section and affix_table_section.find('table'):
        affix_table = affix_table_section.find('table')
        for rank_idx, tr in enumerate(affix_table.find_all('tr')[1:]):
            tds = tr.find_all('td')
            if len(tds) < 2: continue
            
            desc_td = tds[1]
            spans = desc_td.find_all('span', class_='affix-color')
            current_matches = [span.get_text(strip=True) for span in spans]
            
            if rank_idx == 0:
                template_soup = BeautifulSoup(str(desc_td), 'html.parser')
                for i, span in enumerate(template_soup.find_all('span', class_='affix-color')):
                    span.replace_with(f"$[{i}]")
                data["affixData"]["text"] = template_soup.get_text(strip=True)
                
            for i, match in enumerate(current_matches):
                key_str = str(i)
                if key_str not in data["affixData"]["datas"]:
                    data["affixData"]["datas"][key_str] = []
                data["affixData"]["datas"][key_str].append(match)

    return data


def download_images(weapon_id, save_dir):
    base_url = "https://gensh.honeyhunterworld.com/img"
    images = {
        "icon.webp": f"{base_url}/i_n{weapon_id}.webp",
        "awaken.webp": f"{base_url}/i_n{weapon_id}_awaken_icon.webp",
        "gacha.webp": f"{base_url}/i_n{weapon_id}_gacha_icon.webp"
    }
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for filename, url in images.items():
        file_path = os.path.join(save_dir, filename)
        # 判断文件是否存在，存在直接跳过
        if os.path.exists(file_path):
            # print(f"  - 跳过下载 (文件已存在): {filename}")
            continue
            
        try:
            res = requests.get(url, headers=headers, stream=True, timeout=10)
            if res.status_code == 200:
                with open(file_path, 'wb') as f:
                    for chunk in res.iter_content(1024):
                        f.write(chunk)
                print(f"  √ 成功下载: {filename}")
            else:
                print(f"  × 下载失败 {filename} (HTTP {res.status_code})")
        except Exception as e:
            print(f"  × 下载报错 {filename}: {e}")


def update_family_json(family, weapon_id, weapon_name, star):
    family_json_path = os.path.join(BASE_SAVE_PATH, family, "data.json")
    data = {}
    
    if os.path.exists(family_json_path):
        with open(family_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
    str_id = str(weapon_id)
    if str_id not in data:
        data[str_id] = {
            "id": weapon_id,
            "name": weapon_name,
            "star": star
        }
        sorted_data = {k: data[k] for k in sorted(data.keys(), key=lambda x: int(x))}
        with open(family_json_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_data, f, ensure_ascii=False, indent=2)
        print(f"  + 分类字典已更新: {family_json_path}")
    else:
        print(f"  - 存在同名记录跳过更新: {family_json_path}")


def update_alias_js(family, weapon_name):
    if not os.path.exists(ALIAS_JS_PATH):
        print(f"  ! 未找到 alias.js: {ALIAS_JS_PATH}")
        return

    with open(ALIAS_JS_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        if f'"{weapon_name}":' in line:
            print(f"  - 别名配置中已包含 '{weapon_name}'，跳过更新。")
            return
            
    target_comment = FAMILY_ALIAS_MAP.get(family)
    if not target_comment:
        print(f"  ! 未知的武器分类 ({family})，跳过 alias.js 插入。")
        return

    in_alias_block = False
    target_found = False
    last_entry_idx = -1
    end_of_block_idx = -1
    
    # 解析文件结构并定位插入行
    for i, line in enumerate(lines):
        if "export const alias =" in line:
            in_alias_block = True
            continue
            
        if in_alias_block:
            if line.strip() == target_comment:
                target_found = True
                last_entry_idx = i
                continue
                
            if target_found:
                if line.strip().startswith('//') or line.strip().startswith('}'):
                    end_of_block_idx = i
                    break
                elif line.strip() != "":
                    last_entry_idx = i

    if target_found and last_entry_idx != -1:
        if ":" in lines[last_entry_idx] and not lines[last_entry_idx].strip().endswith(','):
            lines[last_entry_idx] = lines[last_entry_idx].rstrip() + ",\n"
        
        new_line = f'  "{weapon_name}": ""'
        
        if lines[end_of_block_idx].strip().startswith('}'):
            new_line += '\n'
        else:
            new_line += ',\n'
            
        lines.insert(last_entry_idx + 1, new_line)
        
        with open(ALIAS_JS_PATH, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"  + 成功将 '{weapon_name}' 追加到 alias.js 的 [{target_comment}] 分类。")
    else:
        print("  ! 解析 alias.js 时未能确定插入位置。")


def process_and_save(data):
    weapon_id = data['id']
    weapon_name = data['name']
    star = data['star']
    weapon_family = data.pop('family', 'unknown')
    
    save_dir = os.path.join(BASE_SAVE_PATH, weapon_family, weapon_name)
    os.makedirs(save_dir, exist_ok=True)
    
    file_path = os.path.join(save_dir, "data.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  √ 成功生成武器数据 ({weapon_name}) -> {file_path}")
    
    download_images(weapon_id, save_dir)
    update_family_json(weapon_family, weapon_id, weapon_name, star)
    update_alias_js(weapon_family, weapon_name)


if __name__ == "__main__":
    target_ids = []
    
    if WEAPON_IDS == "all":
        target_ids = get_all_weapon_ids()
        print(f"=== ALL 源解析完成，共筛出 {len(target_ids)} 个正式武器 ===")
    elif isinstance(WEAPON_IDS, list):
        target_ids = WEAPON_IDS
    else:
        target_ids = [WEAPON_IDS]
        
    for w_id in target_ids:
        print(f"\n[{w_id}] 开始处理武器 ID: {w_id}...")
        try:
            weapon_data = fetch_weapon_data(w_id)
            process_and_save(weapon_data)
        except Exception as e:
            print(f"[{w_id}] 发生严重错误: {e}")
            
    print("\n=== 所有列队操作已完成 ===")