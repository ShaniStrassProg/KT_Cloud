import os
import json
import aiofiles
from datetime import datetime


class MetadataManager:
    def __init__(self, metadata_file='metadata.json'):
        self.metadata_file = metadata_file
        self.metadata = self.load_metadata()


    def load_metadata(self):
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {"server": {"buckets": {}}}

    async def save_metadata(self, is_sync=True):
        if is_sync:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=4, ensure_ascii=False)
        else:
            async with aiofiles.open(self.metadata_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.metadata, indent=4, ensure_ascii=False))

    def get_bucket_metadata(self, bucket, key):
        return self.metadata["server"]["buckets"].get(bucket, {}).get("objects", {}).get(key, None)

    async def update_metadata(self, bucket, key, version_id, data, is_sync=True):
        if bucket not in self.metadata["server"]["buckets"]:
            self.metadata["server"]["buckets"][bucket] = {"objects": {}}
        if key not in self.metadata["server"]["buckets"][bucket]["objects"]:
            self.metadata["server"]["buckets"][bucket]["objects"][key] = {'versions': {}}
        self.metadata["server"]["buckets"][bucket]["objects"][key]['versions'][version_id] = data
        if is_sync:
            await self.save_metadata(True)
        else:
            await self.save_metadata(False)

    async def delete_version(self, bucket, key, version_id, is_sync=True):
        bucket_data = self.metadata["server"]["buckets"].get(bucket, {})
        if key in bucket_data.get("objects", {}) and version_id in bucket_data["objects"][key]["versions"]:
            del self.metadata["server"]["buckets"][bucket]["objects"][key]["versions"][version_id]
            if not self.metadata["server"]["buckets"][bucket]["objects"][key]["versions"]:
                del self.metadata["server"]["buckets"][bucket]["objects"][key]
            if is_sync:
                await self.save_metadata(True)
            else:
                await self.save_metadata(False)
            return True
        return False

    async def delete_object(self, bucket, key, is_sync=True):
        if bucket in self.metadata["server"]["buckets"] and key in self.metadata["server"]["buckets"][bucket][
            "objects"]:
            del self.metadata["server"]["buckets"][bucket]["objects"][key]
            if is_sync:
                await self.save_metadata(True)
            else:
                await self.save_metadata(False)
            return True
        return False

    def get_latest_version(self, bucket, key):
        metadata = self.get_bucket_metadata(bucket, key)
        if metadata and "versions" in metadata:
            return max(metadata["versions"].keys(), key=int)
        else:
            raise FileNotFoundError(f"No versions found for object {key} in bucket {bucket}")

    async def copy_metadata(self, source_bucket, source_key, destination_bucket, destination_key, is_sync=True):
        source_metadata = self.get_bucket_metadata(source_bucket, source_key)
        if not source_metadata:
            raise FileNotFoundError(f"Source object {source_bucket}/{source_key} not found")

        latest_version = self.get_latest_version(source_bucket, source_key)
        source_version_metadata = source_metadata['versions'][latest_version]

        # Prepare destination metadata
        destination_metadata = source_version_metadata.copy()
        destination_metadata['etag'] = 'newetag'  # Generate a new ETag as necessary
        destination_metadata['lastModified'] = datetime.utcnow().isoformat() + 'Z'

        # Update destination metadata
        await self.update_metadata(destination_bucket, destination_key, '1', destination_metadata, is_sync=is_sync)

    async def check_permissions(self, bucket, key, version_id, by_pass_governance_retention, is_sync=True):
        metadata = self.get_bucket_metadata(bucket, key)
        if metadata and version_id in metadata['versions']:
            version_metadata = metadata['versions'][version_id]
            legal_hold = version_metadata.get('legalHold', False)
            retention_mode = version_metadata.get('retention', {}).get('mode', 'NONE')
            retain_until_date = version_metadata.get('retention', {}).get('retainUntilDate', None)

            # Check Legal Hold
            if legal_hold:
                raise PermissionError(
                    f"Version {version_id} of object {key} in bucket {bucket} is under legal hold and cannot be deleted")

            # Check Retention
            if retention_mode == 'COMPLIANCE' and not by_pass_governance_retention:
                if retain_until_date and datetime.utcnow() < datetime.fromisoformat(
                        retain_until_date.replace('Z', '+00:00')):
                    raise PermissionError(
                        f"Version {version_id} of object {key} in bucket {bucket} is under Compliance Retention and cannot be deleted until {retain_until_date}")

            return True
        return False
