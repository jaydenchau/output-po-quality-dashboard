"""
数据加载模块。
使用 session_state 缓存数据避免重复读取，上传 CSV 只需加载一次。
"""

import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime

UPLOAD_DIR = Path(__file__).parent.parent / "data"
UPLOAD_PATH = UPLOAD_DIR / "uploaded_data.parquet"
_LEGACY_UPLOAD_PATH = UPLOAD_DIR / "uploaded_data.json"  # 兼容旧版
SAMPLE_PATH = UPLOAD_DIR / "sample_data.json"


def get_data_source() -> str:
    if UPLOAD_PATH.exists() or _LEGACY_UPLOAD_PATH.exists():
        return "uploaded"
    return "sample"


def get_data_path() -> str:
    if UPLOAD_PATH.exists():
        return str(UPLOAD_PATH)
    if _LEGACY_UPLOAD_PATH.exists():
        return str(_LEGACY_UPLOAD_PATH)
    return str(SAMPLE_PATH)


def save_uploaded_file(uploaded_file) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(UPLOAD_PATH), "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(UPLOAD_PATH)




def _read_data_from_bytes(uploaded_file) -> pd.DataFrame:
    """从上传的文件读取（CSV 或 JSON）"""
    import io
    content = uploaded_file.getvalue()
    if uploaded_file.name.endswith(".json"):
        return pd.read_json(io.BytesIO(content), orient="records", convert_dates=["date"])
    else:
        return pd.read_csv(io.BytesIO(content), parse_dates=["date"], low_memory=False)
def clear_uploaded_data():
    if UPLOAD_PATH.exists():
        UPLOAD_PATH.unlink()
    if _LEGACY_UPLOAD_PATH.exists():
        _LEGACY_UPLOAD_PATH.unlink()


_NUMERIC_COLS = [
    "po_quantity", "wip8_outputs", "tqc3_pass_qty",
    "wip8_po_status_increase", "fg10_po_status_increase", "fg14_po_status_increase",
    "wip8_po_statu_completion_quantity", "fg10_po_statu_completion_quantity",
    "fg14_po_statu_completion_quantity",
]


def _finalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """类型转换 + 预计算派生列（读取和上传时共用）"""
    cols = [c for c in _NUMERIC_COLS if c in df.columns]
    if cols:
        df[cols] = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype("int32")
    if "wip8_outputs" in df.columns and "tqc3_pass_qty" in df.columns:
        df["diff"] = df["wip8_outputs"] - df["tqc3_pass_qty"]
        df["diff_pct"] = (
            (df["wip8_outputs"] - df["tqc3_pass_qty"])
            / df["tqc3_pass_qty"].replace(0, float("nan"))
            * 100
        ).fillna(0).astype("float32")
    return df


def _read_data(path: str) -> pd.DataFrame:
    """读取数据文件（支持 .parquet / .csv / .json），做类型转换"""
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
        if "date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"])
    elif path.endswith(".json"):
        df = pd.read_json(path, orient="records", convert_dates=["date"])
    else:
        df = pd.read_csv(path, parse_dates=["date"], low_memory=False)
    return _finalize_df(df)


def load_data() -> pd.DataFrame:
    """
    从 session_state 获取数据，避免重复读取和缓存哈希开销。
    只有当文件路径变了（上传新文件）才会重新读取。
    """
    current_path = get_data_path()

    # 如果 session_state 已有数据且路径没变，直接返回
    if ("df_raw" in st.session_state
            and "df_path" in st.session_state
            and st.session_state["df_path"] == current_path):
        st.session_state["df_version"] = st.session_state.get("df_version", 0)
        return st.session_state["df_raw"]

    # 需要重新读取
    if not Path(current_path).exists():
        st.error(f"数据文件不存在: {current_path}")
        st.session_state["df_raw"] = pd.DataFrame()
        st.session_state["df_path"] = current_path
        return st.session_state["df_raw"]

    with st.spinner("正在加载数据..."):
        df = _read_data(current_path)

    st.session_state["df_raw"] = df
    st.session_state["df_path"] = current_path
    st.session_state["df_version"] = st.session_state.get("df_version", 0) + 1
    return df


