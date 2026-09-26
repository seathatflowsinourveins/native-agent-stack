#!/usr/bin/env python3
"""Thin async-aware glue for MIRIX main-branch pin (8cb06a62).

Upstream's own samples/generate_demo_api_key.py calls
OrganizationManager/ClientManager methods synchronously, but on this commit
those methods are `async def` (unlike the v0.1.6 release tag, where they were
sync). The unmodified script therefore never awaits its own calls and silently
does nothing (RuntimeWarning: coroutine ... was never awaited).

This wrapper calls the exact same unmodified upstream classes/methods
(mirix.services.organization_manager.OrganizationManager,
mirix.services.client_manager.ClientManager, mirix.security.api_keys.generate_api_key)
with the same demo org/client ids, just correctly awaited via asyncio.run().
No memory/evaluation logic lives here.
"""
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "mirix-main-src"))

from mirix.security.api_keys import generate_api_key
from mirix.services.client_manager import ClientManager
from mirix.services.organization_manager import OrganizationManager
from mirix.schemas.client import Client as PydanticClient
from mirix.schemas.organization import Organization as PydanticOrganization

ORG_ID = "demo-org"
ORG_NAME = "Demo Org"
CLIENT_ID = "demo-client-id"


async def main():
    org_mgr = OrganizationManager()
    client_mgr = ClientManager()

    try:
        await org_mgr.get_organization_by_id(ORG_ID)
    except Exception:
        await org_mgr.create_organization(PydanticOrganization(id=ORG_ID, name=ORG_NAME))

    try:
        await client_mgr.get_client_by_id(CLIENT_ID)
    except Exception:
        await client_mgr.create_client(
            PydanticClient(
                id=CLIENT_ID,
                name="Demo Client",
                organization_id=ORG_ID,
                write_scope="read_write",
                read_scopes=["read_write"],
            )
        )

    api_key = generate_api_key()
    rec = await client_mgr.create_client_api_key(CLIENT_ID, api_key, name="Demo API Key")
    print("Client ID:     ", CLIENT_ID)
    print("Org ID:        ", ORG_ID)
    print("API Key:       ", api_key)
    print("API Key ID:    ", rec.id)
    print("API Key Status:", rec.status)


if __name__ == "__main__":
    asyncio.run(main())
