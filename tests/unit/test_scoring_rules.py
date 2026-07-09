from leadradar.tools.scoring_rules import score_lead

GOOD_VERDICT = {"needs_redesign": False}
BAD_VERDICT = {"needs_redesign": True}


def test_no_website_and_needs_redesign_scores_hot():
    business = {"website": None, "rating": 4.5}
    audit_result = {"error": "no_website", "has_ssl": False, "load_time_ms": None}

    result = score_lead(business, audit_result, BAD_VERDICT)

    assert result["score"] >= 70
    assert result["bucket"] == "HOT"


def test_good_website_scores_cold():
    business = {"website": "https://example.com", "rating": 4.8}
    audit_result = {"error": None, "has_ssl": True, "load_time_ms": 800}

    result = score_lead(business, audit_result, GOOD_VERDICT)

    assert result["score"] == 0
    assert result["bucket"] == "COLD"


def test_mixed_signals_scores_warm():
    business = {"website": "https://example.com", "rating": 3.5}
    audit_result = {"error": None, "has_ssl": False, "load_time_ms": 800}

    result = score_lead(business, audit_result, GOOD_VERDICT)

    assert result["score"] == 20  # +10 low rating, +10 no ssl
    assert result["bucket"] == "COLD"

    # bump it into WARM territory with needs_redesign too
    result = score_lead(business, audit_result, BAD_VERDICT)
    assert result["score"] == 50  # +30 needs_redesign, +10 low rating, +10 no ssl
    assert result["bucket"] == "WARM"


def test_missing_rating_awards_no_points():
    business = {"website": "https://example.com", "rating": None}
    audit_result = {"error": None, "has_ssl": True, "load_time_ms": 800}

    result = score_lead(business, audit_result, GOOD_VERDICT)

    assert result["score"] == 0


def test_missing_load_time_awards_no_slow_load_points():
    business = {"website": None, "rating": 4.5}
    audit_result = {"error": "no_website", "has_ssl": True, "load_time_ms": None}

    result = score_lead(business, audit_result, GOOD_VERDICT)

    assert result["score"] == 40  # only the no-website points


def test_bucket_boundary_exactly_70_is_hot():
    business = {"website": None, "rating": 4.5}
    audit_result = {"error": "no_website", "has_ssl": True, "load_time_ms": None}

    result = score_lead(business, audit_result, BAD_VERDICT)

    assert result["score"] == 70
    assert result["bucket"] == "HOT"


def test_bucket_boundary_exactly_40_is_warm():
    business = {"website": None, "rating": 4.5}
    audit_result = {"error": "no_website", "has_ssl": True, "load_time_ms": None}

    result = score_lead(business, audit_result, GOOD_VERDICT)

    assert result["score"] == 40
    assert result["bucket"] == "WARM"


def test_bucket_boundary_just_under_warm_is_cold():
    # 40/30/10/10/10 are all multiples of 10, so the highest score reachable
    # below the 40-point WARM threshold is 30 (a single +30 or three +10s).
    business = {"website": "https://example.com", "rating": 4.5}
    audit_result = {"error": None, "has_ssl": True, "load_time_ms": 800}

    result = score_lead(business, audit_result, BAD_VERDICT)

    assert result["score"] == 30
    assert result["bucket"] == "COLD"
