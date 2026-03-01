"""Tests for data.base_rates -- BaseRateProvider category base-rate database."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from data.base_provider import BaseDataProvider
from data.base_rates import BaseRateProvider
from data.historical_fetcher import MarketSample


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sample(
    category: str = "politics",
    yes_won: bool = False,
    market_id: str = "m1",
) -> MarketSample:
    """Build a minimal MarketSample for testing."""
    return MarketSample(
        market_id=market_id,
        question="Test question?",
        category=category,
        close_ts=1700000000,
        yes_token="tok_yes",
        yes_won=yes_won,
    )


# ---------------------------------------------------------------------------
# DEFAULT_RATES
# ---------------------------------------------------------------------------


class TestDefaultRates:
    """Verify the DEFAULT_RATES class constant is well-formed."""

    EXPECTED_CATEGORIES = [
        "politics",
        "crypto",
        "geopolitical",
        "sports",
        "science",
        "entertainment",
        "economics",
        "technology",
        "weather",
        "unknown",
    ]

    def test_all_expected_categories_present(self):
        for cat in self.EXPECTED_CATEGORIES:
            assert cat in BaseRateProvider.DEFAULT_RATES, f"Missing category: {cat}"

    def test_no_extra_categories(self):
        assert set(BaseRateProvider.DEFAULT_RATES.keys()) == set(self.EXPECTED_CATEGORIES)

    def test_rates_between_0_and_1(self):
        for cat, entry in BaseRateProvider.DEFAULT_RATES.items():
            rate = entry["no_rate"]
            assert 0.0 <= rate <= 1.0, f"Rate for {cat} out of range: {rate}"

    def test_each_entry_has_description(self):
        for cat, entry in BaseRateProvider.DEFAULT_RATES.items():
            assert "description" in entry, f"Missing description for {cat}"
            assert isinstance(entry["description"], str)

    def test_each_entry_has_no_rate(self):
        for cat, entry in BaseRateProvider.DEFAULT_RATES.items():
            assert "no_rate" in entry, f"Missing no_rate for {cat}"
            assert isinstance(entry["no_rate"], float)

    def test_specific_default_values(self):
        assert BaseRateProvider.DEFAULT_RATES["politics"]["no_rate"] == 0.95
        assert BaseRateProvider.DEFAULT_RATES["crypto"]["no_rate"] == 0.70
        assert BaseRateProvider.DEFAULT_RATES["sports"]["no_rate"] == 0.50
        assert BaseRateProvider.DEFAULT_RATES["unknown"]["no_rate"] == 0.65


# ---------------------------------------------------------------------------
# Construction and inheritance
# ---------------------------------------------------------------------------


class TestBaseRateProviderInit:
    """Constructor defaults and BaseDataProvider inheritance."""

    def test_name(self):
        provider = BaseRateProvider()
        assert provider.name == "base_rates"

    def test_logger_name(self):
        provider = BaseRateProvider()
        assert provider.logger.name == "data.base_rates"

    def test_inherits_base_data_provider(self):
        provider = BaseRateProvider()
        assert isinstance(provider, BaseDataProvider)

    def test_default_cache_dir(self):
        provider = BaseRateProvider()
        assert provider.cache_dir == Path("data/cache/")

    def test_custom_cache_dir(self):
        provider = BaseRateProvider(cache_dir=Path("/tmp/custom_cache"))
        assert provider.cache_dir == Path("/tmp/custom_cache")

    def test_has_in_memory_cache(self):
        provider = BaseRateProvider()
        provider.set_cached("test_key", "test_value")
        assert provider.get_cached("test_key") == "test_value"


# ---------------------------------------------------------------------------
# get_no_rate
# ---------------------------------------------------------------------------


class TestGetNoRate:
    """Look up NO resolution rate by category."""

    def test_known_category(self):
        provider = BaseRateProvider()
        assert provider.get_no_rate("politics") == 0.95

    def test_crypto_category(self):
        provider = BaseRateProvider()
        assert provider.get_no_rate("crypto") == 0.70

    def test_sports_category(self):
        provider = BaseRateProvider()
        assert provider.get_no_rate("sports") == 0.50

    def test_unknown_category_fallback(self):
        provider = BaseRateProvider()
        rate = provider.get_no_rate("nonexistent_category")
        assert rate == 0.65  # unknown fallback

    def test_case_insensitivity_upper(self):
        provider = BaseRateProvider()
        assert provider.get_no_rate("POLITICS") == 0.95

    def test_case_insensitivity_mixed(self):
        provider = BaseRateProvider()
        assert provider.get_no_rate("Crypto") == 0.70

    def test_case_insensitivity_random(self):
        provider = BaseRateProvider()
        assert provider.get_no_rate("WeAtHeR") == 0.60

    def test_empty_string_falls_back_to_unknown(self):
        provider = BaseRateProvider()
        rate = provider.get_no_rate("")
        assert rate == 0.65  # not in defaults, falls back to unknown

    def test_uses_cached_rates_when_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            # Write a cache file with custom rates
            cache_path = Path(tmpdir) / "base_rates.json"
            custom = {"politics": {"no_rate": 0.80, "description": "Custom"},
                      "unknown": {"no_rate": 0.50, "description": "Custom unknown"}}
            cache_path.write_text(json.dumps(custom))

            assert provider.get_no_rate("politics") == 0.80


# ---------------------------------------------------------------------------
# get_yes_rate
# ---------------------------------------------------------------------------


class TestGetYesRate:
    """YES rate is complement of NO rate."""

    def test_politics(self):
        provider = BaseRateProvider()
        assert provider.get_yes_rate("politics") == pytest.approx(0.05)

    def test_crypto(self):
        provider = BaseRateProvider()
        assert provider.get_yes_rate("crypto") == pytest.approx(0.30)

    def test_sports(self):
        provider = BaseRateProvider()
        assert provider.get_yes_rate("sports") == pytest.approx(0.50)

    def test_unknown_fallback(self):
        provider = BaseRateProvider()
        assert provider.get_yes_rate("nonexistent") == pytest.approx(0.35)

    def test_complement_relationship(self):
        provider = BaseRateProvider()
        for cat in BaseRateProvider.DEFAULT_RATES:
            no = provider.get_no_rate(cat)
            yes = provider.get_yes_rate(cat)
            assert no + yes == pytest.approx(1.0), f"Complement violated for {cat}"

    def test_case_insensitivity(self):
        provider = BaseRateProvider()
        assert provider.get_yes_rate("SPORTS") == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# build_from_historical
# ---------------------------------------------------------------------------


class TestBuildFromHistorical:
    """Compute empirical base rates from MarketSample data."""

    def test_computes_correct_rates(self):
        """10 politics samples: 8 resolved NO, 2 resolved YES -> no_rate=0.8."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            samples = (
                [_make_sample("politics", yes_won=False, market_id=f"n{i}") for i in range(8)]
                + [_make_sample("politics", yes_won=True, market_id=f"y{i}") for i in range(2)]
            )
            result = provider.build_from_historical(samples)

            assert result["politics"]["no_rate"] == 0.8

    def test_minimum_samples_threshold(self):
        """Categories with < 10 samples should not override defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            # Only 5 samples for crypto -> below threshold
            samples = [_make_sample("crypto", yes_won=False, market_id=f"c{i}") for i in range(5)]
            result = provider.build_from_historical(samples)

            # Crypto should keep default rate
            assert result["crypto"]["no_rate"] == 0.70

    def test_merges_with_defaults(self):
        """Empirical data for one category should not erase other defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            # 10 politics samples (all NO)
            samples = [_make_sample("politics", yes_won=False, market_id=f"p{i}") for i in range(10)]
            result = provider.build_from_historical(samples)

            # politics overridden
            assert result["politics"]["no_rate"] == 1.0
            # Other categories still present from defaults
            assert "crypto" in result
            assert result["crypto"]["no_rate"] == 0.70
            assert "sports" in result
            assert "unknown" in result

    def test_creates_cache_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            samples = [_make_sample("politics", yes_won=False, market_id=f"p{i}") for i in range(10)]
            provider.build_from_historical(samples)

            cache_path = Path(tmpdir) / "base_rates.json"
            assert cache_path.exists()
            data = json.loads(cache_path.read_text())
            assert isinstance(data, dict)
            assert "politics" in data

    def test_creates_cache_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            deep_cache = Path(tmpdir) / "deep" / "nested" / "cache"
            provider = BaseRateProvider(cache_dir=deep_cache)
            samples = [_make_sample("politics", yes_won=False, market_id=f"p{i}") for i in range(10)]
            provider.build_from_historical(samples)

            assert (deep_cache / "base_rates.json").exists()

    def test_all_yes_won(self):
        """All YES resolutions -> no_rate = 0.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            samples = [_make_sample("sports", yes_won=True, market_id=f"s{i}") for i in range(15)]
            result = provider.build_from_historical(samples)

            assert result["sports"]["no_rate"] == 0.0

    def test_all_no_won(self):
        """All NO resolutions -> no_rate = 1.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            samples = [_make_sample("crypto", yes_won=False, market_id=f"c{i}") for i in range(12)]
            result = provider.build_from_historical(samples)

            assert result["crypto"]["no_rate"] == 1.0

    def test_empty_samples_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            result = provider.build_from_historical([])

            assert result == provider.get_all_rates()
            # But cache file should still be written
            assert (Path(tmpdir) / "base_rates.json").exists()

    def test_category_normalised_to_lowercase(self):
        """Samples with uppercase categories are normalised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            samples = [_make_sample("POLITICS", yes_won=False, market_id=f"p{i}") for i in range(10)]
            result = provider.build_from_historical(samples)

            assert "politics" in result
            assert result["politics"]["no_rate"] == 1.0

    def test_multiple_categories(self):
        """Multiple categories with sufficient data all get empirical rates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            samples = (
                [_make_sample("politics", yes_won=False, market_id=f"p{i}") for i in range(10)]
                + [_make_sample("sports", yes_won=True, market_id=f"s{i}") for i in range(10)]
            )
            result = provider.build_from_historical(samples)

            assert result["politics"]["no_rate"] == 1.0
            assert result["sports"]["no_rate"] == 0.0

    def test_empirical_description_includes_sample_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            samples = [_make_sample("politics", yes_won=False, market_id=f"p{i}") for i in range(25)]
            result = provider.build_from_historical(samples)

            assert "25" in result["politics"]["description"]

    def test_new_category_from_data(self):
        """A category not in defaults can be introduced via empirical data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            samples = [_make_sample("memes", yes_won=True, market_id=f"mm{i}") for i in range(15)]
            result = provider.build_from_historical(samples)

            assert "memes" in result
            assert result["memes"]["no_rate"] == 0.0


# ---------------------------------------------------------------------------
# load_from_cache
# ---------------------------------------------------------------------------


class TestLoadFromCache:
    """Loading base rates from the JSON cache file."""

    def test_reads_valid_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            cache_path = Path(tmpdir) / "base_rates.json"
            expected = {"politics": {"no_rate": 0.90, "description": "Test"}}
            cache_path.write_text(json.dumps(expected))

            result = provider.load_from_cache()
            assert result == expected

    def test_returns_none_when_no_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            assert provider.load_from_cache() is None

    def test_returns_none_for_corrupt_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            cache_path = Path(tmpdir) / "base_rates.json"
            cache_path.write_text("this is not valid JSON {{{{")

            assert provider.load_from_cache() is None

    def test_returns_none_for_non_dict_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            cache_path = Path(tmpdir) / "base_rates.json"
            cache_path.write_text(json.dumps([1, 2, 3]))

            assert provider.load_from_cache() is None

    def test_round_trip_with_build(self):
        """build_from_historical writes cache, load_from_cache reads it back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            samples = [_make_sample("politics", yes_won=False, market_id=f"p{i}") for i in range(10)]
            built = provider.build_from_historical(samples)
            loaded = provider.load_from_cache()

            assert loaded == built


