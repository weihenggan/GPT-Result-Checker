#!/usr/bin/env python3
"""Streamlit app to visualize GPT prompt result comparisons."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from compare_prompt_results import (
    PROMPT_COLUMNS,
    compare_values,
    generate_comparison,
    generate_summary,
)


def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(layout="wide")
    st.title("GPT Prompt Comparison Viewer")
    st.write(
        "Upload a CSV file containing GPT extraction results for NPR and Sandbox "
        "environments to compare prompt outputs."
    )

    uploaded_file = st.file_uploader("CSV file", type="csv")
    if not uploaded_file:
        st.info("Awaiting CSV upload.")
        return

    df = pd.read_csv(uploaded_file)
    comp_df = generate_comparison(df)
    if comp_df.empty:
        st.warning("No case pairs with both NPR and Sandbox found.")
        return

    summary_df = generate_summary(comp_df)

    st.subheader("Comparison Details")
    st.dataframe(comp_df)

    st.subheader("Summary")
    st.dataframe(summary_df)

    st.subheader("Exact Text Comparison")
    case_options = (
        comp_df["casenumber"].astype(str)
        + " | "
        + comp_df["attachment_name"].astype(str)
    )
    selected_case = st.selectbox("Case / Attachment", case_options)
    case_num, attach_name = selected_case.split(" | ")
    prompt = st.selectbox("Prompt", PROMPT_COLUMNS)

    npr_row = df[
        (df["casenumber"].astype(str) == case_num)
        & (df["attachment_name"].astype(str) == attach_name)
        & (df["environment"] == "NPR")
    ]
    sandbox_row = df[
        (df["casenumber"].astype(str) == case_num)
        & (df["attachment_name"].astype(str) == attach_name)
        & (df["environment"] == "Sandbox")
    ]
    npr_text = npr_row[prompt].iloc[0] if not npr_row.empty else ""
    sandbox_text = sandbox_row[prompt].iloc[0] if not sandbox_row.empty else ""

    col1, col2 = st.columns(2)
    col1.text_area("NPR", npr_text, height=500)
    col2.text_area("Sandbox", sandbox_text, height=500)

    status, detail = compare_values(npr_text, sandbox_text)
    if status == "DIFFERENT" and detail:
        st.subheader("Diff")
        st.code(detail)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        comp_df.to_excel(writer, sheet_name="Comparison", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
    buffer.seek(0)

    st.download_button(
        label="Download Excel Report",
        data=buffer,
        file_name="comparison_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    main()
