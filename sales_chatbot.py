import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Sales Intelligence AI", page_icon="📊", layout="wide")

st.markdown("""
<style>

.stApp {
    background: #F8F7FC;
    color: #292638;
}

.stApp p,
.stApp label,
.stApp span,
.stApp li,
.stMarkdown,
[data-testid="stText"],
[data-testid="stCaptionContainer"] {
    color: #292638;
}

.stApp h1, .stApp h2, .stApp h3 {
    color: #454276;
}

[data-testid="stSidebar"] {
    background: #EFEDFA;
}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {
    color: #292638;
}

.stTextInput input {
    color: #292638 !important;
    background: #FFFFFF !important;
}

.stButton > button {
    background: #7775C8;
    color: #FFFFFF !important;
    border-radius: 10px;
}

div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E7E3F5;
    padding: 16px;
    border-radius: 14px;
}

div[data-testid="stMetric"] label,
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #292638 !important;
}

</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    files = [
        "sales_dataset.csv",
        "sales_October_data.csv"
    ]

    dataframes = []

    for file in files:
        try:
            current_df = pd.read_csv(file)
            current_df.columns = [
                str(c).strip() for c in current_df.columns
            ]
            dataframes.append(current_df)
        except FileNotFoundError:
            if file == "sales_dataset.csv":
                raise

    if not dataframes:
        return pd.DataFrame()

    df = pd.concat(dataframes, ignore_index=True)

    # Remove duplicate orders if the same records exist in both files
    if "Order_ID" in df.columns:
        df = df.drop_duplicates(
            subset=["Order_ID"],
            keep="first"
        )

    if "Order_Date" in df.columns:
        df["Order_Date"] = pd.to_datetime(
            df["Order_Date"], errors="coerce"
        )

    for c in [
        "Sales", "Cost", "Profit",
        "Quantity", "Discount", "Unit_Price"
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False),
                errors="coerce"
            )

    return df


def answer_question(question, df):
    q = re.sub(r"[^a-z0-9\s]", " ", question.lower())
    q = re.sub(r"\s+", " ", q).strip()
    aliases = {
        "customer segment":"Customer_Segment", "segment":"Customer_Segment",
        "sales channel":"Sales_Channel", "channel":"Sales_Channel",
        "cities":"City", "city":"City", "regions":"Region", "region":"Region",
        "categories":"Category", "category":"Category", "products":"Product", "product":"Product"
    }
    dimension = next((col for word,col in aliases.items() if re.search(r"\b"+re.escape(word)+r"\b",q)), None)

    if any(x in q for x in ["show data","all data","view records","display data","show records"]):
        return "Sales records", df
    if "how many cities" in q or "number of cities" in q:
        return f"Unique cities: {df['City'].nunique():,}"
    if "how many products" in q or "number of products" in q:
        return f"Unique products: {df['Product'].nunique():,}"

    order_count = any(x in q for x in ["order count","number of orders","total orders","how many orders","count orders"])
    if order_count:
        metric = "Order_ID"
    elif "profit margin" in q or "margin percentage" in q:
        sales = df["Sales"].sum()
        return f"Overall profit margin: {df['Profit'].sum()/sales*100:.2f}%" if sales else "Sales value is zero."
    elif any(x in q for x in ["profit","profitable","earnings"]):
        metric = "Profit"
    elif any(x in q for x in ["cost","costs","expense","expenses"]):
        metric = "Cost"
    elif any(x in q for x in ["quantity","units sold","items sold"]):
        metric = "Quantity"
    elif "discount" in q:
        metric = "Discount"
    elif "unit price" in q or "price" in q:
        metric = "Unit_Price"
    else:
        metric = "Sales"

    if metric not in df.columns:
        return f"Dataset-la {metric} column kidaikkala."
    avg = any(x in q for x in ["average","avg","mean"])
    low = any(x in q for x in ["lowest","least","minimum","smallest","worst"])
    top = any(x in q for x in ["highest","top","best","most","maximum","largest","greatest"])
    monthly = any(x in q for x in ["monthly","month by month","per month","month"])

    if monthly:
        temp = df.dropna(subset=["Order_Date"]).copy()
        if temp.empty:
            return "Valid order dates available illa."
        temp["Month"] = temp["Order_Date"].dt.to_period("M").astype(str)
        if order_count:
            result = temp.groupby("Month")["Order_ID"].nunique().reset_index(name="Orders")
        else:
            grouped = temp.groupby("Month")[metric]
            result = (grouped.mean() if avg else grouped.sum()).reset_index(name=("Average " if avg else "Total ")+metric)
        return "Monthly analysis", result

    if dimension:
        grouped = df.groupby(dimension, dropna=True)["Order_ID"].nunique() if order_count else (
            df.groupby(dimension)[metric].mean() if avg else df.groupby(dimension)[metric].sum())
        name = "Orders" if order_count else ("Average " if avg else "Total ")+metric
        grouped = grouped.dropna()
        if top or low:
            grouped = grouped.sort_values(ascending=low)
            match = re.search(r"\btop\s+(\d+)\b", q)
            n = min(int(match.group(1)),20) if match else 1
            return f"{name} by {dimension}", grouped.head(n).rename(name).reset_index()
        if any(x in q for x in ["compare","breakdown"," by ","each","per ","distribution"]):
            return f"{name} by {dimension}", grouped.sort_values(ascending=False).rename(name).reset_index()

    if order_count:
        return f"Total unique orders: {df['Order_ID'].nunique():,}"
    if avg:
        if "order" in q:
            return f"Average sales per order: {df.groupby('Order_ID')['Sales'].sum().mean():,.2f}"
        return f"Average {metric.replace('_',' ')}: {df[metric].mean():,.2f}"
    if any(x in q for x in ["total","overall","sum","how much","sales","revenue","profit","cost","expenses","quantity"]):
        return f"Total {metric.replace('_',' ')}: {df[metric].sum():,.2f}"
    return "Try: Total sales, Highest profit by city, Monthly sales, Top 5 products by profit, Compare sales by category, Average sales by region."

st.markdown("""
<div style="background:linear-gradient(120deg,#7775C8,#A5A2E8);padding:26px;border-radius:18px;margin-bottom:22px">
<h1 style="color:white">📊 Sales Intelligence Assistant</h1>
<p style="color:white">Ask questions and explore your business data.</p>
</div>
""", unsafe_allow_html=True)

try:
    df = load_data()
    if df.empty:
        st.warning("Sales dataset-la records illa.")
        st.stop()
    st.sidebar.title("💜 Sales Assistant")
    st.sidebar.caption("Sales data explorer")
    st.sidebar.write(f"Records loaded: {len(df):,}")
    st.sidebar.write(f"Unique orders: {df['Order_ID'].nunique():,}")
    c1,c2,c3 = st.columns(3)
    c1.metric("💰 Total Sales", f"{df['Sales'].sum():,.2f}")
    c2.metric("📈 Total Profit", f"{df['Profit'].sum():,.2f}")
    c3.metric("🧾 Total Orders", f"{df['Order_ID'].nunique():,}")
    st.subheader("💬 Ask your sales assistant")
    examples = ["Total sales","Highest profit by city","Monthly sales","Top 5 products by profit","Compare sales by category","Average sales"]
    cols = st.columns(3)
    for i,example in enumerate(examples):
        if cols[i%3].button(example,key=f"example_{i}",use_container_width=True):
            st.session_state["question_input"] = example
    question = st.text_input("Your question",placeholder="Example: Which region has the highest profit?",key="question_input")
    if question:
        answer = answer_question(question,df)
        if isinstance(answer,tuple):
            title,result_df = answer
            st.success(title)
            st.dataframe(result_df,use_container_width=True,hide_index=True)
            numeric_cols = result_df.select_dtypes(include="number").columns
            if len(numeric_cols)==1 and len(result_df)>1:
                st.bar_chart(result_df.set_index(result_df.columns[0])[numeric_cols[0]])
        else:
            st.info(answer)
    with st.expander("View dataset"):
        st.dataframe(df,use_container_width=True,hide_index=True)
except FileNotFoundError:
    st.error("sales_dataset.csv file repository-la irukkanum. GitHub-la upload pannunga.")
except Exception as e:
    st.error("App error. Please check the dataset columns.")
    st.code(str(e))
