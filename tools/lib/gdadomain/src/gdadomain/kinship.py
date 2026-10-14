# Name: kinship.py
# Path: tools/lib/gdadomain/src/gdadomain/kinship.py
# Version: 1.0.0+build.r1

"""Domain engine for genealogical kinship mathematics, symmetry, and graph topology.

Operational Role:
    Code-first canonical authority for reciprocal relationship mapping,
    Ahnentafel binary mathematics, consanguinity cycle detection, and
    union symmetry verification.

Dependencies:
    - Pure in-memory computation with zero registry or disk read/write I/O.
    - References controlled vocabularies directly from GDAReferenceManager.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from gdacore.introspectable import IntrospectableMixin
from gdacore.logger import GDALogger
from gdacore.reference_manager import GDAReferenceManager

__version__ =  "1.0.0+build.r1"

LOGGER = GDALogger.get_logger("gda_kinship")


@dataclass(frozen=True)
class KinshipAuditResult:
    """Outcome of evaluating reciprocal kinship symmetry between two entities."""

    is_symmetric: bool
    expected_reciprocal: Optional[str] = None
    actual_reciprocal: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None


@dataclass(frozen=True)
class UnionAuditResult:
    """Outcome of evaluating reciprocal marriage/union symmetry between two entities."""

    is_symmetric: bool
    status_match: bool
    date_match: bool
    error_code: Optional[str] = None
    message: Optional[str] = None


class KinshipEngine(IntrospectableMixin):
    """Stateless domain authority for kinship reciprocity and graph mathematics."""

    # Explicit Reciprocal Mapping: Outbound Role -> (Target Sex -> Inbound Role)
    # Sex keys normalized to 'M', 'F', and None (gender-neutral / unassigned)
    _RECIPROCAL_MAP: ClassVar[Dict[str, Dict[Optional[str], Optional[str]]]] = {
        "FATH": {"M": "CHIL", "F": "CHIL", None: "CHIL"},
        "MOTH": {"M": "CHIL", "F": "CHIL", None: "CHIL"},
        "PARENT": {"M": "CHIL", "F": "CHIL", None: "CHIL"},
        "CHIL": {"M": "FATH", "F": "MOTH", None: "PARENT"},
        "SON": {"M": "FATH", "F": "MOTH", None: "PARENT"},
        "DAUG": {"M": "FATH", "F": "MOTH", None: "PARENT"},
        "SPOU": {"M": "SPOU", "F": "SPOU", None: "SPOU"},
        "HUSB": {"M": "HUSB", "F": "WIFE", None: "SPOU"},
        "WIFE": {"M": "HUSB", "F": "WIFE", None: "SPOU"},
        "SIBL": {"M": "SIBL", "F": "SIBL", None: "SIBL"},
        "BROT": {"M": "SIBL", "F": "SIBL", None: "SIBL"},
        "SIST": {"M": "SIBL", "F": "SIBL", None: "SIBL"},
        # Contextual event/document roles are strictly non-reciprocal
        "WITN": {"M": None, "F": None, None: None},
        "OFFICIANT": {"M": None, "F": None, None: None},
        "INFORMANT": {"M": None, "F": None, None: None},
    }

    @classmethod
    def get_kinship_roles(cls) -> Set[str]:
        """Return permitted reciprocal family and contextual relationship roles."""
        return GDAReferenceManager.get_kinship_roles()

    @classmethod
    def get_union_statuses(cls) -> Set[str]:
        """Return permitted union and partnership lifecycle states."""
        return GDAReferenceManager.get_union_statuses()

    @staticmethod
    def normalize_sex(sex: Optional[str]) -> Optional[str]:
        """Normalize sex input string into 'M', 'F', or None."""
        if not sex or not isinstance(sex, str):
            return None
        cleaned = sex.strip().upper()
        if cleaned in ("M", "MALE"):
            return "M"
        if cleaned in ("F", "FEMALE"):
            return "F"
        return None

    @classmethod
    def get_reciprocal_role(
        cls,
        outbound_role: Optional[str],
        subject_sex: Optional[str] = None,
    ) -> Optional[str]:
        """Derive the expected reciprocal relationship role based on subject sex.

        Args:
            outbound_role: Asserted role from Subject -> Target (e.g., 'FATH', 'CHIL').
            subject_sex: Sex of Subject entity ('M', 'F', 'Male', 'Female', or None).

        Returns:
            Expected inverse role string, or None if unreciprocated or invalid.
        """
        if not outbound_role or not isinstance(outbound_role, str):
            return None

        role_clean = outbound_role.strip().upper()
        if role_clean not in cls._RECIPROCAL_MAP:
            return None

        sex_key = cls.normalize_sex(subject_sex)
        mapping = cls._RECIPROCAL_MAP[role_clean]
        return mapping.get(sex_key, mapping.get(None))

    @classmethod
    def audit_kinship_symmetry(
        cls,
        person_a: Dict[str, Any],
        person_b: Dict[str, Any],
    ) -> KinshipAuditResult:
        """Audit reciprocal relationship symmetry across two in-memory person dictionaries.

        Evaluates if person_a's asserted role pointing to person_b is properly
        mirrored by person_b pointing back to person_a.

        Args:
            person_a: Primary entity dictionary containing 'person_id', 'sex', 'associated_people'.
            person_b: Target entity dictionary containing 'person_id', 'sex', 'associated_people'.

        Returns:
            KinshipAuditResult indicating whether the edge is symmetric.
        """
        id_a = person_a.get("person_id")
        id_b = person_b.get("person_id")
        if not id_a or not id_b:
            return KinshipAuditResult(
                is_symmetric=False,
                error_code="MISSING_IDENTIFIER",
                message="One or both person dictionaries lack a valid 'person_id'.",
            )

        assoc_a = person_a.get("associated_people", [])
        assoc_b = person_b.get("associated_people", [])

        # Find edge A -> B
        outbound_entry = next((item for item in assoc_a if item.get("person_id") == id_b), None)
        if not outbound_entry:
            return KinshipAuditResult(
                is_symmetric=False,
                error_code="NO_OUTBOUND_RELATION",
                message=f"Entity {id_a} asserts no relationship pointing to {id_b}.",
            )

        outbound_role = outbound_entry.get("role")
        expected_reciprocal = cls.get_reciprocal_role(outbound_role, subject_sex=person_a.get("sex"))

        # Contextual roles (WITN, OFFICIANT, INFORMANT) are non-reciprocal and always pass symmetry audit
        if expected_reciprocal is None:
            return KinshipAuditResult(
                is_symmetric=True,
                expected_reciprocal=None,
                actual_reciprocal=None,
                message=f"Role '{outbound_role}' is an unreciprocated contextual assertion.",
            )

        # Find reverse edge B -> A
        inbound_entry = next((item for item in assoc_b if item.get("person_id") == id_a), None)
        if not inbound_entry:
            return KinshipAuditResult(
                is_symmetric=False,
                expected_reciprocal=expected_reciprocal,
                actual_reciprocal=None,
                error_code="MISSING_RECIPROCAL_EDGE",
                message=f"{id_a} asserts '{outbound_role}' on {id_b}, but {id_b} has no link to {id_a}.",
            )

        actual_reciprocal = inbound_entry.get("role")

        # Evaluate match (allowing gender-neutral and gender-specific equivalents to satisfy reciprocal contracts)
        is_match = False
        if actual_reciprocal == expected_reciprocal:
            is_match = True
        elif expected_reciprocal in ("FATH", "MOTH") and actual_reciprocal == "PARENT":
            is_match = True
        elif expected_reciprocal == "PARENT" and actual_reciprocal in ("FATH", "MOTH"):
            is_match = True
        elif expected_reciprocal == "CHIL" and actual_reciprocal in ("SON", "DAUG"):
            is_match = True
        elif expected_reciprocal == "SIBL" and actual_reciprocal in ("BROT", "SIST"):
            is_match = True
        elif expected_reciprocal == "SPOU" and actual_reciprocal in ("HUSB", "WIFE"):
            is_match = True

        if not is_match:
            return KinshipAuditResult(
                is_symmetric=False,
                expected_reciprocal=expected_reciprocal,
                actual_reciprocal=actual_reciprocal,
                error_code="ASYMMETRIC_KINSHIP_ROLE",
                message=(
                    f"{id_a} asserts '{outbound_role}' on {id_b} (expected reverse '{expected_reciprocal}'), "
                    f"but {id_b} asserts '{actual_reciprocal}'."
                ),
            )

        return KinshipAuditResult(
            is_symmetric=True,
            expected_reciprocal=expected_reciprocal,
            actual_reciprocal=actual_reciprocal,
        )

    @classmethod
    def audit_union_symmetry(
        cls,
        union_a: Dict[str, Any],
        union_b: Optional[Dict[str, Any]],
    ) -> UnionAuditResult:
        """Audit symmetry and attribute consistency between two union records.

        Args:
            union_a: Primary entity union record dictionary.
            union_b: Target entity union record dictionary (or None if missing).

        Returns:
            UnionAuditResult indicating validity, status match, and date alignment.
        """
        if not union_b:
            return UnionAuditResult(
                is_symmetric=False,
                status_match=False,
                date_match=False,
                error_code="MISSING_RECIPROCAL_UNION",
                message="Corresponding reciprocal union record is missing on target spouse.",
            )

        status_a = str(union_a.get("status", "UNKNOWN")).strip().upper()
        status_b = str(union_b.get("status", "UNKNOWN")).strip().upper()
        status_match = status_a == status_b

        date_a = union_a.get("marriage_date")
        date_b = union_b.get("marriage_date")
        date_match = date_a == date_b

        if not status_match:
            return UnionAuditResult(
                is_symmetric=False,
                status_match=False,
                date_match=date_match,
                error_code="UNION_STATUS_MISMATCH",
                message=f"Union status mismatch: '{status_a}' vs '{status_b}'.",
            )

        return UnionAuditResult(
            is_symmetric=True,
            status_match=True,
            date_match=date_match,
            message="Union records are reciprocally aligned.",
        )

    @classmethod
    def calculate_ahnentafel_generation(cls, ahnentafel_num: int) -> int:
        """Calculate generational distance from root subject using Ahnentafel number.

        Args:
            ahnentafel_num: Integer >= 1 (1 = Root Subject, 2 = Father, 3 = Mother, etc.).

        Returns:
            1-based integer generation number (1 = Root, 2 = Parents, 3 = Grandparents).

        Raises:
            ValueError: If ahnentafel_num < 1.
        """
        if ahnentafel_num < 1:
            raise ValueError(f"Ahnentafel number must be >= 1, got {ahnentafel_num}")
        return int(math.floor(math.log2(ahnentafel_num))) + 1

    @classmethod
    def get_ahnentafel_parents(cls, ahnentafel_num: int) -> Tuple[int, int]:
        """Compute parent Ahnentafel numbers for a given subject.

        Args:
            ahnentafel_num: Integer >= 1.

        Returns:
            Tuple of (father_ahnentafel, mother_ahnentafel).

        Raises:
            ValueError: If ahnentafel_num < 1.
        """
        if ahnentafel_num < 1:
            raise ValueError(f"Ahnentafel number must be >= 1, got {ahnentafel_num}")
        return (ahnentafel_num * 2, ahnentafel_num * 2 + 1)

    @classmethod
    def get_ahnentafel_child(cls, ahnentafel_num: int) -> Optional[int]:
        """Compute child Ahnentafel number from a parent Ahnentafel.

        Args:
            ahnentafel_num: Integer >= 1.

        Returns:
            Child Ahnentafel integer, or None if subject is Root (1).

        Raises:
            ValueError: If ahnentafel_num < 1.
        """
        if ahnentafel_num < 1:
            raise ValueError(f"Ahnentafel number must be >= 1, got {ahnentafel_num}")
        if ahnentafel_num == 1:
            return None
        return ahnentafel_num // 2

    @classmethod
    def detect_kinship_cycle(cls, edges: List[Tuple[str, str]]) -> bool:
        """Detect circular parent-child dependency loops in a directed pedigree graph.

        Args:
            edges: List of directed tuples (parent_id, child_id).

        Returns:
            True if a cycle exists (invalid genealogical topology), False if acyclic.
        """
        adjacency: Dict[str, List[str]] = {}
        all_nodes: Set[str] = set()

        for parent, child in edges:
            if parent == child:
                return True
            adjacency.setdefault(parent, []).append(child)
            all_nodes.add(parent)
            all_nodes.add(child)

        visited: Set[str] = set()
        recursion_stack: Set[str] = set()

        def _dfs(node: str) -> bool:
            visited.add(node)
            recursion_stack.add(node)

            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    if _dfs(neighbor):
                        return True
                elif neighbor in recursion_stack:
                    return True

            recursion_stack.remove(node)
            return False

        for node in all_nodes:
            if node not in visited:
                if _dfs(node):
                    return True

        return False


# Aliases for package exports
GDAKinship = KinshipEngine
GDAKinshipEngine = KinshipEngine