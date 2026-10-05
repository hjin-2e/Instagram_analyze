import os
import requests
import pandas as pd
import streamlit as st

# ================= =====================
# 1. Instagram Graph API 연동 클래스
# ================= =====================
class InstagramAPI:
    def __init__(self, access_token, instagram_account_id):
        self.access_token = access_token
        self.account_id = instagram_account_id
        self.base_url = "https://graph.facebook.com/v19.0"

    def get_reels_media(self):
        """계정의 최근 릴스/미디어 목록 및 인사이트 조회"""
        url = f"{self.base_url}/{self.account_id}/media"
        params = {
            'fields': 'id,caption,media_type,media_url,like_count,comments_count,insights.metric(plays,reach,total_interactions)',
            'access_token': self.access_token
        }
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            st.error(f"API 호출 실패: {response.json().get('error', {}).get('message', '알 수 없는 오류')}")
            return []

        data = response.json().get('data', [])
        # REELS (VIDEO) 형태만 필터링
        reels_list = []
        for item in data:
            if item.get('media_type') in ['VIDEO', 'REELS']:
                plays = 0
                insights = item.get('insights', {}).get('data', [])
                for metric in insights:
                    if metric['name'] == 'plays':
                        plays = metric['values'][0]['value']
                
                reels_list.append({
                    'id': item['id'],
                    'caption': item.get('caption', '캡션 없음')[:20] + '...',
                    'views': plays,
                    'likes': item.get('like_count', 0),
                    'comments': item.get('comments_count', 0)
                })
        return reels_list


# ================= =====================
# 2. 성과 및 광고 효율 계산 로직
# ================= =====================
def calculate_metrics(views, streaming_count, ad_budget, cpc_estimate=300, cpm_estimate=4000):
    # 1. 음원 전환율 계산 (조회수 대비 음원 스트리밍 수)
    conversion_rate = (streaming_count / views * 100) if views > 0 else 0
    views_per_stream = round(views / streaming_count, 1) if streaming_count > 0 else 0

    # 2. 성과 등급 판정
    if views >= 100000 and conversion_rate >= 3.0:
        grade = "S (대형 바이럴 & 높은 음원 전환)"
    elif views >= 50000 or conversion_rate >= 2.0:
        grade = "A (상위권 유입 성과)"
    elif views >= 10000 or conversion_rate >= 1.0:
        grade = "B (평균 수준 성과)"
    else:
        grade = "C (개선 필요)"

    # 3. 광고 집행 시 예상 효율
    paid_views = int((ad_budget / cpm_estimate) * 1000) if ad_budget > 0 else 0
    paid_clicks = int(ad_budget / cpc_estimate) if ad_budget > 0 else 0
    paid_streams = int(paid_views * (conversion_rate / 100)) if ad_budget > 0 else 0

    return {
        "conversion_rate": round(conversion_rate, 2),
        "views_per_stream": views_per_stream,
        "grade": grade,
        "paid_views": paid_views,
        "paid_clicks": paid_clicks,
        "paid_streams": paid_streams
    }


# ================= =====================
# 3. Streamlit 대시보드 UI
# ================= =====================
st.set_page_config(page_title="릴스 성과 & 광고 효율 분석기", layout="wide")

st.title("📊 인스타그램 릴스 & 음원 유입 성과 분석기")
st.write("인스타그램 연동을 통해 릴스 조회수를 자동으로 불러오고, 광고 대비 음원 스트리밍 유입을 계산합니다.")

# 사이드바: API 설정
st.sidebar.header("🔑 Instagram API 설정")
access_token = st.sidebar.text_input("Meta Access Token", type="password")
instagram_account_id = st.sidebar.text_input("Instagram Business Account ID")

# 시뮬레이션 샘플 데이터 모드 옵션
use_demo = st.sidebar.checkbox("API 연동 없이 더미 데이터로 테스트", value=True)

views = 0
if use_demo:
    st.info("💡 더미 데이터 모드로 작동 중입니다. 사이드바에서 수치를 자유롭게 수정해 보세요.")
    selected_reels_views = st.number_input("릴스 조회수 (직접 입력)", value=25000, step=1000)
    views = selected_reels_views
else:
    if access_token and instagram_account_id:
        ig_api = InstagramAPI(access_token, instagram_account_id)
        reels_data = ig_api.get_reels_media()
        
        if reels_data:
            df_reels = pd.DataFrame(reels_data)
            st.subheader("🎬 최근 릴스 목록")
            st.dataframe(df_reels, use_container_width=True)
            
            # 특정 릴스 선택
            selected_reel_caption = st.selectbox("분석할 릴스를 선택하세요", df_reels['caption'])
            selected_row = df_reels[df_reels['caption'] == selected_reel_caption].iloc[0]
            views = selected_row['views']
            st.success(f"선택한 릴스 조회수: {views:,} 회")
    else:
        st.warning("사이드바에 Access Token과 Account ID를 입력하거나 '더미 데이터로 테스트'를 체크하세요.")

# 분석 입력 폼
col1, col2 = st.columns(2)
with col1:
    streaming_count = st.number_input("🎵 멜론/스포티파이 음원 스트리밍 유입 수", value=450, step=10)
with col2:
    ad_budget = st.number_input("💰 집행(예정) 광고 비용 (원)", value=50000, step=10000)

# 결과 계산 출력
if views > 0:
    res = calculate_metrics(views, streaming_count, ad_budget)

    st.markdown("---")
    st.subheader("📈 성과 분석 결과")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 릴스 조회수", f"{views:,} 회")
    m2.metric("음원 전환율", f"{res['conversion_rate']} %")
    m3.metric("1유입당 필요 조회수", f"약 {res['views_per_stream']} 회당 1유입")
    m4.metric("콘텐츠 등급", res['grade'])

    if ad_budget > 0:
        st.subheader("🎯 광고 시뮬레이션 예측")
        a1, a2, a3 = st.columns(3)
        a1.metric("예상 추가 노출 (CPM 기준)", f"+{res['paid_views']:,} 회")
        a2.metric("예상 프로필/링크 클릭 (CPC 기준)", f"+{res['paid_clicks']:,} 회")
        a3.metric("예상 추가 음원 스트리밍", f"+{res['paid_streams']:,} 회")