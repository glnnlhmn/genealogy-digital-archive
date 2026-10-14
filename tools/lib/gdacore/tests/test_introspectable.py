# Name: test_introspectable.py
# Path: tools/lib/gdacore/tests/test_introspectable.py
# Version: 1.0.0+build.rc1

"""Unit test suite validating runtime introspection mixin behavior.

Operational Role:
    Validates IntrospectableMixin member discovery, property reflection,
    callable inspection, docstring extraction, error boundaries, signature
    fallback resolution, static attribute branches, and output formatting.

Test Structure & Protocol:
    - Atomized tests: 1:1 assertion mapping per test function.
    - Fully decorated: Explicitly marked with @pytest.mark.unit, @pytest.mark.smoke, @pytest.mark.regression.
    - Dependencies: Pure in-memory inspect descriptors with zero disk I/O.
"""

from __future__ import annotations

import pytest

from gdacore.introspectable import IntrospectableMixin

__version__ = "1.0.0+build.rc1"


class OpaqueCallable:
    """Callable whose signature cannot be introspected via inspect.signature."""

    __call__ = "not_a_function"


class SampleService(IntrospectableMixin):
    """Sample test service inheriting introspection capabilities."""

    STATIC_ATTR = "non_callable_constant"
    opaque_action = OpaqueCallable()

    def __init__(self, value: str = "prod") -> None:
        self._value = value

    @property
    def endpoint_path(self) -> str:
        """Resolve active endpoint destination path.

        Detailed notes regarding protocol endpoints.
        """
        return f"/api/v1/{self._value}"

    @property
    def failing_property(self) -> str:
        """Simulate dynamic property evaluation failure."""
        raise RuntimeError("Dynamic evaluation crashed.")

    @property
    def undocumented_property(self) -> str:
        return "undocumented_val"

    def execute_action(self, target_id: str, flag: bool = False) -> bool:
        """Execute a designated operational action on target entity.

        Args:
            target_id: Target entity identifier.
            flag: Secondary operational toggle.
        """
        return flag

    def undocumented_action(self) -> None:
        pass

    def _private_worker(self) -> None:
        """Private internal worker."""
        pass


class MethodsOnlyService(IntrospectableMixin):
    """Service containing only callable methods to test empty properties branch."""

    def single_action(self) -> None:
        """Execute solo action."""
        pass


class PropertiesOnlyService(IntrospectableMixin):
    """Service containing only property descriptors to test empty methods branch."""

    @property
    def solo_property(self) -> str:
        """Solo property description."""
        return "data"


# ==============================================================================
# GROUP 1: Member Discovery Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_member_discovery_includes_declared_properties() -> None:
    """Verify _get_public_members discovers public properties."""
    props, _ = SampleService._get_public_members()
    assert "endpoint_path" in props


@pytest.mark.unit
@pytest.mark.smoke
def test_member_discovery_includes_declared_callable_methods() -> None:
    """Verify _get_public_members discovers public callable methods."""
    _, meths = SampleService._get_public_members()
    assert "execute_action" in meths


@pytest.mark.unit
@pytest.mark.regression
def test_member_discovery_excludes_static_non_callable_attributes() -> None:
    """Verify _get_public_members ignores non-property, non-callable static attributes."""
    props, meths = SampleService._get_public_members()
    assert "STATIC_ATTR" not in props and "STATIC_ATTR" not in meths


@pytest.mark.unit
@pytest.mark.regression
def test_member_discovery_excludes_private_and_dunder_methods() -> None:
    """Verify _get_public_members filters out private members."""
    props, meths = SampleService._get_public_members()
    assert "_private_worker" not in props and "_private_worker" not in meths


@pytest.mark.unit
@pytest.mark.regression
def test_member_discovery_excludes_help_method_itself() -> None:
    """Verify _get_public_members omits help to avoid recursive self-reference."""
    _, meths = SampleService._get_public_members()
    assert "help" not in meths


@pytest.mark.unit
@pytest.mark.regression
def test_introspectable_ignores_non_callable_class_attributes() -> None:
    """Verify public non-callable constants are not classified as methods or properties."""
    class SampleWithConstant(IntrospectableMixin):
        CONSTANT_VAL = 42

    props, methods = SampleWithConstant._get_public_members()
    assert "CONSTANT_VAL" not in props
    assert "CONSTANT_VAL" not in methods


# ==============================================================================
# GROUP 2: Directory Overview Formatting Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_help_overview_renders_header(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help() renders the class name header."""
    service = SampleService()
    service.help()
    captured = capsys.readouterr().out
    assert "=== SampleService Public Directory ===" in captured


