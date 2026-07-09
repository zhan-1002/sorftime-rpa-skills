# sorftime-rpa

Browser-RPA + 数据分析项目，针对 **sorftime.com** (亚马逊卖家分析 SPA)。覆盖 6 个「选品」模块和 5 个「查」模块，每个模块独立 skill。

## 模块覆盖

### 简单使用

1，安装好 **Kimi WebBridge**（ https://www.kimi.com/zh-cn/features/webbridge ）运行且扩展已连接
2，在codex/claude code 安装好 sorftime-rpa skills

`
❯ 请利用 sorftime skill  对 美国蓝牙耳机市场进行全面调研，写详细分析报告给我
❯ 请利用 sorftime skill  对 美国拍照摄影设备市场进行全面调研，写详细分析报告给我
`

### 选品模块

| Skill | sorftime 路径 | 模式 | 数据可用性 |
|---|---|---|---|
| **sorftime-bestseller** | `/home/bestseller` | DOM-driven, 每类目触发 | ✅ 完整 TOP100 |
| **sorftime-product** | `/home/chooseproduct` | DOM-driven, 自动加载 | ⚠️ 每站 ~20 个未遮蔽 ASIN（免费层） |
| **sorftime-market** | `/home/choosemarketblock` | DOM-driven, `marketBoard.items` 自动加载 | ✅ 9/14 站（20 类目 × 251 字段；IN/CA/MX/AU/SA 0 数据） |
| **sorftime-keyword** | `/home/choosekeyword` | DOM-driven, `keywordData.listData` | ✅ 12/14 站（IN/AE 无数据） |
| **sorftime-brand** | `/home/choosebrand` | DOM-driven, `board.items` 默认加载 | ✅ 14/14 站 |
| **sorftime-seller** | `/home/chooseseller` | DOM-driven, `sellerBoard.items` 默认加载 | ✅ 9/14 站（IN/AE/AU/BR/SA 无数据） |

### 查模块（新品）

| Skill | sorftime 路径 | 输入 | 输出维度 |
|---|---|---|---|
| **sorftime-checkproduct** | `/home/checkproduct` | ASIN（批量，最多 ~100） | 产品详情：价格/销量/评价/BSR/品牌/卖家 |
| **sorftime-checkbrand** | `/home/checkbrand` | 品牌名 / ASIN / 卖家名 / 卖家公司 / 热搜词 | 品牌矩阵：产品数/卖家数/Top100/销量/均价 |
| **sorftime-checkseller** | `/home/checkseller` | 卖家名 / ASIN / 品牌名 / 热搜词 | 卖家店铺：产品数/Top400/月销量/均价 |
| **sorftime-checkmarket** | `/home/checkmarket` | 类目名 / ASIN / 关键词 | 市场概况：月销量/均价/新品占比/星级/周期 |
| **sorftime-checkkeyword** | `/home/checkkeyword` | ASIN / 关键词（实验性） | 多表结构：流量来源/ABA关键词/热搜趋势 |

**14 站点全支持**：US/GB/DE/FR/IN/CA/JP/ES/IT/MX/AE/AU/BR/SA

## 架构

- **kimi-webbridge 驱动**：通过本地 daemon (`http://127.0.0.1:10086`) 控制浏览器
- **DOM-driven 抓取**：sorftime 的 API 用 AES 加密请求/响应（`{v:3, k, d}` 格式），直接调用不可能。每个 skill 驱动 Vue VM 自带的方法（`treeItemClick`, `initData`, `onPageSizeChange` 等）触发加密 POST，然后从 Vue reactive state 读取解密后的数据
- **Python stdlib only**：无第三方依赖
- **CSV + Markdown 报告**：每个 skill 都有 `fetch_*.py` + `analyze.py`

## 快速开始

```bash
# 1. 检查 WebBridge daemon
~/.kimi-webbridge/bin/kimi-webbridge status

# 2. 抓取（示例：bestseller 3 站点）
python .claude/skills/sorftime-bestseller/scripts/fetch_bestseller.py \
    --station US,JP,GB --out data/best.csv

# 3. 生成对比报告
python .claude/skills/sorftime-bestseller/scripts/analyze.py \
    --bestsellers data/best.csv --out-md reports/best.md

# 4. 选市场：14 站点全维度 (251 字段/类目)
python .claude/skills/sorftime-market/scripts/fetch_all14.py \
    --stations US,GB,DE,FR,IN,CA,JP,ES,IT,MX,AE,AU,BR,SA \
    --out data/markets_14sites.csv
python .claude/skills/sorftime-market/scripts/analyze.py \
    --markets data/markets_14sites.csv \
    --out-md reports/markets_14sites.md

# 5. 选品牌：14 站点全覆盖
python .claude/skills/sorftime-brand/scripts/fetch_brands.py \
    --stations US,GB,DE,FR,IN,CA,JP,ES,IT,MX,AE,AU,BR,SA \
    --out data/brands_FINAL_14sites.csv

# 6. 选关键词：12 站点 (默认加载 20 个热门词)
python .claude/skills/sorftime-keyword/scripts/fetch_keywords.py \
    --stations US,GB,DE,FR,CA,JP,ES,IT,MX,AU,BR,SA \
    --out data/keywords_all14sites.csv

# 7. 选卖家：9 站点 (需用户先在 UI 选类目)
python .claude/skills/sorftime-seller/scripts/fetch_sellers.py \
    --stations US,GB,DE,FR,JP,ES,IT,MX,CA \
    --out data/sellers_14sites.csv

# 8. 查模块（示例：checkproduct ASIN 反查）
python .claude/skills/sorftime-checkproduct/scripts/fetch_checkproduct.py \
    --station US,JP --asins B0CHX1W1XY --out data/product_check.csv

# 9. 查模块：品牌矩阵
python .claude/skills/sorftime-checkbrand/scripts/fetch_checkbrand.py \
    --station US,JP --mode brand --queries "Anker,Baseus" --out data/brands.csv
```

