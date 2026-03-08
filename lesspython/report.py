from typing import Dict

import yaml

from lesspython.core import GroupSortKey, ScanReport


def format_yaml_report(report: ScanReport) -> str:
    groups_sorted = sorted(
        report.groups,
        key=lambda item: GroupSortKey(
            count_desc=-len(item.occurrences),
            path_str=str(item.occurrences[0].path),
            lineno=item.occurrences[0].lineno,
            end_lineno=item.occurrences[0].end_lineno,
            hash_value=item.hash_value,
        ),
    )
    payload: Dict[str, object] = {
        "python_files": report.python_files,
        "errors": [
            {"path": str(entry.path), "message": entry.message}
            for entry in report.errors
        ],
        "groups": [
            {
                "occurrences": len(group.occurrences),
                "fragments": [
                    {
                        "path": str(occ.path),
                        "start": occ.lineno,
                        "line_count": occ.line_count,
                    }
                    for occ in group.occurrences
                ],
            }
            for group in groups_sorted
        ],
    }
    return yaml.safe_dump(payload, sort_keys=False)
