# selffetch-portal

local dump project. i store metadata i've already scraped in Postgres, serve that metadata locally through a tiny python backend, and call the remote site's API only to fetch the actual media (streams/files) on demand. frontend is a simple React app for browsing/searching the local metadata and opening media via the backend.

**what it is**
- a personal local mirror/dashboard.
- metadata lives in Postgres (already scraped in other sessions).
- backend (`MediaAPI.py`) reads metadata from Postgres, exposes small endpoints for search/list/detail, and when you open an item it calls the remote site API to fetch the media (so i don't re-scrape metadata, just reuse the db).
- frontend (`xxx/`) is a React app that talks to the backend.

**why**
- original site search is trash/limited.
- i already scraped and normalized metadata so it's easier to search locally.
- calling the site's media API directly avoids downloading/re-hosting everything; i just stream/proxy the media when needed.
- quick local UI for faster exploration without hammering the site.

**structure**

```selffetch-portal/```
```│```
```├── MediaAPI.py # python backend: connects to Postgres, serves metadata endpoints, proxies media requests to remote API```
```├── requirements.txt # pip deps (flask/fastapi, psycopg2/asyncpg, requests/httpx, etc)```
```└── xxx/ # react frontend```
```  ├── package.json```
```  ├── src/```
```  └── public/```


### how i use it
1. run `MediaAPI.py` → starts local api server (fastapi)
2. run `npm start` inside `/xxx` → open `localhost` ui
3. browse freely, it fetches data through my backend not directly to that site

### note
this is not meant for distribution or automation abuse.
i only use this for local exploration and metadata management.

hehe

---
