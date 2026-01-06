# ARC-89: ASA Metadata Registry

## ASA Metadata Registry Reference Implementation

The ASA Metadata Registry implements the [ARC-89 specification](https://github.com/cusma/ARCs/blob/arc89/ARCs/arc-0089.md)
in Algorand Python.

The reference implementation produces the [ARC-56 App Spec](https://github.com/algorandfoundation/arc89/blob/main/smart_contracts/artifacts/asa_metadata_registry/AsaMetadataRegistry.arc56.json),
which can be used by AlgoKit to generate the App Client in Python or TypeScript:

```shell
algokit generate client -l [python|typescript]
```

## ASA Metadata Registry Python SDK

A typed Python SDK for interacting with the ASA Metadata Registry singleton application.

It supports:

- **Box reconstruction (Algod)**: fetch and parse the asset metadata box directly (fast; 1 request).
- **AVM parity (simulate)**: call ARC-4 getters via `simulate()` for smart-contract-parity results.
- **Write module**: create / replace / delete metadata and manage flags, automatically chunking payloads.

> The SDK wraps the AlgoKit **generated App Client** (ARC-56) for simulation and
> writes, so the AppClient can be regenerated without rewriting the rest of the SDK.

### Install

```bash
pip install asa-metadata-registry
```

### Quick start

The following examples use the TestNet deployment of the ASA Metadata Registry and
assume `CALLER_MNEMONIC` environment variable is set for the AVM interactions.

#### Algod read

```python
from algokit_utils import AlgorandClient
from asa_metadata_registry import DEFAULT_DEPLOYMENTS, AsaMetadataRegistry, MetadataSource

algorand_client = AlgorandClient.testnet()
testnet_deployment = DEFAULT_DEPLOYMENTS["testnet"]

registry = AsaMetadataRegistry.from_algod(
    algod=algorand_client.client.algod,
    app_id=testnet_deployment.app_id
)

record = registry.read.get_asset_metadata(asset_id=753203561, source=MetadataSource.BOX)
print(record.header.metadata_hash.hex())
print(record.json.get("name"))
```

#### AVM-parity read (simulate)

```python
from algokit_utils import AlgorandClient
from asa_metadata_registry import DEFAULT_DEPLOYMENTS, AsaMetadataRegistry
from asa_metadata_registry._generated.asa_metadata_registry_client import AsaMetadataRegistryClient

algorand_client = AlgorandClient.testnet()
testnet_deployment = DEFAULT_DEPLOYMENTS["testnet"]
caller = algorand_client.account.from_environment(name="CALLER")

testnet_app_client = algorand_client.client.get_typed_app_client_by_id(
    AsaMetadataRegistryClient,
    app_id=testnet_deployment.app_id,
    default_sender=caller.address,
    default_signer=caller.signer,
)
registry = AsaMetadataRegistry.from_app_client(testnet_app_client)

header = registry.read.avm().arc89_get_metadata_header(asset_id=753203561)
page0 = registry.read.avm().arc89_get_metadata(asset_id=753203561, page=0)

print(header)
print(page0.page_content)
```

#### Write (create metadata)

```python
from algokit_utils import AlgorandClient, AssetCreateParams
from asa_metadata_registry import DEFAULT_DEPLOYMENTS, Arc90Uri, AsaMetadataRegistry, AssetMetadata
from asa_metadata_registry._generated.asa_metadata_registry_client import AsaMetadataRegistryClient


algorand_client = AlgorandClient.testnet()
testnet_deployment = DEFAULT_DEPLOYMENTS["testnet"]
caller = algorand_client.account.from_environment(name="CALLER")

testnet_app_client = algorand_client.client.get_typed_app_client_by_id(
    AsaMetadataRegistryClient,
    app_id=testnet_deployment.app_id,
    default_sender=caller.address,
    default_signer=caller.signer,
)
registry = AsaMetadataRegistry.from_app_client(testnet_app_client)

arc89_partial_uri = Arc90Uri(
        netauth=testnet_deployment.arc90_uri_netauth,
        app_id=testnet_app_client.app_id,
        box_name=None,
    ).to_uri()

asset_id = algorand_client.send.asset_create(
  params=AssetCreateParams(
    sender=caller.address,
    total=1,
    asset_name="Dante Alighieri",
    unit_name="DANTE",
    url=arc89_partial_uri,
    decimals=0,
    manager=caller.address,
    )
).asset_id

metadata = AssetMetadata.from_json(
    asset_id=asset_id,
    json_obj={"name": "Dante", "description": "Sommo Poeta"},
)

mbr_delta = registry.write.create_metadata(asset_manager=caller, metadata=metadata)
print(mbr_delta)
```
