from __future__ import annotations


def build_eval_pairs() -> list[dict]:
    pairs: list[dict] = []

    classes_pool = ["03", "09", "25", "30", "35", "41", "42", "44"]

    def pick_classes(i: int) -> list[str]:
        return [classes_pool[i % len(classes_pool)]]

    def add_pair(
        left: str,
        right: str,
        label: int,
        pair_type: str,
        note: str,
        i: int,
        same_class: bool | None = None,
    ) -> None:
        same = bool((i % 4 == 0) if same_class is None else same_class)
        classes_a = pick_classes(i)
        classes_b = classes_a if same else pick_classes(i + 3)
        pairs.append(
            {
                "id": f"PAIR-{len(pairs)+1:04d}",
                "a": left,
                "b": right,
                "label": int(label),
                "pair_type": pair_type,
                "classes_a": classes_a,
                "classes_b": classes_b,
                "same_class": same,
                "note": note,
            }
        )

    i = 0

    ending_variants = [
        ("POOKIE", "POOKY"),
        ("COOKIE", "COOKY"),
        ("HOKIE", "HOKY"),
        ("BUNNIE", "BUNNY"),
        ("KITTIE", "KITTY"),
        ("LOVIE", "LOVY"),
        ("HOMIE", "HOMY"),
        ("MOVIE", "MOVY"),
        ("INDIE", "INDY"),
        ("AUNTIE", "AUNTY"),
        ("DOGGIE", "DOGGY"),
        ("BIRDIE", "BIRDY"),
        ("PUPPIE", "PUPPY"),
        ("CUTIE", "CUTY"),
        ("FUNKIE", "FUNKY"),
        ("SWEETIE", "SWEETY"),
        ("ROOMIE", "ROOMY"),
        ("SOFTIE", "SOFTY"),
        ("BESTIE", "BESTY"),
        ("ECOIE", "ECOY"),
    ]
    for a, b in ending_variants:
        add_pair(a, b, 1, "en-en", "종결 모음/철자 변형(IE/EE/Y)", i)
        i += 1

    consonant_pos = [
        ("POOKIE", "FOOKY", "P↔F"),
        ("POOKY", "FOOKY", "P↔F"),
        ("POOKIE", "BOOKY", "P↔B"),
        ("POOKY", "BOOKY", "P↔B"),
        ("ROCKY", "LOCKY", "R↔L"),
        ("RIVER", "LIVER", "R↔L"),
        ("RATE", "LATE", "R↔L"),
        ("RING", "LING", "R↔L"),
        ("PARK", "BARK", "P↔B"),
        ("PARK", "FARK", "P↔F"),
        ("KART", "GART", "K↔G"),
        ("TONE", "DONE", "T↔D"),
        ("TANK", "DANK", "T↔D"),
        ("KIND", "GIND", "K↔G"),
        ("POPPY", "FOPPY", "P↔F"),
        ("PAPA", "BABA", "P↔B"),
        ("PURI", "FURI", "P↔F"),
        ("KORE", "GORE", "K↔G"),
        ("TARI", "DARI", "T↔D"),
        ("LUNA", "RUNA", "L↔R"),
    ]
    for a, b, tag in consonant_pos:
        add_pair(a, b, 1, "en-en", f"유사 자음 치환({tag})", i)
        i += 1

    digraph_pos = [
        ("PHONE", "FONE", "PH->F"),
        ("PHASE", "FASE", "PH->F"),
        ("CHECK", "CHEK", "CK->K"),
        ("BACK", "BAK", "CK->K"),
        ("QUICK", "KWIK", "QU->KW"),
        ("QUIT", "KWIT", "QU->KW"),
        ("BOX", "BOKS", "X->KS"),
        ("XENO", "KSENO", "X->KS"),
        ("THING", "TIN", "ING->IN"),
        ("SING", "SIN", "ING->IN"),
        ("LIGHT", "LIT", "GH silent"),
        ("NIGHT", "NIT", "GH silent"),
    ]
    for a, b, tag in digraph_pos:
        add_pair(a, b, 1, "en-en", f"이중문자/묵음 규칙({tag})", i)
        i += 1

    cross_pos = [
        ("POOKY", "푸키"),
        ("POOKIE", "푸키"),
        ("BOOKY", "부키"),
        ("FOOKY", "후키"),
        ("COOKIE", "쿠키"),
        ("QUICK", "퀵"),
        ("PHONE", "폰"),
        ("FONE", "폰"),
        ("ROCKY", "로키"),
        ("LOCKY", "로키"),
        ("PARK", "파크"),
        ("MARK", "마크"),
        ("LUNA", "루나"),
        ("RUNA", "루나"),
        ("TONE", "톤"),
        ("DONE", "돈"),
    ]
    for a, b in cross_pos:
        add_pair(a, b, 1, "cross", "영문↔한글 호칭 대응", i)
        i += 1

    hangul_pos = [
        ("쿠키", "꾸키"),
        ("쿠키", "푸키"),
        ("쿠키", "부키"),
        ("로키", "러키"),
        ("로키", "노키"),
        ("라떼", "라테"),
        ("부키", "푸키"),
        ("후키", "푸키"),
        ("록키", "로키"),
        ("락키", "라키"),
        ("티디", "디티"),
        ("코키", "쿠키"),
        ("루나", "루너"),
        ("마크", "막"),
        ("퀵", "쿠익"),
        ("폰", "퐁"),
    ]
    for a, b in hangul_pos:
        add_pair(a, b, 1, "ko-ko", "한글 자모/음절 유사", i)
        i += 1

    negative_en = [
        ("POOKIE", "POCKET"),
        ("COOKIE", "COCKTAIL"),
        ("ROCKY", "ROCKET"),
        ("PHONE", "PHOENIX"),
        ("QUICK", "QUIET"),
        ("FONE", "FOUND"),
        ("BUNNY", "BINARY"),
        ("KITTY", "KITCHEN"),
        ("PARK", "PARTY"),
        ("MARK", "MARKET"),
        ("RIVER", "RIVAL"),
        ("LIVER", "LIVELY"),
        ("TONE", "TONIC"),
        ("DONE", "DONUT"),
        ("LIGHT", "RIGHT"),
        ("NIGHT", "EIGHT"),
        ("THING", "THINK"),
        ("SING", "SIGNAL"),
        ("BOX", "BOND"),
        ("XENO", "XMAS"),
        ("KORE", "KERNEL"),
        ("GORE", "GOLD"),
        ("TARI", "TAXI"),
        ("DARI", "DASH"),
        ("LUNA", "LUNCH"),
        ("RUNA", "RULER"),
        ("SOFTY", "SAFETY"),
        ("BESTY", "BASIC"),
        ("ROOMY", "RUMOR"),
        ("INDY", "INDEX"),
        ("AUNTY", "UNITY"),
        ("DOGGY", "DIGIT"),
        ("BIRDY", "BORDER"),
        ("PUPPY", "PAPAYA"),
        ("CUTY", "CITY"),
        ("HOKY", "HOCKEY"),
        ("COOKY", "COOKIEJAR"),
        ("POOKY", "POKER"),
        ("BOOKY", "BOOKLET"),
        ("FOOKY", "FUNKY"),
    ]
    for a, b in negative_en:
        add_pair(a, b, 0, "en-en", "철자 일부 유사하지만 호칭/구조 비유사", i)
        i += 1

    negative_cross = [
        ("POOKY", "포기"),
        ("POOKIE", "포켓"),
        ("COOKIE", "칵테일"),
        ("ROCKY", "로켓"),
        ("PHONE", "피닉스"),
        ("QUICK", "콰이어트"),
        ("MARK", "마켓"),
        ("LUNA", "런치"),
        ("RIVER", "라이벌"),
        ("BOX", "본드"),
        ("TONE", "토닉"),
        ("DONE", "도넛"),
    ]
    for a, b in negative_cross:
        add_pair(a, b, 0, "cross", "교차 스크립트이지만 관행 발음 불일치(준실제 hard negative)", i)
        i += 1

    negative_ko = [
        ("쿠키", "쿠폰"),
        ("쿠키", "쿠션"),
        ("로키", "로봇"),
        ("로키", "로고"),
        ("부키", "부동"),
        ("후키", "후드"),
        ("푸키", "푸딩"),
        ("라키", "라면"),
        ("루나", "루프"),
        ("마크", "마술"),
        ("퀵", "퀸"),
        ("폰", "폼"),
        ("락키", "라면"),
        ("록키", "로켓"),
        ("라떼", "라면"),
        ("코키", "코끼리"),
        ("노키", "노트"),
        ("러키", "러브"),
        ("꾸키", "꾸밈"),
        ("티디", "티켓"),
    ]
    for a, b in negative_ko:
        add_pair(a, b, 0, "ko-ko", "한글 일부 글자만 겹치지만 비유사", i)
        i += 1

    return pairs


EVAL_PAIRS = build_eval_pairs()

