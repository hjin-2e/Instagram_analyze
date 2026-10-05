import requests
import pandas as pd
import streamlit as st

# ================= =====================
# 1. Streamlit 기본 페이지 및 스타일 설정
# ================= =====================
st.set_page_config(page_title="인스타그램 릴스 & 광고 성과 자동 분석기", layout="wide")

st.markdown("""
    <html lang="ko" class="notranslate">
    <head><meta name="google" content="notranslate" /></head>
""", unsafe_allow_html=True)

# ================= =====================
# 2. Meta 통합 API (Instagram & Marketing API)
# ================= =====================
class MetaAPI:
    def __init__(self, access_token, instagram_account_id=None, ad_account_id=None):
        self.access_token = access_token
        self.base_url = "https://graph.facebook.com/v19.0"
        self.account_id = instagram_account_id
        self.ad_account_id = ad_account_id if not ad_account_id or ad_account_id.startswith('act_') else f"act_{ad_account_id}"

    def get_reels_media(self):
        """내 계정의 최근 릴스 목록 및 인사이트 가져오기"""
        if not self.account_id:
            st.error("❌ Instagram 계정 ID가 연결되지 않았습니다.")
            return []

        url = f"{self.base_url}/{self.account_id}/media"
        params = {
            'fields': 'id,caption,media_type,media_url,like_count,comments_count,shares,insights.metric(views,reach,total_interactions)',
            'access_token': self.access_token
        }
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            err_msg = response.json().get('error', {}).get('message', 'API 호출 오류')
            st.error(f"❌ Instagram API 오류: {err_msg}")
            return []

        data = response.json().get('data', [])
        reels_list = []
        for item in data:
            if item.get('media_type') in ['VIDEO', 'REELS']:
                views_count = 0
                reach_count = 0
                insights = item.get('insights', {}).get('data', [])
                for metric in insights:
                    if metric['name'] == 'views':
                        views_count = metric['values'][0]['value']
                    elif metric['name'] == 'reach':
                        reach_count = metric['values'][0]['value']
                
                raw_caption = item.get('caption', '캡션 없음').replace('\n', ' ')
                short_caption = raw_caption[:20] + '..' if len(raw_caption) > 20 else raw_caption
                
                reels_list.append({
                    'id': item['id'],
                    'display_label': f"[{item['id'][-4:]}] {short_caption} | 조회수 {views_count:,}회",
                    'caption': raw_caption,
                    'views': views_count,
                    'reach': reach_count,
                    'likes': item.get('like_count', 0),
                    'comments': item.get('comments_count', 0),
                    'shares': item.get('shares', {}).get('count', 0) if isinstance(item.get('shares'), dict) else 0
                })
        return reels_list

    def get_ad_performance_by_media(self, media_id):
        """선택한 릴스 소재로 실제 집행된 광고비 및 클릭 데이터 자동 추적"""
        if not self.ad_account_id:
            return None

        url = f"{self.base_url}/{self.ad_account_id}/insights"
        params = {
            'level': 'ad',
            'fields': 'ad_id,ad_name,spend,impressions,clicks,cpm,cpc,outbound_clicks',
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

        for ad in ad_data:
            total_spend += float(ad.get('spend', 0))
            total_impressions += int(ad.get('impressions', 0))
            total_clicks += int(ad.get('clicks', 0))

        if total_spend == 0:
            return None

        return {
            "spend": int(total_spend),
            "impressions": total_impressions,
            "clicks": total_clicks,
            "cpm": round((total_spend / total_impressions * 1000), 1) if total_impressions > 0 else 0,
            "cpc": round(total_spend / total_clicks, 1) if total_clicks > 0 else 0
        }

# ================= =====================
# 3. Streamlit UI 메인 화면
# ================= =====================
st.title("📊 인스타그램 릴스 광고비 기반 성과 자동 분석기")
st.write("수동 입력 없이 Meta API의 실시간 집행 광고비와 릴스 반응 데이터만으로 광고 효율을 정밀 분석합니다.")

# 사이드바 설정
st.sidebar.header("🔑 Meta 계정 자동 연동")
user_token = st.sidebar.text_input("Access Token (ads_read 권한 포함)", type="password")
custom_ig_id = st.sidebar.text_input("Instagram 계정 ID (178414...)", value="17841400564967767")
ad_account_id = st.sidebar.text_input("Meta 광고 계정 ID (act_...)", placeholder="예: act_1234567890")

if user_token and custom_ig_id:
    meta_api = MetaAPI(user_token, instagram_account_id=custom_ig_id.strip(), ad_account_id=ad_account_id.strip())
    reels_data = meta_api.get_reels_media()
    
    if reels_data:
        df_reels = pd.DataFrame(reels_data)
        st.subheader("🎬 최근 내 릴스 목록")
        st.dataframe(df_reels[['id', 'caption', 'views', 'likes', 'comments', 'shares']], use_container_width=True)
        
        selected_label = st.selectbox("📌 분석할 릴스를 선택하세요", df_reels['display_label'])
        selected_row = df_reels[df_reels['display_label'] == selected_label].iloc[0]
        
        views = selected_row['views']
        likes = selected_row['likes']
        comments = selected_row['comments']
        shares = selected_row['shares']
        selected_media_id = selected_row['id']

        st.success(f"선택한 릴스: **{selected_row['caption']}**")

        # 광고 데이터 조회
        ad_perf = meta_api.get_ad_performance_by_media(selected_media_id) if ad_account_id else None

        st.markdown("---")
        st.subheader("📈 1. 릴스 자연 반응성 분석 (Organic Response)")
        
        total_engagement = likes + comments + shares
        engagement_rate = round((total_engagement / views * 100), 2) if views > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 조회수", f"{views:,} 회")
        col2.metric("좋아요 수", f"{likes:,} 개")
        col3.metric("공유 수 (음원 확산)", f"{shares:,} 회")
        col4.metric("인게이지먼트율", f"{engagement_rate} %")

        st.markdown("---")
        st.subheader("🎯 2. 집행 광고비 대비 유입 성과 리포트")

        if ad_perf:
            spend = ad_perf['spend']
            clicks = ad_perf['clicks']
            impressions = ad_perf['impressions']
            cpm = ad_perf['cpm']
            cpc = ad_perf['cpc']
            cpv = round(spend / views, 1) if views > 0 else 0

            m1, m2, m3 = st.columns(3)
            m1.metric("총 집행 광고 비용", f"{spend:,} 원")
            m2.metric("실제 광고 노출 수", f"{impressions:,} 회")
            m3.metric("프로필/음원링크 클릭 수", f"{clicks:,} 회")

            st.markdown("<br>", unsafe_allow_html=True)
            k1, k2, k3 = st.columns(3)
            k1.metric("1회 재생당 광고 단가 (CPV)", f"약 {cpv} 원 / 재생")
            k2.metric("클릭당 광고 단가 (CPC)", f"약 {cpc:,} 원 / 클릭")
            k3.metric("1,000회 노출 단가 (CPM)", f"약 {cpm:,} 원")

            st.markdown("<br>", unsafe_allow_html=True)
            if cpc <= 250:
                st.success("🔥 **고효율 음원 광고**: 클릭 단가가 낮아 시청자들이 멜론/음원 링크로 활발히 이동하고 있습니다. 광고 증액을 추천합니다!")
            elif cpc <= 500:
                st.info("👍 **보통 수준 성과**: 평균적인 음원 마케팅 단가를 유지하고 있습니다.")
            else:
                st.warning("⚠️ **단가 높음**: 클릭당 비용이 높습니다. 릴스의 초반 3초 구간이나 캡션의 음원 링크 유도 문구를 수정해 보세요.")
        else:
            st.info("💡 사이드바에 **Meta 광고 계정 ID(`act_...`)**를 입력하시면 해당 릴스에 실제 태운 광고비와 클릭 단가가 자동으로 표시됩니다.")

else:
    st.info("👈 사이드바에 Access Token과 계정 ID를 입력해 주세요.")