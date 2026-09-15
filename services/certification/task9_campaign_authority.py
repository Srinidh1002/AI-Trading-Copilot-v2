from services.contracts.task9_campaign_manifest_v1 import Task9CampaignManifestV1,Task9ActiveCampaignPointerV1,Task9CampaignStatus,Task9ActiveCampaignPointerStatus


def validate_task9_campaign_pointer_compatibility(
    manifest,
    pointer,
    *,
    require_runtime_config_provenance_match=True,
):
    if (
        type(manifest) is not Task9CampaignManifestV1
        or type(pointer) is not Task9ActiveCampaignPointerV1
    ):
        raise TypeError("campaign authority")

    if (
        manifest.campaign_id,
        manifest.registry_root,
        manifest.campaign_root,
    ) != (
        pointer.campaign_id,
        pointer.registry_root,
        pointer.campaign_root,
    ):
        raise ValueError("campaign pointer mismatch")

    if (
        manifest.campaign_status
        in {
            Task9CampaignStatus.COMPLETED,
            Task9CampaignStatus.INVALID,
        }
        and pointer.status
        is Task9ActiveCampaignPointerStatus.ACTIVE
    ):
        raise ValueError("campaign cannot continue")

    if type(require_runtime_config_provenance_match) is not bool:
        raise TypeError(
            "require_runtime_config_provenance_match"
        )

    if (
        require_runtime_config_provenance_match
        and (
            manifest.runtime_config_snapshot_id,
            manifest.runtime_config_sha256,
        )
        != (
            pointer.runtime_config_snapshot_id,
            pointer.runtime_config_sha256,
        )
    ):
        raise ValueError(
            "runtime config provenance mismatch"
        )

    return True