def get_factory_list(df: pd.DataFrame) -> list:
    return sorted(df["factory_name"].unique())


def get_date_range(df: pd.DataFrame) -> tuple:
    return df["date"].min(), df["date"].max()


# ════════════════════════════════════════════
# 共享侧边栏
# ════════════════════════════════════════════

def build_sidebar() -> pd.DataFrame:
    """
    侧边栏：工厂筛选 → 日期范围 → 数据管理 → 数据概况
    返回筛选后的 DataFrame。
    """
    try:
        # ── 加载数据（仅首次或上传后读取） ──
        df = load_data()
        if df.empty:
            st.error("无法加载数据，请检查 CSV 文件")
            st.stop()
    except Exception as e:
        st.error(f"数据加载失败: {e}")
        st.stop()

    # ── 1) 工厂筛选 ──
    st.sidebar.title("🏭 工厂筛选")
    all_factories = get_factory_list(df)
    factory_options = ["🏭 全部工厂"] + all_factories
    selected_factory = st.sidebar.selectbox(
        "选择工厂", factory_options, index=0, key="global_factory",
    )

    # ── 2) 日期范围 ──
    st.sidebar.markdown("### 📅 日期范围")
    min_date, max_date = get_date_range(df)
    date_range = st.sidebar.date_input(
        "日期范围",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="global_date_range",
    )

    st.sidebar.markdown("---")

    # ── 3) 数据管理 ──
    st.sidebar.markdown("### 🔧 数据管理")
    data_src = get_data_source()
    if data_src == "uploaded":
        st.sidebar.success("✅ 当前：**上次上传的 CSV**")
        mtime = datetime.fromtimestamp(Path(get_data_path()).stat().st_mtime)
        st.sidebar.caption(f"上传时间：{mtime.strftime('%Y-%m-%d %H:%M')}")
    else:
        st.sidebar.info("📄 当前：**样本数据**")

    uploaded_file = st.sidebar.file_uploader(
        "上传 CSV/JSON 替换数据", type=["csv", "json"],
        help="上传后自动保存为 JSON，下次打开自动加载。",
    )
    if uploaded_file is not None:
        with st.spinner("正在保存并加载数据..."):
            # 读取 + 类型转换 + 派生列
            temp_df = _finalize_df(_read_data_from_bytes(uploaded_file))
            # 后台写 Parquet（下次启动直接读）
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            temp_df.to_parquet(str(UPLOAD_PATH), index=False)
            if _LEGACY_UPLOAD_PATH.exists():
                _LEGACY_UPLOAD_PATH.unlink()
            # 直接把已处理的 df 放入 session_state，跳过二次读取
            st.session_state["df_raw"] = temp_df
            st.session_state["df_path"] = str(UPLOAD_PATH)
            st.session_state["df_version"] = st.session_state.get("df_version", 0) + 1
            st.rerun()

    if data_src == "uploaded":
        if st.sidebar.button("🔄 切换回样本数据"):
            clear_uploaded_data()
            if "df_path" in st.session_state:
                del st.session_state["df_path"]
            st.rerun()

    st.sidebar.markdown("---")

    # ── 4) 数据概况 ──
    st.sidebar.markdown("### 📋 数据概况")
    st.sidebar.metric("总记录数", f"{len(df):,}")
    st.sidebar.metric("工厂数", len(all_factories))

    # ── 应用筛选 ──
    is_all = (selected_factory == "🏭 全部工厂")
    filtered = df if is_all else df[df["factory_name"] == selected_factory]

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            (filtered["date"] >= pd.Timestamp(start_date))
            & (filtered["date"] <= pd.Timestamp(end_date))
        ]

    # ── 保存到 session_state ──
    st.session_state["df_full"] = df
    st.session_state["selected_factory"] = selected_factory
    st.session_state["is_all_factories"] = is_all
    st.session_state["date_range"] = date_range
    st.session_state["filtered_df"] = filtered

    return filtered
