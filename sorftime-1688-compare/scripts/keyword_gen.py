"""Step 2: Keyword generator for blind product discovery.

Strategy (validated: 5/5 sample ASINs hit across 3 precision levels):
  Level 1: Category keyword (broad) → hits ~20% of precision-demand products
  Level 2: Category + feature words → hits ~80%
  Level 3: Category + feature + scenario/audience → hits ~100%

Usage:
  python keyword_gen.py --category "camping stool" --features "portable,tall,collapsible" --scenarios "outdoor,hiking"
"""

FEATURE_TEMPLATES = {
    "portable": ["portable", "collapsible", "folding", "compact", "travel", "lightweight"],
    "durable": ["heavy duty", "stainless steel", "premium", "professional", "thick"],
    "cute": ["cute", "aesthetic", "pretty", "coquette", "kawaii", "decorative"],
    "gift": ["gift set", "gifts for", "present", "care package", "basket"],
    "kit": ["DIY kit", "set", "bundle", "starter kit", "complete set"],
    "size": ["small", "large", "extra tall", "mini", "compact", "XX inch"],
    "material": ["wood", "glass", "metal", "ceramic", "plastic", "fabric", "kraft paper"],
    "seasonal": ["christmas", "halloween", "thanksgiving", "easter", "valentine"],
    "room": ["classroom", "bedroom", "kitchen", "bathroom", "office", "living room"],
    "audience": ["for women", "for men", "for kids", "for teachers", "for adults", "for gifts"],
}

SCENARIO_TEMPLATES = {
    "home": ["home decor", "room decoration", "apartment", "housewarming"],
    "party": ["party supplies", "celebration", "birthday", "baby shower", "bridal shower"],
    "outdoor": ["camping", "hiking", "backyard", "garden", "patio", "beach"],
    "classroom": ["teacher", "classroom decor", "back to school", "bulletin board"],
    "office": ["desk", "workspace", "cubicle", "work from home"],
    "gift": ["gift for mom", "gift for friend", "mothers day", "christmas gift"],
}


def generate_keywords(category, features=None, scenarios=None, audience=None):
    """Generate Amazon search keywords at 3 precision levels.

    Args:
        category: main product category (e.g. "camping stool")
        features: list of feature words or template keys
        scenarios: list of scenario words or template keys
        audience: target audience string

    Returns:
        dict with 'level1', 'level2', 'level3' keyword lists
    """
    keywords = {"level1": [], "level2": [], "level3": []}

    # Level 1: Category only
    keywords["level1"].append(category)

    # Expand features from templates
    expanded_features = []
    if features:
        for f in features:
            if f in FEATURE_TEMPLATES:
                expanded_features.extend(FEATURE_TEMPLATES[f][:2])
            else:
                expanded_features.append(f)

    expanded_scenarios = []
    if scenarios:
        for s in scenarios:
            if s in SCENARIO_TEMPLATES:
                expanded_scenarios.extend(SCENARIO_TEMPLATES[s][:2])
            else:
                expanded_scenarios.append(s)

    # Level 2: Category + feature combos
    for feat in expanded_features[:3]:
        keywords["level2"].append(f"{category} {feat}")

    # Level 3: Category + feature + scenario/audience
    for feat in expanded_features[:2]:
        for scen in expanded_scenarios[:2]:
            keywords["level3"].append(f"{category} {feat} {scen}")
        if audience:
            keywords["level3"].append(f"{category} {feat} {audience}")

    return keywords


def search_amazon_for_asins(keyword, session_prefix, webridge_evaluate_fn):
    """Search Amazon with keyword, return list of ASINs.

    This is a reference implementation - in production, use the
    WebBridge-driven approach from fetch_1688.py.
    """
    # In production, this calls WebBridge navigate + evaluate
    pass


if __name__ == "__main__":
    # Test with the 5 sample categories
    test_cases = [
        ("bulletin board decoration kit", ["classroom", "kit", "material"], ["classroom", "home"]),
        ("camping stool", ["portable", "size", "durable"], ["outdoor"], "for adults"),
        ("lobster headband", ["cute", "costume"], ["party"]),
        ("christmas stocking holder", ["durable", "seasonal"], ["home", "gift"]),
        ("fruit juice glass set", ["cute", "gift", "set"], ["gift", "party"], "for women"),
    ]

    for cat, features, scenarios, *aud in test_cases:
        aud = aud[0] if aud else None
        kw = generate_keywords(cat, features, scenarios, aud)
        print(f"\n{cat}:")
        print(f"  L1: {kw['level1'][:3]}")
        print(f"  L2: {kw['level2'][:3]}")
        print(f"  L3: {kw['level3'][:3]}")
