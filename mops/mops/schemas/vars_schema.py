{
    "jira_url": {
        "type": "string",
        "required": True,
        "check_with": is_url,
        "dependencies": [
            "confluence_url",
            "cas",
            "ic_url"
        ]
    },
    "confluence_url": {
        "type": "string",
        "required": True,
        "check_with": is_url,
        "dependencies": [
            "jira_url",
            "cas",
            "ic_url"
        ]
    },
    "cas": {
        "type": "string",
        "required": True,
        "dependencies": [
            "confluence_url",
            "jira_url",
            "ic_url"
        ]
    },
    "ic_url": {
        "type": "string",
        "required": True,
        "dependencies": [
            "confluence_url",
            "jira_url",
            "cas",
        ]
    }
}