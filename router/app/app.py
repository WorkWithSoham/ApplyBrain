import streamlit as st
import pandas as pd
import psycopg2
import os
import httpx
import plotly.express as px

st.set_page_config(page_title="AI Router Control Plane", layout="wide")

DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://ai_router:changeme_local@postgres:5432/ai_router"
)
ROUTER_URL = "http://router:8081/route"


def get_db_connection():
    return psycopg2.connect(DB_URL)


st.title("🚀 AI Smart Router — Unified Dashboard")

tabs = st.tabs(
    [
        "📊 Analytics & Weights",
        "📜 Request Logs",
        "🧪 Router Test",
        "🗄️ Database Browser",
    ]
)

with tabs[0]:
    st.header("Current Routing Weights")
    conn = get_db_connection()
    df_weights = pd.read_sql(
        "SELECT task_type, model_name, weight, updated_at FROM routing_weights ORDER BY task_type, weight DESC",
        conn,
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        fig = px.bar(
            df_weights,
            x="model_name",
            y="weight",
            color="task_type",
            barmode="group",
            title="Model Weights by Task",
        )
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.dataframe(df_weights, use_container_width=True)

with tabs[1]:
    st.header("Application Request Logs")
    limit = st.slider("Show last N requests", 10, 500, 50)
    query = f"""
        SELECT created_at, task_type, model_used, latency_ms, prompt, response_text 
        FROM request_log 
        ORDER BY created_at DESC LIMIT {limit}
    """
    df_logs = pd.read_sql(query, conn)
    st.dataframe(df_logs, use_container_width=True)

with tabs[2]:
    st.header("Live Router Test")
    with st.form("test_router"):
        prompt = st.text_area(
            "Enter Prompt:", "How do I implement a binary search in Python?"
        )
        task = st.selectbox("Task Type:", ["auto", "simple", "code", "reasoning"])
        submitted = st.form_submit_button("Send to Router")

        if submitted:
            with st.spinner("Routing..."):
                try:
                    resp = httpx.post(
                        ROUTER_URL,
                        json={"prompt": prompt, "task_type": task},
                        timeout=300,
                    )
                    data = resp.json()

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Model Used", data["model_used"])
                    c2.metric("Task Type", data["task_type"])
                    c3.metric("Latency", f"{data['latency_ms']}ms")

                    st.subheader("Response:")
                    st.write(data["response_text"])
                    if data.get("cache_hit"):
                        st.success("⚡ Cache Hit!")
                except Exception as e:
                    st.error(f"Error calling router: {e}")

with tabs[3]:
    st.header("Direct Database Browser")
    table = st.selectbox(
        "Select Table:", ["request_log", "routing_weights", "response_scores"]
    )
    df_table = pd.read_sql(f"SELECT * FROM {table} LIMIT 100", conn)
    st.dataframe(df_table, use_container_width=True)

# Connection is managed by st.cache_resource
