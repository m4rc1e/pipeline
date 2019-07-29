"""Update the following sheets:
    2019 PR Pipeline,
    2019 Sandbox Pipeline,
    2019 Request Pipeline"""
import gspread
import logging
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from __init__ import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("poll_repo")


def main():
    credentials = ServiceAccountCredentials.from_json_keyfile_name(SHEETS_CREDS, SCOPE)
    gc = gspread.authorize(credentials)
    pipeline_doc = gc.open(PIPELINE_SHEET)

    logger.info("Getting google/fonts issues and pull requests")
    yesterday = datetime.now() - timedelta(days=1)
    yesterday = yesterday.strftime("%Y-%m-%dT%H:%M:%SZ")
    github_data = get_github_data(since=yesterday)
    logger.info("Found {} issues/prs".format(len(github_data)))

    logger.info("Getting open prs")
    open_prs = github_open_prs(github_data)
    logger.info("Getting closed prs")
    closed_prs = github_closed_prs(github_data)
    logger.info("Getting merged prs")
    merged_prs = github_merged_prs(closed_prs)
    logger.info("Getting family requests")
    family_requests = github_family_requests(github_data)
    logger.info("Getting closed family requests")
    closed_family_requests = github_closed_family_requests(github_data)

    logger.info("Updating 2019 PR pipeline sheet")
    pr_sheet = pipeline_doc.worksheet("2019 PR Pipeline")
    append_to_sheet(pr_sheet, open_prs)
    remove_from_sheet(pr_sheet, closed_prs)

    logger.info("Updating 2019 Sandbox sheet")
    sandbox_sheet = pipeline_doc.worksheet("2019 Sandbox Pipeline")
    append_to_sheet(sandbox_sheet, merged_prs)

    logger.info("Updating 2019 Request sheet")
    request_sheet = pipeline_doc.worksheet("2019 Request Pipeline")
    append_to_sheet(request_sheet, family_requests)
    remove_from_sheet(request_sheet, closed_family_requests)


if __name__ == "__main__":
    main()

