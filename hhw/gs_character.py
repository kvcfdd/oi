import requests
from bs4 import BeautifulSoup
import json
import re
import os
import urllib.parse

# ================= 配置项 =================
# 基础输出路径
OUTPUT_BASE_DIR = "E:/zzz/miao-plugin/resources/meta-gs/character"

# 图片下载配置
# True: 强制下载并覆盖
# False: 仅本地不存在时才下载
OVERWRITE_IMAGES = False

# 需要抓取的角色ID目标配置：
# "all"   : 抓取所有角色
# [...]   : 数组格式，抓取指定的角色ID 例: [10000130, 10000131]
# 1 (整数) : 抓取全站解析到的ID最大的前N个角色,一般是最新角色
TARGET_IDS = 1
# 是否插入附加机制内容
INSERT_EXTERNAL_LINKS = True
# 是否清理技能描述中的非标HTML标签，包含span、u、nobr，前面的某次提交中喵喵已支持标签样式，如需实现网页般的颜色区分可关闭此项
STRIP_HTML_TAGS = True
# 头
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
    # "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    # "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    # "Referer": "https://gensh.honeyhunterworld.com/",
    # "Connection": "keep-alive",
    # "Upgrade-Insecure-Requests": "1",
    # "Sec-Fetch-Dest": "document",
    # "Sec-Fetch-Mode": "navigate",
    # "Sec-Fetch-Site": "same-origin",
    # "Sec-Fetch-User": "?1"
}
# 缓存已下载的外链页面数据
GLOBAL_HYP_CACHE = {}
# =========================================

# 旅行者技能映射
TRAVELER_SKILL_MAP = {
    "pyro": {"a": 100551, "e": 10097, "q": 10098},
    "hydro": {"a": 100552, "e": 10087, "q": 10088},
    "anemo": {"a": 100553, "e": 10067, "q": 10068},
    "geo": {"a": 100555, "e": 10077, "q": 10078},
    "electro": {"a": 100556, "e": 10602, "q": 10605},
    "dendro": {"a": 100557, "e": 10117, "q": 10118}
}

# 旅行者材料获取的强制属性顺序
TRAVELER_MAT_ORDER = ["anemo", "pyro", "hydro", "geo", "electro", "dendro"]

# 保持整数或原小数
def format_number(val_str):
    try:
        f = float(val_str.replace(',', ''))
        return int(f) if f.is_integer() else f
    except ValueError:
        return 0

# 纯粹提取文本中的所有数字
def extract_numbers(text):
    nums = re.findall(r'\d+\.?\d*', text)
    return [format_number(n) for n in nums]

# 按最外层的 '+' 分割表达式
def split_by_outer_plus(text):
    parts = []
    paren_level = 0
    current_part = []
    for char in text:
        if char == '(':
            paren_level += 1
            current_part.append(char)
        elif char == ')':
            paren_level -= 1
            current_part.append(char)
        elif char == '+' and paren_level == 0:
            parts.append("".join(current_part))
            current_part = []
        else:
            current_part.append(char)
    if current_part:
        parts.append("".join(current_part))
    return [p for p in parts if p]

# 解析技能倍率表达式得出第一组数值
def parse_skill_expr(text):
    text_clean = re.sub(r'[^\d\.\+\-\*\/\(\)]', '', text)
    
    if not text_clean:
        return 0

    if '/' in text_clean:
        nums = extract_numbers(text)
        return nums[0] if len(nums) == 1 else (nums if nums else 0)
        
    if not any(c in text_clean for c in '+*()'):
        nums = extract_numbers(text)
        return nums[0] if len(nums) == 1 else (nums if nums else 0)
        
    parts = split_by_outer_plus(text_clean)
    
    def safe_eval(expr):
        try:
            if not re.match(r'^[\d\.\+\-\*\/\(\)]+$', expr):
                nums = extract_numbers(expr)
                return nums[0] if len(nums) == 1 else (nums if nums else 0)
            val = eval(expr)
            val = round(val, 4)
            return int(val) if val.is_integer() else val
        except Exception:
            nums = extract_numbers(expr)
            return nums[0] if len(nums) == 1 else (nums if nums else 0)

    if len(parts) == 1:
        return safe_eval(parts[0])
    else:
        all_pure_number = True
        for p in parts:
            if any(c in p for c in '*()'):
                all_pure_number = False
                break
        
        if all_pure_number:
            total = sum(safe_eval(p) for p in parts)
            val = round(total, 4)
            return int(val) if val.is_integer() else val
        else:
            return [safe_eval(p) for p in parts]

# 技能倍率中文单位提取与替换
def process_skill_string(val):
    head_match = re.search(r'^([\u4e00-\u9fa5]+)', val)
    tail_match = re.search(r'([\u4e00-\u9fa5]+)$', val)
    
    head_cn = head_match.group(1) if head_match else ""
    tail_cn = tail_match.group(1) if tail_match else ""
    
    start_idx = len(head_cn)
    end_idx = len(val) - len(tail_cn)
    middle = val[start_idx:end_idx]
    
    has_middle_cn = bool(re.search(r'[\u4e00-\u9fa5]', middle))
    
    unit = ""
    new_val = val
    
    if not has_middle_cn:
        if head_cn and tail_cn:
            unit = tail_cn
            new_val = val[:-len(tail_cn)]
        elif tail_cn:
            unit = tail_cn
            new_val = val[:-len(tail_cn)]
        elif head_cn:
            unit = head_cn
            new_val = val[len(head_cn):]

    new_val = new_val.replace("生命值上限", "HP") \
                     .replace("最大生命值", "HP") \
                     .replace("攻击力", "攻击") \
                     .replace("防御力", "防御") \
                     .replace("元素精通", "精通")
                     
    return unit, new_val.strip()

