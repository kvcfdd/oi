import os
import json
import re
import requests

# 目录与文件配置
BASE_DIR = "E:/zzz/miao-plugin/resources/meta-gs/material"
JSON_FILE = os.path.join(BASE_DIR, "data.json")

# 映射关系
CONFIGS =[
    {"url": "fam_char_jewel", "type": "gem", "size": 4},
    {"url": "fam_char_stone", "type": "boss", "size": 1},
    {"url": "fam_char_common", "type": "normal", "size": 3},
    {"url": "fam_char_local", "type": "specialty", "size": 1},
    {"url": "fam_talent_boss", "type": "weekly", "size": 1},
    {"url": "fam_talent_book", "type": "talent", "size": 3},
    {"url": "fam_wep_secondary", "type": "monster", "size": 3},
    {"url": "fam_wep_primary", "type": "weapon", "size": 4}
]

def download_image(raw_id, name, type_dir, headers):
    img_url = f"https://gensh.honeyhunterworld.com/img/i_{raw_id}.webp"
    img_path = os.path.join(type_dir, f"{name}.webp")
    if not os.path.exists(img_path):
        try:
            res = requests.get(img_url, headers=headers, timeout=10)
            if res.status_code == 200:
                with open(img_path, 'wb') as f:
                    f.write(res.content)
                print(f"    -> 图片下载成功: {name}.webp")
            else:
                print(f"    -> 图片下载失败[HTTP {res.status_code}]: {img_url}")
        except Exception as e:
            print(f"    -> 图片请求异常: {e}")

def main():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    data_changed = False

    for cfg in CONFIGS:
        print(f"\n========== 开始处理 [{cfg['type']}] ({cfg['url']}) ==========")
        type_dir = os.path.join(BASE_DIR, cfg["type"])
        os.makedirs(type_dir, exist_ok=True)

        url = f"https://gensh.honeyhunterworld.com/{cfg['url']}/?lang=CHS"
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'

        match = re.search(r'sortable_data\.push\((\[\[.*?\]\])\);', response.text, re.S)
        if not match:
            print(f"未在网页中匹配到数据！URL: {url}")
            continue

        items_array = json.loads(match.group(1))
        flat_items = []

        for row in items_array:
            col2 = row[1]
            col3 = row[2]
            
            id_match = re.search(r'/i_(.*?)/\?lang=CHS', col2)
            name_match = re.search(r'>([^<]+)</a>', col2)
            star_match = re.search(r'<span class="rsh">(\d+)</span>', col3)

            if id_match and name_match:
                item_name = name_match.group(1)
                # 跳过测试物品
                if "(test)" in item_name or "测试" in item_name:
                    continue
                
                raw_id = id_match.group(1)
                item_star = int(star_match.group(1)) if star_match else 1
                
                flat_items.append({
                    "raw_id": raw_id,
                    "id": raw_id.replace('n', ''),
                    "name": item_name,
                    "type": cfg["type"],
                    "star": item_star
                })

        size = cfg["size"]
        if size == 1:
            for item in flat_items:
                if item["name"] not in data:
                    print(f"发现缺失材料:[{item['name']}]")
                    data[item["name"]] = {
                        "id": str(item["id"]),
                        "name": item["name"],
                        "type": item["type"],
                        "star": item["star"]
                    }
                    data_changed = True
                    download_image(item["raw_id"], item["name"], type_dir, headers)
                else:
                    old_id = data[item["name"]].get("id")
                    if old_id != str(item["id"]):
                        print(f"更新 [{item['name']}] ID: {old_id} -> {item['id']}")
                        data[item["name"]]["id"] = str(item["id"])
                        data_changed = True
        else:
            valid_groups = []
            current_group =[]
            
            for item in flat_items:
                if not current_group:
                    current_group.append(item)
                else:
                    if item["star"] == current_group[-1]["star"] + 1:
                        current_group.append(item)
                    else:
                        current_group = [item]
                
                if len(current_group) == size:
                    valid_groups.append(current_group)
                    current_group = []

            for group in valid_groups:
                highest_item = group[-1]
                family_name = highest_item["name"]
                
                if family_name not in data:
                    print(f"发现缺失材料: [{family_name}]")
                    items_dict = {}
                    for it in group:
                        items_dict[it["name"]] = {
                            "id": str(it["id"]),
                            "name": it["name"],
                            "type": it["type"],
                            "star": it["star"]
                        }
                    data[family_name] = {
                        "id": str(highest_item["id"]),
                        "name": family_name,
                        "type": cfg["type"],
                        "star": highest_item["star"],
                        "items": items_dict
                    }
                    data_changed = True
                    
                    for it in group:
                        download_image(it["raw_id"], it["name"], type_dir, headers)
                else:
                    old_fam_id = data[family_name].get("id")
                    if old_fam_id != str(highest_item["id"]):
                        print(f"更新主ID [{family_name}]: {old_fam_id} -> {highest_item['id']}")
                        data[family_name]["id"] = str(highest_item["id"])
                        data_changed = True
                    if "items" in data[family_name]:
                        for it in group:
                            if it["name"] in data[family_name]["items"]:
                                old_sub_id = data[family_name]["items"][it["name"]].get("id")
                                if old_sub_id != str(it["id"]):
                                    print(f"  -> 更新子项ID [{it['name']}]: {old_sub_id} -> {it['id']}")
                                    data[family_name]["items"][it["name"]]["id"] = str(it["id"])
                                    data_changed = True
                            else:
                                data[family_name]["items"][it["name"]] = {
                                    "id": str(it["id"]),
                                    "name": it["name"],
                                    "type": it["type"],
                                    "star": it["star"]
                                }
                                data_changed = True

    # 统一进行升序排序
    print("\n========== 正在排序并检查数据 ==========")
    sorted_data = {
        k: v for k, v in sorted(
            data.items(), 
            key=lambda item: int(item[1].get("id", 0))
        )
    }

    if list(data.keys()) != list(sorted_data.keys()):
        data_changed = True

    # 保存文件
    if data_changed:
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted_data, f, ensure_ascii=False, indent=2)
        print("全部更新与排序完毕！data.json 文件已保存。")
    else:
        print("全部检查完毕，没有发现新材料且 ID 和排序一致，无需更新。")

if __name__ == "__main__":
    main()