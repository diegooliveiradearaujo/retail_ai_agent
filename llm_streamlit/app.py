import streamlit as st
import pandas as pd
import re
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# page streamlit
st.set_page_config(page_title="Retail AI Agent", layout="wide")

st.title("Retail AI Data Analyst Agent")
st.write("Ask questions about sales data.")

# load data
@st.cache_data
def load_data():
    df = pd.read_csv(
        r"C:\Users\diego.araujo\Desktop\projects\Retail\retail_ai_agent\resources\csv\sales_dataset_project.csv"
    )
    df["sale_date"] = pd.to_datetime(df["sale_date"], format="%d-%m-%Y")
    return df


# load model
@st.cache_resource
def load_model():
    model_name = "Qwen/Qwen2.5-3B-Instruct"

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float32,
        device_map="auto"
    )

    model.eval()

    return tokenizer, model


# init
df = load_data()
tokenizer, model = load_model()

# period extraction
def extract_period(question):
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", question)

    if len(dates) == 2:
        return pd.to_datetime(dates[0]), pd.to_datetime(dates[1])

    return None, None


# text generation
def generate_text(messages, max_tokens=150, temperature=0.0):

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False if temperature == 0 else True,
            temperature=temperature,
            pad_token_id=tokenizer.eos_token_id
        )

    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return generated

# llm - pandas query
def generate_pandas_query(question, columns, retry=False):

    correction_note = ""

    if retry:
        correction_note = "The previous answer was invalid. Follow the rules strictly."

    messages = [
        {"role": "system", "content": "You are a precise Python data analyst."},
        {"role": "user", "content": f"""
The dataframe is called df.

Columns available:
{columns}

IMPORTANT:
- ALWAYS select the column BEFORE applying sum(), mean(), std()
- NEVER use df.groupby(...).sum() without selecting a column

{correction_note}

TASK:
Generate exactly ONE valid pandas expression.

STRICT RULES:
- Output ONLY one line
- No explanation
- Must start with df
- No assignments

Question: {question}
"""}
    ]

    generated = generate_text(messages, max_tokens=120)

    code = generated.split("assistant")[-1].strip()
    code = code.split("\n")[0]
    code = code.replace("```", "").strip()

    return code


# validation
def validate_code(code):

    forbidden_keywords = [
        "import", "open(", "exec(", "eval(",
        "os.", "sys.", "__", "subprocess"
    ]

    if any(word in code for word in forbidden_keywords):
        return False

    if not code.strip().startswith("df"):
        return False

    return True


# execution
def safe_execute(code, df_filtered):

    try:
        result = eval(code, {"df": df_filtered})
        return result

    except Exception as e:
        return f"Execution error: {e}"


# explantion
def explain_result(question, result):

    messages = [
        {"role": "system", "content": "You are a business data analyst."},
        {"role": "user", "content": f"""
User question:
{question}

Query result:
{result}

Explain the result clearly in business terms.
"""}
    ]

    explanation = generate_text(messages, max_tokens=150, temperature=0.7)

    return explanation.split("assistant")[-1].strip()


# agent
def run_agent(question):

    start, end = extract_period(question)

    df_filtered = df.copy()

    if start is not None:
        df_filtered = df[
            (df["sale_date"] >= start) &
            (df["sale_date"] <= end)
        ]

    code = generate_pandas_query(question, list(df.columns))

    if not validate_code(code):
        code = generate_pandas_query(question, list(df.columns), retry=True)

    if not validate_code(code):
        return None, None, "Unsafe query generated."

    result = safe_execute(code, df_filtered)

    explanation = explain_result(question, result)

    return code, result, explanation


# interface
question = st.text_input("Ask your question about sales data:")

if st.button("Run Agent"):

    if question.strip() == "":
        st.warning("Please type a question.")

    else:
        with st.spinner("Thinking..."):
            code, result, explanation = run_agent(question)

        st.subheader("Generated Query")
        st.code(code)

        st.subheader("Result")
        st.write(result)

        st.subheader("Explanation")
        st.write(explanation)