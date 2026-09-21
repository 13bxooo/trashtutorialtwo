import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
from io import BytesIO
import copy


# ============================================================
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="전국 시군구별 고령화 지도",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ 전국 시군구별 고령화 지도")
st.caption(
    "65세 이상 인구 비율을 기준으로 전국 시군구의 고령화 정도를 나타낸 지도입니다."
)


# ============================================================
# 데이터 주소
# ============================================================

POPULATION_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/population_yearly.csv.gz"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/boundaries/sigungu_kr.geojson"
)


# ============================================================
# 인구 데이터 불러오기
# ============================================================

@st.cache_data(show_spinner=False)
def load_population_data():
    """
    전국 읍·면·동 인구 데이터를 불러옵니다.

    '코드'는 계산용 숫자가 아니라 행정구역을 구분하는 코드이므로
    문자열로 읽습니다.
    """

    response = requests.get(
        POPULATION_URL,
        timeout=60
    )

    response.raise_for_status()

    population = pd.read_csv(
        BytesIO(response.content),
        compression="gzip",
        dtype={"코드": "string"},
    )

    return population


# ============================================================
# 지도 경계 데이터 불러오기
# ============================================================

@st.cache_data(show_spinner=False)
def load_geojson():
    """
    전국 시군구 경계 GeoJSON을 불러옵니다.

    지도와 인구 데이터를 연결할 때 코드가 정확하게 일치하도록
    GeoJSON의 '코드'도 문자열 5자리로 통일합니다.
    """

    response = requests.get(
        GEOJSON_URL,
        timeout=60
    )

    response.raise_for_status()

    geojson = response.json()

    # 원본 데이터를 직접 수정하지 않도록 복사합니다.
    geojson = copy.deepcopy(geojson)

    for feature in geojson["features"]:

        properties = feature.get("properties", {})

        # 코드가 숫자로 되어 있어도 문자열로 바꿉니다.
        code = properties.get("코드", "")

        code = str(code).strip()

        # 혹시 11110.0처럼 읽힌 경우를 처리합니다.
        if code.endswith(".0"):
            code = code[:-2]

        # 앞 5자리만 시군구 코드로 사용합니다.
        properties["코드"] = code.zfill(5)[:5]

        feature["properties"] = properties

    return geojson


# ============================================================
# 고령화율 계산
# ============================================================

