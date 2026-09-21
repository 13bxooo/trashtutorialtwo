import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json


# ============================================================
# 1. 기본 설정
# ============================================================

st.set_page_config(
    page_title="전국 고령화 지도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시군구별 고령화 지도")
st.write("65세 이상 인구 비율을 기준으로 전국 시군구의 고령화 정도를 나타낸 지도입니다.")


# ============================================================
# 2. 데이터 주소
# ============================================================

POPULATION_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/"
    "main/data/population_yearly.csv.gz"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/"
    "main/data/boundaries/sigungu_kr.geojson"
)


# ============================================================
# 3. 데이터 불러오기
# ============================================================

@st.cache_data
def load_population_data():
    """읍·면·동별 인구 데이터를 불러옵니다."""

    # 코드는 계산용 숫자가 아니라 행정구역을 구분하는 이름표이므로
    # 반드시 문자열로 읽습니다.
    response = requests.get(POPULATION_URL, timeout=60)
    response.raise_for_status()

    from io import BytesIO

    df = pd.read_csv(
        BytesIO(response.content),
        compression="gzip",
        dtype={"코드": str}
    )

    # 코드가 혹시 숫자처럼 변환된 경우에도 문자열로 통일합니다.
    df["코드"] = df["코드"].astype(str).str.strip().str.zfill(8)

    return df


@st.cache_data
def load_boundary_data():
    """전국 시군구 경계 GeoJSON을 불러옵니다."""

    response = requests.get(GEOJSON_URL, timeout=60)
    response.raise_for_status()

    return response.json()


# ============================================================
# 4. 시군구별 고령화율 계산
# ============================================================

@st.cache_data
def calculate_aging_rate(df):
    """
    가장 최신 연도의 읍·면·동 인구를 이용해
    시군구별 65세 이상 인구 비율을 계산합니다.
    """

    # 연도 열을 숫자로 변환합니다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")

    # 가장 최신 연도를 선택합니다.
    latest_year = int(df["연도"].max())
    latest_df = df[df["연도"] == latest_year].copy()

    # 65세 이상 나이 열을 찾습니다.
    # '계_65세'부터 '계_100세 이상'까지 사용합니다.
    age_columns = []

    for age in range(65, 101):
        if age == 100:
            column_name = "계_100세 이상"
        else:
            column_name = f"계_{age}세"

        if column_name in latest_df.columns:
            age_columns.append(column_name)

    if not age_columns:
        raise ValueError("65세 이상 인구 열을 찾을 수 없습니다.")

    # 전체 인구 열을 찾습니다.
    # '계_0세'부터 '계_100세 이상'까지 합산합니다.
    total_age_columns = []

    for age in range(0, 101):
        if age == 100:
            column_name = "계_100세 이상"
        else:
            column_name = f"계_{age}세"

        if column_name in latest_df.columns:
            total_age_columns.append(column_name)

    # 인구 열의 결측값을 0으로 바꿉니다.
    latest_df[age_columns] = latest_df[age_columns].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0)

    latest_df[total_age_columns] = latest_df[total_age_columns].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0)

    # 읍·면·동 코드의 앞 5자리가 시군구 코드입니다.
    latest_df["시군구코드"] = latest_df["코드"].str[:5]

    # 시군구별로 65세 이상 인구와 전체 인구를 합산합니다.
    latest_df["고령인구"] = latest_df[age_columns].sum(axis=1)
    latest_df["전체인구"] = latest_df[total_age_columns].sum(axis=1)

    result = (
        latest_df
        .groupby("시군구코드", as_index=False)
        .agg(
            고령인구=("고령인구", "sum"),
            전체인구=("전체인구", "sum")
        )
    )

    # 고령화율 = 65세 이상 인구 / 전체 인구 × 100
    result["고령화율"] = (
        result["고령인구"] / result["전체인구"] * 100
    )

    result["고령화율"] = result["고령화율"].round(2)

    return latest_year, result


# ============================================================
# 5. GeoJSON 속성에 시군구 코드를 연결
# ============================================================

@st.cache_data
def prepare_geojson(geojson, aging_df):
    """
    경계 데이터의 시군구 코드와
    계산한 고령화율을 연결합니다.
    """

    # 원본 GeoJSON을 직접 변경하지 않도록 복사합니다.
    geojson_copy = json.loads(json.dumps(geojson))

    # 시군구별 고령화율을 딕셔너리로 만듭니다.
    aging_dict = dict(
        zip(aging_df["시군구코드"], aging_df["고령화율"])
    )

    for feature in geojson_copy["features"]:
        properties = feature["properties"]

        # 경계 데이터의 코드도 문자열로 처리합니다.
        code = str(properties["코드"]).strip().zfill(5)

        # 지도에서 사용할 고령화율을 추가합니다.
        properties["고령화율"] = aging_dict.get(code, None)

    return geojson_copy


# ============================================================
# 6. 실행 및 오류 처리
# ============================================================

try:
    with st.spinner("인구 데이터와 지도 경계를 불러오는 중입니다..."):

        population_df = load_population_data()
        geojson_data = load_boundary_data()

        latest_year, aging_df = calculate_aging_rate(population_df)

        # GeoJSON의 시군구 코드와 계산 결과를 연결합니다.
        map_geojson = prepare_geojson(geojson_data, aging_df)

