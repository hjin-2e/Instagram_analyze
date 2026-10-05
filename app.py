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
# 2. Instagram API & OAuth 처리 클래스/함수
# ================= =====================
def get_short_lived_token(client_id, client_secret, redirect_uri, code):
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'code': code
    }
    response = requests.post(url, data=payload)
    return response.json()

def get_long_lived_token(client_id, client_secret, short_token):
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        'grant_type': 'fb_exchange_token',
        'client_id': client_id,
        'client_secret': client_secret,
        'fb_exchange_token': short_token
    }
    response = requests.get(url, params=params)
    return response.json()

class InstagramAPI:
    def __init__(self, access_token, instagram_account_id=None):
        self.access_token = access_token
        self.base_url = "https://graph.facebook.com/v19.0"
        self.account_id = instagram_account_id or self._get_instagram_account_id()

    def _get_instagram_account_id(self):
        """Facebook 페이지에 연결된 Instagram 비즈니스 계정 ID 자동 탐색"""
        url = f"{self.base_url}/me/accounts"
        params = {
            'fields': 'instagram_business_account,name',
            'access_token': self.access_token
        }
        res = requests.get(url, params=params).json()
        
        # 1. /me/accounts 에서 연결된 Instagram 비즈니스 계정 찾기
        for page in res.get('data', []):
            if 'instagram_business_account' in page:
                return page['instagram_business_account']['id']
                
        return None

    def get_reels_media(self):
        """계정의 최근 릴스/미디어 목록 및 인사이트 조회"""
        if not self.account_id:
            st.error("연동된 Instagram 비즈니스 계정 ID를 찾을 수 없습니다. 페이스북 페이지 연결 상태를 확인하시거나 사이드바에 Instagram 계정 ID(178414...)를 직접 입력해주세요.")
            return []

        url = f"{self.base_url}/{self.account_id}/media"
        params = {
            'fields': 'id,caption,media_type,media_url,like_count,comments_count,insights.metric(plays,reach,total_interactions)',
            'access_token': self.access_token
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            err_msg = response.json().get('error', {}).get('message', '알 수 없는 오류')
            st.error(f"API 호출 실패: {err_msg}")
            return []

        data = response.json().get('data', [])
        reels_list = []
        for item in data:
            if item.get('media_type') in ['VIDEO', 'REELS']:
                plays = 0
                insights = item.get('insights', {}).get('data', [])
                for metric in insights:
                    if metric['name'] == 'plays':
                        plays = metric['values'][0]['value']
                
                raw_caption = item.get('caption', '캡션 없음').replace('\n', ' ')
                short_caption = raw_caption[:18] + '..' if len(raw_caption) > 18 else raw_caption
                
                reels_list.append({
                    'id': item['id'],
                    'display_label': f"[{item['id'][-4:]}] {short_caption} ({plays:,}회)",
                    'caption': raw_caption,
                    'views': plays,
                    'likes': item.get('like_count', 0),
                    'comments': item.get('comments_count', 0)
                })
        return reels_list

def calculate_metrics(views, streaming_count, ad_budget, cpc_estimate=300, cpm_estimate=4000):
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
st.write("인스타그램 연동을 통해 릴스 조회수를 자동으로 불러오고, 광고 대비 음원 스트리밍 유입을 계산합니다.")

# 사이드바 1: 인증 연동 방식 선택
st.sidebar.header("🔑 연동 방식 선택")
auth_mode = st.sidebar.radio("인증 모드", ["Access Token 직접 입력", "Meta OAuth 로그인", "더미 데이터 테스트"])

secret_client_id = st.secrets.get("CLIENT_ID", "")
secret_client_secret = st.secrets.get("CLIENT_SECRET", "")
secret_redirect_uri = st.secrets.get("REDIRECT_URI", "https://instagram-reels-analyzer.streamlit.app/")

views = 0

# 모드 1: 토큰 직접 입력 (계정 ID 수동 입력 필드 추가)
if auth_mode == "Access Token 직접 입력":
    st.sidebar.markdown("---")
    user_token = st.sidebar.text_input("Instagram Access Token 입력", type="password")
    custom_ig_id = st.sidebar.text_input("Instagram 계정 ID (선택사항)", help="자동 탐색 실패 시 178414... 형식의 계정 ID를 입력하세요.")
    
    if user_token:
        ig_api = InstagramAPI(user_token, instagram_account_id=custom_ig_id.strip() if custom_ig_id.strip() else None)
        reels_data = ig_api.get_reels_media()
        if reels_data:
            df_reels = pd.DataFrame(reels_data)
            st.subheader("🎬 최근 릴스 목록")
            st.dataframe(df_reels[['id', 'caption', 'views', 'likes', 'comments']], use_container_width=True)
            
            selected_label = st.selectbox("분석할 릴스를 선택하세요", df_reels['display_label'])
            selected_row = df_reels[df_reels['display_label'] == selected_label].iloc[0]
            views = selected_row['views']
            st.success(f"선택한 릴스 조회수: {views:,} 회")
    else:
        st.info("💡 Meta 개발자 도구(Graph API Explorer)에서 생성한 액세스 토큰을 사이드바에 입력해 보세요.")

# 모드 2: OAuth 로그인
elif auth_mode == "Meta OAuth 로그인":
    CLIENT_ID = st.sidebar.text_input("Meta App ID", value=secret_client_id)
    CLIENT_SECRET = st.sidebar.text_input("Meta App Secret", value=secret_client_secret, type="password")
    REDIRECT_URI = st.sidebar.text_input("Redirect URI", value=secret_redirect_uri)

    query_params = st.query_params
    if 'code' in query_params and 'access_token' not in st.session_state:
        auth_code = query_params['code']
        st.info("🔄 Instagram 로그인 승인 확인 중...")
        short_res = get_short_lived_token(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, auth_code)
        
        if 'access_token' in short_res:
            short_token = short_res['access_token']
            long_res = get_long_lived_token(CLIENT_ID, CLIENT_SECRET, short_token)
            st.session_state['access_token'] = long_res.get('access_token', short_token)
            st.query_params.clear()
            st.rerun()

    if 'access_token' in st.session_state:
        st.success("✅ Instagram 계정이 연동되었습니다!")
        ig_api = InstagramAPI(st.session_state['access_token'], instagram_account_id=None)
        reels_data = ig_api.get_reels_media()
        
        if reels_data:
            df_reels = pd.DataFrame(reels_data)
            st.subheader("🎬 최근 릴스 목록")
            st.dataframe(df_reels[['id', 'caption', 'views', 'likes', 'comments']], use_container_width=True)
            
            selected_label = st.selectbox("분석할 릴스를 선택하세요", df_reels['display_label'])
            selected_row = df_reels[df_reels['display_label'] == selected_label].iloc[0]
            views = selected_row['views']
            st.success(f"선택한 릴스 조회수: {views:,} 회")
        
        if st.button("🚪 연동 해제 (로그아웃)"):
            del st.session_state['access_token']
            st.rerun()
    else:
        if CLIENT_ID and CLIENT_SECRET:
            auth_url = (
                f"https://www.facebook.com/v19.0/dialog/oauth"
                f"?client_id={CLIENT_ID}"
                f"&redirect_uri={REDIRECT_URI}"
                f"&scope=public_profile"
                f"&response_type=code"
            )
            st.warning("Instagram 연동을 진행하려면 아래 로그인 버튼을 눌러주세요.")
            st.link_button("📸 Instagram 계정으로 로그인", auth_url, type="primary", use_container_width=True)

# 모드 3: 더미 데이터
else:
    st.info("💡 더미 데이터 모드로 작동 중입니다.")
    views = st.number_input("릴스 조회수 (직접 입력)", value=25000, step=1000)

# 사이드바: 광고 단가 설정
st.sidebar.markdown("---")
st.sidebar.header("⚙️ 광고 단가 설정")
cpm_estimate = st.sidebar.number_input("추정 CPM (1,000회 노출 비용)", value=4000, step=500)
cpc_estimate = st.sidebar.number_input("추정 CPC (클릭당 비용)", value=300, step=50)

# 분석 입력 폼 및 결과 출력
col1, col2 = st.columns(2)
with col1:
    streaming_count = st.number_input("🎵 멜론/스포티파이 음원 스트리밍 유입 수", value=450, step=10)
with col2:
    ad_budget = st.number_input("💰 집행(예정) 광고 비용 (원)", value=50000, step=10000)

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
        st.subheader("🎯 광고 시뮬레이션 예측")
        a1, a2, a3 = st.columns(3)
        a1.metric("예상 추가 노출 (CPM 기준)", f"+{res['paid_views']:,} 회")
        a2.metric("예상 프로필/링크 클릭 (CPC 기준)", f"+{res['paid_clicks']:,} 회")
        a3.metric("예상 추가 음원 스트리밍", f"+{res['paid_streams']:,} 회")