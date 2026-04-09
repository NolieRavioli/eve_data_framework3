# ESI API Notes

- Generated at: 2026-04-08T18:32:21.604311+00:00
- Active compatibility date: `2025-12-16`
- Route count: `208`
- Scope count: `66`

## Request Rules

- Send `X-Compatibility-Date` on requests that need explicit version pinning.
- Respect `ETag`, `If-None-Match`, `Last-Modified`, and `If-Modified-Since` for cache-aware polling.
- Use `X-Pages` when present for page-based pagination.
- Some routes use cursor pagination via `x-pagination` metadata instead of numbered pages.

## Common Headers

- `Accept-Language`: `en`, `de`, `fr`, `ja`, `ru`, `zh`, `ko`, `es`
- `X-Tenant`: defaults to `tranquility`
- `X-Compatibility-Date`: required by the spec parameter model

## Scope Groups

### `esi-alliances.read_contacts.v1`

- `GET` `/alliances/{alliance_id}/contacts`: Get alliance contacts
- `GET` `/alliances/{alliance_id}/contacts/labels`: Get alliance contact labels

### `esi-assets.read_assets.v1`

- `GET` `/characters/{character_id}/assets`: Get character assets
- `POST` `/characters/{character_id}/assets/locations`: Get character asset locations
- `POST` `/characters/{character_id}/assets/names`: Get character asset names

### `esi-assets.read_corporation_assets.v1`

- `GET` `/corporations/{corporation_id}/assets`: Get corporation assets
- `POST` `/corporations/{corporation_id}/assets/locations`: Get corporation asset locations
- `POST` `/corporations/{corporation_id}/assets/names`: Get corporation asset names

### `esi-calendar.read_calendar_events.v1`

- `GET` `/characters/{character_id}/calendar`: List calendar event summaries
- `GET` `/characters/{character_id}/calendar/{event_id}`: Get an event
- `GET` `/characters/{character_id}/calendar/{event_id}/attendees`: Get attendees

### `esi-calendar.respond_calendar_events.v1`

- `PUT` `/characters/{character_id}/calendar/{event_id}`: Respond to an event

### `esi-characters.read_agents_research.v1`

- `GET` `/characters/{character_id}/agents_research`: Get agents research

### `esi-characters.read_blueprints.v1`

- `GET` `/characters/{character_id}/blueprints`: Get blueprints

### `esi-characters.read_contacts.v1`

- `GET` `/characters/{character_id}/contacts`: Get contacts
- `GET` `/characters/{character_id}/contacts/labels`: Get contact labels
- `POST` `/characters/{character_id}/cspa`: Calculate a CSPA charge cost

### `esi-characters.read_corporation_roles.v1`

- `GET` `/characters/{character_id}/roles`: Get character corporation roles

### `esi-characters.read_fatigue.v1`

- `GET` `/characters/{character_id}/fatigue`: Get jump fatigue

### `esi-characters.read_freelance_jobs.v1`

- `GET` `/characters/{character_id}/freelance-jobs`: List character freelance jobs
- `GET` `/characters/{character_id}/freelance-jobs/{job_id}/participation`: Get character freelance job participation

### `esi-characters.read_fw_stats.v1`

- `GET` `/characters/{character_id}/fw/stats`: Overview of a character involved in faction warfare

### `esi-characters.read_loyalty.v1`

- `GET` `/characters/{character_id}/loyalty/points`: Get loyalty points

### `esi-characters.read_medals.v1`

- `GET` `/characters/{character_id}/medals`: Get medals

### `esi-characters.read_notifications.v1`

- `GET` `/characters/{character_id}/notifications`: Get character notifications
- `GET` `/characters/{character_id}/notifications/contacts`: Get new contact notifications

### `esi-characters.read_standings.v1`

- `GET` `/characters/{character_id}/standings`: Get standings

### `esi-characters.read_titles.v1`

- `GET` `/characters/{character_id}/titles`: Get character corporation titles

### `esi-characters.write_contacts.v1`

