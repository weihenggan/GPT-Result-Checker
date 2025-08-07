# GPT-Result-Checker

This repository contains tools for comparing GPT extraction results between two environments.

## Components

- **compare_prompt_results.py** – CLI tool that reads a CSV containing results for multiple prompts and compares the outputs between the "NPR" and "Sandbox" environments. It writes an Excel report summarising the differences.
- **streamlit_app.py** – Streamlit web application for interactively exploring comparison results.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Command line

```
python compare_prompt_results.py input.csv output.xlsx
```

### Streamlit app

```
streamlit run streamlit_app.py
```

Upload a CSV file with results to generate an interactive comparison and download an Excel report. Each NPR and Sandbox output can be individually labelled as *Correct*, *Acceptable*, or *Wrong*, and exported reports are saved with a timestamped filename.

## License

This project is released under the MIT License.
