"""
esi/generated/operations.py
────────────────────────────
AUTO-GENERATED — do not edit by hand.
Source: ESI compatibility date 2025-12-16
Operations: 208

One callable per operation_id.  Each function delegates to
client.execute_operation() and returns the standardised response dict.
"""
# ruff: noqa
from __future__ import annotations
from typing import Any
from esi.generated.client import execute_operation, fetch_all_pages

def GetAlliances(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List all alliances
    Method: GET  Path: /alliances
    """
    return execute_operation('GetAlliances', path_params=None, query_params=query_params, token=token)

def GetAlliancesAllianceId(*, alliance_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get alliance's public information
    Method: GET  Path: /alliances/{alliance_id}
    """
    return execute_operation('GetAlliancesAllianceId', path_params={"alliance_id": alliance_id}, query_params=query_params, token=token)

def GetAlliancesAllianceIdContacts(*, alliance_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get alliance contacts
    Method: GET  Path: /alliances/{alliance_id}/contacts
    Scopes: esi-alliances.read_contacts.v1
    """
    if all_pages:
        return fetch_all_pages('GetAlliancesAllianceIdContacts', path_params={"alliance_id": alliance_id}, query_params=query_params, token=token)
    return execute_operation('GetAlliancesAllianceIdContacts', path_params={"alliance_id": alliance_id}, query_params=query_params, token=token)

def GetAlliancesAllianceIdContactsLabels(*, alliance_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get alliance contact labels
    Method: GET  Path: /alliances/{alliance_id}/contacts/labels
    Scopes: esi-alliances.read_contacts.v1
    """
    return execute_operation('GetAlliancesAllianceIdContactsLabels', path_params={"alliance_id": alliance_id}, query_params=query_params, token=token)

def GetAlliancesAllianceIdCorporations(*, alliance_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List alliance's corporations
    Method: GET  Path: /alliances/{alliance_id}/corporations
    """
    return execute_operation('GetAlliancesAllianceIdCorporations', path_params={"alliance_id": alliance_id}, query_params=query_params, token=token)

def GetAlliancesAllianceIdIcons(*, alliance_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get alliance icon
    Method: GET  Path: /alliances/{alliance_id}/icons
    """
    return execute_operation('GetAlliancesAllianceIdIcons', path_params={"alliance_id": alliance_id}, query_params=query_params, token=token)

def PostCharactersAffiliation(*, token: str | None = None, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Character affiliation
    Method: POST  Path: /characters/affiliation
    """
    return execute_operation('PostCharactersAffiliation', path_params=None, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterId(*, character_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get character's public information
    Method: GET  Path: /characters/{character_id}
    """
    return execute_operation('GetCharactersCharacterId', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdAgentsResearch(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get agents research
    Method: GET  Path: /characters/{character_id}/agents_research
    Scopes: esi-characters.read_agents_research.v1
    """
    return execute_operation('GetCharactersCharacterIdAgentsResearch', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdAssets(*, character_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get character assets
    Method: GET  Path: /characters/{character_id}/assets
    Scopes: esi-assets.read_assets.v1
    """
    if all_pages:
        return fetch_all_pages('GetCharactersCharacterIdAssets', path_params={"character_id": character_id}, query_params=query_params, token=token)
    return execute_operation('GetCharactersCharacterIdAssets', path_params={"character_id": character_id}, query_params=query_params, token=token)

def PostCharactersCharacterIdAssetsLocations(*, character_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Get character asset locations
    Method: POST  Path: /characters/{character_id}/assets/locations
    Scopes: esi-assets.read_assets.v1
    """
    return execute_operation('PostCharactersCharacterIdAssetsLocations', path_params={"character_id": character_id}, query_params=query_params, token=token, json_body=json_body)

def PostCharactersCharacterIdAssetsNames(*, character_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Get character asset names
    Method: POST  Path: /characters/{character_id}/assets/names
    Scopes: esi-assets.read_assets.v1
    """
    return execute_operation('PostCharactersCharacterIdAssetsNames', path_params={"character_id": character_id}, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterIdAttributes(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get character attributes
    Method: GET  Path: /characters/{character_id}/attributes
    Scopes: esi-skills.read_skills.v1
    """
    return execute_operation('GetCharactersCharacterIdAttributes', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdBlueprints(*, character_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get blueprints
    Method: GET  Path: /characters/{character_id}/blueprints
    Scopes: esi-characters.read_blueprints.v1
    """
    if all_pages:
        return fetch_all_pages('GetCharactersCharacterIdBlueprints', path_params={"character_id": character_id}, query_params=query_params, token=token)
    return execute_operation('GetCharactersCharacterIdBlueprints', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdCalendar(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """List calendar event summaries
    Method: GET  Path: /characters/{character_id}/calendar
    Scopes: esi-calendar.read_calendar_events.v1
    """
    return execute_operation('GetCharactersCharacterIdCalendar', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdCalendarEventId(*, character_id: Any, event_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get an event
    Method: GET  Path: /characters/{character_id}/calendar/{event_id}
    Scopes: esi-calendar.read_calendar_events.v1
    """
    return execute_operation('GetCharactersCharacterIdCalendarEventId', path_params={"character_id": character_id, "event_id": event_id}, query_params=query_params, token=token)

def PutCharactersCharacterIdCalendarEventId(*, character_id: Any, event_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Respond to an event
    Method: PUT  Path: /characters/{character_id}/calendar/{event_id}
    Scopes: esi-calendar.respond_calendar_events.v1
    """
    return execute_operation('PutCharactersCharacterIdCalendarEventId', path_params={"character_id": character_id, "event_id": event_id}, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterIdCalendarEventIdAttendees(*, character_id: Any, event_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get attendees
    Method: GET  Path: /characters/{character_id}/calendar/{event_id}/attendees
    Scopes: esi-calendar.read_calendar_events.v1
    """
    return execute_operation('GetCharactersCharacterIdCalendarEventIdAttendees', path_params={"character_id": character_id, "event_id": event_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdClones(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get clones
    Method: GET  Path: /characters/{character_id}/clones
    Scopes: esi-clones.read_clones.v1
    """
    return execute_operation('GetCharactersCharacterIdClones', path_params={"character_id": character_id}, query_params=query_params, token=token)

def DeleteCharactersCharacterIdContacts(*, character_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Delete contacts
    Method: DELETE  Path: /characters/{character_id}/contacts
    Scopes: esi-characters.write_contacts.v1
    """
    return execute_operation('DeleteCharactersCharacterIdContacts', path_params={"character_id": character_id}, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterIdContacts(*, character_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get contacts
    Method: GET  Path: /characters/{character_id}/contacts
    Scopes: esi-characters.read_contacts.v1
    """
    if all_pages:
        return fetch_all_pages('GetCharactersCharacterIdContacts', path_params={"character_id": character_id}, query_params=query_params, token=token)
    return execute_operation('GetCharactersCharacterIdContacts', path_params={"character_id": character_id}, query_params=query_params, token=token)

def PostCharactersCharacterIdContacts(*, character_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Add contacts
    Method: POST  Path: /characters/{character_id}/contacts
    Scopes: esi-characters.write_contacts.v1
    """
    return execute_operation('PostCharactersCharacterIdContacts', path_params={"character_id": character_id}, query_params=query_params, token=token, json_body=json_body)

def PutCharactersCharacterIdContacts(*, character_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Edit contacts
    Method: PUT  Path: /characters/{character_id}/contacts
    Scopes: esi-characters.write_contacts.v1
    """
    return execute_operation('PutCharactersCharacterIdContacts', path_params={"character_id": character_id}, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterIdContactsLabels(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get contact labels
    Method: GET  Path: /characters/{character_id}/contacts/labels
    Scopes: esi-characters.read_contacts.v1
    """
    return execute_operation('GetCharactersCharacterIdContactsLabels', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdContracts(*, character_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get contracts
    Method: GET  Path: /characters/{character_id}/contracts
    Scopes: esi-contracts.read_character_contracts.v1
    """
    if all_pages:
        return fetch_all_pages('GetCharactersCharacterIdContracts', path_params={"character_id": character_id}, query_params=query_params, token=token)
    return execute_operation('GetCharactersCharacterIdContracts', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdContractsContractIdBids(*, character_id: Any, contract_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get contract bids
    Method: GET  Path: /characters/{character_id}/contracts/{contract_id}/bids
    Scopes: esi-contracts.read_character_contracts.v1
    """
    return execute_operation('GetCharactersCharacterIdContractsContractIdBids', path_params={"character_id": character_id, "contract_id": contract_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdContractsContractIdItems(*, character_id: Any, contract_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get contract items
    Method: GET  Path: /characters/{character_id}/contracts/{contract_id}/items
    Scopes: esi-contracts.read_character_contracts.v1
    """
    return execute_operation('GetCharactersCharacterIdContractsContractIdItems', path_params={"character_id": character_id, "contract_id": contract_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdCorporationhistory(*, character_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get corporation history
    Method: GET  Path: /characters/{character_id}/corporationhistory
    """
    return execute_operation('GetCharactersCharacterIdCorporationhistory', path_params={"character_id": character_id}, query_params=query_params, token=token)

def PostCharactersCharacterIdCspa(*, character_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Calculate a CSPA charge cost
    Method: POST  Path: /characters/{character_id}/cspa
    Scopes: esi-characters.read_contacts.v1
    """
    return execute_operation('PostCharactersCharacterIdCspa', path_params={"character_id": character_id}, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterIdFatigue(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get jump fatigue
    Method: GET  Path: /characters/{character_id}/fatigue
    Scopes: esi-characters.read_fatigue.v1
    """
    return execute_operation('GetCharactersCharacterIdFatigue', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdFittings(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get fittings
    Method: GET  Path: /characters/{character_id}/fittings
    Scopes: esi-fittings.read_fittings.v1
    """
    return execute_operation('GetCharactersCharacterIdFittings', path_params={"character_id": character_id}, query_params=query_params, token=token)

def PostCharactersCharacterIdFittings(*, character_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Create fitting
    Method: POST  Path: /characters/{character_id}/fittings
    Scopes: esi-fittings.write_fittings.v1
    """
    return execute_operation('PostCharactersCharacterIdFittings', path_params={"character_id": character_id}, query_params=query_params, token=token, json_body=json_body)

def DeleteCharactersCharacterIdFittingsFittingId(*, character_id: Any, fitting_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Delete fitting
    Method: DELETE  Path: /characters/{character_id}/fittings/{fitting_id}
    Scopes: esi-fittings.write_fittings.v1
    """
    return execute_operation('DeleteCharactersCharacterIdFittingsFittingId', path_params={"character_id": character_id, "fitting_id": fitting_id}, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterIdFleet(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get character fleet info
    Method: GET  Path: /characters/{character_id}/fleet
    Scopes: esi-fleets.read_fleet.v1
    """
    return execute_operation('GetCharactersCharacterIdFleet', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersFreelanceJobsListing(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """List character freelance jobs
    Method: GET  Path: /characters/{character_id}/freelance-jobs
    Scopes: esi-characters.read_freelance_jobs.v1
    """
    return execute_operation('GetCharactersFreelanceJobsListing', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersFreelanceJobsParticipation(*, character_id: Any, job_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get character freelance job participation
    Method: GET  Path: /characters/{character_id}/freelance-jobs/{job_id}/participation
    Scopes: esi-characters.read_freelance_jobs.v1
    """
    return execute_operation('GetCharactersFreelanceJobsParticipation', path_params={"character_id": character_id, "job_id": job_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdFwStats(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Overview of a character involved in faction warfare
    Method: GET  Path: /characters/{character_id}/fw/stats
    Scopes: esi-characters.read_fw_stats.v1
    """
    return execute_operation('GetCharactersCharacterIdFwStats', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdImplants(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get active implants
    Method: GET  Path: /characters/{character_id}/implants
    Scopes: esi-clones.read_implants.v1
    """
    return execute_operation('GetCharactersCharacterIdImplants', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdIndustryJobs(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """List character industry jobs
    Method: GET  Path: /characters/{character_id}/industry/jobs
    Scopes: esi-industry.read_character_jobs.v1
    """
    return execute_operation('GetCharactersCharacterIdIndustryJobs', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdKillmailsRecent(*, character_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get a character's recent kills and losses
    Method: GET  Path: /characters/{character_id}/killmails/recent
    Scopes: esi-killmails.read_killmails.v1
    """
    if all_pages:
        return fetch_all_pages('GetCharactersCharacterIdKillmailsRecent', path_params={"character_id": character_id}, query_params=query_params, token=token)
    return execute_operation('GetCharactersCharacterIdKillmailsRecent', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdLocation(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get character location
    Method: GET  Path: /characters/{character_id}/location
    Scopes: esi-location.read_location.v1
    """
    return execute_operation('GetCharactersCharacterIdLocation', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdLoyaltyPoints(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get loyalty points
    Method: GET  Path: /characters/{character_id}/loyalty/points
    Scopes: esi-characters.read_loyalty.v1
    """
    return execute_operation('GetCharactersCharacterIdLoyaltyPoints', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdMail(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Return mail headers
    Method: GET  Path: /characters/{character_id}/mail
    Scopes: esi-mail.read_mail.v1
    """
    return execute_operation('GetCharactersCharacterIdMail', path_params={"character_id": character_id}, query_params=query_params, token=token)

def PostCharactersCharacterIdMail(*, character_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Send a new mail
    Method: POST  Path: /characters/{character_id}/mail
    Scopes: esi-mail.send_mail.v1
    """
    return execute_operation('PostCharactersCharacterIdMail', path_params={"character_id": character_id}, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterIdMailLabels(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get mail labels and unread counts
    Method: GET  Path: /characters/{character_id}/mail/labels
    Scopes: esi-mail.read_mail.v1
    """
    return execute_operation('GetCharactersCharacterIdMailLabels', path_params={"character_id": character_id}, query_params=query_params, token=token)

def PostCharactersCharacterIdMailLabels(*, character_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Create a mail label
    Method: POST  Path: /characters/{character_id}/mail/labels
    Scopes: esi-mail.organize_mail.v1
    """
    return execute_operation('PostCharactersCharacterIdMailLabels', path_params={"character_id": character_id}, query_params=query_params, token=token, json_body=json_body)

def DeleteCharactersCharacterIdMailLabelsLabelId(*, character_id: Any, label_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Delete a mail label
    Method: DELETE  Path: /characters/{character_id}/mail/labels/{label_id}
    Scopes: esi-mail.organize_mail.v1
    """
    return execute_operation('DeleteCharactersCharacterIdMailLabelsLabelId', path_params={"character_id": character_id, "label_id": label_id}, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterIdMailLists(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Return mailing list subscriptions
    Method: GET  Path: /characters/{character_id}/mail/lists
    Scopes: esi-mail.read_mail.v1
    """
    return execute_operation('GetCharactersCharacterIdMailLists', path_params={"character_id": character_id}, query_params=query_params, token=token)

def DeleteCharactersCharacterIdMailMailId(*, character_id: Any, mail_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Delete a mail
    Method: DELETE  Path: /characters/{character_id}/mail/{mail_id}
    Scopes: esi-mail.organize_mail.v1
    """
    return execute_operation('DeleteCharactersCharacterIdMailMailId', path_params={"character_id": character_id, "mail_id": mail_id}, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterIdMailMailId(*, character_id: Any, mail_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Return a mail
    Method: GET  Path: /characters/{character_id}/mail/{mail_id}
    Scopes: esi-mail.read_mail.v1
    """
    return execute_operation('GetCharactersCharacterIdMailMailId', path_params={"character_id": character_id, "mail_id": mail_id}, query_params=query_params, token=token)

def PutCharactersCharacterIdMailMailId(*, character_id: Any, mail_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Update metadata about a mail
    Method: PUT  Path: /characters/{character_id}/mail/{mail_id}
    Scopes: esi-mail.organize_mail.v1
    """
    return execute_operation('PutCharactersCharacterIdMailMailId', path_params={"character_id": character_id, "mail_id": mail_id}, query_params=query_params, token=token, json_body=json_body)

def GetCharactersCharacterIdMedals(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get medals
    Method: GET  Path: /characters/{character_id}/medals
    Scopes: esi-characters.read_medals.v1
    """
    return execute_operation('GetCharactersCharacterIdMedals', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdMining(*, character_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Character mining ledger
    Method: GET  Path: /characters/{character_id}/mining
    Scopes: esi-industry.read_character_mining.v1
    """
    if all_pages:
        return fetch_all_pages('GetCharactersCharacterIdMining', path_params={"character_id": character_id}, query_params=query_params, token=token)
    return execute_operation('GetCharactersCharacterIdMining', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdNotifications(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get character notifications
    Method: GET  Path: /characters/{character_id}/notifications
    Scopes: esi-characters.read_notifications.v1
    """
    return execute_operation('GetCharactersCharacterIdNotifications', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdNotificationsContacts(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get new contact notifications
    Method: GET  Path: /characters/{character_id}/notifications/contacts
    Scopes: esi-characters.read_notifications.v1
    """
    return execute_operation('GetCharactersCharacterIdNotificationsContacts', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdOnline(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get character online
    Method: GET  Path: /characters/{character_id}/online
    Scopes: esi-location.read_online.v1
    """
    return execute_operation('GetCharactersCharacterIdOnline', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdOrders(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """List open orders from a character
    Method: GET  Path: /characters/{character_id}/orders
    Scopes: esi-markets.read_character_orders.v1
    """
    return execute_operation('GetCharactersCharacterIdOrders', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdOrdersHistory(*, character_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """List historical orders by a character
    Method: GET  Path: /characters/{character_id}/orders/history
    Scopes: esi-markets.read_character_orders.v1
    """
    if all_pages:
        return fetch_all_pages('GetCharactersCharacterIdOrdersHistory', path_params={"character_id": character_id}, query_params=query_params, token=token)
    return execute_operation('GetCharactersCharacterIdOrdersHistory', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdPlanets(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get colonies
    Method: GET  Path: /characters/{character_id}/planets
    Scopes: esi-planets.manage_planets.v1
    """
    return execute_operation('GetCharactersCharacterIdPlanets', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdPlanetsPlanetId(*, character_id: Any, planet_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get colony layout
    Method: GET  Path: /characters/{character_id}/planets/{planet_id}
    Scopes: esi-planets.manage_planets.v1
    """
    return execute_operation('GetCharactersCharacterIdPlanetsPlanetId', path_params={"character_id": character_id, "planet_id": planet_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdPortrait(*, character_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get character portraits
    Method: GET  Path: /characters/{character_id}/portrait
    """
    return execute_operation('GetCharactersCharacterIdPortrait', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdRoles(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get character corporation roles
    Method: GET  Path: /characters/{character_id}/roles
    Scopes: esi-characters.read_corporation_roles.v1
    """
    return execute_operation('GetCharactersCharacterIdRoles', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdSearch(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Search on a string
    Method: GET  Path: /characters/{character_id}/search
    Scopes: esi-search.search_structures.v1
    """
    return execute_operation('GetCharactersCharacterIdSearch', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdShip(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get current ship
    Method: GET  Path: /characters/{character_id}/ship
    Scopes: esi-location.read_ship_type.v1
    """
    return execute_operation('GetCharactersCharacterIdShip', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdSkillqueue(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get character's skill queue
    Method: GET  Path: /characters/{character_id}/skillqueue
    Scopes: esi-skills.read_skillqueue.v1
    """
    return execute_operation('GetCharactersCharacterIdSkillqueue', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdSkills(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get character skills
    Method: GET  Path: /characters/{character_id}/skills
    Scopes: esi-skills.read_skills.v1
    """
    return execute_operation('GetCharactersCharacterIdSkills', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdStandings(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get standings
    Method: GET  Path: /characters/{character_id}/standings
    Scopes: esi-characters.read_standings.v1
    """
    return execute_operation('GetCharactersCharacterIdStandings', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdTitles(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get character corporation titles
    Method: GET  Path: /characters/{character_id}/titles
    Scopes: esi-characters.read_titles.v1
    """
    return execute_operation('GetCharactersCharacterIdTitles', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdWallet(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get a character's wallet balance
    Method: GET  Path: /characters/{character_id}/wallet
    Scopes: esi-wallet.read_character_wallet.v1
    """
    return execute_operation('GetCharactersCharacterIdWallet', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdWalletJournal(*, character_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get character wallet journal
    Method: GET  Path: /characters/{character_id}/wallet/journal
    Scopes: esi-wallet.read_character_wallet.v1
    """
    if all_pages:
        return fetch_all_pages('GetCharactersCharacterIdWalletJournal', path_params={"character_id": character_id}, query_params=query_params, token=token)
    return execute_operation('GetCharactersCharacterIdWalletJournal', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetCharactersCharacterIdWalletTransactions(*, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get wallet transactions
    Method: GET  Path: /characters/{character_id}/wallet/transactions
    Scopes: esi-wallet.read_character_wallet.v1
    """
    return execute_operation('GetCharactersCharacterIdWalletTransactions', path_params={"character_id": character_id}, query_params=query_params, token=token)

def GetContractsPublicBidsContractId(*, contract_id: Any, token: str | None = None, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get public contract bids
    Method: GET  Path: /contracts/public/bids/{contract_id}
    """
    if all_pages:
        return fetch_all_pages('GetContractsPublicBidsContractId', path_params={"contract_id": contract_id}, query_params=query_params, token=token)
    return execute_operation('GetContractsPublicBidsContractId', path_params={"contract_id": contract_id}, query_params=query_params, token=token)

def GetContractsPublicItemsContractId(*, contract_id: Any, token: str | None = None, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get public contract items
    Method: GET  Path: /contracts/public/items/{contract_id}
    """
    if all_pages:
        return fetch_all_pages('GetContractsPublicItemsContractId', path_params={"contract_id": contract_id}, query_params=query_params, token=token)
    return execute_operation('GetContractsPublicItemsContractId', path_params={"contract_id": contract_id}, query_params=query_params, token=token)

def GetContractsPublicRegionId(*, region_id: Any, token: str | None = None, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get public contracts
    Method: GET  Path: /contracts/public/{region_id}
    """
    if all_pages:
        return fetch_all_pages('GetContractsPublicRegionId', path_params={"region_id": region_id}, query_params=query_params, token=token)
    return execute_operation('GetContractsPublicRegionId', path_params={"region_id": region_id}, query_params=query_params, token=token)

def GetCorporationCorporationIdMiningExtractions(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Moon extraction timers
    Method: GET  Path: /corporation/{corporation_id}/mining/extractions
    Scopes: esi-industry.read_corporation_mining.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationCorporationIdMiningExtractions', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationCorporationIdMiningExtractions', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationCorporationIdMiningObservers(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Corporation mining observers
    Method: GET  Path: /corporation/{corporation_id}/mining/observers
    Scopes: esi-industry.read_corporation_mining.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationCorporationIdMiningObservers', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationCorporationIdMiningObservers', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationCorporationIdMiningObserversObserverId(*, corporation_id: Any, observer_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Observed corporation mining
    Method: GET  Path: /corporation/{corporation_id}/mining/observers/{observer_id}
    Scopes: esi-industry.read_corporation_mining.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationCorporationIdMiningObserversObserverId', path_params={"corporation_id": corporation_id, "observer_id": observer_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationCorporationIdMiningObserversObserverId', path_params={"corporation_id": corporation_id, "observer_id": observer_id}, query_params=query_params, token=token)

def GetCorporationsNpccorps(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get npc corporations
    Method: GET  Path: /corporations/npccorps
    """
    return execute_operation('GetCorporationsNpccorps', path_params=None, query_params=query_params, token=token)

def GetCorporationsCorporationId(*, corporation_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get corporation's public information
    Method: GET  Path: /corporations/{corporation_id}
    """
    return execute_operation('GetCorporationsCorporationId', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdAlliancehistory(*, corporation_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get alliance history
    Method: GET  Path: /corporations/{corporation_id}/alliancehistory
    """
    return execute_operation('GetCorporationsCorporationIdAlliancehistory', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdAssets(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation assets
    Method: GET  Path: /corporations/{corporation_id}/assets
    Scopes: esi-assets.read_corporation_assets.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdAssets', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdAssets', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def PostCorporationsCorporationIdAssetsLocations(*, corporation_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Get corporation asset locations
    Method: POST  Path: /corporations/{corporation_id}/assets/locations
    Scopes: esi-assets.read_corporation_assets.v1
    """
    return execute_operation('PostCorporationsCorporationIdAssetsLocations', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token, json_body=json_body)

def PostCorporationsCorporationIdAssetsNames(*, corporation_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Get corporation asset names
    Method: POST  Path: /corporations/{corporation_id}/assets/names
    Scopes: esi-assets.read_corporation_assets.v1
    """
    return execute_operation('PostCorporationsCorporationIdAssetsNames', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token, json_body=json_body)

def GetCorporationsCorporationIdBlueprints(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation blueprints
    Method: GET  Path: /corporations/{corporation_id}/blueprints
    Scopes: esi-corporations.read_blueprints.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdBlueprints', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdBlueprints', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdContacts(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation contacts
    Method: GET  Path: /corporations/{corporation_id}/contacts
    Scopes: esi-corporations.read_contacts.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdContacts', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdContacts', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdContactsLabels(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get corporation contact labels
    Method: GET  Path: /corporations/{corporation_id}/contacts/labels
    Scopes: esi-corporations.read_contacts.v1
    """
    return execute_operation('GetCorporationsCorporationIdContactsLabels', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdContainersLogs(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get all corporation ALSC logs
    Method: GET  Path: /corporations/{corporation_id}/containers/logs
    Scopes: esi-corporations.read_container_logs.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdContainersLogs', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdContainersLogs', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdContracts(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation contracts
    Method: GET  Path: /corporations/{corporation_id}/contracts
    Scopes: esi-contracts.read_corporation_contracts.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdContracts', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdContracts', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdContractsContractIdBids(*, contract_id: Any, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation contract bids
    Method: GET  Path: /corporations/{corporation_id}/contracts/{contract_id}/bids
    Scopes: esi-contracts.read_corporation_contracts.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdContractsContractIdBids', path_params={"contract_id": contract_id, "corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdContractsContractIdBids', path_params={"contract_id": contract_id, "corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdContractsContractIdItems(*, contract_id: Any, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get corporation contract items
    Method: GET  Path: /corporations/{corporation_id}/contracts/{contract_id}/items
    Scopes: esi-contracts.read_corporation_contracts.v1
    """
    return execute_operation('GetCorporationsCorporationIdContractsContractIdItems', path_params={"contract_id": contract_id, "corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdCustomsOffices(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """List corporation customs offices
    Method: GET  Path: /corporations/{corporation_id}/customs_offices
    Scopes: esi-planets.read_customs_offices.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdCustomsOffices', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdCustomsOffices', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdDivisions(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get corporation divisions
    Method: GET  Path: /corporations/{corporation_id}/divisions
    Scopes: esi-corporations.read_divisions.v1
    """
    return execute_operation('GetCorporationsCorporationIdDivisions', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdFacilities(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get corporation facilities
    Method: GET  Path: /corporations/{corporation_id}/facilities
    Scopes: esi-corporations.read_facilities.v1
    """
    return execute_operation('GetCorporationsCorporationIdFacilities', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsFreelanceJobsListing(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """List corporation freelance jobs
    Method: GET  Path: /corporations/{corporation_id}/freelance-jobs
    Scopes: esi-corporations.read_freelance_jobs.v1
    """
    return execute_operation('GetCorporationsFreelanceJobsListing', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsFreelanceJobsParticipants(*, corporation_id: Any, job_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """List participants of a freelance job
    Method: GET  Path: /corporations/{corporation_id}/freelance-jobs/{job_id}/participants
    Scopes: esi-corporations.read_freelance_jobs.v1
    """
    return execute_operation('GetCorporationsFreelanceJobsParticipants', path_params={"corporation_id": corporation_id, "job_id": job_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdFwStats(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Overview of a corporation involved in faction warfare
    Method: GET  Path: /corporations/{corporation_id}/fw/stats
    Scopes: esi-corporations.read_fw_stats.v1
    """
    return execute_operation('GetCorporationsCorporationIdFwStats', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdIcons(*, corporation_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get corporation icon
    Method: GET  Path: /corporations/{corporation_id}/icons
    """
    return execute_operation('GetCorporationsCorporationIdIcons', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdIndustryJobs(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """List corporation industry jobs
    Method: GET  Path: /corporations/{corporation_id}/industry/jobs
    Scopes: esi-industry.read_corporation_jobs.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdIndustryJobs', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdIndustryJobs', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdKillmailsRecent(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get a corporation's recent kills and losses
    Method: GET  Path: /corporations/{corporation_id}/killmails/recent
    Scopes: esi-killmails.read_corporation_killmails.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdKillmailsRecent', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdKillmailsRecent', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdMedals(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation medals
    Method: GET  Path: /corporations/{corporation_id}/medals
    Scopes: esi-corporations.read_medals.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdMedals', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdMedals', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdMedalsIssued(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation issued medals
    Method: GET  Path: /corporations/{corporation_id}/medals/issued
    Scopes: esi-corporations.read_medals.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdMedalsIssued', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdMedalsIssued', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdMembers(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get corporation members
    Method: GET  Path: /corporations/{corporation_id}/members
    Scopes: esi-corporations.read_corporation_membership.v1
    """
    return execute_operation('GetCorporationsCorporationIdMembers', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdMembersLimit(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get corporation member limit
    Method: GET  Path: /corporations/{corporation_id}/members/limit
    Scopes: esi-corporations.track_members.v1
    """
    return execute_operation('GetCorporationsCorporationIdMembersLimit', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdMembersTitles(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get corporation's members' titles
    Method: GET  Path: /corporations/{corporation_id}/members/titles
    Scopes: esi-corporations.read_titles.v1
    """
    return execute_operation('GetCorporationsCorporationIdMembersTitles', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdMembertracking(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Track corporation members
    Method: GET  Path: /corporations/{corporation_id}/membertracking
    Scopes: esi-corporations.track_members.v1
    """
    return execute_operation('GetCorporationsCorporationIdMembertracking', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdOrders(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """List open orders from a corporation
    Method: GET  Path: /corporations/{corporation_id}/orders
    Scopes: esi-markets.read_corporation_orders.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdOrders', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdOrders', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdOrdersHistory(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """List historical orders from a corporation
    Method: GET  Path: /corporations/{corporation_id}/orders/history
    Scopes: esi-markets.read_corporation_orders.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdOrdersHistory', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdOrdersHistory', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsProjectsListing(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """List corporation projects
    Method: GET  Path: /corporations/{corporation_id}/projects
    Scopes: esi-corporations.read_projects.v1
    """
    return execute_operation('GetCorporationsProjectsListing', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsProjectsDetail(*, corporation_id: Any, project_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get project details
    Method: GET  Path: /corporations/{corporation_id}/projects/{project_id}
    Scopes: esi-corporations.read_projects.v1
    """
    return execute_operation('GetCorporationsProjectsDetail', path_params={"corporation_id": corporation_id, "project_id": project_id}, query_params=query_params, token=token)

def GetCorporationsProjectsContribution(*, corporation_id: Any, project_id: Any, character_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get your project contribution
    Method: GET  Path: /corporations/{corporation_id}/projects/{project_id}/contribution/{character_id}
    Scopes: esi-corporations.read_projects.v1
    """
    return execute_operation('GetCorporationsProjectsContribution', path_params={"corporation_id": corporation_id, "project_id": project_id, "character_id": character_id}, query_params=query_params, token=token)

def GetCorporationsProjectsContributors(*, corporation_id: Any, project_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """List project contributors
    Method: GET  Path: /corporations/{corporation_id}/projects/{project_id}/contributors
    Scopes: esi-corporations.read_projects.v1
    """
    return execute_operation('GetCorporationsProjectsContributors', path_params={"corporation_id": corporation_id, "project_id": project_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdRoles(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get corporation member roles
    Method: GET  Path: /corporations/{corporation_id}/roles
    Scopes: esi-corporations.read_corporation_membership.v1
    """
    return execute_operation('GetCorporationsCorporationIdRoles', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdRolesHistory(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation member roles history
    Method: GET  Path: /corporations/{corporation_id}/roles/history
    Scopes: esi-corporations.read_corporation_membership.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdRolesHistory', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdRolesHistory', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdShareholders(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation shareholders
    Method: GET  Path: /corporations/{corporation_id}/shareholders
    Scopes: esi-wallet.read_corporation_wallets.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdShareholders', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdShareholders', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdStandings(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation standings
    Method: GET  Path: /corporations/{corporation_id}/standings
    Scopes: esi-corporations.read_standings.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdStandings', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdStandings', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdStarbases(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation starbases (POSes)
    Method: GET  Path: /corporations/{corporation_id}/starbases
    Scopes: esi-corporations.read_starbases.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdStarbases', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdStarbases', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdStarbasesStarbaseId(*, corporation_id: Any, starbase_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get starbase (POS) detail
    Method: GET  Path: /corporations/{corporation_id}/starbases/{starbase_id}
    Scopes: esi-corporations.read_starbases.v1
    """
    return execute_operation('GetCorporationsCorporationIdStarbasesStarbaseId', path_params={"corporation_id": corporation_id, "starbase_id": starbase_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdStructures(*, corporation_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation structures
    Method: GET  Path: /corporations/{corporation_id}/structures
    Scopes: esi-corporations.read_structures.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdStructures', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdStructures', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdTitles(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get corporation titles
    Method: GET  Path: /corporations/{corporation_id}/titles
    Scopes: esi-corporations.read_titles.v1
    """
    return execute_operation('GetCorporationsCorporationIdTitles', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdWallets(*, corporation_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Returns a corporation's wallet balance
    Method: GET  Path: /corporations/{corporation_id}/wallets
    Scopes: esi-wallet.read_corporation_wallets.v1
    """
    return execute_operation('GetCorporationsCorporationIdWallets', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetCorporationsCorporationIdWalletsDivisionJournal(*, corporation_id: Any, division: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get corporation wallet journal
    Method: GET  Path: /corporations/{corporation_id}/wallets/{division}/journal
    Scopes: esi-wallet.read_corporation_wallets.v1
    """
    if all_pages:
        return fetch_all_pages('GetCorporationsCorporationIdWalletsDivisionJournal', path_params={"corporation_id": corporation_id, "division": division}, query_params=query_params, token=token)
    return execute_operation('GetCorporationsCorporationIdWalletsDivisionJournal', path_params={"corporation_id": corporation_id, "division": division}, query_params=query_params, token=token)

def GetCorporationsCorporationIdWalletsDivisionTransactions(*, corporation_id: Any, division: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get corporation wallet transactions
    Method: GET  Path: /corporations/{corporation_id}/wallets/{division}/transactions
    Scopes: esi-wallet.read_corporation_wallets.v1
    """
    return execute_operation('GetCorporationsCorporationIdWalletsDivisionTransactions', path_params={"corporation_id": corporation_id, "division": division}, query_params=query_params, token=token)

def GetDogmaAttributes(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get attributes
    Method: GET  Path: /dogma/attributes
    """
    return execute_operation('GetDogmaAttributes', path_params=None, query_params=query_params, token=token)

def GetDogmaAttributesAttributeId(*, attribute_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get attribute information
    Method: GET  Path: /dogma/attributes/{attribute_id}
    """
    return execute_operation('GetDogmaAttributesAttributeId', path_params={"attribute_id": attribute_id}, query_params=query_params, token=token)

def GetDogmaDynamicItemsTypeIdItemId(*, item_id: Any, type_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get dynamic item information
    Method: GET  Path: /dogma/dynamic/items/{type_id}/{item_id}
    """
    return execute_operation('GetDogmaDynamicItemsTypeIdItemId', path_params={"item_id": item_id, "type_id": type_id}, query_params=query_params, token=token)

def GetDogmaEffects(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get effects
    Method: GET  Path: /dogma/effects
    """
    return execute_operation('GetDogmaEffects', path_params=None, query_params=query_params, token=token)

def GetDogmaEffectsEffectId(*, effect_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get effect information
    Method: GET  Path: /dogma/effects/{effect_id}
    """
    return execute_operation('GetDogmaEffectsEffectId', path_params={"effect_id": effect_id}, query_params=query_params, token=token)

def GetFleetsFleetId(*, fleet_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get fleet information
    Method: GET  Path: /fleets/{fleet_id}
    Scopes: esi-fleets.read_fleet.v1
    """
    return execute_operation('GetFleetsFleetId', path_params={"fleet_id": fleet_id}, query_params=query_params, token=token)

def PutFleetsFleetId(*, fleet_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Update fleet
    Method: PUT  Path: /fleets/{fleet_id}
    Scopes: esi-fleets.write_fleet.v1
    """
    return execute_operation('PutFleetsFleetId', path_params={"fleet_id": fleet_id}, query_params=query_params, token=token, json_body=json_body)

def GetFleetsFleetIdMembers(*, fleet_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get fleet members
    Method: GET  Path: /fleets/{fleet_id}/members
    Scopes: esi-fleets.read_fleet.v1
    """
    return execute_operation('GetFleetsFleetIdMembers', path_params={"fleet_id": fleet_id}, query_params=query_params, token=token)

def PostFleetsFleetIdMembers(*, fleet_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Create fleet invitation
    Method: POST  Path: /fleets/{fleet_id}/members
    Scopes: esi-fleets.write_fleet.v1
    """
    return execute_operation('PostFleetsFleetIdMembers', path_params={"fleet_id": fleet_id}, query_params=query_params, token=token, json_body=json_body)

def DeleteFleetsFleetIdMembersMemberId(*, fleet_id: Any, member_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Kick fleet member
    Method: DELETE  Path: /fleets/{fleet_id}/members/{member_id}
    Scopes: esi-fleets.write_fleet.v1
    """
    return execute_operation('DeleteFleetsFleetIdMembersMemberId', path_params={"fleet_id": fleet_id, "member_id": member_id}, query_params=query_params, token=token, json_body=json_body)

def PutFleetsFleetIdMembersMemberId(*, fleet_id: Any, member_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Move fleet member
    Method: PUT  Path: /fleets/{fleet_id}/members/{member_id}
    Scopes: esi-fleets.write_fleet.v1
    """
    return execute_operation('PutFleetsFleetIdMembersMemberId', path_params={"fleet_id": fleet_id, "member_id": member_id}, query_params=query_params, token=token, json_body=json_body)

def DeleteFleetsFleetIdSquadsSquadId(*, fleet_id: Any, squad_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Delete fleet squad
    Method: DELETE  Path: /fleets/{fleet_id}/squads/{squad_id}
    Scopes: esi-fleets.write_fleet.v1
    """
    return execute_operation('DeleteFleetsFleetIdSquadsSquadId', path_params={"fleet_id": fleet_id, "squad_id": squad_id}, query_params=query_params, token=token, json_body=json_body)

def PutFleetsFleetIdSquadsSquadId(*, fleet_id: Any, squad_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Rename fleet squad
    Method: PUT  Path: /fleets/{fleet_id}/squads/{squad_id}
    Scopes: esi-fleets.write_fleet.v1
    """
    return execute_operation('PutFleetsFleetIdSquadsSquadId', path_params={"fleet_id": fleet_id, "squad_id": squad_id}, query_params=query_params, token=token, json_body=json_body)

def GetFleetsFleetIdWings(*, fleet_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get fleet wings
    Method: GET  Path: /fleets/{fleet_id}/wings
    Scopes: esi-fleets.read_fleet.v1
    """
    return execute_operation('GetFleetsFleetIdWings', path_params={"fleet_id": fleet_id}, query_params=query_params, token=token)

def PostFleetsFleetIdWings(*, fleet_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Create fleet wing
    Method: POST  Path: /fleets/{fleet_id}/wings
    Scopes: esi-fleets.write_fleet.v1
    """
    return execute_operation('PostFleetsFleetIdWings', path_params={"fleet_id": fleet_id}, query_params=query_params, token=token, json_body=json_body)

def DeleteFleetsFleetIdWingsWingId(*, fleet_id: Any, wing_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Delete fleet wing
    Method: DELETE  Path: /fleets/{fleet_id}/wings/{wing_id}
    Scopes: esi-fleets.write_fleet.v1
    """
    return execute_operation('DeleteFleetsFleetIdWingsWingId', path_params={"fleet_id": fleet_id, "wing_id": wing_id}, query_params=query_params, token=token, json_body=json_body)

def PutFleetsFleetIdWingsWingId(*, fleet_id: Any, wing_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Rename fleet wing
    Method: PUT  Path: /fleets/{fleet_id}/wings/{wing_id}
    Scopes: esi-fleets.write_fleet.v1
    """
    return execute_operation('PutFleetsFleetIdWingsWingId', path_params={"fleet_id": fleet_id, "wing_id": wing_id}, query_params=query_params, token=token, json_body=json_body)

def PostFleetsFleetIdWingsWingIdSquads(*, fleet_id: Any, wing_id: Any, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Create fleet squad
    Method: POST  Path: /fleets/{fleet_id}/wings/{wing_id}/squads
    Scopes: esi-fleets.write_fleet.v1
    """
    return execute_operation('PostFleetsFleetIdWingsWingIdSquads', path_params={"fleet_id": fleet_id, "wing_id": wing_id}, query_params=query_params, token=token, json_body=json_body)

def GetFreelanceJobsListing(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List freelance jobs
    Method: GET  Path: /freelance-jobs
    """
    return execute_operation('GetFreelanceJobsListing', path_params=None, query_params=query_params, token=token)

def GetFreelanceJobsDetail(*, job_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get freelance job details
    Method: GET  Path: /freelance-jobs/{job_id}
    """
    return execute_operation('GetFreelanceJobsDetail', path_params={"job_id": job_id}, query_params=query_params, token=token)

def GetFwLeaderboards(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List of the top factions in faction warfare
    Method: GET  Path: /fw/leaderboards
    """
    return execute_operation('GetFwLeaderboards', path_params=None, query_params=query_params, token=token)

def GetFwLeaderboardsCharacters(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List of the top pilots in faction warfare
    Method: GET  Path: /fw/leaderboards/characters
    """
    return execute_operation('GetFwLeaderboardsCharacters', path_params=None, query_params=query_params, token=token)

def GetFwLeaderboardsCorporations(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List of the top corporations in faction warfare
    Method: GET  Path: /fw/leaderboards/corporations
    """
    return execute_operation('GetFwLeaderboardsCorporations', path_params=None, query_params=query_params, token=token)

def GetFwStats(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """An overview of statistics about factions involved in faction warfare
    Method: GET  Path: /fw/stats
    """
    return execute_operation('GetFwStats', path_params=None, query_params=query_params, token=token)

def GetFwSystems(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Ownership of faction warfare systems
    Method: GET  Path: /fw/systems
    """
    return execute_operation('GetFwSystems', path_params=None, query_params=query_params, token=token)

def GetFwWars(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Data about which NPC factions are at war
    Method: GET  Path: /fw/wars
    """
    return execute_operation('GetFwWars', path_params=None, query_params=query_params, token=token)

def GetIncursions(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List incursions
    Method: GET  Path: /incursions
    """
    return execute_operation('GetIncursions', path_params=None, query_params=query_params, token=token)

def GetIndustryFacilities(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List industry facilities
    Method: GET  Path: /industry/facilities
    """
    return execute_operation('GetIndustryFacilities', path_params=None, query_params=query_params, token=token)

def GetIndustrySystems(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List solar system cost indices
    Method: GET  Path: /industry/systems
    """
    return execute_operation('GetIndustrySystems', path_params=None, query_params=query_params, token=token)

def GetInsurancePrices(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List insurance levels
    Method: GET  Path: /insurance/prices
    """
    return execute_operation('GetInsurancePrices', path_params=None, query_params=query_params, token=token)

def GetKillmailsKillmailIdKillmailHash(*, killmail_hash: Any, killmail_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get a single killmail
    Method: GET  Path: /killmails/{killmail_id}/{killmail_hash}
    """
    return execute_operation('GetKillmailsKillmailIdKillmailHash', path_params={"killmail_hash": killmail_hash, "killmail_id": killmail_id}, query_params=query_params, token=token)

def GetLoyaltyStoresCorporationIdOffers(*, corporation_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List loyalty store offers
    Method: GET  Path: /loyalty/stores/{corporation_id}/offers
    """
    return execute_operation('GetLoyaltyStoresCorporationIdOffers', path_params={"corporation_id": corporation_id}, query_params=query_params, token=token)

def GetMarketsGroups(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get item groups
    Method: GET  Path: /markets/groups
    """
    return execute_operation('GetMarketsGroups', path_params=None, query_params=query_params, token=token)

def GetMarketsGroupsMarketGroupId(*, market_group_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get item group information
    Method: GET  Path: /markets/groups/{market_group_id}
    """
    return execute_operation('GetMarketsGroupsMarketGroupId', path_params={"market_group_id": market_group_id}, query_params=query_params, token=token)

def GetMarketsPrices(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List market prices
    Method: GET  Path: /markets/prices
    """
    return execute_operation('GetMarketsPrices', path_params=None, query_params=query_params, token=token)

def GetMarketsStructuresStructureId(*, structure_id: Any, token: str, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """List orders in a structure
    Method: GET  Path: /markets/structures/{structure_id}
    Scopes: esi-markets.structure_markets.v1
    """
    if all_pages:
        return fetch_all_pages('GetMarketsStructuresStructureId', path_params={"structure_id": structure_id}, query_params=query_params, token=token)
    return execute_operation('GetMarketsStructuresStructureId', path_params={"structure_id": structure_id}, query_params=query_params, token=token)

def GetMarketsRegionIdHistory(*, region_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List historical market statistics in a region
    Method: GET  Path: /markets/{region_id}/history
    """
    return execute_operation('GetMarketsRegionIdHistory', path_params={"region_id": region_id}, query_params=query_params, token=token)

def GetMarketsRegionIdOrders(*, region_id: Any, token: str | None = None, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """List orders in a region
    Method: GET  Path: /markets/{region_id}/orders
    """
    if all_pages:
        return fetch_all_pages('GetMarketsRegionIdOrders', path_params={"region_id": region_id}, query_params=query_params, token=token)
    return execute_operation('GetMarketsRegionIdOrders', path_params={"region_id": region_id}, query_params=query_params, token=token)

def GetMarketsRegionIdTypes(*, region_id: Any, token: str | None = None, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """List type IDs relevant to a market
    Method: GET  Path: /markets/{region_id}/types
    """
    if all_pages:
        return fetch_all_pages('GetMarketsRegionIdTypes', path_params={"region_id": region_id}, query_params=query_params, token=token)
    return execute_operation('GetMarketsRegionIdTypes', path_params={"region_id": region_id}, query_params=query_params, token=token)

def GetMetaChangelog(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get changelog
    Method: GET  Path: /meta/changelog
    """
    return execute_operation('GetMetaChangelog', path_params=None, query_params=query_params, token=token)

def GetMetaCompatibilityDates(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get compatibility dates
    Method: GET  Path: /meta/compatibility-dates
    """
    return execute_operation('GetMetaCompatibilityDates', path_params=None, query_params=query_params, token=token)

def GetMetaStatus(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get health status
    Method: GET  Path: /meta/status
    """
    return execute_operation('GetMetaStatus', path_params=None, query_params=query_params, token=token)

def PostRoute(*, origin_system_id: Any, destination_system_id: Any, token: str | None = None, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Get route between two systems
    Method: POST  Path: /route/{origin_system_id}/{destination_system_id}
    """
    return execute_operation('PostRoute', path_params={"origin_system_id": origin_system_id, "destination_system_id": destination_system_id}, query_params=query_params, token=token, json_body=json_body)

def GetSovereigntyCampaigns(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List sovereignty campaigns
    Method: GET  Path: /sovereignty/campaigns
    """
    return execute_operation('GetSovereigntyCampaigns', path_params=None, query_params=query_params, token=token)

def GetSovereigntyMap(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List sovereignty of systems
    Method: GET  Path: /sovereignty/map
    """
    return execute_operation('GetSovereigntyMap', path_params=None, query_params=query_params, token=token)

def GetSovereigntyStructures(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List sovereignty structures
    Method: GET  Path: /sovereignty/structures
    """
    return execute_operation('GetSovereigntyStructures', path_params=None, query_params=query_params, token=token)

def GetStatus(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Retrieve the uptime and player counts
    Method: GET  Path: /status
    """
    return execute_operation('GetStatus', path_params=None, query_params=query_params, token=token)

def PostUiAutopilotWaypoint(*, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Set Autopilot Waypoint
    Method: POST  Path: /ui/autopilot/waypoint
    Scopes: esi-ui.write_waypoint.v1
    """
    return execute_operation('PostUiAutopilotWaypoint', path_params=None, query_params=query_params, token=token, json_body=json_body)

def PostUiOpenwindowContract(*, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Open Contract Window
    Method: POST  Path: /ui/openwindow/contract
    Scopes: esi-ui.open_window.v1
    """
    return execute_operation('PostUiOpenwindowContract', path_params=None, query_params=query_params, token=token, json_body=json_body)

def PostUiOpenwindowInformation(*, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Open Information Window
    Method: POST  Path: /ui/openwindow/information
    Scopes: esi-ui.open_window.v1
    """
    return execute_operation('PostUiOpenwindowInformation', path_params=None, query_params=query_params, token=token, json_body=json_body)

def PostUiOpenwindowMarketdetails(*, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Open Market Details
    Method: POST  Path: /ui/openwindow/marketdetails
    Scopes: esi-ui.open_window.v1
    """
    return execute_operation('PostUiOpenwindowMarketdetails', path_params=None, query_params=query_params, token=token, json_body=json_body)

def PostUiOpenwindowNewmail(*, token: str, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Open New Mail Window
    Method: POST  Path: /ui/openwindow/newmail
    Scopes: esi-ui.open_window.v1
    """
    return execute_operation('PostUiOpenwindowNewmail', path_params=None, query_params=query_params, token=token, json_body=json_body)

def GetUniverseAncestries(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get ancestries
    Method: GET  Path: /universe/ancestries
    """
    return execute_operation('GetUniverseAncestries', path_params=None, query_params=query_params, token=token)

def GetUniverseAsteroidBeltsAsteroidBeltId(*, asteroid_belt_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get asteroid belt information
    Method: GET  Path: /universe/asteroid_belts/{asteroid_belt_id}
    """
    return execute_operation('GetUniverseAsteroidBeltsAsteroidBeltId', path_params={"asteroid_belt_id": asteroid_belt_id}, query_params=query_params, token=token)

def GetUniverseBloodlines(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get bloodlines
    Method: GET  Path: /universe/bloodlines
    """
    return execute_operation('GetUniverseBloodlines', path_params=None, query_params=query_params, token=token)

def GetUniverseCategories(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get item categories
    Method: GET  Path: /universe/categories
    """
    return execute_operation('GetUniverseCategories', path_params=None, query_params=query_params, token=token)

def GetUniverseCategoriesCategoryId(*, category_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get item category information
    Method: GET  Path: /universe/categories/{category_id}
    """
    return execute_operation('GetUniverseCategoriesCategoryId', path_params={"category_id": category_id}, query_params=query_params, token=token)

def GetUniverseConstellations(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get constellations
    Method: GET  Path: /universe/constellations
    """
    return execute_operation('GetUniverseConstellations', path_params=None, query_params=query_params, token=token)

def GetUniverseConstellationsConstellationId(*, constellation_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get constellation information
    Method: GET  Path: /universe/constellations/{constellation_id}
    """
    return execute_operation('GetUniverseConstellationsConstellationId', path_params={"constellation_id": constellation_id}, query_params=query_params, token=token)

def GetUniverseFactions(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get factions
    Method: GET  Path: /universe/factions
    """
    return execute_operation('GetUniverseFactions', path_params=None, query_params=query_params, token=token)

def GetUniverseGraphics(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get graphics
    Method: GET  Path: /universe/graphics
    """
    return execute_operation('GetUniverseGraphics', path_params=None, query_params=query_params, token=token)

def GetUniverseGraphicsGraphicId(*, graphic_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get graphic information
    Method: GET  Path: /universe/graphics/{graphic_id}
    """
    return execute_operation('GetUniverseGraphicsGraphicId', path_params={"graphic_id": graphic_id}, query_params=query_params, token=token)

def GetUniverseGroups(*, token: str | None = None, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get item groups
    Method: GET  Path: /universe/groups
    """
    if all_pages:
        return fetch_all_pages('GetUniverseGroups', path_params=None, query_params=query_params, token=token)
    return execute_operation('GetUniverseGroups', path_params=None, query_params=query_params, token=token)

def GetUniverseGroupsGroupId(*, group_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get item group information
    Method: GET  Path: /universe/groups/{group_id}
    """
    return execute_operation('GetUniverseGroupsGroupId', path_params={"group_id": group_id}, query_params=query_params, token=token)

def PostUniverseIds(*, token: str | None = None, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Bulk names to IDs
    Method: POST  Path: /universe/ids
    """
    return execute_operation('PostUniverseIds', path_params=None, query_params=query_params, token=token, json_body=json_body)

def GetUniverseMoonsMoonId(*, moon_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get moon information
    Method: GET  Path: /universe/moons/{moon_id}
    """
    return execute_operation('GetUniverseMoonsMoonId', path_params={"moon_id": moon_id}, query_params=query_params, token=token)

def PostUniverseNames(*, token: str | None = None, query_params: dict | None = None, json_body: Any = None) -> dict | list:
    """Get names and categories for a set of IDs
    Method: POST  Path: /universe/names
    """
    return execute_operation('PostUniverseNames', path_params=None, query_params=query_params, token=token, json_body=json_body)

def GetUniversePlanetsPlanetId(*, planet_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get planet information
    Method: GET  Path: /universe/planets/{planet_id}
    """
    return execute_operation('GetUniversePlanetsPlanetId', path_params={"planet_id": planet_id}, query_params=query_params, token=token)

def GetUniverseRaces(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get character races
    Method: GET  Path: /universe/races
    """
    return execute_operation('GetUniverseRaces', path_params=None, query_params=query_params, token=token)

def GetUniverseRegions(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get regions
    Method: GET  Path: /universe/regions
    """
    return execute_operation('GetUniverseRegions', path_params=None, query_params=query_params, token=token)

def GetUniverseRegionsRegionId(*, region_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get region information
    Method: GET  Path: /universe/regions/{region_id}
    """
    return execute_operation('GetUniverseRegionsRegionId', path_params={"region_id": region_id}, query_params=query_params, token=token)

def GetUniverseSchematicsSchematicId(*, schematic_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get schematic information
    Method: GET  Path: /universe/schematics/{schematic_id}
    """
    return execute_operation('GetUniverseSchematicsSchematicId', path_params={"schematic_id": schematic_id}, query_params=query_params, token=token)

def GetUniverseStargatesStargateId(*, stargate_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get stargate information
    Method: GET  Path: /universe/stargates/{stargate_id}
    """
    return execute_operation('GetUniverseStargatesStargateId', path_params={"stargate_id": stargate_id}, query_params=query_params, token=token)

def GetUniverseStarsStarId(*, star_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get star information
    Method: GET  Path: /universe/stars/{star_id}
    """
    return execute_operation('GetUniverseStarsStarId', path_params={"star_id": star_id}, query_params=query_params, token=token)

def GetUniverseStationsStationId(*, station_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get station information
    Method: GET  Path: /universe/stations/{station_id}
    """
    return execute_operation('GetUniverseStationsStationId', path_params={"station_id": station_id}, query_params=query_params, token=token)

def GetUniverseStructures(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List all public structures
    Method: GET  Path: /universe/structures
    """
    return execute_operation('GetUniverseStructures', path_params=None, query_params=query_params, token=token)

def GetUniverseStructuresStructureId(*, structure_id: Any, token: str, query_params: dict | None = None) -> dict | list:
    """Get structure information
    Method: GET  Path: /universe/structures/{structure_id}
    Scopes: esi-universe.read_structures.v1
    """
    return execute_operation('GetUniverseStructuresStructureId', path_params={"structure_id": structure_id}, query_params=query_params, token=token)

def GetUniverseSystemJumps(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get system jumps
    Method: GET  Path: /universe/system_jumps
    """
    return execute_operation('GetUniverseSystemJumps', path_params=None, query_params=query_params, token=token)

def GetUniverseSystemKills(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get system kills
    Method: GET  Path: /universe/system_kills
    """
    return execute_operation('GetUniverseSystemKills', path_params=None, query_params=query_params, token=token)

def GetUniverseSystems(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get solar systems
    Method: GET  Path: /universe/systems
    """
    return execute_operation('GetUniverseSystems', path_params=None, query_params=query_params, token=token)

def GetUniverseSystemsSystemId(*, system_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get solar system information
    Method: GET  Path: /universe/systems/{system_id}
    """
    return execute_operation('GetUniverseSystemsSystemId', path_params={"system_id": system_id}, query_params=query_params, token=token)

def GetUniverseTypes(*, token: str | None = None, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """Get types
    Method: GET  Path: /universe/types
    """
    if all_pages:
        return fetch_all_pages('GetUniverseTypes', path_params=None, query_params=query_params, token=token)
    return execute_operation('GetUniverseTypes', path_params=None, query_params=query_params, token=token)

def GetUniverseTypesTypeId(*, type_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get type information
    Method: GET  Path: /universe/types/{type_id}
    """
    return execute_operation('GetUniverseTypesTypeId', path_params={"type_id": type_id}, query_params=query_params, token=token)

def GetWars(*, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """List wars
    Method: GET  Path: /wars
    """
    return execute_operation('GetWars', path_params=None, query_params=query_params, token=token)

def GetWarsWarId(*, war_id: Any, token: str | None = None, query_params: dict | None = None) -> dict | list:
    """Get war information
    Method: GET  Path: /wars/{war_id}
    """
    return execute_operation('GetWarsWarId', path_params={"war_id": war_id}, query_params=query_params, token=token)

def GetWarsWarIdKillmails(*, war_id: Any, token: str | None = None, query_params: dict | None = None, all_pages: bool = False) -> dict | list:
    """List kills for a war
    Method: GET  Path: /wars/{war_id}/killmails
    """
    if all_pages:
        return fetch_all_pages('GetWarsWarIdKillmails', path_params={"war_id": war_id}, query_params=query_params, token=token)
    return execute_operation('GetWarsWarIdKillmails', path_params={"war_id": war_id}, query_params=query_params, token=token)
