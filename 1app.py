import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI
import pandas as pd
import requests

# ==================== 在这里直接内置你的 API Key ====================
BUILTIN_API_KEY = "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" 
# ==================================================================

# 智能公司名称/代码转换函数（支持中文名搜索）
def get_ticker_from_name(query):
    query = query.strip()
    if not query:
        return ""
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        if 'quotes' in data and len(data['quotes']) > 0:
            return data['quotes'][0]['symbol']
    except Exception:
        pass
    return query.upper()

@st.cache_data
def get_stock_data(ticker, period):
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)
    return df

st.set_page_config(page_title="Financial Terminal", layout="wide")
st.title("📈 AI Financial Terminal (机构专业版)")

# 侧边栏配置
st.sidebar.header("配置")
tickers_raw = st.sidebar.text_input("Name:", "Apple")
period = st.sidebar.selectbox("Time:", ["1D", "10D", "1mo", "3mo", "6mo", "1y", "10y", "20y"], index=2)
normalize = st.sidebar.checkbox("开启归一化对比 (从0%起步)", value=True)

# 优先从 secrets 读取，若无则使用上方定义的 BUILTIN_API_KEY
try:
    api_key = st.secrets["GROQ_API_KEY"]
except:
    api_key = BUILTIN_API_KEY

if st.sidebar.button("Analyse"):
    raw_inputs = [t.strip() for t in tickers_raw.split(',') if t.strip()]
    
    if not raw_inputs:
        st.error("请输入公司名称或股票代码")
    else:
        # 将用户输入的名称实时转换为标准 Ticker
        tickers_input = []
        mapping_info = []
        for item in raw_inputs:
            resolved = get_ticker_from_name(item)
            if resolved:
                tickers_input.append(resolved)
                mapping_info.append(f"**{item}** ➔ `{resolved}`")
        
        # 将原先刺眼的蓝色 info 框改为高级黑灰风格卡片
        st.markdown(f"""
        <div style="background-color: #1a1a1a; padding: 12px 18px; border-radius: 8px; border: 1px solid #333333; color: #f0f0f0; font-size: 14px; margin-bottom: 15px;">
            : {' | '.join(mapping_info)}
        </div>
        """, unsafe_allow_html=True)

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

            # --- 机构级专业 AI 量化投研看板 ---
            st.subheader(f"🤖 机构级 AI 量化投研看板: {primary_ticker}")
            if not api_key or api_key == "你的API_KEY填在这里":
                st.warning("检测到未正确配置 API Key，请修改代码中的 BUILTIN_API_KEY。")
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

                    tech_summary = f"RSI(14): {latest['RSI']:.2f}, MACD: {latest['MACD']:.2f}"
                    
                    # 华尔街投研专家思维链（Chain of Thought）提示词
                    signal_prompt = f"""你是一位资深的华尔街量化投资经理与风险控制专家。请基于以下多维财务与技术数据，对 {primary_ticker} 进行严谨的专业量化评估：

- 核心技术面 (近1个月): {tech_summary}
- 核心基本面: PE市盈率={pe_str}, PB市净率={pb_str}, 利润率={margin_str}, 营收增长={growth_str}

请遵循以下专业分析步骤（Chain of Thought）：
1. 【多头逻辑】：结合上述数据，寻找支撑该股票的正面逻辑（如成长性、估值优势或技术面动能）。
2. 【空头风险】：结合上述数据，寻找潜在的下行风险或估值泡沫。
3. 【综合裁决】：综合多空力量，给出客观评级。

请严格按照以下格式输出：
【操作评级】强烈买入 / 买入 / 持有观望 / 减持 / 卖出 (五选一)
【置信度评分】(1-10分，评估你对该判断的确信程度)
【多空博弈核心逻辑】(60字以内，必须结合具体数字说明)
【关键支撑与风控点】(各一句话，严格对应指标数据)
"""
                    signal_response = client.chat.completions.create(
                        model=auto_model,
                        messages=[{"role": "user", "content": signal_prompt}]
                    )
                    ai_signal_text = signal_response.choices[0].message.content
                    
                    st.markdown(f"""
                    <div style="background-color: #1a1a1a; padding: 18px; border-radius: 10px; border: 1px solid #333333; color: #f0f0f0; font-size: 15px; line-height: 1.7; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                        {ai_signal_text.replace('\n', '<br>')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                except Exception as ai_err:
                    st.error(f"AI 智能决策请求失败: {ai_err}")

            # 2. Tabs 分页
            tab1, tab2, tab3 = st.tabs(["🏢 基本面分析", "📊 技术指标", "📋 数据预览"])

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
                if api_key and api_key != "你的API_KEY填在这里":
                    try:
                        fund_prompt = f"基于 {primary_ticker} 的硬性数据（PE: {pe_str}, PB: {pb_str}, 利润率: {margin_str}, 营收增长: {growth_str}），请用数据推导列出5项核心基本面评价。"
                        fund_response = client.chat.completions.create(
                            model=auto_model,
                            messages=[{"role": "user", "content": fund_prompt}]
                        )
                        st.write(fund_response.choices[0].message.content)
                    except:
                        st.write("基本面 AI 评估加载失败。")
                else:
                    st.info("请先配置 API Key 以查看 AI 评估。")

            with tab2:
                st.subheader(f"技术指标 (近1个月): {primary_ticker}")
                st.line_chart(df_primary[['RSI']])
                st.line_chart(df_primary[['MACD', 'Signal']])

            with tab3:
                st.subheader(f"{primary_ticker} 原始数据预览")
                st.dataframe(df_primary.tail(10))

        except Exception as e:
            st.error(f"程序运行出错: {e}")
