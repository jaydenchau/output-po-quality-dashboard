"""
主页 - 总览仪表板
展示全部工厂的数据对比，无需逐个切换。
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.data_loader import build_sidebar

st.set_page_config(
    page_title="Output & PO Status 质量分析",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 共享侧边栏 ──
_ = build_sidebar()

# ── 总览使用全部数据（不受工厂筛选影响） ──
df_all = st.session_state.get("df_full", None)
if df_all is None or df_all.empty:
    st.error("无法加载数据")
    st.stop()

st.title("📊 总览仪表板 · 全部工厂")
st.markdown(
    """本页展示**全部工厂**的汇总数据与对比，无需切换工厂即可一览全局。
    如需查看单个工厂的详细分析，请使用左侧导航进入具体页面。"""
)

st.markdown("---")

# ════════════════════════════════════════════
# 1. 全局汇总指标
# ════════════════════════════════════════════
st.markdown("### 🌍 全局汇总")

total_rows = len(df_all)
wip8_tqc3_ok = (df_all["wip8_outputs"] == df_all["tqc3_pass_qty"]).sum()
wip8_inc_ok = (df_all["wip8_outputs"] == df_all["wip8_po_status_increase"]).sum()
no_neg_inc = (df_all["wip8_po_status_increase"] >= 0).sum()
neg_count = (df_all["wip8_po_status_increase"] < 0).sum()

if total_rows == 0:
    st.warning("没有数据")
    st.stop()

col1, col2, col3, col4, col5 = st.columns(5)
with col1: st.metric("📋 总记录数", f"{total_rows:,}")
with col2: st.metric("✅ WIP8 = TQC3", f"{wip8_tqc3_ok/total_rows*100:.1f}%")
with col3: st.metric("✅ WIP8 = Increase", f"{wip8_inc_ok/total_rows*100:.1f}%")
with col4: st.metric("✅ 无负增量", f"{no_neg_inc/total_rows*100:.1f}%")
with col5: st.metric("🔴 负增量记录", f"{neg_count:,}")

st.markdown("---")

# ════════════════════════════════════════════
# 2. 各工厂对比
# ════════════════════════════════════════════
st.markdown("### 🏭 各工厂数据对比")

# 用简单循环计算各工厂数据（避免复杂的 lambda）
factory_rows = []
for fac in df_all["factory_name"].unique():
    fd = df_all[df_all["factory_name"] == fac]
    n = len(fd)
    factory_rows.append({
        "工厂": fac,
        "总记录数": n,
        "WIP8=TQC3通过率": f"{(fd['wip8_outputs'] == fd['tqc3_pass_qty']).sum() / n * 100:.1f}%" if n else "0%",
        "WIP8=Increase通过率": f"{(fd['wip8_outputs'] == fd['wip8_po_status_increase']).sum() / n * 100:.1f}%" if n else "0%",
        "无负增量率": f"{(fd['wip8_po_status_increase'] >= 0).sum() / n * 100:.1f}%" if n else "0%",
        "负增量数": (fd['wip8_po_status_increase'] < 0).sum(),
        "WIP8产出": fd['wip8_outputs'].sum(),
        "TQC3产出": fd['tqc3_pass_qty'].sum(),
    })

factory_stats = pd.DataFrame(factory_rows)
st.dataframe(factory_stats, use_container_width=True, hide_index=True)

st.markdown("---")

# ════════════════════════════════════════════
# 3. 对比图表
# ════════════════════════════════════════════
st.markdown("### 📈 各工厂通过率对比")

# 数值化（去掉 % 符号用于图表）
for col in ["WIP8=TQC3通过率", "WIP8=Increase通过率", "无负增量率"]:
    factory_stats[col + "_num"] = factory_stats[col].str.rstrip("%").astype(float)

col_ch1, col_ch2 = st.columns(2)

with col_ch1:
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=factory_stats["工厂"], y=factory_stats["WIP8=TQC3通过率_num"],
                          name="WIP8 = TQC3", marker_color="#2ecc71"))
    fig1.add_trace(go.Bar(x=factory_stats["工厂"], y=factory_stats["WIP8=Increase通过率_num"],
                          name="WIP8 = Increase", marker_color="#3498db"))
    fig1.add_trace(go.Bar(x=factory_stats["工厂"], y=factory_stats["无负增量率_num"],
                          name="无负增量", marker_color="#e67e22"))
    fig1.update_layout(barmode="group", xaxis_title="工厂", yaxis_title="通过率(%)", height=400,
                      yaxis=dict(range=[80, 100]),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig1, use_container_width=True)

with col_ch2:
    fig2 = px.bar(factory_stats, x="工厂", y="负增量数", color="负增量数",
                  color_continuous_scale="Reds", text="负增量数")
    fig2.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ════════════════════════════════════════════
# 4. 各工厂产出对比
# ════════════════════════════════════════════
st.markdown("### 📊 各工厂 WIP8 vs TQC3 产出对比")

fig3 = go.Figure()
fig3.add_trace(go.Bar(x=factory_stats["工厂"], y=factory_stats["WIP8产出"],
                      name="WIP8 产出", marker_color="#3498db", opacity=0.8))
fig3.add_trace(go.Bar(x=factory_stats["工厂"], y=factory_stats["TQC3产出"],
                      name="TQC3 产出", marker_color="#e67e22", opacity=0.8))
fig3.update_layout(barmode="group", xaxis_title="工厂", yaxis_title="产出数量", height=400,
                   legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ════════════════════════════════════════════
# 5. 各工厂 PO 完成情况
# ════════════════════════════════════════════
st.markdown("### 📦 各工厂 PO 完成情况")

po_by_factory = (
    df_all.groupby(["factory_name", "po_number", "style_number", "color_code", "ship_id"], as_index=False)
    .agg(total_wip8=("wip8_outputs", "sum"), po_quantity=("po_quantity", "first"))
)
po_by_factory["完成率"] = po_by_factory["total_wip8"] / po_by_factory["po_quantity"] * 100
po_by_factory["超量"] = po_by_factory["完成率"] > 105
po_by_factory["进度偏低"] = (po_by_factory["total_wip8"] > 0) & (po_by_factory["完成率"] < 30)
po_by_factory["无进度"] = po_by_factory["total_wip8"] == 0

factory_po_summary = po_by_factory.groupby("factory_name").agg(
    PO组合数=("po_number", "count"),
    超量=("超量", "sum"),
    进度偏低=("进度偏低", "sum"),
    无进度=("无进度", "sum"),
    平均完成率=("完成率", "mean"),
).reset_index()

col_sum1, col_sum2 = st.columns(2)
with col_sum1:
    st.dataframe(factory_po_summary.rename(columns={"factory_name": "工厂"}),
                 use_container_width=True, hide_index=True)
with col_sum2:
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(x=factory_po_summary["factory_name"], y=factory_po_summary["超量"],
                          name="⚠️ 超量", marker_color="#e74c3c"))
    fig4.add_trace(go.Bar(x=factory_po_summary["factory_name"], y=factory_po_summary["进度偏低"],
                          name="⚠️ 进度偏低", marker_color="#f39c12"))
    fig4.add_trace(go.Bar(x=factory_po_summary["factory_name"], y=factory_po_summary["无进度"],
                          name="🔴 无进度", marker_color="#9b59b6"))
    fig4.update_layout(barmode="group", xaxis_title="工厂", yaxis_title="PO 组合数", height=350,
                       legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig4, use_container_width=True)

st.markdown("---")

# ════════════════════════════════════════════
# 6. 快速导航
# ════════════════════════════════════════════
st.markdown("### 📌 快速导航")
col_a, col_b, col_c = st.columns(3)
with col_a:
    st.info("📊 **总览仪表板**（当前页面）")
with col_b:
    st.page_link("pages/1_Consistency_Checks.py", label="📋 一致性检查", icon="✅")
with col_c:
    st.page_link("pages/2_TQC3_vs_WIP8.py", label="📊 TQC3 vs WIP8 对比", icon="📈")
