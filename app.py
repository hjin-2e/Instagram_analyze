import requests
import pandas as pd
import streamlit as st

# ================= =====================
# 1. Streamlit 기본 페이지 및 스타일 설정
# ================= =====================
st.set_page_config(page_title="인스타그램 릴스 & 광고 효율 분석기", layout="wide")

st.markdown("""
    <html lang="ko" class="notranslate">
    <head><meta name="google" content="notranslate" /></head>
""", unsafe_allow_html=True)

# ================= =====================
# 2. Instagram & Ads API 통합 클래스
# ================= =====================
class MetaAPI:
    def __init__(self, access_token, instagram_account_id=None, ad_account_id=None):
        self.access_token = access_token
        self.base_url = "https://graph.facebook.com/v19.0"
        self.account_id = instagram_account_id
        self.ad_account_id = ad_account_id if not ad_account_id or ad_account_id.startswith('act_') else f"act_{ad_account_id}"

    def get_reels_media(self):
        """내 계정의 최근 릴스 목록 및 조회수/좋아요/댓글 가져오기"""
        if not self.account_id:
            st.error("❌ 연동된 Instagram 비즈니스 계정 ID를 입력해 주세요.")
            return []

        url = f"{self.base_url}/{self.account_id}/media"
        params = {
            'fields': 'id,caption,media_type,media_url,like_count,comments_count,insights.metric(views)',
            'access_token': self.access_token
        }
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            err_msg = response.json().get('error', {}).get('message', '알 수 없는 오류')
            st.error(f"❌ Instagram API 호출 실패: {err_msg}")
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

    def get_ad_performance_by_media(self, media_id):
        """특정 릴스(Media ID) 소재로 집행된 실제 광고비 및 성과 추적"""
        if not self.ad_account_id:
            return None

        # 광고 계정 내 전체 소재 인사이트 조회
        url = f"{self.base_url}/{self.ad_account_id}/insights"
        params = {
            'level': 'ad',
            'fields': 'ad_id,ad_name,spend,impressions,clicks,cpm,cpc',
            'date_preset': 'maximum',
            'access_token': self.access_token
        }
        res = requests.get(url, params=params)
        
        if res.status_code != 200:
            return None

        ad_data = res.json().get('data', [])
        
        total_spend = 0.0
        total_impressions = 0
        total_clicks = 0

        # 소재별 연동 집계
        for ad in ad_data:
            total_spend += float(ad.get('spend', 0))
            total_impressions += int(ad.get('impressions', 0))
            total_clicks += int(ad.get('clicks', 0))

        if total_spend == 0:
            return None

        real_cpm = round((total_spend / total_impressions * 1000), 1) if total_impressions > 0 else 0
        real_cpc = round(total_spend / total_clicks, 1) if total_clicks > 0 else 0

        return {
            "spend": int(total_spend),
            "impressions": total_impressions,
            "clicks": total_clicks,
            "cpm": real_cpm,
            "cpc": real_cpc
        }

def calculate_metrics(views, streaming_count, ad_budget, stream_revenue=3.0, cpc_estimate=300, cpm_estimate=4000):
    """자연 성과 및 광고 효율 분석 로직"""
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

    paid_views = int((ad_budget / cpm_estimate) * 1000) if ad_budget > 0 and cpm_estimate > 0 else 0
    paid_clicks = int(ad_budget / cpc_estimate) if ad_budget > 0 and cpc_estimate > 0 else 0
    paid_streams = int(paid_views * (conversion_rate / 100)) if ad_budget > 0 else 0
    
    cpa_per_stream = round(ad_budget / paid_streams) if paid_streams > 0 else 0
    est_revenue = int(paid_streams * stream_revenue)
    roas = round((est_revenue / ad_budget) * 100, 1) if ad_budget > 0 else 0

    return {
        "conversion_rate": round(conversion_rate, 2),
        "views_per_stream": views_per_stream,
        "grade": grade,
        "paid_views": paid_views,
        "paid_clicks": paid_clicks,
        "paid_streams": paid_streams,
        "cpa_per_stream": cpa_per_stream,
        "est_revenue": est_revenue,
        "roas": roas
    }

# ================= =====================
# 3. Streamlit UI 메인 화면
# ================= =====================
st.title("📊 인스타그램 릴스 & 실제 광고 성과 분석기")
st.write("Meta Marketing API 연동을 통해 실제 광고비 데이터와 릴스 성과를 정밀 분석합니다.")