def calculate_aging_rate(population):
    """
    가장 최신 연도의 읍·면·동 자료를 이용하여
    시군구별 65세 이상 인구 비율을 계산합니다.
    """

    df = population.copy()

    # 연도를 숫자로 변환합니다.
    df["연도_숫자"] = pd.to_numeric(
        df["연도"],
        errors="coerce"
    )

    # 가장 최신 연도를 찾습니다.
    latest_year = int(
        df["연도_숫자"].max()
    )

    # 최신 연도만 사용합니다.
    df = df[
        df["연도_숫자"] == latest_year
    ].copy()

    # --------------------------------------------------------
    # 행정동 코드 처리
    # --------------------------------------------------------

    # 반드시 문자열로 처리합니다.
    df["코드"] = (
        df["코드"]
        .astype("string")
        .str.strip()
    )

    # 코드 앞 5자리가 시군구 코드입니다.
    df["시군구코드"] = (
        df["코드"]
        .str[:5]
        .str.zfill(5)
    )

    # --------------------------------------------------------
    # 65세 이상 인구 열 찾기
    # --------------------------------------------------------

    elderly_columns = []

    for age in range(65, 100):

        column = f"계_{age}세"

        if column in df.columns:
            elderly_columns.append(column)

    # 100세 이상도 포함합니다.
    if "계_100세 이상" in df.columns:
        elderly_columns.append("계_100세 이상")

    if not elderly_columns:
        raise ValueError(
            "65세 이상 인구 열을 찾지 못했습니다."
        )

    # --------------------------------------------------------
    # 전체 인구 열 찾기
    # --------------------------------------------------------

    total_columns = []

    for age in range(0, 100):

        column = f"계_{age}세"

        if column in df.columns:
            total_columns.append(column)

    if "계_100세 이상" in df.columns:
        total_columns.append("계_100세 이상")

    if not total_columns:
        raise ValueError(
            "전체 연령 인구 열을 찾지 못했습니다."
        )

    # --------------------------------------------------------
    # 인구 열을 숫자로 변환
    # --------------------------------------------------------

    df[elderly_columns] = (
        df[elderly_columns]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    df[total_columns] = (
        df[total_columns]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    # --------------------------------------------------------
    # 읍·면·동별 인구 계산
    # --------------------------------------------------------

    df["65세이상인구"] = (
        df[elderly_columns]
        .sum(axis=1)
    )

    df["전체인구"] = (
        df[total_columns]
        .sum(axis=1)
    )

    # --------------------------------------------------------
    # 시군구별로 합산
    # --------------------------------------------------------

    result = (
        df.groupby(
            "시군구코드",
            as_index=False
        )[
            ["65세이상인구", "전체인구"]
        ]
        .sum()
    )

    # --------------------------------------------------------
    # 고령화율 계산
    # --------------------------------------------------------

    result["고령화율"] = np.where(
        result["전체인구"] > 0,
        result["65세이상인구"]
        / result["전체인구"]
        * 100,
        np.nan
    )

    result["고령화율"] = (
        result["고령화율"]
        .round(2)
    )

    return result, latest_year


# ============================================================
# 지도용 데이터 만들기
# ============================================================

def make_map_dataframe(aging_df, geojson):
    """
    GeoJSON의 시군구 코드와 인구 데이터의 시군구 코드를
    코드 기준으로 연결합니다.
    """

    boundary_rows = []

    for feature in geojson["features"]:

        properties = feature.get(
            "properties",
            {}
        )

        code = str(
            properties.get("코드", "")
        ).strip()

        if code.endswith(".0"):
            code = code[:-2]

        code = code.zfill(5)[:5]

        boundary_rows.append(
            {
                "시군구코드": code,
                "시군구": properties.get(
                    "시군구",
                    "정보 없음"
                ),
                "시도": properties.get(
                    "시도",
                    "정보 없음"
                ),
            }
        )

    boundary_df = pd.DataFrame(
        boundary_rows
    )

    boundary_df = (
        boundary_df
        .drop_duplicates(
            subset=["시군구코드"]
        )
    )

    # ★ 이름이 아니라 코드로 연결합니다.
    map_df = boundary_df.merge(
        aging_df,
        on="시군구코드",
        how="left"
    )

    return map_df


# ============================================================
# 단계구분 구간 만들기
# ============================================================

def make_category(value):

    if pd.isna(value):
        return "자료 없음"

    if value < 19:
        return "19% 미만"

    elif value < 23:
        return "19% 이상 ~ 23% 미만"

    elif value < 28:
        return "23% 이상 ~ 28% 미만"

    elif value < 38:
        return "28% 이상 ~ 38% 미만"

    else:
        return "38% 이상"


# ============================================================
# 프로그램 실행
# ============================================================

try:

    with st.spinner(
        "인구 및 지도 데이터를 불러오는 중입니다..."
    ):

        population_df = (
            load_population_data()
        )

        geojson = (
            load_geojson()
        )

        aging_df, latest_year = (
            calculate_aging_rate(
                population_df
            )
        )

        map_df = (
            make_map_dataframe(
                aging_df,
                geojson
            )
        )


    # ========================================================
    # 단계구분
    # ========================================================

    map_df["구간"] = (
        map_df["고령화율"]
        .apply(make_category)
    )


    category_order = [
        "19% 미만",
        "19% 이상 ~ 23% 미만",
        "23% 이상 ~ 28% 미만",
        "28% 이상 ~ 38% 미만",
        "38% 이상",
        "자료 없음",
    ]


    # ========================================================
    # 지도
    # ========================================================

    st.subheader(
        f"{latest_year}년 전국 시군구별 고령화율"
    )


    # 단계별 색상
    color_map = {

        "19% 미만":
            "#E8F3FA",

        "19% 이상 ~ 23% 미만":
            "#B9DDF0",

        "23% 이상 ~ 28% 미만":
            "#78B9D9",

        "28% 이상 ~ 38% 미만":
            "#367FAF",

        "38% 이상":
            "#124B78",

        "자료 없음":
            "#D9D9D9",
    }


    # ========================================================
    # 중요:
    # Mapbox를 사용하지 않고 일반 GeoJSON 지도를 사용합니다.
    # 따라서 배경 지도 타일이나 Mapbox 토큰이 필요하지 않습니다.
    # ========================================================

    fig = px.choropleth(

        map_df,

        geojson=geojson,

        locations="시군구코드",

        featureidkey="properties.코드",

        color="구간",

        category_orders={
            "구간": category_order
        },

        color_discrete_map=color_map,

        hover_name="시군구",

        hover_data={
            "시도": True,
            "고령화율": ":.2f",
            "시군구코드": False,
            "구간": False,
        },

        labels={
            "시도": "시도",
            "고령화율": "고령화율(%)",
        },

    )


    # ========================================================
    # 지도 모양 설정
    # ========================================================

    fig.update_geos(

        # 대한민국 전체 경계에 맞춰 자동 확대
        fitbounds="locations",

        # 배경 지도 없음
        visible=False,

        # 지도 바깥 배경
        showland=True,
        landcolor="white",

        # 바다
        showocean=True,
        oceancolor="white",

        # 주변 지역
        showcountries=False,

        # 경계선
        showlakes=False,

        projection_type="mercator",
    )


    # 시군구 경계선
    fig.update_traces(

        marker_line_color="#777777",

        marker_line_width=0.5,

    )


    fig.update_layout(

        height=720,

        margin=dict(
            l=0,
            r=0,
            t=0,
            b=0,
        ),

        legend_title_text="고령화율 구간",

        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.01,
        ),

    )


    # 지도 표시
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False
        },
    )


    # ========================================================
    # 데이터 확인용 안내
    # ========================================================

    valid_df = (
        map_df
        .dropna(
            subset=["고령화율"]
        )
        .copy()
    )


    # ========================================================
    # 고령화율 높은 지역 10곳
    # ========================================================

    high_df = (
        valid_df
        .sort_values(
            "고령화율",
            ascending=False
        )
        .head(10)
        [
            [
                "시도",
                "시군구",
                "고령화율"
            ]
        ]
        .reset_index(drop=True)
    )


    high_df["고령화율"] = (
        high_df["고령화율"]
        .round(2)
    )


    # ========================================================
    # 고령화율 낮은 지역 10곳
    # ========================================================

    low_df = (
        valid_df
        .sort_values(
            "고령화율",
            ascending=True
        )
        .head(10)
        [
            [
                "시도",
                "시군구",
                "고령화율"
            ]
        ]
        .reset_index(drop=True)
    )


    low_df["고령화율"] = (
        low_df["고령화율"]
        .round(2)
    )


    # ========================================================
    # 표를 나란히 표시
    # ========================================================

    col1, col2 = st.columns(2)


    with col1:

        st.subheader(
            "고령화율 높은 지역 10곳"
        )

        st.dataframe(
            high_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "시도": "시도",
                "시군구": "시군구",
                "고령화율": st.column_config.NumberColumn(
                    "고령화율(%)",
                    format="%.2f"
                ),
            },
        )


    with col2:

        st.subheader(
            "고령화율 낮은 지역 10곳"
        )

        st.dataframe(
            low_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "시도": "시도",
                "시군구": "시군구",
                "고령화율": st.column_config.NumberColumn(
                    "고령화율(%)",
                    format="%.2f"
                ),
            },
        )


# ============================================================
# 오류가 발생했을 때
# ============================================================

except Exception as error:

    st.error(
        "데이터를 불러오거나 지도를 만드는 중 오류가 발생했습니다."
    )

    st.exception(error)
