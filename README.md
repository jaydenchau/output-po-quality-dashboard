# Output & PO Status 质量分析看板

基于 Streamlit 的工厂产出与 PO 状态数据质量分析工具，用于监控和验证 
`ads.ads_dtd_po_status_output_quality_history` 的数据一致性。

## 功能

### 1. Output & PO Status 一致性检查
| 模块 | 说明 |
|------|------|
| **1.1 WIP8 vs Output vs FG10** | 验证 `wip8_outputs == tqc3_pass_qty == wip8_po_status_increase` 以及 `fg10_po_status_increase >= 0` |
| **1.2 负增量检查** | 检查 `wip8_po_status_increase < 0` 的异常记录 |
| **1.3 累积 vs PO 数量** | 按 PO-Style-Color-Ship 对比累积产出与 PO 下单量 |

### 2. TQC3 vs WIP8 对比分析
- 每日总产出对比（柱状图 + 差异折线图）
- 支持下钻：日总览 → PO 级别 → Style 级别
- 差异明细数据导出

## 快速开始

```bash
# 安装依赖
pip3 install streamlit pandas plotly numpy

# 生成样本数据（可选，已预置）
cd waytobox && python3 data/generate_sample_data.py

# 启动看板
streamlit run app.py
```

## 每日刷新

将你从 Redshift 导出的 CSV 替换到 `data/sample_data.csv`，
保持相同的列结构，刷新页面即可更新看板。

## 列结构要求

CSV 需包含以下列：

| 列名 | 类型 | 说明 |
|------|------|------|
| id | varchar | 唯一标识 |
| factory_name | varchar | 工厂名称 |
| factory_code | varchar | 工厂代码 |
| date | date | 日期 |
| po_number | varchar | PO 号 (distkey) |
| style_number | varchar | 款式号 |
| color_code | varchar | 颜色代码 |
| ship_id | varchar | 船次号 |
| po_type | varchar | PO 类型 |
| po_quantity | bigint | PO 下单量 |
| wip8_outputs | bigint | 当天 WIP8 产出 |
| tqc3_pass_qty | bigint | 当天 TQC3 通过数 |
| wip8_po_status_increase | bigint | WIP8 PO 状态当日增量 |
| fg10_po_status_increase | bigint | FG10 PO 状态当日增量 |
| fg14_po_status_increase | bigint | FG14 PO 状态当日增量 |
| wip8_po_statu_completion_quantity | bigint | WIP8 累积完成量 |
| fg10_po_statu_completion_quantity | bigint | FG10 累积完成量 |
| fg14_po_statu_completion_quantity | bigint | FG14 累积完成量 |

## 技术栈

- **前端/框架**: Streamlit
- **图表**: Plotly
- **数据处理**: Pandas, NumPy
- **数据库接入**: 当前 CSV → 后续可切换 Redshift (SQLAlchemy)

## 项目结构

```
waytobox/
├── app.py                          # 主入口
├── pages/
│   ├── 1_一致性检查.py             # 一致性检查页面
│   └── 2_TQC3_vs_WIP8_对比.py     # TQC3 vs WIP8 对比页面
├── data/
│   ├── generate_sample_data.py     # 样本数据生成器
│   └── sample_data.csv             # 数据文件（每日替换）
├── utils/
│   └── data_loader.py              # 数据加载模块
├── requirements.txt
└── README.md
```


## 部署到 Streamlit Community Cloud

代码仓库：https://github.com/jaydenchau/output-po-quality-dashboard

### 部署步骤

**第 1 步**：打开 https://streamlit.io/cloud，用 GitHub 账号登录

**第 2 步**：点击 **"New app"** 按钮

**第 3 步**：填写以下信息：

| 项目 | 填写内容 |
|------|---------|
| Repository | `jaydenchau/output-po-quality-dashboard` |
| Branch | `main` |
| Main file path | `app.py` |

**第 4 步**：点击 **"Deploy"** 按钮

等待 2-3 分钟，部署完成后会生成链接，例如：
```
https://output-po-quality-dashboard.streamlit.app
```

### 后续更新代码

```bash
git add .
git commit -m "修改说明"
git push
```

Streamlit Cloud 会自动检测更新并重新部署。
