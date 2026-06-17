"""
生成样本 CSV 数据，模拟 ads.ads_dtd_po_status_output_quality_history 表。
有意植入一些异常，使分析看板展示时有内容可看。
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

FACTORIES = [
    {"factory_name": "越南平政厂", "factory_code": "VN_BZ"},
    {"factory_name": "柬埔寨金边厂", "factory_code": "KH_PP"},
    {"factory_name": "中国中山厂", "factory_code": "CN_ZS"},
]

STYLES = {
    "ST001": [("BLK", "SH01"), ("WHT", "SH01"), ("RED", "SH02")],
    "ST002": [("BLU", "SH03"), ("GRN", "SH03")],
    "ST003": [("YLW", "SH04"), ("BLK", "SH04"), ("WHT", "SH05")],
    "ST004": [("GRY", "SH06"), ("NVY", "SH06")],
    "ST005": [("PNK", "SH07"), ("LBL", "SH07"), ("WHT", "SH08")],
    "ST006": [("BLK", "SH09"), ("RED", "SH09")],
    "ST007": [("TEA", "SH10"), ("NVY", "SH10")],
}

PO_TYPES = ["FOB", "CMT", "FOB", "FOB", "CMT"]
START_DATE = datetime(2026, 5, 1)
NUM_DAYS = 35


def generate_po_base(po_id: int, factory_code: str):
    style_key = list(STYLES.keys())[np.random.randint(len(STYLES))]
    color_ship = STYLES[style_key][np.random.randint(len(STYLES[style_key]))]
    # 更大的PO数量，更真实
    po_qty = int(np.random.choice([800, 1000, 1500, 2000, 3000, 5000, 8000]))
    # 随机决定这个PO在什么时候开始生产（前中后期）
    start_delay = np.random.choice([0, 0, 0, 0, 0, 2, 3, 5, 7])
    return {
        "po_number": f"{factory_code}-PO-{po_id:04d}",
        "style_number": style_key,
        "color_code": color_ship[0],
        "ship_id": color_ship[1],
        "po_type": np.random.choice(PO_TYPES),
        "po_quantity": po_qty,
        "start_delay": start_delay,
    }


def generate_sample_data():
    rows = []
    for factory in FACTORIES:
        fc = factory["factory_code"]
        po_bases = [generate_po_base(i, fc) for i in range(1, 26)]

        for day_offset in range(NUM_DAYS):
            current_date = START_DATE + timedelta(days=day_offset)
            if current_date.weekday() == 6:
                continue

            active_count = max(1, int(len(po_bases) * 0.7))
            active_indices = np.random.choice(len(po_bases), size=active_count, replace=False)
            active_pos = [po_bases[i] for i in active_indices]

            for base in active_pos:
                po = base["po_number"]
                style = base["style_number"]
                color = base["color_code"]
                ship = base["ship_id"]
                po_qty = base["po_quantity"]

                # 还没到开始日期
                if day_offset < base["start_delay"]:
                    continue

                # 查找之前日期的累积量
                prev_row = None
                for r in reversed(rows):
                    if (r["factory_code"] == fc and r["po_number"] == po
                            and r["style_number"] == style
                            and r["color_code"] == color
                            and r["ship_id"] == ship):
                        prev_row = r
                        break

                prev_wip8_acc = prev_row["wip8_po_statu_completion_quantity"] if prev_row else 0
                prev_fg10_acc = prev_row["fg10_po_statu_completion_quantity"] if prev_row else 0
                prev_fg14_acc = prev_row["fg14_po_statu_completion_quantity"] if prev_row else 0

                # 如果已经完成了，就不再产生新产出（留白）
                # 但有 20% 概率 PO 完成后再产出（表示实际上有超量）
                is_completed = prev_wip8_acc >= po_qty
                if is_completed and np.random.random() < 0.8:
                    continue

                # 当天产出 - 接近完成的 PO 产出会减少
                if prev_wip8_acc > po_qty * 0.8:
                    daily_output = int(np.random.poisson(lam=40) + 15)
                elif prev_wip8_acc > po_qty * 0.5:
                    daily_output = int(np.random.poisson(lam=80) + 30)
                else:
                    daily_output = int(np.random.poisson(lam=120) + 50)
                daily_output = max(0, daily_output)

                # 不要超过 PO 数量太多（除非异常）
                max_allowed = int(po_qty * 1.15)
                if prev_wip8_acc + daily_output > max_allowed:
                    daily_output = max(0, max_allowed - prev_wip8_acc)

                # ── 异常植入 ──
                anomaly_roll = np.random.random()
                wip8_out = daily_output
                tqc3_out = daily_output
                wip8_inc = daily_output

                if anomaly_roll < 0.04:  # 4%: wip8_outputs != tqc3_pass_qty
                    diff = np.random.choice([-15, -10, 10, 15])
                    wip8_out = max(0, daily_output + diff)
                elif anomaly_roll < 0.07:  # 3%: 负增量
                    wip8_inc = -abs(int(np.random.normal(30, 10)))
                    wip8_out = daily_output
                    tqc3_out = daily_output
                elif anomaly_roll < 0.10:  # 3%: increase 与 output 不一致
                    wip8_inc = daily_output + np.random.choice([-20, 20])
                    wip8_out = daily_output
                    tqc3_out = daily_output

                # FG10/FG14 增量
                fg10_inc = int(wip8_inc * np.random.uniform(0.4, 0.9))
                fg14_inc = int(fg10_inc * np.random.uniform(0.3, 0.8))
                if np.random.random() < 0.02:
                    fg10_inc = -abs(int(np.random.normal(20, 10)))

                new_wip8_acc = max(0, prev_wip8_acc + wip8_inc)
                new_fg10_acc = max(0, prev_fg10_acc + fg10_inc)
                new_fg14_acc = max(0, prev_fg14_acc + fg14_inc)

                row = {
                    "id": f"{fc}_{current_date.strftime('%Y%m%d')}_{po}_{color}_{ship}",
                    "factory_name": factory["factory_name"],
                    "factory_code": fc,
                    "date": current_date,
                    "po_number": po,
                    "style_number": style,
                    "color_code": color,
                    "ship_id": ship,
                    "po_type": base["po_type"],
                    "po_quantity": po_qty,
                    "wip8_outputs": wip8_out,
                    "tqc3_pass_qty": tqc3_out,
                    "wip8_po_status_increase": wip8_inc,
                    "fg10_po_status_increase": fg10_inc,
                    "fg14_po_status_increase": fg14_inc,
                    "wip8_po_statu_completion_quantity": new_wip8_acc,
                    "fg10_po_statu_completion_quantity": new_fg10_acc,
                    "fg14_po_statu_completion_quantity": new_fg14_acc,
                }
                rows.append(row)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["factory_code", "date", "po_number"]).reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = generate_sample_data()
    output_path = "data/sample_data.csv"
    df.to_csv(output_path, index=False, date_format="%Y-%m-%d")
    print(f"生成 {len(df)} 行数据到 {output_path}")
    print(f"日期范围: {df['date'].min().date()} ~ {df['date'].max().date()}")
    print(f"工厂: {list(df['factory_name'].unique())}")
    print()

    # 分析完成率
    latest = df.sort_values('date').groupby(
        ['po_number', 'style_number', 'color_code', 'ship_id', 'factory_name'],
        as_index=False
    ).last()
    latest['rate'] = latest['wip8_po_statu_completion_quantity'] / latest['po_quantity'] * 100
    print(f"PO 组合数: {len(latest)}")
    print(f"完成率: 平均={latest['rate'].mean():.1f}%  中位数={latest['rate'].median():.1f}%")
    print(f"  0-50%:    {(latest['rate'] < 50).sum()} 个")
    print(f"  50-80%:   {((latest['rate'] >= 50) & (latest['rate'] < 80)).sum()} 个")
    print(f"  80-95%:   {((latest['rate'] >= 80) & (latest['rate'] < 95)).sum()} 个")
    print(f"  95-105%:  {((latest['rate'] >= 95) & (latest['rate'] <= 105)).sum()} 个")
    print(f"  105-115%: {((latest['rate'] > 105) & (latest['rate'] <= 115)).sum()} 个")
    print(f"  115%+:    {(latest['rate'] > 115).sum()} 个")
    print()

    total = len(df)
    wip8_vs_tqc3_diff = (df["wip8_outputs"] != df["tqc3_pass_qty"]).sum()
    wip8_vs_inc_diff = (df["wip8_outputs"] != df["wip8_po_status_increase"]).sum()
    neg_inc = (df["wip8_po_status_increase"] < 0).sum()
    print(f"异常统计:")
    print(f"  wip8_outputs != tqc3_pass_qty: {wip8_vs_tqc3_diff}/{total} ({wip8_vs_tqc3_diff/total*100:.1f}%)")
    print(f"  wip8_outputs != wip8_po_status_increase: {wip8_vs_inc_diff}/{total} ({wip8_vs_inc_diff/total*100:.1f}%)")
    print(f"  wip8_po_status_increase < 0: {neg_inc}/{total} ({neg_inc/total*100:.1f}%)")
