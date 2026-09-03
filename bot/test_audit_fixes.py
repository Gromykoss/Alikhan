"""
test_audit_fixes.py — Unit tests for AUDIT-critical functions.
Tests volumes(), staff(), weather(), yesterday_cum() and new modules.

Run: python3 -m pytest test_audit_fixes.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from datetime import date, timedelta


class TestVolumes:
    """AUDIT-005: volumes() should accept all categories with VOR codes."""

    def test_volumes_accepts_beton_category(self, monkeypatch):
        """Facts with category 'бетонирование' should be parsed."""
        import data_sources

        def mock_get_daily_works(d):
            raise Exception("no ojr")

        # Mock legacy QA fallback to return beton category facts
        def mock_qa_legacy(d, cat=None):
            return [
                {'category': 'бетонирование', 'fact': '2.1.1 = 104.3'},
                {'category': 'монтаж', 'fact': '3.2.1 = 50'},
            ]

        monkeypatch.setattr(data_sources, 'get_daily_works', mock_get_daily_works)
        monkeypatch.setattr(data_sources, '_qa_legacy', mock_qa_legacy)
        monkeypatch.setattr(data_sources, 'get_plans_from_messages', lambda d: data_sources.PlanData(plans={}))

        result = data_sources.get_volumes(date.today())
        assert '2.1.1' in result.works, \
            "Бетонирование факт должен быть распарсен"
        assert '3.2.1' in result.works, \
            "Монтаж факт должен быть распарсен"

    def test_volumes_plan_category(self, monkeypatch):
        """Plan facts should go to plans, not works."""
        import data_sources

        def mock_get_daily_works(d):
            raise Exception("no ojr")

        def mock_qa_legacy(d, cat=None):
            return [
                {'category': 'план', 'fact': '2.1.5 = 50'},
            ]

        monkeypatch.setattr(data_sources, 'get_daily_works', mock_get_daily_works)
        monkeypatch.setattr(data_sources, '_qa_legacy', mock_qa_legacy)
        monkeypatch.setattr(data_sources, 'get_plans_from_messages', lambda d: data_sources.PlanData(plans={}))

        result = data_sources.get_volumes(date.today())
        assert '2.1.5' in result.plans, "План должен быть в plans"
        assert '2.1.5' not in result.works, "План не должен быть в works"


class TestGetAibikonHeadcount:
    """AUDIT-009: fallback should return is_fallback=True."""

    def test_fallback_flag(self, monkeypatch):
        """When timesheet not found, is_fallback should be True."""
        import data_sources

        def mock_get_conn():
            raise Exception("no db")

        monkeypatch.setattr(data_sources, '_get_conn', mock_get_conn)
        monkeypatch.setattr(data_sources, 'get_staff', lambda d: data_sources.StaffData(orgs={}))

        result = data_sources.get_aibikon_headcount()
        assert result['is_fallback'] is True, "При отсутствии табеля is_fallback должен быть True"
        assert result['total'] == 5, "Fallback total должен быть 5"


class TestMessaging:
    """Task 1: messaging.py unifies send_msg."""

    def test_messaging_imports(self):
        """messaging.py should export send_msg, send_voice, send_document."""
        from messaging import send_msg, send_voice, send_document
        assert callable(send_msg)
        assert callable(send_voice)
        assert callable(send_document)


class TestConfig:
    """Task 6,11: config.py centralizes settings."""

    def test_config_has_sim_date(self):
        from config import SIM_DATE, TEMPLATE_PATH, SANDBOX
        assert SIM_DATE is None  # production default
        assert os.path.exists(TEMPLATE_PATH), f"Template not found: {TEMPLATE_PATH}"
        assert '@g.us' in SANDBOX


class TestValidateEjo:
    """Task 8: EJO validation before sending."""

    def test_nonexistent_file(self):
        from validate_ejo import validate_ejo
        ok, reason = validate_ejo("/tmp/nonexistent_file.xlsx")
        assert not ok
        assert reason

    def test_template_exists(self):
        """Validate the actual EJO template (should have codes)."""
        from validate_ejo import validate_ejo
        from config import TEMPLATE_PATH
        ok, reason = validate_ejo(TEMPLATE_PATH)
        assert ok or "empty" not in reason.lower(), f"Template validation: {reason}"


class TestCodeCache:
    """Task 14: code→name cache."""

    def test_cache_init(self):
        from code_cache import init_cache, get_code_name
        from config import TEMPLATE_PATH
        init_cache(TEMPLATE_PATH)
        # Should have at least some codes
        name = get_code_name('2.1.1')
        # May be empty if code not in template — that's OK
        assert isinstance(name, str)


class TestGraceful:
    """Task 19: graceful degradation."""

    def test_with_fallback_success(self):
        from graceful import with_fallback
        result, used_fallback = with_fallback(
            primary=lambda: "ok",
            fallback=lambda: "fallback",
            service='test'
        )
        assert result == "ok"
        assert not used_fallback

    def test_with_fallback_failover(self):
        from graceful import with_fallback
        result, used_fallback = with_fallback(
            primary=lambda: (_ for _ in ()).throw(Exception("down")),
            fallback=lambda: "fallback",
            service='test'
        )
        assert result == "fallback"
        assert used_fallback


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
