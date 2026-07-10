# 开发计划

## 已完成

### P0：基础设施
- [x] `common.py` — WebBridge 驱动层
- [x] `fetch_1688.py` — 1688 图搜 pipeline（image URL → upload → click → extract → CSV）
- [x] `amz_product.py` — ASIN → Amazon 产品页 → 提取主图/标题/价格
- [x] `analyze.py` — FBA 利润 + 供应商信誉评分
- [x] `category_filter.py` — 品类过滤引擎（硬门槛 + 加权评分）
- [x] `ad_scan.py` — sellersprite 广告洞察扫描器（批量 ASIN → 广告依赖度）

### P1：sellersprite 集成
- [x] `sellersprite-competitors` — 竞品查询（47 字段，API-first）
- [x] `sellersprite-markets` — 细分市场数据
- [x] `sellersprite-products` — 产品排行
- [x] sellersprite 广告洞察（DOM-driven，`/v3/ads-insights?q=<ASIN>`）

### P2：验证
- [x] FBA 利润公式验证（与桌面利润表一致）
- [x] 供应商评分验证（回头率/年限/销量）
- [x] 10 个样本 ASIN 全流程验证
- [x] 六维判断模型校准
- [x] 广告依赖度作为关键维度确认

## 进行中

- [ ] Step 1-8 全流程串联脚本 `pipeline.py`

## 搁置

- [ ] sorftime checkproduct（需 PRO 账号）
- [ ] 1688 文字搜索（中文编码待解决）
- [ ] dHash 视觉过滤（已设计，未实现）
- [ ] 供应链表格自动写入

## 待开发

### Phase 2 全流程串联
- [ ] `pipeline.py` — 一键 ASIN → 完整分析报告
- [ ] Step 1: 品类自动发现（sellersprite markets → filter）
- [ ] Step 2: Amazon 多关键词搜索 → ASIN 提取
- [ ] Step 3: sellersprite competitors 自动分析
- [ ] Step 4: 模板自动评分 + 推荐
- [ ] Step 5: 广告洞察自动扫描
- [ ] Step 6: Amazon 页面深度抓取（评论/套装详情）
- [ ] Step 7: 1688 图搜 → 成本拆解 → 利润
- [ ] Step 8: 差异化方案生成 + 利润重算

### 增强
- [ ] 专利排查串联（us-patent-mcp）
- [ ] 多站点支持
- [ ] 历史数据趋势对比
- [ ] 差评自动挖掘（NLP 关键词提取）
