import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import time

# 1. 페이지 설정
st.set_page_config(page_title="밥그릇 단타 스크리너", layout="wide")
st.title("🥣 KOSDAQ 밥그릇 3번 자리 스크리너")
st.markdown("**조건:** 224일선 상향 돌파 & 거래량 20일 평균 대비 500% 이상 폭발")

# 2. 기초 종목 필터링 (불량 종목 & 소외주 1차 컷아웃)
@st.cache_data(ttl=3600)
def get_base_symbols():
    try:
        df_krx = fdr.StockListing('KOSDAQ')
        
        # [방어선 1] 스팩, 우선주 제외
        df_krx = df_krx[~df_krx['Name'].str.contains('스팩|우$|우[A-Z]$', regex=True, na=False)]
        
        # [방어선 2] 관리종목 제외
        try:
            admin_df = fdr.StockListing('KRX-ADMIN')
            admin_symbols = admin_df['Symbol'].tolist() if not admin_df.empty else []
            df_krx = df_krx[~df_krx['Code'].isin(admin_symbols)]
        except:
            pass 
            
        # 🚀 [속도 최적화] 당일 거래대금 10억 미만 소외주 우선 탈락 (시간 단축)
        # 종목 리스트 자체에서 거래량이 터지지 않은 애들을 미리 걸러냅니다.
        if 'Amount' in df_krx.columns:
            df_krx = df_krx[df_krx['Amount'] >= 1000000000]
            
        return df_krx[['Code', 'Name']].copy()
    except Exception as e:
        st.error("종목 목록을 불러오지 못했습니다.")
        return pd.DataFrame()

# 3. 핵심 로직
# ✨ [버그 수정 2] show_spinner=False를 추가해 글자 겹침 해결
@st.cache_data(ttl=600, show_spinner=False)
def run_screener():
    symbols_df = get_base_symbols()
    if symbols_df.empty: return pd.DataFrame()

    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    results = []
    total_stocks = len(symbols_df)
    progress_text = "전체 종목 차트 분석 중..."
    my_bar = st.progress(0.0, text=f"{progress_text} (0/{total_stocks})")

    # ✨ [버그 수정 1] enumerate를 사용해 고유 번호표(i) 대신 순수한 카운트(count) 사용
    for count, (i, row) in enumerate(symbols_df.iterrows()):
        code = row['Code']
        name = row['Name']
        
        if count % 10 == 0:
            # count / total_stocks는 절대 1.0을 넘지 않음
            my_bar.progress(count / total_stocks, text=f"{progress_text} ({count}/{total_stocks})")

        try:
            df = fdr.DataReader(code, start_date, end_date)
            if len(df) < 224: continue
                
            df['MA224'] = df['Close'].rolling(window=224).mean()
            df['Vol20'] = df['Volume'].rolling(window=20).mean()
            
            today_data = df.iloc[-1]
            yesterday_data = df.iloc[-2]
            
            if pd.isna(today_data['MA224']) or pd.isna(today_data['Vol20']) or today_data['Vol20'] == 0:
                continue

            vol_surge = (today_data['Volume'] / today_data['Vol20']) * 100
            
            if vol_surge >= 500:
                if yesterday_data['Close'] < yesterday_data['MA224'] and today_data['Close'] > today_data['MA224']:
                    
                    disparity_224 = ((today_data['Close'] / today_data['MA224']) - 1) * 100
                    chg_ratio = ((today_data['Close'] / yesterday_data['Close']) - 1) * 100
                    
                    results.append({
                        '종목명': name,
                        '현재가': int(today_data['Close']),
                        '등락률(%)': round(chg_ratio, 2),
                        '거래량 증폭률(%)': int(vol_surge),
                        '224일선 이격도(%)': round(disparity_224, 2),
                        '당일 거래량': int(today_data['Volume'])
                    })
        except:
            continue

    my_bar.progress(1.0, text="분석 완료!")
    time.sleep(1)
    my_bar.empty() 
    
    return pd.DataFrame(results)

# 4. 화면 출력
if st.button("🚀 스크리너 실행 (수집 시작)"):
    run_screener.clear() 
    
    with st.spinner('세력의 흔적을 찾는 중입니다...'):
        result_df = run_screener()
        
        if not result_df.empty:
            st.success(f"🔥 총 {len(result_df)}개의 돌파 종목을 찾았습니다!")
            
            styled_df = result_df.style.format({
                '현재가': '{:,.0f}원',
                '당일 거래량': '{:,.0f}주',
                '등락률(%)': '{:,.2f}%',
                '거래량 증폭률(%)': '{:,.0f}%',
                '224일선 이격도(%)': '{:,.2f}%'
            }).map(
                lambda x: 'color: #FF4B4B; font-weight: bold' if x > 0 else ('color: #1E90FF' if x < 0 else 'color: inherit'), 
                subset=['등락률(%)', '224일선 이격도(%)']
            )
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.info("현재 조건을 만족하는 종목이 없습니다.")
