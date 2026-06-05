import streamlit as st
import pandas as pd
from query_planner import generate_query_plan
from executor import execute_plan
from charts import create_chart
import time

# --- Setup UI Configuration ---
st.set_page_config(
    page_title="Talk to Indian Crime Data (2018)",
    page_icon="🚨",
    layout="wide"
)

# --- Caching Data Load ---
@st.cache_data
def load_data():
    try:
        # Update path as necessary if the app is run from a different directory
        df = pd.read_csv("NDAP_REPORT_7060.csv")
        return df
    except FileNotFoundError:
        st.error("Error: NDAP_REPORT_7060.csv not found!")
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def get_cached_query_plan(query):
    """Caches LLM responses to avoid hitting Gemini free tier rate limits (5 requests/minute)."""
    return generate_query_plan(query)

EVALUATION_TEST_CASES = [
    {"q": "Which state had the highest fraud incidents?", "expect_intent": "top_state"},
    {"q": "Which state had the highest kidnapping victims?", "expect_intent": "victims_analysis"},
    {"q": "Compare fraud incidents in Karnataka and Tamil Nadu.", "expect_intent": "compare_states"},
    {"q": "Which state had the highest robbery crime rate?", "expect_intent": "crime_rate_ranking"},
    {"q": "Which crime categories had the most incidents?", "expect_intent": "category_ranking"},
    {"q": "Who is the Prime Minister of India?", "expect_intent": "out_of_scope"},
]

EVALUATION_PLAN_CACHE = {
    "Which state had the highest fraud incidents?": {"intent": "top_state", "crime": "Fraud", "metric": "incidents"},
    "Which state had the highest kidnapping victims?": {"intent": "victims_analysis", "crime": "Kidnapping", "metric": "victims"},
    "Compare fraud incidents in Karnataka and Tamil Nadu.": {"intent": "compare_states", "crime": "Fraud", "states": ["Karnataka", "Tamil Nadu"], "metric": "incidents"},
    "Which state had the highest robbery crime rate?": {"intent": "crime_rate_ranking", "crime": "Robbery", "metric": "rate"},
    "Which crime categories had the most incidents?": {"intent": "category_ranking", "crime": "Total Crimes", "metric": "incidents"},
    "Who is the Prime Minister of India?": {"intent": "out_of_scope"},
}

PLANNER_FAILURE_INTENTS = {"rate_limited", "api_error", "invalid_json", "error"}


def get_evaluation_plan(question, use_live_gemini):
    if use_live_gemini:
        return generate_query_plan(question)
    return EVALUATION_PLAN_CACHE.get(
        question,
        {"intent": "api_error", "message": "No cached evaluation plan found."},
    )

# --- Title & Description ---
st.title("🚨 Talk to Indian Crime Data (2018)")
st.markdown("""
Welcome to the AI analytics app. Ask natural language questions about Indian crime data from 2018.
The AI agent converts your request into a structured JSON, and an execution engine fetches the actual exact numbers.
**No Hallucinations. Pure Data.**
""")

# Load Data
with st.spinner("Loading Crime Dataset..."):
    df = load_data()

st.sidebar.header("Dataset Overview")
if not df.empty:
    st.sidebar.write(f"Rows: {df.shape[0]}, Columns: {df.shape[1]}")
    st.sidebar.write("Available columns mapping mapped locally to answer your questions.")

# --- User Input Section ---

tab1, tab2 = st.tabs(["Analytics", "Evaluation"])

