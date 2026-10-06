import os
import requests
import pandas as pd
import streamlit as st

# Streamlit Cloud Secrets 및 환경변수 안전 조회 함수
def get_secret(key_name, default_val=""):
    try:
        if hasattr(st, "secrets") and key_name in st.secrets:
            return st.secrets[key_name]
    except Exception:
        pass
    return os.getenv(key_name, default_val)

# ================= =====================
# 1. Streamlit 기본 페이지 및 스타일 설정
# ================= =====================
st.set_page_config(page_title="인스타그램 월별 광고 효율 & 릴스 분석기", layout="wide")

st.markdown("""
    <html lang="ko" class="notranslate">
    <head><meta name="google" content="notranslate" /></head>
""", unsafe_allow_html=True)

# ================= =====================
# 2. Meta 통합 API 클래스
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
                short_caption = raw_caption[:25] + '..' if len(raw_caption) > 25 else raw_caption
                media_id = str(item['id'])
                
                reels_list.append({
                    'id': media_id,
                    'short_caption': short_caption,
                    'display_label': f"[{media_id[-4:]}] {short_caption} | 조회수 {views_count:,}회",
                    'caption': raw_caption,
                    'views': int(views_count),
                    'reach': int(reach_count),
                    'likes': int(item.get('like_count', 0)),
                    'comments': int(item.get('comments_count', 0)),
                    'shares': int(item.get('shares', {}).get('count', 0)) if isinstance(item.get('shares'), dict) else 0
                })
        return reels_list

    def get_monthly_ad_performance(self):
        """월별 광고비 대비 유입량(클릭/노출/CPC 등) 자동 집계"""
        if not self.ad_account_id:
            return None

        url = f"{self.base_url}/{self.ad_account_id}/insights"
        params = {
            'level': 'account',
            'time_increment': 'monthly',
            'date_preset': 'maximum',
            'fields': 'date_start,date_stop,spend,impressions,clicks,cpm,cpc',
            'access_token': self.access_token
        }
        res = requests.get(url, params=params)
        
        if res.status_code != 200:
            st.error(f"❌ 광고 데이터 조회 실패: {res.json().get('error', {}).get('message', '')}")
            return None

        data = res.json().get('data', [])
        monthly_records = []
        
        for item in data:
            spend = float(item.get('spend', 0))
            clicks = int(item.get('clicks', 0))
            impressions = int(item.get('impressions', 0))
            month_label = item.get('date_start', '')[:7]
            
            if spend > 0:
                monthly_records.append({
                    '년월': month_label,
                    '광고비(원)': int(spend),
                    '유입량(클릭수)': clicks,
                    '노출수': impressions,
                    'CPC(원/클릭)': round(spend / clicks, 1) if clicks > 0 else 0,
                    'CPM(원/1천회)': round((spend / impressions * 1000), 1) if impressions > 0 else 0
                })

        return pd.DataFrame(monthly_records)

# ================= =====================
# 3. Streamlit UI 메인 화면
# ================= =====================
st.title("📊 월별 광고비 대비 유입량 & 릴스 성과 자동 분석기")

# 시크릿 및 환경변수 로드
env_token = get_secret("META_ACCESS_TOKEN", "")
env_ig_id = get_secret("INSTAGRAM_ACCOUNT_ID", "17841400564967767")
env_ad_id = get_secret("META_AD_ACCOUNT_ID", "")

# 사이드바 설정
st.sidebar.header("🔑 Meta 계정 연동")
user_token = st.sidebar.text_input("Access Token", value=env_token, type="password")
custom_ig_id = st.sidebar.text_input("Instagram 계정 ID", value=env_ig_id)
ad_account_id = st.sidebar.text_input("Meta 광고 계정 ID (act_...)", value=env_ad_id)

