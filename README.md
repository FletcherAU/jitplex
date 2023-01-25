# Plex Just-In-Time

This script attempts to download episodes that are likely going to be watched by plex users in the near future.

It specifically requires a setup that utilises:
* [Tautulli](https://github.com/Tautulli/Tautulli) to get watch history
* [Sonarr](https://github.com/Sonarr/Sonarr) to manage episode files/indexers
* [SABnzbd](https://github.com/sabnzbd/sabnzbd) to manage downloads

## Installation

* Clone the repo.
* Run `pip install -r requirements.txt`.
* Copy `config.json.example` to `config.json` and updated values as below.
* Run via cron.

## Options

* Exclude `URL_BASE` from Tautulli/Sonarr/SABnzbd if not used.
* Set API keys as appropriate.
* Set `days_to_check` to the number of days of viewing history you'd like to process. 2 is a safe number if you're running the script once a day.
* Set `episodes_to_check` to how many future episodes should be checked/downloaded. eg. If set to 3 and S01E01 is played then episodes 2, 3, and 4 will be checked. This number is entirely going to depend on your plex activity, download speed etc.
* Set `skip_specials` to either `true` or `false` depending on whether they should be considered. This can be advantageous if the coverage or accuracy of specials on your provider is subpar.

## Running

Start with `-v` to see generally what the script is doing `-vv` if there's an issue. Issues that require your attention will be raised as `WARNING`

## Notes

* Due to an issues in [Pyarr](https://github.com/totaldebug/pyarr) this script won't set episodes as monitored if they aren't already. It'll raise a warning instead for now. (Sonarr changed the way a specific API works, Pyarr [fixed the issue](https://github.com/totaldebug/pyarr/issues/108) but hasn't backported the fix to the currently stable version - 3.1.3)
* The script queries Sonarr for all series when first running. On larger setups this can take 10+s. Timing of this query is included in `-vv`.
