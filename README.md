## GF pipeline (Wip)

Update the GF Pipeline sheet based on changes made to the issues and prs in google/fonts.

Users are still able to hand modify the pipeline doc because it is never overwritten. The script will only append or remove rows. You will need to include a sheets_creds.json file in this dir. This is the credentials file for Google Sheets. You can generate this file by following: https://gspread.readthedocs.io/en/latest/oauth2.html.

This script should be run every 5 mins using a crontab. For the time being, this script is run from GF Regression. Ask Marc Foley m.foley.88 at gmail.com for more info.

