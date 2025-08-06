import streamlit as st
import pandas as pd

st.set_page_config(page_title="GPT Result Checker", layout="wide")

if 'df' not in st.session_state:
    st.session_state.df = None

st.title("GPT Result Checker")

uploaded_file = st.file_uploader("Upload CSV", type="csv")
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    if 'Validation Status' not in df.columns:
        df['Validation Status'] = ''
    if 'Comments' not in df.columns:
        df['Comments'] = ''
    st.session_state.df = df

if st.session_state.df is not None:
    df = st.session_state.df
    st.sidebar.header("Filters")
    env_filter = st.sidebar.multiselect(
        "Environment", options=sorted(df['environment'].dropna().unique())
    )

    prompt_filter = []
    if 'Prompt Name' in df.columns:
        prompt_filter = st.sidebar.multiselect(
            "Prompt Name", options=sorted(df['Prompt Name'].dropna().unique())
        )

    model_filter = []
    if 'Model' in df.columns:
        model_filter = st.sidebar.multiselect(
            "Model", options=sorted(df['Model'].dropna().unique())
        )

    file_filter = []
    file_col = None
    if 'FileName' in df.columns:
        file_col = 'FileName'
        file_filter = st.sidebar.multiselect(
            "FileName", options=sorted(df[file_col].dropna().unique())
        )
    elif 'attachment_name' in df.columns:
        file_col = 'attachment_name'
        file_filter = st.sidebar.multiselect(
            "Attachment Name", options=sorted(df[file_col].dropna().unique())
        )

    search_case = st.sidebar.text_input("Search casenumber")

    filtered_df = df.copy()
    if env_filter:
        filtered_df = filtered_df[filtered_df['environment'].isin(env_filter)]
    if prompt_filter and 'Prompt Name' in df.columns:
        filtered_df = filtered_df[filtered_df['Prompt Name'].isin(prompt_filter)]
    if model_filter and 'Model' in df.columns:
        filtered_df = filtered_df[filtered_df['Model'].isin(model_filter)]
    if file_filter and file_col:
        filtered_df = filtered_df[filtered_df[file_col].isin(file_filter)]
    if search_case:
        filtered_df = filtered_df[
            filtered_df['casenumber'].astype(str).str.contains(search_case)
        ]

    st.sidebar.header("Batch Actions")
    selected_cases = st.sidebar.multiselect(
        "Select casenumbers", filtered_df['casenumber'].astype(str)
    )
    batch_status = st.sidebar.selectbox(
        "Status", ['', 'Valid', 'Invalid', 'Needs Review']
    )
    batch_comment = st.sidebar.text_input("Comment for batch")
    if st.sidebar.button("Apply") and selected_cases:
        mask = df['casenumber'].astype(str).isin(selected_cases)
        if batch_status:
            df.loc[mask, 'Validation Status'] = batch_status
        if batch_comment:
            df.loc[mask, 'Comments'] = batch_comment
        st.session_state.df = df

    st.subheader("Records")
    result_col = next((col for col in ['Response', 'Result'] if col in df.columns), None)
    column_config = {
        "Validation Status": st.column_config.SelectboxColumn(
            "Validation Status",
            options=['', 'Valid', 'Invalid', 'Needs Review'],
        ),
    }
    if result_col:
        column_config[result_col] = st.column_config.TextColumn(width="large")

    edited_df = st.data_editor(
        filtered_df,
        num_rows="dynamic",
        column_config=column_config,
        hide_index=True,
        key="data_editor",
    )

    # update original df with edits
    for idx in edited_df.index:
        st.session_state.df.loc[idx, 'Validation Status'] = edited_df.loc[idx, 'Validation Status']
        st.session_state.df.loc[idx, 'Comments'] = edited_df.loc[idx, 'Comments']

    st.subheader("View Result")
    if not edited_df.empty:
        case_view = st.selectbox(
            "Select casenumber", edited_df['casenumber'].astype(str)
        )
        record = edited_df[
            edited_df['casenumber'].astype(str) == case_view
        ].iloc[0]
        if result_col and result_col in record:
            st.write(record.drop(result_col))
            with st.expander(result_col):
                st.write(record[result_col])
        else:
            st.write(record)

    st.subheader("Statistics")
    st.write(
        edited_df['environment'].value_counts().rename("count")
    )
    st.write(
        edited_df['Validation Status'].value_counts().rename("status")
    )

    def convert_df(df):
        return df.to_csv(index=False).encode('utf-8')

    st.download_button(
        "Download annotated CSV",
        convert_df(st.session_state.df),
        "validated_results.csv",
        "text/csv",
    )
else:
    st.info("Upload a CSV file to begin.")