@pytest.mark.unit
@pytest.mark.smoke
def test_help_overview_renders_properties_list(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help() renders property member lines with summaries."""
    service = SampleService()
    service.help()
    captured = capsys.readouterr().out
    assert "• endpoint_path             - Resolve active endpoint destination path." in captured


@pytest.mark.unit
@pytest.mark.smoke
def test_help_overview_renders_methods_list(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help() renders method member lines with summaries."""
    service = SampleService()
    service.help()
    captured = capsys.readouterr().out
    assert "• execute_action            - Execute a designated operational action on target entity." in captured


@pytest.mark.unit
@pytest.mark.regression
def test_help_overview_renders_fallback_for_undocumented_callable(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help() renders fallback text when docstrings are missing."""
    service = SampleService()
    service.help()
    captured = capsys.readouterr().out
    assert "• undocumented_action       - No description available." in captured


@pytest.mark.unit
@pytest.mark.regression
def test_help_overview_skips_properties_section_when_none_exist(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help() omits properties section when no properties are defined."""
    service = MethodsOnlyService()
    service.help()
    captured = capsys.readouterr().out
    assert "Properties (Attributes & Paths):" not in captured


@pytest.mark.unit
@pytest.mark.regression
def test_help_overview_skips_methods_section_when_none_exist(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help() omits methods section when no callable methods are defined."""
    service = PropertiesOnlyService()
    service.help()
    captured = capsys.readouterr().out
    assert "Callable Methods:" not in captured


@pytest.mark.unit
@pytest.mark.regression
def test_help_overview_triggered_by_whitespace_argument(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help() with whitespace string renders overview directory."""
    service = SampleService()
    service.help("   ")
    captured = capsys.readouterr().out
    assert "=== SampleService Public Directory ===" in captured


# ==============================================================================
# GROUP 3: Detailed Property Inspection Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_help_property_renders_current_runtime_value(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(prop_name) displays evaluated runtime value on instance."""
    service = SampleService(value="staging")
    service.help("endpoint_path")
    captured = capsys.readouterr().out
    assert "Current Value: /api/v1/staging" in captured


@pytest.mark.unit
@pytest.mark.smoke
def test_help_property_renders_unbound_notice_on_class_call(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(prop_name) called on class displays unbound property notice."""
    SampleService.help("endpoint_path")
    captured = capsys.readouterr().out
    assert "Current Value: <Unbound property: call help() on an instance to inspect value>" in captured


@pytest.mark.unit
@pytest.mark.smoke
def test_help_property_renders_full_multiline_docstring(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(prop_name) displays full docstring text."""
    service = SampleService()
    service.help("endpoint_path")
    captured = capsys.readouterr().out
    assert "Detailed notes regarding protocol endpoints." in captured


@pytest.mark.unit
@pytest.mark.regression
def test_help_property_renders_fallback_when_undocumented(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(prop_name) displays fallback message when property lacks docstring."""
    service = SampleService()
    service.help("undocumented_property")
    captured = capsys.readouterr().out
    assert "Description:   No documentation provided." in captured


@pytest.mark.unit
@pytest.mark.regression
def test_help_property_handles_dynamic_exceptions_gracefully(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(prop_name) catches dynamic property evaluation failures cleanly."""
    service = SampleService()
    service.help("failing_property")
    captured = capsys.readouterr().out
    assert "<Error evaluating: Dynamic evaluation crashed.>" in captured


# ==============================================================================
# GROUP 4: Detailed Method Inspection Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_help_method_renders_callable_signature_name(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(method_name) prints method name in signature line."""
    service = SampleService()
    service.help("execute_action")
    captured = capsys.readouterr().out
    assert "Signature:   execute_action" in captured


@pytest.mark.unit
@pytest.mark.smoke
def test_help_method_renders_callable_signature_parameters(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(method_name) prints method parameters in signature line."""
    service = SampleService()
    service.help("execute_action")
    captured = capsys.readouterr().out
    assert "target_id" in captured and "flag" in captured


@pytest.mark.unit
@pytest.mark.smoke
def test_help_method_renders_docstring_description(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(method_name) prints method docstring description."""
    service = SampleService()
    service.help("execute_action")
    captured = capsys.readouterr().out
    assert "Execute a designated operational action on target entity." in captured


@pytest.mark.unit
@pytest.mark.regression
def test_help_method_renders_fallback_description_when_missing(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(method_name) falls back when method docstring is missing."""
    service = SampleService()
    service.help("undocumented_action")
    captured = capsys.readouterr().out
    assert "Description: No documentation provided." in captured


@pytest.mark.unit
@pytest.mark.regression
def test_help_method_handles_signature_resolution_failure(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(method_name) handles callables whose signature cannot be introspected."""
    service = SampleService()
    service.help("opaque_action")
    captured = capsys.readouterr().out
    assert "Signature:   opaque_action(...)" in captured


@pytest.mark.unit
@pytest.mark.regression
def test_help_handles_non_property_non_callable_member_gracefully(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(static_attr) returns cleanly without crashing."""
    service = SampleService()
    service.help("STATIC_ATTR")
    captured = capsys.readouterr().out
    assert "Error:" not in captured


@pytest.mark.unit
@pytest.mark.regression
def test_help_unrecognized_member_reports_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify help(unknown) prints error message without crashing."""
    service = SampleService()
    service.help("non_existent_member")
    captured = capsys.readouterr().out
    assert "Error: 'non_existent_member' is not a recognized member of SampleService." in captured