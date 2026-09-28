import html
from datetime import date
from zoneinfo import ZoneInfo

import requests
import streamlit as st


SCHOOL_API_URL = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"

KST = ZoneInfo("Asia/Seoul")


st.set_page_config(
    page_title="학교 급식 찾아보기",
    page_icon="🍚",
    layout="centered",
)


def search_schools(school_name: str):
    """학교 이름 일부로 학교기본정보 API를 조회한다."""
    params = {
        "Type": "json",
        "SCHUL_NM": school_name,
    }

    try:
        response = requests.get(
            SCHOOL_API_URL,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return None, f"학교 정보를 가져오는 중 오류가 발생했습니다: {e}"
    except ValueError:
        return None, "학교 정보 API가 올바른 JSON을 반환하지 않았습니다."

    # 조회 결과가 없는 경우
    if "schoolInfo" not in data:
        result_code = get_result_code(data)

        if result_code == "INFO-200":
            return [], None

        if result_code:
            return None, f"학교 정보 API 오류가 발생했습니다. ({result_code})"

        return [], None

    try:
        rows = data["schoolInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return [], None

    return rows, None


def get_result_code(data):
    """NEIS API의 RESULT.CODE를 찾아 반환한다."""
    for section_name in ("schoolInfo", "mealServiceDietInfo"):
        section = data.get(section_name)

        if not isinstance(section, list):
            continue

        for box in section:
            if not isinstance(box, dict):
                continue

            result = box.get("RESULT")
            if isinstance(result, dict):
                return result.get("CODE")

            head = box.get("head")
            if isinstance(head, list):
                for item in head:
                    if isinstance(item, dict) and "RESULT" in item:
                        result = item["RESULT"]
                        if isinstance(result, dict):
                            return result.get("CODE")

    return None


def expand_school_name(name: str):
    """
    줄임말 검색을 위한 학교명 확장.

    예:
    수도여고 -> 수도여자고등학교
    서울고 -> 서울고등학교
    """
    expanded = name.strip()

    if "여고" in expanded:
        expanded = expanded.replace("여고", "여자고등학교")
    elif expanded.endswith("고"):
        expanded = expanded[:-1] + "고등학교"

    return expanded


def school_label(school):
    """학교 선택 목록에 표시할 문자열."""
    name = school.get("SCHUL_NM", "")
    region = school.get("LCTN_SC_NM", "")
    office_code = school.get("ATPT_OFCDC_SC_CODE", "")
    school_code = school.get("SD_SCHUL_CODE", "")

    return f"{name} — {region}"


def get_meal(office_code: str, school_code: str, target_date: date):
    """선택한 학교의 특정 날짜 중식을 조회한다."""
    ymd = target_date.strftime("%Y%m%d")

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": ymd,
        "MLSV_TO_YMD": ymd,
        "pSize": "1000",
        "pIndex": "1",
    }

    try:
        response = requests.get(
            MEAL_API_URL,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return None, f"급식 정보를 가져오는 중 오류가 발생했습니다: {e}"
    except ValueError:
        return None, "급식 API가 올바른 JSON을 반환하지 않았습니다."

    if "mealServiceDietInfo" not in data:
        result_code = get_result_code(data)

        if result_code == "INFO-200":
            return [], None

        if result_code:
            return None, f"급식 정보 API 오류가 발생했습니다. ({result_code})"

        return [], None

    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return [], None

    return rows, None


def parse_menu(menu_text: str):
    """
    DDISH_NM의 <br/>를 줄바꿈으로 바꾸고 HTML escape를 적용한다.
    API에서 오는 메뉴 문자열 자체는 변경하지 않고 표시한다.
    """
    if not menu_text:
        return []

    # <br>, <br/>, <br /> 등 모두 처리
    normalized = (
        menu_text.replace("<br/>", "\n")
        .replace("<br />", "\n")
        .replace("<br>", "\n")
    )

    lines = [line.strip() for line in normalized.split("\n")]
    return [html.unescape(line) for line in lines if line.strip()]


st.title("학교 급식 찾아보기")
st.caption("나이스 교육정보 개방 포털의 학교 정보와 급식 식단을 조회합니다.")


# ─────────────────────────────────────────────
# 학교 검색
# ─────────────────────────────────────────────

st.subheader("1. 학교 선택")

with st.form("school_search_form"):
    school_query = st.text_input(
        "학교 이름",
        placeholder="예: 송탄고, 수도여고",
        help="학교 이름의 일부만 입력해도 검색할 수 있습니다.",
    )

    search_button = st.form_submit_button(
        "학교 찾기",
        type="primary",
        use_container_width=True,
    )


if search_button:
    query = school_query.strip()

    if not query:
        st.warning("학교 이름을 입력해 주세요.")
        st.session_state.pop("schools", None)
        st.session_state.pop("school_search_message", None)
    else:
        schools, error = search_schools(query)

        if error:
            st.error(error)
            st.session_state.pop("schools", None)
            st.session_state.pop("school_search_message", None)

        elif schools:
            st.session_state["schools"] = schools
            st.session_state["school_search_message"] = (
                f"'{query}' 검색 결과입니다."
            )

        else:
            # 첫 검색에 결과가 없으면 줄임말을 풀어서 한 번 더 검색
            expanded_query = expand_school_name(query)

            if expanded_query != query:
                expanded_schools, expanded_error = search_schools(
                    expanded_query
                )

                if expanded_error:
                    st.error(expanded_error)
                    st.session_state.pop("schools", None)
                    st.session_state.pop("school_search_message", None)

                elif expanded_schools:
                    st.session_state["schools"] = expanded_schools
                    st.session_state["school_search_message"] = (
                        f"'{query}'로 찾지 못해 "
                        f"'{expanded_query}'로 다시 검색한 결과입니다."
                    )

                else:
                    st.session_state.pop("schools", None)
                    st.session_state["school_search_message"] = (
                        f"'{query}'에 해당하는 학교를 찾지 못했습니다. "
                        "학교 이름을 다시 확인해 주세요."
                    )
            else:
                st.session_state.pop("schools", None)
                st.session_state["school_search_message"] = (
                    f"'{query}'에 해당하는 학교를 찾지 못했습니다. "
                    "학교 이름을 다시 확인해 주세요."
                )


schools = st.session_state.get("schools", [])
search_message = st.session_state.get("school_search_message")


if search_message:
    st.info(search_message)


if schools:
    selected_index = st.selectbox(
        "학교를 선택하세요",
        options=range(len(schools)),
        format_func=lambda i: school_label(schools[i]),
    )

    selected_school = schools[selected_index]

    st.session_state["selected_school"] = selected_school

    st.caption(
        f"학교 코드: {selected_school.get('SD_SCHUL_CODE', '')} · "
        f"교육청 코드: {selected_school.get('ATPT_OFCDC_SC_CODE', '')}"
    )


# ─────────────────────────────────────────────
# 날짜 선택
# ─────────────────────────────────────────────

st.subheader("2. 날짜 선택")

today_kst = datetime_now_kst = date.today()

# date.today()는 서버 시간대 영향을 받을 수 있으므로
# 실제 한국 날짜를 datetime.now(ZoneInfo(...))로 구한다.
from datetime import datetime

today_kst = datetime.now(KST).date()

selected_date = st.date_input(
    "급식 날짜",
    value=today_kst,
    format="YYYY-MM-DD",
)


# ─────────────────────────────────────────────
# 급식 조회
# ─────────────────────────────────────────────

st.subheader("3. 중식")

selected_school = st.session_state.get("selected_school")

if not selected_school:
    st.info("먼저 학교 이름을 검색하고 학교를 선택해 주세요.")
else:
    if st.button(
        "중식 조회",
        type="primary",
        use_container_width=True,
    ):
        office_code = selected_school.get("ATPT_OFCDC_SC_CODE")
        school_code = selected_school.get("SD_SCHUL_CODE")

        with st.spinner("급식 정보를 가져오는 중입니다..."):
            meals, error = get_meal(
                office_code,
                school_code,
                selected_date,
            )

        if error:
            st.error(error)

        elif not meals:
            st.info(
                f"{selected_date.strftime('%Y년 %m월 %d일')}에는 "
                "등록된 중식 급식 정보가 없습니다."
            )

        else:
            # 같은 날짜의 중식만 표시
            target_ymd = selected_date.strftime("%Y%m%d")

            target_meals = [
                meal
                for meal in meals
                if meal.get("MLSV_YMD") == target_ymd
            ]

            if not target_meals:
                st.info(
                    f"{selected_date.strftime('%Y년 %m월 %d일')}에는 "
                    "등록된 중식 급식 정보가 없습니다."
                )
            else:
                meal = target_meals[0]

                st.markdown(
                    f"### {selected_school.get('SCHUL_NM', '')} "
                    f"중식 · {selected_date.strftime('%Y년 %m월 %d일')}"
                )

                menu_lines = parse_menu(meal.get("DDISH_NM", ""))

                if menu_lines:
                    st.markdown("**🍚 메뉴**")

                    for menu in menu_lines:
                        st.markdown(f"- {menu}")
                else:
                    st.info("등록된 메뉴 정보가 없습니다.")

                cal_info = meal.get("CAL_INFO", "").strip()

                if cal_info:
                    st.markdown(f"**🔥 칼로리:** {cal_info}")

                st.caption(
                    "※ 메뉴 뒤 괄호의 숫자는 나이스에서 제공하는 "
                    "알레르기 유발 식품 번호입니다."
                )
