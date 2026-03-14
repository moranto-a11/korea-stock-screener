import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import time

# 1. 페이지 설정 (모바일 최적화)
st.set_page_config(page_title="밥그릇 단타 스크리너", layout="wide")
st.title("🥣 KOSDAQ 밥그릇 3번 자리 스크리너")
st.markdown("**조건:** 224일선 상향 돌파 & 거래량 20일 평균 대비 500% 이상 폭발")

# 2. 기초 종목 필터링 (스팩, 우선주, 관리종목 제외)
@st.cache_data(ttl=3600)
def get_base_symbols():
    try:
        df_krx = fdr.StockListing('KOSDAQ')
        
        # [방어선 1] 스팩, 우선주 제외
        df_krx = df_krx[~df_krx['Name'].str.contains('스팩|우$|우[A-Z]$', regex=True, na=False)]
        
        # [방어선 2] 관리종목 제외 (상폐 위험 회피)
        try:
            admin_df = fdr.StockListing('KRX-ADMIN')
            admin_symbols = admin_df['Symbol'].tolist() if not admin_df.empty else []
            df_krx = df_krx[~df_krx['Code'].isin(admin_symbols)]
        except:
            pass # 관리종목 조회가 안 될 경우 패스
            
        return df_krx[['Code', 'Name']].copy()
    except Exception as e:
        st.error("종목 목록을 불러오지 못했습니다.")
        return pd.DataFrame()

# 3. 핵심 로직: 224일선 및 거래량 계산
@st.cache_data(ttl=600) # 10분마다 갱신
def run_screener():
    symbols_df = get_base_symbols()
    if symbols_df.empty: return pd.DataFrame()

    # 1년 치 데이터를 가져오기 위한 날짜 설정
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    results = []
    
    # UI: 진행 상태 표시줄
    progress_text = "전체 종목 차트 분석 중... (약 2~3분 소요)"
    my_bar = st.progress(0, text=progress_text)
    total_stocks = len(symbols_df)

    for i, row in symbols_df.iterrows():
        code = row['Code']
        name = row['Name']
        
        # 진행 상태 업데이트 (UI 멈춤 방지를 위해 50종목마다 갱신)
        if i % 50 == 0:
            my_bar.progress(i / total_stocks, text=f"{progress_text} ({i}/{total_stocks})")

        try:
            # 개별 종목 주가 가져오기
            df = fdr.DataReader(code, start_date, end_date)
            
            if len(df) < 224:
                continue # 상장한 지 224일이 안 된 신규 상장주는 패스
                
            # 기술적 지표 계산
            df['MA224'] = df['Close'].rolling(window=224).mean()
            df['Vol20'] = df['Volume'].rolling(window=20).mean()
            
            # 가장 최근 거래일 데이터 추출
            today_data = df.iloc[-1]
            yesterday_data = df.iloc[-2]
            
            # 데이터가 0이거나 NaN인 경우 오류 방지
            if pd.isna(today_data['MA224']) or pd.isna(today_data['Vol20']) or today_data['Vol20'] == 0:
                continue

            # [조건 1] 거래량 폭발: 당일 거래량이 20일 평균 거래량의 5배(500%) 이상인가?
            vol_surge = (today_data['Volume'] / today_data['Vol20']) * 100
            
            if vol_surge >= 500:
                # [조건 2] 224일선 돌파: 어제는 224일선 아래였는데, 오늘은 위로 올라왔는가? (크로스업)
                if yesterday_data['Close'] < yesterday_data['MA224'] and today_data['Close'] > today_data['MA224']:
                    
                    # UI에 보여줄 부가 데이터 계산
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
            continue # 데이터 로드 실패 종목은 패스

    my_bar.progress(1.0, text="분석 완료!")
    time.sleep(1)
    my_bar.empty() # 완료 후 진행 바 숨김
    
    return pd.DataFrame(results)

# 4. 화면 출력
if st.button("🚀 스크리너 실행 (수집 시작)"):
    run_screener.clear() # 캐시 초기화 후 재실행
    
    with st.spinner('세력의 흔적을 찾는 중입니다...'):
        result_df = run_screener()
        
        if not result_df.empty:
            st.success(f"🔥 총 {len(result_df)}개의 돌파 종목을 찾았습니다!")
            
            # 모바일 가독성을 위한 스타일링
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
            st.info("현재 224일선 돌파 & 거래량 폭발 조건을 만족하는 종목이 없습니다. (시장이 잠잠하거나 하락장일 확률이 높습니다.)")
