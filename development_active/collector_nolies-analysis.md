

collectors simply workat the lowest level to pass esi over to the db writer. The biggest difference between analysis and collectors is that collectors must be given the current users' esi auth token. Analysis task might have to perform a task using specific auth tokens or multiple auth tokens.  
collectors are considered, not generated. They must be manually rebuilt when affected by ESI and SDE updates.  
these collectors own and register each of the tables with `io` modules' model engine.

all the analysis logic (iterating regions for regional markets collection, discovering structures for structure market) should be in `analysis/`. marked with **'Database enrichment needed from `analysis/`'**

The following document is organized like this:
```
{public db/character db/corperation db/alliance db} {table}  
{primary endpoint}
 **Database enrichment needed from `analysis/`:**  
   - {analysis esi endpoints}
 ```

---

PUBLIC alliances
https://esi.evetech.net/alliances  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/alliances/{alliance_id}

---

ALLIANCE corporations  
https://esi.evetech.net/alliances/{alliance_id}/corporations

---

PUBLIC corporations  
there is no way to get all corporations. we will have to do analysis enrichment to get corp ids via alliance corps and from private dbs.  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/alliances/{alliance_id}/corporations  
   - https://esi.evetech.net/corporations/{corporation_id}  
   - https://esi.evetech.net/corporations/{corporation_id}/members/limit (requires auth from soneone in the corp, may be NULL)

---

PERSONAL assets  
https://esi.evetech.net/characters/{character_id}/assets

---

CORP assets  
https://esi.evetech.net/corporations/{corporation_id}/assets

---

PERSONAL calandar  
https://esi.evetech.net/characters/{character_id}/calendar  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/characters/{character_id}/calendar/{event_id}  
   - https://esi.evetech.net/characters/{character_id}/calendar/{event_id}/attendees

---

PERSONAL characters  
https://esi.evetech.net/characters/{character_id}  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/characters/{character_id}/fatigue  
   - https://esi.evetech.net/characters/{character_id}/roles  
   - https://esi.evetech.net/characters/{character_id}/implants  
   - https://esi.evetech.net/characters/{character_id}/location  
   - https://esi.evetech.net/characters/{character_id}/online  
   - https://esi.evetech.net/characters/{character_id}/ship  
   - https://esi.evetech.net/characters/{character_id}/attributes  
   - https://esi.evetech.net/characters/{character_id}/wallet  
   - https://esi.evetech.net/characters/affiliation (bulk inset into all character dbs. public info to enrich private database 'characters' table.)

---

PUBLIC characters  
https://esi.evetech.net/characters/{character_id}  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/characters/affiliation (bulk inset into all character dbs. public info to enrich private database 'characters' table.)

---

PERSONAL agent_research  
https://esi.evetech.net/characters/{character_id}/agents_research

---

PERSONAL blueprints  
https://esi.evetech.net/characters/{character_id}/blueprints

---

PERSONAL corporation_history  
https://esi.evetech.net/characters/{character_id}/corporationhistory

---

PERSONAL medals  
https://esi.evetech.net/characters/{character_id}/medals

---

PERSONAL notifications  
https://esi.evetech.net/characters/{character_id}/notifications  
https://esi.evetech.net/characters/{character_id}/notifications/contacts

---

PERSONAL standings  
https://esi.evetech.net/characters/{character_id}/standings

---

PERSONAL clones  
https://esi.evetech.net/characters/{character_id}/clones

---

ALLIANCE contacts  
https://esi.evetech.net/alliances/{alliance_id}/contacts  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/alliances/{alliance_id}/contacts/labels

---

PERSONAL contacts  
https://esi.evetech.net/characters/{character_id}/contacts  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/characters/{character_id}/contacts/labels

---

CORP contacts  
https://esi.evetech.net/corporations/{corporation_id}/contacts  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/corporations/{corporation_id}/contacts/labels

---

PERSONAL contracts  
https://esi.evetech.net/characters/{character_id}/contracts  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/characters/{character_id}/contracts/{contract_id}/bids  
   - https://esi.evetech.net/characters/{character_id}/contracts/{contract_id}/items

---

