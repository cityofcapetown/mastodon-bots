# CoCT Mastodon Bots
This repo contains code for various [Mastodon](https://mastodon.social/) bots maintained by the Data Science branch at
the City of Cape Town. Primarily intended as demonstration applications for some public data infrastructure, they're 
also a bit of fun!

⚠ These bots are experimental, and so any and all content produced by the bots is liable to change 
without warning, and probably should be treated with a degree of scepticism. ⚠

## The bots
### CoCT Loadshedding Alerts
Code is [here](./loadshedding_bot.py)

### CoCT Service Alerts
Code is [here](./service_alerts_bot.py)

## Deployment
Bots are "running" inside AWS Lambda, and are deployed to the https://botsin.space instance, a Mastodon instance 
dedicated to bots. They may be found here:

* [Service Alert Bot](https://botsin.space/@coct_service_alerts)
* [CoCT Loadshedding Bot](https://botsin.space/@coct_loadshedding_alerts)