if user_token and custom_ig_id:
    meta_api = MetaAPI(user_token, instagram_account_id=custom_ig_id.strip(), ad_account_id=ad_account_id.strip())
    
    tab1, tab2 = st.tabs(["📅 월별 광고비 vs 유입량 분석", "🎬 개별 릴스 성과 분석"])

    # ----------------------------------
    # TAB 1: 월별 광고비 vs 유입량 분석
    # ----------------------------------
    with tab1:
        st.subheader("🗓️ 최근 월별 광고비 집행액 & 유입 성과 추이")
        if ad_account_id:
            df_monthly = meta_api.get_monthly_ad_performance()
            if df_monthly is not None and not df_monthly.empty:
                df_monthly = df_monthly.sort_values(by='년월', ascending=False).reset_index(drop=True)
                
                latest = df_monthly.iloc[0]
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("최근 월 (년-월)", latest['년월'])
                col2.metric("이번 달 광고 집행비", f"{latest['광고비(원)']:,} 원")
                col3.metric("이번 달 총 유입량", f"{latest['유입량(클릭수)']:,} 회")
                col4.metric("평균 클릭 단가 (CPC)", f"{latest['CPC(원/클릭)']} 원")

                st.markdown("---")
                st.write("📊 **월별 광고비 vs 유입량(클릭수) 시각화 차트**")
                
                df_chart = df_monthly.sort_values(by='년월', ascending=True).set_index('년월')
                
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.write("💰 **월별 광고 집행 비용 (원)**")
                    st.bar_chart(df_chart['광고비(원)'])
                with col_c2:
                    st.write("🎯 **월별 실제 유입량 (클릭수)**")
                    st.line_chart(df_chart['유입량(클릭수)'])

                st.markdown("---")
                st.write("📋 **월별 데이터 상세 테이블**")
                st.dataframe(df_monthly, use_container_width=True)
            else:
                st.info("해당 기간 동안 집행된 광고 데이터가 없습니다.")
        else:
            st.warning("사이드바에 Meta 광고 계정 ID (`act_...`)를 입력해 주세요.")

    # ----------------------------------
    # TAB 2: 개별 릴스 성과 분석
    # ----------------------------------
    with tab2:
        reels_data = meta_api.get_reels_media()
        if reels_data:
            df_reels = pd.DataFrame(reels_data)
            
            st.subheader("🎬 분석할 릴스를 선택하세요")
            
            reel_indices = list(range(len(reels_data)))
            
            selected_idx = st.selectbox(
                "📌 릴스 선택",
                options=reel_indices,
                format_func=lambda idx: reels_data[idx]['display_label'],
                key="selected_reel_index"
            )
            
            selected_reel = reels_data[selected_idx]
            
            views = selected_reel['views']
            likes = selected_reel['likes']
            comments = selected_reel['comments']
            shares = selected_reel['shares']
            caption = selected_reel['caption']

            total_engagement = likes + comments + shares
            engagement_rate = round((total_engagement / views * 100), 2) if views > 0 else 0

            st.markdown("---")
            st.success(f"📌 **선택한 릴스**: {caption}")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("총 조회수", f"{views:,} 회")
            col2.metric("좋아요 수", f"{likes:,} 개")
            col3.metric("공유 수 (음원 확산)", f"{shares:,} 회")
            col4.metric("인게이지먼트율 (참여율)", f"{engagement_rate} %")

            st.markdown("---")
            st.write("📈 **선택한 릴스 반응 분석 & 전체 비교**")
            
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.write("🎯 **인게이지먼트 구성 비율 (좋아요 / 댓글 / 공유)**")
                df_engagement = pd.DataFrame({
                    '반응 유형': ['좋아요', '댓글', '공유'],
                    '수량': [likes, comments, shares]
                }).set_index('반응 유형')
                st.bar_chart(df_engagement)

            with chart_col2:
                st.write("🏆 **전체 릴스 조회수 Top 10**")
                df_top_views = df_reels.sort_values(by='views', ascending=False).head(10)[['short_caption', 'views']].set_index('short_caption')
                st.bar_chart(df_top_views)

            st.markdown("---")
            st.write("📋 **전체 릴스 목록 및 요약 데이터**")
            st.dataframe(df_reels[['id', 'caption', 'views', 'likes', 'comments', 'shares']], use_container_width=True)
        else:
            st.info("등록된 릴스 데이터가 없습니다.")
else:
    st.info("👈 사이드바에 Access Token과 계정 ID를 입력해 주세요.")