# Name: introspectable.py
# Path: tools/lib/gdacore/src/gdacore/introspectable.py
# Version: 1.0.0+build.rc1

"""Provide centralized runtime introspection mixin for self-documenting archive components."""

from __future__ import annotations

__version__ = "1.0.0+build.rc1"

import inspect
from collections.abc import Callable
from typing import Any


class _HybridHelpDescriptor:
    """Enable .help() to function seamlessly as both a classmethod and an instancemethod."""

    def __get__(self, instance: Any, owner: type) -> Callable[..., None]:
        """Bind the introspection dispatcher to the target class or instance.

        Args:
            instance: Active instance invoking help(), or None if called on the class.
            owner: Class type declaring or inheriting IntrospectableMixin.

        Returns:
            Callable dispatcher executing member inspection or public directory listing.
        """
        def help_dispatcher(member_name: str | None = None) -> None:
            cls = owner

            if member_name and member_name.strip():
                clean_name = member_name.strip()
                cls_attr = getattr(cls, clean_name, None)
                if cls_attr is None:
                    print(f"Error: '{clean_name}' is not a recognized member of {cls.__name__}.")
                    return

                if isinstance(cls_attr, property):
                    doc = inspect.getdoc(cls_attr.fget) or "No documentation provided."
                    if instance is not None:
                        try:
                            current_val = getattr(instance, clean_name)
                        except Exception as err:
                            current_val = f"<Error evaluating: {err}>"
                    else:
                        current_val = "<Unbound property: call help() on an instance to inspect value>"

                    print(f"\nHelp on property '{cls.__name__}.{clean_name}':")
                    print(f"  Current Value: {current_val}")
                    print(f"  Description:   {doc}\n")
                elif callable(cls_attr):
                    doc = inspect.getdoc(cls_attr) or "No documentation provided."
                    target_callable = getattr(instance, clean_name) if instance is not None else cls_attr
                    try:
                        sig = inspect.signature(target_callable)
                    except (ValueError, TypeError):
                        sig = "(...)"
                    print(f"\nHelp on method '{cls.__name__}.{clean_name}':")
                    print(f"  Signature:   {clean_name}{sig}")
                    print(f"  Description: {doc}\n")
                return

            props, meths = cls._get_public_members()
            print(f"\n=== {cls.__name__} Public Directory ===")

            if props:
                print("\nProperties (Attributes & Paths):")
                for p in props:
                    prop_obj = getattr(cls, p, None)
                    doc = inspect.getdoc(prop_obj.fget) if isinstance(prop_obj, property) else None
                    first_line = doc.split("\n")[0] if doc else "No description available."
                    print(f"  • {p:<25} - {first_line}")

            if meths:
                print("\nCallable Methods:")
                for m in meths:
                    meth_obj = getattr(cls, m, None)
                    doc = inspect.getdoc(meth_obj) if callable(meth_obj) else None
                    first_line = doc.split("\n")[0] if doc else "No description available."
                    print(f"  • {m:<25} - {first_line}")

            print("\nTip: Call .help('name') on your instance or class for full details.\n")

        return help_dispatcher


class IntrospectableMixin:
    """Provide dual class- and instance-level runtime directory inspection.

    Subclasses inherit the self-documenting .help() method, allowing operators
    to inspect public properties, methods, call signatures, and docstring contracts
    in interactive REPL sessions or CLI utilities.

    Attributes:
        help: Descriptor dispatcher providing indexed directory output or detailed member help.
    """

    help = _HybridHelpDescriptor()

    @classmethod
    def _get_public_members(cls) -> tuple[list[str], list[str]]:
        """Discover and categorize public properties and callable methods on the class.

        Returns:
            Tuple containing a sorted list of property names and a sorted list of callable method names.
        """
        properties: list[str] = []
        methods: list[str] = []

        for name in dir(cls):
            if name.startswith("_") or name == "help":
                continue

            attr_class_level = getattr(cls, name, None)
            if isinstance(attr_class_level, property):
                properties.append(name)
            elif callable(attr_class_level):
                methods.append(name)

        return sorted(properties), sorted(methods)