# 获取全局角色映射字典
def get_character_url_map():
    print("正在获取全角色基础数据映射列表...")
    url = "https://gensh.honeyhunterworld.com/fam_chars/?lang=CHS"
    
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS)
        response.encoding = 'utf-8'
        html_text = response.text
        match_data_block = re.search(r'sortable_data\.push\(\[(.*?)\]\);', html_text, re.DOTALL)
        
        if not match_data_block:
            print("[错误] 未能在页面中找到 sortable_data 数据列表。")
            return {}

        data_block = match_data_block.group(1)
        row_groups = re.findall(r'\[(.*?)\]', data_block, re.DOTALL)

        url_map = {}
        # 过滤假数据
        STOP_KEY = "mavuika_901"
        # 过滤人偶，空
        FILTER_KEYS = ["playerboy_005", "mannequingirl_118", "mannequinboy_117"]
        for row_content in row_groups:
            match_href = re.search(r'href=[\\"]+\/?\\/?([a-zA-Z0-9_]+_(\d{3}))\/?\\/?\?lang=CHS', row_content)
            if match_href:
                path = match_href.group(1)
                id_str = match_href.group(2)
                if path == STOP_KEY: break
                if path in FILTER_KEYS: continue

                char_id = 10000000 + int(id_str)
                clean_url = f"https://gensh.honeyhunterworld.com/{path}/?lang=CHS"
                url_map[char_id] = (clean_url, path)
            
        print(f"映射列表获取成功，共解析到 {len(url_map)} 个角色链接。")
        return url_map

    except Exception as e:
        print(f"[错误] 获取映射列表时发生异常: {e}")
        return {}

def download_image(url, save_path):
    img_headers = DEFAULT_HEADERS.copy()
    img_headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    
    try:
        res = requests.get(url, headers=img_headers, timeout=15)
        if res.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(res.content)
            return True
        else:
            print(f"      [失败] 图片下载失败，状态码 {res.status_code}: {url}")
            return False
    except Exception as e:
        print(f"      [错误] 图片下载发生异常: {e} -> {url}")
        return False


