import re
import time

import pandas as pd
import streamlit as st

from improvement import get_improvements
from kipris_api import search_all_pages
from report_generator import generate_report_pdf
from scoring import evaluate_registration, similarity_percent, strip_html
from search_mapper import get_category_suggestions
from similarity_code_db import get_all_codes_by_class, get_similarity_codes


def reset_session() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def get_result_style(score: int) -> tuple[str, str, str]:
    if score >= 90:
        return "result-90", "", "등록 가능성 매우 높음"
    if score >= 70:
        return "result-70", "", "등록 가능성 높음"
    if score >= 50:
        return "result-50", "", "주의 필요 - 전문가 상담 권장"
    if score >= 30:
        return "result-30", "", "등록 어려움 - 변리사 상담 필요"
    return "result-0", "⛔", "등록 불가 가능성 높음"


def normalize_result(item: dict, trademark_name: str) -> dict:
    name = strip_html(item.get("trademarkName", item.get("trademark_name", "알 수 없음")))
    similarity = similarity_percent(trademark_name, name)
    return {
        "trademarkName": name,
        "applicationNumber": item.get("applicationNumber", item.get("application_number", "-")),
        "applicationDate": item.get("applicationDate", item.get("application_date", "-")),
        "registerStatus": item.get("registerStatus", item.get("registrationStatus", item.get("status", "-"))),
        "applicantName": strip_html(item.get("applicantName", item.get("applicant", "-"))),
        "classificationCode": item.get("classificationCode", item.get("class", "-")),
        "similarity": similarity,
    }


def deduplicate_results(items: list[dict], trademark_name: str) -> list[dict]:
    seen = set()
    results = []
    for item in items:
        normalized = normalize_result(item, trademark_name)
        key = (normalized["applicationNumber"], normalized["trademarkName"])
        if key in seen:
            continue
        seen.add(key)
        results.append(normalized)
    results.sort(key=lambda row: row["similarity"], reverse=True)
    return results


def field_key(field: dict) -> str:
    return f'{field.get("class_no", "")}|{field.get("description", "")}'


def field_widget_key(field: dict) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", field_key(field))


def field_label(field: dict) -> str:
    return f'{field.get("description", "")} ({field.get("class_no", "")})'


def current_selected_fields() -> list[dict]:
    return st.session_state.get("selected_fields", [])


def reset_analysis_state() -> None:
    st.session_state.search_results = None
    st.session_state.score = None
    st.session_state.analysis = None
    st.session_state.search_source = ""


def get_field_inputs() -> dict:
    return st.session_state.setdefault("field_inputs", {})


def ensure_field_input(field: dict) -> dict:
    inputs = get_field_inputs()
    key = field_key(field)
    if key not in inputs:
        inputs[key] = {"specific_product": "", "selected_codes": []}
    return inputs[key]


def get_field_input(field: dict) -> dict:
    return ensure_field_input(field)


def add_selected_field(field: dict) -> bool:
    selected_fields = current_selected_fields()
    key = field_key(field)
    if any(field_key(item) == key for item in selected_fields):
        return True
    if len(selected_fields) >= 3:
        st.session_state.selection_error = "상품군은 최대 3개까지 선택할 수 있습니다."
        return False
    selected_fields.append(
        {
            "class_no": field.get("class_no", field.get("류", "")),
            "description": field.get("description", field.get("설명", "")),
            "example": field.get("example", field.get("예시", "")),
        }
    )
    ensure_field_input(selected_fields[-1])
    st.session_state.selection_error = ""
    reset_analysis_state()
    return True


def remove_selected_field(target_key: str) -> None:
    st.session_state.selected_fields = [
        field for field in current_selected_fields() if field_key(field) != target_key
    ]
    inputs = get_field_inputs()
    inputs.pop(target_key, None)
    reset_analysis_state()


def update_field_product(field: dict, product: str) -> None:
    config = ensure_field_input(field)
    if config["specific_product"] != product:
        config["specific_product"] = product
        config["selected_codes"] = []
        reset_analysis_state()


def toggle_field_code(field: dict, code: str) -> None:
    config = ensure_field_input(field)
    selected_codes = list(config.get("selected_codes", []))
    if code in selected_codes:
        selected_codes.remove(code)
    else:
        selected_codes.append(code)
    config["selected_codes"] = selected_codes
    reset_analysis_state()


def field_ready(field: dict) -> bool:
    config = get_field_input(field)
    return bool(config.get("specific_product", "").strip() and config.get("selected_codes"))


def all_fields_ready() -> bool:
    selected_fields = current_selected_fields()
    return bool(selected_fields) and all(field_ready(field) for field in selected_fields)