- `DELETE` `/characters/{character_id}/contacts`: Delete contacts
- `POST` `/characters/{character_id}/contacts`: Add contacts
- `PUT` `/characters/{character_id}/contacts`: Edit contacts

### `esi-clones.read_clones.v1`

- `GET` `/characters/{character_id}/clones`: Get clones

### `esi-clones.read_implants.v1`

- `GET` `/characters/{character_id}/implants`: Get active implants

### `esi-contracts.read_character_contracts.v1`

- `GET` `/characters/{character_id}/contracts`: Get contracts
- `GET` `/characters/{character_id}/contracts/{contract_id}/bids`: Get contract bids
- `GET` `/characters/{character_id}/contracts/{contract_id}/items`: Get contract items

### `esi-contracts.read_corporation_contracts.v1`

- `GET` `/corporations/{corporation_id}/contracts`: Get corporation contracts
- `GET` `/corporations/{corporation_id}/contracts/{contract_id}/bids`: Get corporation contract bids
- `GET` `/corporations/{corporation_id}/contracts/{contract_id}/items`: Get corporation contract items

### `esi-corporations.read_blueprints.v1`

- `GET` `/corporations/{corporation_id}/blueprints`: Get corporation blueprints

### `esi-corporations.read_contacts.v1`

- `GET` `/corporations/{corporation_id}/contacts`: Get corporation contacts
- `GET` `/corporations/{corporation_id}/contacts/labels`: Get corporation contact labels

### `esi-corporations.read_container_logs.v1`

- `GET` `/corporations/{corporation_id}/containers/logs`: Get all corporation ALSC logs

### `esi-corporations.read_corporation_membership.v1`

- `GET` `/corporations/{corporation_id}/members`: Get corporation members
- `GET` `/corporations/{corporation_id}/roles`: Get corporation member roles
- `GET` `/corporations/{corporation_id}/roles/history`: Get corporation member roles history

### `esi-corporations.read_divisions.v1`

- `GET` `/corporations/{corporation_id}/divisions`: Get corporation divisions

### `esi-corporations.read_facilities.v1`

- `GET` `/corporations/{corporation_id}/facilities`: Get corporation facilities

### `esi-corporations.read_freelance_jobs.v1`

- `GET` `/corporations/{corporation_id}/freelance-jobs`: List corporation freelance jobs
- `GET` `/corporations/{corporation_id}/freelance-jobs/{job_id}/participants`: List participants of a freelance job

### `esi-corporations.read_fw_stats.v1`

- `GET` `/corporations/{corporation_id}/fw/stats`: Overview of a corporation involved in faction warfare

### `esi-corporations.read_medals.v1`

- `GET` `/corporations/{corporation_id}/medals`: Get corporation medals
- `GET` `/corporations/{corporation_id}/medals/issued`: Get corporation issued medals

### `esi-corporations.read_projects.v1`

- `GET` `/corporations/{corporation_id}/projects`: List corporation projects
- `GET` `/corporations/{corporation_id}/projects/{project_id}`: Get project details
- `GET` `/corporations/{corporation_id}/projects/{project_id}/contribution/{character_id}`: Get your project contribution
- `GET` `/corporations/{corporation_id}/projects/{project_id}/contributors`: List project contributors

### `esi-corporations.read_standings.v1`

- `GET` `/corporations/{corporation_id}/standings`: Get corporation standings

### `esi-corporations.read_starbases.v1`

- `GET` `/corporations/{corporation_id}/starbases`: Get corporation starbases (POSes)
- `GET` `/corporations/{corporation_id}/starbases/{starbase_id}`: Get starbase (POS) detail

### `esi-corporations.read_structures.v1`

- `GET` `/corporations/{corporation_id}/structures`: Get corporation structures

### `esi-corporations.read_titles.v1`

- `GET` `/corporations/{corporation_id}/members/titles`: Get corporation's members' titles
- `GET` `/corporations/{corporation_id}/titles`: Get corporation titles

### `esi-corporations.track_members.v1`

- `GET` `/corporations/{corporation_id}/members/limit`: Get corporation member limit
- `GET` `/corporations/{corporation_id}/membertracking`: Track corporation members

