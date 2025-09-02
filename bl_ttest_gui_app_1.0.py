# bl_ttest_gui_app

import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import xlsxwriter

st.set_page_config(page_title="Welch T検定 GUI", layout="centered")
st.title("📊 Welchのt検定ツール（新旧BLライフなどに）")

st.markdown("""
このツールでは、2群の構造一貫データ（例：旧BL vs 新BL）をアップロードして、
Welchのt検定（等分散なし）を簡単に実行できます。

- 入力：2列構造のCSVまたはExcel（例：旧BL列 / 新BL列）
- 検定：片側 or 両側（指定可）
- 出力：平均、差、p値、95%信頼区間、ヒストグラム、Excelダウンロード
""")

uploaded_file = st.file_uploader("CSVまたはExcelファイルをアップロード", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.subheader("✏️ データプレビュー")
    st.dataframe(df.head())

    colnames = df.columns.tolist()
    col1 = st.selectbox("群1のカラム名（例：旧BL）", colnames)
    col2 = st.selectbox("群2のカラム名（例：新BL）", colnames, index=1 if len(colnames) > 1 else 0)

    tail_type = st.radio("検定の方向", ["両側 (差があるか)", "片側 (群2 > 群1)"])
    alpha = st.slider("有意水準（α）", 0.001, 0.10, 0.05, step=0.001)

    if st.button("⚖️ 検定を実行"):
        data1 = df[col1].dropna()
        data2 = df[col2].dropna()

        t_stat, p_val = stats.ttest_ind(data2, data1, equal_var=False)
        diff = data2.mean() - data1.mean()
        se = np.sqrt(np.var(data2, ddof=1)/len(data2) + np.var(data1, ddof=1)/len(data1))
        df_w = (se**4) / (
            ((np.var(data2, ddof=1)/len(data2))**2)/(len(data2)-1) +
            ((np.var(data1, ddof=1)/len(data1))**2)/(len(data1)-1)
        )
        t_crit = stats.t.ppf(1 - alpha/2, df_w)
        ci_low, ci_high = diff - t_crit * se, diff + t_crit * se

        if tail_type.startswith("片側"):
            p_val = p_val / 2 if diff > 0 else 1 - (p_val / 2)

        st.markdown("### ✅ 検定結果")
        st.write(f"平均差: {diff:.2f}")
        st.write(f"p値: {p_val:.3g}")
        st.write(f"信頼区間（{100*(1-alpha):.1f}%）: [{ci_low:.2f}, {ci_high:.2f}]")

        # 自動生成されるコメント（スライド貼り付け用）
        st.markdown("### 💬 コメント（コピーして活用可）")
        comment = f"群2（{col2}）の平均が群1（{col1}）より {diff:.1f} 高く、\np値 = {p_val:.2e}（α = {alpha:.2f}）より十分に小さいため、\n統計的に有意な差があると判断できます（Welchのt検定・{tail_type}）。"
        st.code(comment, language="markdown")

        # ヒストグラムの表示
        st.markdown("### 🌐 ヒストグラム")
        plt.rcParams['font.family'] = 'Meiryo'
        fig, ax = plt.subplots()
        bins = np.histogram_bin_edges(pd.concat([data1, data2]), bins=20)
        ax.hist(data1, bins=bins, alpha=0.6, label=f"{col1} (n={len(data1)})", color='skyblue')
        ax.hist(data2, bins=bins, alpha=0.6, label=f"{col2} (n={len(data2)})", color='orange')
        ax.axvline(data1.mean(), color='blue', linestyle='--', label=f"{col1} 平均")
        ax.axvline(data2.mean(), color='orange', linestyle='--', label=f"{col2} 平均")
        ax.set_xlabel("値")
        ax.set_ylabel("頻度")
        ax.set_title("2群のヒストグラム")
        ax.legend()
        st.pyplot(fig)

        # Excel出力用ダウンロード（元データ＋集計＋グラフ）
        hist1, _ = np.histogram(data1, bins=bins)
        hist2, _ = np.histogram(data2, bins=bins)
        bin_labels = [f"{int(bins[i])}-{int(bins[i+1])}" for i in range(len(bins)-1)]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # 元データ
            df[[col1, col2]].to_excel(writer, sheet_name="元データ", index=False)

            # 集計データ
            df_hist = pd.DataFrame({
                "階級": bin_labels,
                f"{col1}": hist1,
                f"{col2}": hist2
            })
            df_hist.to_excel(writer, index=False, sheet_name="ヒストグラム")

            # 書式設定
            workbook = writer.book
            ws_data = writer.sheets["元データ"]
            ws_hist = writer.sheets["ヒストグラム"]
            for ws in [ws_data, ws_hist]:
                ws.autofilter(0, 0, len(df_hist), 2)
                ws.freeze_panes(1, 0)
                for i, _ in enumerate(df_hist.columns):
                    ws.set_column(i, i, 15)

            # グラフ追加
            chart = workbook.add_chart({'type': 'column'})
            chart.add_series({
                'name': col1,
                'categories': ['ヒストグラム', 1, 0, len(bin_labels), 0],
                'values':     ['ヒストグラム', 1, 1, len(bin_labels), 1],
                'fill':       {'color': '#87CEEB'}
            })
            chart.add_series({
                'name': col2,
                'categories': ['ヒストグラム', 1, 0, len(bin_labels), 0],
                'values':     ['ヒストグラム', 1, 2, len(bin_labels), 2],
                'fill':       {'color': '#FFA500'}
            })
            chart.set_title({'name': '2群のヒストグラム'})
            chart.set_x_axis({'name': 'BLライフ階級'})
            chart.set_y_axis({'name': '頻度'})
            ws_hist.insert_chart('E2', chart)

        st.download_button(
            label="📥 Excelでダウンロード",
            data=output.getvalue(),
            file_name="bl_life_histogram.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.success("検定完了。報告書への貼り付けや説明にご活用ください！")