def fetch_and_parse(url, target_id, char_path_slug):
    print(f"开始抓取 ID: {target_id} | Path: {char_path_slug}")
    response = requests.get(url, headers=DEFAULT_HEADERS)
    response.encoding = 'utf-8'
    
    html_text = response.text
    html_text = re.sub(r'<color=(#[a-zA-Z0-9]+)>', r'<span class="honey-color" data-color="\1">', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'</color>', r'</span>', html_text, flags=re.IGNORECASE)
    
    soup = BeautifulSoup(html_text, 'html.parser')

    namecard_id = None
    nc_match = re.search(r'href=\\"\\/(i_n?\d+)\\/((?!href=\\"\\/i_).)*?fam_nameplate', html_text, re.DOTALL)
    
    if nc_match:
        namecard_id = nc_match.group(1)

    is_traveler = (char_path_slug == 'playergirl_007')
    char_id = 20000000 if is_traveler else target_id
    char_id_str = str(char_id)[-3:]

    name, title, allegiance, weapon, base_elem, desc, cncv, jpcv = "", "", "", "", "", "", "", ""
    astro_intro, astro_discov, astro = "", "", "???"
    star = 5
    birth_month, birth_day = "", ""
    char_mats, skill_mats = {}, {}
    traveler_talents_list = []
    
    main_table = soup.find('table', class_='main_table')
    if not main_table:
        print(f"警告：无法找到 {target_id} 的主表格数据。")
        return []
        
    tbody_trs = main_table.find('tbody').find_all('tr', recursive=False) if main_table.find('tbody') else main_table.find_all('tr', recursive=False)
    
    for row in tbody_trs:
        cells = row.find_all('td', recursive=False)
        if len(cells) < 2: continue
            
        key = cells[-2].text.strip()
        val_td = cells[-1]
        val_text = val_td.text.strip()
        
        if key == "Name": name = val_text
        elif key == "Title": title = val_text
        elif key == "Occupation": allegiance = val_text
        elif key == "Constellation (Introduced)": astro_intro = val_text
        elif key == "Constellation (Discovered)": astro_discov = val_text
        elif key == "Chinese Seuyu": cncv = val_text
        elif key == "Japanese Seuyu": jpcv = val_text
        elif key == "Description": desc = val_text
        elif key == "Month of Birth": birth_month = val_text
        elif key == "Day of Birth": birth_day = val_text
        elif key == "Rarity":
            count = len([img for img in val_td.find_all('img') if 'star_35' in img.get('src', '')])
            star = count if count > 0 else 5
        elif key == "Weapon":
            w_match = re.search(r'weapon_types/(.*?)_35', str(val_td))
            weapon = w_match.group(1) if w_match else ""
        elif key == "Element":
            e_match = re.search(r'element/(.*?)_35', str(val_td))
            base_elem = e_match.group(1) if e_match else ""
        elif key == "Character Ascension Materials":
            alts = []
            for img in val_td.find_all('img'):
                alt = img.get('alt', '')
                if alt and alt != '摩拉' and alt not in alts: alts.append(alt)
            char_mats = {
                "gem": alts[3] if len(alts) > 3 else "",
                "boss": alts[4] if len(alts) > 4 else "",
                "specialty": alts[5] if len(alts) > 5 else "",
                "normal": alts[8] if len(alts) > 8 else ""
            }
        elif key == "Skill Ascension Materials":
            alts = []
            for img in val_td.find_all('img'):
                alt = img.get('alt', '')
                if alt and alt != '摩拉' and alt != '智识之冕': 
                    alts.append(alt)
            if is_traveler:
                for idx, alt in enumerate(alts):
                    if "的哲学" in alt:
                        weekly = alts[idx+1] if idx + 1 < len(alts) else ""
                        if not any(x["talent"] == alt for x in traveler_talents_list):
                            traveler_talents_list.append({"talent": alt, "weekly": weekly})
            else:
                skill_mats = {
                    "talent": alts[2] if len(alts) > 2 else "",
                    "weekly": alts[3] if len(alts) > 3 else ""
                }

    birth = f"{birth_month}-{birth_day}" if birth_month else ""
    if birth == "0-0":
        birth = "-"

    # 根据优先级合并 astro
    if astro_intro and astro_intro != "???":
        astro = astro_intro
    elif astro_discov and astro_discov != "???":
        astro = astro_discov
    else:
        astro = "???"

    if is_traveler:
        title = "异界的旅人"
        birth = "-"
        cncv = "宴宁/鹿喑"
        jpcv = "悠木碧/堀江瞬"
        char_mats = {
            "gem": "璀璨原钻",
            "specialty": "风车菊",
            "normal": "不祥的面具"
        }
            
    stat_map = {
        "Bonus CritRate%": "cpct", "Bonus CritDMG%": "cdmg", "Bonus Heal": "heal",
        "Bonus ER": "recharge", "Bonus EM": "mastery", "Bonus HP%": "hpPct",
        "Bonus Atk%": "atkPct", "Bonus Def": "defPct", "Bonus Phys%": "phy"
    }
    
    stat_table = soup.find('table', class_='stat_table')
    grow_attr_key, attr_data, baseAttr, growAttr = "dmg", {}, {}, {}
    
    if stat_table:
        thead_tds = stat_table.find('thead').find('tr').find_all('td', recursive=False)
        bonus_header = thead_tds[6].text.strip() if len(thead_tds) > 6 else ""
        grow_attr_key = stat_map.get(bonus_header, "dmg")
        
        raw_attr_details = {}
        stat_trs = stat_table.find('tbody').find_all('tr', recursive=False) if stat_table.find('tbody') else stat_table.find_all('tr', recursive=False)
        for row in stat_trs:
            cells = row.find_all('td', recursive=False)
            if len(cells) < 7: continue
            lv = cells[0].text.strip()
            if lv == "Lv": continue
            
            hp = format_number(cells[1].text.strip())
            atk = format_number(cells[2].text.strip())
            df = format_number(cells[3].text.strip())
            bonus = format_number(cells[6].text.strip().replace('%', ''))
            raw_attr_details[lv] = [hp, atk, df, bonus]
            
        if "100" in raw_attr_details:
            baseAttr = {
                "hp": raw_attr_details["100"][0],
                "atk": raw_attr_details["100"][1],
                "def": raw_attr_details["100"][2]
            }
            growAttr = {"key": grow_attr_key, "value": raw_attr_details["100"][3]}
        
        lv_order = ["1", "20", "40", "50", "60", "70", "80", "90", "100", 
                    "20+", "40+", "50+", "60+", "70+", "80+", "90+"]
        ordered_attr_details = {lv: raw_attr_details[lv] for lv in lv_order if lv in raw_attr_details}
        attr_data = {"keys": ["hpBase", "atkBase", "defBase", grow_attr_key], "details": ordered_attr_details}

    def clean_desc(td_html):
        td_html = re.sub(r'[\r\n\t]+', '', td_html)
        if STRIP_HTML_TAGS:
            td_html = re.sub(r'\{LINK#[^\}]+\}', '', td_html)
        else:
            td_html = re.sub(r'\{LINK#[^\}]+\}([^<]+)', r'<u>\1</u>', td_html)
            td_html = re.sub(r'\{LINK#[^\}]+\}', '', td_html)

        def fix_i_tag(m):
            return "<i>" + re.sub(r'\s*<br\s*/?>\s*', '</i><br><i>', m.group(1), flags=re.IGNORECASE) + "</i>"
        td_html = re.sub(r'<i>(.*?)</i>', fix_i_tag, td_html, flags=re.IGNORECASE)
        def fix_span_tag(m):
            attrs = m.group(1)
            inner = m.group(2)
            replaced = re.sub(r'\s*<br\s*/?>\s*', f'</span><br><span {attrs}>', inner, flags=re.IGNORECASE)
            return f'<span {attrs}>{replaced}</span>'
        td_html = re.sub(r'<span\s+([^>]+)>(.*?)</span>', fix_span_tag, td_html, flags=re.IGNORECASE)

        lines = re.split(r'\s*<br\s*/?>\s*', td_html, flags=re.IGNORECASE)
        cleaned = []
        
        allowed_tags = ['h3', 'i'] if STRIP_HTML_TAGS else ['h3', 'i', 'nobr', 'span', 'u']
        yellow_colors = ['#FFD780FF', '#FFD780']
        
        for line in lines:
            line = line.strip()
            if not line: continue
            if not re.sub(r'<[^>]+>', '', line).strip():
                continue

            line_soup = BeautifulSoup(line, 'html.parser')
            
            for span in line_soup.find_all('span', class_='honey-color'):
                color = span.get('data-color', '').upper()
                if color in yellow_colors:
                    if span.text == line_soup.text:
                        span.name = 'h3'
                    else:
                        span.name = 'nobr'
                    del span['class']
                    del span['data-color']
                else:
                    span.name = 'span'
                    span['style'] = f"color:{color};"
                    del span['class']
                    del span['data-color']
                    
            for tag in line_soup.find_all(True):
                if tag.name not in allowed_tags:
                    tag.unwrap()
                    
            res = str(line_soup).strip()
            if res: cleaned.append(res)

        cut_idx = -1
        for i, line in enumerate(cleaned):
            plain_text = re.sub(r'<[^>]+>', '', line).strip()
            if "Buffed State:" in plain_text:
                cut_idx = i
                break
                
        if cut_idx != -1:
            cleaned = cleaned[cut_idx + 1:]
            
        return cleaned

    bili_flavor_texts = {'e': [], 'q': []}
    bili_fetched = False

    def fetch_bili_flavor():
        nonlocal bili_fetched
        if bili_fetched: return
        bili_fetched = True
        if is_traveler or not name: return
        bili_url = "https://wiki.biligame.com/ys/" + urllib.parse.quote(name)
        try:
            b_res = requests.get(bili_url, headers=DEFAULT_HEADERS, timeout=10)
            if b_res.status_code == 200:
                b_soup = BeautifulSoup(b_res.text, 'html.parser')
                b_cols = b_soup.find_all('div', class_='col-sm-9')
                if len(b_cols) > 1:
                    for i_tag in b_cols[1].find_all('i'):
                        inner_html = str(i_tag.decode_contents())
                        for l in re.split(r'\s*<br\s*/?>\s*', inner_html):
                            l_clean = re.sub(r'<[^>]+>', '', l.strip())
                            if l_clean:
                                bili_flavor_texts['e'].append(f"<i>{l_clean}</i>")
                if len(b_cols) > 2:
                    for i_tag in b_cols[2].find_all('i'):
                        inner_html = str(i_tag.decode_contents())
                        for l in re.split(r'\s*<br\s*/?>\s*', inner_html):
                            l_clean = re.sub(r'<[^>]+>', '', l.strip())
                            if l_clean:
                                bili_flavor_texts['q'].append(f"<i>{l_clean}</i>")
        except Exception as e:
            print(f"      [警告] 请求B站WIKI失败: {e}")

    injected_hyp_links = set()
    def extract_and_fetch_links(soup_obj):
        effects = []
        for a_tag in soup_obj.find_all('a'):
            href = a_tag.get('href', '')
            if '/hyp_' in href:
                name = a_tag.get_text(strip=True)
                u_tag = BeautifulSoup('', 'html.parser').new_tag('u')
                for child in list(a_tag.contents):
                    u_tag.append(child)
                a_tag.replace_with(u_tag)
                if not INSERT_EXTERNAL_LINKS: continue
                if href not in GLOBAL_HYP_CACHE:
                    GLOBAL_HYP_CACHE[href] = None
                    full_url = "https://gensh.honeyhunterworld.com" + href
                    try:
                        r = requests.get(full_url, headers=DEFAULT_HEADERS, timeout=10)
                        if r.status_code == 200:
                            r.encoding = 'utf-8'
                            h_text = r.text
                            h_text = re.sub(r'<color=(#[a-zA-Z0-9]+)>', r'<span class="honey-color" data-color="\1">', h_text, flags=re.IGNORECASE)
                            h_text = re.sub(r'</color>', r'</span>', h_text, flags=re.IGNORECASE)
                            h_soup = BeautifulSoup(h_text, 'html.parser')
                            
                            tds = h_soup.find_all('td')
                            desc_html = ""
                            for i, td in enumerate(tds):
                                if td.get_text(strip=True) == "Description" and i + 1 < len(tds):
                                    desc_html = tds[i+1].decode_contents()
                                    break
                            
                            if desc_html:
                                real_name = name
                                main_img = h_soup.find('img', class_='main_image')
                                if main_img and main_img.get('alt'):
                                    real_name = main_img.get('alt').strip()
                                inner_soup = BeautifulSoup(desc_html, 'html.parser')
                                nested_effs = extract_and_fetch_links(inner_soup)
                                
                                GLOBAL_HYP_CACHE[href] = {
                                    "href": href,
                                    "name": real_name,
                                    "desc_html": inner_soup.decode_contents(),
                                    "nested": nested_effs
                                }
                    except Exception as e:
                        print(f"      [警告] 请求外链机制数据失败 {href}: {e}")
                if GLOBAL_HYP_CACHE.get(href):
                    effects.append(GLOBAL_HYP_CACHE[href])
                    
        return effects

    def process_skill_desc(desc_td):
        effects = extract_and_fetch_links(desc_td)
        main_desc = clean_desc(desc_td.decode_contents())
        flat_effects = []
        def add_effs(eff_list):
            for eff in eff_list:
                if not any(e['href'] == eff['href'] for e in flat_effects):
                    flat_effects.append(eff)
                add_effs(eff.get('nested', []))
        
        add_effs(effects)
        effects_lines = []
        for eff in flat_effects:
            href = eff['href']
            if href not in injected_hyp_links:
                injected_hyp_links.add(href)
                cleaned_eff_desc = clean_desc(eff['desc_html'])
                if cleaned_eff_desc:
                    effects_lines.append(f"<h3>● {eff['name']}</h3>")
                    effects_lines.extend(cleaned_eff_desc)
            
        if effects_lines:
            insert_index = len(main_desc)
            for i in range(len(main_desc)-1, -1, -1):
                line = main_desc[i].strip()
                soup_line = BeautifulSoup(line, 'html.parser')
                is_pure_i = True
                for child in soup_line.contents:
                    if getattr(child, 'name', None) != 'i':
                        if str(child).strip() != '':
                            is_pure_i = False
                            break
                if is_pure_i and len(soup_line.contents) > 0:
                    insert_index = i
                else:
                    break
            main_desc = main_desc[:insert_index] + effects_lines + main_desc[insert_index:]
            
        return main_desc

    skill_containers = []
    if is_traveler:
        for i in range(1, 10): 
            sec = soup.find('section', id=f'skillset_{i}')
            if sec:
                elem_h3 = sec.find('h3')
                elem_name = elem_h3.text.strip().lower() if elem_h3 else f"element_{i}"
                skill_containers.append((elem_name, sec))
    else:
        sec = soup.find('section', id='char_skills')
        if sec:
            skill_containers.append((None, sec))

    all_results = []

    for idx, (sub_folder_name, container) in enumerate(skill_containers):
        elem_name = sub_folder_name if sub_folder_name else base_elem.lower()

        cur_skill_mats = skill_mats
        cur_talentId_map = {}
        cur_talent_elem = {}
        cur_skill_map = {}

        if is_traveler:
            if elem_name in TRAVELER_MAT_ORDER:
                mat_idx = TRAVELER_MAT_ORDER.index(elem_name)
                if mat_idx < len(traveler_talents_list):
                    cur_skill_mats = traveler_talents_list[mat_idx]
                else:
                    cur_skill_mats = {"talent": "", "weekly": ""}
            else:
                cur_skill_mats = {"talent": "", "weekly": ""}
                
            cur_skill_map = TRAVELER_SKILL_MAP.get(elem_name, {})
            cur_talentId_map = {str(v): k for k, v in cur_skill_map.items()}
            if "e" in cur_skill_map and "q" in cur_skill_map:
                cur_talent_elem = {
                    str(cur_skill_map["e"]): elem_name,
                    str(cur_skill_map["q"]): elem_name
                }

        cur_materials = {**char_mats, **cur_skill_mats}
        if is_traveler and "boss" in cur_materials:
            del cur_materials["boss"]

        active_tables, passive_tables, cons_tables = [], [], []
        current_category = None
        for child in container.children:
            if child.name == 'span' and 'delim' in child.get('class', []):
                text = child.get_text(strip=True).lower()
                if 'active' in text: current_category = 'active'
                elif 'passive' in text: current_category = 'passive'
                elif 'constellation' in text: current_category = 'cons'
            elif child.name == 'table' and 'skill_table' in child.get('class', []):
                if current_category == 'active': active_tables.append(child)
                elif current_category == 'passive': passive_tables.append(child)
                elif current_category == 'cons': cons_tables.append(child)

        target_active_tables = {}
        extra_passive_tables = []

        valid_active_tables = []
        for t in active_tables:
            a_tag = t.find('a')
            if not a_tag:
                extra_passive_tables.append((t, None))
                continue
            
            href = a_tag.get('href', '')
            match = re.search(r'/s_(\d+)', href)
            if not match:
                extra_passive_tables.append((t, None))
                continue
                
            full_id_str = match.group(1)
            if full_id_str.endswith('01'):
                skill_id_str = full_id_str[:-2]
            else:
                skill_id_str = full_id_str
                
            t_id = int(skill_id_str)
            valid_active_tables.append((t, t_id, skill_id_str))

        if len(valid_active_tables) == 3:
            letters = ['a', 'e', 'q']
            for i, (t, t_id, _) in enumerate(valid_active_tables):
                target_active_tables[letters[i]] = (t, t_id)
        else:
            for t, t_id, skill_id_str in valid_active_tables:
                if skill_id_str.endswith('1'):
                    letter = 'a'
                elif skill_id_str.endswith('2'):
                    letter = 'e'
                elif skill_id_str.endswith('9'):
                    letter = 'q'
                else:
                    letter = None
                    
                if letter and letter not in target_active_tables:
                    target_active_tables[letter] = (t, t_id)
                else:
                    extra_passive_tables.append((t, t_id))

        def parse_dmg_table(dmg_table, letter_for_nahida=None, is_special=False):
            t_tables = []
            parsed_data = {}
            if not dmg_table:
                return t_tables, parsed_data
                
            tds = [td.get_text(strip=True) for td in dmg_table.find_all('td')]
            cols = 16
            for idx_td, text in enumerate(tds):
                if text == 'Lv15':
                    cols = idx_td + 1
                    break
            
            rows = [tds[k:k+cols] for k in range(cols, len(tds), cols)]
            nahida_q_counter = {"火": 0, "雷": 0, "水": 0}

            for row in rows:
                if not row or len(row) < 2: continue
                row_name = row[0]
                if not row_name: continue

                if char_path_slug == 'nahida_073' and letter_for_nahida == 'q':
                    for elem_key in ["火", "雷", "水"]:
                        if elem_key in row_name:
                            nahida_q_counter[elem_key] += 1
                            count = nahida_q_counter[elem_key]
                            row_name = re.sub(f'{elem_key}[：:]\\s*', f'{elem_key}{count}', row_name)
                            break

                str_values = row[1:]
                nahida_q_unit_prefix = ""
                if char_path_slug == 'nahida_073' and letter_for_nahida == 'q':
                    match_role = re.search(r'^([12]名角色)', str_values[0])
                    if match_role:
                        nahida_q_unit_prefix = match_role.group(1)
                        str_values = [val.replace(nahida_q_unit_prefix, "").strip() for val in str_values]

                if is_special:
                    t_tables.append({
                        "name": row_name,
                        "unit": nahida_q_unit_prefix,
                        "isSame": True,
                        "values": [str_values[0]]
                    })
                    continue

                is_same = len(set(str_values)) == 1
                
                if is_same:
                    t_tables.append({
                        "name": row_name,
                        "unit": nahida_q_unit_prefix,
                        "isSame": True,
                        "values": [str_values[0]]
                    })
                    continue 
                else:
                    if nahida_q_unit_prefix:
                        t_tables.append({
                            "name": row_name,
                            "unit": nahida_q_unit_prefix,
                            "isSame": False,
                            "values": str_values
                        })
                        processed_values = str_values
                    else:
                        unit_val = ""
                        processed_values = []
                        for idx_val, val in enumerate(str_values):
                            u, n_val = process_skill_string(val)
                            if idx_val == 0: 
                                unit_val = u
                            processed_values.append(n_val)
                        
                        t_tables.append({
                            "name": row_name,
                            "unit": unit_val,
                            "isSame": False,
                            "values": processed_values
                        })
                    
                has_operator = any(any(c in val for c in '+*/') for val in processed_values)
                group1_list = []
                group2_list = []
                
                for val in processed_values:
                    if has_operator:
                        group1_list.append(parse_skill_expr(val))
                        nums = extract_numbers(val)
                        group2_list.append(nums[0] if len(nums) == 1 else (nums if nums else 0))
                    else:
                        nums = extract_numbers(val)
                        group1_list.append(nums[0] if len(nums) == 1 else (nums if nums else 0))
                        
                final_row_name = row_name
                while final_row_name in parsed_data:
                    final_row_name += "2"
                    
                parsed_data[final_row_name] = group1_list
                
                if has_operator:
                    second_name = final_row_name + "2"
                    while second_name in parsed_data:
                        second_name += "2"
                    parsed_data[second_name] = group2_list

            return t_tables, parsed_data

        talent = {}
        talent_data = {}
        talent_img_urls = {}
        passive_img_urls = []
        cons_img_urls = {}

        for letter in ['a', 'e', 'q']:
            if letter not in target_active_tables:
                continue
            t, t_id = target_active_tables[letter]
            skill_name = t.find('a').text.strip()
            
            img_tag = t.find('img')
            if img_tag and img_tag.get('src'):
                talent_img_urls[letter] = "https://gensh.honeyhunterworld.com" + img_tag['src']
            # 由于数据源没有技能id，按照id规律构建一个，但不保证完全正确
            if not is_traveler:
                suffix = 1 if letter == 'a' else (2 if letter == 'e' else 5)
                legacy_id = int(f"1{char_id_str}{suffix}")
                cur_talentId_map[str(legacy_id)] = letter
            
            tr_list = t.find('tbody').find_all('tr', recursive=False) if t.find('tbody') else t.find_all('tr', recursive=False)
            desc_td = tr_list[1].find('td')
            
            dmg_table = t.find('table', class_='skill_dmg_table')
            t_tables, parsed_data = parse_dmg_table(dmg_table, letter)
            talent_data[letter] = parsed_data

            c_desc = process_skill_desc(desc_td)
            if letter in ['e', 'q'] and not is_traveler:
                if not c_desc or not c_desc[-1].strip().startswith('<i>'):
                    fetch_bili_flavor()
                    if bili_flavor_texts.get(letter):
                        c_desc.extend(bili_flavor_texts[letter])

            talent[letter] = {
                "id": t_id,
                "name": skill_name,
                "desc": c_desc,
                "tables": t_tables
            }
            
        passives = []

        for t in passive_tables:
            a_tag = t.find('a')
            if not a_tag: continue
            p_name = a_tag.text.strip()
            
            img_tag = t.find('img')
            if img_tag and img_tag.get('src'):
                passive_img_urls.append("https://gensh.honeyhunterworld.com" + img_tag['src'])
                
            tr_list = t.find('tbody').find_all('tr', recursive=False) if t.find('tbody') else t.find_all('tr', recursive=False)
            if len(tr_list) > 1:
                desc_td = tr_list[1].find('td')
                if desc_td:
                    passives.append({
                        "name": p_name,
                        "desc": process_skill_desc(desc_td)
                    })

        for item in extra_passive_tables:
            t, t_id = item
            a_tag = t.find('a')
            if not a_tag: continue
            p_name = a_tag.text.strip()
            
            img_tag = t.find('img')
            if img_tag and img_tag.get('src'):
                passive_img_urls.append("https://gensh.honeyhunterworld.com" + img_tag['src'])
                
            tr_list = t.find('tbody').find_all('tr', recursive=False) if t.find('tbody') else t.find_all('tr', recursive=False)
            if len(tr_list) > 1:
                desc_td = tr_list[1].find('td')
                if desc_td:
                    dmg_table = t.find('table', class_='skill_dmg_table')
                    t_tables, _ = parse_dmg_table(dmg_table, is_special=True) 
                    
                    passive_item = {}
                    if t_id is not None:
                        passive_item["id"] = t_id
                    passive_item["name"] = p_name
                    passive_item["desc"] = process_skill_desc(desc_td)
                    
                    if t_tables:
                        passive_item["tables"] = t_tables
                        
                    passives.append(passive_item)
        
        cons_dict = {}
        for i, t in enumerate(cons_tables[:6]):
            c_name = t.find('a').text.strip()
            img_tag = t.find('img')
            if img_tag and img_tag.get('src'):
                cons_img_urls[str(i+1)] = "https://gensh.honeyhunterworld.com" + img_tag['src']
                
            tr_list = t.find('tbody').find_all('tr', recursive=False) if t.find('tbody') else t.find_all('tr', recursive=False)
            c_desc_td = tr_list[1].find('td')
            cons_dict[str(i+1)] = {"name": c_name, "desc": process_skill_desc(c_desc_td)}
        
        talentCons = {"a": 0, "e": 0, "q": 0}
        for i in [3, 5]:
            if str(i) not in cons_dict: continue
            cons_desc = "".join(cons_dict[str(i)]["desc"])
            if "等级提高" in cons_desc or "等级提升" in cons_desc:
                matched = False
                if "普通攻击" in cons_desc:
                    talentCons["a"] = i
                    matched = True
                elif "元素战技" in cons_desc:
                    talentCons["e"] = i
                    matched = True
                elif "元素爆发" in cons_desc:
                    talentCons["q"] = i
                    matched = True
                    
                if not matched:
                    if "a" in talent and talent["a"]["name"] in cons_desc: talentCons["a"] = i
                    elif "e" in talent and talent["e"]["name"] in cons_desc: talentCons["e"] = i
                    elif "q" in talent and talent["q"]["name"] in cons_desc: talentCons["q"] = i

        ordered_data = {
            "id": 7 if is_traveler else char_id,
            "name": name,
            "abbr": name,
            "title": title,
            "star": star,
            "elem": elem_name,
            "allegiance": allegiance,
            "weapon": weapon,
            "birth": birth,
            "astro": astro,
            "desc": desc,
            "cncv": cncv,
            "jpcv": jpcv,
            "costume": False,  # 数据源没有提供皮肤信息，暂时设为False
            "ver": 1,
            "baseAttr": baseAttr,
            "growAttr": growAttr,
            "talentId": cur_talentId_map,
        }

        if is_traveler:
            ordered_data["talentElem"] = cur_talent_elem

        ordered_data.update({
            "talentCons": talentCons,
            "materials": cur_materials,
            "talent": talent,
            "talentData": talent_data,
            "cons": cons_dict,
            "passive": passives,
            "attr": attr_data
        })
        
        element_download_tasks = []

        if talentCons["e"] == 0 and "e" in talent_img_urls:
            element_download_tasks.append((talent_img_urls["e"], "icons/talent-e.webp"))
        if talentCons["q"] == 0 and "q" in talent_img_urls:
            element_download_tasks.append((talent_img_urls["q"], "icons/talent-q.webp"))
            
        for idx_p, p_url in enumerate(passive_img_urls):
            element_download_tasks.append((p_url, f"icons/passive-{idx_p}.webp"))
            
        for i in range(1, 7):
            if str(i) in cons_img_urls:
                element_download_tasks.append((cons_img_urls[str(i)], f"icons/cons-{i}.webp"))

        all_results.append({
            "sub_folder": elem_name,
            "data": ordered_data,
            "tasks": element_download_tasks
        })

    if not is_traveler and all_results:
        base_img_url = "https://gensh.honeyhunterworld.com/img"
        if namecard_id:
            all_results[0]["tasks"].append((f"{base_img_url}/{namecard_id}_back.webp", "imgs/banner.webp"))
            all_results[0]["tasks"].append((f"{base_img_url}/{namecard_id}_profile.webp", "imgs/card.webp"))
        
        if char_path_slug:
            all_results[0]["tasks"].append((f"{base_img_url}/{char_path_slug}_icon.webp", "imgs/face.webp"))
            all_results[0]["tasks"].append((f"{base_img_url}/{char_path_slug}_side_icon.webp", "imgs/side.webp"))
            all_results[0]["tasks"].append((f"{base_img_url}/{char_path_slug}_gacha_card.webp", "imgs/gacha.webp"))
            all_results[0]["tasks"].append((f"{base_img_url}/{char_path_slug}_gacha_splash.webp", "imgs/splash.webp"))
    
    print(f"-> 角色 {name} (ID: {char_id}) 数据解析完毕！共解析出 {len(all_results)} 套技能数据。")
    return all_results


