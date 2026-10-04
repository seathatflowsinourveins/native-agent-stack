#!/usr/bin/env python3
"""Awaited demo-key helper for the MIRIX main-branch pin (8cb06a62), fixed so the key is never printed.

The as-run version printed the generated API key to the terminal and is not retained.
This version addresses CodeQL py/clear-text-logging-sensitive-data and adapts upstream
samples/generate_demo_api_key.py at 8cb06a62bbb7c478beb33dd4f2815696a72df482;
see ../../security-repair-sources.md. It makes the same unmodified upstream calls
(OrganizationManager, ClientManager, generate_api_key, with the same demo organization and
client ids), awaited via asyncio.run(), but never prints or logs the key. Before any MIRIX call
it creates the file named by --key-file with O_CREAT|O_EXCL|O_NOFOLLOW and mode
0600 (fchmod'ed, so the umask cannot widen or narrow it); an existing file or symlink there
is refused. It then writes the key and a newline to that file and prints only the client id,
organization id and destination path. If any MIRIX call fails,
the file it created is removed.

Usage: python gen_key_main.py --key-file PATH [--mirix-src DIR]
       then, for example, read the key from PATH into MIRIX_API_KEY in the client's shell.
"""
import argparse
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
ORG_ID = "demo-org"
ORG_NAME = "Demo Org"
CLIENT_ID = "demo-client-id"


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Create the MIRIX demo client and store a new API key in a 0600 file.")
    parser.add_argument("--key-file", dest="destination", required=True,
                        help="path of a new file (it must not exist) that receives the key, mode 0600")
    parser.add_argument("--mirix-src", default=os.path.join(PROJECT_ROOT, "mirix-main-src"),
                        help="MIRIX source checkout at the pinned commit (default: mirix-main-src next to this file)")
    return parser.parse_args(argv)


def create_private_file(destination):
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
    except BaseException:
        os.close(descriptor)
        os.unlink(destination)
        raise
    return descriptor


def write_all(descriptor, data):
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if written == 0:
            raise OSError("key file write made no progress")
        view = view[written:]
    os.fsync(descriptor)


async def main(args):
    sys.path.insert(0, args.mirix_src)
    from mirix.security.api_keys import generate_api_key
    from mirix.services.client_manager import ClientManager
    from mirix.services.organization_manager import OrganizationManager
    from mirix.schemas.client import Client as PydanticClient
    from mirix.schemas.organization import Organization as PydanticOrganization

    descriptor = create_private_file(args.destination)
    try:
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
        await client_mgr.create_client_api_key(CLIENT_ID, api_key, name="Demo API Key")
        write_all(descriptor, (api_key + "\n").encode("utf-8"))
    except BaseException:
        os.close(descriptor)
        os.unlink(args.destination)
        raise
    os.close(descriptor)
    print("Client ID:     ", CLIENT_ID)
    print("Org ID:        ", ORG_ID)
    print("Key written to:", args.destination, "(mode 0600)")


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    try:
        asyncio.run(main(args))
    except Exception:
        # Upstream exception messages can contain the key; never echo or log them.
        print("Key creation failed; no key value was printed. Check the destination and MIRIX setup.",
              file=sys.stderr)
        sys.exit(1)
