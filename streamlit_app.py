#!/usr/bin/env python3
"""Streamlit app to visualize GPT prompt result comparisons."""

from __future__ import annotations

import io
import json
import difflib
from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit.components.v1 import html as st_html
from streamlit.delta_generator import DeltaGenerator

from compare_prompt_results import (
    PROMPT_COLUMNS,
    generate_comparison,
    generate_summary,
)


def show_json_diff(
    npr_text: str,
    sandbox_text: str,
    container: DeltaGenerator | None = None,
) -> bool:
    """Render a side-by-side JSON diff view.

    Returns ``True`` if both inputs are valid JSON and the diff was rendered,
    otherwise returns ``False`` so the caller can fall back to plain text
    rendering.
    """

    try:
        npr_json = json.loads(npr_text)
        sandbox_json = json.loads(sandbox_text)
    except (TypeError, ValueError):
        return False

    npr_pretty = json.dumps(npr_json, indent=2, sort_keys=True)
    sandbox_pretty = json.dumps(sandbox_json, indent=2, sort_keys=True)

    diff = difflib.HtmlDiff(wrapcolumn=80)
    diff_table = diff.make_table(
        npr_pretty.splitlines(),
        sandbox_pretty.splitlines(),
        fromdesc="NPR",
        todesc="Sandbox",
        context=True,
        numlines=2,
    )

    html_content = f"""
        <style>
        .diff-viewer {{
            background: #1e1e1e;
            color: #fff;
            font-family: 'Fira Mono', 'Menlo', 'Consolas', monospace;
            overflow: auto;
            padding: 1rem;
            width: 100%;
            min-height: 600px;
            box-sizing: border-box;
        }}
        .diff-viewer table.diff {{
            border-collapse: collapse;
            width: 100%;
            table-layout: fixed;
        }}
        .diff-viewer table.diff td:nth-of-type(3),
        .diff-viewer table.diff td:nth-of-type(6) {{
            width: 50%;
        }}
        .diff-viewer .diff_header,
        .diff-viewer .diff_next {{
            background-color: #2a2c2e;
        }}
        .diff-viewer td.diff_header {{ text-align: left; }}
        .diff-viewer .diff_add,
        .diff-viewer .diff_chg,
        .diff-viewer .diff_sub {{
            background-color: #3498db !important;
            color: #fff !important;
            border-radius: 4px;
        }}
        </style>
        <div class="diff-viewer">{diff_table}</div>
    """
    if container is not None:
        with container:
            st_html(html_content, height=600)
    else:
        st_html(html_content, height=600)
    return True


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

    st.subheader("JSON Diff")
    diff_container = st.container()
    rendered = show_json_diff(npr_text, sandbox_text, diff_container)

    col1, col2 = st.columns(2)
    if rendered:
        try:
            col1.code(json.dumps(json.loads(npr_text), indent=2, sort_keys=True), language="json")
        except (TypeError, ValueError):
            col1.text_area("NPR", npr_text, height=500)
        try:
            col2.code(json.dumps(json.loads(sandbox_text), indent=2, sort_keys=True), language="json")
        except (TypeError, ValueError):
            col2.text_area("Sandbox", sandbox_text, height=500)
    else:
        col1.text_area("NPR", npr_text, height=500)
        col2.text_area("Sandbox", sandbox_text, height=500)

    key = f"{case_num}|{attach_name}|{prompt}"
    validation = st.session_state["validations"].get(key, {})

    label_options = ["", "Correct", "Acceptable", "Wrong"]

    npr_index = label_options.index(validation.get("npr_label", ""))
    npr_label = col1.radio(
        "Label",
        label_options,
        index=npr_index,
        format_func=lambda x: "Select Label" if x == "" else x,
        key=f"npr_label_{key}",
    )

    sandbox_index = label_options.index(validation.get("sandbox_label", ""))
    sandbox_label = col2.radio(
        "Label",
        label_options,
        index=sandbox_index,
        format_func=lambda x: "Select Label" if x == "" else x,
        key=f"sandbox_label_{key}",
    )

    npr_acceptable_reason = ""
    if npr_label == "Acceptable":
        npr_acceptable_reason = col1.text_input(
            "Acceptable Reason",
            value=validation.get("npr_acceptable_reason", ""),
            key=f"npr_acceptable_{key}",
        )
    else:
        st.session_state.pop(f"npr_acceptable_{key}", None)

    sandbox_acceptable_reason = ""
    if sandbox_label == "Acceptable":
        sandbox_acceptable_reason = col2.text_input(
            "Acceptable Reason",
            value=validation.get("sandbox_acceptable_reason", ""),
            key=f"sandbox_acceptable_{key}",
        )
    else:
        st.session_state.pop(f"sandbox_acceptable_{key}", None)

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

    if npr_label and sandbox_label:
        st.session_state["validations"][key] = {
            "case_num": case_num,
            "attachment_name": attach_name,
            "prompt": prompt,
            "npr": npr_text,
            "sandbox": sandbox_text,
            "npr_label": npr_label,
            "npr_acceptable_reason": st.session_state.get(
                f"npr_acceptable_{key}", ""
            ),
            "sandbox_label": sandbox_label,
            "sandbox_acceptable_reason": st.session_state.get(
                f"sandbox_acceptable_{key}", ""
            ),
            "standard_response": standard_response,
            "remark": remark,
        }
    else:
        st.session_state["validations"].pop(key, None)

    # ``show_json_diff`` already visualizes differences if present, so the
    # textual diff output previously displayed here is no longer required.

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        comp_df.to_excel(writer, sheet_name="Comparison", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
    buffer.seek(0)

    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    st.download_button(
        label="Download Excel Report",
        data=buffer,
        file_name=f"{timestamp}_comparison_report.xlsx",
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
                "NPR Label": [v["npr_label"] for v in st.session_state["validations"].values()],
                "NPR Acceptable Reason": [
                    v["npr_acceptable_reason"] for v in st.session_state["validations"].values()
                ],
                "Sandbox Label": [
                    v["sandbox_label"] for v in st.session_state["validations"].values()
                ],
                "Sandbox Acceptable Reason": [
                    v["sandbox_acceptable_reason"]
                    for v in st.session_state["validations"].values()
                ],
                "Standard Response": [
                    v["standard_response"] for v in st.session_state["validations"].values()
                ],
                "Remark": [v["remark"] for v in st.session_state["validations"].values()],
            }
        )
        csv_data = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Save Validation Results",
            data=csv_data,
            file_name=f"{timestamp}_validation_results.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
