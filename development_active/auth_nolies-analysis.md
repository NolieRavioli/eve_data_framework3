

`core/auth/` module is for SSO as well as  site management. It acts as the framework for esi token management and site roles

all authentication for the codebase is based around EVE Online SSO.

an owner_id might have many `character_id`s that they control and can access.

## io stuff

there are databases that are seperated by auth.
 - PUBLIC means that anyone can query or write that data
 - PERSONAL means that it is a character_id database
 - CORP means that only people in the corp should be able to query or write data
 - ALLIANCE is the same as corp with a bigger scope.



## website auth

Individuals are given an owner_id. `owner_id` starts at `1` and counts upwards as more users log into the site.

the site owner is always owner_id `1`.

'login' creates a new owner_id and a new character_id with the given token (from callback)

'add toon' adds a new character_id to the owner_id table

auth module owns the `auth_roles` list:
```
owner: 1, roles: ['dashboard', 'market', 'sde'], admin: 1
owner: 2, roles: ['dashboard', 'market', 'sde'], admin: 1
owner: 3, roles: ['dashboard', 'market', 'sde', 'hauler'], admin: 0
```
 - owner 1 is the site owner
 - owner 2 is a site admin
 - owner 3 is a user with 'hauler' application role (they are allowed to use the hauling trade application)

## sso auth

tokens are stored only in private character databases. 