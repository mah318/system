import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI

# 缓存函数：只返回纯数据 DataFrame
@st.cache_data
def get_stock_data(ticker, period):
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)
    return df

st.set_page_config(page_title="Financial Terminal", layout="wide")
st.title("📈 AI Financial Terminal")

# 侧边栏配置
st.sidebar.header("配置")
api_key = st.sidebar.text_input("API Key:", type="password")

# [新功能] 使用 multiselect 支持多只股票
tickers_input = st.sidebar.multiselect(
    "选择股票:", 
    ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"], 
    default=["AAPL"]
)
period = st.sidebar.selectbox("时间范围:", ["1mo", "3mo", "6mo", "1y", "2y", "5y"])

if st.sidebar.button("Analyse"):
    if not api_key:
        st.error("请输入 API Key")
    elif not tickers_input:
        st.error("请至少选择一只股票")
    else:
        try:
            fig = go.Figure()
            
            # 遍历每一只选择的股票进行绘制
            for t in tickers_input:
                clean_ticker = t.strip().upper()
                df = get_stock_data(clean_ticker, period)
                
                if df.empty:
                    st.warning(f"无法获取代码 '{clean_ticker}' 的数据。")
                    continue
                
                # 绘制折线图用于对比
                fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', name=clean_ticker))

            # 更新图表布局
            fig.update_layout(
                template="plotly_dark", 
                title="股票表现对比",
                xaxis_title="日期",
                yaxis_title="收盘价 (USD)"
            )
            st.plotly_chart(fig, use_container_width=True)

            # AI 分析（只对列表中的第一只股票做深度分析，避免 Token 消耗过大）
            st.write("---")
            primary_ticker = tickers_input[0]
            st.subheader(f"深度 AI 分析: {primary_ticker}")
            
            df_primary = get_stock_data(primary_ticker, period)
            stock_primary = yf.Ticker(primary_ticker)
            info = stock_primary.info
            
            # 展示基本面
            with st.expander("📊 查看公司基本面信息"):
                st.write(f"**公司**: {info.get('longName', 'N/A')}")
                st.write(f"**行业**: {info.get('industry', 'N/A')}")
                st.write(f"**市值**: {info.get('marketCap', 0):,}")

            # 准备 AI 数据
            df_primary['Daily %'] = df_primary['Close'].pct_change() * 100
            df_primary['SMA_50'] = df_primary['Close'].rolling(window=50).mean()
            data_for_ai = df_primary[['Close', 'Daily %', 'SMA_50']].tail(10).to_string()
            
            client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "你是一位专业金融分析师。请分析给定数据，判断趋势并给出投资逻辑。"},
                    {"role": "user", "content": f"分析对象: {info.get('longName', 'N/A')}\n最近10天数据:\n{data_for_ai}"}
                ]
            )
            st.info(response.choices[0].message.content)

        except Exception as e:
            st.error(f"程序出错: {e}")
