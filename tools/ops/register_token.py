#!/usr/bin/env python3
# Path: tools/ops/register_token.py
"""
auto/op_tools/register_token.py: Archival Token Registration Tool
Safely appends validated tokens, aliases, and controlled vocabularies to _token_registry.json.
"""

import argparse
import json
import sys
from pathlib import Path

REGISTRY_PATH = Path("schemas/naming/_token_registry.json")

# Token categories modeled as lists
LIST_VOCABULARIES = {
    "counties",
    "conflicts",
    "award_categories",
    "diploma_levels",
    "other_categories",
    "news_classifications",
    "record_types"
}

# Token categories modeled as key-value mappings
DICT_VOCABULARIES = {
    "states",
    "jurisdictions",
    "pub_codes"
}

def load_registry(path: Path) -> dict:
    if not path.exists():
        print(f"Error: Token registry not found at {path.resolve()}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_registry(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Successfully updated token registry: {path}")

def register_token(vocabulary: str, key: str, value: str = None):
    registry = load_registry(REGISTRY_PATH)

    if vocabulary in LIST_VOCABULARIES:
        items = registry.get(vocabulary, [])
        if key in items:
            print(f"Token '{key}' already exists in '{vocabulary}'. No changes made.")
            return
        items.append(key)
        if vocabulary in {"counties", "record_types", "other_categories"}:
            items.sort()
        registry[vocabulary] = items
        print(f"Registered token '{key}' to list '{vocabulary}'.")

    elif vocabulary in DICT_VOCABULARIES:
        mapping = registry.get(vocabulary, {})
        if key in mapping:
            existing_target = mapping[key]
            if existing_target == value:
                print(f"Mapping '{key}': '{value}' already exists in '{vocabulary}'. No changes made.")
                return
            print(f"Updating '{key}' in '{vocabulary}': '{existing_target}' -> '{value}'")
        else:
            print(f"Registered mapping '{key}': '{value}' in '{vocabulary}'.")
        
        mapping[key] = value
        # Alphabetize dictionary keys to keep version control diffs clean
        registry[vocabulary] = dict(sorted(mapping.items(), key=lambda x: x[0].lower()))

    else:
        valid_vocabs = sorted(list(LIST_VOCABULARIES | DICT_VOCABULARIES))
        print(f"Error: Unknown vocabulary '{vocabulary}'. Must be one of: {', '.join(valid_vocabs)}", file=sys.stderr)
        sys.exit(1)

    save_registry(REGISTRY_PATH, registry)

def main():
    parser = argparse.ArgumentParser(
        description="Append a controlled token or jurisdiction mapping to schemas/naming/_token_registry.json."
    )
    parser.add_argument(
        "vocabulary",
        help="Target controlled vocabulary (e.g., jurisdictions, counties, pub_codes, states, other_categories)"
    )
    parser.add_argument(
        "key",
        help="Token name, jurisdiction alias, or dictionary key"
    )
    parser.add_argument(
        "value",
        nargs="?",
        default=None,
        help="Target canonical value for dictionary vocabularies (if omitted for 'jurisdictions', defaults to key)"
    )

    args = parser.parse_args()

    # Convenience shortcut: If registering a jurisdiction without an alias, map to itself
    if args.vocabulary == "jurisdictions" and not args.value:
        args.value = args.key
    elif args.vocabulary in DICT_VOCABULARIES and not args.value:
        print(f"Error: Vocabulary '{args.vocabulary}' requires both key and value.", file=sys.stderr)
        sys.exit(1)

    register_token(args.vocabulary, args.key, args.value)

if __name__ == "__main__":
    main()