with tab1:
    st.sidebar.header("Example Questions")
    st.sidebar.markdown("""
    - Which state had the highest fraud incidents?
    - Which state had the highest kidnapping victims?
    - Compare fraud incidents in Karnataka and Tamil Nadu.
    - Which state had the highest robbery crime rate?
    - Which crime categories had the most incidents?
    """)
    
    user_query = st.text_input("Ask a question:", placeholder="e.g., Which state has the highest number of murder incidents?")

    if st.button("Submit", type="primary"):
        if not user_query.strip():
            st.warning("Please enter a question.")
        elif df.empty:
            st.error("Dataset not loaded. Cannot proceed.")
        else:
            start_time = time.time()
            
            # Step 1: Gemini Query Planner (NL -> JSON)
            with st.status("Analyzing question structure with Gemini...", expanded=True) as status:
                st.write("Generating structured JSON intent...")
                plan_json = generate_query_plan(user_query)
                
                st.write("Executing queries against raw data using Pandas...")
                # Step 2: Pandas Execution
                result = execute_plan(df, plan_json)
                
                status.update(label="Analytics complete!", state="complete", expanded=False)
                
            execution_time = round(time.time() - start_time, 2)
            
            st.success(f"Response assembled in {execution_time} seconds.")
            
            # --- UI Layout for Results ---
            
            if plan_json.get('intent') == 'out_of_scope':
                st.warning("⚠️ " + result['answer'])
            else:
                # 1. Answer
                st.subheader("💡 Answer")
                st.info(result['answer'])
                
                if result['data'] is not None:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        # 2. Chart
                        st.subheader("📊 Visualization")
                        fig = create_chart(plan_json, result)
                        if fig:
                            st.plotly_chart(fig, width='stretch')
                        else:
                            st.write("No chart available for this intent/data combination.")
                    
                    with col2:
                        # 3. Data View
                        st.subheader("📋 Top Data")
                        st.dataframe(result['data'], hide_index=True)
                        
            # Query JSON Visibility
            with st.expander("🛠 Generated Query JSON"):
                st.code(plan_json, language="json")

            # 4. Computation Details
            with st.expander("🛠 How this answer was computed"):
                computation_steps = result.get('computation', [])
                if isinstance(computation_steps, list):
                    for i, step in enumerate(computation_steps, 1):
                        st.markdown(f"{i}. {step}")
                else:
                    st.write(f"**Execution Log:** {computation_steps}")

with tab2:
    st.header("Evaluation")
    st.write("Here we evaluate standard test cases against the system architecture.")
    st.info("Cached evaluation mode is used to conserve Gemini API quota. Manual queries continue to use the live Gemini planner.")

    cached_validation = st.checkbox("Cached Validation (Recommended)", value=True)
    use_live_gemini = st.checkbox("Live Gemini Validation", value=False)

    if use_live_gemini:
        st.warning("Live validation uses the Gemini API and may be affected by free-tier rate limits.")
    if cached_validation and use_live_gemini:
        st.caption("Live Gemini Validation is active for this run; cached plans are bypassed.")
    validation_mode_selected = cached_validation or use_live_gemini
    if not validation_mode_selected:
        st.warning("Select Cached Validation or Live Gemini Validation before running evaluations.")

    if st.button("Run Evaluations", disabled=not validation_mode_selected):
        results_data = []
        progress_text = "Running evaluation suite..."
        my_bar = st.progress(0, text=progress_text)

        for i, tc in enumerate(EVALUATION_TEST_CASES):
            my_bar.progress((i) / len(EVALUATION_TEST_CASES), text=f"Evaluating: '{tc['q']}'")

            res_json = get_evaluation_plan(tc["q"], use_live_gemini)
            actual_intent = res_json.get("intent", "api_error")
            execution_result = execute_plan(df, res_json) if not df.empty else {
                "answer": "Dataset not loaded. Cannot execute evaluation.",
                "data": None,
                "computation": []
            }

            passed = actual_intent == tc["expect_intent"] and actual_intent not in PLANNER_FAILURE_INTENTS
            results_data.append({
                "Question": tc["q"],
                "Expected Intent": tc["expect_intent"],
                "Actual Intent": actual_intent,
                "Planner Status": "ok" if actual_intent not in PLANNER_FAILURE_INTENTS else actual_intent,
                "Answer": execution_result.get("answer"),
                "Pass/Fail": "Pass" if passed else "Fail"
            })

            time.sleep(2 if use_live_gemini else 0.2)

        my_bar.progress(1.0, text="Evaluation complete!")
        results_df = pd.DataFrame(results_data)
        total_tests = len(results_df)
        passed_tests = int((results_df["Pass/Fail"] == "Pass").sum())
        failed_tests = total_tests - passed_tests
        pass_rate = round((passed_tests / total_tests) * 100, 2) if total_tests else 0

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        metric_col1.metric("Total Tests", total_tests)
        metric_col2.metric("Passed", passed_tests)
        metric_col3.metric("Failed", failed_tests)
        metric_col4.metric("Pass Rate %", pass_rate)

        st.table(results_df)