def build_report_payload() -> dict:
    analysis = st.session_state.get("analysis") or {}
    field_reports = []
    for report in analysis.get("field_reports", []):
        field = report.get("field", {})
        field_reports.append(
            {
                "field_label": field_label(field),
                "specific_product": report.get("specific_product", ""),
                "selected_classes": [field_label(field)],
                "selected_codes": report.get("selected_codes", []),
                "score": report.get("score", 0),
                "score_label": report.get("band", {}).get("label", "-"),
                "distinctiveness": report.get("distinctiveness", "-"),
                "prior_count": report.get("prior_count", 0),
                "total_prior_count": report.get("total_prior_count", 0),
                "top_prior": report.get("top_prior", []),
                "distinctiveness_analysis": report.get("distinctiveness_analysis", {}),
                "product_similarity_analysis": report.get("product_similarity_analysis", {}),
                "mark_similarity_analysis": report.get("mark_similarity_analysis", {}),
                "confusion_analysis": report.get("confusion_analysis", {}),
                "name_options": [
                    {"name": item["name"], "expected_score": item["score"]}
                    for item in report.get("improvements", {}).get("name_suggestions", [])
                ],
                "scope_options": [
                    {
                        "title": item["description"],
                        "description": item["reason"],
                        "expected_score": item["expected_score"],
                    }
                    for item in report.get("improvements", {}).get("code_suggestions", [])
                ],
                "class_options": [
                    {
                        "title": item["description"],
                        "description": item["reason"],
                        "expected_score": item["expected_score"],
                    }
                    for item in report.get("improvements", {}).get("class_suggestions", [])
                ],
            }
        )
    return {
        "trademark_name": st.session_state.get("trademark_name", ""),
        "trademark_type": st.session_state.get("trademark_type", ""),
        "selected_classes": [field_label(field) for field in current_selected_fields()],
        "field_reports": field_reports,
    }


def similarity_cell_style(value) -> str:
    try:
        numeric = int(str(value).replace("%", ""))
    except ValueError:
        return ""
    if numeric >= 70:
        return "background-color: #FFEBEE; color: #B71C1C; font-weight: bold;"
    if numeric >= 50:
        return "background-color: #FFF3E0; color: #E65100; font-weight: bold;"
    return "background-color: #E8F5E9; color: #2E7D32;"


