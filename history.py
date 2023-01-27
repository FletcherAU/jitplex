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
                continue
            if care and care+config["episodes_to_check"] >= i:
                e = files[season][ep]
                file_string = format_play({"title":play["title"],"season":season,"episode":ep})
                # Check if file already exists
                if e["hasFile"]:
                    logging.debug(f'{file_string} already on disk')
                elif (datetime.now()-datetime.strptime(e["airDate"],'%Y-%m-%d')).days > 0:
                    logging.info(f'{file_string} not on disk')
                    if not e["monitored"]:
                        logging.debug(f'{file_string} not monitored, queued for monitoring')
                        to_monitor.append(e["id"])
                    q = get_queue(e["id"])
                    if q:
                        logging.info(f'{file_string} already queued')
                        to_jump.append(e["id"])
                        to_notify.append(q)
                    else:
                        logging.debug(f'{file_string} Queued for search')
                        to_search.append(e["id"])
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
            to_notify.append(id)
            sonarr.download_release(guid = release["guid"], indexer_id = release["indexerId"])
            to_jump.append(id)
            return True
    logging.debug(f'{len(releases)} found but were all rejected or not on usenet.')

def force_episode(id,down=False):
    # Priorities: https://sabnzbd.org/wiki/configuration/3.7/api#priority
    p = 2
    if down:
        p = 0
    params = {"mode":"queue",
              "name":"priority",
              "apikey":config["sabnzbd"]["key"],
              "output":"json",
              "value":id,
              "value2":p}
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

def monitor(id):
    logging.debug(f'Monitoring {id}')
    sonarr.upd_episode(id_=id, data={"monitored": True})
    # Should probably check if this was successful
    return True

def get_download_id(episode):
    q = get_queue(episode)
    if q:
        return q["downloadId"]
    else:
        logging.warning(f'Can\'t find {episode} in queue.')
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

# Load config

logging.info("Loading config from config.json")
with open("config.json","r") as f:
    config = json.load(f)
    logging.debug("Config is valid JSON")

# Initialise Sonarr

sonarr = pyarr.sonarr.SonarrAPI(host_url=config["sonarr"]["url"], api_key=config["sonarr"]["key"])

# load cached Sonarr data

fetch = False
try:
    with open("cache.json","r") as f:
        try:
            data = json.load(f)
        except json.decoder.JSONDecodeError:
            logging.error("cache.json is not a valid JSON file and will be replaced.")
            data = {"cached": 0, "data": {}}
            fetch = True
        if data["cached"] < time.time() - 21600:
            logging.debug("Cache is older than six hours, will be refreshed.")
            fetch = True
except FileNotFoundError:
    logging.warning("cache.json not found and will be created.")
    fetch = True

if fetch == False:
    series = data["data"]
else:
    # Get existing show data
    logging.info("Getting series IDs from Sonarr")
    q_time = time.time()
    s_raw = sonarr.get_series()
    logging.debug(f'Got {len(s_raw)} series in {round(time.time() - q_time,2)}s')
    logging.info("Processing series from Sonarr")
    series = {}
    for s in s_raw:
        series[s["title"]] = s["id"]
    logging.debug(f'Processed into {len(series)} series')
    if len(s_raw) != len(series):
        logging.error("Sonarr series count and processed series count do not match")
    with open("cache.json","w") as f:
        json.dump({"cached":time.time(),"data":series},f)

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

# Set up queues
to_jump = []
already_searched = []
to_monitor = []
to_search = []
to_notify = []

for play in plays:
    logging.info(format_play(play))
    check_future(play)

if not to_monitor and not to_search and not to_notify and not to_jump:
    sys.exit()

# Set episodes to monitored. Deduped because an episode can be flagged as unmonitored multiple times.
logging.debug(f'Monitoring {len(to_monitor)} episodes')
for episode in list(dict.fromkeys(to_monitor)):
    monitor(episode)

# Search for missing episodes. Deduped because an episode can be flagged for downloading multiple times.
logging.debug(f'Searching for {len(to_search)} episodes')
for episode in list(dict.fromkeys(to_search)):
    queue_episode(episode)

logging.debug("Refreshing queue within Sonarr")
sonarr.post_command(name="RefreshMonitoredDownloads")
logging.debug("Giving the refresh time to run")
time.sleep(3)
logging.debug("Refresh hopefully complete")

# Force episodes to the top of the queue. Since we're working on each job twice they should be translated into download IDs and deduped.
to_jump_translated = []
for item in list(dict.fromkeys(to_jump)):
    to_jump_translated.append(get_download_id(item))

# Set all our jobs to normal priority because a job that's already forced won't be reforced in a way we expect
for item in to_jump_translated:
    force_episode(item, down=True)

# Reverse jump queue so that earlier episodes will end up at the top
to_jump_translated.reverse()
for item in to_jump_translated:
    force_episode(item)

# Send download notifications (if enabled)
if "notifier" in config["tautulli"] and to_notify:
    # Bundle episodes into shows
    queued = {}
    for ep in to_notify:
        if type(ep) != dict:
            q_e = get_queue(ep)
            if q_e:
                ep = q_e
            else:
                continue
        if ep["series"]["title"] not in queued:
            queued[ep["series"]["title"]] = []
        queued[ep["series"]["title"]].append((ep["episode"]["seasonNumber"],ep["episode"]["episodeNumber"]))
    
    # Format message body
    message = []
    for show in queued:
        message.append(f'{show} - ')
        for e in queued[show]:
            message[-1] += f'S{str(e[0]).zfill(2)}E{str(e[1]).zfill(2)}, '
        message[-1] = message[-1][:-2]
    message = "\n".join(message)
    # Send message
    if message:
        notify(subject="Items have been queued based on user activity", body=message)
sys.exit()