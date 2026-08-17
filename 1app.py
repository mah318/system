import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI
import pandas as pd

@st.cache_data
def get_stock_data(ticker, period):
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)
    return df

st.set_page_config(page_title="Financial Terminal", layout="wide")
st.title("📈 AI Financial Terminal")

# 侧边栏配置（默认时间已设为 10D 两个星期）
st.sidebar.header("配置")
api_key = st.sidebar.text_input("API Key:", type="password")
tickers_raw = st.sidebar.text_input("Enter Stock:", "NVDA")
period = st.sidebar.selectbox("Time:", ["1D", "10D", "1mo", "3mo", "6mo", "1y", "10y", "20y"], index=1)
normalize = st.sidebar.checkbox("开启归一化对比 (从0%起步)", value=True)

if st.sidebar.button("Analyse"):
    tickers_input = [t.strip().upper() for t in tickers_raw.split(',') if t.strip()]
    
    if not tickers_input:
        st.error("请输入股票代码")
    else:
        try:
            # 1. 绘图与对比
            fig = go.Figure()
            for t in tickers_input:
                df = get_stock_data(t, period)
                if df.empty: continue
                y_data = (df['Close'] / df['Close'].iloc[0] - 1) * 100 if normalize else df['Close']
                fig.add_trace(go.Scatter(x=df.index, y=y_data, mode='lines', name=t))

            fig.update_layout(template="plotly_dark", title="收益率对比" if normalize else "价格对比")
            st.plotly_chart(fig, use_container_width=True)

            # 准备主分析对象的数据
            primary_ticker = tickers_input[0]
            df_primary = get_stock_data(primary_ticker, period)
            if df_primary.empty:
                st.error(f"未获取到 {primary_ticker} 的行情数据。")
                st.stop()
                
            stock_primary = yf.Ticker(primary_ticker)
            
            # 获取基本面核心指标
            info = stock_primary.info
            raw_market_cap = info.get('marketCap', 'N/A')
            raw_pe = info.get('trailingPE', 'N/A')
            raw_pb = info.get('priceToBook', 'N/A')
            raw_margin = info.get('profitMargins', 'N/A')
            raw_growth = info.get('revenueGrowth', 'N/A')
            
            market_cap_str = f"{raw_market_cap:,}" if isinstance(raw_market_cap, (int, float)) else str(raw_market_cap)
            pe_str = f"{raw_pe:.2f}" if isinstance(raw_pe, (int, float)) else str(raw_pe)
            pb_str = f"{raw_pb:.2f}" if isinstance(raw_pb, (int, float)) else str(raw_pb)
            margin_str = f"{raw_margin * 100:.2f}%" if isinstance(raw_margin, (int, float)) else "N/A"
            growth_str = f"{raw_growth * 100:.2f}%" if isinstance(raw_growth, (int, float)) else "N/A"
            
            # 计算技术指标
            delta = df_primary['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df_primary['RSI'] = 100 - (100 / (1 + rs))
            ema12 = df_primary['Close'].ewm(span=12, adjust=False).mean()
            ema26 = df_primary['Close'].ewm(span=26, adjust=False).mean()
            df_primary['MACD'] = ema12 - ema26
            df_primary['Signal'] = df_primary['MACD'].ewm(span=9, adjust=False).mean()

            latest = df_primary.iloc[-1]

            # --- AI 智能信号看板 (强化倾向性，禁止模棱两可) ---
            st.subheader(f"🤖 AI 智能决策看板: {primary_ticker}")
            if not api_key:
                st.warning("未输入 API Key，已跳过 AI 智能分析。")
            else:
                try:
                    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                    
                    models_response = client.models.list()
                    available_models = [m.id for m in models_response.data]
                    
                    auto_model = available_models[0] if available_models else "openai/gpt-oss-120b"
                    for m in available_models:
                        if any(k in m.lower() for k in ['chat', 'versatile', 'instant', '8b', '70b', 'gpt-oss', 'instruct']):
                            auto_model = m
                            break

                    tech_summary = f"Ticker: {primary_ticker}, RSI: {latest['RSI']:.2f}, MACD: {latest['MACD']:.2f}"
                    signal_prompt = f"""请根据以下近两周数据对 {primary_ticker} 进行果断、犀利的分析：
- 技术面: {tech_summary}
- 基本面: PE={pe_str}, PB={pb_str}, 利润率={margin_str}, 营收增长={growth_str}

要求：必须表现出鲜明的观点，**严禁无脑观望或模棱两可**，根据多空指标强制倾向于“买入”或“卖出”其中之一。
严格按以下格式输出：
【操作评级】买入 / 卖出 (二选一，必须明确)
【核心理由】(40字以内，直击要害)
【关键支撑与风险】(各一句话)
"""
                    signal_response = client.chat.completions.create(
                        model=auto_model,
                        messages=[{"role": "user", "content": signal_prompt}]
                    )
                    ai_signal_text = signal_response.choices[0].message.content
                    st.session_state['analysis_result'] = ai_signal_text
                    
                    st.markdown(f"""
                    <div style="background-color: #1a1a1a; padding: 18px; border-radius: 10px; border: 1px solid #333333; color: #f0f0f0; font-size: 15px; line-height: 1.7; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                        {ai_signal_text.replace('\n', '<br>')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                except Exception as ai_err:
                    st.error(f"AI 智能决策请求失败: {ai_err}")

            # 2. Tabs 分页
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏢 基本面分析", "📊 技术指标", "📰 情绪分析", "📝 生成报告", "📋 数据预览"])

            with tab1:
                st.subheader(f"基本盘分析: {primary_ticker}")
                col1, col2, col3 = st.columns(3)
                col1.metric("市值 (Market Cap)", market_cap_str)
                col2.metric("市盈率 (P/E)", pe_str)
                col3.metric("市净率 (P/B)", pb_str)
                
                col4, col5 = st.columns(2)
                col4.metric("利润率 (Profit Margin)", margin_str)
                col5.metric("营收增长率 (Revenue Growth)", growth_str)
                
                st.markdown("---")
                st.write("**🤖 AI 基本盘深度评估:**")
                if api_key:
                    try:
                        fund_prompt = f"请对 {primary_ticker} 进行简要基本面评估（PE: {pe_str}, PB: {pb_str}, 利润率: {margin_str}），分点列出5项核心指标评价。"
                        fund_response = client.chat.completions.create(
                            model=auto_model,
                            messages=[{"role": "user", "content": fund_prompt}]
                        )
                        st.write(fund_response.choices[0].message.content)
                    except:
                        st.write("基本面 AI 评估加载失败。")
                else:
                    st.info("请输入 API Key 以查看 AI 深度评估。")

            with tab2:
                st.subheader(f"技术指标 (近两周): {primary_ticker}")
                st.line_chart(df_primary[['RSI']])
                st.line_chart(df_primary[['MACD', 'Signal']])

            with tab3:
                st.subheader("新闻情绪分析")
                try:
                    news = stock_primary.news
                    if news and isinstance(news, list):
                        headlines = [n.get('title', '无标题新闻') for n in news[:5]]
                        for h in headlines: st.write(f"- {h}")
                    else:
                        st.write("暂无相关新闻。")
                except:
                    st.write("获取新闻接口异常。")

            with tab4:
                st.subheader("一键导出报告")
                if 'analysis_result' in st.session_state:
                    st.download_button("下载分析报告", data=st.session_state['analysis_result'], file_name=f"{primary_ticker}_analysis.txt")
                else:
                    st.write("当前暂无可导出的 AI 分析结果。")
            
            with tab5:
                st.subheader(f"{primary_ticker} 原始数据预览")
                st.dataframe(df_primary.tail(10))

        except Exception as e:
            st.error(f"程序运行出错: {e}")