PUBLIC contracts  
https://esi.evetech.net/contracts/public/{region_id}  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/contracts/public/bids/{contract_id}  
   - https://esi.evetech.net/contracts/public/items/{contract_id}

---

CORP contracts  
https://esi.evetech.net/corporations/{corporation_id}/contracts  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/corporations/{corporation_id}/contracts/{contract_id}/bids  
   - https://esi.evetech.net/corporations/{corporation_id}/contracts/{contract_id}/items

---

PUBLIC npccorps (MAY BE UNNEEDED IF IT IS IN THE SDE!)  
https://esi.evetech.net/corporations/npccorps

---

CORP alliance_history  
https://esi.evetech.net/corporations/{corporation_id}/alliancehistory

---

CORP blueprints  
https://esi.evetech.net/corporations/{corporation_id}/blueprints

---

CORP divisions  
https://esi.evetech.net/corporations/{corporation_id}/divisions

---

CORP facilities  
https://esi.evetech.net/corporations/{corporation_id}/facilities

---

CORP medals  
https://esi.evetech.net/corporations/{corporation_id}/medals

---

CORP members  
https://esi.evetech.net/corporations/{corporation_id}/members  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/corporations/{corporation_id}/medals/issued  
   - https://esi.evetech.net/corporations/{corporation_id}/members/titles  
   - https://esi.evetech.net/corporations/{corporation_id}/roles

---
	
CORP shareholders  
https://esi.evetech.net/corporations/{corporation_id}/shareholders

---

CORP standings  
https://esi.evetech.net/corporations/{corporation_id}/standings

---

CORP starbases  
https://esi.evetech.net/corporations/{corporation_id}/starbases  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/corporations/{corporation_id}/starbases/{starbase_id}

---

CORP structures  
https://esi.evetech.net/corporations/{corporation_id}/structures

---

CORP titles  
https://esi.evetech.net/corporations/{corporation_id}/titles

---

CORP projects  
https://esi.evetech.net/corporations/{corporation_id}/projects  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/corporations/{corporation_id}/projects/{project_id}

---

PERSONAL projects  
https://esi.evetech.net/corporations/<corporation_id>/projects  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/corporations/<corporation_id>/projects/{project_id}  
   - https://esi.evetech.net/corporations/<corporation_id>/projects/{project_id}/contribution/{character_id}

---

Im gonna be honest-- i have no idea how to organize factional warfare or if we need any tables for it... anyways ill let you decide that

---

PERSONAL fittings  
https://esi.evetech.net/characters/{character_id}/fittings

---

PERSONAL freelance  
https://esi.evetech.net/characters/{character_id}/freelance-jobs  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/freelance-jobs/{job_id}

---

CORP freelance  
https://esi.evetech.net/corporations/{corporation_id}/freelance-jobs  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/freelance-jobs/{job_id}

---

PUBLIC freelance  
https://esi.evetech.net/freelance-jobs  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/freelance-jobs/{job_id}

---

PUBLIC incursions  
https://esi.evetech.net/incursions

---

PRIVATE industry_jobs  
https://esi.evetech.net/characters/{character_id}/industry/jobs

---

PRIVATE mining_ledger  
https://esi.evetech.net/characters/{character_id}/mining

---

CORP moon_extractions  
https://esi.evetech.net/corporation/{corporation_id}/mining/extractions

---

CORP observers  
https://esi.evetech.net/corporation/{corporation_id}/mining/observers  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/corporation/{corporation_id}/mining/observers/{observer_id}

---

CORP industry_jobs  
https://esi.evetech.net/corporations/{corporation_id}/industry/jobs

---

PUBLIC facilities  
https://esi.evetech.net/industry/facilities

---

PUBLIC cost_indices  
https://esi.evetech.net/industry/systems

---

PERSONAL killmail  
https://esi.evetech.net/characters/{character_id}/killmails/recent

---

CORP killmail  
https://esi.evetech.net/corporations/{corporation_id}/killmails/recent

---

PERSONAL loyalty_points  
https://esi.evetech.net/characters/{character_id}/loyalty/points

---

PUBLIC loyalty_offers  
https://esi.evetech.net/loyalty/stores/{corporation_id}/offers

---

PERSONAL mail  
https://esi.evetech.net/characters/{character_id}/mail  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/characters/{character_id}/mail/{mail_id}