if __name__ == "__main__":
    try:
        global_url_map = get_character_url_map()
        success_count = 0

        index_file_path = os.path.join(OUTPUT_BASE_DIR, "data.json")
        global_index = {}
        if os.path.exists(index_file_path):
            try:
                with open(index_file_path, "r", encoding="utf-8") as f:
                    global_index = json.load(f)
            except Exception as e:
                print(f"读取现有全局索引文件失败: {e}")

        all_url_ids = list(global_url_map.keys())
        
        if isinstance(TARGET_IDS, str) and TARGET_IDS.lower() == "all":
            ids_to_process = all_url_ids
            print(f"当前模式：抓取全站全量 {len(ids_to_process)} 个角色。")
        elif isinstance(TARGET_IDS, list):
            ids_to_process = TARGET_IDS
            print(f"当前模式：指定抓取 {len(ids_to_process)} 个角色。")
        elif isinstance(TARGET_IDS, int) and TARGET_IDS > 0:
            sorted_ids = sorted(all_url_ids, reverse=True)
            ids_to_process = sorted_ids[:TARGET_IDS]
            print(f"当前模式：抓取全站ID最大的前 {len(ids_to_process)} 个角色。")
        else:
            ids_to_process = all_url_ids
            print(f"当前模式：默认抓取全量 {len(ids_to_process)} 个角色。")

        for cid in ids_to_process:
            if cid in global_url_map:
                target_url, target_path = global_url_map[cid]
                char_results = fetch_and_parse(target_url, cid, target_path)
                
                if char_results:
                    first_data = char_results[0]["data"]
                    char_name = first_data.get("name", f"Unknown_{cid}")
                    safe_char_name = re.sub(r'[\\/*?:"<>|]', "", char_name)
                    is_traveler_mode = "旅行者" in char_name or cid == 10000007 or cid == 20000000

                    for res in char_results:
                        sub_folder = res["sub_folder"]
                        char_data = res["data"]
                        download_tasks = res["tasks"]
                        
                        if is_traveler_mode and sub_folder:
                            save_dir = os.path.join(OUTPUT_BASE_DIR, safe_char_name, sub_folder)
                        else:
                            save_dir = os.path.join(OUTPUT_BASE_DIR, safe_char_name)
                            
                        os.makedirs(save_dir, exist_ok=True)
                        file_path = os.path.join(save_dir, "data.json")

                        if os.path.exists(file_path):
                            try:
                                with open(file_path, "r", encoding="utf-8") as f:
                                    old_data = json.load(f)
                                for reuse_key in ["abbr", "talentId"]:
                                    if reuse_key in old_data:
                                        char_data[reuse_key] = old_data[reuse_key]
                            except Exception as read_e:
                                print(f"      [警告] 读取旧数据失败，跳过复用: {read_e}")
                                
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(char_data, f, ensure_ascii=False, indent=2)
                            
                        info_str = f"[{sub_folder}] " if is_traveler_mode and sub_folder else ""
                        print(f"   [成功] {info_str}数据已保存至: {file_path}")
                        
                        if download_tasks:
                            dl_count = 0
                            for img_url, rel_filename in download_tasks:
                                img_path = os.path.join(save_dir, rel_filename)
                                if not OVERWRITE_IMAGES and os.path.exists(img_path):
                                    continue
                                    
                                os.makedirs(os.path.dirname(img_path), exist_ok=True)
                                if download_image(img_url, img_path):
                                    dl_count += 1
                                    
                            if dl_count > 0:
                                print(f"   [完成] 本次下载了 {dl_count} 张图片。")

                    idx_cid = 20000000 if is_traveler_mode else cid
                    idx_cid_str = str(idx_cid)
                    
                    if is_traveler_mode:
                        merged_talent_id = {}
                        for res in char_results:
                            merged_talent_id.update(res["data"].get("talentId", {}))

                        index_entry = {
                            "id": 20000000,
                            "name": "旅行者",
                            "abbr": "旅行者",
                            "star": 5,
                            "elem": "multi",
                            "weapon": "sword",
                            "talentId": merged_talent_id,
                            "talentCons": {
                                "e": 5,
                                "q": 3
                            }
                        }
                    else:
                        abbr = first_data.get("abbr", first_data["name"])
                        if idx_cid_str in global_index and "abbr" in global_index[idx_cid_str]:
                            abbr = global_index[idx_cid_str]["abbr"]
                            
                        index_entry = {
                            "id": idx_cid,
                            "name": first_data["name"],
                            "abbr": abbr,
                            "star": first_data["star"],
                            "elem": first_data["elem"],
                            "weapon": first_data["weapon"],
                            "talentId": first_data.get("talentId", {}),
                            "talentCons": first_data.get("talentCons", {"a": 0, "e": 0, "q": 0})
                        }
                        
                    global_index[idx_cid_str] = index_entry

                    print("") 
                    success_count += 1
            else:
                print(f"警告：角色 ID {cid} 未在全局映射表中找到对应的 URL，跳过。\n")

        if global_index:
            sorted_index = {str(k): global_index[str(k)] for k in sorted(int(x) for x in global_index.keys())}
            try:
                with open(index_file_path, "w", encoding="utf-8") as f:
                    json.dump(sorted_index, f, ensure_ascii=False, indent=2)
                print(f"[成功] 全局索引文件已更新: {index_file_path}")
            except Exception as e:
                print(f"[错误] 写入全局索引文件失败: {e}")

        alias_file_path = os.path.join(OUTPUT_BASE_DIR, "alias.js")
        if os.path.exists(alias_file_path):
            try:
                with open(alias_file_path, "r", encoding="utf-8") as f:
                    alias_lines = f.readlines()
                
                existing_aliases = set()
                for line in alias_lines:
                    match = re.search(r'^\s*(?:["\']?)([^"\':]+?)(?:["\']?)\s*:', line)
                    if match:
                        existing_aliases.add(match.group(1).strip())

                missing_aliases = []
                for item in global_index.values():
                    c_name = item["name"]
                    if c_name not in existing_aliases:
                        missing_aliases.append(c_name)
                        existing_aliases.add(c_name)
                
                if missing_aliases:
                    insert_index = -1
                    for i in range(len(alias_lines)-1, -1, -1):
                        if '}' in alias_lines[i]:
                            insert_index = i
                            break
                    
                    if insert_index != -1:
                        prev_idx = insert_index - 1
                        while prev_idx >= 0:
                            line_strip = alias_lines[prev_idx].strip()
                            if line_strip and not line_strip.startswith('//'):
                                if not line_strip.endswith(',') and not line_strip.endswith('{'):
                                    alias_lines[prev_idx] = alias_lines[prev_idx].rstrip('\r\n') + ',\n'
                                break
                            prev_idx -= 1

                        add_str = ""
                        for c_name in missing_aliases:
                            add_str += f'  "{c_name}": "",\n'
                        
                        alias_lines.insert(insert_index, add_str)
                        
                        with open(alias_file_path, "w", encoding="utf-8") as f:
                            f.writelines(alias_lines)
                        print(f"[成功] 检测到新角色，已向 alias.js 追加: {', '.join(missing_aliases)}")
                    else:
                        print("[警告] alias.js 中未找到结束的 '}'，放弃追加。")
            except Exception as e:
                print(f"[错误] 更新 alias.js 失败: {e}")
        print(f"全部任务执行完毕！共成功提取并生成 {success_count} 个角色文件夹。")
            
    except Exception as e:
        print(f"出现错误: {e}")
