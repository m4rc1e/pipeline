import gspread
import logging
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from __init__ import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("poll_production")


def main():
    credentials = ServiceAccountCredentials.from_json_keyfile_name(SHEETS_CREDS, SCOPE)
    gc = gspread.authorize(credentials)
    pipeline_doc = gc.open(PIPELINE_SHEET)

    logger.info("Getting google/fonts issues and pull requests")
    last_year = datetime.now() - timedelta(days=1000)#365)
    last_year = last_year.strftime("%Y-%m-%dT%H:%M:%SZ")
    github_data = get_github_data(since=last_year)
    logger.info("Found {} issues/prs".format(len(github_data)))

    closed_prs = github_closed_prs(github_data)
    merged_prs = github_merged_prs(closed_prs)
    families_in_production = get_families_in_production(merged_prs)

    logger.info("Updating 2019 Archive sheet")
    archive_sheet = pipeline_doc.worksheet("2019 Pushed Archived")
    append_to_sheet(archive_sheet, families_in_production)

    logger.info("Updating 2019 Sandbox sheet")
    sandbox_sheet = pipeline_doc.worksheet("2019 Sandbox Pipeline")
    remove_from_sheet(sandbox_sheet, families_in_production)


if __name__ == "__main__":
    main()