## 项目结构

```
sorftime-rpa/
├── README.md                    (本文，中文主版本)
├── README.en.md                 (英文版)
├── CLAUDE.md                    (Claude Code 项目指南)
├── phase1_investigation.md      (调研笔记)
├── .claude/skills/
│   ├── sorftime-bestseller/     (✅ 选品-畅销榜)
│   ├── sorftime-product/        (⚠️ 选品-免费层限制)
│   ├── sorftime-market/         (✅ 选市场-251 字段 × 9 站)
│   ├── sorftime-keyword/        (✅ 选品-12/14 站)
│   ├── sorftime-brand/          (✅ 选品-14/14 站)
│   ├── sorftime-seller/         (✅ 选品-9/14 站)
│   ├── sorftime-checkproduct/   (✅ 查-ASIN 产品详情)
│   ├── sorftime-checkbrand/     (✅ 查-品牌矩阵)
│   ├── sorftime-checkseller/    (✅ 查-卖家信息)
│   ├── sorftime-checkmarket/    (✅ 查-细分市场)
│   └── sorftime-checkkeyword/   (🔬 查-关键词, 实验性)
├── data/                        (CSV 输出)
└── reports/                     (Markdown 报告)
```

## 已知限制

### sorftime API 加密
sorftime 用混淆的 AES routine 加密所有 API 请求/响应。直接调用 `api.sorftime.com/*` 不可能。所有 skill 都通过驱动 Vue VM 的内置方法间接调用。

### 免费层遮蔽
- **bestseller**: 完全开放（每类目 TOP100 完整）
- **product**: 每站点 ~20 个未遮蔽 ASIN（其余 ASIN/Name/Brand 显示为 `"--"`）
- **market** ✅: 已突破！`marketBoard.items` 自动加载 20 个 top 类目（251 字段/类目），无需 `initData(nodeId)` 手动触发
- **keyword** ✅: 已突破！默认加载 20 个热门词，无需选类目
- **brand** ✅: 已突破！`board.items` 默认加载 20 个品牌，无门控
- **seller**: 9/14 站免费层有数据（IN/AE/AU/BR/SA 0 数据，与 market 一致）

### 选市场页（已突破）
`/home/choosemarketblock` 页面**不需要 initData(nodeId)**：`marketBoard.items` 在页面 mount 时自动加载 20 个 top 类目（每类目 251 字段）。可通过切换 `vm.marketType` 在 4 个 sub-modes（multi/buyer/new/lowprice）之间切换获取不同 20 类目，最多 80 类目/站。9/14 站有数据，5 站（IN/CA/MX/AU/SA）返回 0。详见 `sorftime-market/SKILL.md`。

### 选关键词页（已突破）
`/home/choosekeyword` 页面**不需要选类目**：默认加载 20 个当前站点的热门词到 `keywordData.listData`（小写 l，匿名父 VM depth 6）。详见 `sorftime-keyword/SKILL.md`。

### 选品牌页（已突破）
`/home/choosebrand` 页面**不需要选类目**：`board.items` 默认加载 20 个品牌，14/14 站全支持。详见 `sorftime-brand/SKILL.md`。

### 筛选门控页面（仅 seller）
sorftime-seller 页面仍要求用户在浏览器 UI 中选类目：
1. 打开「类目」对话框
2. 选择具体类目
3. 关闭对话框

之后 `sellerBoard.items` 才会填充。9/14 站有数据，5 站（IN/AE/AU/BR/SA）返回 0。**完整 reverse-engineer 类目对话框的 Vue 组件交互**留作未来工作。

## 14 站点映射

| Code | Site | 中文 |
|---|---|---|
| 1 | US | 美国 |
| 2 | GB | 英国 |
| 3 | DE | 德国 |
| 4 | FR | 法国 |
| 5 | IN | 印度 |
| 6 | CA | 加拿大 |
| 7 | JP | 日本 |
| 8 | ES | 西班牙 |
| 9 | IT | 意大利 |
| 10 | MX | 墨西哥 |
| 11 | AE | 阿联酋 |
| 12 | AU | 澳大利亚 |
| 13 | BR | 巴西 |
| 14 | SA | 沙特 |

