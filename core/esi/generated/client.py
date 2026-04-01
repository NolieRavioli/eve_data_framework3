"""

core/esi/generated/client.py

------------------------

AUTO-GENERATED — do not edit by hand.

Source: ESI compatibility date 2025-12-16



Provides:

  execute_operation(operation_id, *, path_params, query_params, token,

                    json_body, headers, pages) -> dict | list[dict]

    Generic executor for any operation in the manifest.  Routes all HTTP

    through core.queue.esi_req.esi_request — never calls requests directly.



  execute_tag(tag, owner_id, ...) -> list[dict]

    Convenience batch runner for all GET operations in a tag.



  validate_write(operation_id, path_params, json_body) -> list[str]

    Lightweight pre-dispatch validation for write routes.

    Returns a list of error strings; empty means valid.

"""

# ruff: noqa

from __future__ import annotations



import re

from typing import Any



from core.esi.generated.manifest import OPERATIONS, COMPATIBILITY_DATE, ALL_SCOPES





RESPONSE_CONTRACT_KEYS = ("route", "url", "status_code", "headers", "body", "queue_channel")



ESI_BASE_URL = "https://esi.evetech.net"





class OperationNotFound(KeyError):

    """Raised when an operation_id is not in the manifest."""





class MissingPathParam(ValueError):

    """Raised when a required path parameter is absent."""





class AuthRequired(PermissionError):

    """Raised when a token is required but not supplied."""





class ValidationError(ValueError):

    """Raised by validate_write when the request body is structurally invalid."""





# -- Path building -------------------------------------------------------------



def build_path(operation_id: str, path_params: dict[str, Any] | None = None) -> str:

    op = OPERATIONS.get(operation_id)

    if op is None:

        raise OperationNotFound(operation_id)

    template: str = op["path"]

    values = path_params or {}

    missing: list[str] = []



    def _replace(m: re.Match[str]) -> str:

        k = m.group(1)

        if k not in values:

            missing.append(k)

            return m.group(0)

        return str(values[k])



    resolved = re.sub(r"\{([^}]+)\}", _replace, template)

    if missing:

        raise MissingPathParam(

            f"Operation {operation_id!r} is missing path params: {missing}"

        )

    return resolved





# -- Validation ----------------------------------------------------------------



def validate_write(

    operation_id: str,

    path_params: dict[str, Any] | None = None,

    json_body: Any = None,

) -> list[str]:

    """

    Validate a write (POST/PUT/DELETE/PATCH) operation before dispatch.

    Returns a list of error strings; empty list means the request looks valid.

    """

    op = OPERATIONS.get(operation_id)

    if op is None:

        return [f"Unknown operation: {operation_id!r}"]



    errors: list[str] = []

    method = op.get("method", "GET")

    if method == "GET":

        errors.append(f"{operation_id!r} is a GET operation — use execute_operation instead.")



    # Check all required path params are present

    for p in op.get("parameters", []):

        if p.get("in") == "path" and p.get("required") and p.get("name"):

            name = p["name"]

            if not path_params or name not in path_params:

                errors.append(f"Missing required path param: {name!r}")



    # Check request body schema refs

    body_refs = op.get("request_body_schema_refs") or []

    if body_refs and json_body is None:

        errors.append(f"Operation {operation_id!r} requires a request body.")



    return errors





# -- Core executor -------------------------------------------------------------



def execute_operation(

    operation_id: str,

    *,

    path_params: dict[str, Any] | None = None,

    query_params: dict[str, Any] | None = None,

    json_body: Any = None,

    token: str | None = None,

    headers: dict[str, str] | None = None,

    page: int | None = None,

) -> dict:

    """

    Execute a single ESI operation and return the standardised response dict.



    Response dict keys: route, url, status_code, headers, body, queue_channel.

    All HTTP goes through core.queue.esi_req.esi_request.

    """

    from core.queue.esi_req import esi_request



    op = OPERATIONS.get(operation_id)

    if op is None:

        raise OperationNotFound(operation_id)



    if op.get("requires_auth") and not token:

        raise AuthRequired(

            f"{operation_id!r} requires authentication but no token was provided."

        )



    resolved_path = build_path(operation_id, path_params)



    req_headers: dict[str, str] = {"Accept": "application/json", **(headers or {})}

    req_headers.setdefault("X-Compatibility-Date", COMPATIBILITY_DATE)

    req_headers.setdefault("X-Tenant", "tranquility")

    if token:

        req_headers["Authorization"] = f"Bearer {token}"



    params = dict(query_params or {})

    if page is not None and op.get("pagination", {}).get("has_page_param"):

        params["page"] = page



    response = esi_request(

        op["method"],

        f"{ESI_BASE_URL}{resolved_path}",

        params=params or None,

        json=json_body,

        headers=req_headers,

    )



    content_type = response.headers.get("Content-Type", "")

    if "application/json" in content_type:

        try:

            body = response.json() if response.content else None

        except ValueError:

            body = response.text

    else:

        body = response.text



    return {

        "route": op,

        "url": response.url,

        "status_code": response.status_code,

        "headers": dict(response.headers),

        "body": body,

        "queue_channel": op.get("queue_channel", "public"),

    }





def fetch_all_pages(

    operation_id: str,

    *,

    path_params: dict[str, Any] | None = None,

    query_params: dict[str, Any] | None = None,

    token: str | None = None,

    headers: dict[str, str] | None = None,

) -> list:

    """

    Fetch all pages for a paginated operation and return the concatenated list.

    Returns [] on 403/404.  Raises on 401.

    """

    op = OPERATIONS.get(operation_id)

    if op is None:

        raise OperationNotFound(operation_id)



    has_pages = op.get("pagination", {}).get("has_page_param", False)



    r1 = execute_operation(

        operation_id,

        path_params=path_params,

        query_params=query_params,

        token=token,

        headers=headers,

        page=1 if has_pages else None,

    )

    status = r1["status_code"]

    if status == 401:

        raise AuthRequired(f"401 for {operation_id!r}")

    if status in (403, 404):

        return []

    if not (200 <= status < 300):

        return []



    body = r1["body"]

    if not isinstance(body, list):

        return [body] if body is not None else []



    if not has_pages:

        return body



    total_pages = int(r1["headers"].get("X-Pages", 1))

    results: list = list(body)

    for page in range(2, total_pages + 1):

        rn = execute_operation(

            operation_id,

            path_params=path_params,

            query_params=query_params,

            token=token,

            headers=headers,

            page=page,

        )

        if not (200 <= rn["status_code"] < 300):

            break

        if isinstance(rn["body"], list):

            results.extend(rn["body"])



    return results





def execute_tag_batch(

    tag: str,

    *,

    token: str | None = None,

    path_params: dict[str, Any] | None = None,

    method_filter: str = "GET",

) -> list[dict]:

    """

    Execute all operations with the given tag and optional method filter.

    Each result is a standardised response dict with an added 'operation_id' key.

    Skips operations that require auth when no token is supplied.

    """

    from core.esi.generated.manifest import OPERATIONS_BY_TAG

    results: list[dict] = []

    for op_id in OPERATIONS_BY_TAG.get(tag, []):

        op = OPERATIONS[op_id]

        if method_filter and op.get("method") != method_filter:

            continue

        if op.get("requires_auth") and not token:

            continue

        try:

            r = fetch_all_pages(op_id, token=token, path_params=path_params)

            results.append({"operation_id": op_id, "data": r, "error": None})

        except Exception as exc:

            results.append({"operation_id": op_id, "data": None, "error": str(exc)})

    return results

