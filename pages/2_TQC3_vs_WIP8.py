"""
Page 2: TQC3 vs WIP8 对比分析
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
title = f"📊 TQC3 vs WIP8 产出对比 - {'全部工厂' if is_all else selected_factory}"
st.title(title)

df_version = st.session_state.get("df_version", 0)
date_range = st.session_state.get("date_range", None)
date_key = f"{date_range[0]}_{date_range[1]}" if isinstance(date_range, tuple) and len(date_range) == 2 else "all"
cache_key = f"{df_version}_{date_key}_{'all' if is_all else selected_factory}"

@st.cache_data(show_spinner=False)
def _compute_daily_agg(df_input, key: str):
    """Cache daily aggregation by factory"""
    return df_input.groupby(df_input["date"]).agg(
        wip8_outputs=("wip8_outputs", "sum"),
        tqc3_pass_qty=("tqc3_pass_qty", "sum"),
    ).reset_index()

@st.cache_data(show_spinner=False)
def _compute_po_agg(df_input, key: str):
    """Cache PO-level aggregation"""
    return df_input.groupby(["po_number", "style_number", "factory_name"]).agg(
        wip8_outputs=("wip8_outputs", "sum"),
        tqc3_pass_qty=("tqc3_pass_qty", "sum"),
        date_count=("date", "nunique"),
    ).reset_index()

@st.cache_data(show_spinner=False)
def _compute_style_agg(df_input, key: str):
    """Cache Style-level aggregation"""
    return df_input.groupby(["style_number", "factory_name"]).agg(
        wip8_outputs=("wip8_outputs", "sum"),
        tqc3_pass_qty=("tqc3_pass_qty", "sum"),
        po_count=("po_number", "nunique"),
    ).reset_index()

# Pre-compute all aggregations
daily_agg = _compute_daily_agg(df, cache_key)
po_agg = _compute_po_agg(df, cache_key)
style_agg = _compute_style_agg(df, cache_key)

st.markdown(
    """对比分析 **TQC3 Pass Qty** 与 **WIP8 Outputs** 的差异。
    **预期**: `wip8_outputs == tqc3_pass_qty`，差异可能表示数据采集或流程问题。"""
)

# ── 全局指标 ──
total_records = len(df)
match_count = (df["wip8_outputs"] == df["tqc3_pass_qty"]).sum()
match_rate = match_count / total_records * 100 if total_records > 0 else 0
total_diff = df["diff"].abs().sum()

col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("📋 记录数", f"{total_records:,}")
with col2: st.metric("✅ 匹配数", f"{match_count:,}")
with col3: st.metric("匹配率", f"{match_rate:.1f}%")
with col4: st.metric("总绝对差异", f"{total_diff:,}")

st.markdown("---")

# ── 辅助函数 ──
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


# ── 2.1 每日总产出对比 ──
st.markdown("### 2.1 每日总产出对比")

agg_level = st.radio(
    "选择查看层级",
    ["工厂总览 (Daily)", "PO 级别", "Style 级别"],
    horizontal=True, key="agg_level",
)

if agg_level == "工厂总览 (Daily)":
    daily_agg["diff"] = daily_agg["wip8_outputs"] - daily_agg["tqc3_pass_qty"]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily_agg["date"], y=daily_agg["wip8_outputs"],
                         name="WIP8 Outputs", marker_color="#3498db", opacity=0.8))
    fig.add_trace(go.Bar(x=daily_agg["date"], y=daily_agg["tqc3_pass_qty"],
                         name="TQC3 Pass Qty", marker_color="#e67e22", opacity=0.8))
    fig.update_layout(barmode="group", xaxis_title="日期", yaxis_title="数量", height=450,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 每日 WIP8 - TQC3 差异")
    fig_diff = px.line(daily_agg, x="date", y="diff", markers=True,
                       labels={"diff": "差异 (WIP8 - TQC3)", "date": "日期"})
    fig_diff.add_hline(y=0, line_dash="dash", line_color="red")
    fig_diff.update_layout(height=300)
    st.plotly_chart(fig_diff, use_container_width=True)

    # 下钻
    st.markdown("#### 📋 选择日期查看该天 PO 明细")
    with st.expander("点击展开", expanded=False):
        selected_date = st.selectbox(
            "选择日期", sorted(df["date"].unique()),
            format_func=lambda d: d.strftime("%Y-%m-%d"),
        )
        if selected_date is not None:
            detail_df = df[df["date"] == selected_date].copy()
            detail_df["diff"] = detail_df["wip8_outputs"] - detail_df["tqc3_pass_qty"]
            st.dataframe(
                detail_df[["po_number", "style_number", "color_code", "ship_id",
                           "wip8_outputs", "tqc3_pass_qty", "diff"]].sort_values("diff", ascending=False),
                use_container_width=True, hide_index=True,
            )

elif agg_level == "PO 级别":
    po_agg["diff"] = po_agg["wip8_outputs"] - po_agg["tqc3_pass_qty"]
    po_agg["diff_pct"] = np.where(
        po_agg["tqc3_pass_qty"] != 0,
        po_agg["diff"] / po_agg["tqc3_pass_qty"] * 100, 0,
    )

    st.markdown(f"共有 **{len(po_agg)}** 个 PO")

    fig_po = px.scatter(
        po_agg, x="tqc3_pass_qty", y="wip8_outputs", color="diff_pct",
        size="date_count", hover_data=["po_number", "style_number", "diff_pct"],
        labels={"tqc3_pass_qty": "TQC3 (累计)", "wip8_outputs": "WIP8 (累计)", "diff_pct": "差异(%)"},
        color_continuous_scale="RdYlBu", range_color=[-50, 50],
    )
    max_val = max(po_agg["wip8_outputs"].max(), po_agg["tqc3_pass_qty"].max())
    fig_po.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode="lines",
                                line=dict(color="gray", dash="dash"), name="y=x"))
    fig_po.update_layout(height=500)
    st.plotly_chart(fig_po, use_container_width=True)

    st.markdown("#### PO 级别明细")
    search_po_po = st.text_input("🔍 搜索 PO 号", "", key="po_po_search",
                                  placeholder="输入 PO 号关键字...")
    po_show = po_agg.copy()
    if search_po_po:
        po_show = po_show[po_show['po_number'].astype(str).str.contains(search_po_po, case=False, na=False)]
    st.dataframe(
        po_show.sort_values("diff", ascending=False),
        use_container_width=True, hide_index=True,
        column_config={"diff_pct": st.column_config.NumberColumn("差异(%)", format="%.1f%%")},
    )

else:  # Style 级别
    style_agg["diff"] = style_agg["wip8_outputs"] - style_agg["tqc3_pass_qty"]
    style_agg["diff_pct"] = np.where(
        style_agg["tqc3_pass_qty"] != 0,
        style_agg["diff"] / style_agg["tqc3_pass_qty"] * 100, 0,
    )

    st.markdown(f"共有 **{len(style_agg)}** 个 Style")

    fig_style = go.Figure()
    fig_style.add_trace(go.Bar(x=style_agg["style_number"], y=style_agg["wip8_outputs"],
                               name="WIP8 Outputs", marker_color="#3498db"))
    fig_style.add_trace(go.Bar(x=style_agg["style_number"], y=style_agg["tqc3_pass_qty"],
                               name="TQC3 Pass Qty", marker_color="#e67e22"))
    fig_style.update_layout(barmode="group", xaxis_title="Style", yaxis_title="数量", height=400)
    st.plotly_chart(fig_style, use_container_width=True)

    st.markdown("#### Style 级别明细")
    st.dataframe(style_agg.sort_values("diff", ascending=False), use_container_width=True, hide_index=True)

    st.markdown("#### 🔍 选择 Style 查看 PO")
    selected_style = st.selectbox("选择 Style", sorted(df["style_number"].unique()))
    if selected_style:
        style_po_df = (
            df[df["style_number"] == selected_style]
            .groupby(["po_number", "style_number", "color_code", "factory_name"])
            .agg(wip8_outputs=("wip8_outputs", "sum"), tqc3_pass_qty=("tqc3_pass_qty", "sum"))
            .reset_index()
        )
        style_po_df["diff"] = style_po_df["wip8_outputs"] - style_po_df["tqc3_pass_qty"]
        st.dataframe(style_po_df.sort_values("diff", ascending=False), use_container_width=True, hide_index=True)


# ── 2.2 差异明细总表 ──
st.markdown("---")
st.markdown("### 2.2 差异明细数据")

show_all = st.checkbox("显示所有记录", value=False)
if show_all:
    diff_df = df.copy()
else:
    diff_df = df[df["wip8_outputs"] != df["tqc3_pass_qty"]].copy()
    st.info(f"默认仅显示存在差异的记录（{len(diff_df)} 条）")

if len(diff_df) > 0:
    diff_filtered = add_table_filters(diff_df, key_prefix="diff_detail")
    diff_display_cols = ["date", "factory_name", "po_number", "style_number", "color_code", "ship_id",
                         "wip8_outputs", "tqc3_pass_qty", "diff", "diff_pct"]
    diff_display_cols = [c for c in diff_display_cols if c in diff_filtered.columns]
    st.dataframe(
        diff_filtered[diff_display_cols].sort_values(["date", "po_number"]),
        use_container_width=True, hide_index=True, height=500,
        column_config={"diff_pct": st.column_config.NumberColumn("差异(%)", format="%.1f%%")},
    )
    csv_diff = diff_filtered[diff_display_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 下载差异数据 CSV", csv_diff, f"tqc3_vs_wip8_diff.csv", "text/csv")