# ---------------------------------------------------------------------------
# get_all_rates
# ---------------------------------------------------------------------------


class TestGetAllRates:
    """Return rates from cache or defaults."""

    def test_returns_defaults_when_no_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            rates = provider.get_all_rates()

            assert rates == {k: dict(v) for k, v in BaseRateProvider.DEFAULT_RATES.items()}

    def test_returns_cached_rates_when_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            cache_path = Path(tmpdir) / "base_rates.json"
            custom = {"custom_cat": {"no_rate": 0.99, "description": "Custom"}}
            cache_path.write_text(json.dumps(custom))

            rates = provider.get_all_rates()
            assert rates == custom

    def test_defaults_are_deep_copies(self):
        """Mutating the returned dict should not affect DEFAULT_RATES."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            rates = provider.get_all_rates()
            rates["politics"]["no_rate"] = 0.0

            # DEFAULT_RATES should be unaffected
            assert BaseRateProvider.DEFAULT_RATES["politics"]["no_rate"] == 0.95


# ---------------------------------------------------------------------------
# categorize_question
# ---------------------------------------------------------------------------


class TestCategorizeQuestion:
    """Keyword-based market question classification."""

    def test_politics_trump(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will Trump win the election?") == "politics"

    def test_politics_biden(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will Biden be re-elected?") == "politics"

    def test_politics_senate(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will the Senate pass the bill?") == "politics"

    def test_crypto_bitcoin(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will Bitcoin reach $100k?") == "crypto"

    def test_crypto_ethereum(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will Ethereum flip Bitcoin?") == "crypto"

    def test_sports_super_bowl(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Who will win the Super Bowl?") == "sports"

    def test_sports_nba(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("NBA Finals MVP?") == "sports"

    def test_weather_rain(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will it rain in NYC tomorrow?") == "weather"

    def test_weather_hurricane(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will a hurricane hit Florida?") == "weather"

    def test_geopolitical_war(self):
        provider = BaseRateProvider()
        # "Will the war in Ukraine end?" -- use a question without "ukraine"
        # because "ukraine" contains "rain" (weather keyword) as a substring.
        assert provider.categorize_question("Will the war escalate further?") == "geopolitical"

    def test_geopolitical_nato(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will NATO expand?") == "geopolitical"

    def test_science_nasa(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will NASA launch Artemis?") == "science"

    def test_science_vaccine(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will a new vaccine be approved?") == "science"

    def test_economics_inflation(self):
        provider = BaseRateProvider()
        # Avoid "inflation" which contains "nfl" (sports keyword) as a substring.
        assert provider.categorize_question("Will the GDP grow this quarter?") == "economics"

    def test_economics_fed(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will the Fed raise rates?") == "economics"

    def test_technology_ai(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will AI replace programmers?") == "technology"

    def test_technology_apple(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will Apple release a new product?") == "technology"

    def test_entertainment_oscar(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Who will win the Oscar?") == "entertainment"

    def test_entertainment_netflix(self):
        provider = BaseRateProvider()
        # Avoid words matching earlier categories (e.g. "stock"->economics, "release"->technology).
        assert provider.categorize_question("Will Netflix win an Emmy this year?") == "entertainment"

    def test_unknown_no_match(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will aliens visit Earth?") == "unknown"

    def test_unknown_empty_string(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("") == "unknown"

    def test_case_insensitivity_upper(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("WILL TRUMP WIN THE ELECTION?") == "politics"

    def test_case_insensitivity_mixed(self):
        provider = BaseRateProvider()
        assert provider.categorize_question("Will BITCOIN Reach $100K?") == "crypto"

    def test_multi_word_keyword(self):
        """Multi-word keywords like 'super bowl' and 'interest rate' match."""
        provider = BaseRateProvider()
        assert provider.categorize_question("Super Bowl predictions?") == "sports"
        assert provider.categorize_question("Will the interest rate change?") == "economics"

    def test_first_match_wins(self):
        """When multiple categories could match, the first in iteration order wins."""
        provider = BaseRateProvider()
        # "game" matches sports; ensure it's categorized, not unknown
        result = provider.categorize_question("Will the game be played?")
        assert result != "unknown"


# ---------------------------------------------------------------------------
# fetch (entry point)
# ---------------------------------------------------------------------------


class TestFetchEntryPoint:
    """The fetch() method delegates to get_all_rates."""

    def test_fetch_returns_all_rates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            result = provider.fetch()
            expected = provider.get_all_rates()
            assert result == expected

    def test_fetch_returns_cached_when_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = BaseRateProvider(cache_dir=Path(tmpdir))
            cache_path = Path(tmpdir) / "base_rates.json"
            custom = {"test": {"no_rate": 0.42, "description": "Test"}}
            cache_path.write_text(json.dumps(custom))

            result = provider.fetch()
            assert result == custom

    def test_fetch_accepts_kwargs(self):
        """fetch() should accept kwargs without error, matching base signature."""
        provider = BaseRateProvider()
        result = provider.fetch(some_param="ignored")
        assert isinstance(result, dict)