### `esi-fittings.read_fittings.v1`

- `GET` `/characters/{character_id}/fittings`: Get fittings

### `esi-fittings.write_fittings.v1`

- `POST` `/characters/{character_id}/fittings`: Create fitting
- `DELETE` `/characters/{character_id}/fittings/{fitting_id}`: Delete fitting

### `esi-fleets.read_fleet.v1`

- `GET` `/characters/{character_id}/fleet`: Get character fleet info
- `GET` `/fleets/{fleet_id}`: Get fleet information
- `GET` `/fleets/{fleet_id}/members`: Get fleet members
- `GET` `/fleets/{fleet_id}/wings`: Get fleet wings

### `esi-fleets.write_fleet.v1`

- `PUT` `/fleets/{fleet_id}`: Update fleet
- `POST` `/fleets/{fleet_id}/members`: Create fleet invitation
- `DELETE` `/fleets/{fleet_id}/members/{member_id}`: Kick fleet member
- `PUT` `/fleets/{fleet_id}/members/{member_id}`: Move fleet member
- `DELETE` `/fleets/{fleet_id}/squads/{squad_id}`: Delete fleet squad
- `PUT` `/fleets/{fleet_id}/squads/{squad_id}`: Rename fleet squad
- `POST` `/fleets/{fleet_id}/wings`: Create fleet wing
- `DELETE` `/fleets/{fleet_id}/wings/{wing_id}`: Delete fleet wing
- `PUT` `/fleets/{fleet_id}/wings/{wing_id}`: Rename fleet wing
- `POST` `/fleets/{fleet_id}/wings/{wing_id}/squads`: Create fleet squad

### `esi-industry.read_character_jobs.v1`

- `GET` `/characters/{character_id}/industry/jobs`: List character industry jobs

### `esi-industry.read_character_mining.v1`

- `GET` `/characters/{character_id}/mining`: Character mining ledger

### `esi-industry.read_corporation_jobs.v1`

- `GET` `/corporations/{corporation_id}/industry/jobs`: List corporation industry jobs

### `esi-industry.read_corporation_mining.v1`

- `GET` `/corporation/{corporation_id}/mining/extractions`: Moon extraction timers
- `GET` `/corporation/{corporation_id}/mining/observers`: Corporation mining observers
- `GET` `/corporation/{corporation_id}/mining/observers/{observer_id}`: Observed corporation mining

### `esi-killmails.read_corporation_killmails.v1`

- `GET` `/corporations/{corporation_id}/killmails/recent`: Get a corporation's recent kills and losses

### `esi-killmails.read_killmails.v1`

- `GET` `/characters/{character_id}/killmails/recent`: Get a character's recent kills and losses

### `esi-location.read_location.v1`

- `GET` `/characters/{character_id}/location`: Get character location

### `esi-location.read_online.v1`

- `GET` `/characters/{character_id}/online`: Get character online

### `esi-location.read_ship_type.v1`

- `GET` `/characters/{character_id}/ship`: Get current ship

### `esi-mail.organize_mail.v1`

- `POST` `/characters/{character_id}/mail/labels`: Create a mail label
- `DELETE` `/characters/{character_id}/mail/labels/{label_id}`: Delete a mail label
- `DELETE` `/characters/{character_id}/mail/{mail_id}`: Delete a mail
- `PUT` `/characters/{character_id}/mail/{mail_id}`: Update metadata about a mail

### `esi-mail.read_mail.v1`

- `GET` `/characters/{character_id}/mail`: Return mail headers
- `GET` `/characters/{character_id}/mail/labels`: Get mail labels and unread counts
- `GET` `/characters/{character_id}/mail/lists`: Return mailing list subscriptions
- `GET` `/characters/{character_id}/mail/{mail_id}`: Return a mail

### `esi-mail.send_mail.v1`

- `POST` `/characters/{character_id}/mail`: Send a new mail

### `esi-markets.read_character_orders.v1`

- `GET` `/characters/{character_id}/orders`: List open orders from a character
- `GET` `/characters/{character_id}/orders/history`: List historical orders by a character

### `esi-markets.read_corporation_orders.v1`

