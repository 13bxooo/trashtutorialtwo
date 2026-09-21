import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="전국 고령화 지도", layout="wide")

st.title("🗺️ 전국 고령화 지도")
st.caption("시군구별 65세 이상 인구 비율 (행정안전부 주민등록 인구)")

# =========================================================
# 데이터 주소
# =========================================================

POP_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/population_yearly.csv.gz"
)

# 전국 시군구 경계
GEO_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/boundaries/sigungu_kr.geojson"
)

# 전국 읍·면·동 경계
DONG_GEO_URL = (
    "https://raw.githubusercontent.com/vuski/admdongkor/master/"
    "ver20260701/HangJeongDong_ver20260701.geojson"
)


# =========================================================
# 데이터 불러오기
# =========================================================

@st.cache_data(show_spinner="인구 데이터를 불러오는 중입니다...")
def load_population():
    # 코드가 0으로 시작할 수 있으므로 문자열로 읽음
    return pd.read_csv(
        POP_URL,
        dtype={"코드": str}
    )


@st.cache_data(show_spinner="시군구 경계를 불러오는 중입니다...")
def load_geojson():
    response = requests.get(GEO_URL, timeout=30)
    response.raise_for_status()
    return response.json()


@st.cache_data(show_spinner="읍·면·동 경계를 불러오는 중입니다...")
def load_dong_geojson():
    response = requests.get(DONG_GEO_URL, timeout=30)
    response.raise_for_status()
    return response.json()


df = load_population()
geojson = load_geojson()
dong_geojson = load_dong_geojson()


# =========================================================
# 1. 가장 최신 연도만 사용
# =========================================================

latest_year = int(df["연도"].max())

df = df[
    df["연도"] == latest_year
].copy()


# =========================================================
# 2. 전체 인구 열 찾기
# =========================================================

total_cols = [
    c for c in df.columns
    if c.startswith("계_")
]


def age_of(col):
    m = re.match(r"계_(\d+)세", col)

    if m:
        return int(m.group(1))

    return None


# =========================================================
# 3. 65세 이상 인구 열 찾기
# =========================================================

elderly_cols = [
    c for c in total_cols
    if age_of(c) is not None
    and age_of(c) >= 65
]


# =========================================================
# 4. 읍·면·동별 전체 인구 / 고령 인구 계산
# =========================================================

df["전체인구"] = df[total_cols].sum(axis=1)

df["고령인구"] = df[elderly_cols].sum(axis=1)


# =========================================================
# 5. 코드 앞 5자리 → 시군구 코드
# =========================================================

df["코드"] = (
    df["코드"]
    .astype(str)
    .str.strip()
    .str.zfill(10)
)

df["시군구코드"] = df["코드"].str[:5]


# =========================================================
# 6. 시군구별 고령화율 계산
# =========================================================

grouped = (
    df.groupby("시군구코드")[
        ["전체인구", "고령인구"]
    ]
    .sum()
    .reset_index()
)

grouped["고령화율"] = (
    grouped["고령인구"]
    / grouped["전체인구"]
    * 100
).round(2)


# =========================================================
# 7. 시군구 GeoJSON에 이름 붙이기
# =========================================================

names = pd.DataFrame([
    {
        "시군구코드": str(
            feature["properties"]["코드"]
        ).strip().zfill(5),

        "시군구": feature["properties"]["시군구"],

        "시도": feature["properties"]["시도"],
    }

    for feature in geojson["features"]
])


merged = grouped.merge(
    names,
    on="시군구코드",
    how="left"
)


# =========================================================
# 8. 5단계 색 구간
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
    "19% 미만": "#fee6ce",
    "19~23%": "#fdc086",
    "23~28%": "#f79646",
    "28~38%": "#e8590c",
    "38% 이상": "#a63603",
}

merged["단계"] = pd.cut(
    merged["고령화율"],
    bins=BINS,
    labels=LABELS,
    right=False
)


# =========================================================
# 9. 전국 시군구 지도
# =========================================================

st.subheader(f"📍 {latest_year}년 전국 시군구별 고령화율")

fig = px.choropleth(
    merged,
    geojson=geojson,
    locations="시군구코드",
    featureidkey="properties.코드",

    color="단계",

    category_orders={
        "단계": LABELS
    },

    color_discrete_map=COLORS,

    hover_name="시군구",

    hover_data={
        "고령화율": True,
        "시도": True,
        "시군구코드": False,
        "단계": False,
    },

    labels={
        "고령화율": "65세 이상 비율(%)"
    },
)

fig.update_geos(
    fitbounds="locations",
    visible=False
)

fig.update_layout(
    margin=dict(
        l=0,
        r=0,
        t=10,
        b=0
    ),

    height=700,

    legend_title_text=(
        f"65세 이상 비율 ({latest_year}년)"
    ),
)

st.plotly_chart(
    fig,
    width="stretch"
)


# =========================================================
# 10. 시군구 순위
# =========================================================

c1, c2 = st.columns(2)

cols = [
    "시도",
    "시군구",
    "고령화율"
]


with c1:

    st.subheader("🔴 고령화율 높은 곳 10")

    st.dataframe(
        merged
        .nlargest(
            10,
            "고령화율"
        )[cols]
        .reset_index(drop=True)
    )


with c2:

    st.subheader("🟢 고령화율 낮은 곳 10")

    st.dataframe(
        merged
        .nsmallest(
            10,
            "고령화율"
        )[cols]
        .reset_index(drop=True)
    )


# =========================================================
# 11. 읍·면·동 GeoJSON 확인
# =========================================================

st.divider()

st.subheader("🧭 읍·면·동 경계 데이터")

st.write(
    f"읍·면·동 경계 {len(dong_geojson['features']):,}개를 "
    "불러왔습니다."
)
