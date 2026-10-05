import requests
import pandas as pd
import streamlit as st

# ================= =====================
# 1. Streamlit 기본 페이지 및 번역 오류 방지 설정
# ================= =====================
st.set_page_config(page_title="인스타그램 릴스 & 광고 효율 분석기", layout="wide")

st.markdown("""
    <html lang="ko" class="notranslate">
    <head><meta name="google" content="notranslate" /></head>
""", unsafe_allow_html=True)

# ================= =====================
# 2. Instagram API 클래스 및 성과 계산 함수
# ================= =====================
class InstagramAPI:
    def __init__(self, access_token, instagram_account_id=None):
        self.access_token = access_token
        self.base_url = "https://graph.facebook.com/v19.0"
        self.account_id = instagram_account_id or self._get_instagram_account_id()

    def _get_instagram_account_id(self):
        """액세스 토큰에 연결된 Instagram 비즈니스 계정 ID 자동 검색"""
        url = f"{self.base_url}/me/accounts"
        params = {
            'fields': 'instagram_business_account',
            'access_token': self.access_token
        }
        res = requests.get(url, params=params).json()
        for page in res.get('data', []):
            if 'instagram_business_account' in page:
                return page['instagram_business_account']['id']
        return None

    def get_reels_media(self):
        """내 계정의 최근 릴스 목록 및 조회수/좋아요/댓글 가져오기"""
        if not self.account_id:
            st.error("❌ 연동된 Instagram 비즈니스 계정 ID를 찾을 수 없습니다. 사이드바에 ID(178414...)를 직접 입력해 주세요.")
            return []

        url = f"{self.base_url}/{self.account_id}/media"
        # Meta API 최신 규격 반영: plays -> views 변경
        params = {
            'fields': 'id,caption,media_type,media_url,like_count,comments_count,insights.metric(views)',
            'access_token': self.access_token
        }
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            err_msg = response.json().get('error', {}).get('message', '알 수 없는 오류')
            st.error(f"❌ API 호출 실패: {err_msg}")
            return []

        data = response.json().get('data', [])
        reels_list = []
        for item in data:
            if item.get('media_type') in ['VIDEO', 'REELS']:
                views_count = 0
                insights = item.get('insights', {}).get('data', [])
                for metric in insights:
                    if metric['name'] == 'views':
                        views_count = metric['values'][0]['value']
                
                raw_caption = item.get('caption', '캡션 없음').replace('\n', ' ')
                short_caption = raw_caption[:20] + '..' if len(raw_caption) > 20 else raw_caption
                
                reels_list.append({
                    'id': item['id'],
                    'display_label': f"[{item['id'][-4:]}] {short_caption} | 조회수 {views_count:,}회",
                    'caption': raw_caption,
                    'views': views_count,
                    'likes': item.get('like_count', 0),
                    'comments': item.get('comments_count', 0)
                })
        return reels_list

def calculate_metrics(views, streaming_count, ad_budget, cpc_estimate=300, cpm_estimate=4000):
    """릴스 성과 분석 및 음원 유입 / 광고 시뮬레이션 계산"""
    conversion_rate = (streaming_count / views * 100) if views > 0 else 0
    views_per_stream = round(views / streaming_count, 1) if streaming_count > 0 else 0

    # 릴스 성과 등급 판정
    if views >= 100000 and conversion_rate >= 3.0:
        grade = "S (대형 바이럴 & 높은 음원 전환)"
    elif views >= 50000 or conversion_rate >= 2.0:
        grade = "A (상위권 유입 성과)"
    elif views >= 10000 or conversion_rate >= 1.0:
        grade = "B (평균 수준 성과)"
    else:
        grade = "C (개선 필요)"

    # 광고 집행 시 예상 유입 예측
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
st.title("📊 내 인스타그램 릴스 성과 & 광고 효율 분석기")
st.write("인스타그램 계정을 연동하여 릴스 목록을 불러오고, 음원 유입 전환율과 광고 효율을 계산합니다.")

# 사이드바: 계정 연동 정보 설정
st.sidebar.header("🔑 인스타그램 계정 연동")
user_token = st.sidebar.text_input("Access Token 입력", type="password")
custom_ig_id = st.sidebar.text_input("Instagram 계정 ID (178414...)", help="자동 연동 실패 시 직접 입력하세요.")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 광고 단가 기준 설정")
cpm_estimate = st.sidebar.number_input("추정 CPM (1,000회 노출 비용 / 원)", value=4000, step=500)
cpc_estimate = st.sidebar.number_input("추정 CPC (클릭당 비용 / 원)", value=300, step=50)

views = 0

# 메인 연동 로직
if user_token:
    ig_api = InstagramAPI(user_token, instagram_account_id=custom_ig_id.strip() if custom_ig_id.strip() else None)
    reels_data = ig_api.get_reels_media()
    
    if reels_data:
        df_reels = pd.DataFrame(reels_data)
        st.subheader("🎬 최근 내 릴스 목록")
        st.dataframe(df_reels[['id', 'caption', 'views', 'likes', 'comments']], use_container_width=True)
        
        # 릴스 선택 드롭다운
        selected_label = st.selectbox("📌 분석할 릴스를 선택하세요", df_reels['display_label'])
        selected_row = df_reels[df_reels['display_label'] == selected_label].iloc[0]
        views = selected_row['views']
        st.success(f"선택한 릴스: **{selected_row['caption']}** (조회수: **{views:,}회**)")

else:
    st.info("👈 사이드바에 Access Token을 입력하여 내 인스타그램 계정을 연동해 주세요.")

# 음원 유입 수 및 광고 예산 입력 폼
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    streaming_count = st.number_input("🎵 멜론/스포티파이 음원 스트리밍 유입 수", value=450, step=10)
with col2:
    ad_budget = st.number_input("💰 집행(예정) 광고 비용 (원)", value=50000, step=10000)

# 분석 결과 출력
if views > 0:
    res = calculate_metrics(views, streaming_count, ad_budget, cpc_estimate, cpm_estimate)
    st.markdown("---")
    st.subheader("📈 릴스 성과 분석 결과")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 릴스 조회수", f"{views:,} 회")
    m2.metric("음원 유입 전환율", f"{res['conversion_rate']} %")
    m3.metric("1유입당 필요 조회수", f"약 {res['views_per_stream']} 회당 1유입")
    m4.metric("콘텐츠 등급", res['grade'])

    if ad_budget > 0:
        st.subheader("🎯 광고 집행 시 예상 효율 시뮬레이션")
        a1, a2, a3 = st.columns(3)
        a1.metric("예상 추가 노출 (CPM 기준)", f"+{res['paid_views']:,} 회")
        a2.metric("예상 프로필/링크 클릭 (CPC 기준)", f"+{res['paid_clicks']:,} 회")
        a3.metric("예상 추가 음원 스트리밍", f"+{res['paid_streams']:,} 회")