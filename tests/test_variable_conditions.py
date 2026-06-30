"""Tests for variable_conditions pure-function helpers."""

import pytest

from scaffoldkit.models import Blueprint, BlueprintVariable
from scaffoldkit.variable_conditions import (
    _is_truthy,
    prune_inactive_variables,
    variable_is_active,
)


def _var(name: str, *, condition: str | None = None, default=None) -> BlueprintVariable:
    return BlueprintVariable(name=name, condition=condition, default=default)


class TestIsTruthy:
    @pytest.mark.parametrize("value", [True, 1, "true", "True", "TRUE", "yes", "YES", "1", "on"])
    def test_truthy_values(self, value):
        assert _is_truthy(value) is True

    @pytest.mark.parametrize("value", ["false", "no", "0", "off", ""])
    def test_false_strings(self, value):
        assert _is_truthy(value) is False

    def test_false_bool(self):
        assert _is_truthy(False) is False

    def test_none_is_falsy(self):
        assert _is_truthy(None) is False

    def test_zero_int_is_falsy(self):
        assert _is_truthy(0) is False

    def test_nonempty_string_is_truthy(self):
        assert _is_truthy("hello") is True


class TestVariableIsActive:
    def test_no_condition_always_active(self):
        var = _var("x")
        assert variable_is_active(var, {}, {}) is True

    def test_condition_in_values_truthy(self):
        var = _var("child", condition="ctrl")
        assert variable_is_active(var, {"ctrl": True}, {}) is True

    def test_condition_in_values_falsy(self):
        var = _var("child", condition="ctrl")
        assert variable_is_active(var, {"ctrl": False}, {}) is False

    def test_cycle_detected_returns_false(self):
        # condition_name "a" is already in the `seen` set — cycle guard at line 25 fires
        var = _var("b", condition="a")
        assert variable_is_active(var, {}, {}, seen={"a"}) is False

    def test_inactive_controller_makes_child_inactive(self):
        # ctrl depends on gate; gate=False → ctrl inactive → child inactive (line 31)
        ctrl = _var("ctrl", condition="gate")
        child = _var("child", condition="ctrl")
        definitions = {"ctrl": ctrl, "child": child}
        assert variable_is_active(child, {"gate": False}, definitions) is False

    def test_none_controller_returns_false(self):
        # condition references a name absent from definitions and values (lines 36-37)
        var = _var("child", condition="nonexistent")
        assert variable_is_active(var, {}, {}) is False

    def test_falls_back_to_controller_default_true(self):
        # condition_name not in values; falls through to _is_truthy(controller.default) (line 39)
        ctrl = _var("ctrl", default=True)
        child = _var("child", condition="ctrl")
        definitions = {"ctrl": ctrl}
        assert variable_is_active(child, {}, definitions) is True

    def test_falls_back_to_controller_default_false(self):
        ctrl = _var("ctrl", default=False)
        child = _var("child", condition="ctrl")
        definitions = {"ctrl": ctrl}
        assert variable_is_active(child, {}, definitions) is False


class TestPruneInactiveVariables:
    def _blueprint(self, *variables: BlueprintVariable) -> Blueprint:
        return Blueprint(name="test", display_name="Test", variables=list(variables))

    def test_drops_inactive_variable(self):
        ctrl = _var("ctrl")
        child = _var("child", condition="ctrl")
        bp = self._blueprint(ctrl, child)
        pruned = prune_inactive_variables(bp, {"ctrl": False, "child": "val"})
        assert "child" not in pruned
        assert "ctrl" in pruned

    def test_keeps_active_variable(self):
        ctrl = _var("ctrl")
        child = _var("child", condition="ctrl")
        bp = self._blueprint(ctrl, child)
        pruned = prune_inactive_variables(bp, {"ctrl": True, "child": "val"})
        assert "child" in pruned
        assert pruned["child"] == "val"

    def test_unconditional_variable_always_kept(self):
        var = _var("plain")
        bp = self._blueprint(var)
        pruned = prune_inactive_variables(bp, {"plain": "hello"})
        assert pruned["plain"] == "hello"

    def test_missing_value_not_added_by_prune(self):
        var = _var("x")
        bp = self._blueprint(var)
        pruned = prune_inactive_variables(bp, {})
        assert "x" not in pruned
