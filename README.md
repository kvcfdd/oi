# 原神元数据更新脚本 (for miao-plugin)

这是一组用于从 [Honey Hunter World](https://gensh.honeyhunterworld.com/) 抓取原神最新数据的 Python 爬虫脚本。脚本会自动解析角色、武器、圣遗物和材料的数据，下载相关图片，并将其格式化为兼容 **miao-plugin (喵喵插件)** 的 JSON 和 JS 数据结构。

项目仅供学习交流使用，严禁用于任何商业用途和非法行为

## 包含的脚本

- `gs_character.py`：抓取角色基础属性、技能、命座、材料等数据及相关图片。
- `gs_weapon.py`：抓取武器属性、突破材料、特效文案等数据及相关图片。
- `gs_artifact.py`：抓取圣遗物套装效果、部件信息及相关图片。
- `gs_materials.py`：抓取角色与武器所需的各类培养材料及相关图片。

---

## 🛠️ 环境准备

1. **Python 环境**：请确保已安装 Python 3.7 或更高版本。
2. **安装依赖库**：脚本依赖 `requests` 和 `beautifulsoup4`。请在终端执行以下命令：

   ```bash
   pip install requests beautifulsoup4 -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

## ⚙️ 运行前必看：修改配置路径！

脚本中默认配置的保存路径为开发者本地路径。**在运行任何脚本之前，请务必用文本编辑器打开这四个 Python 文件，修改顶部的 BASE_SAVE_PATH 或 OUTPUT_BASE_DIR 为你实际的喵喵插件目录！**

例如：

    ```bash
    # 修改前
    BASE_SAVE_PATH = "E:/zzz/miao-plugin/resources/meta-gs/weapon"
    # 修改后 (请根据你的实际情况填写绝对路径)
    BASE_SAVE_PATH = "/你的云崽/plugins/miao-plugin/resources/meta-gs/weapon"
    ```

## 🚀 使用说明

1. 更新角色数据 (gs_character.py)

- 打开脚本，根据需求修改顶部的 TARGET_IDS 变量：
- TARGET_IDS = 1：抓取全站最新上线的 1 个角色（推荐日常更新使用）。
- TARGET_IDS = "all"：全量抓取所有角色（耗时较长）。
- TARGET_IDS = [10000130, 10000131]：抓取指定 ID 的角色。

2. 更新武器数据 (gs_weapon.py)

- 打开脚本，根据需求修改顶部的 WEAPON_IDS 变量：
- WEAPON_IDS = 15516：抓取指定单把武器。
- WEAPON_IDS = [15516, 15517]：抓取多把武器。
- WEAPON_IDS = "all"：抓取全站所有 3 星及以上武器。

3. 更新圣遗物数据 (gs_artifact.py)

- 该脚本默认会自动从总览页面提取所有圣遗物套装并进行比对抓取。

4. 更新材料数据 (gs_materials.py)

- 该脚本会自动遍历各个材料分类，按照星级分组，并自动判断是否有新材料加入。如果有，会自动下载图片并更新data.json。

5. 运行

- 可双击add.bat选择运行或使用命令运行

```bash
python xxx.py
```

## ⚠️ 注意事项

数据源不提供技能id，脚本会按格式拼接，大概率是没问题的(不含旅行者)，如更新已有老角色，则会复用已有id
