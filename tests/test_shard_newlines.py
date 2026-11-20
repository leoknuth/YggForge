import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from knowledge.shard_store import SortedShardStore


class ShardNewlineTests(unittest.TestCase):
    def test_shared_index_bytes_are_utf8_lf_and_manifest_sizes_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = SortedShardStore(root, 10000, 100, 10000)
            records = {"金融": "现金流", "法律": "合同"}
            manifest = store.write_records(records, source_digest="shared-source")
            expected = "".join(key + "\t" + value + "\n" for key, value in sorted(records.items())).encode("utf-8")
            actual = (root / "_all.tsv").read_bytes()
            self.assertEqual(actual, expected)
            self.assertNotIn(b"\r", actual)
            manifest_bytes = (root / "manifest.json").read_bytes()
            self.assertNotIn(b"\r", manifest_bytes)
            self.assertEqual(manifest["total_bytes"], len(expected))
            self.assertEqual(manifest["files"][0]["bytes"], len(expected))
            self.assertEqual(json.loads(manifest_bytes), manifest)


if __name__ == "__main__":
    unittest.main()
