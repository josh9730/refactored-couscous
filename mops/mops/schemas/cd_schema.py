{
    "login_vars": {
        "required": True,
        "type": "dict",
        "schema": {
            "jira_url": {
                "type": "string",
                "required": True,
                "nullable": True,
                "check_with": is_url,
                "dependencies": [
                    "confluence_url",
                    "cas",
                ]
            },
            "confluence_url": {
                "type": "string",
                "required": True,
                "nullable": True,
                "check_with": is_url,
                "dependencies": [
                    "jira_url",
                    "cas",
                ]
            },
            "cas": {
                "type": "string",
                "required": True,
                "nullable": True,
                "dependencies": [
                    "confluence_url",
                    "jira_url",
                ]
            }
        }
    },
    "login_path": {
        "type": "string",
        "required": True,
        "nullable": True,
    },
    "mop_repo": {"required": True, "type": "string"},
    "page_title": {"required": True, "type": "string"},
    "parent_page_id": {"required": True, "type": "integer"},
    "ticket": {
        "required": True,
        "type": "string",
        "regex": "^((NOC)|(COR)|(SYS))-[0-9]{3,6}$",
    },
    "summary": {
        "required": True,
        "type": "list",
        "schema": {"required": True, "type": "string"},
    },
    "start_time": {
        "type": "integer",
        "min": 0,
        "max": 2400,
        "nullable": True,
        "check_with": is_24h,
        "dependencies": [
            "end_time",
            "start_day",
            "ic_url"
        ],
    },
    "end_time": {
        "type": "number",
        "min": 0,
        "max": 2400,
        "nullable": True,
        "check_with": is_24h,
        "dependencies": [
            "start_time",
            "start_day",
            "ic_url"
        ],
    },
    "start_day": {
        "check_with": is_date,
        "nullable": True,
        "dependencies": [
            "start_time",
            "end_time",
            "ic_url"
        ],
    },
    "ic_url": {
        "type": "string",
        "nullable": True,
        "dependencies": [
            "start_time",
            "end_time",
            "start_day"
        ]
    },
    "changes": {
        "required": True,
        "type": "list",
        "valuesrules": {
            "required": True,
            "type": "list",
            "schema": {"required": True, "type": "list"},
        },
    },
}
