# 开发计划

## 已完成

### P0：基础设施
- [x] `common.py` — WebBridge 驱动层（navigate / evaluate / call）
- [x] `fetch_1688.py` — 1688 图搜 pipeline（image URL → upload → click → extract）
- [x] `amz_product.py` — ASIN → Amazon 产品页 → 提取主图/标题/价格
- [x] `analyze.py` — FBA 利润计算 + 供应商信誉评分
- [x] `category_filter.py` — 品类过滤引擎（硬门槛 + 加权评分）

### P1：集成
- [x] `fetch_1688.py --asin` — ASIN 自动提取主图后搜 1688
- [x] `--search-mode combined` — 图搜+文搜双路框架
- [x] 1688 登录检测门控

### P2：验证
- [x] FBA 利润公式验证（与桌面利润表一致）
- [x] 供应商评分验证（回头率/年限/销量）
- [x] 品类过滤器基于样本数据校准

## 进行中

- [ ] Step 1-7 全流程串联脚本 `pipeline.py`
- [ ] 文搜关键词编码问题修复

## 搁置

- [ ] sorftime checkproduct 集成（需 PRO 账号）
- [ ] 1688 文字搜索（中文编码待解决）
- [ ] dHash 视觉过滤（已设计，未实现）
- [ ] 供应链表格自动写入（openpyxl 兼容问题）
- [ ] 专利排查集成（us-patent-mcp 已可用，待串联）

## 待开发

### Phase 2 流程串联
- [ ] `scripts/pipeline.py` — 一键运行 Step 1-7
- [ ] Step 2: Amazon 品类搜索 → ASIN 提取自动化
- [ ] Step 4: 竞品深度分析（评论抓取、套装拆解）
- [ ] Step 6: 差异化方案生成（基于差评挖掘）
- [ ] Step 7: 综合可做性报告生成

### 增强
- [ ] 1688 供应商自动联系（旺旺消息模板）
- [ ] 多站点支持（UK/DE/JP）
- [ ] 历史数据对比（竞品价格/销量趋势）
