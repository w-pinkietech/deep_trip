"""Cached fallback responses for demo reliability.

When the LLM is unavailable or slow, these pre-written responses ensure the
demo can continue smoothly. Responses match the omotenashi tone — polite,
warm, and culturally informative Japanese.
"""

# Mapping of (location_name, query_type) -> response text.
# query_type is matched by keyword search against the user's input.
_FALLBACK_RESPONSES: dict[str, dict[str, str]] = {
    "sensoji": {
        "greeting": (
            "浅草寺へようこそ！こちらは東京で最も古いお寺で、"
            "西暦628年に創建されたと伝えられています。"
            "雷門の大きな提灯が目印ですね。何でもお聞きください。"
        ),
        "history": (
            "浅草寺は、推古天皇の時代、628年に隅田川から引き上げられた"
            "観音像を祀ったのが始まりとされています。"
            "雷門は正式には「風雷神門」と呼ばれ、風神と雷神が守護しています。"
            "仲見世通りは日本最古の商店街のひとつで、約250メートルにわたって"
            "伝統的なお土産や和菓子のお店が並んでいます。"
        ),
        "etiquette": (
            "参拝のマナーをご案内しますね。まず、山門では軽く一礼してからくぐります。"
            "本堂前の常香炉では、お線香の煙を体にあびて身を清めます。"
            "お賽銭を入れたら、二拍手一礼で参拝します。"
            "境内では帽子を取り、静かに歩くのがマナーです。"
            "写真撮影は可能ですが、本堂内部は禁止の場合がありますのでご注意ください。"
        ),
        "hidden_gem": (
            "浅草寺の裏手、少し歩いたところに「伝法院通り」という小さな路地があります。"
            "江戸の風情が残る素敵な通りで、観光客にはあまり知られていません。"
            "また、浅草寺の北側にある「待乳山聖天」もおすすめです。"
            "大根をお供えするユニークなお寺で、地元の人に愛されています。"
        ),
    },
    "shibuya": {
        "description": (
            "渋谷スクランブル交差点は、世界で最も有名な交差点のひとつです。"
            "信号が青になると、一度に最大3,000人もの人が四方八方から渡る光景は圧巻です。"
            "特に夕方から夜にかけて、巨大なスクリーンのネオンに照らされた"
            "この場所は、東京のエネルギーそのものを感じられます。"
        ),
        "hachiko": (
            "ハチ公の銅像は渋谷駅の前にあります。"
            "ハチ公は1920年代に東京大学の上野英三郎教授に飼われていた秋田犬です。"
            "教授が亡くなった後も、毎日渋谷駅で帰りを待ち続けたという忠犬の物語は、"
            "日本中の人々の心を打ちました。今でも待ち合わせの定番スポットとして"
            "多くの人に親しまれています。"
        ),
        "hidden_gem": (
            "渋谷の喧騒から少し離れた場所に「奥渋谷」というエリアがあります。"
            "代々木公園の近くで、おしゃれなカフェや個性的なセレクトショップが"
            "点在する大人の隠れ家的スポットです。"
            "また、渋谷駅から徒歩10分ほどの「金王八幡宮」は、"
            "渋谷の喧騒が嘘のような静寂に包まれた穴場の神社です。"
        ),
    },
    "meiji": {
        "history": (
            "明治神宮は、明治天皇と昭憲皇太后をお祀りする神社で、"
            "1920年に創建されました。約70万平方メートルの広大な森に囲まれ、"
            "全国から届けられた約10万本の木々が植えられています。"
            "都会の真ん中にありながら、深い森の静けさを感じられる特別な場所です。"
        ),
        "etiquette": (
            "神社の参拝マナーをご案内します。鳥居をくぐる前に軽く一礼します。"
            "参道は中央を避け、端を歩きましょう。中央は神様の通り道とされています。"
            "手水舎では、左手、右手の順に清め、最後に口をすすぎます。"
            "お参りは二礼二拍手一礼が基本です。"
        ),
        "hidden_gem": (
            "明治神宮の敷地内にある「明治神宮御苑」をご存知ですか？"
            "入園料500円で入れる美しい日本庭園で、特に6月の花菖蒲の時期は見事です。"
            "また、本殿の裏手にある「宝物殿」周辺の芝生広場は、"
            "地元の人しか知らない穴場の休憩スポットです。"
        ),
    },
    "_general": {
        "hidden_gem": (
            "この辺りには素敵な隠れたスポットがいくつかあります。"
            "地元の人に愛されている小さな神社や、路地裏の昔ながらの喫茶店など、"
            "ガイドブックには載っていない魅力的な場所をご案内できますよ。"
            "具体的なご希望があれば、ぜひお聞かせください。"
        ),
        "greeting": (
            "こんにちは！Deep Tripへようこそ。"
            "日本の素敵な場所をご一緒に巡りましょう。"
            "気になることがあれば、何でもお気軽にお聞きくださいね。"
        ),
    },
}

# Keywords used to determine query_type from user input
_QUERY_KEYWORDS: dict[str, list[str]] = {
    "greeting": ["こんにちは", "hello", "hi", "はじめまして", "ようこそ"],
    "history": ["歴史", "history", "由来", "起源", "教えて", "について", "どんな", "what is", "tell me about"],
    "etiquette": ["マナー", "etiquette", "参拝", "作法", "ルール", "manner", "how to visit", "rules"],
    "hachiko": ["ハチ公", "hachiko", "忠犬", "銅像", "statue"],
    "description": ["どんなところ", "what is", "describe", "スクランブル", "crossing", "場所"],
    "hidden_gem": ["隠れ", "hidden", "おすすめ", "recommend", "穴場", "知られていない", "gem", "secret"],
}


def _match_query_type(text: str) -> str | None:
    """Match user text to a query type using keyword search."""
    text_lower = text.lower()
    for query_type, keywords in _QUERY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                return query_type
    return None


def get_fallback_response(location_name: str | None, query_text: str) -> str | None:
    """Return a cached fallback response for the given location and query.

    Args:
        location_name: Normalized location key (e.g. "sensoji", "shibuya", "meiji")
                       or None for general responses.
        query_text: The user's raw query text.

    Returns:
        A pre-written Japanese response string, or None if no fallback matches.
    """
    query_type = _match_query_type(query_text)
    if not query_type:
        return None

    # Try location-specific response first
    if location_name and location_name in _FALLBACK_RESPONSES:
        response = _FALLBACK_RESPONSES[location_name].get(query_type)
        if response:
            return response

    # Fall back to general responses
    general = _FALLBACK_RESPONSES.get("_general", {})
    return general.get(query_type)