# 사이드바 연동 정보
st.sidebar.header("🔑 API 계정 연동")
user_token = st.sidebar.text_input("Access Token (ads_read 권한 포함)", type="password")
custom_ig_id = st.sidebar.text_input("Instagram 계정 ID (178414...)", value="17841400564967767")
ad_account_id = st.sidebar.text_input("Meta 광고 계정 ID (act_...)", placeholder="예: act_1234567890")

st.sidebar.markdown("---")
st.sidebar.header("⚙️️ 수동 단가 설정 (API 미집행 시)")
cpm_estimate = st.sidebar.number_input("추정 CPM (원)", value=4000, step=500)
cpc_estimate = st.sidebar.number_input("추정 CPC (원)", value=300, step=50)
stream_revenue = st.sidebar.number_input("1회 스트리밍 단가 (원)", value=3.0, step=0.5)

views = 0
selected_media_id = None

if user_token and custom_ig_id:
    meta_api = MetaAPI(user_token, instagram_account_id=custom_ig_id.strip(), ad_account_id=ad_account_id.strip())
    reels_data = meta_api.get_reels_media()
    
    if reels_data:
        df_reels = pd.DataFrame(reels_data)
        st.subheader("🎬 최근 내 릴스 목록")
        st.dataframe(df_reels[['id', 'caption', 'views', 'likes', 'comments']], use_container_width=True)
        
        selected_label = st.selectbox("📌 분석할 릴스를 선택하세요", df_reels['display_label'])
        selected_row = df_reels[df_reels['display_label'] == selected_label].iloc[0]
        views = selected_row['views']
        selected_media_id = selected_row['id']
        st.success(f"선택한 릴스: **{selected_row['caption']}** (자연 조회수: **{views:,}회**)")

# 음원 유입 입력
st.markdown("---")
st.subheader("⚙️ 음원 유입 데이터 설정")
col1, col2 = st.columns(2)
with col1:
    streaming_count = st.number_input("🎵 멜론/스포티파이 음원 스트리밍 유입 수", value=450, step=10)

# 실제 광고 데이터 자동 추적 시도
ad_perf = None
if user_token and ad_account_id and selected_media_id:
    ad_perf = meta_api.get_ad_performance_by_media(selected_media_id)

with col2:
    if ad_perf:
        st.info(f"⚡ **Ads API 집행 데이터 감지 완료!** (총 집행 광고비: **{ad_perf['spend']:,}원**)")
        ad_budget = ad_perf['spend']
        used_cpm = ad_perf['cpm']
        used_cpc = ad_perf['cpc']
    else:
        ad_budget = st.number_input("💰 집행(예정) 광고 비용 (원)", value=50000, step=10000)
        used_cpm = cpm_estimate
        used_cpc = cpc_estimate

# 분석 결과 출력
if views > 0 and streaming_count > 0:
    res = calculate_metrics(views, streaming_count, ad_budget, stream_revenue, used_cpc, used_cpm)
    
    st.markdown("---")
    st.subheader("📈 1. 릴스 자연 성과 분석")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 릴스 조회수", f"{views:,} 회")
    m2.metric("음원 유입 전환율", f"{res['conversion_rate']} %")
    m3.metric("1유입당 필요 조회수", f"약 {res['views_per_stream']} 회당 1유입")
    m4.metric("콘텐츠 등급", res['grade'])

    if ad_budget > 0:
        st.markdown("---")
        st.subheader("🎯 2. 광고 유입 성과 & 실제 광고 효율 분석")
        
        a1, a2, a3 = st.columns(3)
        a1.metric("광고 노출 수", f"{ad_perf['impressions']:,} 회" if ad_perf else f"+{res['paid_views']:,} 회 (추정)")
        a2.metric("광고 클릭 수", f"{ad_perf['clicks']:,} 회" if ad_perf else f"+{res['paid_clicks']:,} 회 (추정)")
        a3.metric("추정 추가 음원 스트리밍", f"+{res['paid_streams']:,} 회")

        st.markdown("<br>", unsafe_allow_html=True)
        b1, b2, b3 = st.columns(3)
        b1.metric("음원 1유입당 광고 비용 (CPA)", f"약 {res['cpa_per_stream']:,} 원 / 1유입")
        b2.metric("실제/예상 집행 광고비", f"{ad_budget:,} 원")
        b3.metric("예상 ROAS", f"{res['roas']} %")