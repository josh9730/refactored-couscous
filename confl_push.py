from tools.utils import conf_login


def main():
    confluence = conf_login()

    doc = open("doc.txt").read()
    parent_page_id = "8881304"
    page_title = "HPR IPVPN"

    confluence.update_or_create(parent_page_id, page_title, doc, representation="wiki")


if __name__ == "__main__":
    main()
