import requests
import logging
import sys
import json

level = logging.WARNING
if len(sys.argv) > 1:
    levels = {"-v":logging.INFO,"-vv":logging.DEBUG}
    if sys.argv[1] in levels:
        level = levels[sys.argv[1]]
    else:
        print(f'history.py [{"|".join(levels.keys())}]')
        sys.exit(1)
logging.basicConfig(format='%(levelname)s:%(message)s', level=level)

logging.info("Loading config from config.json")
with open("config.json","r") as f:
    config = json.load(f)
    logging.debug("Config is valid JSON")

print(f'{config["sonarr"]["url"]}/settings/importlists')

url = f'{config["sonarr"]["url"]}/api/v3/importlistexclusion/'

start = 1
while True:
    print("Attempting to delete 50 entries...")
    for x in range(start,start+50):
        r = requests.delete(f'{url}{x}', headers={"x-api-key":config["sonarr"]["key"]})
    if input(f'Anything left at {config["sonarr"]["url"]}/settings/importlists ? [Y/n] ') != "n":
        start += 50
    else:
        break
print(f'Attempted to delete {start+50} entries.')