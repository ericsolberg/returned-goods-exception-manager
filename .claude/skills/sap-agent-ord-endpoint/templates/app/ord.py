import json
import logging
import os
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logger = logging.getLogger(__name__)

# Paths to the ORD documents (stored as static JSON files in app/ord/)
ORD_BASE_PATH = Path(__file__).parent / "ord"
ORD_SYSTEM_VERSION_PATH = ORD_BASE_PATH / "document-system-version.json"
ORD_SYSTEM_INSTANCE_PATH = ORD_BASE_PATH / "document-system-instance.json"


def load_ord_document(path: Path) -> dict:
    """
    Load an ORD document from disk.

    Args:
        path: Path to the JSON document file

    Returns:
        Dict containing the ORD document

    Raises:
        FileNotFoundError: If document file cannot be found
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load ORD document from {path}: {e}")
        raise


def inject_base_url(document: dict, base_url: str) -> dict:
    """
    Inject the runtime base URL into the ORD document.

    Replaces the {{AGENT_BASE_URL}} placeholder with the actual URL
    from the AGENT_PUBLIC_URL environment variable at request time.
    This ensures the ORD document always contains the correct provider
    tenant URL without requiring manual updates to the JSON files.
    """
    doc_str = json.dumps(document)
    doc_str = doc_str.replace("{{AGENT_BASE_URL}}", base_url)
    return json.loads(doc_str)


async def well_known_ord_config(request: Request) -> JSONResponse:
    """
    ORD Configuration endpoint (well-known endpoint).

    GET /.well-known/open-resource-discovery

    Entry point for ORD discovery. Returns the locations of both ORD documents:
    - system-version: describes the system type and version (static, open access)
    - system-instance: describes a specific tenant instance (dynamic, tenant-aware)

    This endpoint is open (no authentication required) so UMS can discover
    the agent's ORD documents using provider tenant credentials.
    """
    config = {
        "openResourceDiscoveryV1": {
            "documents": [
                {
                    "url": "/open-resource-discovery/v1/documents/system-version",
                    "accessStrategies": [
                        {
                            "type": "open"
                        }
                    ],
                    "perspective": "system-version"
                },
                {
                    "url": "/open-resource-discovery/v1/documents/system-instance",
                    "accessStrategies": [
                        {
                            "type": "custom",
                            "customType": "sap.xref:open-global-tenant-id:v1",
                            "customDescription": "The metadata information is openly accessible but system instance aware.\nThe tenant is selected by providing a SAP global tenant ID header.\nTo understand how to use this access strategy, please read the documentation on the [ORD Reference App Access Strategies](https://github.com/open-resource-discovery/reference-application#access-strategies)."
                        },
                        {
                            "type": "custom",
                            "customType": "sap.xref:open-local-tenant-id:v1",
                            "customDescription": "The metadata information is openly accessible but system instance aware.\nThe tenant is selected by providing a local tenant ID header.\nTo understand how to use this access strategy, please read the documentation on the [ORD Reference App Access Strategies](https://github.com/open-resource-discovery/reference-application#access-strategies)."
                        }
                    ],
                    "perspective": "system-instance"
                }
            ]
        }
    }

    logger.info("ORD well-known config requested")
    return JSONResponse(
        content=config,
        media_type="application/json;charset=UTF-8",
        headers={"Cache-Control": "max-age=300"}
    )


async def ord_document_system_version(request: Request) -> JSONResponse:
    """
    ORD system-version document endpoint.

    GET /open-resource-discovery/v1/documents/system-version

    Returns the static ORD document that describes the agent's APIs, capabilities,
    and metadata at the system (provider) level. Loaded from
    app/ord/document-system-version.json.
    """
    try:
        base_url = os.environ.get("AGENT_PUBLIC_URL", str(request.base_url).rstrip("/"))
        document = load_ord_document(ORD_SYSTEM_VERSION_PATH)
        document = inject_base_url(document, base_url)

        logger.info("Serving ORD system-version document")
        return JSONResponse(
            content=document,
            media_type="application/json;charset=UTF-8",
            headers={"Cache-Control": "max-age=300"}
        )
    except Exception as e:
        logger.error(f"Error serving ORD system-version document: {e}")
        return JSONResponse(
            content={"error": "Failed to load ORD document"},
            status_code=500
        )


def resolve_tenant_id(request: Request) -> str:
    """
    Resolve the local tenant ID from the request.

    Query parameters take priority over headers, matching the ORD reference app behaviour.
    Supported inputs (in priority order):
      1. Query param  ?local-tenant-id=T1
      2. Header       local-tenant-id: T1

    Returns an empty string if no tenant ID is found.
    """
    return (
        request.query_params.get("local-tenant-id")
        or request.headers.get("local-tenant-id", "")
    )


async def ord_document_system_instance(request: Request) -> JSONResponse:
    """
    ORD system-instance document endpoint.

    GET /open-resource-discovery/v1/documents/system-instance

    Returns the dynamic ORD document that describes the agent's APIs and metadata
    for a specific tenant instance. The tenant ID is resolved from the request
    (query param takes priority over header) and injected into
    `describedSystemInstance.localId`. Loaded from app/ord/document-system-instance.json.

    Examples:
        GET /open-resource-discovery/v1/documents/system-instance?local-tenant-id=T1
        GET /open-resource-discovery/v1/documents/system-instance  (with header: local-tenant-id: T1)
    """
    try:
        base_url = os.environ.get("AGENT_PUBLIC_URL", str(request.base_url).rstrip("/"))
        local_tenant_id = resolve_tenant_id(request)

        document = load_ord_document(ORD_SYSTEM_INSTANCE_PATH)
        document = inject_base_url(document, base_url)

        # Inject the tenant ID into describedSystemInstance.localId
        doc_str = json.dumps(document)
        doc_str = doc_str.replace("{{LOCAL_TENANT_ID}}", local_tenant_id)
        document = json.loads(doc_str)

        logger.info(f"Serving ORD system-instance document, local_tenant_id={local_tenant_id!r}")
        return JSONResponse(
            content=document,
            media_type="application/json;charset=UTF-8",
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        logger.error(f"Error serving ORD system-instance document: {e}")
        return JSONResponse(
            content={"error": "Failed to load ORD document"},
            status_code=500
        )


def create_ord_routes() -> list:
    """
    Create ORD routes for the application.

    Returns a list of Starlette Route objects for the ORD endpoints.
    Mount these routes before the A2A app in main.py:

        combined_app = Starlette(
            routes=[
                *create_ord_routes(),
                Mount("/", app=a2a_app),
            ]
        )

    Endpoints:
        /.well-known/open-resource-discovery                           — ORD config (lists both documents)
        /open-resource-discovery/v1/documents/system-version           — static ORD document
        /open-resource-discovery/v1/documents/system-instance          — dynamic ORD document (tenant-aware)
    """
    return [
        Route(
            "/.well-known/open-resource-discovery",
            well_known_ord_config,
            methods=["GET"],
            name="ord_config"
        ),
        Route(
            "/open-resource-discovery/v1/documents/system-version",
            ord_document_system_version,
            methods=["GET"],
            name="ord_document_system_version"
        ),
        Route(
            "/open-resource-discovery/v1/documents/system-instance",
            ord_document_system_instance,
            methods=["GET"],
            name="ord_document_system_instance"
        ),
    ]