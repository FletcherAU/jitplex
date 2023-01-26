# Plex Just-In-Time

This script attempts to download episodes that are likely going to be watched by plex users in the near future.

It specifically requires a setup that utilises:
* [Tautulli](https://github.com/Tautulli/Tautulli) to get watch history
* [Sonarr](https://github.com/Sonarr/Sonarr) to manage episode files/indexers
* [SABnzbd](https://github.com/sabnzbd/sabnzbd) to manage downloads

## Installation

* Clone the repo.
* Run `pip install -r requirements.txt`. Important: This installs code from a personal repo as a stopgap see notes below.
* Copy `config.json.example` to `config.json` and updated values as below.
* Run via cron.

## Options

* Exclude `URL_BASE` from Tautulli/Sonarr/SABnzbd if not used.
* Set API keys as appropriate.
* Use `notifier` to specify a Tautulli notification agent if you want to send notifications via Tautulli when an episode is queued. Remove this entry if you don't want to send notifications.
* Set `days_to_check` to the number of days of viewing history you'd like to process. 2 is a safe number if you're running the script once a day.
* Set `episodes_to_check` to how many future episodes should be checked/downloaded. eg. If set to 3 and S01E01 is played then episodes 2, 3, and 4 will be checked. This number is entirely going to depend on your plex activity, download speed etc.
* Set `skip_specials` to either `true` or `false` depending on whether they should be considered. This can be advantageous if the coverage or accuracy of specials on your provider is subpar.

## Running

Start with `-v` to see generally what the script is doing `-vv` if there's an issue. Issues that require your attention will be raised as `WARNING`

## Notes

* When Sonarr shifted to a new API version the [Pyarr](https://github.com/totaldebug/pyarr) implementation was [updated](https://github.com/totaldebug/pyarr/issues/108) to match. Unfortunately due to unrelated issues the versions of Pyarr that includes this update have been yanked on PyPI. Until the issue is resolved upstream I've backported [the fix](https://github.com/totaldebug/pyarr/compare/v3.1.3...FletcherAU:pyarr:backport-upd_episode) on a [personal repo](https://github.com/FletcherAU/pyarr/tree/backport-upd_episode). This is the version of Pyarr set out in `requirements.txt` for now.
* The script queries Sonarr for all series when first running. On larger setups this can take a few seconds. Timing of this query is included in `-vv` to help inform run frequency decisions.