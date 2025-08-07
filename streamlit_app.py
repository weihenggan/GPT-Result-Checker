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

    if "validations" not in st.session_state:
        st.session_state["validations"] = {}

    total_pairs = len(comp_df) * len(PROMPT_COLUMNS)
    validated_count = len(st.session_state["validations"])
    remaining = total_pairs - validated_count

    st.subheader("Validation Progress")
    st.write(f"Validated: {validated_count} | Remaining: {remaining}")
    st.progress(validated_count / total_pairs if total_pairs else 0)

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

    key = f"{case_num}|{attach_name}|{prompt}"
    validation = st.session_state["validations"].get(key, {})

    label_options = ["", "Correct", "Acceptable", "Wrong"]
    index = label_options.index(validation.get("label", ""))
    label = st.radio(
        "Label",
        label_options,
        index=index,
        format_func=lambda x: "Select Label" if x == "" else x,
        key=f"label_{key}",
    )

    acceptable_reason = ""
    if label == "Acceptable":
        acceptable_reason = st.text_input(
            "Acceptable Reason",
            value=validation.get("acceptable_reason", ""),
            key=f"acceptable_{key}",
        )
    else:
        st.session_state.pop(f"acceptable_{key}", None)

    standard_response = st.text_area(
        "Standard Response",
        value=validation.get("standard_response", ""),
        height=120,
        key=f"standard_{key}",
    )
    remark = st.text_area(
        "Remark",
        value=validation.get("remark", ""),
        height=120,
        key=f"remark_{key}",
    )

    if label:
        st.session_state["validations"][key] = {
            "case_num": case_num,
            "attachment_name": attach_name,
            "prompt": prompt,
            "npr": npr_text,
            "sandbox": sandbox_text,
            "label": label,
            "acceptable_reason": st.session_state.get(f"acceptable_{key}", ""),
            "standard_response": standard_response,
            "remark": remark,
        }
    else:
        st.session_state["validations"].pop(key, None)

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

    if st.session_state["validations"]:
        export_df = pd.DataFrame(
            {
                "Case/Attachment ID": [
                    f"{v['case_num']} | {v['attachment_name']}" for v in st.session_state["validations"].values()
                ],
                "Prompt": [v["prompt"] for v in st.session_state["validations"].values()],
                "NPR Result": [v["npr"] for v in st.session_state["validations"].values()],
                "Sandbox Result": [v["sandbox"] for v in st.session_state["validations"].values()],
                "Label": [v["label"] for v in st.session_state["validations"].values()],
                "Acceptable Reason": [v["acceptable_reason"] for v in st.session_state["validations"].values()],
                "Standard Response": [v["standard_response"] for v in st.session_state["validations"].values()],
                "Remark": [v["remark"] for v in st.session_state["validations"].values()],
            }
        )
        csv_data = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Save Validation Results",
            data=csv_data,
            file_name="validation_results.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