---

PERSONAL mail_stats  
https://esi.evetech.net/characters/{character_id}/mail/labels

---

PERSONAL mail_lists  
https://esi.evetech.net/characters/{character_id}/mail/lists

---

PERSONAL market_orders  
https://esi.evetech.net/characters/{character_id}/orders

---

PERSONAL marketHistory  
https://esi.evetech.net/characters/{character_id}/orders/history

---

CORP market_orders  
https://esi.evetech.net/corporations/{corporation_id}/orders

---

CORP marketHistory  
https://esi.evetech.net/corporations/{corporation_id}/orders/history

---

PUBLIC market_prices  
https://esi.evetech.net/markets/prices  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/markets/{region_id}/history

---

PUBLIC market_orders  
https://esi.evetech.net/markets/{region_id}/orders  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/markets/structures/{structure_id}

---

PUBLIC market_items  
https://esi.evetech.net/markets/{region_id}/types

---

PERSONAL colonies  
https://esi.evetech.net/characters/{character_id}/planets  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/characters/{character_id}/planets/{planet_id}

---

CORP customs_offices  
https://esi.evetech.net/corporations/{corporation_id}/customs_offices

---

PERSONAL skill_queue  
https://esi.evetech.net/characters/{character_id}/skillqueue

---

PERSONAL skills  
https://esi.evetech.net/characters/{character_id}/skills

---

IDK what to do with sov either:  
https://esi.evetech.net/sovereignty/campaigns  
https://esi.evetech.net/sovereignty/map  
https://esi.evetech.net/sovereignty/structures  
dont know if we need tables for those or not...

---

PUBLIC structures  
https://esi.evetech.net/universe/structures  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/industry/facilities  
   - add all CORPS structures  
   - add all PERSONAL structures

PERSONAL wallet_journal  
https://esi.evetech.net/characters/{character_id}/wallet/journal

---

PERSONAL wallet_txn  
https://esi.evetech.net/characters/{character_id}/wallet/transactions

---

CORP wallets  
https://esi.evetech.net/corporations/{corporation_id}/wallets

---

CORP wallet_journals (keyed per division)  
https://esi.evetech.net/corporations/{corporation_id}/wallets/{division}/journal

---

CORP wallet_txns (keyed per division)  
https://esi.evetech.net/corporations/{corporation_id}/wallets/{division}/transactions

---

PUBLIC wars  
https://esi.evetech.net/wars  
 **Database enrichment needed from `analysis/`:**  
   - https://esi.evetech.net/wars/{war_id}  
   - https://esi.evetech.net/wars/{war_id}/killmails

---
```
collectors/												# define the table model, required scopes, `esi` passing to `io`. invokers:
	__init__.py											# get proper token,  

	alliance/
		alliance.py										# corporations(alliance_id)
		contacts.py										# contacts(alliance_id)

	corp/
		__init__.py										# ensure Corp Role Token for the
		assets.py										# assets(), names(asset_id: list) locations(asset_id: list)
		contacts.py										# contacts()
		contracts.py									# contracts(), items(contract_id), bids(contract_id)
		corporation.py									# 
		corp_projects.py								# 
		faction_warfare.py
		fleets.py
		freelance.py
		industry.py
		killmails.py
		market.py
		planetary_interaction.py
		wallet.py

	personal/
		assets.py										# characterAssets(character_id), 
		calandar.py										# 
		character.py									#
		clones.py
		contacts.py
		contracts.py
		corporation.py
		corp_projects.py
		faction_warfare.py
		fittings.py
		fleets.py
		freelance.py
		industry.py
		killmails.py
		location.py
		loyalty.py
		mail.py
		market.py
		planetary_interaction.py
		skills.py
		wallet.py

	public/
		alliance.py										# allAlliances()
		characters.py									# character(character_id), 
		contracts.py
		corporation.py
		dogma.py # if needed
		faction_warfare.py
		freelance.py
		incursions.py
		industry.py
		insurance.py # if needed
		loyalty.py
		market.py										
		meta.py # if needed
		planetary_interaction.py # not really needed
		routes.py										# simple table for route caching.
		soverngty.py
		status.py
		universe.py
		wars.py


		
```