- `GET` `/corporations/{corporation_id}/orders`: List open orders from a corporation
- `GET` `/corporations/{corporation_id}/orders/history`: List historical orders from a corporation

### `esi-markets.structure_markets.v1`

- `GET` `/markets/structures/{structure_id}`: List orders in a structure

### `esi-planets.manage_planets.v1`

- `GET` `/characters/{character_id}/planets`: Get colonies
- `GET` `/characters/{character_id}/planets/{planet_id}`: Get colony layout

### `esi-planets.read_customs_offices.v1`

- `GET` `/corporations/{corporation_id}/customs_offices`: List corporation customs offices

### `esi-search.search_structures.v1`

- `GET` `/characters/{character_id}/search`: Search on a string

### `esi-skills.read_skillqueue.v1`

- `GET` `/characters/{character_id}/skillqueue`: Get character's skill queue

### `esi-skills.read_skills.v1`

- `GET` `/characters/{character_id}/attributes`: Get character attributes
- `GET` `/characters/{character_id}/skills`: Get character skills

### `esi-ui.open_window.v1`

- `POST` `/ui/openwindow/contract`: Open Contract Window
- `POST` `/ui/openwindow/information`: Open Information Window
- `POST` `/ui/openwindow/marketdetails`: Open Market Details
- `POST` `/ui/openwindow/newmail`: Open New Mail Window

### `esi-ui.write_waypoint.v1`

- `POST` `/ui/autopilot/waypoint`: Set Autopilot Waypoint

### `esi-universe.read_structures.v1`

- `GET` `/universe/structures/{structure_id}`: Get structure information

### `esi-wallet.read_character_wallet.v1`

- `GET` `/characters/{character_id}/wallet`: Get a character's wallet balance
- `GET` `/characters/{character_id}/wallet/journal`: Get character wallet journal
- `GET` `/characters/{character_id}/wallet/transactions`: Get wallet transactions

### `esi-wallet.read_corporation_wallets.v1`

- `GET` `/corporations/{corporation_id}/shareholders`: Get corporation shareholders
- `GET` `/corporations/{corporation_id}/wallets`: Returns a corporation's wallet balance
- `GET` `/corporations/{corporation_id}/wallets/{division}/journal`: Get corporation wallet journal
- `GET` `/corporations/{corporation_id}/wallets/{division}/transactions`: Get corporation wallet transactions

## Route Tags

- `Universe`: `30` route(s)
- `Corporation`: `22` route(s)
- `Character`: `14` route(s)
- `Fleets`: `14` route(s)
- `Market`: `11` route(s)
- `Contacts`: `9` route(s)
- `Contracts`: `9` route(s)
- `Mail`: `9` route(s)
- `Faction Warfare`: `8` route(s)
- `Industry`: `8` route(s)
- `Assets`: `6` route(s)
- `Freelance Jobs`: `6` route(s)
- `Wallet`: `6` route(s)
- `Dogma`: `5` route(s)
- `User Interface`: `5` route(s)
- `Alliance`: `4` route(s)
- `Calendar`: `4` route(s)
- `Corporation Projects`: `4` route(s)
- `Planetary Interaction`: `4` route(s)
- `Fittings`: `3` route(s)
- `Killmails`: `3` route(s)
- `Location`: `3` route(s)
- `Meta`: `3` route(s)
- `Skills`: `3` route(s)
- `Sovereignty`: `3` route(s)
- `Wars`: `3` route(s)
- `Clones`: `2` route(s)
- `Loyalty`: `2` route(s)
- `Incursions`: `1` route(s)
- `Insurance`: `1` route(s)
- `Routes`: `1` route(s)
- `Search`: `1` route(s)
- `Status`: `1` route(s)

## Notes

- Public market, universe, and status routes often have `x-cache-age` values and should be cached aggressively.
- Corporation and fleet routes frequently include both OAuth scope requirements and `x-required-roles` metadata.
- The raw `openapi.json` remains the source of truth; this document is a quick operating summary.

Spec title: `EVE Stroopwafel Ingestion (ESI) - tranquility`