切换站点：`localStorage.setItem("site", "<code>")` + `location.reload()`（URL `?i=` 参数无效）

## 姊妹项目

- **`fastmoss-rpa`** — TikTok Shop 分析（fastmoss.com）
- **`sellersprite-rpa`** — 亚马逊 卖家精灵分析（sellersprite.com，10 站点）

sorftime-rpa 复用了这两个项目的 DOM-driven 模式和报告模板。

## 工具依赖

- **Python 3.10+**（仅用 stdlib）
- **Kimi WebBridge**：`~/.kimi-webbridge/bin/kimi-webbridge status`
- **bash shell**（Windows 上 Git Bash 即可）




## Fork 新增

本仓库在原始项目基础上新增了 **Amazon → 1688 比价闭环**，将选品调研流程延伸至供应链端。

### 新增模块

| 模块 | 功能 | 输入 | 输出 |
|---|---|---|---|
| **sorftime-1688-compare** | Amazon 图片 → 1688 以图搜图 → 供应商比价 | Amazon 商品图片 URL | 1688 供应商列表（报价/销量/回头率/链接）+ FBA 利润测算 |
| **[us-patent-mcp](https://github.com/zhan-1002/us-patent-mcp-for-china-ecommerce)** | 美国专利检索（外观/实用新型） | 产品名称、关键特征、产品图片 | 多策略专利搜索报告（标题/发明人/申请人追踪） |

### 完整调研流程

```
sorftime 选品调研 → 发现潜力品类
       │
       ▼
Amazon 搜索 → 提取真实 ASIN → sorftime 反查销量/评价/FBA
       │
       ├──────────────┬──────────────┐
       ▼              ▼              ▼
  1688 供应商比价   利润测算      专利排查
  (sorftime-       (FBA 利润     (us-patent-mcp
   1688-compare)    计算表)       外观/实用新型)
       │              │              │
       └──────────────┴──────────────┘
                      │
                      ▼
          综合可做性判断（利润 + 竞争 + 专利风险）
```

### 专利排查

通过 [us-patent-mcp-for-china-ecommerce](https://github.com/zhan-1002/us-patent-mcp-for-china-ecommerce) MCP 服务器在 Claude Code 中直接检索美国专利：

```bash
# 安装专利 MCP 工具
git clone https://github.com/zhan-1002/us-patent-mcp-for-china-ecommerce.git
cd us-patent-mcp-for-china-ecommerce && uv sync

# 配置到 Claude Code
claude mcp add-json patents '{"command": "uv", "args": ["--directory", "/path/to/us-patent-mcp-for-china-ecommerce", "run", "patent-mcp-server"]}'
```

配置后在 Claude Code 中对话即可触发专利检索，提供以下信息可获得最佳搜索效果：

```
帮我搜索这个产品的专利：
- 产品名称：Self Watering Pots with Water Level Indicator（可以直接复制亚马逊标题）
- 关键特征：水位指示器、可拆卸底座（补充说明产品功能特征有利于搜索隐藏专利）
- 产品图片：上传产品图片用于模型视觉分析
```

提供三要素（产品名称、关键特征、图片）后，MCP 会自动：
1. 分析产品关键特征
2. 构建多策略搜索关键词（标题精确匹配、全文关键词组合）
3. 执行搜索并追踪发明人/申请人关联专利
4. 输出专利风险评估报告

### 使用示例

```bash
# 搜 Amazon 商品图片在 1688 的同款供应商
python .claude/skills/sorftime-1688-compare/scripts/fetch_1688.py \
    --image-url "https://m.media-amazon.com/images/I/XXXXX.jpg" \
    --out data/1688_results.csv

# 生成供应商对比 + FBA 利润报告
python .claude/skills/sorftime-1688-compare/scripts/analyze.py \
    --results data/1688_results.csv \
    --amz-price 8.99 \
    --out-md reports/compare_report.md
```

### 技术要点

- **1688 以图搜图**：通过 `fetch()` + `DataTransfer` 绕过浏览器文件对话框限制，将 Amazon 图片注入 1688 的图片搜索
- **登录检测**：`check_login()` 门控函数检测 1688 登录状态，未登录时提示用户
- **FBA 利润公式**：复用 FBA 选品利润计算表（采购价/头程/FBA费/佣金）
- **供应商链接**：自动构建 `detail.1688.com/offer/{id}.html` 产品详情页

### 已知限制

- 1688 需要手动登录（一次性，cookie 持久化在 WebBridge 浏览器中）
- 1688 图搜按颜色/形状匹配，可能返回视觉相似但品类无关的结果

---

### 致谢

- 原始项目作者 [liangdabiao](https://github.com/liangdabiao) — 感谢开源的 sorftime-rpa-skills 项目
- https://linux.do 社区佬友