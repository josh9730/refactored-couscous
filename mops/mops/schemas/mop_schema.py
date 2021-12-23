{
    "login_vars": {
        "required": True,
        "type": "dict",
        "schema": {
            "jira_url": {
                "required": True,
                "nullable": True,
                "check_with": is_url,
                "dependencies": [
                    "confluence_url",
                    "cas",
                ]
            },
            "confluence_url": {
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
            },
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
    "level": {"required": True, "type": "number", "min": 0, "max": 3},
    "exec": {"required": True, "type": "string", "regex": "^(NOC)|(COR)|(SYS)"},
    "rh": {"required": False, "type": "string", "dependencies": "approval"},
    "approval": {
        "required": False,
        "type": "string",
        "regex": "^((NOC)|(COR)|(SYS))-[0-9]{3,6}$",
    },
    "impact": {
        "required": True,
        "type": "list",
    },
    "escalation": {"required": True, "type": "string"},
    "p_rollback": {
        "required": True,
        "type": "boolean",
    },
    "rollback": {
        "required": True,
        "type": "list",
    },
    "pm": {
        "required": True,
        "type": "list",
    },
    "tech_equip": {
        "required": True,
        "type": "list",
    },
    "shipping": {
        "nullable": True,
        "type": "dict",
        "keysrules": {
            "type": "string",
            "regex": "^((NOC)|(COR)|(SYS))-[0-9]{3,6}$",
        },
        "valuesrules": {"nullable": True, "type": "list", "schema": {"type": "string"}},
    },
    "sections": {
        "required": True,
        "type": "dict",
        "keysrules": {
            "type": "string",
        },
        "valuesrules": {
            "type": "list",
            "required": True,
            "schema": {
                "type": "dict",
                "keysrules": {"type": "string", "check_with": is_func},
            },
        },
    },
}
