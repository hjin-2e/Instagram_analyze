import requests
import pandas as pd
import streamlit as st

# ================= =====================
# 1. Streamlit 기본 페이지 및 번역 오류 방지 설정
# ================= =====================
st.set_page_config(page_title="릴스 성과 & 광고 효율 분석기", layout="wide")

st.markdown("""
    <html lang="ko" class="notranslate">
    <head><meta name="google" content="notranslate" /></head>
""", unsafe_allow_html=True)

# ================= =====================
# 2. Instagram API & 계산 로직
# ================= =====================
class InstagramAPI:
    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = "https://graph.facebook.com/v19.0"

    def get_single_media_by_id(self, media_id):
        """특정 릴스/미디어 ID로 직접 조회수 및 정보 단건 조회"""
        url = f"{self.base_url}/{media_id}"
        params = {
            'fields': 'id,caption,media_type,like_count,comments_count,insights.metric(plays)',
            'access_token': self.access_token
        }
        res = requests.get(url, params=params)
        if res.status_code != 200:
            err_msg = res.json().get('error', {}).get('message', '미디어 정보를 불러올 수 없습니다.')
            st.error(f"⚠️️ 조회 실패: {err_msg}")
            return None

        data = res.json()
        plays = 0
        insights = data.get('insights', {}).get('data', [])
        for metric in insights:
            if metric['name'] == 'plays':
                plays = metric['values'][0]['value']

        raw_caption = data.get('caption', '캡션 없음').replace('\n', ' ')
        return {
            'id': data['id'],
            'caption': raw_caption,
            'views': plays,
            'likes': data.get('like_count', 0),
            'comments': data.get('comments_count', 0)
        }

def calculate_metrics(views, streaming_count, ad_budget, cpc_estimate=300, cpm_estimate=4000):
    """음원 유입 전환율 및 광고 효과 시뮬레이션 계산"""
    conversion_rate = (streaming_count / views * 100) if views > 0 else 0
    views_per_stream = round(views / streaming_count, 1) if streaming_count > 0 else 0

    if views >= 100000 and conversion_rate >= 3.0:
        grade = "S (대형 바이럴 & 높은 음원 전환)"
    elif views >= 50000 or conversion_rate >= 2.0:
        grade = "A (상위권 유입 성과)"
    elif views >= 10000 or conversion_rate >= 1.0:
        grade = "B (평균 수준 성과)"
    else:
        grade = "C (개선 필요)"

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
# 3. Streamlit UI 메인 화면
# ================= =====================
st.title("📊 인스타그램 릴스 & 음원 유입 성과 분석기")
st.write("인스타그램 릴스 성과를 바탕으로 음원 스트리밍 유입 전환율과 집행 광고 대비 추정 효율을 계산합니다.")

# 사이드바: 입력 방식 선택
st.sidebar.header("⚙️ 분석 방식 선택")
input_mode = st.sidebar.radio("데이터 입력 모드", ["조회수 직접 입력 (빠른 시뮬레이션)", "Media ID로 릴스 자동 조회"])

# 사이드바: 단가 설정
st.sidebar.markdown("---")
st.sidebar.header("💰 광고 단가 설정")
cpm_estimate = st.sidebar.number_input("추정 CPM (1,000회 노출 비용)", value=4000, step=500)
cpc_estimate = st.sidebar.number_input("추정 CPC (클릭당 비용)", value=300, step=50)

views = 0
selected_media_info = None

# 모드 1: 조회수 수동 입력
if input_mode == "조회수 직접 입력 (빠른 시뮬레이션)":
    st.info("💡 릴스 조회수 수치를 직접 입력하여 빠르게 광고 유입 성과를 시뮬레이션합니다.")
    views = st.number_input("🎯 분석할 릴스 조회수 (회)", value=25000, step=1000)

# 모드 2: Media ID 자동 조회
else:
    st.info("💡 Graph API Access Token과 릴스 Media ID를 입력하여 API 정보를 단건으로 조회합니다.")
    access_token = st.sidebar.text_input("Graph API Access Token", type="password")
    target_media_id = st.text_input("📌 분석할 릴스 Media ID 입력", placeholder="예: 17901234567890123")

    if access_token and target_media_id:
        api = InstagramAPI(access_token)
        media_info = api.get_single_media_by_id(target_media_id.strip())
        if media_info:
            selected_media_info = media_info
            views = media_info['views']
            st.success(f"✅ 릴스 데이터 로드 완료! (조회수: {views:,}회 / 좋아요: {media_info['likes']:,}개)")
            st.caption(f"캡션 내용: {media_info['caption']}")

# 지표 입력 및 성과 분석 결과 출력
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    streaming_count = st.number_input("🎵 멜론/스포티파이 음원 스트리밍 유입 수", value=450, step=10)
with col2:
    ad_budget = st.number_input("💵 집행(예정) 광고 예산 (원)", value=50000, step=10000)

if views > 0:
    res = calculate_metrics(views, streaming_count, ad_budget, cpc_estimate, cpm_estimate)
    st.markdown("---")
    st.subheader("📈 성과 분석 결과")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 릴스 조회수", f"{views:,} 회")
    m2.metric("음원 전환율", f"{res['conversion_rate']} %")
    m3.metric("1유입당 필요 조회수", f"약 {res['views_per_stream']} 회당 1유입")
    m4.metric("콘텐츠 등급", res['grade'])

    if ad_budget > 0:
        st.subheader("🎯 광고 효율 시뮬레이션 예측")
        a1, a2, a3 = st.columns(3)
        a1.metric("예상 추가 노출 (CPM 기준)", f"+{res['paid_views']:,} 회")
        a2.metric("예상 프로필/링크 클릭 (CPC 기준)", f"+{res['paid_clicks']:,} 회")
        a3.metric("예상 추가 음원 스트리밍", f"+{res['paid_streams']:,} 회")