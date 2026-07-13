import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI

# [修复] 缓存函数：只返回纯数据 DataFrame
@st.cache_data
def get_stock_data(ticker, period):
    # 在这里创建临时 ticker 对象获取数据
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)
    return df

st.set_page_config(page_title="Financial Terminal", layout="wide")
st.title("📈 AI Financial Terminal")

# 侧边栏配置
st.sidebar.header("配置")
api_key = st.sidebar.text_input("API Key:", type="password")
ticker = st.sidebar.text_input("Enter Stock:", "AAPL")
period = st.sidebar.selectbox("Time:", ["1D", "10D", "1mo", "3mo", "6mo", "1y", "10y", "20y"])

if st.sidebar.button("Analyse"):
    if not api_key:
        st.error("请输入 API Key")
    elif not ticker:
        st.error("请输入股票代码")
    else:
        try:
            # 清理输入
            clean_ticker = ticker.strip().upper()

            # [修复] 获取数据：只接收 df，不解包
            df = get_stock_data(clean_ticker, period)
            
            # 在主逻辑中单独创建 ticker 对象以获取 info (不缓存它)
            stock = yf.Ticker(clean_ticker)

            if df.empty:
                st.error(f"找不到代码 '{clean_ticker}'。")
            else:
                # 展示公司基本面信息
                info = stock.info
                with st.expander("📊 查看公司基本面信息"):
                    col1, col2 = st.columns(2)
                    col1.write(f"**公司全称**: {info.get('longName', 'N/A')}")
                    col1.write(f"**所属行业**: {info.get('industry', 'N/A')}")
                    col2.write(f"**当前市值**: {info.get('marketCap', 0):,}")
                    col2.write(f"**市盈率 (PE)**: {info.get('trailingPE', 'N/A')}")
                    st.write(f"**公司简介**: {info.get('longBusinessSummary', '无详细介绍')}")

                # 计算数据
                df['Daily %'] = df['Close'].pct_change() * 100
                df['SMA_50'] = df['Close'].rolling(window=50).mean()
                
                st.write(f"### {clean_ticker} Preview")
                st.dataframe(df.tail().style.format({'Daily %': '{:.2f}%'}))

                # 画图
                fig = go.Figure(data=[go.Candlestick(x=df.index,
                                open=df['Open'], high=df['High'],
                                low=df['Low'], close=df['Close'])])
                
                fig.add_trace(go.Scatter(
                    x=df.index, y=df['SMA_50'], name='50 SMA', 
                    line=dict(color='yellow', width=1.5)
                ))
                
                fig.update_layout(template="plotly_dark", title=f"{clean_ticker} Performance")
                st.plotly_chart(fig, use_container_width=True)
                
                # AI 分析
                client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                data_for_ai = df[['Close', 'Daily %', 'SMA_50']].tail(10).to_string()
                info = stock.info
                company_context = f"""
                公司名称: {info.get('longName', 'N/A')}
                行业: {info.get('industry', 'N/A')}
                市值: {info.get('marketCap', 0)}
                """

# 3. 优化系统提示词 (Prompt Engineering)
system_prompt = f"""
你是一位顶尖的量化金融分析师。
请结合以下公司背景和最近10天的价格趋势（含50日均线数据）进行分析。
如果股价在SMA_50之上，说明处于长期上升趋势；反之则需警惕。
请给出趋势判断、关键支撑位及你的投资逻辑。
"""

# 4. 发送请求
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"分析对象:\n{company_context}\n\n最近10天数据:\n{data_for_ai}"}
    ]
)
st.info(response.choices[0].message.content)
        except Exception as e:
            st.error(f"程序出错: {e}")