except Exception as e:
    st.error("데이터를 불러오거나 계산하는 중 오류가 발생했습니다.")
    st.exception(e)
    st.stop()


# ============================================================
# 7. 시군구 이름과 시도 정보를 데이터에 연결
# ============================================================

# GeoJSON의 지역 정보를 표와 지도에 사용하기 위해 추출합니다.
boundary_info = []

for feature in geojson_data["features"]:
    properties = feature["properties"]

    boundary_info.append({
        "시군구코드": str(properties["코드"]).strip().zfill(5),
        "시군구": properties["시군구"],
        "시도": properties["시도"]
    })

boundary_df = pd.DataFrame(boundary_info)

# 코드로만 결합합니다.
# '남구'처럼 이름이 중복되는 지역도 정확하게 구분할 수 있습니다.
aging_df = aging_df.merge(
    boundary_df,
    on="시군구코드",
    how="left"
)

# 지도에 표시할 데이터가 없는 지역은 제외합니다.
map_df = aging_df.dropna(subset=["고령화율"]).copy()


# ============================================================
# 8. 지도 그리기
# ============================================================

st.subheader(f"{latest_year}년 전국 시군구별 고령화율")

# 고령화율을 5단계로 구분합니다.
# 구간 경계: 19%, 23%, 28%, 38%
# 낮은 값부터 옅은 색, 높은 값부터 진한 색을 사용합니다.
color_scale = [
    "#edf8fb",
    "#b2e2e2",
    "#66c2a4",
    "#238b8d",
    "#005824"
]

# 지도에 사용할 단계 이름을 만듭니다.
def classify_aging_rate(value):
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


map_df["고령화율구간"] = map_df["고령화율"].apply(
    classify_aging_rate
)

# 범례에 표시할 순서를 고정합니다.
category_order = [
    "19% 미만",
    "19% 이상 ~ 23% 미만",
    "23% 이상 ~ 28% 미만",
    "28% 이상 ~ 38% 미만",
    "38% 이상"
]

map_df["고령화율구간"] = pd.Categorical(
    map_df["고령화율구간"],
    categories=category_order,
    ordered=True
)

fig = px.choropleth(
    map_df,
    geojson=map_geojson,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="고령화율구간",
    color_discrete_map={
        "19% 미만": color_scale[0],
        "19% 이상 ~ 23% 미만": color_scale[1],
        "23% 이상 ~ 28% 미만": color_scale[2],
        "28% 이상 ~ 38% 미만": color_scale[3],
        "38% 이상": color_scale[4]
    },
    category_orders={
        "고령화율구간": category_order
    },
    custom_data=["시군구", "시도", "고령화율"],
    labels={
        "고령화율구간": "고령화율 구간"
    }
)

# 마우스를 올렸을 때 표시할 정보입니다.
fig.update_traces(
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "시도: %{customdata[1]}<br>"
        "고령화율: %{customdata[2]:.2f}%"
        "<extra></extra>"
    ),
    marker_line_color="white",
    marker_line_width=0.5
)

# 배경 지도 타일 없이 행정구역 경계만 표시합니다.
fig.update_geos(
    fitbounds="locations",
    visible=False,
    showland=False,
    showcountries=False,
    showcoastlines=False,
    showframe=False
)

fig.update_layout(
    height=750,
    margin=dict(l=0, r=0, t=20, b=0),
    legend_title_text="고령화율 구간",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.08,
        xanchor="center",
        x=0.5
    )
)

st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 9. 고령화율 높은 지역과 낮은 지역
# ============================================================

st.subheader("📊 고령화율 순위")

# 표에 표시할 열만 선택합니다.
table_columns = ["시도", "시군구", "고령화율"]

high_df = (
    map_df
    .sort_values("고령화율", ascending=False)
    .head(10)
    [table_columns]
    .reset_index(drop=True)
)

low_df = (
    map_df
    .sort_values("고령화율", ascending=True)
    .head(10)
    [table_columns]
    .reset_index(drop=True)
)

high_df.index = high_df.index + 1
low_df.index = low_df.index + 1

high_df = high_df.rename(columns={"고령화율": "고령화율(%)"})
low_df = low_df.rename(columns={"고령화율": "고령화율(%)"})

high_df["고령화율(%)"] = high_df["고령화율(%)"].map(
    lambda x: f"{x:.2f}%"
)

low_df["고령화율(%)"] = low_df["고령화율(%)"].map(
    lambda x: f"{x:.2f}%"
)

# 두 표를 나란히 배치합니다.
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🔴 고령화율 높은 지역 TOP 10")
    st.dataframe(
        high_df,
        use_container_width=True
    )

with col2:
    st.markdown("#### 🔵 고령화율 낮은 지역 TOP 10")
    st.dataframe(
        low_df,
        use_container_width=True
    )


# ============================================================
# 10. 데이터 안내
# ============================================================

st.caption(
    f"자료: 제공된 전국 읍·면·동 인구 데이터 및 시군구 경계 GeoJSON | "
    f"표시 연도: {latest_year}년"
)
