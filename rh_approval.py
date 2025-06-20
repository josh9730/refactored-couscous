import re

import keyring
import typer
from atlassian import Jira
from rich import print, prompt

app = typer.Typer(help="Remote Hands Approvals")


def jira_auth() -> Jira:
    cas_user = keyring.get_password("cas", "user")
    cas_pass = keyring.get_password("cas", cas_user)
    jira_url = keyring.get_password("jira", "url")

    return Jira(url=jira_url, username=cas_user, password=cas_pass)


def test_ticket(ticket: str, jira: Jira) -> None:
    if not jira.issue_exists(ticket):
        print(f"Ticket `{ticket}` not found.")
        typer.Abort()


def parse_description(ticket: str, jira: Jira) -> tuple[str, str]:
    description = jira.issue_field_value(ticket, "description")
    chargeback_field = re.search("Chargeback.*:.*\n", description)
    authorization_field = re.search("Authorization:.*", description)

    charge, auth = "", ""
    if chargeback_field:
        charge = chargeback_field.group().split(":")[1].strip()
    if authorization_field:
        auth = authorization_field.group().split(":")[1].strip()

    return charge, auth


def prompt_for_vals(ticket_charge: str, ticket_auth: str) -> tuple[str, str]:
    charge = prompt.Prompt.ask("Update Chargeback", default=ticket_charge)
    auth = prompt.Prompt.ask("Update Approval", default=ticket_auth)

    return charge, auth


def add_approval_comment(ticket: str, jira: Jira, chargeback: str, approval: str) -> None:
    COMMENT = "Approved\nCharge: {}\nApproval: {}"
    jira.issue_add_comment(ticket, COMMENT.format(chargeback, approval))


def resolve_ticket(ticket: str, jira: Jira) -> None:
    status = jira.get_issue_status(ticket)
    if status != "Resolved":
        if status == "New":
            jira.issue_transition(ticket, "Open")
        jira.issue_transition(ticket, "Resolved")


def verify_and_print(ticket: str, jira: Jira) -> None:
    status = jira.get_issue_status(ticket)
    if status == "Resolved":
        print(f"\nCurrent Status: [green]{status}")
    else:
        print(f"\nCurrent Status: [red]{status}")
    print("[blue]Last Comment:")
    print(jira.issue_get_comments(ticket)["comments"][-1]["body"])


@app.command()
def approve(
    ticket: str = typer.Argument(..., help="Ticket to Approve"),
) -> None:
    jira = jira_auth()
    test_ticket(ticket, jira)
    ticket_charge, ticket_auth = parse_description(ticket, jira)
    chargeback, approval = prompt_for_vals(ticket_charge, ticket_auth)
    add_approval_comment(ticket, jira, chargeback, approval)
    resolve_ticket(ticket, jira)
    verify_and_print(ticket, jira)


if __name__ == "__main__":
    app()
