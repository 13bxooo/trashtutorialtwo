import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import streamlit.components.v1 as components


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="전국 고령화 지도",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# UI 스타일
# =========================================================

st.markdown(
    """
    <style>

    /* 전체 배경 */
    .stApp {
        background: #f5f7fb;
    }

    /* 기본 여백 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1450px;
    }

    /* 제목 */
    .main-title {
        font-size: 2.6rem;
        font-weight: 800;
        color: #172033;
        margin-bottom: 0.2rem;
        letter-spacing: -1.5px;
    }

    .subtitle {
        color: #718096;
        font-size: 1rem;
        margin-bottom: 1.8rem;
    }

    /* 카드 */
    .card {
        background: white;
        border-radius: 18px;
        padding: 22px 24px;
        box-shadow: 0 5px 22px rgba(30, 50, 80, 0.07);
        border: 1px solid #e8edf5;
        margin-bottom: 18px;
    }

    /* 섹션 제목 */
    .section-title {
        font-size: 1.25rem;
        font-weight: 750;
        color: #172033;
        margin-bottom: 4px;
    }

    .section-caption {
        color: #8a94a6;
        font-size: 0.9rem;
    }

    /* 통계 카드 */
    .stat-card {
        background: white;
        border-radius: 16px;
        padding: 18px 20px;
        border: 1px solid #e8edf5;
        box-shadow: 0 4px 18px rgba(30, 50, 80, 0.05);
    }

    .stat-label {
        color: #7c8799;
        font-size: 0.85rem;
        margin-bottom: 7px;
    }

    .stat-value {
        color: #1d4ed8;
        font-size: 1.55rem;
        font-weight: 800;
    }

    /* 버튼 */
    .stButton > button {
        border-radius: 10px;
        border: 1px solid #dbe4f0;
        background: white;
        color: #334155;
        font-weight: 600;
    }

    .stButton > button:hover {
        border-color: #2563eb;
        color: #2563eb;
        background: #f8fbff;
    }

    /* 데이터프레임 */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
    }

    /* 고양이 */
    .cat {
        position: fixed;
        bottom: 18px;
        right: 22px;
        font-size: 34px;
        z-index: 9999;
        animation: walk 12s linear infinite;
        pointer-events: none;
    }

    @keyframes walk {
        0% {
            transform: translateX(0) scaleX(1);
        }

        45% {
            transform: translateX(-180px) scaleX(1);
        }

        50% {
            transform: translateX(-180px) scaleX(-1);
        }

        95% {
            transform: translateX(0) scaleX(-1);
        }

        100% {
            transform: translateX(0) scaleX(1);
        }
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 고양이
# =========================================================

components.html(
    """
    <div class="cat">🐈</div>
    """,
    height=0
)


# =========================================================
# 제목
# =========================================================

st.markdown(
    '<div class="main-title">🗺️ 전국 고령화 지도</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    '대한민국 시군구와 읍·면·동별 65세 이상 인구 비율을 한눈에 확인해보세요.'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# 주소
# =========================================================

POP_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/population_yearly.csv.gz"
)

GEO_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/boundaries/sigungu_kr.geojson"
)

DONG_GEO_URL = (
    "https://raw.githubusercontent.com/vuski/admdongkor/master/"
    "ver20260701/HangJeongDong_ver20260701.geojson"
)


# =========================================================
# 데이터 로딩
# =========================================================

@st.cache_data(show_spinner="인구 데이터를 불러오는 중...")
def load_population():

    response = requests.get(
        POP_URL,
        timeout=60
    )

    response.raise_for_status()

    return pd.read_csv(
        POP_URL,
        dtype={"코드": str}
    )


@st.cache_data(show_spinner="전국 시군구 지도를 불러오는 중...")
def load_sigungu_geojson():

    response = requests.get(
        GEO_URL,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    for feature in data["features"]:

        code = feature["properties"].get("코드")

        if code is not None:

            feature["properties"]["지도코드"] = (
                str(code)
                .strip()
                .zfill(5)
            )

    return data


# ---------------------------------------------------------
# 중요:
# 33MB짜리 읍·면·동 GeoJSON은 여기서 바로 불러오지 않는다.
# 사용자가 시군구를 클릭했을 때만 실행한다.
# ---------------------------------------------------------

@st.cache_data(show_spinner="읍·면·동 지도를 불러오는 중... (처음 한 번만 걸릴 수 있어요)")
def load_dong_geojson():

    response = requests.get(
        DONG_GEO_URL,
        timeout=120
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# 데이터 준비
# =========================================================

df = load_population()

sigungu_geojson = load_sigungu_geojson()


latest_year = int(
    df["연도"].max()
)

df = df[
    df["연도"] == latest_year
].copy()


# =========================================================
# 코드 정리
# =========================================================

df["코드"] = (
    df["코드"]
    .astype(str)
    .str.strip()
    .str.zfill(10)
)

df["시군구코드"] = df["코드"].str[:5]


# =========================================================
# 나이 열
# =========================================================

total_cols = [
    c for c in df.columns
    if c.startswith("계_")
]


def age_of(column):

    match = re.match(
        r"계_(\d+)세",
        column
    )

    if match:
        return int(match.group(1))

    return None


elderly_cols = [
    c for c in total_cols
    if age_of(c) is not None
    and age_of(c) >= 65
]


# =========================================================
# 전체 / 고령 인구
# =========================================================

df["전체인구"] = (
    df[total_cols]
    .sum(axis=1)
)

df["고령인구"] = (
    df[elderly_cols]
    .sum(axis=1)
)


# =========================================================
# 시군구 데이터
# =========================================================

sigungu = (
    df
    .groupby("시군구코드")
    [["전체인구", "고령인구"]]
    .sum()
    .reset_index()
)

sigungu["고령화율"] = (
    sigungu["고령인구"]
    / sigungu["전체인구"]
    * 100
).round(2)


# =========================================================
# 시군구 이름
# =========================================================

names = pd.DataFrame(
    [
        {
            "시군구코드":
                feature["properties"]["지도코드"],

            "시군구":
                feature["properties"].get("시군구", ""),

            "시도":
                feature["properties"].get("시도", ""),
        }

        for feature
        in sigungu_geojson["features"]
    ]
)


sigungu = sigungu.merge(
    names,
    on="시군구코드",
    how="left"
)


# =========================================================
# 색상 단계
# =========================================================

BINS = [
    0,
    19,
    23,
    28,
    38,
    100
]

LABELS = [
    "19% 미만",
    "19~23%",
    "23~28%",
    "28~38%",
    "38% 이상"
]

COLORS = {
    "19% 미만": "#dbeafe",
    "19~23%": "#93c5fd",
    "23~28%": "#60a5fa",
    "28~38%": "#3b82f6",
    "38% 이상": "#1d4ed8"
}


sigungu["단계"] = pd.cut(
    sigungu["고령화율"],
    bins=BINS,
    labels=LABELS,
    right=False
)


# =========================================================
# 현재 선택 지역
# =========================================================

if "selected_sigungu" not in st.session_state:

    st.session_state.selected_sigungu = None


# =========================================================
# 선택된 지역이 없는 경우
# =========================================================

if st.session_state.selected_sigungu is None:

    # -----------------------------------------------------
    # 통계 카드
    # -----------------------------------------------------

    total_population = int(
        sigungu["전체인구"].sum()
    )

    elderly_population = int(
        sigungu["고령인구"].sum()
    )

    national_rate = round(
        elderly_population
        / total_population
        * 100,
        2
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-label">기준 연도</div>
                <div class="stat-value">{latest_year}년</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:

        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-label">전국 65세 이상 인구</div>
                <div class="stat-value">
                    {elderly_population:,}명
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c3:

        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-label">전국 고령화율</div>
                <div class="stat-value">
                    {national_rate:.2f}%
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.write("")

    # -----------------------------------------------------
    # 지도 카드
    # -----------------------------------------------------

    st.markdown(
        """
        <div class="card">
            <div class="section-title">
                📍 전국 시군구별 고령화율
            </div>
            <div class="section-caption">
                지도의 시군구를 클릭하면 해당 지역의
                읍·면·동 지도로 이동합니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


    # -----------------------------------------------------
    # 전국 지도
    # -----------------------------------------------------

    fig = px.choropleth(
        sigungu,

        geojson=sigungu_geojson,

        locations="시군구코드",

        featureidkey="properties.지도코드",

        color="단계",

        category_orders={
            "단계": LABELS
        },

        color_discrete_map=COLORS,

        hover_name="시군구",

        hover_data={
            "시도": True,
            "고령화율": True,
            "전체인구": True,
            "고령인구": True,
            "시군구코드": False,
            "단계": False
        },

        custom_data=[
            "시군구코드"
        ],

        labels={
            "고령화율": "고령화율 (%)",
            "전체인구": "전체 인구",
            "고령인구": "65세 이상 인구",
            "시도": "시도"
        }
    )


    fig.update_geos(
        fitbounds="locations",
        visible=False
    )


    fig.update_layout(
        height=700,

        margin=dict(
            l=0,
            r=0,
            t=10,
            b=0
        ),

        paper_bgcolor="white",

        plot_bgcolor="white",

        legend_title_text="65세 이상 비율"
    )


    # -----------------------------------------------------
    # 지도 클릭 이벤트
    # -----------------------------------------------------

    event = st.plotly_chart(
        fig,
        width="stretch",
        on_select="rerun",
        selection_mode="points",
        key="national_map"
    )


    # -----------------------------------------------------
    # 클릭된 시군구 확인
    # -----------------------------------------------------

    try:

        points = event.selection.points

        if points:

            code = points[0]["customdata"][0]

            st.session_state.selected_sigungu = code

            st.rerun()

    except Exception:

        pass


    # -----------------------------------------------------
    # 순위
    # -----------------------------------------------------

    st.write("")

    c1, c2 = st.columns(2)


    with c1:

        st.markdown(
            """
            <div class="card">
                <div class="section-title">
                    🔴 고령화율이 높은 지역
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        high = (
            sigungu
            .nlargest(
                10,
                "고령화율"
            )
            [
                [
                    "시도",
                    "시군구",
                    "고령화율"
                ]
            ]
            .reset_index(drop=True)
        )

        st.dataframe(
            high,
            width="stretch",
            hide_index=True
        )


    with c2:

        st.markdown(
            """
            <div class="card">
                <div class="section-title">
                    🟢 고령화율이 낮은 지역
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        low = (
            sigungu
            .nsmallest(
                10,
                "고령화율"
            )
            [
                [
                    "시도",
                    "시군구",
                    "고령화율"
                ]
            ]
            .reset_index(drop=True)
        )

        st.dataframe(
            low,
            width="stretch",
            hide_index=True
        )


# =========================================================
# 시군구 선택 상태
# =========================================================

else:

    selected_code = (
        st.session_state.selected_sigungu
    )


    selected_info = sigungu[
        sigungu["시군구코드"]
        == selected_code
    ]


    # -----------------------------------------------------
    # 지역이 존재하지 않는 경우
    # -----------------------------------------------------

    if selected_info.empty:

        st.session_state.selected_sigungu = None

        st.rerun()


    selected_info = selected_info.iloc[0]

    selected_name = selected_info["시군구"]

    selected_sido = selected_info["시도"]


    # -----------------------------------------------------
    # 돌아가기
    # -----------------------------------------------------

    if st.button(
        "← 전국 지도으로 돌아가기"
    ):

        st.session_state.selected_sigungu = None

        st.rerun()


    st.write("")


    # -----------------------------------------------------
    # 지역 제목
    # -----------------------------------------------------

    st.markdown(
        f"""
        <div class="main-title">
            📍 {selected_name}
        </div>

        <div class="subtitle">
            {selected_sido} · {latest_year}년 읍·면·동별 고령화율
        </div>
        """,
        unsafe_allow_html=True
    )


    # =====================================================
    # 33MB GeoJSON 로딩
    # =====================================================

    dong_geojson = load_dong_geojson()


    # =====================================================
    # 읍·면·동 데이터
    # =====================================================

    dong_df = df[
        df["시군구코드"]
        == selected_code
    ].copy()


    dong_df["고령화율"] = (
        dong_df["고령인구"]
        / dong_df["전체인구"]
        * 100
    ).round(2)


    # =====================================================
    # GeoJSON 코드 정리
    # =====================================================

    dong_features = []


    for feature in dong_geojson["features"]:

        properties = feature.get(
            "properties",
            {}
        )


        # admdongkor의 행정동 코드
        code = properties.get(
            "adm_cd2"
        )


        if code is None:

            code = properties.get(
                "adm_cd"
            )


        if code is None:

            continue


        code = (
            str(code)
            .strip()
            .zfill(10)
        )


        # 선택된 시군구에 해당하는 동만 남김
        if code[:5] != selected_code:

            continue


        feature["properties"]["지도코드"] = code

        dong_features.append(feature)


    # =====================================================
    # 선택된 시군구의 읍·면·동 GeoJSON
    # =====================================================

    selected_dong_geojson = {
        "type": "FeatureCollection",
        "features": dong_features
    }


    # =====================================================
    # 코드 기준으로 연결
    # =====================================================

    dong_map = dong_df[
        [
            "코드",
            "동",
            "전체인구",
            "고령인구",
            "고령화율"
        ]
    ].copy()


    dong_map["지도코드"] = (
        dong_map["코드"]
        .astype(str)
        .str.strip()
        .str.zfill(10)
    )


    # =====================================================
    # 통계 카드
    # =====================================================

    c1, c2, c3 = st.columns(3)


    with c1:

        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-label">지역</div>
                <div class="stat-value">
                    {selected_name}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


    with c2:

        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-label">65세 이상 인구</div>
                <div class="stat-value">
                    {int(selected_info["고령인구"]):,}명
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


    with c3:

        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-label">지역 고령화율</div>
                <div class="stat-value">
                    {selected_info["고령화율"]:.2f}%
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


    st.write("")


    # =====================================================
    # 읍·면·동 지도
    # =====================================================

    if len(dong_features) == 0:

        st.error(
            "해당 지역의 읍·면·동 경계를 찾지 못했습니다."
        )

    else:

        fig = px.choropleth(
            dong_map,

            geojson=selected_dong_geojson,

            locations="지도코드",

            featureidkey="properties.지도코드",

            color="고령화율",

            color_continuous_scale=[
                "#eff6ff",
                "#bfdbfe",
                "#60a5fa",
                "#2563eb",
                "#1e3a8a"
            ],

            hover_name="동",

            hover_data={
                "고령화율": True,
                "전체인구": True,
                "고령인구": True,
                "지도코드": False
            },

            labels={
                "고령화율": "고령화율 (%)",
                "전체인구": "전체 인구",
                "고령인구": "65세 이상 인구"
            }
        )


        fig.update_geos(
            fitbounds="locations",
            visible=False
        )


        fig.update_layout(
            height=650,

            margin=dict(
                l=0,
                r=0,
                t=10,
                b=0
            ),

            paper_bgcolor="white",

            plot_bgcolor="white",

            coloraxis_colorbar_title="고령화율 (%)"
        )


        st.plotly_chart(
            fig,
            width="stretch"
        )


    # =====================================================
    # 읍·면·동 표
    # =====================================================

    st.write("")

    st.markdown(
        """
        <div class="card">
            <div class="section-title">
                📊 읍·면·동별 고령화율
            </div>
            <div class="section-caption">
                65세 이상 인구 비율을 기준으로 정렬했습니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


    table = (
        dong_map
        [
            [
                "동",
                "전체인구",
                "고령인구",
                "고령화율"
            ]
        ]
        .sort_values(
            "고령화율",
            ascending=False
        )
        .reset_index(drop=True)
    )


    st.dataframe(
        table,
        width="stretch",
        hide_index=True
    )
