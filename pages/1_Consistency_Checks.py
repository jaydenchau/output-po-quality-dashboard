"""
Page 1: Output & PO Status 一致性检查
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from utils.data_loader import build_sidebar

# ── 共享侧边栏（含工厂筛选、日期筛选、数据管理） ──
df = build_sidebar()


selected_factory = st.session_state.get("selected_factory", "")
is_all = st.session_state.get("is_all_factories", False)
title = f"📋 一致性检查 - {'全部工厂' if is_all else selected_factory}"
st.title(title)

cache_key = "all" if is_all else selected_factory

@st.cache_data(show_spinner=False)
def _compute_checks(_df, _key: str):
    """Cache consistency checks by factory, only recompute on data/factory change"""
    c = _df.copy()
    c["check_wip8_tqc3"] = c["wip8_outputs"] == c["tqc3_pass_qty"]
    c["check_wip8_inc"] = c["wip8_outputs"] == c["wip8_po_status_increase"]
    c["check_fg10_nonneg"] = c["fg10_po_status_increase"] >= 0
    c["all_pass"] = c["check_wip8_tqc3"] & c["check_wip8_inc"] & c["check_fg10_nonneg"]
    # Daily stats for trend chart
    daily = c.groupby(c["date"]).agg(
        总记录=("all_pass", "count"),
        异常数=("all_pass", lambda x: (~x).sum())
    ).reset_index()
    daily["通过率"] = (daily["总记录"] - daily["异常数"]) / daily["总记录"] * 100
    return c, daily

@st.cache_data(show_spinner=False)
def _compute_neg_increment(_df, _key: str):
    """Cache negative increment analysis"""
    neg = _df[_df["wip8_po_status_increase"] < 0].copy()
    daily_neg = _df.groupby(_df["date"])["wip8_po_status_increase"].apply(
        lambda x: (x < 0).sum()).reset_index(name="负增量数")
    return neg, daily_neg

@st.cache_data(show_spinner=False)
def _compute_po_completion(_df, _key: str):
    """Cache PO completion analysis"""
    g = (
        _df.groupby(["po_number", "style_number", "color_code", "ship_id", "factory_name"], as_index=False)
        .agg(
            total_wip8_output=("wip8_outputs", "sum"),
            po_quantity=("po_quantity", "first"),
            date_count=("date", "nunique"),
        )
    )
    g["completion_rate"] = g["total_wip8_output"] / g["po_quantity"] * 100
    g["over_quota"] = g["completion_rate"] > 105
    g["far_below"] = (g["total_wip8_output"] > 0) & (g["completion_rate"] < 30)
    g["zero_progress"] = g["total_wip8_output"] == 0
    return g

# Compute (or get from cache)
df_c, daily_stats = _compute_checks(df, cache_key)
neg_df_full, neg_daily = _compute_neg_increment(df, cache_key)
po_grouped = _compute_po_completion(df, cache_key)


# ── 辅助函数：表格搜索筛选 ──
def add_table_filters(df_in, key_prefix=""):
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        s_date = st.date_input("起始日期", df_in["date"].min().date(), key=f"{key_prefix}_sdate")
    with col_f2:
        e_date = st.date_input("截止日期", df_in["date"].max().date(), key=f"{key_prefix}_edate")
    with col_f3:
        search_po = st.text_input("🔍 搜索 PO 号", "", key=f"{key_prefix}_po_search",
                                  placeholder="输入 PO 号关键字...")
    filtered = df_in.copy()
    filtered = filtered[
        (filtered["date"] >= pd.Timestamp(s_date))
        & (filtered["date"] <= pd.Timestamp(e_date))
    ]
    if search_po:
        filtered = filtered[
            filtered["po_number"].astype(str).str.contains(search_po, case=False, na=False)
        ]
    return filtered


# ── 三个 Tab ──
tab1, tab2, tab3 = st.tabs([
    "1.1 WIP8 vs Output vs FG10 验证",
    "1.2 负增量检查",
    "1.3 累积产出 vs PO 数量",
])


# ════════════════════════════════════════════
# TAB 1
# ════════════════════════════════════════════
with tab1:
    st.markdown(
        """### 验证规则
        - **规则 1**: `wip8_outputs == tqc3_pass_qty`
        - **规则 2**: `wip8_outputs == wip8_po_status_increase`
        - **规则 3**: `fg10_po_status_increase >= 0`
        """
    )

    total = len(df_c)
    pass_all = df_c["all_pass"].sum()
    fail_count = total - pass_all
    rate = pass_all / total * 100 if total > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("📋 总记录", f"{total:,}")
    with col2: st.metric("✅ 全部通过", f"{pass_all:,}")
    with col3: st.metric("❌ 存在异常", f"{fail_count:,}", delta=f"-{fail_count}" if fail_count else "0", delta_color="inverse")
    with col4: st.metric("📈 通过率", f"{rate:.1f}%")
    st.progress(rate / 100, text=f"综合通过率 {rate:.1f}%")

    st.markdown("### 各检查项统计")
    check_summary = pd.DataFrame({
        "检查项": ["wip8_outputs == tqc3_pass_qty", "wip8_outputs == wip8_po_status_increase", "fg10_po_status_increase >= 0"],
        "通过数": [df_c["check_wip8_tqc3"].sum(), df_c["check_wip8_inc"].sum(), df_c["check_fg10_nonneg"].sum()],
        "异常数": [total - df_c["check_wip8_tqc3"].sum(), total - df_c["check_wip8_inc"].sum(), total - df_c["check_fg10_nonneg"].sum()],
        "通过率": [f"{df_c['check_wip8_tqc3'].sum()/total*100:.1f}%", f"{df_c['check_wip8_inc'].sum()/total*100:.1f}%", f"{df_c['check_fg10_nonneg'].sum()/total*100:.1f}%"],
    })
    st.dataframe(check_summary, use_container_width=True, hide_index=True)

    # 每日趋势
    st.markdown("### 每日异常数量趋势")


    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily_stats["date"], y=daily_stats["异常数"], name="异常数", marker_color="#e74c3c", opacity=0.7))
    fig.add_trace(go.Scatter(x=daily_stats["date"], y=daily_stats["通过率"], name="通过率(%)", yaxis="y2", marker_color="#2ecc71", line=dict(width=3)))
    fig.update_layout(xaxis_title="日期", yaxis_title="异常数",
                      yaxis2=dict(title="通过率(%)", overlaying="y", side="right", range=[0, 105]),
                      hovermode="x unified", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # 异常明细
    st.markdown("### ❌ 异常数据明细")
    fail_df = df_c[~df_c["all_pass"]].copy()
    fail_df["失败检查"] = ""
    fail_df.loc[~fail_df["check_wip8_tqc3"], "失败检查"] += "WIP8!=TQC3 "
    fail_df.loc[~fail_df["check_wip8_inc"], "失败检查"] += "WIP8!=Increase "
    fail_df.loc[~fail_df["check_fg10_nonneg"], "失败检查"] += "FG10负增量 "

    if len(fail_df) > 0:
        fail_filtered = add_table_filters(fail_df, key_prefix="tab1_fail")
        display_cols = ["date", "factory_name", "po_number", "style_number", "color_code", "ship_id",
                        "wip8_outputs", "tqc3_pass_qty", "wip8_po_status_increase", "fg10_po_status_increase", "失败检查"]
        display_cols = [c for c in display_cols if c in fail_filtered.columns]
        st.dataframe(fail_filtered[display_cols].sort_values(["date", "po_number"]),
                     use_container_width=True, hide_index=True, height=500)
        csv = fail_filtered[display_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 下载异常数据 CSV", csv, f"consistency_anomalies.csv", "text/csv")
    else:
        st.success("🎉 所有记录均通过一致性检查！")


# ════════════════════════════════════════════
# TAB 2: 负增量检查
# ════════════════════════════════════════════
with tab2:
    st.markdown("""### 检查 WIP8 PO Status 负增量
    - `wip8_po_status_increase` 应为非负数（>= 0）
    - 负值意味着 PO 状态倒退，属于数据异常
    """)

    total_all = len(df)
    neg_count = len(neg_df_full)

    col1, col2, col3 = st.columns(3)
    with col1: st.metric("🔴 负增量记录数", f"{neg_count:,}")
    with col2: st.metric("占比", f"{neg_count/total_all*100:.2f}%" if total_all else "0%")
    with col3:
        avg_neg = neg_df_full["wip8_po_status_increase"].mean() if neg_count > 0 else 0
        st.metric("平均负增量", f"{avg_neg:.0f}" if neg_count > 0 else "N/A")

    if neg_count > 0:
        st.markdown("### 负增量分布")
        fig = px.histogram(neg_df_full, x="wip8_po_status_increase", nbins=20,
                           color_discrete_sequence=["#e74c3c"])
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 每日负增量数量趋势")
        pass  # already computed in cache
        fig2 = px.bar(neg_daily, x="date", y="负增量数", color="负增量数", color_continuous_scale="Reds")
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("### 📋 负增量数据明细")
        neg_filtered = add_table_filters(neg_df_full, key_prefix="tab2_neg")
        neg_display_cols = ["date", "factory_name", "po_number", "style_number", "color_code", "ship_id",
                            "wip8_outputs", "wip8_po_status_increase", "wip8_po_statu_completion_quantity"]
        neg_display_cols = [c for c in neg_display_cols if c in neg_filtered.columns]
        st.dataframe(neg_filtered[neg_display_cols].sort_values(["date", "po_number"]),
                     use_container_width=True, hide_index=True, height=500)
        csv2 = neg_filtered[neg_display_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 下载负增量数据 CSV", csv2, f"negative_increment.csv", "text/csv")
    else:
        st.success("🎉 没有发现负增量记录！")


# ════════════════════════════════════════════
# TAB 3: 累积产出 vs PO 数量
# ════════════════════════════════════════════
with tab3:
    st.markdown(
        """### 验证 Order-level WIP 累积产出 vs PO Quantity
        - 按 `po_number + style_number + color_code + ship_id` 分组
        - 加总 `wip8_outputs` 得到该 PO 组合的总产出
        - 与 `po_quantity`（PO 下单量）对比
        """
    )

    grouped = po_grouped
    total_orders = len(grouped)
    over_count = grouped["over_quota"].sum()
    below_count = grouped["far_below"].sum()
    zero_count = grouped["zero_progress"].sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("📦 PO 组合数", f"{total_orders:,}")
    with col2: st.metric("⚠️ 超量 (>105%)", f"{over_count:,}", delta=f"{over_count/total_orders*100:.1f}%" if total_orders else "0", delta_color="inverse")
    with col3: st.metric("⚠️ 进度偏低 (<30%)", f"{below_count:,}", delta=f"{below_count/total_orders*100:.1f}%" if total_orders else "0", delta_color="inverse")
    with col4: st.metric("🔴 无进度 (0)", f"{zero_count:,}", delta=f"{zero_count/total_orders*100:.1f}%" if total_orders else "0", delta_color="inverse")

    # 散点图
    st.markdown("### 总产出 vs PO 数量")
    fig3 = px.scatter(
        grouped, x="po_quantity", y="total_wip8_output", color="completion_rate",
        hover_data=["po_number", "style_number", "color_code", "completion_rate"],
        labels={"po_quantity": "PO 下单量", "total_wip8_output": "WIP8 总产出", "completion_rate": "完成率(%)"},
        color_continuous_scale="RdYlGn", range_color=[0, 150],
    )
    max_val = max(grouped["po_quantity"].max(), grouped["total_wip8_output"].max())
    fig3.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode="lines",
                              line=dict(color="gray", dash="dash"), name="y=x"))
    fig3.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val * 1.05], mode="lines",
                              line=dict(color="red", dash="dot"), name="105% 上限"))
    fig3.update_layout(height=500)
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("### 完成率分布")
    fig4 = px.histogram(grouped, x="completion_rate", nbins=30, color_discrete_sequence=["#3498db"])
    fig4.add_vline(x=105, line_dash="dash", line_color="red", annotation_text="105%")
    fig4.update_layout(height=350)
    st.plotly_chart(fig4, use_container_width=True)

    st.markdown("### ⚠️ 异常 PO 明细")
    anomaly_orders = grouped[grouped["over_quota"] | grouped["far_below"] | grouped["zero_progress"]].copy()
    if len(anomaly_orders) > 0:
        anomaly_orders["异常类型"] = ""
        anomaly_orders.loc[anomaly_orders["over_quota"], "异常类型"] += "超量 "
        anomaly_orders.loc[anomaly_orders["far_below"], "异常类型"] += "进度偏低 "
        anomaly_orders.loc[anomaly_orders["zero_progress"], "异常类型"] += "无进度 "

        search_po3 = st.text_input("🔍 搜索 PO 号", "", key="tab3_po_search", placeholder="输入 PO 号关键字...")
        if search_po3:
            anomaly_orders = anomaly_orders[
                anomaly_orders["po_number"].astype(str).str.contains(search_po3, case=False, na=False)
            ]

        disp_cols = ["po_number", "style_number", "color_code", "ship_id", "factory_name",
                     "po_quantity", "total_wip8_output", "completion_rate", "异常类型"]
        disp_cols = [c for c in disp_cols if c in anomaly_orders.columns]
        st.dataframe(anomaly_orders[disp_cols].sort_values("completion_rate", ascending=False),
                     use_container_width=True, hide_index=True, height=500,
                     column_config={"completion_rate": st.column_config.NumberColumn("完成率(%)", format="%.1f%%")})
        csv3 = anomaly_orders[disp_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 下载异常 PO 数据 CSV", csv3, f"po_anomalies.csv", "text/csv")
    else:
        st.success("🎉 所有 PO 在正常范围内！")