st.set_page_config(
    page_title="상표등록 가능성 검토",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .stApp { background-color: #F0F8FF; }
    .main-header {
        background: linear-gradient(135deg, #1565C0, #2196F3);
        padding: 20px 30px;
        border-radius: 12px;
        color: white;
        margin-bottom: 24px;
    }
    .step-bar {
        display: flex;
        justify-content: center;
        gap: 8px;
        margin: 16px 0;
        flex-wrap: wrap;
    }
    .step-active {
        background: #2196F3;
        color: white;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 14px;
    }
    .step-done {
        background: #4CAF50;
        color: white;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 14px;
    }
    .step-todo {
        background: #B0BEC5;
        color: white;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 14px;
    }
    .card {
        background: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 2px 8px rgba(33,150,243,0.1);
        border-left: 4px solid #2196F3;
        margin-bottom: 16px;
    }
    .category-card {
        background: #E3F2FD;
        border: 2px solid #90CAF9;
        border-radius: 10px;
        padding: 16px;
        margin: 8px 0;
    }
    .code-card {
        background: #F8FBFF;
        border: 1px solid #90CAF9;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
    }
    .code-recommended {
        border-color: #2196F3;
        border-width: 2px;
        background: #E3F2FD;
    }
    .code-sales {
        border-color: #66BB6A;
        background: #F1F8E9;
    }
    .result-90 { background:#E8F5E9; border:3px solid #4CAF50; border-radius:12px; padding:20px; text-align:center; }
    .result-70 { background:#E3F2FD; border:3px solid #2196F3; border-radius:12px; padding:20px; text-align:center; }
    .result-50 { background:#FFF3E0; border:3px solid #FF9800; border-radius:12px; padding:20px; text-align:center; }
    .result-30 { background:#FFEBEE; border:3px solid #F44336; border-radius:12px; padding:20px; text-align:center; }
    .result-0  { background:#B71C1C; border:3px solid #7F0000; border-radius:12px; padding:20px; text-align:center; color:white; }
    .trademark-high { background:#FFEBEE; border-left:4px solid #F44336; border-radius:8px; padding:14px; margin:8px 0; }
    .trademark-medium { background:#FFF3E0; border-left:4px solid #FF9800; border-radius:8px; padding:14px; margin:8px 0; }
    .trademark-low { background:#E8F5E9; border-left:4px solid #4CAF50; border-radius:8px; padding:14px; margin:8px 0; }
    .stButton>button {
        background: linear-gradient(135deg, #1976D2, #2196F3);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 16px;
        font-weight: bold;
        white-space: pre-wrap;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #1565C0, #1976D2);
        color: white;
    }
    .tip-box {
        background: #E8F4FD;
        border: 1px solid #90CAF9;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 13px;
        color: #1565C0;
        margin: 8px 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

if "step" not in st.session_state:
    st.session_state.step = 1
if "trademark_name" not in st.session_state:
    st.session_state.trademark_name = ""
if "trademark_type" not in st.session_state:
    st.session_state.trademark_type = "문자만"
if "is_coined" not in st.session_state:
    st.session_state.is_coined = False
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "specific_keyword" not in st.session_state:
    st.session_state.specific_keyword = ""
if "specific_product" not in st.session_state:
    st.session_state.specific_product = ""
if "selected_fields" not in st.session_state:
    st.session_state.selected_fields = []
if "field_inputs" not in st.session_state:
    st.session_state.field_inputs = {}
if "selected_codes" not in st.session_state:
    st.session_state.selected_codes = []
if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "score" not in st.session_state:
    st.session_state.score = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "search_source" not in st.session_state:
    st.session_state.search_source = ""
if "selection_error" not in st.session_state:
    st.session_state.selection_error = ""

st.markdown(
    """
<div class="main-header">
    <h1 style="margin:0; font-size:28px;">상표등록 가능성 검토</h1>
    <p style="margin:4px 0 0 0; opacity:0.9;">내 브랜드를 법적으로 보호하세요</p>
</div>
""",
    unsafe_allow_html=True,
)


def render_steps(current: int) -> None:
    steps = ["① 상표명", "② 상품선택", "③ 유사군코드", "④ 검토결과", "⑤ 개선방안"]
    html = '<div class="step-bar">'
    for index, label in enumerate(steps, 1):
        if index < current:
            html += f'<span class="step-done">✓ {label}</span>'
        elif index == current:
            html += f'<span class="step-active">{label}</span>'
        else:
            html += f'<span class="step-todo">{label}</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


render_steps(st.session_state.step)
st.markdown("---")


if st.session_state.step == 1:
    st.markdown("## 안녕하세요!")
    st.markdown("### 등록하고 싶은 상표명을 알려주세요")

    st.markdown(
        """
    <div class="tip-box">
    <b>상표란?</b> 내 브랜드·회사명·제품명을 법적으로 보호하는 권리예요.<br>
    상표를 등록하면 다른 사람이 같은 이름을 쓰지 못하게 막을 수 있어요!
    </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        name = st.text_input(
            "상표명 입력",
            placeholder="예) POOKIE, 사랑해, BRAND ONE, 달빛커피...",
            value=st.session_state.trademark_name,
            label_visibility="collapsed",
        )

    st.markdown("#### 상표 유형을 선택해주세요")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("문자만\n(텍스트 상표)", use_container_width=True):
            st.session_state.trademark_type = "문자만"
    with col2:
        if st.button("문자 + 로고\n(결합 상표)", use_container_width=True):
            st.session_state.trademark_type = "문자+로고"
    with col3:
        if st.button("로고만\n(도형 상표)", use_container_width=True):
            st.session_state.trademark_type = "로고만"

    st.markdown(f"선택됨: **{st.session_state.trademark_type}**")

    st.markdown("#### 새로 만든 단어인가요?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 네, 새로 만든 단어예요\n(조어상표 - 등록에 유리!)", use_container_width=True):
            st.session_state.is_coined = True
    with col2:
        if st.button("아니요, 기존 단어예요\n(일반단어)", use_container_width=True):
            st.session_state.is_coined = False

    st.markdown(
        """
    <div class="tip-box">
    <b>조어상표란?</b> 기존에 없던 새로운 단어로 만든 상표예요.<br>
    예) KAKAO, NAVER, COUPANG → 등록 가능성이 높아져요!
    </div>
    """,
        unsafe_allow_html=True,
    )

    if st.button("다음 단계로 → 상품 선택", use_container_width=True, type="primary"):
        if name.strip():
            st.session_state.trademark_name = name.strip()
            st.session_state.step = 2
            st.rerun()
        st.error("상표명을 입력해주세요!")

elif st.session_state.step == 2:
    st.markdown(f"## '{st.session_state.trademark_name}' 상표를")
    st.markdown("### 어떤 분야에 사용하실 예정인가요? 최대 3개까지 선택할 수 있어요.")

    st.markdown(
        """
    <div class="tip-box">
    상표는 반드시 <b>사용할 상품/서비스 분야</b>를 지정해서 등록해야 해요.<br>
    아래에서 업종을 검색하거나 직접 선택해주세요.
    </div>
    """,
        unsafe_allow_html=True,
    )

    search_keyword = st.text_input(
        "업종/상품 검색",
        placeholder="예) 가구, 커피, 옷, 화장품, 앱개발, 음식점...",
        label_visibility="collapsed",
    )

    if search_keyword:
        suggestions = get_category_suggestions(search_keyword, limit=6)
        if suggestions:
            st.markdown("#### 추천 상품/서비스 분야")
            for index, sug in enumerate(suggestions):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(
                        f"""
                    <div class="category-card">
                        <b>{sug['아이콘']} {sug['설명']} ({sug['류']})</b><br>
                        <small style="color:#546E7A">예시: {sug['예시']}</small>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    already_selected = any(
                        field_key(field) == field_key({"class_no": sug["류"], "description": sug["설명"]})
                        for field in current_selected_fields()
                    )
                    if st.button("선택됨" if already_selected else "추가", key=f"sel_{index}_{sug['류']}"):
                        add_selected_field(
                            {"class_no": sug["류"], "description": sug["설명"], "example": sug["예시"]}
                        )
                        st.rerun()
        else:
            st.warning("검색 결과가 없어요. 아래 전체 목록에서 선택해주세요.")

    st.markdown("---")
    st.markdown("#### 전체 목록에서 직접 선택")

    all_categories = {
        "상품": [
            {"류": "3류", "설명": "화장품/향수/세제", "예시": "스킨케어, 향수, 샴푸", "아이콘": "💄"},
            {"류": "5류", "설명": "의약품/건강기능식품", "예시": "영양제, 건강식품", "아이콘": "💊"},
            {"류": "9류", "설명": "전자기기/소프트웨어", "예시": "스마트폰, 앱, 컴퓨터", "아이콘": "📱"},
            {"류": "14류", "설명": "귀금속/시계/보석", "예시": "반지, 목걸이, 시계", "아이콘": "⌚"},
            {"류": "16류", "설명": "종이/문구/출판물", "예시": "노트, 책, 달력", "아이콘": "📚"},
            {"류": "18류", "설명": "가방/지갑/가죽제품", "예시": "핸드백, 백팩, 지갑", "아이콘": "👜"},
            {"류": "20류", "설명": "가구/인테리어", "예시": "소파, 침대, 책상", "아이콘": "🪑"},
            {"류": "21류", "설명": "주방용품/생활용품", "예시": "컵, 냄비, 칫솔", "아이콘": "🍽️"},
            {"류": "25류", "설명": "의류/신발/모자", "예시": "티셔츠, 운동화, 모자", "아이콘": "👕"},
            {"류": "28류", "설명": "완구/스포츠용품", "예시": "장난감, 게임기, 운동용품", "아이콘": "🎮"},
            {"류": "29류", "설명": "가공식품", "예시": "육류, 유제품, 김치", "아이콘": "🥩"},
            {"류": "30류", "설명": "커피/빵/과자/음료", "예시": "커피, 빵, 과자, 라면", "아이콘": "☕"},
            {"류": "32류", "설명": "음료/맥주", "예시": "탄산음료, 주스, 맥주", "아이콘": "🥤"},
            {"류": "33류", "설명": "주류(소주/와인)", "예시": "소주, 와인, 위스키", "아이콘": "🍷"},
        ],
        "서비스": [
            {"류": "35류", "설명": "광고/소매업/쇼핑몰", "예시": "온라인쇼핑몰, 편의점", "아이콘": "🛍️"},
            {"류": "36류", "설명": "금융/보험/부동산", "예시": "은행, 보험, 증권", "아이콘": "🏢"},
            {"류": "37류", "설명": "건설/수리/인테리어", "예시": "건설, 인테리어, 수리", "아이콘": "🏠"},
            {"류": "38류", "설명": "통신/인터넷/방송", "예시": "통신서비스, SNS", "아이콘": "📡"},
            {"류": "39류", "설명": "운송/여행/물류", "예시": "택배, 여행사, 항공", "아이콘": "✈️"},
            {"류": "41류", "설명": "교육/엔터테인먼트", "예시": "학원, 게임, 공연", "아이콘": "📘"},
            {"류": "42류", "설명": "IT/개발/디자인", "예시": "앱개발, 클라우드", "아이콘": "💻"},
            {"류": "43류", "설명": "음식점/카페/숙박", "예시": "식당, 카페, 호텔", "아이콘": "🍽️"},
            {"류": "44류", "설명": "의료/미용/헬스케어", "예시": "병원, 미용실", "아이콘": "🩺"},
            {"류": "45류", "설명": "법률/보안/개인서비스", "예시": "법률, 변리사", "아이콘": "⚖️"},
        ],
    }

    tab1, tab2 = st.tabs(["상품류 (1~34류)", "서비스류 (35~45류)"])
    with tab1:
        cols = st.columns(2)
        for index, cat in enumerate(all_categories["상품"]):
            with cols[index % 2]:
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.markdown(
                        f"""
                    <div class="category-card">
                        <b>{cat['아이콘']} {cat['설명']}</b> <small>({cat['류']})</small><br>
                        <small style="color:#546E7A">{cat['예시']}</small>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                with col_b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    already_selected = any(
                        field_key(field) == field_key({"class_no": cat["류"], "description": cat["설명"]})
                        for field in current_selected_fields()
                    )
                    if st.button("선택됨" if already_selected else "추가", key=f"goods_{cat['류']}"):
                        add_selected_field(
                            {"class_no": cat["류"], "description": cat["설명"], "example": cat["예시"]}
                        )
                        st.rerun()

    with tab2:
        cols = st.columns(2)
        for index, cat in enumerate(all_categories["서비스"]):
            with cols[index % 2]:
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.markdown(
                        f"""
                    <div class="category-card">
                        <b>{cat['아이콘']} {cat['설명']}</b> <small>({cat['류']})</small><br>
                        <small style="color:#546E7A">{cat['예시']}</small>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                with col_b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    already_selected = any(
                        field_key(field) == field_key({"class_no": cat["류"], "description": cat["설명"]})
                        for field in current_selected_fields()
                    )
                    if st.button("선택됨" if already_selected else "추가", key=f"service_{cat['류']}"):
                        add_selected_field(
                            {"class_no": cat["류"], "description": cat["설명"], "example": cat["예시"]}
                        )
                        st.rerun()

    if st.session_state.selection_error:
        st.warning(st.session_state.selection_error)

    if current_selected_fields():
        st.markdown("#### 선택된 상품군")
        for index, field in enumerate(current_selected_fields(), start=1):
            col1, col2 = st.columns([6, 1])
            with col1:
                st.markdown(
                    f"""
                    <div class="card">
                        <b>{index}. {field_label(field)}</b><br>
                        <small style="color:#546E7A;">예시: {field.get('example', '-')}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button("삭제", key=f"remove_field_{field_widget_key(field)}"):
                    remove_selected_field(field_key(field))
                    st.rerun()

    if st.button("← 이전 단계로"):
        st.session_state.step = 1
        st.rerun()

    if st.button(
        "다음 단계로 → 유사군코드 선택",
        use_container_width=True,
        type="primary",
        disabled=not current_selected_fields(),
    ):
        st.session_state.step = 3
        st.rerun()

elif st.session_state.step == 3:
    selected_fields = current_selected_fields()
    st.markdown("## 선택한 상품군별 구체 상품/서비스와 유사군코드를 정해주세요")

    st.markdown(
        """
    <div class="tip-box">
    <b>유사군코드란?</b> 비슷한 상품끼리 묶은 분류 코드예요.<br>
    코드가 같은 상표끼리 서로 충돌할 수 있어요. 정확히 선택할수록 검토가 정확해져요!
    </div>
    """,
        unsafe_allow_html=True,
    )

    for index, field in enumerate(selected_fields, start=1):
        config = get_field_input(field)
        widget_key = field_widget_key(field)
        st.markdown("---")
        st.markdown(f"### {index}. {field_label(field)}")
        specific_product = st.text_input(
            f"{field_label(field)} 구체 상품명 입력",
            placeholder=f"예) {field.get('example', '').split(',')[0].strip()}...",
            value=config.get("specific_product", ""),
            key=f"product_{widget_key}",
        )
        update_field_product(field, specific_product)
        config = get_field_input(field)

        if specific_product.strip():
            codes = get_similarity_codes(specific_product, field["class_no"])
            if codes:
                st.markdown("#### 추천 유사군코드")
                for code_info in codes:
                    col1, col2 = st.columns([5, 1])
                    badge = ""
                    card_class = "code-card"
                    if code_info.get("추천"):
                        badge = "⭐ 추천"
                        card_class = "code-card code-recommended"
                    if code_info.get("판매업"):
                        badge = "판매업 코드"
                        card_class = "code-card code-sales"

                    with col1:
                        st.markdown(
                            f"""
                        <div class="{card_class}">
                            <b>{badge} {code_info['code']}</b> - {code_info['name']}<br>
                            <small style="color:#546E7A">{code_info['설명']}</small>
                            {"<br><small style='color:#2E7D32'>판매업도 함께 보호받으려면 이 코드도 선택하세요!</small>" if code_info.get("판매업") else ""}
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )
                    with col2:
                        is_selected = code_info["code"] in config.get("selected_codes", [])
                        label = "✓ 선택됨" if is_selected else "선택"
                        if st.button(label, key=f"code_{widget_key}_{code_info['code']}"):
                            toggle_field_code(field, code_info["code"])
                            st.rerun()
            else:
                st.info("추천 결과가 없어 전체 유사군코드 목록을 보여드립니다.")

            if not codes:
                all_codes = get_all_codes_by_class(field["class_no"])
                for code_info in all_codes:
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(
                            f"""
                        <div class="code-card">
                            <b>{code_info['code']}</b> - {code_info['name']}<br>
                            <small>{code_info['설명']}</small>
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )
                    with col2:
                        is_selected = code_info["code"] in config.get("selected_codes", [])
                        label = "✓ 선택됨" if is_selected else "선택"
                        if st.button(label, key=f"all_code_{widget_key}_{code_info['code']}"):
                            toggle_field_code(field, code_info["code"])
                            st.rerun()

        selected_codes = config.get("selected_codes", [])
        if selected_codes:
            st.markdown("#### 선택된 유사군코드")
            st.markdown(" ".join([f"**{code}**" for code in selected_codes]))
        else:
            st.caption("이 상품군에 대한 유사군코드를 최소 1개 선택해주세요.")

    if st.button("← 이전 단계로"):
        st.session_state.step = 2
        st.rerun()

    if st.button(
        "검토 시작하기!",
        use_container_width=True,
        type="primary",
        disabled=not all_fields_ready(),
    ):
        reset_analysis_state()
        st.session_state.step = 4
        st.rerun()

elif st.session_state.step == 4:
    if st.session_state.analysis is None:
        st.markdown("## 검토 중입니다...")
        progress = st.progress(0)
        status = st.empty()
        field_reports = []
        selected_fields = current_selected_fields()
        total_fields = max(1, len(selected_fields))

        for index, field in enumerate(selected_fields, start=1):
            config = get_field_input(field)
            status.markdown(f"🔎 {field_label(field)} KIPRIS 선행상표 검색 및 분석 중... ({index}/{total_fields})")
            all_results = []
            used_real_search = False

            for code in config.get("selected_codes", []):
                result = search_all_pages(st.session_state.trademark_name, similar_goods_code=code, max_pages=3)
                if result and result.get("items"):
                    all_results.extend([{**item, "queried_codes": [code]} for item in result["items"]])
                if result and result.get("success") and not result.get("mock", False):
                    used_real_search = True

            if not all_results:
                fallback = search_all_pages(st.session_state.trademark_name, max_pages=3)
                if fallback and fallback.get("items"):
                    all_results.extend([{**item, "queried_codes": []} for item in fallback["items"]])
                if fallback and fallback.get("success") and not fallback.get("mock", False):
                    used_real_search = True

            field_analysis = evaluate_registration(
                trademark_name=st.session_state.trademark_name,
                trademark_type=st.session_state.trademark_type,
                is_coined=st.session_state.is_coined,
                selected_classes=[field["class_no"]],
                selected_codes=config.get("selected_codes", []),
                prior_items=all_results,
                selected_fields=[field],
                specific_product=config.get("specific_product", ""),
            )
            field_reports.append(
                {
                    **field_analysis,
                    "field": field,
                    "specific_product": config.get("specific_product", ""),
                    "selected_codes": list(config.get("selected_codes", [])),
                    "search_source": "실제 KIPRIS 데이터" if used_real_search else "Mock 데이터 또는 제한 조회",
                    "improvements": get_improvements(
                        st.session_state.trademark_name,
                        config.get("selected_codes", []),
                        field_analysis.get("included_priors", []),
                        field_analysis.get("score", 0),
                    ),
                }
            )
            progress.progress(int(index / total_fields * 100))

        st.session_state.analysis = {"field_reports": field_reports}
        st.session_state.search_results = field_reports
        st.session_state.score = None
        st.session_state.search_source = "상품군별 개별 분석"

        status.markdown("✅ 상품군별 검토 완료!")
        time.sleep(0.5)
        st.rerun()

    analysis = st.session_state.analysis or {}
    field_reports = analysis.get("field_reports", [])
    st.markdown(f"## **'{st.session_state.trademark_name}'** 등록 가능성 검토 결과")
    st.markdown("### 선택한 상품군별로 따로 판단한 결과입니다.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("검토 상품군", f"{len(field_reports)}개")
    with col2:
        high_risk_fields = sum(1 for report in field_reports if report.get("actual_risk_prior_count", 0) > 0)
        st.metric("실제 충돌 위험 상품군", f"{high_risk_fields}개")
    with col3:
        st.metric("조어상표 여부", "예" if st.session_state.is_coined else "아니오")
    with col4:
        total_code_count = sum(len(report.get("selected_codes", [])) for report in field_reports)
        st.metric("선택 유사군코드", f"{total_code_count}개")

    for field_index, report in enumerate(field_reports, start=1):
        field = report.get("field", {})
        score = report.get("score", 0)
        results = report.get("included_priors", [])
        excluded_results = report.get("excluded_priors", [])
        total_results = report.get("total_prior_count", len(results) + len(excluded_results))
        css_class, emoji, label = get_result_style(score)
        color = "#FFFFFF" if score < 30 else "#2E7D32" if score >= 90 else "#1565C0" if score >= 70 else "#E65100" if score >= 50 else "#B71C1C"

        st.markdown("---")
        st.markdown(f"## {field_index}. {field_label(field)}")
        st.markdown(
            f"""
            <div class="{css_class}">
                <h1 style="font-size:56px; margin:0; color:{color};">{score}%</h1>
                <h2 style="margin:8px 0; color:{color};">{emoji} {label}</h2>
                <p style="color:{color}; margin:0;">구체 상품: <b>{report.get('specific_product', '-')}</b> |
                코드: <b>{', '.join(report.get('selected_codes', []))}</b> |
                검색 출처: <b>{report.get('search_source', '-')}</b></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        sub1, sub2, sub3, sub4 = st.columns(4)
        with sub1:
            st.metric("전체 검색 건수", f"{total_results}건")
        with sub2:
            st.metric("필터 통과 건수", f"{report.get('filtered_prior_count', report.get('prior_count', 0))}건")
        with sub3:
            st.metric("실제 충돌 위험 건수", f"{report.get('actual_risk_prior_count', 0)}건")
        with sub4:
            st.metric("제외된 후보 건수", f"{report.get('excluded_prior_count', len(excluded_results))}건")

        st.markdown("### 점수 산정 해설")
        score_explanation = report.get("score_explanation", {})
        st.markdown(
            f"""
            <div class="card">
                <b>최종 점수 {report.get('score', 0)}% (원점수 {score_explanation.get('raw_score', report.get('score', 0))}%)</b><br>
                <small style="color:#546E7A;">{score_explanation.get('summary', '-')}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for note in score_explanation.get("notes", []):
            st.markdown(f"- {note}")
        if report.get("filtered_prior_count", 0) == 0:
            st.markdown("- 검색 결과가 있어도 상품 유사성 필터 통과 선행상표가 0건이면 상대적 거절사유 리스크를 매우 낮게 봅니다.")
        if report.get("distinctiveness") in {"식별력 약함", "거절 가능성 큼"} and report.get("filtered_prior_count", 0) == 0:
            st.markdown("- 식별력 약함은 별도 축으로 반영되며, 충돌 후보가 없으면 등록 가능성이 여전히 높게 나올 수 있습니다.")

        st.markdown("### 식별력 판단")
        distinctiveness = report.get("distinctiveness_analysis", {})
        st.markdown(
            f"""
            <div class="card">
                <b>{report.get('distinctiveness', '-')}</b><br>
                <small style="color:#546E7A;">{distinctiveness.get('summary', '-')}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for reason in distinctiveness.get("reasons", []):
            st.markdown(f"- {reason}")

        st.markdown("### 상품 유사성 검토 결과")
        product_analysis = report.get("product_similarity_analysis", {})
        bucket_counts = product_analysis.get("bucket_counts", {})
        st.markdown(
            f"""
            <div class="card">
                <b>{product_analysis.get('summary', '-')}</b><br>
                <small style="color:#546E7A;">
                동일 유사군코드 {bucket_counts.get('same_code', 0)}건 /
                동일 류 {bucket_counts.get('same_class', 0)}건 /
                타 류 예외군 {bucket_counts.get('exception', 0)}건 /
                제외 {bucket_counts.get('excluded', 0)}건
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"- {product_analysis.get('exclusion_reason_summary', report.get('exclusion_reason_summary', '-'))}")

        st.markdown("### 표장 유사성 검토 결과")
        st.markdown(
            f"""
            <div class="card">
                <b>{report.get('mark_similarity_analysis', {}).get('summary', '-')}</b><br>
                <small style="color:#546E7A;">기존 문자열 유사도와 발음 유사 보조 로직은 유지하되, 상품 유사성 필터 통과 후보에만 적용했습니다.</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if results:
            for item in results[:3]:
                st.markdown(
                    f"- `{item['trademarkName']}`: 외관 {item.get('appearance_similarity', 0)}%, "
                    f"호칭 {item.get('phonetic_similarity', 0)}%, "
                    f"관념 {item.get('conceptual_similarity', 0)}%, "
                    f"표장 유사도 {item.get('mark_similarity', 0)}%"
                )
        else:
            st.markdown("- 상품 유사성 필터를 통과한 후보가 없어 표장 유사도는 강한 감점에 쓰지 않았습니다.")

        st.markdown("### 혼동 가능성 종합")
        st.markdown(
            f"""
            <div class="card">
                <b>{report.get('confusion_analysis', {}).get('summary', '-')}</b><br>
                <small style="color:#546E7A;">검색 출처: {report.get('search_source', '-')}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if results:
            st.markdown("### 주요 선행상표 목록")
            for index, item in enumerate(results[:10]):
                confusion_score = item.get("confusion_score", 0)
                if confusion_score >= 75:
                    card_class = "trademark-high"
                    risk_label = "높은 위험"
                    bar_color = "#F44336"
                elif confusion_score >= 55:
                    card_class = "trademark-medium"
                    risk_label = "주의"
                    bar_color = "#FF9800"
                else:
                    card_class = "trademark-low"
                    risk_label = "낮은 위험"
                    bar_color = "#4CAF50"

                st.markdown(
                    f"""
                    <div class="{card_class}">
                        <table style="width:100%; border:none;">
                        <tr>
                            <td style="width:60%">
                                <b>{index + 1}. {item['trademarkName']}</b> &nbsp; {risk_label}<br>
                                <small>출원번호: {item['applicationNumber']} | 출원일: {item['applicationDate']}</small><br>
                                <small>상태: {item['registerStatus']} | 류: {item['classificationCode']} | 출원인: {item['applicantName']}</small><br>
                                <small>상품군 판단: {item.get('product_similarity_label', '-')} | {item.get('product_reason', '-')}</small>
                            </td>
                            <td style="width:40%; text-align:right; vertical-align:top;">
                                <b style="font-size:20px;">혼동 위험 {confusion_score}%</b><br>
                                <small>표장 {item.get('mark_similarity', 0)}% / 상품 {item.get('product_similarity_score', 0)}%</small><br>
                                <div style="background:#ddd; border-radius:4px; height:8px; margin-top:4px;">
                                    <div style="background:{bar_color}; width:{confusion_score}%; height:8px; border-radius:4px;"></div>
                                </div>
                                <br>
                                <a href="https://www.kipris.or.kr" target="_blank" style="color:#2196F3; font-size:12px;">KIPRIS에서 보기 →</a>
                            </td>
                        </tr>
                        </table>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("### 데이터 표 보기")
            result_df = pd.DataFrame(
                [
                    {
                        "상표명": row["trademarkName"],
                        "혼동위험": f'{row.get("confusion_score", 0)}%',
                        "표장유사도": f'{row.get("mark_similarity", 0)}%',
                        "상품판단": row.get("product_similarity_label", "-"),
                        "상태": row["registerStatus"],
                        "류": row["classificationCode"],
                        "출원인": row["applicantName"],
                    }
                    for row in results[:10]
                ]
            )
            styled_df = result_df.style.map(similarity_cell_style, subset=["혼동위험", "표장유사도"])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.markdown(
                """
                <div style="background:#E8F5E9; border:2px solid #4CAF50; border-radius:12px; padding:20px; text-align:center;">
                    <h3 style="color:#2E7D32;">상품 유사성 검토를 통과한 선행상표가 없어요!</h3>
                    <p style="color:#388E3C;">타 류·타 코드 후보는 점수에서 제외했고,<br>
                    등록 가능성이 매우 높습니다!</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if excluded_results:
            st.markdown(
                f"""
                <div class="tip-box" style="margin-top:12px;">
                검색 결과가 있었지만 상품 유사성 검토에서 제외된 후보 {len(excluded_results)}건은 최종 점수와 top_prior에 반영하지 않았습니다.
                예: {', '.join(row['trademarkName'] for row in excluded_results[:3])}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="tip-box" style="margin-top:16px;">
        ⚠️ 본 결과는 AI 자동 분석 참고용이며, 최종 판단은 반드시 <b>변리사와 상담</b>하세요.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("등록 가능성 높이기", use_container_width=True, type="primary"):
            st.session_state.step = 5
            st.rerun()
    with col2:
        st.download_button(
            "PDF 보고서 받기",
            data=generate_report_pdf(build_report_payload()),
            file_name=f"{st.session_state.trademark_name}_검토보고서.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with col3:
        if st.button("처음부터 다시", use_container_width=True):
            reset_session()
            st.rerun()

elif st.session_state.step == 5:
    st.markdown("## 등록 가능성을 높이는 방법")
    st.markdown("### 선택한 상품군별 개선안을 따로 제안합니다.")

    for index, report in enumerate((st.session_state.analysis or {}).get("field_reports", []), start=1):
        improvements = report.get("improvements", {})
        field = report.get("field", {})
        current_score = report.get("score", 0)

        st.markdown("---")
        st.markdown(f"## {index}. {field_label(field)}")
        st.markdown(f"현재: **{st.session_state.trademark_name}** / **{report.get('specific_product', '-') }** / **{current_score}%**")

        st.markdown("### 방법 1: 상표명 변경")
        st.markdown(
            """
        <div class="tip-box">
        현재 상표명과 발음이 다른 새로운 이름을 사용하면 등록 가능성이 높아져요.
        </div>
        """,
            unsafe_allow_html=True,
        )

        for suggestion in improvements.get("name_suggestions", []):
            score_value = suggestion.get("score", 0)
            if score_value >= 90:
                color, bg = "#2E7D32", "#E8F5E9"
            elif score_value >= 70:
                color, bg = "#1565C0", "#E3F2FD"
            else:
                color, bg = "#E65100", "#FFF3E0"

            st.markdown(
                f"""
                <div style="background:{bg}; border-radius:8px; padding:12px 16px; margin:6px 0; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <b style="font-size:18px;">{suggestion['name']}</b><br>
                        <small style="color:#546E7A">{suggestion.get('reason', '')}</small>
                    </div>
                    <div style="text-align:right;">
                        <b style="font-size:22px; color:{color};">예상 {score_value}%</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### 방법 2: 상품 범위 조정")
        for suggestion in improvements.get("code_suggestions", []):
            st.markdown(
                f"""
                <div style="background:#E3F2FD; border-radius:8px; padding:12px 16px; margin:6px 0;">
                    <b>{suggestion['description']}</b><br>
                    <small style="color:#546E7A">{suggestion.get('reason', '')}</small><br>
                    <b style="color:#1565C0;">→ 예상 {suggestion.get('expected_score', 0)}%로 향상</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### 방법 3: 다른 상품군 검토")
        for suggestion in improvements.get("class_suggestions", []):
            st.markdown(
                f"""
                <div style="background:#F1F8E9; border-radius:8px; padding:12px 16px; margin:6px 0;">
                    <b>{suggestion['description']}</b><br>
                    <small style="color:#546E7A">{suggestion.get('reason', '')}</small><br>
                    <b style="color:#2E7D32;">→ 예상 {suggestion.get('expected_score', 0)}%로 향상</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
    <div class="tip-box" style="margin-top:24px;">
    ⚠️ 위 제안은 AI 참고용 분석이에요. 최종 결정은 반드시 <b>변리사와 상담</b>하세요.
    </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← 결과로 돌아가기", use_container_width=True):
            st.session_state.step = 4
            st.rerun()
    with col2:
        if st.button("처음부터 다시", use_container_width=True):
            reset_session()
            st.rerun()
