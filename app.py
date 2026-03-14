import streamlit as st
import FinanceDataReader as fdr
import pandas as pd

# 1. 페이지 설정 (모바일 화면에 꽉 차도록 wide 레이아웃 적용)
st.set_page_config(page_title="KOSDAQ 단타 스크리너", layout="wide")

st.title("📈 KOSDAQ 단타 스크리너")

# 2. 데이터 로드 및 캐싱 (API 호출 최소화 및 로딩 속도 향상)
# ttl=60 설정으로 60초 동안 데이터를 캐싱합니다.
@st.cache_data(ttl=60)
def load_and_filter_data():
    try:
        # KRX 전체 종목 가져오기
        krx_df = fdr.StockListing('KRX')
        
        # 코스닥(KOSDAQ) 종목만 필터링
        df = krx_df[krx_df['Market'] == 'KOSDAQ'].copy()
        
        # 관리종목 가져오기
        admin_df = fdr.StockListing('KRX-ADMIN')
        admin_symbols = admin_df['Symbol'].tolist() if not admin_df.empty else []
        
        # [필터링 1] 관리종목 제외 (단타 부적합)
        if admin_symbols:
            df = df[~df['Code'].isin(admin_symbols)]
            
        # [필터링 2] 스팩(SPAC) 제외
        df = df[~df['Name'].str.contains('스팩', na=False)]
        
        # [필터링 3] 우선주 제외 (종목명이 '우', '우B' 등으로 끝나는 종목)
        df = df[~df['Name'].str.contains(r'우$|우[A-Z]$', regex=True, na=False)]
        
        # FinanceDataReader의 등락률 컬럼명 오타(ChagesRatio) 대응 및 컬럼 선택
        ratio_col = 'ChagesRatio' if 'ChagesRatio' in df.columns else 'ChangesRatio'
        
        # 필요한 컬럼만 선택
        result_df = df[['Name', 'Close', ratio_col, 'Volume']].copy()
        result_df.columns = ['종목명', '현재가', '등락률', '당일 거래량']
        
        return result_df

    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

# 3. 상단 '데이터 갱신' 버튼
# 버튼을 누르면 캐시를 지우고 데이터를 새로고침합니다.
if st.button("🔄 데이터 갱신"):
    load_and_filter_data.clear()

# 데이터 로딩 스피너
with st.spinner('실시간 KOSDAQ 데이터를 불러오는 중입니다...'):
    df_kosdaq = load_and_filter_data()

# 4. 결과 출력 (Dataframe)
if not df_kosdaq.empty:
    # 모바일 가독성을 높이기 위한 데이터 포맷팅 및 스타일링
    # 등락률이 양수면 빨간색, 음수면 파란색으로 표시합니다.
    styled_df = df_kosdaq.style.format({
        '현재가': '{:,.0f}',
        '등락률': '{:,.2f}%',
        '당일 거래량': '{:,.0f}'
    }).map(
        lambda x: 'color: red' if x > 0 else ('color: blue' if x < 0 else 'color: inherit'), 
        subset=['등락률']
    )
    
    # 모바일 화면에 꽉 차게(use_container_width=True), 인덱스 번호 숨김(hide_index=True)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.warning("조건에 맞는 종목 데이터가 없습니다.")