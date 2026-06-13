"""
Extension-registry tests — the seam that replaces hardcoded agent imports.

Guards core/registry.py: lazy "module:function" resolution, runtime register(),
and the two failure modes an operator must get a clear error for — an unknown id
and a malformed target.
"""
import pytest

from core.registry import ExtensionRegistry


def test_get_resolves_dotted_target_by_lazy_import():
    # A real, import-light stdlib target proves resolution without a fixture module.
    reg = ExtensionRegistry({"upper": "string:capwords"})
    fn = reg.get("upper")
    assert fn("hello world") == "Hello World"
    assert fn.__name__ == "capwords"


def test_register_adds_an_extension_at_runtime():
    reg = ExtensionRegistry()
    assert reg.ids() == frozenset()
    reg.register("upper", "string:capwords")
    assert "upper" in reg.ids()
    assert reg.get("upper")("a b") == "A B"


def test_ids_reflects_the_table():
    reg = ExtensionRegistry({"a": "string:capwords", "b": "string:capwords"})
    assert reg.ids() == frozenset({"a", "b"})


def test_unknown_id_raises_keyerror_listing_known_ids():
    reg = ExtensionRegistry({"known": "string:capwords"})
    with pytest.raises(KeyError) as exc:
        reg.get("missing")
    # the message must name what IS registered, so the operator can fix the call
    assert "known" in str(exc.value)


def test_malformed_target_without_colon_raises_valueerror():
    reg = ExtensionRegistry({"bad": "string.capwords"})   # dot, no colon
    with pytest.raises(ValueError) as exc:
        reg.get("bad")
    assert "module.path:function" in str(exc.value)


def test_table_is_copied_not_aliased():
    """Mutating the caller's dict after construction must not change the registry."""
    src = {"a": "string:capwords"}
    reg = ExtensionRegistry(src)
    src["b"] = "string:capwords"
    assert reg.ids() == frozenset({"a"})
