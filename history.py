#!/usr/bin/python3

import json
import requests
from pprint import pprint
from datetime import datetime, timedelta
import sys
import pyarr
import logging
import time

def get_episodes(id):
    if type(id) == int:
        eps = sonarr.get_episodes_by_series_id(id_=1433)
    elif id in series:
        eps = sonarr.get_episodes_by_series_id(id_=series[id])
    else:
        logging.warning(f'Cannot find: {id}')
        return False
    
    episodes = {}
    # make episode list searchable
    for ep in eps:
        if ep["seasonNumber"] not in episodes:
            episodes[ep["seasonNumber"]] = {ep["episodeNumber"]:ep}
        else:
            episodes[ep["seasonNumber"]][ep["episodeNumber"]] = ep
    return episodes

def get_queue(id):
    queue = {}
    for q in sonarr.get_queue():
        queue[q['episode']['id']] = q
    if id in queue:
        return queue[id]
    return False

def check_future(play):
    if play["title"] not in series:
        logging.warning(f'"{play["title"]}" not found in Sonarr data, skipping.')
        return True
    files = get_episodes(play["title"])
    
    # iterate over episodes until we get to the one we care about, start checking/reporting
    i = 1
    care = False
    for season in files:
        if season == 0 and config["skip_specials"]:
            continue
        for ep in files[season]:
            if season == play["season"] and ep == play["episode"]:
                care = int(i)
            if care and care+config["episodes_to_check"] >= i:
                e = files[season][ep]
                file_string = format_play({"title":play["title"],"season":season,"episode":ep})
                # Check if file already exists
                if e["hasFile"]:
                    logging.debug(f'{file_string} already on disk')
                elif (datetime.now()-datetime.strptime(e["airDate"],'%Y-%m-%d')).days > 0:
                    logging.info(f'{file_string} not on disk')
                    if not e["monitored"]:
                        logging.debug(f'{file_string} not monitored')
                        sonarr.upd_episode(id_=e["id"], data={"monitored": True})
                        logging.info(f'{file_string} has been set to monitored')
                    if get_queue(e["id"]):
                        logging.info(f'{file_string} already queued')
                        to_jump.append(e["id"])
                    else:
                        logging.debug(f'{file_string} Searching...')
                        queue_episode(e["id"])
                else:
                    logging.debug(f'{file_string} hasn\'t aired yet')
            i += 1

def queue_episode(id):
    if id in already_searched:
        logging.debug(f'{id} requested multiple times, ignored.')
        return False
    already_searched.append(id)
    releases = sonarr.get_releases(id_=id)
    for release in releases:
        if not release["rejected"] and release["protocol"] == "usenet":
            logging.debug(f'Sending {release["infoUrl"]} to the queue')
            notify(subject="Release added to queue based on user activity", body=f'{release["title"]}')
            sonarr.download_release(guid = release["guid"], indexer_id = release["indexerId"])
            to_jump.append(id)
            return True
    logging.debug(f'{len(releases)} found but were all rejected or not on usenet.')

def force_episode(id):
    params = {"mode":"queue",
              "name":"priority",
              "apikey":config["sabnzbd"]["key"],
              "output":"json",
              "value":id,
              "value2":2}
    requests.get(config["sabnzbd"]["url"],params=params)

def format_play(play):
    return f'{play["title"]} - S{str(play["season"]).zfill(2)}E{str(play["episode"]).zfill(2)}'

def notify(subject, body):
    if "notifier" in config["tautulli"]:
        n = config["tautulli"]["notifier"]
        if type(n) != int:
            logging.warning("Tautulli notification agent set incorrectly. Fix or remove the 'notifier' entry")
            return False
        params = {"apikey":config["tautulli"]["key"],
                  "cmd": "notify",
                  "notifier_id": n,
                  "subject": subject,
                  "body": body}
        r = requests.get(config["tautulli"]["url"],params = params)
        if r.status_code == 200:
            return True
        return False

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

# Get existing show data
logging.info("Getting series IDs from Sonarr")
q_time = time.time()
sonarr = pyarr.sonarr.SonarrAPI(host_url=config["sonarr"]["url"], api_key=config["sonarr"]["key"])
s_raw = sonarr.get_series()
logging.debug(f'Got {len(s_raw)} series in {round(time.time() - q_time,2)}s')
logging.info("Processing series from Sonarr")
series = {}
for s in s_raw:
    series[s["title"]] = s["id"]
logging.debug(f'Processed into {len(series)} series')
if len(s_raw) != len(series):
    logging.warning("Sonarr series count and processed series count do not match")

# Get episode plays in the last day (ish)
logging.info("Getting play data from Tautulli")
params = {"apikey":config["tautulli"]["key"],
          "cmd":"get_history",
          "after":datetime.strftime(datetime.now() - timedelta(config["days_to_check"]), '%Y-%m-%d'),
          "media_type":"episode",
          "length": 1000}
r = requests.get(config["tautulli"]["url"],params = params)
plays = []
for play in r.json()["response"]["data"]["data"]:
    p = {"title": play["grandparent_title"],
         "season": play["parent_media_index"],
         "episode": play["media_index"]}
    plays.append(p)
logging.debug(f'Got {len(plays)} plays')

#pprint(get_queue(131434))

to_jump = []
already_searched = []

for play in plays:
    logging.info(format_play(play))
    check_future(play)

logging.info(f'{len(to_jump)} jobs hopefully pushed to the download queue.')

logging.debug("Refreshing queue within Sonarr")
sonarr.post_command(name="RefreshMonitoredDownloads")
logging.debug("Giving the refresh time to run")
time.sleep(3)
logging.debug("Refresh hopefully complete")

b = 0
for episode in to_jump:
    q = get_queue(episode)
    if q:
        force_episode(q["downloadId"])
        logging.debug(f'Bumped {q["downloadId"]} for {q["title"]}')
        b += 1
    else:
        logging.warning(f'Can\'t bump {episode}. Doesn\'t seem to be in the queue.')
logging.info(f'Bumped {b}/{len(to_jump)} queued items')